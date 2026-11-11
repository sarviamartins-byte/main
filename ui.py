"""Spec da interface web independente do banco DuckDB já ingerido.

O caminho de ``olist.duckdb`` é relativo a este arquivo, não ao diretório
corrente, para que a interface sempre abra o banco da raiz. Antes de conectar,
verifica se o arquivo existe; se faltar, informa que a ingestão deve rodar e
termina com código 1. Criar um banco vazio faria a ausência de dados parecer
uma ingestão quebrada.

Sem importar a ingestão, instala e carrega a extensão DuckDB ``ui`` e chama
``CALL start_ui()``, que serve a interface em ``http://localhost:4213`` e abre
o navegador. O processo e a conexão ficam vivos até Ctrl+C, pois o servidor
depende da conexão; a interrupção fecha a conexão e sai sem traceback. Isso
libera o lock do arquivo, que só pode ter um processo escrevendo, para que a
ingestão possa rodar depois.

O stdout é reconfigurado para UTF-8 para que a URL e a instrução
``Ctrl+C para encerrar`` sejam legíveis no Prompt de Comando do Windows.
"""

import pathlib
import sys
import time

import duckdb


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    caminho_banco = pathlib.Path(__file__).resolve().parent / "olist.duckdb"
    if not caminho_banco.is_file():
        print(
            f"O banco {caminho_banco} não existe. Rode a ingestão antes de abrir a interface.",
            file=sys.stderr,
        )
        sys.exit(1)

    con = duckdb.connect(str(caminho_banco))
    try:
        con.execute("INSTALL ui")
        con.execute("LOAD ui")
        con.execute("CALL start_ui()")
        print("Interface disponível em http://localhost:4213")
        print("Ctrl+C para encerrar")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        return
    finally:
        con.close()


if __name__ == "__main__":
    main()
