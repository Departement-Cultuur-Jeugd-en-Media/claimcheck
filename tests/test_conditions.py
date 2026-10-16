# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The conditions document loads as spec section 4 says, and hand-broken copies are rejected."""

from pathlib import Path

import pytest
import yaml

from claimcheck import conditions, semantic

MODEL = Path(__file__).parent.parent / "model"


@pytest.fixture(scope="module")
def dataset():
    return semantic.load(MODEL / "semantic.yaml")


def test_the_real_conditions_load(dataset):
    doc = conditions.load(MODEL / "conditions.yaml", dataset)
    assert doc.version == 1 and doc.dataset == "jeugdbewegingen"
    assert len(doc.items) == 10
    wallonie = doc.by_id["wallonie-zit-er-niet-in"]
    assert wallonie.kind == "named_exclusion"
    assert wallonie.dimensions == ("gewest",)
    assert wallonie.values == ("Waals Gewest",)
    assert wallonie.authority == "blocks"
    assert wallonie.alternative.startswith("Vraag naar")
    assert doc.by_id["gemeente-is-de-gemeente-van-de-groep"].dimensions == (
        "gemeente",
        "provincie",
        "gewest",
    )
    assert doc.by_id["ratio-zonder-noemer"].measure == "leden_per_100_jongeren"


def test_conditions_are_indexed_by_the_operation_they_fire_on(dataset):
    doc = conditions.load(MODEL / "conditions.yaml", dataset)
    assert [c.id for c in doc.bound_to("over_time")] == [
        "leden-is-een-standcijfer",
        "bevolking-is-een-standcijfer",
        "reeks-begint-in-2017-2018",
        "koepels-scharnierjaar-2024-2025",
    ]
    assert [c.id for c in doc.bound_to("default")] == [
        "zonder-periode-het-laatste-werkjaar",
        "leden-zonder-leiding",
    ]
    assert doc.bound_to("join") == ()


def item(doc, id):
    return next(c for c in doc["conditions"] if c["id"] == id)


@pytest.mark.parametrize(
    ("mutate", "key"),
    [
        (lambda d: item(d, "leden-is-een-standcijfer").update(id="wallonie-zit-er-niet-in"), "id"),
        (lambda d: item(d, "leden-is-een-standcijfer").pop("alternative"), "alternative"),
        (lambda d: item(d, "leden-is-een-standcijfer").update(fires_on=["filter"]), "fires_on"),
        (lambda d: item(d, "leden-is-een-standcijfer").update(kind="stock"), "kind"),
        (
            lambda d: item(d, "ratio-zonder-noemer").update(applies_to={"measure": "x"}),
            "applies_to",
        ),
        (
            lambda d: item(d, "koepels-scharnierjaar-2024-2025").update(reliable_from="2017-2018"),
            "breaks_at",
        ),
        (
            lambda d: item(d, "koepels-scharnierjaar-2024-2025").update(breaks_at="2024"),
            "breaks_at",
        ),
        (lambda d: item(d, "leden-zonder-leiding").pop("default"), "default"),
    ],
)
def test_a_broken_document_is_rejected_by_key(tmp_path, dataset, mutate, key):
    doc = yaml.safe_load((MODEL / "conditions.yaml").read_text())
    mutate(doc)
    path = tmp_path / "conditions.yaml"
    path.write_text(yaml.safe_dump(doc, allow_unicode=True))
    with pytest.raises(ValueError, match=key):
        conditions.load(path, dataset)
