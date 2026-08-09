from datetime import date
from decimal import Decimal

import pytest

from app.services.pricing import compute_montant_total, compute_nombre_jours


def test_compute_nombre_jours_basic():
    assert compute_nombre_jours(date(2026, 8, 10), date(2026, 8, 15)) == 5


def test_compute_nombre_jours_same_day_invalid():
    with pytest.raises(ValueError):
        compute_nombre_jours(date(2026, 8, 10), date(2026, 8, 10))


def test_compute_nombre_jours_end_before_start_invalid():
    with pytest.raises(ValueError):
        compute_nombre_jours(date(2026, 8, 15), date(2026, 8, 10))


def test_compute_montant_total():
    total = compute_montant_total(Decimal("350.00"), date(2026, 8, 10), date(2026, 8, 15))
    assert total == Decimal("1750.00")
