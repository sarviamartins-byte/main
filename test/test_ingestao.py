import gzip

import duckdb
import pytest

import pipeline.ingestao as ingestao


class _SaidaTeste:
    def reconfigure(self, **kwargs):
        return None

    def write(self, texto):
        return len(texto)

    def flush(self):
        return None


def _preparar_arquivos_gzip(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    for arquivo, _ in ingestao.ARQUIVOS:
        with gzip.open(
            pasta / arquivo, "wt", encoding="utf-8", newline=""
        ) as destino:
            destino.write("codigo,marcador,vazio\n")
            destino.write("001,NA,\n")  # Preserva zeros iniciais e o texto NA.
            destino.write("002,valor,preenchido\n")  # Segunda linha de entrada.


def test_csv_gzip_vira_tabelas_com_linhas_originais_e_reexecucao_substitui(
    tmp_path, monkeypatch
):
    pasta_raw = tmp_path / "raw"
    caminho_banco = tmp_path / "teste.duckdb"
    _preparar_arquivos_gzip(pasta_raw)
    monkeypatch.setattr(ingestao, "PASTA_RAW", pasta_raw)
    monkeypatch.setattr(
        ingestao, "conectar", lambda: duckdb.connect(str(caminho_banco))
    )
    monkeypatch.setattr(ingestao.sys, "stdout", _SaidaTeste())

    ingestao.main()
    ingestao.main()

    conexao = duckdb.connect(str(caminho_banco), read_only=True)
    try:
        tabelas = {
            linha[0]
            for linha in conexao.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'raw'"
            ).fetchall()
        }
        assert tabelas == {tabela for _, tabela in ingestao.ARQUIVOS}
        assert conexao.execute(
            "SELECT * FROM raw.pedidos ORDER BY codigo"
        ).fetchall() == [
            ("001", "NA", None),
            ("002", "valor", "preenchido"),
        ]
    finally:
        conexao.close()


def test_arquivo_ausente_encerra_antes_de_abrir_o_banco(tmp_path, monkeypatch):
    caminho_banco = tmp_path / "nao_criado.duckdb"
    monkeypatch.setattr(ingestao, "PASTA_RAW", tmp_path / "raw_vazia")
    monkeypatch.setattr(
        ingestao, "conectar", lambda: duckdb.connect(str(caminho_banco))
    )
    monkeypatch.setattr(ingestao.sys, "stdout", _SaidaTeste())

    with pytest.raises(SystemExit) as erro:
        ingestao.main()
    assert erro.value.code == 1
    assert not caminho_banco.exists()
