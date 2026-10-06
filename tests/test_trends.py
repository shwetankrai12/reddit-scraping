from datetime import datetime, timezone, timedelta
from pain_radar.scoring.trends import TrendDetector


def test_trend_detection_rising():
    detector = TrendDetector(window_days=30)
    now = datetime.now(timezone.utc)

    # 10 mentions in current 30 days, 2 mentions in previous 30 days -> +400%
    current_ts = [(now - timedelta(days=5)).isoformat() for _ in range(10)]
    prev_ts = [(now - timedelta(days=40)).isoformat() for _ in range(2)]

    label, growth, audit = TrendDetector(window_days=30).evaluate_trend(current_ts + prev_ts)
    assert label == "RISING"
    assert growth >= 0.50
    assert audit["current_window"] == 10
    assert audit["previous_window"] == 2


def test_trend_detection_stable():
    detector = TrendDetector(window_days=30)
    now = datetime.now(timezone.utc)

    current_ts = [(now - timedelta(days=5)).isoformat() for _ in range(10)]
    prev_ts = [(now - timedelta(days=40)).isoformat() for _ in range(10)]

    label, growth, audit = detector.evaluate_trend(current_ts + prev_ts)
    assert label == "STABLE"
    assert growth == 0.0


def test_trend_detection_small_sample():
    detector = TrendDetector(window_days=30)
    now = datetime.now(timezone.utc)
    # Only 2 mentions
    ts = [(now - timedelta(days=2)).isoformat() for _ in range(2)]

    label, growth, audit = detector.evaluate_trend(ts)
    assert label == "NEW"
    assert growth == 0.0
