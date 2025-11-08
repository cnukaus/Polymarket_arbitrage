#!/usr/bin/env python3
"""Utilities for analysing Polymarket odds progressions and threshold behaviours."""

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

DIRECTION_UP = "up"
DIRECTION_DOWN = "down"
VALID_DIRECTIONS = {DIRECTION_UP, DIRECTION_DOWN}


@dataclass
class OddsSequence:
    """A contiguous slice of odds history for a market outcome."""

    identifier: str
    sequence_index: int
    data: pd.DataFrame

    @property
    def sequence_id(self) -> str:
        return f"{self.identifier}#{self.sequence_index}"


@dataclass
class ThresholdProgressStats:
    """Aggregated progression statistics across sequences."""

    threshold_path: Tuple[float, ...]
    direction: str
    sequence_base_count: int = 0
    sequence_success_count: int = 0
    event_base_ids: set = field(default_factory=set)
    event_success_ids: set = field(default_factory=set)

    @property
    def sequence_success_ratio(self) -> float:
        if self.sequence_base_count == 0:
            return 0.0
        return self.sequence_success_count / self.sequence_base_count

    @property
    def event_success_ratio(self) -> float:
        if not self.event_base_ids:
            return 0.0
        return len(self.event_success_ids) / len(self.event_base_ids)

    def to_dict(self, include_identifiers: bool = False) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "threshold_path": [round(threshold, 6) for threshold in self.threshold_path],
            "direction": self.direction,
            "sequence_base_count": self.sequence_base_count,
            "sequence_success_count": self.sequence_success_count,
            "sequence_success_ratio": round(self.sequence_success_ratio, 6),
            "event_base_count": len(self.event_base_ids),
            "event_success_count": len(self.event_success_ids),
            "event_success_ratio": round(self.event_success_ratio, 6),
        }
        if include_identifiers:
            payload["event_base_identifiers"] = sorted(self.event_base_ids)
            payload["event_success_identifiers"] = sorted(self.event_success_ids)
        return payload


def parse_threshold_values(raw_values: Sequence[str]) -> Tuple[float, ...]:
    if not raw_values:
        raise ValueError("At least one threshold is required per set.")

    thresholds: List[float] = []
    for raw in raw_values:
        value = float(raw)
        if value > 1:
            value /= 100.0
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"Threshold {raw} normalised to {value:.4f} is outside [0, 1].")
        thresholds.append(value)

    return tuple(thresholds)


