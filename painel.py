"""Spec do painel analítico Olist.

LEITURA
-------
``ler(marts)`` retorna um dicionário nome -> DataFrame. Para cada nome, a
única consulta é ``SELECT * FROM marts.<nome>``. A conexão usa
``duckdb.connect("olist.duckdb", read_only=True)`` e é aberta e fechada dentro
da função: uma conexão persistente mantém um lock e impede o pipeline de
escrever no banco enquanto o painel está aberto. O app lê os marts
``vendas_mensais``, ``top_categorias``, ``entrega_no_prazo``,
``nota_por_categoria``, ``recompra``, ``ticket_medio_por_estado``,
``mix_pagamento``, ``vendedores_pareto``, ``kpis`` e ``clientes_por_uf``.

REGRAS DE NEGÓCIO
-----------------
O painel não agrega dados nem deriva métricas: só apresenta valores existentes
nos marts. Não há agregações, junções ou operações aritméticas entre colunas.
Assim, cada novo número exige sua definição no SQL, que é a fonte de verdade.
A única exceção é a recompra, exibida como 100 menos ``pct_clientes`` da linha
``pedidos_por_cliente = 1`` do mart ``recompra``.

LAYOUT
------
O app usa ``layout="wide"``. No cabeçalho, o título fica à esquerda e o filtro
de período à direita. A primeira faixa contém, nesta ordem, Ticket médio
(``kpis.ticket_medio``, reais), Cancelados (``kpis.pct_cancelados``, percentual
de todos os pedidos, duas casas), Peso do frete (``kpis.pct_frete``, uma casa),
Recompra (duas casas), No prazo (``entrega_no_prazo.pct_no_prazo``, uma casa),
Dias até entregar (``kpis.dias_entrega``, uma casa) e Nota média
(``kpis.nota_media``, duas casas). A seguir há faturamento mensal em linha com
marcadores, depois receita por categoria (dez maiores, barras horizontais,
maior no topo), mix de pagamento (barras por ``pct_valor``) e ticket médio por
UF (barras horizontais, maior no topo). A última faixa mostra clientes por UF
(barras horizontais, maior no topo), as dez primeiras notas por
``posicao_pior`` (pontos, pior no topo) e concentração de vendedores (linha de
``pct_acumulado`` por ``posicao``, com linha tracejada em 80).

Cada gráfico tem título com o número do mart, uma cor de dados e eixos com
unidades. A referência tracejada de 80% é a exceção visual necessária no
gráfico de vendedores. O Streamlit usa ``width="stretch"`` para todos os
gráficos.

FORMATAÇÃO E FIGURAS
--------------------
``reais(valor, casas=2)``, ``pct(valor, casas=1)`` e
``numero(valor, casas=0)`` são funções puras com separadores fixos: ponto para
milhar e vírgula para decimal, sem depender do locale da máquina. Exemplos:
``R$ 1.003.862,14``, ``93,2%`` e ``96.470``. Cada gráfico é construído por
uma função que recebe um DataFrame e devolve uma figura Plotly; isso permite
reutilizá-la em relatórios HTML.

FILTRO
------
O ``st.select_slider`` oferece os meses existentes em ``vendas_mensais`` e
abre de janeiro de 2017 a agosto de 2018: 20 meses, dos 24 disponíveis quando
o seletor cobre as duas pontas. Ele filtra apenas as linhas do gráfico mensal;
cartões e demais gráficos sempre representam o período inteiro, como informa
a legenda abaixo do filtro, evitando recalcular métricas fora do SQL.

CACHE E FALHAS
--------------
A leitura é cacheada com ``st.cache_data`` e o botão "Recarregar dados" limpa
esse cache. Se ``olist.duckdb`` ou qualquer mart usado pelo painel faltar, o
app informa o que está ausente, mostra ``uv run python -m pipeline.marts`` e
interrompe a página com ``st.stop()``.

CRITÉRIOS DE ACEITE
-------------------
Os cartões mostram ``R$ 137,42``, ``0,63%``, ``14,2%``, ``3,04%``, ``93,2%``,
``12,5`` e ``4,09``. O gráfico mensal abre com 20 linhas e pode mostrar 24.
No top 10 de categorias, ``health_beauty`` aparece no topo; em notas,
``office_furniture``; no ticket por UF, ``PB`` fica no topo e ``SP`` embaixo.
Com o painel ativo, ``uv run python -m pipeline.marts`` deve gravar sem erro
de lock.
"""

from collections.abc import Iterable
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


COR_DADOS = "#286C91"


class MartsAusentesError(Exception):
    """Indica quais tabelas analíticas não foram encontradas."""

    def __init__(self, marts: list[str]):
        self.marts = marts
        super().__init__(", ".join(marts))


