from datetime import date
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

import pipeline.marts as marts
from pipeline.transformacao import TABELAS


class _SaidaTeste:
    def reconfigure(self, **kwargs):
        return None

    def write(self, texto):
        return len(texto)

    def flush(self):
        return None


def _preparar_marts(tmp_path, monkeypatch):
    caminho_banco = tmp_path / "teste.duckdb"
    conexao = duckdb.connect(str(caminho_banco))
    conexao.execute("CREATE SCHEMA refined")
    for tabela in TABELAS:
        conexao.execute(f'CREATE TABLE refined."{tabela}" (id INTEGER)')
    conexao.execute("CREATE SCHEMA marts")
    # A tabela preexistente prova que falha dentro da transação faz rollback.
    conexao.execute("CREATE TABLE marts.anterior AS SELECT 8 AS valor")
    conexao.close()
    monkeypatch.setattr(
        marts, "conectar", lambda: duckdb.connect(str(caminho_banco))
    )
    monkeypatch.setattr(marts.sys, "stdout", _SaidaTeste())
    return caminho_banco, tmp_path / "sql"


def test_arquivo_sem_prefixo_nn_encerra_antes_de_alterar_marts(
    tmp_path, monkeypatch
):
    caminho_banco, pasta_sql = _preparar_marts(tmp_path, monkeypatch)
    pasta_sql.mkdir()
    (pasta_sql / "sem_prefixo.sql").write_text(
        "SELECT 1 AS valor", encoding="utf-8"
    )
    monkeypatch.setattr(marts, "PASTA_MARTS", pasta_sql)

    with pytest.raises(SystemExit) as erro:
        marts.main()
    assert erro.value.code == 1

    conexao = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert conexao.execute(
            "SELECT valor FROM marts.anterior"
        ).fetchone() == (8,)
    finally:
        conexao.close()


def test_pasta_sql_vazia_encerra_sem_apagar_marts(tmp_path, monkeypatch):
    caminho_banco, pasta_sql = _preparar_marts(tmp_path, monkeypatch)
    pasta_sql.mkdir()
    monkeypatch.setattr(marts, "PASTA_MARTS", pasta_sql)

    with pytest.raises(SystemExit) as erro:
        marts.main()
    assert erro.value.code == 1

    conexao = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert conexao.execute(
            "SELECT valor FROM marts.anterior"
        ).fetchone() == (8,)
    finally:
        conexao.close()


def test_nomes_de_tabela_duplicados_ignoram_diferenca_de_caixa(
    tmp_path, monkeypatch
):
    caminho_banco, pasta_sql = _preparar_marts(tmp_path, monkeypatch)
    pasta_sql.mkdir()
    (pasta_sql / "01_repetido.sql").write_text(
        "SELECT 1 AS valor", encoding="utf-8"
    )
    (pasta_sql / "02_REPETIDO.sql").write_text(
        "SELECT 2 AS valor", encoding="utf-8"
    )
    monkeypatch.setattr(marts, "PASTA_MARTS", pasta_sql)

    with pytest.raises(SystemExit) as erro:
        marts.main()
    assert erro.value.code == 1

    conexao = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert conexao.execute(
            "SELECT valor FROM marts.anterior"
        ).fetchone() == (8,)
    finally:
        conexao.close()


def test_tabela_refined_ausente_encerra_antes_de_criar_marts(
    tmp_path, monkeypatch
):
    caminho_banco = tmp_path / "sem_refined.duckdb"
    duckdb.connect(str(caminho_banco)).close()
    pasta_sql = tmp_path / "sql"
    pasta_sql.mkdir()
    (pasta_sql / "01_teste.sql").write_text(
        "SELECT 1 AS valor", encoding="utf-8"
    )
    monkeypatch.setattr(
        marts, "conectar", lambda: duckdb.connect(str(caminho_banco))
    )
    monkeypatch.setattr(marts, "PASTA_MARTS", pasta_sql)
    monkeypatch.setattr(marts.sys, "stdout", _SaidaTeste())

    with pytest.raises(SystemExit) as erro:
        marts.main()
    assert erro.value.code == 1

    conexao = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert conexao.execute(
            "SELECT count(*) FROM information_schema.schemata "
            "WHERE schema_name = 'marts'"
        ).fetchone() == (0,)
    finally:
        conexao.close()


