"""MCP somente leitura para consultar o DuckDB do projeto com a versão instalada.

O servidor oficial mcp-server-motherduck fixa uma versão DuckDB anterior à
usada pelo projeto e não consegue abrir seu formato de armazenamento. Este
servidor usa a dependência DuckDB do próprio projeto, abre o banco em modo
read-only e desabilita acesso externo para que consultas não leiam outros
arquivos da máquina. A ferramenta de SQL aceita somente uma instrução SELECT.
"""

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import duckdb
from fastmcp import FastMCP


DB_PATH = Path(__file__).resolve().parent.parent / "olist.duckdb"
MCP = FastMCP("Olist DuckDB (read-only)")


@contextmanager
def _conexao() -> Iterator[duckdb.DuckDBPyConnection]:
    conexao = duckdb.connect(
        str(DB_PATH),
        read_only=True,
        config={"enable_external_access": "false"},
    )
    try:
        yield conexao
    finally:
        conexao.close()


def _json(resultados) -> str:
    return json.dumps(resultados, ensure_ascii=False, default=str)


@MCP.tool
def execute_query(sql: str) -> str:
    """Execute uma única instrução SELECT no banco Olist, sem operações de escrita."""
    instrucoes = duckdb.extract_statements(sql)
    if (
        len(instrucoes) != 1
        or instrucoes[0].type != duckdb.StatementType.SELECT
    ):
        raise ValueError("Somente uma instrução SELECT é permitida.")

    with _conexao() as conexao:
        resultado = conexao.execute(sql)
        colunas = [coluna[0] for coluna in resultado.description or ()]
        linhas = resultado.fetchall()
    return _json(
        {
            "columns": colunas,
            "rows": linhas,
            "row_count": len(linhas),
        }
    )


@MCP.tool
def list_databases() -> str:
    """Lista os bancos disponíveis na conexão DuckDB atual."""
    with _conexao() as conexao:
        linhas = conexao.execute(
            "SELECT database_name, path, type FROM duckdb_databases() "
            "ORDER BY database_name"
        ).fetchall()
    return _json(
        [
            {"database_name": nome, "path": caminho, "type": tipo}
            for nome, caminho, tipo in linhas
        ]
    )


@MCP.tool
def list_tables(schema: str | None = None) -> str:
    """Lista tabelas e views do banco atual, opcionalmente filtradas por schema."""
    with _conexao() as conexao:
        linhas = conexao.execute(
            "SELECT table_schema, table_name, table_type "
            "FROM information_schema.tables "
            "WHERE table_catalog = current_database() "
            "AND (? IS NULL OR table_schema = ?) "
            "ORDER BY table_schema, table_name",
            [schema, schema],
        ).fetchall()
    return _json(
        [
            {"schema": esquema, "table": tabela, "type": tipo}
            for esquema, tabela, tipo in linhas
        ]
    )


@MCP.tool
def list_columns(table: str, schema: str | None = None) -> str:
    """Lista colunas, tipos e nulabilidade da tabela no banco atual."""
    with _conexao() as conexao:
        linhas = conexao.execute(
            "SELECT table_schema, table_name, column_name, data_type, "
            "is_nullable, ordinal_position "
            "FROM information_schema.columns "
            "WHERE table_catalog = current_database() "
            "AND table_name = ? "
            "AND (? IS NULL OR table_schema = ?) "
            "ORDER BY table_schema, ordinal_position",
            [table, schema, schema],
        ).fetchall()
    return _json(
        [
            {
                "schema": esquema,
                "table": nome_tabela,
                "column": coluna,
                "type": tipo,
                "nullable": nulo == "YES",
                "position": posicao,
            }
            for esquema, nome_tabela, coluna, tipo, nulo, posicao in linhas
        ]
    )


def main() -> None:
    MCP.run()


if __name__ == "__main__":
    main()
