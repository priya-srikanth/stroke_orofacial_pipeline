"""Batch DLC video analysis on O2.

This module is superseded by the split into ``runner.py``, ``batch.py``,
and ``o2_job.py``. Kept as a re-export for backward compatibility with
the Phase 0 skeleton.

See ``runner.py`` for the core inference script generator.
"""

from stroke_orofacial.dlc_inference_o2.runner import generate_inference_script

__all__ = ["generate_inference_script"]
