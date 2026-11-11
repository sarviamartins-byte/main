"""Execução dos marts definidos exclusivamente em ``sql/marts/*.sql``.

ESCOPO
------
As consultas leem de ``refined`` e criam tabelas somente em ``marts``,
preservando as camadas de origem. O schema ``marts`` é apagado e recriado em
cada execução para que um mart cujo arquivo foi removido também desapareça.

ARQUIVOS E TABELAS
------------------
Todos os arquivos SQL são processados em ordem alfabética para manter a
execução e a saída determinísticas. O nome da tabela vem do nome do arquivo
sem extensão e sem o prefixo ``NN_``; cada conteúdo é executado como
``CREATE TABLE marts.<nome> AS <conteúdo>``. O Python remove somente espaços
e um ponto e vírgula finais: a regra de negócio mora inteira no arquivo SQL.

VALIDAÇÕES E FALHAS
-------------------
Antes da recriação, todas as oito tabelas de ``refined`` devem existir para
que os marts tenham as entradas esperadas; se faltarem, a mensagem indica
como executar a transformação. A pasta deve ter arquivos SQL, cada nome deve
começar com ``NN_`` e não pode haver nomes de tabela repetidos. Sem arquivos
não há marts a produzir, e a validação prévia evita nomes sem correspondência
ou destinos ambíguos antes de qualquer alteração no schema.

Se uma consulta falhar, o arquivo e a mensagem do DuckDB são mostrados e
nenhuma consulta seguinte é executada. Cada mart precisa ter ao menos uma
linha: um resultado vazio costuma indicar um JOIN que não casou, e um
dashboard vazio pode parecer um negócio parado. Qualquer erro, inclusive um
mart vazio, reverte toda a transação para que o schema da última execução
bem-sucedida continue disponível.

SAÍDA
-----
O stdout é UTF-8 para preservar os caracteres no terminal do Windows. A tela
mostra contagens lidas do banco, em vez de estimadas, por mart e o número
total de marts e linhas; separador de milhar por ponto facilita a leitura.
"""

import re
import sys
from pathlib import Path

import duckdb

from pipeline.db import conectar
from pipeline.transformacao import TABELAS


PASTA_MARTS = Path(__file__).resolve().parent.parent / "sql" / "marts"
PREFIXO_ARQUIVO = re.compile(r"^\d{2}_(.+)$")


def _identificador(nome):
    return '"' + nome.replace('"', '""') + '"'


def _formatar_quantidade(quantidade):
    return f"{quantidade:,}".replace(",", ".")


def _validar_arquivos(arquivos):
    if not arquivos:
        print("Nenhum arquivo .sql encontrado em sql/marts/.", file=sys.stderr)
        raise SystemExit(1)

    nomes = []
    invalidos = []
    for arquivo in arquivos:
        correspondencia = PREFIXO_ARQUIVO.fullmatch(arquivo.stem)
        if correspondencia is None:
            invalidos.append(arquivo.name)
        else:
            nomes.append((arquivo, correspondencia.group(1)))

    repetidos = {}
    for arquivo, nome in nomes:
        repetidos.setdefault(nome.casefold(), []).append(arquivo.name)
    colisoes = [
        arquivos_com_mesmo_nome
        for arquivos_com_mesmo_nome in repetidos.values()
        if len(arquivos_com_mesmo_nome) > 1
    ]

    if invalidos or colisoes:
        print("Nomes de arquivos .sql inválidos ou conflitantes:", file=sys.stderr)
        for arquivo in invalidos:
            print(f"  sem prefixo NN_: {arquivo}", file=sys.stderr)
        for arquivos_com_mesmo_nome in colisoes:
            print(
                f"  mesmo nome de tabela: {', '.join(arquivos_com_mesmo_nome)}",
                file=sys.stderr,
            )
        raise SystemExit(1)

    return nomes


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    try:
        existentes = {
            linha[0]
            for linha in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'refined' AND table_type = 'BASE TABLE'"
            ).fetchall()
        }
        faltantes = [tabela for tabela in TABELAS if tabela not in existentes]
        if faltantes:
            print("Tabelas ausentes em refined:", file=sys.stderr)
            for tabela in faltantes:
                print(f"  refined.{tabela}", file=sys.stderr)
            print(
                'Rode "uv run python -m pipeline.transformacao" antes dos marts.',
                file=sys.stderr,
            )
            raise SystemExit(1)

        arquivos = sorted(PASTA_MARTS.glob("*.sql"), key=lambda arquivo: arquivo.name)
        trabalhos = _validar_arquivos(arquivos)
        resultados = []

        con.execute("BEGIN TRANSACTION")
        try:
            con.execute("DROP SCHEMA IF EXISTS marts CASCADE")
            con.execute("CREATE SCHEMA marts")

            for arquivo, nome_tabela in trabalhos:
                try:
                    consulta = arquivo.read_text(encoding="utf-8").strip()
                    if consulta.endswith(";"):
                        consulta = consulta[:-1].rstrip()

                    con.execute(
                        f"CREATE TABLE marts.{_identificador(nome_tabela)} "
                        f"AS {consulta}"
                    )
                    quantidade = int(
                        con.execute(
                            "SELECT count(*) FROM "
                            f"marts.{_identificador(nome_tabela)}"
                        ).fetchone()[0]
                    )
                except duckdb.Error as erro:
                    raise RuntimeError(
                        f"Erro no arquivo {arquivo.name}: {erro}"
                    ) from erro
                except OSError as erro:
                    raise RuntimeError(
                        f"Não foi possível ler {arquivo.name}: {erro}"
                    ) from erro

                if quantidade == 0:
                    raise RuntimeError(
                        f"Mart {arquivo.name} retornou zero linhas."
                    )
                resultados.append((nome_tabela, quantidade))

            con.execute("COMMIT")
        except Exception as erro:
            con.execute("ROLLBACK")
            print(str(erro), file=sys.stderr)
            raise SystemExit(1) from erro

        total_linhas = 0
        for nome_tabela, quantidade in resultados:
            total_linhas += quantidade
            print(
                f"✓ {f'marts.{nome_tabela}':<28}"
                f"{_formatar_quantidade(quantidade)} linhas"
            )
        print(
            f"Total: {len(resultados)} marts, "
            f"{_formatar_quantidade(total_linhas)} linhas"
        )
    finally:
        con.close()


if __name__ == "__main__":
    main()
