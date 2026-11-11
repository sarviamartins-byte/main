from datetime import date, datetime
from decimal import Decimal

import duckdb
import pytest

import pipeline.transformacao as transformacao


class _SaidaTeste:
    def reconfigure(self, **kwargs):
        return None

    def write(self, texto):
        return len(texto)

    def flush(self):
        return None


def _criar_raw(conexao, linhas_pedidos=None, linhas_itens=None):
    conexao.execute("CREATE SCHEMA raw")
    for tabela, definicao in transformacao.TABELAS.items():
        colunas = ", ".join(
            f'"{origem}" VARCHAR'
            for origem, _, _ in definicao["colunas"]
        )
        conexao.execute(f'CREATE TABLE raw."{tabela}" ({colunas})')

    pedidos = linhas_pedidos or []
    for linha in pedidos:
        nomes = list(linha)
        colunas = ", ".join(f'"{nome}"' for nome in nomes)
        valores = ", ".join("?" for _ in nomes)
        conexao.execute(
            f"INSERT INTO raw.pedidos ({colunas}) VALUES ({valores})",
            [linha[nome] for nome in nomes],
        )

    itens = linhas_itens or []
    for linha in itens:
        nomes = list(linha)
        colunas = ", ".join(f'"{nome}"' for nome in nomes)
        valores = ", ".join("?" for _ in nomes)
        conexao.execute(
            f"INSERT INTO raw.itens_pedido ({colunas}) VALUES ({valores})",
            [linha[nome] for nome in nomes],
        )


def _preparar_transformacao(tmp_path, monkeypatch, pedidos=None, itens=None):
    caminho_banco = tmp_path / "transformacao.duckdb"
    conexao = duckdb.connect(str(caminho_banco))
    _criar_raw(conexao, pedidos, itens)
    conexao.close()
    monkeypatch.setattr(
        transformacao, "conectar", lambda: duckdb.connect(str(caminho_banco))
    )
    monkeypatch.setattr(transformacao.sys, "stdout", _SaidaTeste())
    return caminho_banco


def _pedido(pedido_id="p-1", data_compra="2020-01-02 12:30:00"):
    return {
        "order_id": pedido_id,
        "order_purchase_timestamp": data_compra,
        "order_estimated_delivery_date": "2020-01-04",
    }


def _item(preco="12.34"):
    return {
        "order_id": "p-1",
        "order_item_id": "1",
        "shipping_limit_date": "2020-01-03 10:00:00",
        "price": preco,
        "freight_value": "2.50",
    }


def test_transformacao_remove_duplicata_e_converte_datas_e_dinheiro(
    tmp_path, monkeypatch
):
    caminho_banco = _preparar_transformacao(
        tmp_path,
        monkeypatch,
        pedidos=[_pedido()],
        # A segunda linha é uma duplicata exata, que deve virar uma só.
        itens=[_item(), _item()],
    )

    transformacao.main()

    conexao = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert conexao.execute(
            "SELECT count(*) FROM refined.itens_pedido"
        ).fetchone() == (1,)
        assert conexao.execute(
            "SELECT data_compra FROM refined.pedidos"
        ).fetchone() == (datetime(2020, 1, 2, 12, 30),)
        assert conexao.execute(
            "SELECT data_entrega_prevista FROM refined.pedidos"
        ).fetchone() == (date(2020, 1, 4),)
        assert conexao.execute(
            "SELECT preco, frete FROM refined.itens_pedido"
        ).fetchone() == (Decimal("12.34"), Decimal("2.50"))
        assert conexao.execute(
            "SELECT data_compra IS NULL FROM refined.pedidos"
        ).fetchone() == (False,)
        assert conexao.execute(
            "SELECT data_aprovacao IS NULL FROM refined.pedidos"
        ).fetchone() == (True,)
    finally:
        conexao.close()


def test_valor_que_nao_converte_encerra_sem_substituir_refined(
    tmp_path, monkeypatch
):
    # O texto não é data válida e não deve ser convertido em NULL.
    caminho_banco = _preparar_transformacao(
        tmp_path,
        monkeypatch,
        pedidos=[_pedido(data_compra="data-invalida")],
    )
    conexao = duckdb.connect(str(caminho_banco))
    conexao.execute("CREATE SCHEMA refined")
    conexao.execute("CREATE TABLE refined.anterior AS SELECT 9 AS valor")
    conexao.close()

    with pytest.raises(SystemExit) as erro:
        transformacao.main()
    assert erro.value.code == 1

    conexao = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        assert conexao.execute(
            "SELECT valor FROM refined.anterior"
        ).fetchone() == (9,)
        assert conexao.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = 'refined' AND table_name = 'pedidos'"
        ).fetchone() == (0,)
    finally:
        conexao.close()


def test_chave_com_conteudo_conflitante_encerra_transformacao(
    tmp_path, monkeypatch
):
    # Mesmo pedido com duas datas diferentes é conflito, não duplicata exata.
    caminho_banco = _preparar_transformacao(
        tmp_path,
        monkeypatch,
        pedidos=[
            _pedido(),
            {
                **_pedido(),
                "order_purchase_timestamp": "2020-01-03 12:30:00",
            },
        ],
    )

    with pytest.raises(SystemExit) as erro:
        transformacao.main()
    assert erro.value.code == 1


def test_entrada_raw_ausente_encerra_transformacao(tmp_path, monkeypatch):
    caminho_banco = tmp_path / "raw_ausente.duckdb"
    duckdb.connect(str(caminho_banco)).close()
    monkeypatch.setattr(
        transformacao, "conectar", lambda: duckdb.connect(str(caminho_banco))
    )
    monkeypatch.setattr(transformacao.sys, "stdout", _SaidaTeste())

    with pytest.raises(SystemExit) as erro:
        transformacao.main()
    assert erro.value.code == 1


def test_exemplo_da_falha_tem_fallback_quando_duckdb_nao_indica_valor():
    mensagem = "erro sem valor identificável"

    assert transformacao._exemplo_da_falha(mensagem) == (
        f"valor indicado pelo DuckDB: {mensagem}"
    )
