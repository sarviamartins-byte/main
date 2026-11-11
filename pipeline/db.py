"""Spec do módulo compartilhado de conexão e gravação.

Este módulo expõe somente ``PASTA_RAW``, ``conectar()``, ``criar_schema(con,
nome)`` e ``gravar(con, df, schema, tabela)``. As etapas do curso decidem
nomes de tabela, leitura de arquivos, apresentação e conversões; centralizar
essas regras aqui as aplicaria silenciosamente às demais aulas.

``PASTA_RAW`` e ``olist.duckdb`` são localizados pela pasta acima de
``pipeline/``, não pelo diretório corrente. Assim, executar um script de outra
pasta não cria por engano um banco vazio no lugar errado.

``conectar()`` abre o banco (criando-o se necessário), devolve a conexão e não
a guarda globalmente. Quem chama controla seu encerramento, inclusive para
liberar o lock do arquivo.

``criar_schema(con, nome)`` usa ``CREATE SCHEMA IF NOT EXISTS`` para permitir
que uma etapa prepare seu destino em reexecuções sem falhar se o schema já
existe.

``gravar(con, df, schema, tabela)`` recria a tabela com as colunas e tipos do
DataFrame, sem conversão: strings ficam ``VARCHAR`` e nulos continuam ``NULL``.
Remove a relação temporária usada para gravar e devolve ``SELECT count(*)``
lido do banco, para que a contagem exibida corresponda aos dados persistidos.

Importar este módulo não abre conexão nem cria arquivo; isso só ocorre quando
``conectar()`` é chamada.
"""

import pathlib as _pathlib
import uuid as _uuid

import duckdb as _duckdb


PASTA_RAW = _pathlib.Path(__file__).resolve().parent.parent / "raw"


def conectar():
    """Abre o banco na raiz do projeto, criando-o se ainda não existir."""
    caminho_banco = _pathlib.Path(__file__).resolve().parent.parent / "olist.duckdb"
    return _duckdb.connect(str(caminho_banco))


def criar_schema(con, nome):
    """Cria o schema solicitado sem erro caso ele já exista."""
    nome_sql = '"' + nome.replace('"', '""') + '"'
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {nome_sql}")


def gravar(con, df, schema, tabela):
    """Substitui uma tabela pelos dados do DataFrame e lê sua contagem."""
    schema_sql = '"' + schema.replace('"', '""') + '"'
    tabela_sql = '"' + tabela.replace('"', '""') + '"'
    relacao = f"_dataframe_{_uuid.uuid4().hex}"
    con.register(relacao, df)
    try:
        con.execute(
            f"CREATE OR REPLACE TABLE {schema_sql}.{tabela_sql} "
            f"AS SELECT * FROM {relacao}"
        )
        return int(
            con.execute(
                f"SELECT count(*) FROM {schema_sql}.{tabela_sql}"
            ).fetchall()[0][0]
        )
    finally:
        con.unregister(relacao)
