# Repo Cleanup Audit — 2026-06

**Chore:** `chore-repo-cleanup` (worktree `stroke_orofacial_pipeline-cleanup`, off `origin/main` @ `34378b7`).
**Stage:** 0 — exhaustive read-only audit. **No deletes, promotions, or branch prunes have been performed.**
**Status:** PAUSED for Priya review. Stage 1 will not start until the Q-locks below are resolved.

> **Discipline applied:** lost-producer anti-pattern from the jaw v3.4 incident
> (`project_jaw_v34_cleanup_overaggressive_existing_parquets`,
> `verify_producer_code_in_repo_before_depending_on_outputs`) — every scratch dir
> was grepped for canonical-data writers (`to_parquet`/`savez`) and each was
> cross-checked against committed `src/`+`scripts/` before being called deletable.

---

## ‼️ Blocking flags — read before Stage 1

1. **GR8 vs. kickoff Stage 1(c) — direct conflict (Q-lock 2).**
   The kickoff instructs `git branch -D <branch>` for squash-merged-equivalent
   branches. **CLAUDE.md GR8 forbids this:** *"Never delete a feature branch with
   `git branch -D` (force-delete)"* and *"Pruning is Priya's call, not Claude
   Code's."* Mechanically, squash-merged branches are **not** ancestors of `main`
   (squash gives the merge a new SHA), so even the safe `git branch -d` will
   **refuse** them — only `-D` works. That is precisely why GR8 routes this to a
   human. **I will not run any `git branch -D` without explicit, per-branch Priya
   approval.** Recommended default: leave local branches in place (their content is
   on origin/main; they are harmless and free).

2. **Named discipline memory does not exist.**
   The kickoff says to read
   `memory/feedback_enumerate_branch_unique_files_before_force_delete.md`. It is
   **not** in the memory tree, and there is no repo-level `memory/` dir. I applied
   the equivalent existing discipline
   (`verify_producer_code_in_repo_before_depending_on_outputs` +
   `project_jaw_v34_cleanup_overaggressive_existing_parquets`). Flagging so the
   reference can be corrected or the memory written.

3. **Two branches the kickoff guessed "obsolete docs" have OPEN PRs.**
   `chore/v7-spatial-impact-audit` → **PR #147 OPEN**;
   `docs/cowork-state-phase-7e-cascade-close` → **PR #146 OPEN**.
   These are in-review work, **not** prune candidates. Do not touch.

4. **One local-only branch carries unique, unmerged work.**
   `investigation/dlc-tongue-quality-severe-acute` — no PR, not on origin
   anywhere, **3 unique commits** (incl. a phase-9.1 figure-module scaffold + V4
   preview emit). Force-deleting it is the exact "lose work" failure the
   discipline guards against. **Do not delete; enumerate + Priya decision (Q-lock).**

---

## A. Scratch directories (`.scratch_*/`)

22 dirs, **2.35 GB** total. `.scratch_*` are gitignored and exist **only in the
main working tree** (`C:\Users\sabatini\GitHub\stroke_orofacial_pipeline`), not in
this worktree — Stage-1 deletes target that path and are branch-independent.
Latest-mtime = newest file under the dir.

### CLOSED-PHASE-SAFE — delete candidates (merged + tagged phases) — **2.3 GB**

