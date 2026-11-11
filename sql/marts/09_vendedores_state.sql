-- Concentração de vendedores.
SELECT 
    seller_state AS estado,
    count(DISTINCT seller_id) AS total_vendedores
FROM raw.vendedores
GROUP BY seller_state
ORDER BY total_vendedores DESC;
