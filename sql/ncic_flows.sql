-- FBI NCIC juvenile (under 18) records, 2015-2025: records closed each year, average days open,
-- and change in active records.
--
-- Uses: a CTE; window functions LAG() OVER (the previous published year) and
-- AVG() OVER (moving average of days open over the three most recent published years; with 2021
-- missing, 2022's average covers 2019, 2020 and 2022).
-- Source: models/ncic_juvenile_by_year.csv (yearly FBI reports; 2021 not published online).
-- Run: python sql/run_sql.py sql/ncic_flows.sql

WITH yearly AS (
    SELECT
        year,
        entries_u18,
        active_u18_dec31,
        LAG(year)             OVER (ORDER BY year) AS prev_year,
        LAG(active_u18_dec31) OVER (ORDER BY year) AS prev_active
    FROM read_csv('models/ncic_juvenile_by_year.csv', header = true)
    WHERE entries_u18 IS NOT NULL
)
SELECT
    year,
    entries_u18,
    active_u18_dec31,
    -- closed in the year = open at the start + entered - open at the end (only for consecutive years)
    CASE WHEN year - prev_year = 1
         THEN prev_active + entries_u18 - active_u18_dec31 END                 AS closed_u18,
    ROUND(365.0 * active_u18_dec31 / entries_u18, 1)                           AS avg_days_open,
    ROUND(AVG(365.0 * active_u18_dec31 / entries_u18)
          OVER (ORDER BY year ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1)    AS avg_days_open_3yr,
    CASE WHEN year - prev_year = 1
         THEN ROUND(100.0 * (active_u18_dec31 / prev_active - 1), 1) END       AS active_change_pct
FROM yearly
ORDER BY year;