| Dir | Size | Latest | Dominant content | Producer (canonical-data) check | Phase tag |
|---|---|---|---|---|---|
| `.scratch_phase_8a_10_1` | **1.9G** | 2026-05-14 | `inspect_npz_output/` (1.9G NPZ scratch copies) + 23 audit py | 5 hits = audit/verify only (no pipeline writer) | `v8a.10.1-tone-reward-swap-fix` |
| `.scratch_phase_7b_light` | **359M** | 2026-05-15 | `spot_check/` (358M parquet/npz copies) + 4 py | savez appears **in comments only** — no producer | `v7b-light-dlc-narrative-cleanup` |
| `.scratch_7a4` | 31M | 2026-04-30 | 66 png renders + 8 py | none | `v7a.3-*` |
| `.scratch_7a6` | 16M | 2026-05-03 | 44 png + 15 py + 4 ipynb | 2 = notebook-gen (`_gen_notebooks_task8`) | 7a (merged) |
| `.scratch_phase_7c2` | 4.5M | 2026-05-21 | 67 py + 38 log + 10 svg + 5 .bak | 3 = manifest-reset / spot-check | `v7c.2-*` |
| `.scratch_phase_7e` | 2.4M | 2026-05-26 | 14 py + 10 png + 4 csv | **see C — `gen_v7_canonical_fixtures.py`** | 7e (merged) |
| `.scratch_phase_8a_10` | 1.5M | 2026-05-13 | 60 py + 21 txt + 11 json | 12 = audit/inspect/update_notebook | `v8a.10-spout-visual-gate` |
| `.scratch_phase_7_pre_aligntmpl` | 364K | 2026-05-22 | 9 py + 8 md + 3 csv | none (producer ported → `scripts/phase_7_pre_aligntmpl/`) | 7-pre (merged) |
| `.scratch_7a3` | 417K | 2026-04-29 | 29 py (legacy cell port-source) | **see C — `tongue_cell36/39.py` velocity_metrics savez** | `v7a.3-tongue-pertrial-features` |
| `.scratch_7a5_mismatch` | 352K | 2026-05-01 | 15 py + 20 .out + 8 md | 1 = audit (`cell_053` to_csv) | 7a (merged) |
| `.scratch_7a3_jaw` | 328K | 2026-05-01 | 3 py + notes | none | `v7a.3-jaw-audit-no-pertrial-features` |
| `.scratch_phase_7d` | 228K | 2026-05-21 | 3 md + 2 txt (notes only) | none | `v7d-*` |
| `.scratch_phase_7_pre` | 171K | 2026-05-12 | 11 py + 12 log | none | 7-pre (merged) |
| `.scratch_phase_7c2_alignment_test` | 165K | 2026-05-21 | 1 py + 5 pyc | none | `v7c.2-*` |
| `.scratch_phase_7c1` | 124K | 2026-05-15 | 3 py | 1 = `rename_cell_id` to_csv (audit) | `v7c.1-*` |
| `.scratch_chore_yaml_cohort_gap` | 121K | 2026-05-14 | 6 py + notes | 1 = `audit_gap` to_csv (audit) | yaml-cohort-gap (merged) |
| `.scratch_phase_7e1` | 32K | 2026-05-26 | 3 py | none | 7e.1 (merged) |
| `.scratch_chore_audit_stale_dirs` | 8K | 2026-05-25 | 1 md | none | audit (merged) |

### PRESERVE — explicit hold (Q-lock 1)

