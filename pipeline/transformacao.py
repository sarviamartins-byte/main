"""Transformação de ``raw`` para ``refined`` conforme a spec aprovada.

ESCOPO
------
Entram ``pedidos``, ``itens_pedido``, ``pagamentos``, ``clientes``,
``vendedores``, ``produtos``, ``traducao_categorias`` e ``avaliacoes``.
``geolocalizacao`` fica fora porque nenhum mart do curso a usa; limpar dado
que ninguém lerá não agrega valor. A origem nunca é escrita.

NOMES
-----
Cada mapa é completo e literal: não descarta nem acrescenta colunas. O
vocabulário em português permite digitar de memória os JOINs da aula 3.

* ``pedidos``: ``order_id``→``pedido_id``, ``customer_id``→``cliente_id``,
  ``order_status``→``status``, ``order_purchase_timestamp``→``data_compra``,
  ``order_approved_at``→``data_aprovacao``,
  ``order_delivered_carrier_date``→``data_envio``,
  ``order_delivered_customer_date``→``data_entrega``,
  ``order_estimated_delivery_date``→``data_entrega_prevista``.
* ``itens_pedido``: ``order_id``→``pedido_id``,
  ``order_item_id``→``item_seq``, ``product_id``→``produto_id``,
  ``seller_id``→``vendedor_id``, ``shipping_limit_date``→``data_limite_envio``,
  ``price``→``preco``, ``freight_value``→``frete``.
* ``pagamentos``: ``order_id``→``pedido_id``,
  ``payment_sequential``→``pagamento_seq``, ``payment_type``→``tipo``,
  ``payment_installments``→``parcelas``, ``payment_value``→``valor``.
* ``clientes``: ``customer_id``→``cliente_id``,
  ``customer_unique_id``→``cliente_unico_id``,
  ``customer_zip_code_prefix``→``cep_prefixo``,
  ``customer_city``→``cidade``, ``customer_state``→``uf``.
* ``vendedores``: ``seller_id``→``vendedor_id``,
  ``seller_zip_code_prefix``→``cep_prefixo``, ``seller_city``→``cidade``,
  ``seller_state``→``uf``.
* ``produtos``: ``product_id``→``produto_id``,
  ``product_category_name``→``categoria``,
  ``product_name_lenght``→``tamanho_nome``,
  ``product_description_lenght``→``tamanho_descricao``,
  ``product_photos_qty``→``qtd_fotos``, ``product_weight_g``→``peso_g``,
  ``product_length_cm``→``comprimento_cm``,
  ``product_height_cm``→``altura_cm``, ``product_width_cm``→``largura_cm``.
* ``traducao_categorias``: ``product_category_name``→``categoria``,
  ``product_category_name_english``→``categoria_en``.
* ``avaliacoes``: ``review_id``→``avaliacao_id``, ``order_id``→``pedido_id``,
  ``review_score``→``nota``, ``review_comment_title``→``titulo``,
  ``review_comment_message``→``comentario``,
  ``review_creation_date``→``data_criacao``,
  ``review_answer_timestamp``→``data_resposta``.

TIPOS E CONVERSÕES
------------------
Datas com hora são TIMESTAMP via ``strptime`` no formato
``%Y-%m-%d %H:%M:%S``: ``data_compra``, ``data_aprovacao``, ``data_envio``,
``data_entrega``, ``data_limite_envio`` e ``data_resposta``. O formato
declarado evita inferência ambígua. ``data_entrega_prevista`` é DATE porque
a hora é 00:00:00 em todas as 99.441 linhas; guardar essa hora inventaria
precisão. ``data_criacao`` também é DATE: nas 99.224 avaliações, 99.139
horas são 00:00:00 e as outras 85 são 01:00:00 por horário de verão, não
horário real.

``preco``, ``frete`` e ``valor`` são DECIMAL(10,2), pois DOUBLE não
representa centavos com exatidão e a soma de dinheiro deve fechar.
``item_seq``, ``pagamento_seq``, ``parcelas``, ``tamanho_nome``,
``tamanho_descricao``, ``qtd_fotos``, ``peso_g``, ``comprimento_cm``,
``altura_cm``, ``largura_cm`` e ``nota`` são INTEGER por serem contagens ou
medidas inteiras. Todo o resto permanece VARCHAR, inclusive ``cep_prefixo``:
23.995 clientes têm CEP iniciado por zero; CEP é identificador, não medida,
e convertê-lo em número apagaria esse zero.

DuckDB executa as conversões em SQL, pois os dados já estão no banco e não
precisam ir à memória Python para conversão. ``strptime`` e ``CAST`` são
estritos. Se um valor não converter, a execução informa tabela, coluna e
exemplo e termina com código 1. Não se usa TRY_* nem coerção para NULL,
porque um nulo fabricado ficaria indistinguível de um nulo original.

DUPLICATAS E NULOS
------------------
As chaves são ``pedidos(pedido_id)``,
``itens_pedido(pedido_id, item_seq)``,
``pagamentos(pedido_id, pagamento_seq)``, ``clientes(cliente_id)``,
``vendedores(vendedor_id)``, ``produtos(produto_id)``,
``traducao_categorias(categoria)`` e
``avaliacoes(avaliacao_id, pedido_id)``. ``avaliacao_id`` sozinho não é
chave, pois um mesmo id pode aparecer em mais de um pedido. SELECT DISTINCT
mantém uma cópia de linha inteira repetida e a contagem informa quantas
saíram. Chave com conteúdo diferente interrompe a execução e mostra chave e
linhas conflitantes: escolher uma seria decidir silenciosamente.

Nenhuma linha é removida por ter NULL e nenhum NULL é preenchido. Datas de
pedido ausentes podem indicar cancelamento e não entrega; os 610 produtos
sem categoria devem receber qualquer rótulo somente por decisão do mart;
avaliações sem título ou comentário são regra, não exceção. Anomalias de
negócio (como entrega ausente, envio anterior à compra ou mais de uma
avaliação por pedido) também ficam em ``refined``: quem decide seu tratamento
é a pergunta que o mart responde.

SAÍDA E ERROS
-------------
Antes de transformar, verifica as oito entradas em ``raw``. Se faltar uma,
lista as ausentes, indica ``uv run python -m pipeline.ingestao`` e termina
com código 1. Todas as validações ocorrem antes de criar ou substituir saída,
para que falta, conversão inválida ou conflito não deixe tabelas parciais.
Cada tabela de ``refined`` é criada com CREATE OR REPLACE TABLE: reexecutar
substitui dados, nunca acrescenta. A tela mostra uma linha por tabela com
entrada, saída e duplicatas removidas, depois NULLs mantidos por coluna e
total; contagens vêm do banco e o stdout é UTF-8 para acentos no Windows.
"""

