# Exchange contract (v1.0)

Adjacent projects share **aggregate tables only**, through files. Each project writes its own
`exchange/outbox/` and reads a peer's outbox. Nothing else crosses: no raw records, no
names, no case numbers, no coordinates, nothing finer than fiscal year.

The core sections below (Files, Table schema, Rules, Versioning) are identical in every project
that uses this contract. Each project then lists its own measures.

## Files

```
exchange/
  EXCHANGE.md          this contract
  export_exchange.py   writes the outbox
  outbox/              generated, not committed
    aggregates.csv     one table, long format
    manifest.json      who produced it, when, from what, and what every measure means
```

A consumer finds a peer's outbox by path, `../<peer-folder>/exchange/outbox` by default, or by a
`--peer` argument.

## Table schema (`aggregates.csv`)

| column | type | meaning |
|---|---|---|
| `geo_level` | `national`, `state`, `county`, `other_counties` | Geographic level of the row |
| `state` | USPS code (e.g. `TX`) or empty for national | State |
| `county_key` | `name|ST`, lower case, without "county"/"parish" (e.g. `harris|TX`), or empty | County key; FIPS is planned for v1.1 |
| `county_name` | text or empty | Display name |
| `fiscal_year` | integer, or empty for measures without a year | Federal fiscal year, October–September (FY2023 = Oct 1, 2022 – Sep 30, 2023) |
| `measure` | identifier from the producer's measure list | What is counted |
| `value` | number | The count |
| `publishable` | `true` / `false` | `false` when the count is below the producer's publication threshold |

`manifest.json` holds `producer`, `contract_version`, `generated_at`, `source` (what data and
which snapshot date), `publication_threshold`, `row_count` and `measures` (identifier → description).

## Rules

1. **Aggregates only.** A row never describes one person or one household.
2. **Small counts stay unpublished.** Exact values may cross between projects on the same computer,
   but any row with `publishable = false`, and any figure derived from such a row, must be shown as
   "fewer than *threshold*" in anything published (reports, repositories, apps, write-ups).
3. **No back-calculation.** A consumer never reconstructs a value that the producer or the original
   source withheld (for example, counties a source suppresses).
4. **Outboxes are generated and local.** `exchange/outbox/` is not committed to any repository.
5. **Check the version.** A consumer refuses an outbox whose major `contract_version` differs from its own.

## Versioning

- **1.0** (2026-10-22): first version. File-based publish-and-read.
- **Planned 1.1:** county FIPS codes alongside `county_key`.
- **Planned 2.0:** requests. A consumer writes `exchange/requests.json` naming the measures and
  periods it wants; the producer answers in its outbox and logs each answer, refusing any request
  that would let a withheld value be worked out by subtraction.

## Measures produced by this project (MP: missing children and young adults)

Counts of **open** NamUs and NCMEC cases on the collection date, by the fiscal year and state of
last contact. Publication threshold: 5.

| measure | levels | meaning |
|---|---|---|
| `open_cases_u18` | national, state | Open cases where the person was under 18 when last seen |
| `open_cases_18_25` | national, state | Open cases aged 18–25 when last seen |
| `open_cases_u18_with_county` | national | Under-18 cases whose record names a county |
| `open_cases_u18_tag:<tag>` | national, state | Under-18 cases matching a locally defined tag rule (see below) |
| `open_cases_u18_in_peer_county_same_fy` | national | Under-18 cases last seen in a county that the peer's outbox lists for that fiscal year |
| `open_cases_u18_tag:<tag>_in_peer_county_same_fy` | national | The same, for a tag |
| `census_pop_u18_2024` | state | U.S. Census Bureau 2024 civilian population aged 0–17 (Vintage 2024 estimates) |

**Tags** are rules that match wording in public case summaries. They are defined in
`exchange/tags.local.json`, which stays on the local computer and is never committed. If that
file is absent, no tag measures are produced.
