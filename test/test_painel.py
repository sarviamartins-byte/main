from datetime import date

import duckdb
import pandas as pd
import plotly.graph_objects as go
import pytest

import painel


def test_formatadores_usam_separadores_fixos_sem_locale():
    assert painel.reais(1003862.14) == "R$ 1.003.862,14"
    assert painel.reais(12.5, casas=0) == "R$ 12"
    assert painel.pct(93.2) == "93,2%"
    assert painel.pct(0.625, casas=2) == "0,62%"
    assert painel.numero(96470) == "96.470"
    assert painel.numero(12.5, casas=1) == "12,5"


def test_ler_fecha_conexao_e_retorna_apenas_marts_solicitados(
    tmp_path, monkeypatch
):
    caminho_banco = tmp_path / "olist.duckdb"
    conexao = duckdb.connect(str(caminho_banco))
    conexao.execute("CREATE SCHEMA marts")
    conexao.execute("CREATE TABLE marts.escolhido AS SELECT 4 AS valor")
    conexao.execute("CREATE TABLE marts.nao_solicitado AS SELECT 9 AS valor")
    conexao.close()
    monkeypatch.chdir(tmp_path)

    dados = painel.ler(("escolhido",))

    assert list(dados) == ["escolhido"]
    assert dados["escolhido"]["valor"].tolist() == [4]
    conexao = duckdb.connect(str(caminho_banco))
    try:
        conexao.execute("CREATE TABLE escrita_pos_leitura AS SELECT 1 AS valor")
        assert conexao.execute(
            "SELECT valor FROM escrita_pos_leitura"
        ).fetchone() == (1,)
    finally:
        conexao.close()


def test_ler_informa_todos_os_marts_ausentes(tmp_path, monkeypatch):
    caminho_banco = tmp_path / "olist.duckdb"
    duckdb.connect(str(caminho_banco)).close()
    monkeypatch.chdir(tmp_path)

    with pytest.raises(painel.MartsAusentesError) as erro:
        painel.ler(("faltante_a", "faltante_b"))
    assert erro.value.marts == ["faltante_a", "faltante_b"]


def test_banco_existe_consulta_o_diretorio_atual(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert not painel.banco_existe()
    (tmp_path / "olist.duckdb").touch()
    assert painel.banco_existe()


def test_todas_as_funcoes_de_grafico_retorna_figura_com_um_ponto_por_linha():
    # Cada par de linhas foi inventado para conferir a contagem exibida em cada gráfico.
    exemplos = (
        (
            painel.grafico_vendas_mensais,
            pd.DataFrame(
                {
                    "mes": [date(2017, 1, 1), date(2017, 2, 1)],
                    "receita": [10, 20],
                }
            ),
        ),
        (
            painel.grafico_vendas_trimestrais,
            pd.DataFrame(
                {
                    "trimestre": [date(2020, 1, 1), date(2020, 4, 1)],
                    "receita": [10, 20],
                }
            ),
        ),
        (
            painel.grafico_mix_pagamento,
            pd.DataFrame({"tipo": ["cartao", "pix"], "pct_valor": [60, 40]}),
        ),
        (
            painel.grafico_receita_por_estado,
            pd.DataFrame(
                {"estado": ["AA", "BB"], "receita_total": [10, 20]}
            ),
        ),
        (
            painel.grafico_vendedores_por_estado,
            pd.DataFrame(
                {"estado": ["AA", "BB"], "total_vendedores": [10, 20]}
            ),
        ),
        (
            painel.grafico_clientes_unicos_por_mes,
            pd.DataFrame(
                {
                    "mes": [date(2020, 1, 1), date(2020, 2, 1)],
                    "clientes_unicos": [10, 20],
                }
            ),
        ),
        (
            painel.grafico_nota_por_categoria,
            pd.DataFrame(
                {
                    "categoria": ["a", "b"],
                    "nota_media": [4.1, 3.8],
                    "posicao_pior": [2, 1],
                }
            ),
        ),
    )

    for funcao, dados in exemplos:
        figura = funcao(dados)
        assert isinstance(figura, go.Figure)
        assert sum(len(trace.x) for trace in figura.data) == len(dados)
