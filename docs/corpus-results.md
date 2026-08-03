# Corpus results

Model: `claude-haiku-4-5-20251001`. 14/15 labels landed in an accepted verdict.
Latency: min 3.1s, median 4.1s, max 6.7s.

| Label | Tests | Accepted | Result | Seconds |
|---|---|---|---|---|
| clean_bourbon.png | Happy path, everything matches | pass | pass | 5.2 |
| stones_throw.png | Fuzzy brand judgment: caps difference is REVIEW, not FAIL | review | review | 4.2 |
| warning_title_case.png | Warning capitalization: title case must fail | fail | fail | 4.1 |
| warning_reworded.png | Warning wording: reworded statement must fail | fail | fail | 3.6 |
| warning_missing.png | Missing warning statement entirely | fail | fail | 6.7 |
| abv_mismatch.png | Label ABV 40 vs application 45 | fail | fail | 3.9 |
| net_contents_700.png | Net contents 700 mL vs application 750 mL | fail | fail | 3.9 |
| table_wine.png | Table wine ABV exception: no numeric ABV is compliant | pass | pass | 4.0 |
| proof_inconsistent.png | Proof does not equal 2 x ABV, internal consistency check | review | review | 4.0 |
| warning_not_bold.png | GOVERNMENT WARNING not bold, best-effort visual check | fail|review | pass (MISS) | 4.3 |
| import_no_country.png | Imported spirit missing country of origin | fail | fail | 4.3 |
| blurry_bourbon.png | Badly blurred photo, graceful degradation | unreadable|review | unreadable | 3.1 |
| glare_bourbon.png | Heavy glare over the warning area | review|unreadable | review | 3.5 |
| angled_bourbon.png | Photo taken at a sharp angle | review|unreadable | review | 4.4 |
| dim_bourbon.png | Dark, low-contrast photo | review|unreadable | unreadable | 4.6 |

## Model choice finding

Haiku 4.5 and Sonnet both score 14/15, but they miss DIFFERENT labels and the
difference decides the default:

- Haiku misses `warning_not_bold` (it assumes an all-caps GOVERNMENT WARNING is
  bold). The bold sub-check is best-effort by design and reported as such.
- Sonnet misses `warning_title_case`: it silently transcribes "Government
  Warning" as "GOVERNMENT WARNING", auto-correcting the exact defect the tool
  must catch (reproduced 2/2; Haiku reads it verbatim 2/2). A transcriber that
  fixes violations is unusable for compliance, so this miss is disqualifying.
- Latency: Haiku median ~4s vs Sonnet median ~5.2s against a 5 second budget.
  Haiku is also roughly 10x cheaper per label.

Default model: claude-haiku-4-5 (env-overridable via TTB_VISION_MODEL).
