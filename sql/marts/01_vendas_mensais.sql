-- Quanto cada vendedor vendeu por mês?
-- Grão: um mês de compra por vendedor.
SELECT
    date_trunc('month', p.data_compra)::DATE AS mes,
    i.vendedor_id                            AS vendedor_id, -- Adicionado o vendedor
    count(DISTINCT p.pedido_id)              AS pedidos,
    sum(i.preco)                             AS receita
FROM refined.pedidos      AS p
JOIN refined.itens_pedido AS i ON i.pedido_id = p.pedido_id
WHERE p.status NOT IN ('canceled', 'unavailable')
GROUP BY mes, vendedor_id -- Adicionado o vendedor no agrupamento
ORDER BY mes, receita DESC