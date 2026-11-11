"""Spec da ingestão literal dos nove arquivos públicos para o schema ``raw``.

Mapa completo e literal de arquivo para tabela:

* ``olist_orders_dataset.csv.gz`` → ``pedidos``
* ``olist_order_items_dataset.csv.gz`` → ``itens_pedido``
* ``olist_order_payments_dataset.csv.gz`` → ``pagamentos``
* ``olist_order_reviews_dataset.csv.gz`` → ``avaliacoes``
* ``olist_customers_dataset.csv.gz`` → ``clientes``
* ``olist_sellers_dataset.csv.gz`` → ``vendedores``
* ``olist_products_dataset.csv.gz`` → ``produtos``
* ``product_category_name_translation.csv.gz`` → ``traducao_categorias``
* ``olist_geolocation_dataset.csv.gz`` → ``geolocalizacao``

Os destinos em português são o vocabulário dos JOINs das próximas aulas.
Todos os nove arquivos são verificados antes de abrir o banco; se algum faltar,
seus nomes e a pasta procurada são informados e o processo termina com código
1. Isso impede uma ingestão parcial que pareça completa.

Os arquivos gzip são lidos diretamente, com ``encoding="utf-8"`` e
``dtype=str``. Só o campo vazio vira nulo; marcadores textuais como ``NA`` não
são reinterpretados. Não há conversão de tipos, inferência, descarte,
deduplicação, renomeação de coluna, correção, preenchimento ou normalização de
valores. Essa fronteira preserva o dado recebido e deixa decisões para a
passagem de ``raw`` para ``refined``.

Cada tabela é substituída (nunca acrescida), para que reexecutar a etapa tenha
o mesmo resultado. A saída tem uma linha por tabela qualificada, com contagem
lida do banco e milhar separado por ponto, seguida do total; a soma esperada é
1.550.922 registros e serve como conferência da ingestão. O stdout é
reconfigurado para UTF-8 porque o Prompt de Comando do Windows pode exibir
acentos incorretamente com a codificação padrão.
"""

import sys

import pandas as pd

from pipeline.db import PASTA_RAW, conectar, criar_schema, gravar


ARQUIVOS = (
    ("olist_orders_dataset.csv.gz", "pedidos"),
    ("olist_order_items_dataset.csv.gz", "itens_pedido"),
    ("olist_order_payments_dataset.csv.gz", "pagamentos"),
    ("olist_order_reviews_dataset.csv.gz", "avaliacoes"),
    ("olist_customers_dataset.csv.gz", "clientes"),
    ("olist_sellers_dataset.csv.gz", "vendedores"),
    ("olist_products_dataset.csv.gz", "produtos"),
    ("product_category_name_translation.csv.gz", "traducao_categorias"),
    ("olist_geolocation_dataset.csv.gz", "geolocalizacao"),
)


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    faltantes = [arquivo for arquivo, _ in ARQUIVOS if not (PASTA_RAW / arquivo).is_file()]
    if faltantes:
        print(f"Arquivos ausentes em {PASTA_RAW}:", file=sys.stderr)
        for arquivo in faltantes:
            print(f"  {arquivo}", file=sys.stderr)
        sys.exit(1)

    con = conectar()
    try:
        criar_schema(con, "raw")
        total = 0
        for arquivo, tabela in ARQUIVOS:
            df = pd.read_csv(
                PASTA_RAW / arquivo,
                compression="gzip",
                encoding="utf-8",
                dtype=str,
                keep_default_na=False,
                na_values=[""],
            )
            quantidade = gravar(con, df, "raw", tabela)
            total += quantidade
            print(f"raw.{tabela}: {quantidade:,}".replace(",", "."))
        print(f"Total: {total:,}".replace(",", "."))
    finally:
        con.close()


if __name__ == "__main__":
    main()
