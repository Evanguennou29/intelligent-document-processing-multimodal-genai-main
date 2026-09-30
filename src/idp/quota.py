"""Rate limiting and usage quotas for the hosted demo.

The Streamlit Community Cloud demo runs without any login, so "per user" is a
best-effort anonymous identity derived from the request headers (a hash of the
client IP). The monthly cap is a global counter. Both limits are persisted to a
small JSON file in a writable directory.

Everything is configurable through the environment (secrets on the cloud):

- ``DEMO_QUOTA_ENABLED``   - enable/disable the quotas (default ``false``)
- ``DEMO_PER_USER_LIMIT``  - documents a single visitor may process (default 3)
- ``DEMO_MONTHLY_LIMIT``   - total documents per calendar month (default 50)
- ``DEMO_QUOTA_PATH``      - where the counter is stored

Note: on Streamlit Community Cloud the filesystem persists between user
sessions but resets on redeploy. For a counter that survives redeploys, point
``DEMO_QUOTA_PATH`` at a mounted volume or swap this store for a hosted
key-value service.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from idp.config import Settings, get_settings
from idp.logging_utils import get_logger

logger = get_logger(__name__)

_LOCK = threading.Lock()


@dataclass(frozen=True)
class QuotaStatus:
    """Read-only snapshot of the current usage."""

    monthly_used: int
    monthly_limit: int
    user_used: int
    user_limit: int

    @property
    def remaining_month(self) -> int:
        return max(0, self.monthly_limit - self.monthly_used)

    @property
    def remaining_user(self) -> int:
        return max(0, self.user_limit - self.user_used)


class QuotaStore:
    """Tiny JSON-file-backed counter with a per-calendar-month reset."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.path = Path(self.settings.demo_quota_path)
        self.user_limit = self.settings.demo_per_user_limit
        self.monthly_limit = self.settings.demo_monthly_limit

    # ------------------------------------------------------------- storage --
    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, data: dict) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:  # a read-only filesystem must not break the demo
            logger.warning("Quota non persiste (%s) : %s", self.path, exc)

    @staticmethod
    def _month_key() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def _fresh_state(self, data: dict) -> dict:
        """Return ``data`` reset if it belongs to a previous month."""
        if data.get("month") == self._month_key():
            return data
        return {"month": self._month_key(), "monthly": 0, "users": {}}

    # ------------------------------------------------------------ public API --
    def status(self, user_key: str) -> QuotaStatus:
        """Return current usage without consuming anything."""
        with _LOCK:
            data = self._fresh_state(self._load())
        monthly_used = int(data.get("monthly", 0))
        user_used = int(data.get("users", {}).get(user_key, {}).get("count", 0))
        return QuotaStatus(
            monthly_used=monthly_used,
            monthly_limit=self.monthly_limit,
            user_used=user_used,
            user_limit=self.user_limit,
        )

    def try_consume(self, user_key: str, requested: int) -> tuple[bool, str]:
        """Atomically consume ``requested`` units for ``user_key`` if allowed.

        Returns ``(allowed, message)``. When ``allowed`` is false, nothing is
        recorded and ``message`` explains which limit was reached.
        """
        with _LOCK:
            data = self._fresh_state(self._load())
            monthly_used = int(data.get("monthly", 0))
            user_used = int(data.get("users", {}).get(user_key, {}).get("count", 0))

            if monthly_used + requested > self.monthly_limit:
                return (
                    False,
                    f"Quota mensuel atteint ({monthly_used}/{self.monthly_limit}). "
                    "Revenez le mois prochain.",
                )
            if user_used + requested > self.user_limit:
                return (
                    False,
                    f"Limite atteinte pour ce visiteur ({user_used}/{self.user_limit}).",
                )

            monthly_used += requested
            user_used += requested
            data["monthly"] = monthly_used
            users = data.setdefault("users", {})
            users[user_key] = {
                "count": user_used,
                "last": datetime.now(timezone.utc).isoformat(),
            }
            self._save(data)
            return True, ""
