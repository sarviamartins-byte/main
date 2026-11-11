import streamlit as st
import painel

# Layout em modo wide estrito
st.set_page_config(layout="wide")

# Inicialização ou limpeza de cache
if st.sidebar.button("Recarregar dados"):
    st.cache_data.clear()

@st.cache_data
def carregar_dados_seguro():
    """Chama a leitura isolada encapsulando erros de infraestrutura ou marts incompletos."""
    try:
        return painel.ler()
    except (FileNotFoundError, KeyError) as e:
        st.error(f"Erro no carregamento: {e}\n\nExecute o comando abaixo para gerar a base:\n`uv run python -m pipeline.marts`")
        st.stop()

# Carrega os dados persistidos no DuckDB
dados = carregar_dados_seguro()

# --- CABEÇALHO ---
col_titulo, col_filtro = st.columns([1, 1])

with col_titulo:
    st.title("Olist · visão da operação")

with col_filtro:
    # Coleta a listagem de meses para o slider de intervalo cronológico temporal
    df_vendas = dados["vendas_mensais"].sort_values("mes")
    lista_meses = df_vendas["mes"].tolist()
    
    # Define os índices padrão baseados nos critérios de aceite (jan/2017 a ago/2018)
    idx_inicio = lista_meses.index("2017-01") if "2017-01" in lista_meses else 0
    idx_fim = lista_meses.index("2018-08") if "2018-08" in lista_meses else len(lista_meses) - 1
    
    mes_inicio, mes_fim = st.select_slider(
        "Filtrar Período do Faturamento",
        options=lista_meses,
        value=(lista_meses[idx_inicio], lista_meses[idx_fim])
    )
    st.caption("os cartões valem para o período inteiro")

# --- FAIXA 1: METRICS ---
df_kpis = dados["kpis"].iloc[0]
df_recompra = dados["recompra"]
df_prazo = dados["entrega_no_prazo"].iloc[0]

# Extração e única operação aritmética autorizada por spec: 100 - pct_clientes(linha=1)
linha_recompra_1 = df_recompra[df_recompra["pedidos_por_cliente"] == 1]
val_recompra = 100.0 - float(linha_recompra_1["pct_clientes"].values[0])

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("Ticket médio", painel.reais(df_kpis["ticket_medio"]))
c2.metric("Cancelados · %", painel.pct(df_kpis["pct_cancelados"], casas=2))
c3.metric("Peso do frete", painel.pct(df_kpis["pct_frete"], casas=1))
c4.metric("Recompra", painel.pct(val_recompra, casas=2))
c5.metric("No prazo", painel.pct(df_prazo["pct_no_prazo"], casas=1))
c6.metric("Dias até entregar", painel.numero(df_kpis["dias_entrega"], casas=1))
c7.metric("Nota média", painel.numero(df_kpis["nota_media"], casas=2))

# --- FAIXA 2: FATURAMENTO MENSAL (LARGURA INTEIRA) ---
# Filtra dinamicamente as linhas para o gráfico 01 conforme os limites do slider
df_vendas_filtrado = df_vendas[
    (df_vendas["mes"] >= mes_inicio) & (df_vendas["mes"] <= mes_fim)
]
fig_fat = painel.fig_faturamento_mensal(df_vendas_filtrado)
st.plotly_chart(fig_fat, width="stretch")

# --- FAIXA 3: TRES COLUNAS IGUAIS ---
f3_c1, f3_c2, f3_c3 = st.columns(3)

with f3_c1:
    st.plotly_chart(painel.fig_receita_categoria(dados["top_categorias"]), width="stretch")
with f3_c2:
    st.plotly_chart(painel.fig_mix_pagamento(dados["mix_pagamento"]), width="stretch")
with f3_c3:
    st.plotly_chart(painel.fig_ticket_medio_uf(dados["ticket_medio_por_estado"]), width="stretch")

# --- FAIXA 4: TRES COLUNAS IGUAIS ---
f4_c1, f4_c2, f4_c3 = st.columns(3)

with f4_c1:
    st.plotly_chart(painel.fig_clientes_uf(dados["clientes_por_uf"]), width="stretch")
with f4_c2:
    st.plotly_chart(painel.fig_nota_categoria(dados["nota_por_categoria"]), width="stretch")
with f4_c3:
    st.plotly_chart(painel.fig_vendedores_pareto(dados["vendedores_pareto"]), width="stretch")
