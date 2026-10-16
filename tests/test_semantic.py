# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The semantic model loads as spec section 3 says, and hand-broken copies are rejected."""

from pathlib import Path

import pytest
import yaml

from claimcheck import semantic

ROOT = Path(__file__).parent.parent
MODEL = ROOT / "model" / "semantic.yaml"


def broken(tmp_path, mutate):
    """Write a copy of the real model with one change and return its path, next to the data."""
    doc = yaml.safe_load(MODEL.read_text())
    mutate(doc)
    (tmp_path / "data").symlink_to(ROOT / "data")
    (tmp_path / "model").mkdir()
    path = tmp_path / "model" / "semantic.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


def test_the_real_model_loads():
    dataset = semantic.load(MODEL)
    assert dataset.name == "jeugdbewegingen"
    assert dataset.covers.startswith("Leden en leiding")
    assert set(dataset.tables) == {"ledenaantallen", "bevolking", "gemeenten", "groepen"}
    assert dataset.measures["leden"].kind == "stock"
    assert dataset.measures["leden"].per == "leden_per_100_jongeren"
    assert dataset.measures["leden_per_100_jongeren"].numerator == "leden"
    assert dataset.period.name == "werkjaar"
    assert dataset.dimensions["gemeente"].role == "place"
    assert dataset.dimensions["type_deelnemer"].values == ("Leden", "Leiding")
    assert len(dataset.joins) == 3


def test_values_of_a_dimension_come_from_the_data():
    dataset = semantic.load(MODEL)
    assert semantic.values_of(dataset, "werkjaar")[:2] == ("2017-2018", "2018-2019")
    assert "Leuven" in semantic.values_of(dataset, "gemeente")


@pytest.mark.parametrize(
    ("mutate", "key"),
    [
        (lambda d: d["measures"]["leden"].update(table="ledental"), "measures.leden.table"),
        (lambda d: d["measures"]["leden"].update(kind="count"), "measures.leden.kind"),
        (lambda d: d["measures"]["leden"].update(per="inwoners"), "measures.leden.per"),
        (
            lambda d: d["measures"]["leden_per_100_jongeren"].update(denominator="jongeren"),
            "measures.leden_per_100_jongeren.denominator",
        ),
        (lambda d: d["dimensions"]["koepel"].update(table="koepels"), "dimensions.koepel.table"),
        (lambda d: d["dimensions"]["koepel"].update(column="label"), "dimensions.koepel.column"),
        (lambda d: d["dimensions"]["gemeente"].update(role="period"), "dimensions.role"),
    ],
)
def test_a_broken_model_is_rejected_by_key(tmp_path, mutate, key):
    with pytest.raises(ValueError, match=key):
        semantic.load(broken(tmp_path, mutate))
