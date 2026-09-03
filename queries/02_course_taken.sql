-- This query returns a table that displays each course in order of how many times the course was taken
-- We observe that the results are very even as our data generator "randomly" assigns courses causing it to evenly distribute across courses.

SELECT c.title, COUNT(*) as taken
from courses c
join course_enrollments e on c.course_id = e.course_id 
group by c.title 
order by taken desc