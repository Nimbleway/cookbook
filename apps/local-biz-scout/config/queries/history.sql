SELECT
  search_id,
  business_type,
  location,
  COUNT(*)              AS businesses,
  ROUND(AVG(rating), 1) AS avg_rating,
  date_format(MAX(searched_at), 'yyyy-MM-dd HH:mm') AS search_time
FROM users.toms_nimbleway_com.local_biz_scout
GROUP BY search_id, business_type, location
ORDER BY MAX(searched_at) DESC
LIMIT 20