import re
import sys

import duckdb

from pipeline.db import conectar, criar_schema


FORMATO_TIMESTAMP = "%Y-%m-%d %H:%M:%S"

TABELAS = {
    "pedidos": {
        "chave": ("pedido_id",),
        "colunas": (
            ("order_id", "pedido_id", None),
            ("customer_id", "cliente_id", None),
            ("order_status", "status", None),
            ("order_purchase_timestamp", "data_compra", "TIMESTAMP"),
            ("order_approved_at", "data_aprovacao", "TIMESTAMP"),
            ("order_delivered_carrier_date", "data_envio", "TIMESTAMP"),
            ("order_delivered_customer_date", "data_entrega", "TIMESTAMP"),
            ("order_estimated_delivery_date", "data_entrega_prevista", "DATE"),
        ),
    },
    "itens_pedido": {
        "chave": ("pedido_id", "item_seq"),
        "colunas": (
            ("order_id", "pedido_id", None),
            ("order_item_id", "item_seq", "INTEGER"),
            ("product_id", "produto_id", None),
            ("seller_id", "vendedor_id", None),
            ("shipping_limit_date", "data_limite_envio", "TIMESTAMP"),
            ("price", "preco", "DECIMAL(10,2)"),
            ("freight_value", "frete", "DECIMAL(10,2)"),
        ),
    },
    "pagamentos": {
        "chave": ("pedido_id", "pagamento_seq"),
        "colunas": (
            ("order_id", "pedido_id", None),
            ("payment_sequential", "pagamento_seq", "INTEGER"),
            ("payment_type", "tipo", None),
            ("payment_installments", "parcelas", "INTEGER"),
            ("payment_value", "valor", "DECIMAL(10,2)"),
        ),
    },
    "clientes": {
        "chave": ("cliente_id",),
        "colunas": (
            ("customer_id", "cliente_id", None),
            ("customer_unique_id", "cliente_unico_id", None),
            ("customer_zip_code_prefix", "cep_prefixo", None),
            ("customer_city", "cidade", None),
            ("customer_state", "uf", None),
        ),
    },
    "vendedores": {
        "chave": ("vendedor_id",),
        "colunas": (
            ("seller_id", "vendedor_id", None),
            ("seller_zip_code_prefix", "cep_prefixo", None),
            ("seller_city", "cidade", None),
            ("seller_state", "uf", None),
        ),
    },
    "produtos": {
        "chave": ("produto_id",),
        "colunas": (
            ("product_id", "produto_id", None),
            ("product_category_name", "categoria", None),
            ("product_name_lenght", "tamanho_nome", "INTEGER"),
            ("product_description_lenght", "tamanho_descricao", "INTEGER"),
            ("product_photos_qty", "qtd_fotos", "INTEGER"),
            ("product_weight_g", "peso_g", "INTEGER"),
            ("product_length_cm", "comprimento_cm", "INTEGER"),
            ("product_height_cm", "altura_cm", "INTEGER"),
            ("product_width_cm", "largura_cm", "INTEGER"),
        ),
    },
    "traducao_categorias": {
        "chave": ("categoria",),
        "colunas": (
            ("product_category_name", "categoria", None),
            ("product_category_name_english", "categoria_en", None),
        ),
    },
    "avaliacoes": {
        "chave": ("avaliacao_id", "pedido_id"),
        "colunas": (
            ("review_id", "avaliacao_id", None),
            ("order_id", "pedido_id", None),
            ("review_score", "nota", "INTEGER"),
            ("review_comment_title", "titulo", None),
            ("review_comment_message", "comentario", None),
            ("review_creation_date", "data_criacao", "DATE"),
            ("review_answer_timestamp", "data_resposta", "TIMESTAMP"),
        ),
    },
}


