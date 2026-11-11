-- Quanto cada cliente comprou por mês
SELECT 
    date_trunc('month', p.data_compra)::DATE AS mes,
    p.cliente_id,
    count(DISTINCT p.pedido_id) AS pedidos,
    sum(i.preco) AS receita
FROM refined.pedidos AS p 
JOIN refined.itens_pedido AS i ON i.pedido_id = p.pedido_id 
WHERE p.status NOT IN ('canceled', 'unavailable') 
GROUP BY mes, p.cliente_id 
ORDER BY mes, receita DESC;