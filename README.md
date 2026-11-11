# Análise de dados de e-commerce Olist

Projeto de engenharia e análise de dados com o conjunto público de e-commerce da Olist. O pipeline carrega os arquivos CSV compactados, organiza os dados em camadas no DuckDB, produz tabelas analíticas e disponibiliza um painel interativo em Streamlit.

## Requisitos

- Python 3.13 ou superior
- [uv](https://docs.astral.sh/uv/)
- Os arquivos `.csv.gz` esperados na pasta `raw/` (já incluídos neste projeto)

As dependências Python são declaradas em `pyproject.toml` e fixadas em `uv.lock`.

## Instalação e execução

Na raiz do projeto, instale as dependências:

```bash
uv sync
```

Execute as etapas na ordem abaixo:

```bash
# 1. Carrega os arquivos compactados no schema raw
uv run python -m pipeline.ingestao

# 2. Renomeia, tipa e valida os dados no schema refined
uv run python -m pipeline.transformacao

# 3. Executa as consultas SQL e recria as tabelas do schema marts
uv run python -m pipeline.marts
```

O banco `olist.duckdb` é criado na raiz do projeto. As etapas podem ser reexecutadas: a ingestão substitui suas tabelas, a transformação recria as tabelas `refined` e a execução dos marts substitui o schema `marts`.

## Painel Streamlit

Para abrir o painel analítico com os marts já gerados:

```bash
uv run streamlit run app.py
```

A página usa `layout="wide"`, exibe os cartões, o faturamento por mês e os principais gráficos de categoria, UF, nota e concentração de vendedores. O filtro de período afeta somente o gráfico mensal; os cartões e os demais gráficos permanecem sobre o período inteiro.

O botão `Recarregar dados` limpa o cache de leitura e faz a tela reabrir os marts do DuckDB. Se o banco ou algum mart necessário estiver ausente, a aplicação informa o problema e orienta para `uv run python -m pipeline.marts`.

## Relatório HTML

Para gerar o relatório HTML estático com os marts existentes:

```bash
uv run python relatorio.py
```

O comando cria `relatorio.html` na raiz do projeto; abra o arquivo no navegador. Os gráficos carregam a biblioteca Plotly pelo CDN.

## Interface web do DuckDB

Para abrir a interface web do DuckDB depois de gerar o banco:

```bash
uv run python ui.py
```

A interface fica disponível em <http://localhost:4213>. Encerre o processo com `Ctrl+C`. A primeira execução pode precisar baixar a extensão `ui` do DuckDB. Feche a interface antes de executar novamente qualquer etapa que escreva no banco, pois o DuckDB mantém um lock exclusivo no arquivo.

## MCP DuckDB

O workspace configura um servidor MCP local em `.vscode/mcp.json`, executado com `uv run python -m pipeline.mcp`. Ele usa a mesma versão de DuckDB do projeto, abre `olist.duckdb` em modo somente leitura e desabilita acesso a arquivos externos. A ferramenta SQL aceita apenas uma instrução `SELECT`. Ao alterar dependências ou a configuração MCP, reinicie o servidor MCP do workspace para aplicar as mudanças.

## Pipeline e dados

O fluxo usa três schemas no banco:

| Camada | Conteúdo |
| --- | --- |
| `raw` | Cópias das nove fontes carregadas sem conversão de tipos, mantendo os nomes originais das colunas. Campos vazios são gravados como `NULL`. |
| `refined` | Oito tabelas com colunas em português, tipos apropriados para datas e valores numéricos, e validações de conversão e chaves. Duplicatas de linhas inteiras são removidas; nulos são preservados. |
| `marts` | Tabelas analíticas produzidas exclusivamente pelas consultas em `sql/marts/`. O schema é recriado a cada execução. |

As fontes em `raw/` cobrem pedidos, itens, pagamentos, avaliações, clientes, vendedores, produtos, tradução de categorias e geolocalização. A geolocalização é preservada em `raw`, mas não é transformada porque os marts atuais não a utilizam.

As consultas SQL criam os seguintes marts:

1. `vendas_mensais` — pedidos e receita por mês e vendedor.
2. `trimestre` — pedidos e receita por trimestre.
3. `entrega_no_prazo` — desempenho de entregas em relação à data prevista.
4. `nota_por_categoria` — avaliação média por categoria.
5. `venda_por_estado` — pedidos e receita por estado do cliente.
6. `ticket_medio_por_estado` — ticket médio por estado.
7. `mix_pagamento` — distribuição dos meios de pagamento.
8. `nota_por_prazo` — avaliações em relação ao prazo de entrega.
9. `vendedores_state` — contagem de vendedores por estado, consultada de `raw.vendedores`.
10. `tempo_entrega_por_estado` — tempo de entrega por estado.
11. `kpis` — indicadores gerais da operação.
12. `clientes_por_mes` — pedidos e receita mensal por cliente.
13. `vendas_totais_mensais` — receita e pedidos distintos por mês, sem separar vendedores.
14. `clientes_unicos_por_mes` — cadastros de clientes distintos por mês (`cliente_id`).

## Estrutura do projeto

```text
.
├── pipeline/
│   ├── db.py                 # Conexão, schemas e gravação no DuckDB
│   ├── ingestao.py           # CSVs compactados -> raw
│   ├── transformacao.py      # raw -> refined
│   └── marts.py              # SQL -> marts
├── raw/                      # Arquivos-fonte .csv.gz
├── sql/
│   └── marts/                # Consultas analíticas versionadas
├── painel.py                 # Leitura, formatação e gráficos reutilizáveis
├── app.py                    # Painel Streamlit
├── relatorio.py              # Geração do relatório HTML
├── ui.py                     # Inicialização da interface web do DuckDB
├── olist.duckdb              # Banco gerado pelo pipeline
├── test/                     # Testes unitários com pytest e coverage
├── pyproject.toml
└── uv.lock
```

## Testes

A suíte usa `pytest` com `pytest-cov` e valida leitura, transformação, marts, painel e relatório sem depender do banco real do projeto.

```bash
uv run pytest --cov
```

A configuração está em `pyproject.toml` e exige cobertura mínima de 60% do total do projeto (exceto `app.py`, que é a tela Streamlit). Os testes criam um DuckDB temporário em `tmp_path` e geram CSVs gzip pequenos quando necessário.

## Validações e tratamento de falhas

- A ingestão verifica a presença de todos os nove arquivos antes de gravar dados.
- A transformação verifica as tabelas de entrada, conversões de tipos e conflitos nas chaves antes de substituir a saída. Conversões inválidas e chaves repetidas com conteúdo diferente interrompem a etapa.
- Os marts exigem todas as tabelas de `refined`. Cada consulta deve produzir ao menos uma linha; se alguma falhar ou retornar vazia, a transação é revertida e a última versão bem-sucedida dos marts é preservada.
- As mensagens das etapas mostram contagens para facilitar a conferência. Valores nulos de origem não são preenchidos automaticamente.
- O painel e o relatório usam marts prontos; se um mart requerido faltar, a execução para com mensagem clara e orientação para regenerar o banco.

Se uma etapa indicar entradas ausentes, execute primeiro a etapa anterior na sequência do pipeline.