def _identificador(nome):
    return '"' + nome.replace('"', '""') + '"'


def _expressao(origem, tipo):
    coluna = _identificador(origem)
    if tipo == "TIMESTAMP":
        return f"strptime({coluna}, '{FORMATO_TIMESTAMP}')"
    if tipo is not None:
        return f"CAST({coluna} AS {tipo})"
    return coluna


def _select_transformacao(tabela):
    colunas = TABELAS[tabela]["colunas"]
    selecao = ", ".join(
        f"{_expressao(origem, tipo)} AS {_identificador(destino)}"
        for origem, destino, tipo in colunas
    )
    return f"SELECT DISTINCT {selecao} FROM raw.{_identificador(tabela)}"


def _exemplo_da_falha(mensagem):
    padroes = (
        r"""Could not parse string\s+(['"])(.*?)\1""",
        r"""Could not convert string\s+(['"])(.*?)\1""",
        r"""invalid date field format:\s*(['"])(.*?)\1""",
    )
    for padrao in padroes:
        resultado = re.search(padrao, mensagem, re.IGNORECASE | re.DOTALL)
        if resultado:
            return repr(resultado.group(2))
    return f"valor indicado pelo DuckDB: {mensagem}"


def _validar_conversoes(con, tabela):
    for origem, destino, tipo in TABELAS[tabela]["colunas"]:
        if tipo is None:
            continue
        expressao = _expressao(origem, tipo)
        consulta = (
            f"SELECT count({expressao}) "
            f"FROM raw.{_identificador(tabela)}"
        )
        try:
            con.execute(consulta).fetchone()
        except duckdb.Error as erro:
            exemplo = _exemplo_da_falha(str(erro))
            print(
                f"Falha de conversão em raw.{tabela}.{origem} "
                f"(refined.{tabela}.{destino}); exemplo: {exemplo}",
                file=sys.stderr,
            )
            raise SystemExit(1) from erro


