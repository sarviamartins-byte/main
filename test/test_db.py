import duckdb
import pandas as pd

import pipeline.db as db


def test_conectar_usa_a_raiz_do_modulo_e_abre_banco_temporario(tmp_path, monkeypatch):
    caminho_modulo = tmp_path / "pipeline" / "db.py"
    caminho_modulo.parent.mkdir()
    monkeypatch.setattr(db, "__file__", str(caminho_modulo))

    conexao = db.conectar()
    try:
        assert conexao.execute("SELECT 7").fetchone() == (7,)
        assert (tmp_path / "olist.duckdb").is_file()
    finally:
        conexao.close()


def test_criar_schema_e_gravar_recriam_tabela_sem_deixar_relacao_registrada(tmp_path):
    conexao = duckdb.connect(str(tmp_path / "db.duckdb"))
    try:
        db.criar_schema(conexao, 'camada"raw')
        db.criar_schema(conexao, 'camada"raw')
        # Identificador com zero inicial e NULL verificam gravação sem coerção.
        primeira = pd.DataFrame({"codigo": ["001", None]})
        assert db.gravar(conexao, primeira, 'camada"raw', 'tabela"um') == 2
        assert conexao.execute(
            'SELECT * FROM "camada""raw"."tabela""um" ORDER BY codigo NULLS LAST'
        ).fetchall() == [("001",), (None,)]

        segunda = pd.DataFrame({"codigo": ["002"]})
        assert db.gravar(conexao, segunda, 'camada"raw', 'tabela"um') == 1
        assert conexao.execute(
            'SELECT * FROM "camada""raw"."tabela""um"'
        ).fetchall() == [("002",)]
    finally:
        conexao.close()