def test_mart_vazio_reverte_schema_marts_anterior(
    tmp_path, monkeypatch
):
    caminho_banco, pasta_sql = _preparar_marts(tmp_path, monkeypatch)
    pasta_sql.mkdir()
    (pasta_sql / "01_vazio.sql").write_text(
        "SELECT 1 AS valor WHERE FALSE", encoding="utf-8"
    )
    monkeypatch.setattr(marts, "PASTA_MARTS", pasta_sql)

    with pytest.raises(SystemExit) as erro:
        marts.main()
    assert erro.value.code == 1

    conexao = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert conexao.execute(
            "SELECT valor FROM marts.anterior"
        ).fetchone() == (8,)
    finally:
        conexao.close()


def test_sql_removido_faz_tabela_sumir_na_execucao_seguinte(
    tmp_path, monkeypatch
):
    caminho_banco, pasta_sql = _preparar_marts(tmp_path, monkeypatch)
    pasta_sql.mkdir()
    atual = pasta_sql / "01_atual.sql"
    removido = pasta_sql / "02_removido.sql"
    atual.write_text("SELECT 1 AS valor;", encoding="utf-8")
    removido.write_text("SELECT 2 AS valor", encoding="utf-8")
    monkeypatch.setattr(marts, "PASTA_MARTS", pasta_sql)

    marts.main()
    removido.unlink()
    marts.main()

    conexao = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        tabelas = {
            linha[0]
            for linha in conexao.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'marts'"
            ).fetchall()
        }
        assert tabelas == {"atual"}
        assert conexao.execute(
            "SELECT valor FROM marts.atual"
        ).fetchone() == (1,)
    finally:
        conexao.close()


def test_erro_sql_reverte_schema_marts_anterior(tmp_path, monkeypatch):
    caminho_banco, pasta_sql = _preparar_marts(tmp_path, monkeypatch)
    pasta_sql.mkdir()
    (pasta_sql / "01_falha.sql").write_text(
        "SELECT * FROM tabela_inexistente", encoding="utf-8"
    )
    monkeypatch.setattr(marts, "PASTA_MARTS", pasta_sql)

    with pytest.raises(SystemExit) as erro:
        marts.main()
    assert erro.value.code == 1

    conexao = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert conexao.execute(
            "SELECT valor FROM marts.anterior"
        ).fetchone() == (8,)
    finally:
        conexao.close()


def test_sql_01_conta_pedido_com_dois_itens_uma_vez_e_ignora_cancelado(
    tmp_path,
):
    conexao = duckdb.connect(str(tmp_path / "sql_01.duckdb"))
    try:
        conexao.execute("CREATE SCHEMA refined")
        conexao.execute(
            "CREATE TABLE refined.pedidos "
            "(pedido_id VARCHAR, data_compra TIMESTAMP, status VARCHAR)"
        )
        conexao.execute(
            "CREATE TABLE refined.itens_pedido "
            "(pedido_id VARCHAR, vendedor_id VARCHAR, preco DECIMAL(10,2))"
        )
        # Um pedido válido e outro cancelado isolam a regra do mart mensal.
        conexao.execute(
            "INSERT INTO refined.pedidos VALUES "
            "('dois-itens', '2017-01-10 09:00:00', 'delivered'), "
            "('cancelado', '2017-01-11 09:00:00', 'canceled')"
        )
        # Dois itens pertencem ao mesmo pedido; o cancelado tem receita a excluir.
        conexao.execute(
            "INSERT INTO refined.itens_pedido VALUES "
            "('dois-itens', 'vendedor-1', 10.00), "
            "('dois-itens', 'vendedor-1', 15.00), "
            "('cancelado', 'vendedor-1', 90.00)"
        )

        consulta = (
            Path(__file__).resolve().parents[1]
            / "sql"
            / "marts"
            / "01_vendas_mensais.sql"
        )
        resultado = conexao.execute(consulta.read_text(encoding="utf-8")).fetchall()

        assert resultado == [
            (date(2017, 1, 1), "vendedor-1", 1, Decimal("25.00"))
        ]
    finally:
        conexao.close()


