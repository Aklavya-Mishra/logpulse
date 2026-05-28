"""
LogPulse — Statistical Anomaly Detector
Sliding window Z-score gate. Maintains a per-service error rate
history and fires when deviation exceeds threshold.
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Optional

import numpy as np

from config import settings


@dataclass
class WindowState:
    """Sliding window state for a single service."""
    levels: deque = field(default_factory=lambda: deque())
    error_rates: deque = field(default_factory=lambda: deque())

    def push(self, level: str, window_size: int):
        """Add a new log level, evict oldest if window full."""
        self.levels.append(level)
        if len(self.levels) > window_size:
            self.levels.popleft()

    def current_error_rate(self) -> float:
        """Fraction of ERROR/CRITICAL in current window."""
        if not self.levels:
            return 0.0
        errors = sum(1 for l in self.levels if l in ("ERROR", "CRITICAL"))
        return errors / len(self.levels)

    def push_rate(self, rate: float, history_size: int = 200):
        """Maintain a rolling history of error rates for Z-score."""
        self.error_rates.append(rate)
        if len(self.error_rates) > history_size:
            self.error_rates.popleft()

    def zscore(self) -> Optional[float]:
        """
        Z-score of the most recent error rate vs historical mean/std.
        Returns None if insufficient history (< 10 points).
        """
        if len(self.error_rates) < 10:
            return None
        arr = np.array(list(self.error_rates))
        mean = arr.mean()
        std = arr.std()
        if std == 0:
            return 0.0
        return float((arr[-1] - mean) / std)


@dataclass
class AnomalyResult:
    """Result returned when an anomaly is detected."""
    service: str
    error_rate: float
    zscore: float
    window_size: int
    error_count: int
    total_count: int


class AnomalyDetector:
    """
    Stateful sliding-window anomaly detector.
    One instance shared across the application lifetime.
    """

    def __init__(self):
        self._windows: Dict[str, WindowState] = {}
        self._window_size = settings.zscore_window_size
        self._zscore_threshold = settings.zscore_threshold
        self._error_rate_threshold = settings.error_rate_threshold

    def _get_window(self, service: str) -> WindowState:
        if service not in self._windows:
            self._windows[service] = WindowState()
        return self._windows[service]

    def ingest(self, service: str, level: str) -> Optional[AnomalyResult]:
        """
        Feed one log event into the detector.

        Returns an AnomalyResult if an anomaly is detected, else None.
        The statistical gate fires when BOTH conditions are true:
          1. Current error rate > error_rate_threshold
          2. Z-score of current rate vs history > zscore_threshold
        """
        window = self._get_window(service)
        window.push(level, self._window_size)

        error_rate = window.current_error_rate()
        window.push_rate(error_rate)

        zscore = window.zscore()
        if zscore is None:
            return None  # Not enough history yet

        # Both gates must fire
        if error_rate >= self._error_rate_threshold and zscore >= self._zscore_threshold:
            error_count = sum(1 for l in window.levels if l in ("ERROR", "CRITICAL"))
            total_count = len(window.levels)
            return AnomalyResult(
                service=service,
                error_rate=round(error_rate, 4),
                zscore=round(zscore, 4),
                window_size=self._window_size,
                error_count=error_count,
                total_count=total_count,
            )

        return None


# Singleton detector instance
detector = AnomalyDetector()
