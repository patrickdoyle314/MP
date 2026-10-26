-- Caseload by region and case type for children, on the dummy practice database (synthetic data).
--
-- Uses: four joins (cases -> agencies -> states -> regions, and cases -> case_types) and aggregate
-- functions COUNT, COUNT(column), COUNT(DISTINCT), AVG, MEDIAN and SUM(CASE ...), filtered with HAVING.
-- Build the database first: python sql/practice/build_practice_db.py
-- Run: python sql/run_sql.py sql/practice/caseload_by_region.sql --db sql/practice/practice.duckdb

-- HOW TO READ THIS QUERY
-- Business question: for children, how many cases does each region have by case type, how many were
-- resolved, and how fast? SELECT lists the output columns; FROM/JOIN says where they come from.
SELECT
    r.region_name,
    ct.case_type_name,
    COUNT(*)                                                         AS cases,
    COUNT(c.resolved_on)                                             AS resolved,  -- COUNT(column) skips blanks (NULL), so this counts only resolved cases
    ROUND(100.0 * COUNT(c.resolved_on) / COUNT(*), 1)                AS pct_resolved,
    -- Conditional counting: CASE WHEN ... THEN 1 ELSE 0 END turns each row into 1 or 0; SUM adds them up.
    CAST(SUM(CASE WHEN date_diff('day', c.reported_on, c.resolved_on) <= 30
                  THEN 1 ELSE 0 END) AS INTEGER)                     AS resolved_within_30_days,
    ROUND(AVG(date_diff('day', c.reported_on, c.resolved_on)), 1)    AS avg_days_to_resolve,
    MEDIAN(date_diff('day', c.reported_on, c.resolved_on))           AS median_days_to_resolve,
    COUNT(DISTINCT a.agency_id)                                      AS agencies_reporting
-- Joins link tables by their shared ids: each case -> its agency -> that agency's state -> the state's
-- region, and each case -> its case type name. "AS c" gives a table a short alias.
FROM cases AS c
JOIN agencies   AS a  ON a.agency_id     = c.agency_id
JOIN states     AS s  ON s.state_code    = a.state_code
JOIN regions    AS r  ON r.region_id     = s.region_id
JOIN case_types AS ct ON ct.case_type_id = c.case_type_id
WHERE c.age_group = 'child'
GROUP BY r.region_name, ct.case_type_name  -- one output row per region and case type
HAVING COUNT(*) >= 5  -- HAVING filters groups after counting (WHERE filters rows before): hide tiny groups
ORDER BY r.region_name, cases DESC;
