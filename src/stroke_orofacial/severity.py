"""Behavioral stroke-severity scoring from spout (lick) data.

FaceRhythm-independent, per-animal severity from the Phase-2 ``licks_and_rewards``
NPZs. The canonical metric is the **integrated deficit burden** — the area between
the pre-stroke baseline and the post-stroke per-trial response over days (depth ×
duration) — computed *separately* for the contralesional and ipsilesional responses,
so a lasting focal contra deficit (moderate) is distinguished from a transient dip,
and a unilateral deficit (moderate) from a bilateral one (severe).

Sides are mouse-frame (the ``licks_and_rewards`` NPZ is emitted in the mouse frame)
and mapped to ipsi/contra per animal via
:meth:`stroke_orofacial.animals.AnimalInfo.mouse_side_to_ipsi_contra`, so the code
is correct for either lesion laterality (all current cohort animals are left-VLS).

No absolute paths or hardcoded animal metadata — locations come from
:class:`stroke_orofacial.paths.PathResolver`, stroke dates / laterality from
``configs/animals.yaml`` via :func:`stroke_orofacial.animals.get_animal`.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

import numpy as np

from stroke_orofacial.animals import AnimalInfo, get_animal
from stroke_orofacial.paths import PathResolver

# np.trapz was renamed np.trapezoid in NumPy 2.0; support both.
_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))

#: Response window after a tone (wavesurfer samples @ 1 kHz) in which licks are
#: counted toward that trial. Trials are ~tens of seconds apart, so 3 s never
#: bleeds into the next trial.
RESPONSE_WINDOW_SAMPLES = 3000


def _sides(info: AnimalInfo) -> tuple[str, str]:
    """Return ``(ipsi_side, contra_side)`` as mouse-frame "L"/"R" labels."""
    ipsi = info.stroke_laterality
    contra = "R" if ipsi == "L" else "L"
    return ipsi, contra


def session_responses(npz: dict, info: AnimalInfo) -> tuple[float, float]:
    """Per-trial correct-response lick counts for one session.

    Returns ``(contra_response, ipsi_response)`` = mean licks within
    ``RESPONSE_WINDOW_SAMPLES`` after the same-side tone, for the contralesional
    and ipsilesional sides respectively. NaN if that trial type is absent.
    """
    ipsi, contra = _sides(info)
    out = []
    for side in (contra, ipsi):
        tones = np.asarray(npz[f"Tone_{side}"])
        licks = np.asarray(npz[f"Lick_{side}"])
        if tones.size == 0:
            out.append(np.nan)
            continue
        per_trial = [
            int(np.sum((licks >= t) & (licks < t + RESPONSE_WINDOW_SAMPLES)))
            for t in tones
        ]
        out.append(float(np.mean(per_trial)))
    return out[0], out[1]


@dataclass
class SeverityResult:
    """Per-animal severity summary.

    ``*_burden`` are **null-floor-corrected** integrated deficits (the animal's
    pre-stroke rectified-deficit rate is subtracted before integrating, so
    pre-existing licking noise / session drift does not inflate the score).
    ``*_burden_raw`` are the uncorrected integrals (kept for transparency).
    """

    animal: str
    stroke_laser_power_mW: float | None
    contra_burden: float       # corrected contralesional deficit (deficit-days)
    ipsi_burden: float         # corrected ipsilesional deficit (deficit-days)
    contra_burden_raw: float
    ipsi_burden_raw: float
    contra_baseline: float
    ipsi_baseline: float
    n_pre: int
    n_post: int

    @property
    def focal_deficit(self) -> float:
        """Contralesional-*specific* deficit = max(0, contra − ipsi) burden.

        The stroke-specific (lateralized) severity. A general bilateral
        reduction in licking/engagement cancels out; only a contra≫ipsi deficit
        (a focal lesion signature) scores > 0. E.g. PS49's small non-specific
        ipsi dip → focal_deficit ≈ 0.
        """
        return max(0.0, self.contra_burden - self.ipsi_burden)

    @property
    def lateralization(self) -> float:
        """contra:ipsi burden ratio (high = focal/unilateral; ~1 = bilateral)."""
        return self.contra_burden / (self.ipsi_burden + 1e-6)


def _response_trajectory(
    animal: str, resolver: PathResolver, min_trials: int = 10
) -> tuple[AnimalInfo, np.ndarray, np.ndarray, np.ndarray]:
    """Per-session (days_from_stroke, contra response, ipsi response) arrays."""
    info = get_animal(animal)
    root = resolver.pipeline_outputs(subdir="spout_behavior") / "licks_and_rewards" / animal
    days, contra, ipsi = [], [], []
    for path in sorted(root.glob("*.npz")):
        if not path.stem.isdigit():
            continue  # skip merged/multi-half names like 20250314a
        date = datetime.datetime.strptime(path.stem, "%Y%m%d").date()
        npz = np.load(path, allow_pickle=True)
        if "Lick_L" not in npz or (len(npz["Lick_L"]) + len(npz["Lick_R"])) < min_trials:
            continue
        c, i = session_responses(npz, info)
        days.append(info.day_relative_to_stroke(date))
        contra.append(c)
        ipsi.append(i)
    return (info, np.asarray(days, float),
            np.asarray(contra, float), np.asarray(ipsi, float))


def deficit_burden(
    animal: str,
    resolver: PathResolver | None = None,
    *,
    baseline_n: int = 5,
    min_trials: int = 10,
) -> SeverityResult:
    """Compute the integrated contra/ipsi deficit burden for one animal.

    Enumerates the animal's ``licks_and_rewards`` NPZs, builds the per-session
    contralesional and ipsilesional correct-response time series, and integrates
    the fractional deficit ``max(0, 1 - response/baseline)`` over post-stroke days
    (trapezoid in day units → "deficit-days"). Baseline = mean of the last
    ``baseline_n`` pre-stroke sessions.
    """
    resolver = resolver or PathResolver()
    info, days, contra, ipsi = _response_trajectory(animal, resolver, min_trials)
    pre = days <= 0
    post = days > 0
    bc = float(np.nanmean(contra[pre][-baseline_n:]))
    bi = float(np.nanmean(ipsi[pre][-baseline_n:]))

    def _burden(resp: np.ndarray, base: float) -> tuple[float, float]:
        """Return (raw, null-floor-corrected) integrated deficit (deficit-days)."""
        pre_rate = float(np.nanmean(np.nan_to_num(np.clip(1 - resp[pre] / base, 0, 1)))) if pre.any() else 0.0
        post_def = np.nan_to_num(np.clip(1 - resp[post] / base, 0, 1))
        raw = float(_trapz(post_def, days[post]))
        corr = float(_trapz(np.clip(post_def - pre_rate, 0, 1), days[post]))
        return raw, corr

    c_raw, c_corr = _burden(contra, bc)
    i_raw, i_corr = _burden(ipsi, bi)
    return SeverityResult(
        animal=animal,
        stroke_laser_power_mW=info.stroke_laser_power_mW,
        contra_burden=c_corr,
        ipsi_burden=i_corr,
        contra_burden_raw=c_raw,
        ipsi_burden_raw=i_raw,
        contra_baseline=bc,
        ipsi_baseline=bi,
        n_pre=int(pre.sum()),
        n_post=int(post.sum()),
    )


def cohort_burden(
    animals: list[str], resolver: PathResolver | None = None
) -> list[SeverityResult]:
    """Deficit burden for several animals (skips those with no usable data)."""
    resolver = resolver or PathResolver()
    out = []
    for a in animals:
        try:
            out.append(deficit_burden(a, resolver))
        except (KeyError, FileNotFoundError):
            continue
    return out


@dataclass
class SeverityGrade:
    """Composite behavioral severity from three interpretable spout axes.

    Reproduces the clinical grading from per-session lick observations:
      - ``bilateral_cessation_days`` (A): post days with BOTH the contra and ipsi
        correct responses < 25% of baseline (acute total absence of licking).
      - ``contra_absent_days`` (B): post days with the contralesional response
        < 25% of baseline (duration of absent contra licking).
      - ``contra_persistence`` (C): residual contra deficit over the last sessions
        (1 − mean contra response / baseline) — does the contra deficit persist to
        the end (severe) or recover (moderate)?

    The two suppression thresholds were originally 20 % (cessation) and 30 %
    (absence); they are unified to 25 % here. The four-way grouping is invariant
    to this choice (verified at 20 / 25 / 30 % — the A/B counts shift slightly
    but never cross a grade boundary), so a single threshold is used for
    simplicity.
    """

    animal: str
    bilateral_cessation_days: int
    contra_absent_days: int
    contra_persistence: float
    grade: str  # 3-tier: mild|moderate|severe; 4-tier adds mod-severe


#: Grading schemes. The 3-tier scheme collapses the 4-tier "mod-severe" tier
#: (acute bilateral cessation that recovers) into "moderate", so a focal
#: contra-only deficit (PS46) and a recovering bilateral cessation (PS51) share
#: one "moderate" grade. Both schemes share the severe / mild cutoffs.
GRADING_SCHEMES = ("3tier", "4tier")


def _grade(A: int, B: int, C: float, scheme: str = "3tier") -> str:
    """Composite severity grade from the three axes (PS46–55-tuned; N=8).

    Shared cutoffs: **severe** if the contra deficit fails to resolve by the end
    (``C > 0.6``) OR bilateral cessation is prolonged (``A >= 10`` days);
    **mild** if there is at most a brief deficit.

    The middle differs by ``scheme``:

    - ``"4tier"``: **mod-severe** if acute bilateral cessation recovers
      (``A >= 2``), else **moderate** if a sustained contra-only deficit
      (``B >= 3``). PS51 → mod-severe, PS46 → moderate.
    - ``"3tier"`` (default): a single **moderate** tier covering both routes
      (``A >= 2 or B >= 3``). PS51 and PS46 both → moderate.
    """
    if scheme not in GRADING_SCHEMES:
        raise ValueError(f"scheme must be one of {GRADING_SCHEMES}, got {scheme!r}")
    if C > 0.6 or A >= 10:        # persistent contra deficit OR prolonged cessation
        return "severe"
    if scheme == "4tier":
        if A >= 2:                # acute bilateral cessation that recovers
            return "mod-severe"
        if B >= 3:                # sustained contra-only deficit (ipsi spared)
            return "moderate"
        return "mild"
    # 3-tier: collapse mod-severe into moderate
    if A >= 2 or B >= 3:
        return "moderate"
    return "mild"


def severity_grade(
    animal: str,
    resolver: PathResolver | None = None,
    *,
    baseline_n: int = 5,
    min_trials: int = 10,
    late_window: int = 6,
    cessation_frac: float = 0.25,
    absent_frac: float = 0.25,
    scheme: str = "3tier",
) -> SeverityGrade:
    """Composite behavioral severity grade for one animal (see :class:`SeverityGrade`).

    ``scheme`` selects the 3-tier (default) or 4-tier grading (see :func:`_grade`).
    The three axes (A/B/C) are identical across schemes; only the grade label
    differs.
    """
    resolver = resolver or PathResolver()
    info, days, contra, ipsi = _response_trajectory(animal, resolver, min_trials)
    pre = days <= 0
    post = days > 0
    cf = contra / float(np.nanmean(contra[pre][-baseline_n:]))
    inf = ipsi / float(np.nanmean(ipsi[pre][-baseline_n:]))
    A = int(np.sum(post & (cf < cessation_frac) & (inf < cessation_frac)))
    B = int(np.sum(post & (cf < absent_frac)))
    late = post & (days >= days[post].max() - late_window)
    C = float(max(0.0, 1 - np.nanmean(cf[late])))
    return SeverityGrade(animal, A, B, C, _grade(A, B, C, scheme))


def cohort_grade(
    animals: list[str], resolver: PathResolver | None = None, *, scheme: str = "3tier"
) -> list[SeverityGrade]:
    """Composite severity grade for several animals (``scheme`` = ``"3tier"``/``"4tier"``)."""
    resolver = resolver or PathResolver()
    out = []
    for a in animals:
        try:
            out.append(severity_grade(a, resolver, scheme=scheme))
        except (KeyError, FileNotFoundError):
            continue
    return out
