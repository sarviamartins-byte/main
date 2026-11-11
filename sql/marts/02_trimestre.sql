-- Quanto vendemos por trimestre? -- Grão: um trimestre de compra.
SELECT 
    date_trunc('quarter', p.data_compra)::DATE AS trimestre,
    count(DISTINCT p.pedido_id) AS pedidos,
    sum(i.preco) AS receita
FROM refined.pedidos AS p 
JOIN refined.itens_pedido AS i ON i.pedido_id = p.pedido_id 
WHERE p.status NOT IN ('canceled', 'unavailable') 
GROUP BY trimestre 
ORDER BY trimestre;