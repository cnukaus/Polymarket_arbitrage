import importlib.util
import math
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
MODULE_PATH = PROJECT_ROOT / "odds_sequence_monitor.py"
SPEC = importlib.util.spec_from_file_location("odds_sequence_monitor", MODULE_PATH)
odds_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(odds_module)

DIRECTION_DOWN = odds_module.DIRECTION_DOWN
DIRECTION_UP = odds_module.DIRECTION_UP
evaluate_threshold_sets = odds_module.evaluate_threshold_sets
extract_sequences = odds_module.extract_sequences
load_time_series = odds_module.load_time_series
parse_threshold_values = odds_module.parse_threshold_values
split_into_sequences = odds_module.split_into_sequences


def build_dataframe(offset_minutes, prices):
    base = pd.Timestamp("2024-01-01T00:00:00Z")
    timestamps = [base + pd.Timedelta(minutes=offset) for offset in offset_minutes]
    return pd.DataFrame({"timestamp": timestamps, "price": prices})


def test_parse_threshold_values_accepts_percentages():
    thresholds = parse_threshold_values(["80", "95"])
    assert thresholds == (0.8, 0.95)


def test_split_into_sequences_respects_gap():
    df = build_dataframe(
        [0, 30, 100, 130],
        [0.5, 0.55, 0.6, 0.65],
    )

    sequences = split_into_sequences(df, max_gap_minutes=60)
    assert len(sequences) == 2
    assert sequences[0].iloc[-1]["timestamp"] == pd.Timestamp("2024-01-01T00:30:00Z")
    assert sequences[1].iloc[0]["timestamp"] == pd.Timestamp("2024-01-01T01:40:00Z")


def test_evaluate_threshold_sets_counts_sequences_and_events():
    event_a = build_dataframe(
        [0, 30, 60, 190, 220],
        [0.75, 0.82, 0.96, 0.81, 0.89],
    )
    event_b = build_dataframe(
        [5, 35, 60],
        [0.79, 0.83, 0.9],
    )

    series = {"event_a_yes": event_a, "event_b_yes": event_b}
    sequences = extract_sequences(series, max_gap_minutes=60)

    stats_objects = evaluate_threshold_sets(
        sequences,
        threshold_sets=[(0.8, 0.95)],
        direction=DIRECTION_UP,
    )

    stats = stats_objects[0]
    assert stats.sequence_base_count == 3
    assert stats.sequence_success_count == 1
    assert stats.event_base_ids == {"event_a_yes", "event_b_yes"}
    assert stats.event_success_ids == {"event_a_yes"}
    assert math.isclose(stats.sequence_success_ratio, 1 / 3)
    assert math.isclose(stats.event_success_ratio, 0.5)


def test_load_time_series_reads_csv(tmp_path):
    df = build_dataframe([0, 30, 60], [0.4, 0.5, 0.6])
    csv_path = tmp_path / "market_yes.csv"
    df.to_csv(csv_path, index=False)

    series = load_time_series(tmp_path, extensions=[".csv"])
    assert "market_yes" in series
    loaded = series["market_yes"]
    assert list(loaded.columns) == ["timestamp", "price"]
    assert len(loaded) == 3


def test_evaluate_threshold_sets_down_direction():
    event = build_dataframe(
        [0, 30, 60, 90],
        [0.9, 0.8, 0.7, 0.5],
    )

    sequences = extract_sequences({"event_down_yes": event}, max_gap_minutes=60)
    stats_objects = evaluate_threshold_sets(
        sequences,
        threshold_sets=[(0.85, 0.6)],
        direction=DIRECTION_DOWN,
    )

    stats = stats_objects[0]
    assert stats.sequence_base_count == 1
    assert stats.sequence_success_count == 1
    assert stats.event_success_ids == {"event_down_yes"}
