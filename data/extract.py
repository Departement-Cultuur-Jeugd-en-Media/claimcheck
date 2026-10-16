# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""Write the four parquet files of the dataset from the proef-data warehouse.

Reads the marts of a built `warehouse.duckdb` and writes `ledenaantallen`, `bevolking`,
`gemeenten` and `groepen` next to this script, each sorted on its key so a re-run yields the
same file. Local groups only: the warehouse holds no Leden/Leiding split for the supra-local
level. Gemeenten without a name in the warehouse are left out; a group seated there keeps
its nis_code and reads as a group without gemeente.
"""

import argparse
from pathlib import Path

import duckdb

HERE = Path(__file__).parent

SELECTS = {
    "ledenaantallen": """
        select organisatie_sk as groep_id, nis_code, werkjaar, period_year as jaar,
               type_deelnemer, aantal
        from marts.fct_ledenaantallen
        order by werkjaar, groep_id, type_deelnemer""",
    "bevolking": """
        select nis_code, kalenderjaar as jaar, inwoners_7_18, inwoners_totaal
        from marts.fct_bevolking
        order by jaar, nis_code""",
    "gemeenten": """
        select nis_code, gemeente_name as gemeente, province as provincie, region as gewest
        from marts.dim_gemeente
        where gemeente_name is not null
        order by nis_code""",
    "groepen": """
        select organisatie_sk as groep_id, koepel_slug as koepel, koepel_label,
               organisatie_naam as naam, nis_code
        from marts.dim_jeugdbeweging
        where niveau = 'lokaal'
        order by groep_id""",
}


def extract(warehouse: Path) -> None:
    """Write the four files; prints one line per file with its row count."""
    con = duckdb.connect(str(warehouse), read_only=True)
    for name, select in SELECTS.items():
        target = HERE / f"{name}.parquet"
        con.execute(f"copy ({select}) to '{target}' (format parquet)")
        rows = con.execute(f"select count(*) from '{target}'").fetchone()[0]
        print(f"{target.name}: {rows} rows")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--warehouse", type=Path, required=True, help="path to warehouse.duckdb")
    extract(parser.parse_args().warehouse)
