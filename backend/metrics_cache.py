# metrics_cache.py
import time
from typing import Any, Dict, Optional

class MetricsCache:
    def __init__(self, ttl_seconds: int = 30):
        self.ttl = ttl_seconds
        self._value: Optional[Dict[str, Any]] = None
        self._expires_at: float = 0.0

    def get(self) -> Optional[Dict[str, Any]]:
        if self._value is None:
            return None
        if time.time() >= self._expires_at:
            # expired
            self._value = None
            return None
        return self._value

    def set(self, data: Dict[str, Any]) -> None:
        self._value = data
        self._expires_at = time.time() + self.ttl

metrics_cache = MetricsCache(ttl_seconds=30)
