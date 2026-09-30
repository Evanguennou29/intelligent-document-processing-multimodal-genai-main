"""Quota store: per-user and monthly limits, with month rollover."""

from __future__ import annotations

import json
from pathlib import Path

from idp.config import Settings
from idp.quota import QuotaStore


def make_store(tmp_path: Path, per_user: int = 3, monthly: int = 50) -> QuotaStore:
    settings = Settings(
        provider="ollama",
        demo_quota_enabled=True,
        demo_per_user_limit=per_user,
        demo_monthly_limit=monthly,
        demo_quota_path=tmp_path / "quota.json",
        cache_dir=tmp_path,
    )
    return QuotaStore(settings)


def test_allows_up_to_user_limit(tmp_path: Path) -> None:
    store = make_store(tmp_path, per_user=3)
    for _ in range(3):
        allowed, _ = store.try_consume("user-a", 1)
        assert allowed is True
    allowed, message = store.try_consume("user-a", 1)
    assert allowed is False
    assert "visiteur" in message


def test_monthly_limit_is_global(tmp_path: Path) -> None:
    store = make_store(tmp_path, per_user=10, monthly=5)
    for index in range(5):
        allowed, _ = store.try_consume(f"user-{index}", 1)
        assert allowed is True
    allowed, message = store.try_consume("user-6", 1)
    assert allowed is False
    assert "mensuel" in message


def test_status_reports_remaining(tmp_path: Path) -> None:
    store = make_store(tmp_path, per_user=3, monthly=50)
    store.try_consume("user-a", 2)
    status = store.status("user-a")
    assert status.user_used == 2
    assert status.remaining_user == 1
    assert status.remaining_month == 48


def test_batch_exceeding_limit_is_rejected_whole(tmp_path: Path) -> None:
    store = make_store(tmp_path, per_user=3, monthly=50)
    store.try_consume("user-a", 2)  # 1 remaining
    allowed, _ = store.try_consume("user-a", 2)  # would exceed the per-user cap
    assert allowed is False
    # Nothing was partially recorded.
    assert store.status("user-a").user_used == 2


def test_month_rollover_resets_counters(tmp_path: Path) -> None:
    store = make_store(tmp_path, per_user=3, monthly=50)
    store.try_consume("user-a", 3)

    # Simulate the start of a new month by rewriting the stored month key.
    data = json.loads(store.path.read_text(encoding="utf-8"))
    data["month"] = "2000-01"
    store.path.write_text(json.dumps(data), encoding="utf-8")

    allowed, _ = store.try_consume("user-a", 1)
    assert allowed is True
    assert store.status("user-a").user_used == 1
    assert store.status("user-a").monthly_used == 1
