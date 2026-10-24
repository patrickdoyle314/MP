-- Caseload by region and case type for children, on the dummy practice database (synthetic data).
--
-- Uses: four joins (cases -> agencies -> states -> regions, and cases -> case_types) and aggregate
-- functions COUNT, COUNT(column), COUNT(DISTINCT), AVG, MEDIAN and SUM(CASE ...), filtered with HAVING.
-- Build the database first: python sql/practice/build_practice_db.py
-- Run: python sql/run_sql.py sql/practice/caseload_by_region.sql --db sql/practice/practice.duckdb

SELECT
    r.region_name,
    ct.case_type_name,
    COUNT(*)                                                         AS cases,
    COUNT(c.resolved_on)                                             AS resolved,
    ROUND(100.0 * COUNT(c.resolved_on) / COUNT(*), 1)                AS pct_resolved,
    CAST(SUM(CASE WHEN date_diff('day', c.reported_on, c.resolved_on) <= 30
                  THEN 1 ELSE 0 END) AS INTEGER)                     AS resolved_within_30_days,
    ROUND(AVG(date_diff('day', c.reported_on, c.resolved_on)), 1)    AS avg_days_to_resolve,
    MEDIAN(date_diff('day', c.reported_on, c.resolved_on))           AS median_days_to_resolve,
    COUNT(DISTINCT a.agency_id)                                      AS agencies_reporting
FROM cases AS c
JOIN agencies   AS a  ON a.agency_id     = c.agency_id
JOIN states     AS s  ON s.state_code    = a.state_code
JOIN regions    AS r  ON r.region_id     = s.region_id
JOIN case_types AS ct ON ct.case_type_id = c.case_type_id
WHERE c.age_group = 'child'
GROUP BY r.region_name, ct.case_type_name
HAVING COUNT(*) >= 5
ORDER BY r.region_name, cases DESC;