def load_time_series(
    data_dir: Path,
    extensions: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
) -> Dict[str, pd.DataFrame]:
    if extensions is None:
        extensions = (".csv", ".parquet")

    normalised_exts = tuple(ext if ext.startswith(".") else f".{ext}" for ext in extensions)
    series: Dict[str, pd.DataFrame] = {}

    count = 0
    for path in sorted(data_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in normalised_exts:
            continue

        df = _load_single_series(path)
        if df.empty:
            continue

        identifier = path.relative_to(data_dir).as_posix()
        identifier = identifier.rsplit(".", 1)[0]
        series[identifier] = df

        count += 1
        if limit is not None and count >= limit:
            break

    return series


def _load_single_series(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path)
    elif suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        return pd.DataFrame()

    if "timestamp" not in df.columns or "price" not in df.columns:
        return pd.DataFrame()

    cleaned = df.copy()
    cleaned["timestamp"] = pd.to_datetime(cleaned["timestamp"], utc=True, errors="coerce")
    cleaned["price"] = pd.to_numeric(cleaned["price"], errors="coerce")
    cleaned = cleaned.dropna(subset=["timestamp", "price"]).sort_values("timestamp")
    cleaned = cleaned.reset_index(drop=True)
    return cleaned


def split_into_sequences(df: pd.DataFrame, max_gap_minutes: int) -> List[pd.DataFrame]:
    if df.empty:
        return []

    max_gap = pd.Timedelta(minutes=max_gap_minutes)
    timestamp_diff = df["timestamp"].diff()
    group_ids = (timestamp_diff > max_gap).cumsum()

    sequences: List[pd.DataFrame] = []
    for _, group in df.groupby(group_ids):
        group = group.reset_index(drop=True)
        if not group.empty:
            sequences.append(group)

    return sequences


def extract_sequences(series: Dict[str, pd.DataFrame], max_gap_minutes: int) -> List[OddsSequence]:
    sequences: List[OddsSequence] = []
    for identifier, df in series.items():
        chunks = split_into_sequences(df, max_gap_minutes)
        for index, chunk in enumerate(chunks):
            sequences.append(OddsSequence(identifier=identifier, sequence_index=index, data=chunk))
    return sequences


def evaluate_threshold_sets(
    sequences: Iterable[OddsSequence],
    threshold_sets: Sequence[Tuple[float, ...]],
    direction: str,
) -> List[ThresholdProgressStats]:
    stats_objects = [ThresholdProgressStats(threshold_path=thresholds, direction=direction) for thresholds in threshold_sets]

    for sequence in sequences:
        prices = sequence.data["price"].tolist()
        for stats in stats_objects:
            base_hit, success = _sequence_hits_thresholds(prices, stats.threshold_path, direction)
            if not base_hit:
                continue

            stats.sequence_base_count += 1
            stats.event_base_ids.add(sequence.identifier)

            if success:
                stats.sequence_success_count += 1
                stats.event_success_ids.add(sequence.identifier)

    return stats_objects


def _meets_threshold(value: float, threshold: float, direction: str) -> bool:
    if direction == DIRECTION_UP:
        return value >= threshold
    return value <= threshold


def _sequence_hits_thresholds(
    prices: Sequence[float],
    thresholds: Tuple[float, ...],
    direction: str,
) -> Tuple[bool, bool]:
    if not thresholds:
        return False, False

    if not prices:
        return False, False

    base_index = _find_index(prices, thresholds[0], direction, start=0)
    if base_index is None:
        return False, False

    current_index = base_index
    for threshold in thresholds[1:]:
        next_index = _find_index(prices, threshold, direction, start=current_index + 1)
        if next_index is None:
            return True, False
        current_index = next_index

    return True, True


def _find_index(
    prices: Sequence[float],
    threshold: float,
    direction: str,
    start: int,
) -> Optional[int]:
    for index in range(start, len(prices)):
        value = prices[index]
        if pd.isna(value):
            continue
        if _meets_threshold(value, threshold, direction):
            return index
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyse historical odds sequences and report threshold progression statistics.",
    )
    parser.add_argument(
        "--data-dir",
        default="data/historical",
        help="Directory with historical CSV/Parquet files (default: data/historical).",
    )
    parser.add_argument(
        "--max-gap-minutes",
        type=int,
        default=60,
        help="Maximum allowed gap between observations to stay within a sequence (default: 60).",
    )
    parser.add_argument(
        "--threshold-set",
        dest="threshold_sets",
        action="append",
        nargs="+",
        required=True,
        help="Threshold progression definition (provide multiple values per set; use multiple flags for multiple sets).",
    )
    parser.add_argument(
        "--direction",
        choices=sorted(VALID_DIRECTIONS),
        default=DIRECTION_UP,
        help="Progression direction: up (default) or down.",
    )
    parser.add_argument(
        "--output-json",
        help="Optional path to write JSON summary.",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".csv", ".parquet"],
        help="File extensions to include (default: .csv .parquet).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of series loaded for quick inspection.",
    )
    parser.add_argument(
        "--include-identifiers",
        action="store_true",
        help="Include event identifiers in JSON output for thresholds.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        raise SystemExit(f"Data directory {data_dir} does not exist.")

    threshold_sets = [parse_threshold_values(values) for values in args.threshold_sets]
    series = load_time_series(data_dir, extensions=args.extensions, limit=args.limit)
    sequences = extract_sequences(series, args.max_gap_minutes)
    stats_objects = evaluate_threshold_sets(sequences, threshold_sets, args.direction)

    print(f"Series processed: {len(series)}")
    print(f"Sequences analysed: {len(sequences)}")
    print(f"Max gap (minutes): {args.max_gap_minutes}")
    print("")

    for stats in stats_objects:
        threshold_display = " -> ".join(f"{value:.2%}" for value in stats.threshold_path)
        print(f"Threshold path: {threshold_display} ({stats.direction})")
        print(f"  Sequences reaching first threshold: {stats.sequence_base_count}")
        print(f"  Sequences reaching full path: {stats.sequence_success_count}")
        print(f"  Sequence success ratio: {stats.sequence_success_ratio:.2%}")
        print(f"  Events reaching first threshold: {len(stats.event_base_ids)}")
        print(f"  Events reaching full path: {len(stats.event_success_ids)}")
        print(f"  Event success ratio: {stats.event_success_ratio:.2%}")
        print("")

    if args.output_json:
        payload = {
            "data_dir": str(data_dir),
            "max_gap_minutes": args.max_gap_minutes,
            "direction": args.direction,
            "series_processed": len(series),
            "sequences_analysed": len(sequences),
            "thresholds": [stats.to_dict(include_identifiers=args.include_identifiers) for stats in stats_objects],
        }
        Path(args.output_json).write_text(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
