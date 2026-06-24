-- @param search_id STRING
SELECT
  CONCAT(CAST(CAST(FLOOR(rating) AS INT) AS STRING), ' stars') AS rating_bucket,
  COUNT(*) AS businesses
FROM users.toms_nimbleway_com.local_biz_scout
WHERE (:search_id = '' OR search_id = :search_id)
  AND rating IS NOT NULL
GROUP BY FLOOR(rating)
ORDER BY FLOOR(rating) ASC
