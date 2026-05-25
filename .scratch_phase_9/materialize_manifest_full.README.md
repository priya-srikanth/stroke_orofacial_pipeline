# materialize_manifest_full.csv — provenance legend

Unified Phase 9 Task 2 materialization manifest. Merges three source manifests + the
lick_switch_rate flip + the 3 Commit C v1 orphan annotations into a single CSV with a
`materializer_pass` provenance column.

Regenerate via `python .scratch_phase_9/_aggregate_manifests.py` from the repo root.
The script reads from `materialize_manifest.csv` (Commit A + Commit B), `_smoke_lsr_flip.csv`
(Commit A close re-emit), and `materialize_spatial_manifest.csv` (Commit C v3 cohort emit).

## `materializer_pass` values

| value | meaning |
|---|---|
| `commit_a` | 256 non-spatial endpoints emitted in Phase 9 Commit A (commit `18aa566`). |
| `commit_b_latency_hist` | 8 `latency_hist` parquets emitted in Phase 9 Commit B (commit `36b7a0c`). |
| `commit_c_v3` | 384 spatial parquets emitted in Phase 9 Commit C v3 cohort run (commits `cfb76aa` + cohort emit 2026-05-23 to 2026-05-24). |
| `lick_switch_rate_flip` | 8 re-emitted parquets at commit `5e78807` — "to" (destination) semantics flip per Priya 2026-05-23 Commit A close approval. SUPERSEDES the 8 lick_switch_rate rows from the original Commit A emit. |
| `commit_c_v1_orphan_superseded_by_addendum_7_rename` | Pre-Addendum-7 slug names from the Commit C v1 smoke (2026-05-23 15:40:54); superseded by `*_tone_aligned_all/` counterparts in the cohort emit; NOT consumed by current pipeline. ~30 KB total, preserved on disk for audit trail rather than deleted per CLAUDE.md Rule 7 anti-pattern guidance (multiple destructive invocations within a single session). |

## Row count sanity check

Source row counts at Task 2 close:

- `materialize_manifest.csv`: 264 rows (256 Commit A + 8 Commit B). The 8 `lick_switch_rate`
  rows here reflect the ORIGINAL "from" semantics emit (mtime 14:27); these are EXCLUDED
  from the aggregate and replaced by `_smoke_lsr_flip.csv`.
- `_smoke_lsr_flip.csv`: 8 `lick_switch_rate` rows reflecting the "to" semantics re-emit
  (mtime 17:38).
- `materialize_spatial_manifest.csv`: 384 rows from the Commit C v3 cohort emit (366 success
  + 18 skipped_existing).
- Synthesized orphan annotations: 3 rows (Commit C v1 PS46-tongue parquets at pre-Addendum-7
  slug names).

Aggregate total = (264 − 8) + 8 + 384 + 3 = **651 rows**.

The 1 empty directory (`spatial_wasserstein_jaw_eye_midpoint/`, no parquet inside) is left
unannotated in the manifest since the manifest is parquet-granular; the empty dir is a
harmless filesystem residue.