def test_sql_03_entrega_na_tarde_do_dia_previsto_conta_no_prazo(tmp_path):
    from decimal import Decimal

    conexao = duckdb.connect(str(tmp_path / "sql_03.duckdb"))
    try:
        conexao.execute("CREATE SCHEMA refined")
        conexao.execute(
            "CREATE TABLE refined.pedidos "
            "(pedido_id VARCHAR, status VARCHAR, data_entrega TIMESTAMP, "
            "data_entrega_prevista DATE)"
        )
        # Entrega às 15h no dia previsto deve contar como pontual.
        # A linha atrasada e a data nula completam os limites do denominador.
        conexao.execute(
            "INSERT INTO refined.pedidos VALUES "
            "('pontual', 'delivered', '2020-01-02 15:00:00', '2020-01-02'), "
            "('atrasado', 'delivered', '2020-01-03 08:00:00', '2020-01-02'), "
            "('sem-data', 'delivered', NULL, '2020-01-02')"
        )
        consulta = (
            Path(__file__).resolve().parents[1]
            / "sql"
            / "marts"
            / "03_entrega_no_prazo.sql"
        )
        resultado = conexao.execute(consulta.read_text(encoding="utf-8")).fetchone()

        assert resultado == (2, 1, 1, Decimal("50.0"))
    finally:
        conexao.close()


def test_sql_13_resume_receita_mensal_e_conta_pedido_com_varios_itens_uma_vez(
    tmp_path,
):
    conexao = duckdb.connect(str(tmp_path / "sql_13.duckdb"))
    try:
        conexao.execute("CREATE SCHEMA refined")
        conexao.execute(
            "CREATE TABLE refined.pedidos "
            "(pedido_id VARCHAR, data_compra TIMESTAMP, status VARCHAR)"
        )
        conexao.execute(
            "CREATE TABLE refined.itens_pedido "
            "(pedido_id VARCHAR, preco DECIMAL(10,2))"
        )
        # Dois itens do mesmo pedido verificam receita somada e pedido contado uma vez.
        conexao.execute(
            "INSERT INTO refined.pedidos VALUES "
            "('valido', '2017-01-10 09:00:00', 'delivered'), "
            "('cancelado', '2017-01-11 09:00:00', 'canceled')"
        )
        conexao.execute(
            "INSERT INTO refined.itens_pedido VALUES "
            "('valido', 10.00), ('valido', 15.00), ('cancelado', 90.00)"
        )
        consulta = (
            Path(__file__).resolve().parents[1]
            / "sql"
            / "marts"
            / "13_vendas_totais_mensais.sql"
        )

        resultado = conexao.execute(
            consulta.read_text(encoding="utf-8")
        ).fetchall()

        assert resultado == [(date(2017, 1, 1), 1, Decimal("25.00"))]
    finally:
        conexao.close()


def test_sql_14_conta_cliente_id_distinto_no_mes_e_ignora_cancelado(tmp_path):
    conexao = duckdb.connect(str(tmp_path / "sql_14.duckdb"))
    try:
        conexao.execute("CREATE SCHEMA refined")
        conexao.execute(
            "CREATE TABLE refined.pedidos "
            "(pedido_id VARCHAR, cliente_id VARCHAR, data_compra TIMESTAMP, "
            "status VARCHAR)"
        )
        conexao.execute(
            "CREATE TABLE refined.itens_pedido (pedido_id VARCHAR)"
        )
        # Cliente repetido em dois pedidos conta uma vez; outro cliente conta também.
        conexao.execute(
            "INSERT INTO refined.pedidos VALUES "
            "('p1', 'c1', '2017-01-10 09:00:00', 'delivered'), "
            "('p2', 'c1', '2017-01-12 09:00:00', 'delivered'), "
            "('p3', 'c2', '2017-01-13 09:00:00', 'delivered'), "
            "('p4', 'c3', '2017-01-14 09:00:00', 'canceled')"
        )
        conexao.execute(
            "INSERT INTO refined.itens_pedido VALUES "
            "('p1'), ('p2'), ('p3'), ('p4')"
        )
        consulta = (
            Path(__file__).resolve().parents[1]
            / "sql"
            / "marts"
            / "14_clientes_unicos_por_mes.sql"
        )

        resultado = conexao.execute(
            consulta.read_text(encoding="utf-8")
        ).fetchall()

        assert resultado == [(date(2017, 1, 1), 2)]
    finally:
        conexao.close()
