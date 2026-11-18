# Baya SEO / AEO / GEO routine

Draft-only. Once a day (after `SEO_ROUTINE_HOUR`, local time, when `SEO_ROUTINE_ENABLED=1`) Baya's worker covers the site that was checked longest ago (sites in `seo_sites.json`): read-only snapshot, diff against last run, the model picks one uncovered question, then a draft and a report are saved in `seo/<site>/`. Nothing is published, posted or sent. Drafts are flagged if they contain forbidden claims (guarantees, fees, discounts, counts).

Manual: `python -m app.routines.seo_routine --site wae-academy [--dry-run]`
Know it ran: new `seo/<site>/<date>-report.md`, `seo/<site>/.baya_state.json` (last_run), `seo/.baya_last_run`, worker log.
Tests: `python -m unittest tests.test_seo_routine`
