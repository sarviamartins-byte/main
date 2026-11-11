-- Quanto vendemos por estado do cliente (tabela refined.clientes)
SELECT 
    uf AS estado,
    count(DISTINCT p.pedido_id) AS total_pedidos,
    sum(i.preco) AS receita_total
FROM refined.pedidos AS p 
JOIN refined.itens_pedido AS i ON i.pedido_id = p.pedido_id 
JOIN refined.clientes AS c ON c.cliente_id = p.cliente_id 
WHERE p.status NOT IN ('canceled', 'unavailable') 
GROUP BY c.uf 
ORDER BY receita_total DESC;