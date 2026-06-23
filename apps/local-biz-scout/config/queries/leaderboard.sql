-- @param search_id STRING
SELECT
  name,
  rating,
  review_count,
  price_level,
  address,
  category,
  place_url,
  search_title
FROM users.toms_nimbleway_com.local_biz_scout
WHERE (:search_id = '' OR search_id = :search_id)
  AND name IS NOT NULL
ORDER BY rating DESC NULLS LAST, review_count DESC NULLS LAST
LIMIT 50
