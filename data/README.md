# The dataset

Four parquet files, extracted from the marts of the `proef-data` pipeline (the CJAM pack of
Departement Cultuur, Jeugd en Media) on 2026-10-16 with `extract.py`. The pipeline reads the
yearly membership workbooks of the recognised youth-movement koepels (*Jeugdbewegingen in
cijfers*) and the population figures per gemeente. Public data of the Vlaamse overheid; the
licence of the source files is not recorded in the pipeline and is to be confirmed by the owner.

```bash
uv run python data/extract.py --warehouse <path to proef-data/pack/warehouse.duckdb>
```

Rows are sorted, so a re-run on the same warehouse writes identical files.

| File | Grain | Rows |
|---|---|---|
| `ledenaantallen.parquet` | one row per groep, werkjaar and type_deelnemer (Leden, Leiding) | 36,072 |
| `bevolking.parquet` | one row per gemeente and kalenderjaar, 2014 to 2025 | 3,564 |
| `gemeenten.parquet` | one row per gemeente with a name: 327 Flemish, 19 Brussels, 54 Walloon | 400 |
| `groepen.parquet` | one row per local groep, with its koepel and the gemeente of its seat | 2,471 |

`jaar` on `ledenaantallen` is the calendar year the werkjaar starts in; it is what joins a
werkjaar to its population denominator (2024-2025 to 2024).

## Known gaps

Facts about the data, not conditions, until a failure makes them one.

- The series starts at werkjaar 2017-2018 and runs to 2025-2026: nine werkjaren.
- Up to 2023-2024 five koepels report, from 2024-2025 nine.
- In werkjaar 2024-2025, 33 gemeenten carry leden but no population denominator: 24 Flemish
  (gemeenten of the 2025 fusions: the groups still carry the old nis-code, the population
  table only the new one), 4 Walloon, and 5 nis-codes the warehouse has no name for. Their
  16,776 leden fall out of every ratio.
- 12 groups active in 2024-2025 (28 over all werkjaren) sit in one of those 5 unnamed
  nis-codes and so have no gemeente, provincie or gewest.
- No age for leden or leiding; the workbooks since 2024-2025 carry birth years, the marts do not.

The anchor: Leuven 3,506 and Gent 8,566 leden in 2024-2025, 29.4 and 25.3 per 100 jongeren of
7 to 18. `tests/test_data.py` holds it.