def _consulta_conflitos(tabela):
    chaves = TABELAS[tabela]["chave"]
    nomes_chave = ", ".join(_identificador(nome) for nome in chaves)
    colunas = TABELAS[tabela]["colunas"]
    struct = ", ".join(
        f"c{indice} := {_identificador(destino)}"
        for indice, (_, destino, _) in enumerate(colunas)
    )
    selecao = _select_transformacao(tabela)
    return (
        f"SELECT transformada.* "
        f"FROM ({selecao}) AS transformada "
        f"JOIN ("
        f"SELECT {nomes_chave} "
        f"FROM ({selecao}) AS linhas "
        f"GROUP BY {nomes_chave} "
        f"HAVING count(DISTINCT struct_pack({struct})) > 1"
        f") AS conflitos USING ({nomes_chave}) "
        f"ORDER BY {nomes_chave}"
    )


def _contagem_nulos(con, schema, tabela, colunas):
    expressoes = ", ".join(
        f"count(*) FILTER (WHERE {_identificador(coluna)} IS NULL)"
        for coluna in colunas
    )
    return con.execute(
        f"SELECT {expressoes} "
        f"FROM {_identificador(schema)}.{_identificador(tabela)}"
    ).fetchone()


def _formatar_quantidade(quantidade):
    return f"{quantidade:,}".replace(",", ".")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = conectar()
    try:
        existentes = {
            linha[0]
            for linha in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'raw'"
            ).fetchall()
        }
        faltantes = [tabela for tabela in TABELAS if tabela not in existentes]
        if faltantes:
            print("Tabelas ausentes em raw:", file=sys.stderr)
            for tabela in faltantes:
                print(f"  raw.{tabela}", file=sys.stderr)
            print(
                'Rode "uv run python -m pipeline.ingestao" antes da '
                "transformação.",
                file=sys.stderr,
            )
            raise SystemExit(1)

        contagens_entrada = {}
        contagens_saida = {}
        for tabela in TABELAS:
            _validar_conversoes(con, tabela)
            contagens_entrada[tabela] = con.execute(
                f"SELECT count(*) FROM raw.{_identificador(tabela)}"
            ).fetchone()[0]
            consulta = _select_transformacao(tabela)
            contagens_saida[tabela] = con.execute(
                f"SELECT count(*) FROM ({consulta}) AS transformada"
            ).fetchone()[0]

            cursor_conflitos = con.execute(_consulta_conflitos(tabela))
            nomes_colunas = [coluna[0] for coluna in cursor_conflitos.description]
            conflitos = cursor_conflitos.fetchall()
            if conflitos:
                print(
                    f"Chave repetida com conteúdo diferente em raw.{tabela}; "
                    "chave e linhas conflitantes:",
                    file=sys.stderr,
                )
                for linha in conflitos:
                    valores = dict(zip(nomes_colunas, linha))
                    chave = {
                        coluna: valores[coluna]
                        for coluna in TABELAS[tabela]["chave"]
                    }
                    print(
                        f"  chave={chave}; linha={valores}",
                        file=sys.stderr,
                    )
                raise SystemExit(1)

        criar_schema(con, "refined")
        total = 0
        for tabela, definicao in TABELAS.items():
            con.execute(
                f"CREATE OR REPLACE TABLE "
                f"refined.{_identificador(tabela)} AS "
                f"{_select_transformacao(tabela)}"
            )
            quantidade_saida = con.execute(
                f"SELECT count(*) "
                f"FROM refined.{_identificador(tabela)}"
            ).fetchone()[0]
            quantidade_entrada = contagens_entrada[tabela]
            duplicatas = quantidade_entrada - contagens_saida[tabela]
            total += quantidade_saida

            print(
                f"{f'refined.{tabela}':<29}"
                f"{_formatar_quantidade(quantidade_entrada)} -> "
                f"{_formatar_quantidade(quantidade_saida)} linhas  "
                f"({_formatar_quantidade(duplicatas)} duplicatas)"
            )

            colunas_saida = [destino for _, destino, _ in definicao["colunas"]]
            nulos = _contagem_nulos(con, "refined", tabela, colunas_saida)
            mantidos = [
                f"{coluna} {_formatar_quantidade(quantidade)}"
                for coluna, quantidade in zip(colunas_saida, nulos)
                if quantidade
            ]
            if mantidos:
                print(f"    nulos mantidos: {', '.join(mantidos)}")

        print(f"Total: {_formatar_quantidade(total)}")
    finally:
        con.close()


if __name__ == "__main__":
    main()
