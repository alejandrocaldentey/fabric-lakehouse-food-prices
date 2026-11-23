"""Check a table against its data contract (quality/contracts/*.yaml).

Checks: required columns not null, allowed values, numeric ranges, primary-key uniqueness.
Raises ContractViolation listing every failed rule, so a run stops before gold is touched.
"""

from __future__ import annotations

from pathlib import Path

import yaml


class ContractViolation(RuntimeError):
    pass


def _count(con, sql: str) -> int:
    return con.execute(sql).fetchone()[0]


def check_contract(con, contract_path: Path) -> None:
    contract = yaml.safe_load(Path(contract_path).read_text())
    table = contract["table"]
    failures: list[str] = []

    for col, rules in contract["columns"].items():
        if rules.get("required"):
            n = _count(con, f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL")
            if n:
                failures.append(f"{col}: {n} null values")
        if "allowed" in rules:
            allowed = ", ".join(f"'{v}'" for v in rules["allowed"])
            n = _count(con, f"SELECT COUNT(*) FROM {table} WHERE {col} NOT IN ({allowed})")
            if n:
                failures.append(f"{col}: {n} values outside {rules['allowed']}")
        if "min" in rules or "max" in rules:
            lo, hi = rules.get("min"), rules.get("max")
            cond = " OR ".join(
                c
                for c in (
                    f"{col} < {lo}" if lo is not None else "",
                    f"{col} > {hi}" if hi is not None else "",
                )
                if c
            )
            n = _count(con, f"SELECT COUNT(*) FROM {table} WHERE {cond}")
            if n:
                failures.append(f"{col}: {n} values outside [{lo}, {hi}]")

    key = ", ".join(contract["primary_key"])
    dupes = _count(
        con,
        f"SELECT COUNT(*) FROM (SELECT {key} FROM {table} GROUP BY {key} HAVING COUNT(*) > 1) d",
    )
    if dupes:
        failures.append(f"primary key ({key}): {dupes} duplicated keys")

    if failures:
        raise ContractViolation(f"{table} breaks its contract: " + "; ".join(failures))
