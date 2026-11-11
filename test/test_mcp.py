import json

import duckdb
import pytest

import pipeline.mcp as mcp


def _criar_banco(caminho):
    conexao = duckdb.connect(str(caminho))
    conexao.execute("CREATE SCHEMA refined")
    conexao.execute("CREATE TABLE refined.amostra (id INTEGER, nome VARCHAR)")
    conexao.execute("INSERT INTO refined.amostra VALUES (1, 'teste')")
    conexao.close()


def test_execute_query_consulta_banco_em_json_e_libera_conexao(
    tmp_path, monkeypatch
):
    caminho_banco = tmp_path / "mcp.duckdb"
    _criar_banco(caminho_banco)
    monkeypatch.setattr(mcp, "DB_PATH", caminho_banco)

    resultado = json.loads(
        mcp.execute_query("SELECT id, nome FROM refined.amostra")
    )

    assert resultado == {
        "columns": ["id", "nome"],
        "rows": [[1, "teste"]],
        "row_count": 1,
    }
    conexao = duckdb.connect(str(caminho_banco))
    try:
        assert conexao.execute("SELECT count(*) FROM refined.amostra").fetchone() == (
            1,
        )
    finally:
        conexao.close()


@pytest.mark.parametrize(
    "sql",
    (
        "DELETE FROM refined.amostra",
        "CREATE TABLE refined.nova (id INTEGER)",
        "SELECT 1; DROP TABLE refined.amostra",
    ),
)
def test_execute_query_rejeita_sql_que_nao_seja_um_select(sql):
    with pytest.raises(ValueError, match="Somente uma instrução SELECT"):
        mcp.execute_query(sql)


def test_conexao_read_only_impede_escrita_no_banco(tmp_path, monkeypatch):
    caminho_banco = tmp_path / "mcp.duckdb"
    _criar_banco(caminho_banco)
    monkeypatch.setattr(mcp, "DB_PATH", caminho_banco)

    with pytest.raises(duckdb.Error):
        with mcp._conexao() as conexao:
            conexao.execute("CREATE TABLE refined.proibida (id INTEGER)")

    conexao = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert conexao.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'refined' AND table_name = 'proibida'"
        ).fetchone() == (0,)
    finally:
        conexao.close()


def test_conexao_impede_leitura_de_arquivos_externos(tmp_path, monkeypatch):
    caminho_banco = tmp_path / "mcp.duckdb"
    _criar_banco(caminho_banco)
    arquivo_externo = tmp_path / "externo.csv"
    arquivo_externo.write_text("valor\nfora\n", encoding="utf-8")
    monkeypatch.setattr(mcp, "DB_PATH", caminho_banco)

    with pytest.raises(duckdb.Error):
        mcp.execute_query(f"SELECT * FROM read_csv('{arquivo_externo}')")


def test_catalogo_lista_tabelas_e_colunas_com_filtro_de_schema(
    tmp_path, monkeypatch
):
    caminho_banco = tmp_path / "mcp.duckdb"
    _criar_banco(caminho_banco)
    monkeypatch.setattr(mcp, "DB_PATH", caminho_banco)

    bancos = json.loads(mcp.list_databases())
    tabelas = json.loads(mcp.list_tables("refined"))
    colunas = json.loads(mcp.list_columns("amostra", "refined"))

    assert any(banco["path"] == str(caminho_banco) for banco in bancos)
    assert [tabela["table"] for tabela in tabelas] == ["amostra"]
    assert [coluna["column"] for coluna in colunas] == ["id", "nome"]
