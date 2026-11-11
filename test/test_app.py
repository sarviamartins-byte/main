from pathlib import Path

import duckdb
from streamlit.testing.v1 import AppTest


def _criar_marts(caminho):
    conexao = duckdb.connect(str(caminho))
    conexao.execute("CREATE SCHEMA marts")
    consultas = (
        "CREATE TABLE marts.vendas_totais_mensais AS "
        "SELECT DATE '2017-01-01' AS mes, "
        "1 AS pedidos, 10.00 AS receita "
        "UNION ALL SELECT DATE '2018-08-01', 1, 20.00",
        "CREATE TABLE marts.trimestre AS "
        "SELECT DATE '2017-01-01' AS trimestre, 1 AS pedidos, 10.00 AS receita",
        "CREATE TABLE marts.entrega_no_prazo AS "
        "SELECT 93.2 AS pct_no_prazo",
        "CREATE TABLE marts.nota_por_categoria AS "
        "SELECT 'categoria_a' AS categoria, 4.0 AS nota_media, 1 AS posicao_pior",
        "CREATE TABLE marts.venda_por_estado AS "
        "SELECT 'AA' AS estado, 1 AS total_pedidos, 10.00 AS receita_total",
        "CREATE TABLE marts.mix_pagamento AS "
        "SELECT 'cartao' AS tipo, 100.0 AS pct_valor",
        "CREATE TABLE marts.vendedores_state AS "
        "SELECT 'AA' AS estado, 1 AS total_vendedores",
        "CREATE TABLE marts.kpis AS "
        "SELECT 137.42 AS ticket_medio, 0.63 AS pct_cancelados, "
        "14.2 AS pct_frete, 12.5 AS dias_entrega, 4.09 AS nota_media",
        "CREATE TABLE marts.clientes_unicos_por_mes AS "
        "SELECT DATE '2017-01-01' AS mes, 1 AS clientes_unicos",
    )
    for consulta in consultas:
        conexao.execute(consulta)
    conexao.close()


def test_app_renderiza_seis_cartoes_e_sete_graficos_dos_marts_atuais(
    tmp_path, monkeypatch
):
    _criar_marts(tmp_path / "olist.duckdb")
    monkeypatch.chdir(tmp_path)

    script = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(script).run()

    assert not app.exception
    assert [metrica.value for metrica in app.metric] == [
        "R$ 137,42",
        "0,63%",
        "14,2%",
        "93,2%",
        "12,5",
        "4,09",
    ]
    assert len(app.get("plotly_chart")) == 7
