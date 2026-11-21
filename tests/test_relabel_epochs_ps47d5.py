"""PS47 chronic onset day 5 (2026-11-19): configs/animals.yaml boundaries and the opt-in
build_pooled_phenotype_stats --relabel-epochs path."""
import datetime

import pandas as pd
from scripts.phase_9_stats.build_pooled_phenotype_stats import relabel_epochs

from stroke_orofacial.animals import load_animals
from stroke_orofacial.stats.recovery_epochs import assign_epoch_label


def _d(rel):
    return load_animals()["PS47"].stroke_date + datetime.timedelta(days=rel)


def test_ps47_boundaries_day5():
    info = load_animals()["PS47"]
    labels = {rel: assign_epoch_label(rel, info) for rel in (-1, 1, 2, 3, 4, 5, 9)}
    assert labels == {-1: "pre", 1: "acute", 2: "sub_acute", 3: "sub_acute",
                      4: "sub_acute", 5: "chronic", 9: "chronic"}


def test_relabel_epochs_only_moves_stale_rows():
    # rows as a run with the OLD PS47 boundaries (chronic from day 3) would have written them
    df = pd.DataFrame({
        "animal": ["PS47"] * 5 + ["PS48", "PSXX"],
        "date": [_d(r) for r in (2, 3, 4, 5, -1)] + [_d(3), _d(3)],
        "epoch_label": ["sub_acute", "chronic", "chronic", "chronic", "pre", "OLD", "keep"],
        "family": "scalar", "value": range(7),
    })
    out = relabel_epochs(df)
    assert out["epoch_label"].tolist()[:5] == ["sub_acute", "sub_acute", "sub_acute", "chronic", "pre"]
    ps48 = assign_epoch_label(int(load_animals()["PS48"].day_relative_to_stroke(_d(3))), load_animals()["PS48"])
    assert out["epoch_label"].iloc[5] == ps48          # every row is re-derived from the config
    assert out["epoch_label"].iloc[6] == "keep"        # animals not in animals.yaml keep their label
    assert out.drop(columns="epoch_label").equals(df.drop(columns="epoch_label"))
