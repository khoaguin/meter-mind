"""Seed boundary — seed.yaml validates into SeedData, derived values stay derived.

Guards the Phase-0 boundary the DB loader reuses: a malformed file must fail at
the boundary, and money amounts must be computed, never stored literals that can
silently desync when a tariff changes.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from hub.core.service import load_seed_data


def test_seed_yaml_validates() -> None:
    # WHY: the frozen seed.yaml must load into SeedData or every downstream reader breaks.
    seed = load_seed_data()
    assert seed.period == "2026-07"
    assert {a.tenant_id for a in seed.accounts} == {"room1", "room2", "room3"}
    assert seed.tariffs == {"water": 15000, "elec": 3000}


def test_amount_is_derived_not_stored() -> None:
    # WHY: editing usage in YAML must move the invoice amount — no stale literal.
    from hub.core import service

    invoice = service.compute_invoice("room3")
    assert invoice.amount == invoice.usage * invoice.tariff_rate
    assert invoice.amount == 620 * 3000


def test_malformed_seed_fails_loud(tmp_path: Path) -> None:
    # WHY: fail-fast at the boundary — a bad file errors, never loads half a model.
    bad = tmp_path / "bad.yaml"
    bad.write_text("period: 2026-07\naccounts: not-a-list\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_seed_data(bad)
