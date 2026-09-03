-- This query returns a table that displays the headcount for the fall term
-- The same query can be used for any term by simply changing the t.season parameter

SELECT t.label, COUNT(*) AS headcount
FROM enrollments e
JOIN terms t ON t.term_id = e.term_id
WHERE t.season = 'Fall'
GROUP BY t.label, t.term_id
ORDER BY t.term_id;