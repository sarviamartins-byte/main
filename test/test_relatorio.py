from datetime import datetime
from pathlib import Path

import duckdb
import pytest

import relatorio


class _SaidaTeste:
    def reconfigure(self, **kwargs):
        return None

    def write(self, texto):
        return len(texto)

    def flush(self):
        return None


def _criar_banco_relatorio(caminho):
    conexao = duckdb.connect(str(caminho))
    conexao.execute("CREATE SCHEMA marts")
    # Duas pontas sintéticas bastam para satisfazer o período do relatório.
    consultas = (
        "CREATE TABLE marts.vendas_mensais AS "
        "SELECT DATE '2017-01-01' AS mes, 1 AS pedidos, 10.00 AS receita "
        "UNION ALL SELECT DATE '2018-08-01', 1, 20.00",
        # Uma categoria sintética basta para desenhar o gráfico de receita.
        "CREATE TABLE marts.top_categorias AS "
        "SELECT 'categoria_a' AS categoria, 10.00 AS receita",
        # Os valores abaixo só alimentam os cartões e gráficos do relatório.
        "CREATE TABLE marts.entrega_no_prazo AS "
        "SELECT 100.0 AS pct_no_prazo",
        "CREATE TABLE marts.nota_por_categoria AS "
        "SELECT 'categoria_a' AS categoria, 4.0 AS nota_media, 1 AS posicao_pior",
        "CREATE TABLE marts.recompra AS "
        "SELECT 1 AS pedidos_por_cliente, 75.0 AS pct_clientes",
        "CREATE TABLE marts.ticket_medio_por_estado AS "
        "SELECT 'AA' AS uf, 10.0 AS ticket_medio",
        "CREATE TABLE marts.mix_pagamento AS "
        "SELECT 'cartao' AS tipo, 100.0 AS pct_valor",
        "CREATE TABLE marts.vendedores_pareto AS "
        "SELECT 1 AS posicao, 100.0 AS pct_acumulado",
        "CREATE TABLE marts.kpis AS "
        "SELECT 10.0 AS ticket_medio, 2.0 AS pct_cancelados, "
        "5.0 AS pct_frete, 3.0 AS dias_entrega, 4.0 AS nota_media",
        "CREATE TABLE marts.clientes_por_uf AS "
        "SELECT 'AA' AS uf, 1 AS clientes",
    )
    for consulta in consultas:
        conexao.execute(consulta)
    conexao.close()


def test_relatorio_grava_em_tmp_e_duas_execucoes_so_mudam_o_rodape(
    tmp_path, monkeypatch
):
    caminho_banco = tmp_path / "olist.duckdb"
    _criar_banco_relatorio(caminho_banco)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(relatorio, "__file__", str(tmp_path / "relatorio.py"))
    monkeypatch.setattr(relatorio.sys, "stdout", _SaidaTeste())

    instantes = iter(
        (
            datetime(2024, 1, 2, 3, 4),
            datetime(2024, 1, 2, 3, 5),
        )
    )

    class _Relogio:
        @staticmethod
        def now():
            return next(instantes)

    monkeypatch.setattr(relatorio, "datetime", _Relogio)

    primeiro = relatorio.gerar_relatorio()
    html_primeiro = primeiro.read_text(encoding="utf-8")
    segundo = relatorio.gerar_relatorio()
    html_segundo = segundo.read_text(encoding="utf-8")

    assert primeiro == tmp_path / "relatorio.html"
    assert segundo.is_file()
    assert html_primeiro.replace(
        "Dados de 02/01/2024 03:04", "Dados de <RODAPE>"
    ) == html_segundo.replace("Dados de 02/01/2024 03:05", "Dados de <RODAPE>")
    assert "<article class=\"cartao\">" in html_segundo


def test_relatorio_falha_se_nao_houver_meses_padrao(tmp_path, monkeypatch):
    caminho_banco = tmp_path / "olist.duckdb"
    _criar_banco_relatorio(caminho_banco)
    conexao = duckdb.connect(str(caminho_banco))
    conexao.execute("DELETE FROM marts.vendas_mensais WHERE mes = DATE '2018-08-01'")
    conexao.close()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(relatorio, "__file__", str(tmp_path / "relatorio.py"))
    monkeypatch.setattr(relatorio.sys, "stdout", _SaidaTeste())

    with pytest.raises(ValueError) as erro:
        relatorio.gerar_relatorio()
    assert "jan/2017 e ago/2018" in str(erro.value)
