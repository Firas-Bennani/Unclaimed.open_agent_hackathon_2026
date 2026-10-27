# Decisions log (one line each)

- 11:50 Nemotron via `https://integrate.api.nvidia.com/v1`; reasoning = `nvidia/nemotron-3-ultra-550b-a55b`, extraction = `nvidia/nemotron-3.5-lightning-30b-a3b` (super-120b and nano-3 returned 404 for this account).
- 11:52 Docker daemon unavailable → no-Docker path is primary; DWP source uses SQLite locally, Postgres via compose (`DWP_DB_URL`).
- 11:52 Zetaris/Meterless: no public API without human access → ship interfaces + local fallbacks, say so plainly in the README.
- 13:05 Label/reference disagreement HH-046 (income £290, savings missing): I had labelled no escalations; reference says CTR must escalate (taper still leaves a reduction if capital ≤ £16k). Checked by hand: reference correct, label fixed.