| Dir | Size | Latest | Why preserve |
|---|---|---|---|
| `.scratch_phase_7f_scoping` | 51M | 2026-05-30 | Jaw v3.4 cleanup **provenance**: 149 PNG overlay renders + 41 CSV audit_results + the `audit_jaw_cleanup_sim_v3*.py` ladder (v1→v3p4) — the "why these constants" evidence. **The algorithm itself is now safely committed** (`src/.../jaw_cleanup_v34.py` + `scripts/phase_7f/reemit_jaw_cleaned_traces.py` + test, on origin/main via PR #165, merged 2026-06-02), so this is no longer last-copy — but the audit ladder + renders are the only record of the rejected alternatives. **Q-lock 1.** |

### ACTIVE — do **not** delete (Phase 9.1 in flight)

| Dir | Size | Latest | Note |
|---|---|---|---|
| `.scratch_phase_9_1` | 32M | 2026-05-27 | 108 png + 31 py + 9 svg — live Phase 9.1 figure work. May be in use by the parallel CC session. |
| `.scratch_phase_9` | 674K | 2026-05-26 | 18 py + 13 csv — Phase 9 / 9.1 supporting. |

### RECENT / BUFFER (Q-lock 3)

| Dir | Size | Latest | Note |
|---|---|---|---|
| `.scratch_chore_phase_7e_reemit` | 499K | 2026-05-26 | 15 py + 7 json + **6 cohort manifests (csv)** + 5 md. Downstream chores referenced these manifests. Buffer-period candidate, not an immediate delete. **Q-lock 3.** |

---

## B. Local branches

The repo has **~70 local branches**; this audit deeply analyzed the kickoff's
known-list + every branch with **no origin upstream** (the genuine force-delete
risk). A full prune of all 70 is **out of scope** unless Priya asks — and is
gated by the GR8 conflict (blocking flag 1) regardless.

### Local-only branches (no origin copy — the real risk set)

| Branch | Unique commits vs origin/main | On origin/main? | Classification |
|---|---|---|---|
| `experiment/alignment-regime-sweep-2026-05-archive` | 0 | **YES (tip is ancestor)** | SQUASH-MERGED-EQUIVALENT — content fully on main (tag `v7c.2-alignment-regime-archive`). Local copy safe to drop. |
| `docs/decision-26-amendment` | 0 | **YES (tip is ancestor)** | SQUASH-MERGED-EQUIVALENT — content fully on main. Local copy safe to drop. |
| `investigation/dlc-tongue-quality-severe-acute` | **3** | **NO** | ⚠️ **UNIQUE-CONTENT / LOCAL-ONLY / UNMERGED.** No PR. Commits: `ed777de` investigation Part 3a (3 candidate policies + 10-session diagnostics), `001c95c` phase-9.1 Task 1a V4 preview emit, `f24c0a7` phase-9.1 Task 0 figure-module scaffold. **Do not delete** — enumerate which of these landed elsewhere (phase/9.1-figures likely re-did the scaffold) before any prune. Priya decision. |

### Known-list branches (origin-tracked — content safe on origin regardless)

| Branch | PR | State | Classification |
|---|---|---|---|
| `chore/dlc-pooled-phenotype-unification` | #160 | **MERGED** | SQUASH-MERGED-EQUIVALENT |
| `chore/dlc-session-and-trial-filtering` | #158 | **MERGED** | SQUASH-MERGED-EQUIVALENT |
| `chore/dlc-session-trial-sensitivity-probe` | #157 | **MERGED** | SQUASH-MERGED-EQUIVALENT |
| `docs/phase-8a.10-kickoff-amend-verdict` | #111 | **MERGED** | SQUASH-MERGED-EQUIVALENT |
| `feat/phase-6-8a-first-emit-runner` | #63 | **MERGED** | SQUASH-MERGED-EQUIVALENT |
| `chore/v7-spatial-impact-audit` | #147 | **OPEN** | ⚠️ ACTIVE — open PR. **Do not prune.** (Kickoff "UNKNOWN" → resolved: in review.) |
| `docs/cowork-state-phase-7e-cascade-close` | #146 | **OPEN** | ⚠️ ACTIVE — open PR. **Do not prune.** (Kickoff "likely obsolete" → wrong.) |
| `phase/9.1-figures` | — (no PR) | 10 unique commits, pushed to origin | UNIQUE-CONTENT, **Phase 9.1 ACTIVE** — do not prune. |

**KEEP (per kickoff):** `docs/readme-pipeline-walkthrough` — current checked-out
branch in the main tree; has uncommitted cowork doc edits
(`docs/COWORK_SESSION_STATE.md` + 2 new kickoff docs) belonging to the parallel
CC session. Now 1 behind origin/main (PR #168 merged after it).

**Prune-eligible-after-approval (squash-merged-equivalent, GR8-gated):**
the 5 merged known-list branches + the 2 fully-merged local-only branches
(`experiment/alignment-regime-sweep-2026-05-archive`, `docs/decision-26-amendment`).
All require explicit per-branch `-D` approval (blocking flag 1). Origin copies are
left intact regardless.

---

## C. Producer-script migration candidates

Of all `to_parquet`/`savez` hits in delete-candidate dirs, only **two** touch
canonical pipeline data; the rest write audit reports (`to_csv`/`json.dump`) and
need no promotion (they delete with their dir).

| Producer | Writes | In-repo equivalent? | Recommendation |
|---|---|---|---|
| `.scratch_7a3/tongue_cell36.py`, `tongue_cell39.py` | `np.savez_compressed` → `<mouse>_tongue_kinematics/.../velocity_metrics/` | ⚠️ **No literal `velocity_metrics` writer found in `src/` or `scripts/`.** These are legacy notebook port-source cells; Phase 7a.3 ported tongue kinematics to `tongue_pertrial.py`/`features.py`, almost certainly restructuring `velocity_metrics`. | **Verify gate:** confirm the velocity-metrics output is covered by the ported tongue per-trial module before deleting `.scratch_7a3`. If genuinely dropped, decide promote vs. intentional-removal. Do not silently delete. |
| `.scratch_phase_7e/gen_v7_canonical_fixtures.py` | generates v7 canonical test fixtures | ⚠️ Fixtures dir exists (`tests/fixtures/v7_canonical/`, README committed) but **no committed generator**. | **Promote candidate:** if the fixtures are regenerable artifacts, `git add` the generator to `scripts/phase_7e/`. If they're static committed inputs, document that the generator is intentionally one-shot. Lost-producer risk if deleted as-is. |

`.scratch_phase_7f_scoping`'s 14 jaw-sim "producers" need **no** migration — the
canonical v3.4 algorithm is already committed in-repo (PR #165). The dir is held
for provenance (section A / Q-lock 1), not for the producer.

---

## D. Memory consolidation candidate (Cowork-side — surface only)

- `project_secondary_spout_no_dlc.md` is flagged "DELETE in next consolidation."
  It is **not in this repo** (no repo `memory/` dir; not in the CC memory tree
  either). This is a **Cowork memory-tree** action for Priya — **out of scope for
  this repo PR**, surfaced here per the kickoff.
- Also surfaced: the missing
  `feedback_enumerate_branch_unique_files_before_force_delete` memory
  (blocking flag 2) — write or fix the reference.

---

## Q-locks to resolve before Stage 1

1. **`.scratch_phase_7f_scoping` (51M) disposition** — preserve-all-to-share +
   delete / preserve only the sim ladder + renders + audit_results / keep
   indefinitely? (Algorithm is safely in `src/` now; this is purely about the
   provenance evidence.)
2. **Squash-merged-equivalent local branches** — prune local copies (requires you
   to authorize / run each `git branch -D`, per GR8) or leave as historical local
   reference? Origin is untouched either way.
3. **`.scratch_chore_phase_7e_reemit` (499K, cohort manifests)** — delete now or
   hold one more buffer pass?
4. **Stage 2 (`docs/prompts/` archive sweep)** — in or out of scope for this PR?

## Recommended Stage-1 default (pending your answers)

- **Delete** the 18 CLOSED-PHASE-SAFE dirs (**2.3 GB**) — each `rm -rf` surfaced
  individually for per-invocation GR7 approval; **no pre-wipe / no force-re-emit**.
- **Resolve the 2 producer verify-gates (C)** before deleting `.scratch_7a3` and
  `.scratch_phase_7e` — promote `gen_v7_canonical_fixtures.py` if regenerable.
- **Hold** `.scratch_phase_7f_scoping` (Q1), `.scratch_phase_9*` (active), and
  `.scratch_chore_phase_7e_reemit` (Q3).
- **Branches:** take **no** `-D` action pending Q-lock 2 + explicit per-branch
  approval; never touch `investigation/dlc-tongue-quality-severe-acute` or the two
  open-PR branches.
</content>
</invoke>
