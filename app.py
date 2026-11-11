from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from painel import (
    MartsAusentesError,
    grafico_clientes_por_uf,
    grafico_concentracao_vendedores,
    grafico_mix_pagamento,
    grafico_nota_por_categoria,
    grafico_ticket_por_uf,
    grafico_top_categorias,
    grafico_vendas_mensais,
    ler,
    numero,
    pct,
    reais,
)


MARTS = (
    "vendas_mensais",
    "top_categorias",
    "entrega_no_prazo",
    "nota_por_categoria",
    "recompra",
    "ticket_medio_por_estado",
    "mix_pagamento",
    "vendedores_pareto",
    "kpis",
    "clientes_por_uf",
)


@st.cache_data
def carregar_dados():
    return ler(MARTS)


def rotulo_mes(mes: date) -> str:
    return f"{mes.month:02d}/{mes.year}"


st.set_page_config(page_title="Olist · visão da operação", layout="wide")

if not Path("olist.duckdb").is_file():
    st.error(
        "O banco `olist.duckdb` não foi encontrado. "
        "Gere as tabelas com `uv run python -m pipeline.marts`."
    )
    st.stop()

try:
    dados = carregar_dados()
except MartsAusentesError as erro:
    st.error(
        f"Faltam estes marts: {', '.join(erro.marts)}. "
        "Gere as tabelas com `uv run python -m pipeline.marts`."
    )
    st.stop()

cabecalho, filtro = st.columns([1.5, 1])
with cabecalho:
    st.title("Olist · visão da operação")
    st.button("Recarregar dados", on_click=carregar_dados.clear)

meses = dados["vendas_mensais"]["mes"].tolist()
inicio_padrao = pd.Timestamp(date(2017, 1, 1))
fim_padrao = pd.Timestamp(date(2018, 8, 1))
if inicio_padrao not in meses or fim_padrao not in meses:
    st.error(
        "O mart `vendas_mensais` não contém os meses padrão "
        "jan/2017 e ago/2018."
    )
    st.stop()

with filtro:
    periodo = st.select_slider(
        "Período",
        options=meses,
        value=(inicio_padrao, fim_padrao),
        format_func=rotulo_mes,
    )
    st.caption("os cartões valem para o período inteiro")

kpis = dados["kpis"].iloc[0]
clientes_uma_compra = dados["recompra"].loc[
    dados["recompra"]["pedidos_por_cliente"] == 1, "pct_clientes"
].iloc[0]
valores_cartoes = (
    ("Ticket médio", reais(kpis["ticket_medio"])),
    ("Cancelados · % de todos os pedidos", pct(kpis["pct_cancelados"], 2)),
    ("Peso do frete", pct(kpis["pct_frete"], 1)),
    ("Recompra", pct(100 - clientes_uma_compra, 2)),
    (
        "No prazo",
        pct(dados["entrega_no_prazo"].iloc[0]["pct_no_prazo"], 1),
    ),
    ("Dias até entregar", numero(kpis["dias_entrega"], 1)),
    ("Nota média", numero(kpis["nota_media"], 2)),
)

cartoes = st.columns(7)
for coluna, (rotulo, valor) in zip(cartoes, valores_cartoes):
    coluna.metric(rotulo, valor)

inicio, fim = periodo
vendas_periodo = dados["vendas_mensais"].loc[
    dados["vendas_mensais"]["mes"].between(inicio, fim)
]
st.plotly_chart(grafico_vendas_mensais(vendas_periodo), width="stretch")

coluna_1, coluna_2, coluna_3 = st.columns(3)
with coluna_1:
    st.plotly_chart(grafico_top_categorias(dados["top_categorias"]), width="stretch")
with coluna_2:
    st.plotly_chart(grafico_mix_pagamento(dados["mix_pagamento"]), width="stretch")
with coluna_3:
    st.plotly_chart(
        grafico_ticket_por_uf(dados["ticket_medio_por_estado"]),
        width="stretch",
    )

coluna_1, coluna_2, coluna_3 = st.columns(3)
with coluna_1:
    st.plotly_chart(grafico_clientes_por_uf(dados["clientes_por_uf"]), width="stretch")
with coluna_2:
    st.plotly_chart(
        grafico_nota_por_categoria(dados["nota_por_categoria"]),
        width="stretch",
    )
with coluna_3:
    st.plotly_chart(
        grafico_concentracao_vendedores(dados["vendedores_pareto"]),
        width="stretch",
    )