def ler(marts: Iterable[str]) -> dict[str, pd.DataFrame]:
    """Lê os marts solicitados e sempre libera a conexão com o banco."""
    conexao = duckdb.connect("olist.duckdb", read_only=True)
    dados = {}
    ausentes = []
    try:
        for nome in marts:
            try:
                dados[nome] = conexao.execute(
                    f"SELECT * FROM marts.{nome}"
                ).fetchdf()
            except duckdb.CatalogException as erro:
                if "does not exist" not in str(erro):
                    raise
                ausentes.append(nome)
    finally:
        conexao.close()

    if ausentes:
        raise MartsAusentesError(ausentes)
    return dados


def _separadores_br(valor: float, casas: int) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.translate(str.maketrans({",": ".", ".": ","}))


def reais(valor: float, casas: int = 2) -> str:
    return f"R$ {_separadores_br(valor, casas)}"


def pct(valor: float, casas: int = 1) -> str:
    return f"{_separadores_br(valor, casas)}%"


def numero(valor: float, casas: int = 0) -> str:
    return _separadores_br(valor, casas)


def _ajustar_figura(figura: go.Figure) -> go.Figure:
    figura.update_layout(
        separators=",.",
        margin={"l": 12, "r": 12, "t": 58, "b": 12},
    )
    return figura


def grafico_vendas_mensais(df: pd.DataFrame) -> go.Figure:
    figura = px.line(
        df,
        x="mes",
        y="receita",
        markers=True,
        title="01 · Faturamento mensal",
        labels={"mes": "Mês", "receita": "Receita (R$)"},
        color_discrete_sequence=[COR_DADOS],
    )
    figura.update_yaxes(tickprefix="R$ ")
    return _ajustar_figura(figura)


def grafico_top_categorias(df: pd.DataFrame) -> go.Figure:
    top = df.nlargest(10, "receita").sort_values("receita", ascending=True)
    figura = px.bar(
        top,
        x="receita",
        y="categoria",
        orientation="h",
        title="02 · Receita por categoria",
        labels={"receita": "Receita (R$)", "categoria": "Categoria"},
        color_discrete_sequence=[COR_DADOS],
    )
    figura.update_xaxes(tickprefix="R$ ")
    return _ajustar_figura(figura)


def grafico_mix_pagamento(df: pd.DataFrame) -> go.Figure:
    figura = px.bar(
        df,
        x="tipo",
        y="pct_valor",
        title="07 · Mix de pagamento",
        labels={"tipo": "Tipo de pagamento", "pct_valor": "Valor (%)"},
        color_discrete_sequence=[COR_DADOS],
    )
    figura.update_yaxes(ticksuffix="%")
    return _ajustar_figura(figura)


def grafico_ticket_por_uf(df: pd.DataFrame) -> go.Figure:
    ordenado = df.sort_values("ticket_medio", ascending=True)
    figura = px.bar(
        ordenado,
        x="ticket_medio",
        y="uf",
        orientation="h",
        title="06 · Ticket médio por UF",
        labels={"ticket_medio": "Ticket médio (R$)", "uf": "UF"},
        color_discrete_sequence=[COR_DADOS],
    )
    figura.update_xaxes(tickprefix="R$ ")
    return _ajustar_figura(figura)


def grafico_clientes_por_uf(df: pd.DataFrame) -> go.Figure:
    ordenado = df.sort_values("clientes", ascending=True)
    figura = px.bar(
        ordenado,
        x="clientes",
        y="uf",
        orientation="h",
        title="12 · Clientes por UF",
        labels={"clientes": "Clientes (pessoas)", "uf": "UF"},
        color_discrete_sequence=[COR_DADOS],
    )
    return _ajustar_figura(figura)


def grafico_nota_por_categoria(df: pd.DataFrame) -> go.Figure:
    piores = df.nsmallest(10, "posicao_pior").sort_values(
        "posicao_pior", ascending=False
    )
    figura = px.scatter(
        piores,
        x="nota_media",
        y="categoria",
        title="04 · Nota por categoria",
        labels={"nota_media": "Nota média (1–5)", "categoria": "Categoria"},
        color_discrete_sequence=[COR_DADOS],
    )
    figura.update_xaxes(range=[0, 5])
    return _ajustar_figura(figura)


def grafico_concentracao_vendedores(df: pd.DataFrame) -> go.Figure:
    figura = px.line(
        df.sort_values("posicao"),
        x="posicao",
        y="pct_acumulado",
        title="09 · Concentração de vendedores",
        labels={"posicao": "Posição do vendedor", "pct_acumulado": "Receita acumulada (%)"},
        color_discrete_sequence=[COR_DADOS],
    )
    figura.add_hline(
        y=80,
        line_dash="dash",
        line_color="#6B7280",
        annotation_text="80%",
    )
    figura.update_yaxes(ticksuffix="%")
    return _ajustar_figura(figura)


def banco_existe() -> bool:
    """Verifica a presença do arquivo esperado na raiz de execução."""
    return Path("olist.duckdb").is_file()
