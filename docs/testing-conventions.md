# Testing conventions

Conventions for writing tests in this repo. Additive to pytest defaults —
only items that aren't covered by standard pytest / ruff behavior are
documented here.

---

## Output path convention for tests

**Rule.** Tests MUST NOT write under the real
`stroke_orofacial_pipeline_outputs/` tree. The production output tree is
the canonical artifact store for the pipeline; test runs touching it
silently stamp production artifacts with pytest-era timestamps, poison
the Phase 2/5/6 re-emit provenance trail, and create a parity-drift risk
between re-emit cycles.

**How to comply.** Any test that invokes a pipeline function which
writes output (currently: `process_session`, `process_session_by_animal_date`,
`build_centered_parquet`, and any future orchestrator that passes
`overwrite="force"` or otherwise emits under `pipeline_outputs()`) must
construct its `PathResolver` with the `output_root` kwarg pointing at a
pytest `tmp_path`:

```python
def test_my_orchestrator(self, monkeypatch, tmp_path):
    monkeypatch.setenv("STROKE_PIPELINE_MACHINE", "mac")
    from stroke_orofacial.paths import PathResolver

    resolver = PathResolver(output_root=tmp_path)  # <- the fix
    # ... call the orchestrator as usual
```

The override is surgically scoped: `PathResolver(output_root=tmp_path)`
only redirects `pipeline_outputs()` results; all other logical roots
(wavesurfer_raw, camera_raw, microscope_server, etc.) continue to resolve
from the real config. Integration tests that need to read real
MICROSCOPE data alongside writing to `tmp_path` are fully supported.

**What this rule does NOT cover.**

Reading from the real tree for parity checks is fine and normal.
`tests/test_dlc_parquet.py::TestIntegrationParity` and
`tests/test_reward_aligned.py` both open the real `_V2` path to compare
against legacy baselines — that is how parity tests work and is not a
hygiene concern.

The rule targets WRITE-TO-REAL-PATH, not READ-FROM-REAL-PATH.

**If you're not sure which your test does**, check whether it passes
`overwrite="force"` (or `overwrite="prompt"` — also a writer path) to
any orchestrator. If yes → apply the rule. If no → you're reading, and
no action needed.

**How this rule is enforced.**

No static linter — convention only. The mtime-diff verification baked
into task #20 (`scratch/mtime_diff_task20.py`) is the dynamic check: a
SHA-256 of every mtime under the production spout_behavior/ tree, run
before and after a pytest invocation, should be identical. If a future
PR drifts from this convention the digest will change and the drift is
easy to locate.

---

## Context

This convention was codified in task #20 (`fix/test-hygiene-task-20`)
after the task #17 Phase 2 re-emit surfaced a production artifact that
had been silently re-emitted by a Mac-side `pytest` run between re-emit
cycles. See:

- [docs/MIGRATION_LOG.md](MIGRATION_LOG.md) — "Task #17 follow-up —
  Phase 2 re-emit across PS46–PS55" entry, "Hygiene finding" section
  for the original observation.
- Task #20 PR: adds the `PathResolver(output_root=...)` kwarg, retrofits
  the four known offenders in `tests/test_session_processing.py`, and
  documents this convention.
