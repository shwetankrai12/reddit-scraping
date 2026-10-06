from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Tuple


class TrendDetector:
    def __init__(self, window_days: int = 30):
        self.window_days = window_days

    def evaluate_trend(self, timestamps: List[str]) -> Tuple[str, float, Dict[str, int]]:
        """
        Calculates time-window growth rate and assigns trend label.
        Labels: NEW, EMERGING, RISING, STABLE, DECLINING
        """
        now = datetime.now(timezone.utc)
        current_cutoff = now - timedelta(days=self.window_days)
        previous_cutoff = now - timedelta(days=self.window_days * 2)

        current_count = 0
        previous_count = 0
        older_count = 0

        for ts in timestamps:
            if not ts:
                current_count += 1
                continue
            try:
                ts_clean = ts.replace("Z", "+00:00")
                if len(ts_clean) > 5 and ts_clean[-5] in ("+", "-") and ":" not in ts_clean[-5:]:
                    ts_clean = ts_clean[:-2] + ":" + ts_clean[-2:]
                dt = datetime.fromisoformat(ts_clean)
                if dt >= current_cutoff:
                    current_count += 1
                elif dt >= previous_cutoff:
                    previous_count += 1
                else:
                    older_count += 1
            except Exception:
                current_count += 1

        total_mentions = current_count + previous_count + older_count
        counts_audit = {
            "current_window": current_count,
            "previous_window": previous_count,
            "older_window": older_count,
            "total": total_mentions,
        }

        # Guard against small sample sizes
        if total_mentions < 3:
            return "NEW", 0.0, counts_audit

        if previous_count == 0:
            if current_count >= 5:
                growth_rate = 2.0  # +200% synthetic cap
                label = "EMERGING"
            else:
                growth_rate = 0.5
                label = "NEW"
            return label, growth_rate, counts_audit

        growth_rate = (current_count - previous_count) / float(previous_count)

        if growth_rate >= 0.50:
            label = "RISING"
        elif growth_rate >= 0.15:
            label = "EMERGING"
        elif growth_rate >= -0.20:
            label = "STABLE"
        else:
            label = "DECLINING"

        return label, round(growth_rate, 2), counts_audit
