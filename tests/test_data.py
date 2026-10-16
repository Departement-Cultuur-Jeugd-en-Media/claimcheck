# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""The four parquet files hold what docs/003 phase 0 says, and the anchor numbers hold."""

from pathlib import Path

import duckdb
import pytest

DATA = Path(__file__).parent.parent / "data"

FILES = {
    "ledenaantallen": (
        ["groep_id", "nis_code", "werkjaar", "jaar", "type_deelnemer", "aantal"],
        36072,
    ),
    "bevolking": (["nis_code", "jaar", "inwoners_7_18", "inwoners_totaal"], 3564),
    "gemeenten": (["nis_code", "gemeente", "provincie", "gewest"], 400),
    "groepen": (["groep_id", "koepel", "koepel_label", "naam", "nis_code"], 2471),
}


@pytest.fixture(scope="module")
def db():
    con = duckdb.connect()
    for name in FILES:
        con.execute(f"create view {name} as select * from '{DATA / name}.parquet'")
    return con


@pytest.mark.parametrize("name", FILES)
def test_file_has_the_columns_and_rows_of_the_plan(db, name):
    columns, rows = FILES[name]
    assert [c[0] for c in db.execute(f"describe {name}").fetchall()] == columns
    assert db.execute(f"select count(*) from {name}").fetchone()[0] == rows


def test_leuven_and_gent_in_2024_2025_are_the_anchor(db):
    rows = db.execute(
        """
        select g.gemeente, sum(l.aantal), round(100.0 * sum(l.aantal) / max(b.inwoners_7_18), 1)
        from ledenaantallen l
        join gemeenten g using (nis_code)
        join bevolking b on b.nis_code = l.nis_code and b.jaar = l.jaar
        where l.werkjaar = '2024-2025' and l.type_deelnemer = 'Leden'
          and g.gemeente in ('Leuven', 'Gent')
        group by 1 order by 1
        """
    ).fetchall()
    assert rows == [("Gent", 8566, 25.3), ("Leuven", 3506, 29.4)]
