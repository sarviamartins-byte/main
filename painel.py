"""Spec do painel Olist alinhada aos marts atuais em ``sql/marts/*.sql``.

LEITURA
-------
``ler(marts)`` retorna nome -> DataFrame e executa somente
``SELECT * FROM marts.<nome>`` para cada nome solicitado. Usa
``duckdb.connect("olist.duckdb", read_only=True)`` e fecha a conexão dentro
da função para não manter o lock que impediria o pipeline de gravar.
O app usa ``vendas_totais_mensais``, ``trimestre``, ``entrega_no_prazo``,
``nota_por_categoria``, ``venda_por_estado``, ``mix_pagamento``,
``vendedores_state``, ``kpis`` e ``clientes_unicos_por_mes``. Os marts
detalhados ``vendas_mensais`` (mês-vendedor) e ``clientes_por_mes``
(mês-cliente) permanecem no banco, mas não são plotados: agregá-los na camada
de apresentação violaria a regra de não calcular. O mart 09 lê
``raw.vendedores`` conforme sua consulta SQL atual; essa origem é uma
exceção ao padrão das demais consultas.

REGRAS DE NEGÓCIO
-----------------
O painel não agrega nem deriva valores: apresenta as colunas existentes,
permitindo ordenar e filtrar linhas para a visualização. As novas métricas e
grãos são definidos em SQL. Como o mart ``recompra`` foi substituído, não há
cartão de recompra: o painel mostra somente os seis indicadores disponíveis,
sem estimar um indicador a partir de outros dados.

LAYOUT
------
O app usa ``layout="wide"``. No cabeçalho, ficam o título à esquerda e o
filtro de período à direita. A primeira faixa tem seis cartões, nesta ordem:
Ticket médio (``kpis.ticket_medio``, reais), Cancelados (``kpis.pct_cancelados``,
percentual de todos os pedidos, duas casas), Peso do frete
(``kpis.pct_frete``, uma casa), No prazo
(``entrega_no_prazo.pct_no_prazo``, uma casa), Dias até entregar
(``kpis.dias_entrega``, uma casa) e Nota média (``kpis.nota_media``, duas
casas).

A faixa seguinte mostra faturamento mensal (``vendas_totais_mensais``, linha
com marcadores). A terceira faixa contém faturamento trimestral
(``trimestre``, linha com marcadores), mix de pagamento (``mix_pagamento``,
barras por ``pct_valor``) e receita por estado (``venda_por_estado``, barras
horizontais, maior no topo). A quarta faixa contém clientes por mês
(``clientes_unicos_por_mes``, linha com marcadores, distintos por
``cliente_id``), nota por categoria (dez primeiras por ``posicao_pior``,
pontos, pior no topo) e quantidade de vendedores por estado
(``vendedores_state``, barras horizontais, maior no topo). Os marts mensais
resumidos são SQL separado para evitar agregações na apresentação. As
substituições não reconstroem top categorias, recompra, ticket por UF,
clientes por UF ou Pareto.

Cada gráfico tem o número e o nome do mart no título, uma cor de dados e
unidades nos eixos. As funções de gráfico recebem DataFrame e devolvem figura
Plotly, sem Streamlit ou conexão ao banco, para serem reutilizadas no relatório.
O app usa ``width="stretch"``.

FORMATAÇÃO
----------
``reais(valor, casas=2)``, ``pct(valor, casas=1)`` e
``numero(valor, casas=0)`` são funções puras com milhar separado por ponto e
decimal por vírgula, sem depender do locale. Isso mantém o resultado igual
entre máquinas.

FILTRO
------
O ``st.select_slider`` oferece os meses de ``vendas_totais_mensais``, com
padrão jan/2017 a ago/2018. O intervalo filtra somente as linhas do gráfico
de faturamento mensal; cartões e outros gráficos cobrem o período inteiro. A
página informa isso abaixo do filtro.

CACHE E FALHAS
--------------
A leitura usa ``st.cache_data`` e o botão "Recarregar dados" limpa o cache.
Se ``olist.duckdb`` ou qualquer mart usado faltar, o app informa os nomes,
mostra ``uv run python -m pipeline.marts`` e chama ``st.stop()``.
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
        title="13 · Faturamento mensal",
        labels={"mes": "Mês", "receita": "Receita (R$)"},
        color_discrete_sequence=[COR_DADOS],
    )
    figura.update_yaxes(tickprefix="R$ ")
    return _ajustar_figura(figura)


def grafico_vendas_trimestrais(df: pd.DataFrame) -> go.Figure:
    figura = px.line(
        df.sort_values("trimestre"),
        x="trimestre",
        y="receita",
        markers=True,
        title="02 · Faturamento trimestral",
        labels={"trimestre": "Trimestre", "receita": "Receita (R$)"},
        color_discrete_sequence=[COR_DADOS],
    )
    figura.update_yaxes(tickprefix="R$ ")
    return _ajustar_figura(figura)


def grafico_receita_por_estado(df: pd.DataFrame) -> go.Figure:
    ordenado = df.sort_values("receita_total", ascending=True)
    figura = px.bar(
        ordenado,
        x="receita_total",
        y="estado",
        orientation="h",
        title="05 · Receita por estado",
        labels={"receita_total": "Receita (R$)", "estado": "Estado"},
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


def grafico_vendedores_por_estado(df: pd.DataFrame) -> go.Figure:
    ordenado = df.sort_values("total_vendedores", ascending=True)
    figura = px.bar(
        ordenado,
        x="total_vendedores",
        y="estado",
        orientation="h",
        title="09 · Vendedores por estado",
        labels={"total_vendedores": "Vendedores (pessoas)", "estado": "Estado"},
        color_discrete_sequence=[COR_DADOS],
    )
    return _ajustar_figura(figura)


def grafico_clientes_unicos_por_mes(df: pd.DataFrame) -> go.Figure:
    figura = px.line(
        df.sort_values("mes"),
        x="mes",
        y="clientes_unicos",
        markers=True,
        title="14 · Clientes únicos por mês",
        labels={"mes": "Mês", "clientes_unicos": "Clientes (cadastros)"},
        color_discrete_sequence=[COR_DADOS],
    )
    return _ajustar_figura(figura)


def grafico_nota_por_categoria(df: pd.DataFrame) -> go.Figure:
    piores = (
        df.sort_values("posicao_pior")
        .head(10)
        .sort_values("posicao_pior", ascending=False)
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


def banco_existe() -> bool:
    """Verifica a presença do arquivo esperado na raiz de execução."""
    return Path("olist.duckdb").is_file()
