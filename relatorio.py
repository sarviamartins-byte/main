import sys
from datetime import date, datetime
from html import escape
from pathlib import Path

import pandas as pd

import painel


MARTS = (
    "vendas_totais_mensais",
    "trimestre",
    "entrega_no_prazo",
    "nota_por_categoria",
    "venda_por_estado",
    "mix_pagamento",
    "vendedores_state",
    "kpis",
    "clientes_unicos_por_mes",
)


def _valores_cartoes(dados):
    kpis = dados["kpis"].iloc[0]
    return (
        ("Ticket médio", painel.reais(kpis["ticket_medio"])),
        (
            "Cancelados · % de todos os pedidos",
            painel.pct(kpis["pct_cancelados"], 2),
        ),
        ("Peso do frete", painel.pct(kpis["pct_frete"], 1)),
        (
            "No prazo",
            painel.pct(dados["entrega_no_prazo"].iloc[0]["pct_no_prazo"], 1),
        ),
        ("Dias até entregar", painel.numero(kpis["dias_entrega"], 1)),
        ("Nota média", painel.numero(kpis["nota_media"], 2)),
    )


def _html_cartoes(cartoes):
    itens = "\n".join(
        '<article class="cartao">'
        f'<div class="rotulo">{escape(rotulo)}</div>'
        f'<div class="valor">{escape(valor)}</div>'
        "</article>"
        for rotulo, valor in cartoes
    )
    return f'<section class="cartoes">{itens}</section>'


def _html_grafico(figura, div_id, incluir_plotly):
    return figura.to_html(
        full_html=False,
        include_plotlyjs="cdn" if incluir_plotly else False,
        div_id=div_id,
    )


def gerar_relatorio() -> Path:
    sys.stdout.reconfigure(encoding="utf-8")
    dados = painel.ler(MARTS)

    inicio = pd.Timestamp(date(2017, 1, 1))
    fim = pd.Timestamp(date(2018, 8, 1))
    vendas = dados["vendas_totais_mensais"]
    if inicio not in vendas["mes"].tolist() or fim not in vendas["mes"].tolist():
        raise ValueError(
            "O mart vendas_totais_mensais não contém jan/2017 e ago/2018."
        )
    vendas_periodo = vendas.loc[vendas["mes"].between(inicio, fim)]
    figura_mensal = painel.grafico_vendas_mensais(vendas_periodo)
    figura_mensal.update_layout(
        title="13 · Faturamento mensal (jan/2017 a ago/2018)"
    )

    figuras = (
        figura_mensal,
        painel.grafico_vendas_trimestrais(dados["trimestre"]),
        painel.grafico_mix_pagamento(dados["mix_pagamento"]),
        painel.grafico_receita_por_estado(dados["venda_por_estado"]),
        painel.grafico_clientes_unicos_por_mes(dados["clientes_unicos_por_mes"]),
        painel.grafico_nota_por_categoria(dados["nota_por_categoria"]),
        painel.grafico_vendedores_por_estado(dados["vendedores_state"]),
    )
    graficos = [
        _html_grafico(figura, f"g{indice:02d}", indice == 1)
        for indice, figura in enumerate(figuras, start=1)
    ]

    gerado_em = datetime.now().strftime("%d/%m/%Y %H:%M")
    documento = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Olist · visão da operação</title>
  <style>
    :root {{ color-scheme: light; font-family: Arial, sans-serif; color: #17212b; background: #f5f7f9; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 28px; }}
    main {{ max-width: 1600px; margin: 0 auto; }}
    h1 {{ margin: 0 0 20px; font-size: 28px; }}
    .cartoes {{ display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 12px; margin-bottom: 18px; }}
    .cartao, .grafico {{ min-width: 0; background: #fff; border: 1px solid #e4e9ee; border-radius: 8px; }}
    .cartao {{ padding: 16px; }}
    .rotulo {{ min-height: 36px; color: #52616d; font-size: 13px; }}
    .valor {{ margin-top: 6px; font-size: 23px; font-weight: 700; }}
    .grafico {{ overflow: hidden; }}
    .linha-mensal {{ margin-bottom: 18px; }}
    .linha-tripla {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin-bottom: 18px; }}
    .linha-tripla .grafico {{ align-self: stretch; }}
    footer {{ padding: 4px 0 16px; color: #52616d; font-size: 13px; text-align: right; }}
    @media (max-width: 1050px) {{
      .cartoes {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .linha-tripla {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
    @media (max-width: 650px) {{
      body {{ padding: 16px; }}
      .cartoes, .linha-tripla {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>Olist · visão da operação</h1>
    {_html_cartoes(_valores_cartoes(dados))}
    <section class="grafico linha-mensal">{graficos[0]}</section>
    <section class="linha-tripla">
      <div class="grafico">{graficos[1]}</div>
      <div class="grafico">{graficos[2]}</div>
      <div class="grafico">{graficos[3]}</div>
    </section>
    <section class="linha-tripla">
      <div class="grafico">{graficos[4]}</div>
      <div class="grafico">{graficos[5]}</div>
      <div class="grafico">{graficos[6]}</div>
    </section>
    <footer>Dados de {gerado_em}</footer>
  </main>
</body>
</html>
"""
    destino = Path(__file__).resolve().with_name("relatorio.html")
    destino.write_text(documento, encoding="utf-8")
    tamanho_kb = destino.stat().st_size / 1024
    print(f"Arquivo: {destino}")
    print(f"Tamanho: {tamanho_kb:.2f} KB")
    return destino


if __name__ == "__main__":
    gerar_relatorio()
