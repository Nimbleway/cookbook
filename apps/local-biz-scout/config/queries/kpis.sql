-- @param search_id STRING
SELECT
  COUNT(*)                      AS total_businesses,
  ROUND(AVG(rating), 1)         AS avg_rating,
  CAST(AVG(review_count) AS INT) AS avg_reviews
FROM users.toms_nimbleway_com.local_biz_scout
WHERE (:search_id = '' OR search_id = :search_id)
  AND name IS NOT NULL
