#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DATASET_RE = re.compile(
    r"^(speed_out|position_out|linpos_out|gnss_out|balises_out)_(\d{8}_\d{6})\.csv$"
)
REQUIRED_TYPES = ("speed_out", "position_out", "linpos_out", "gnss_out", "balises_out")
DEFAULT_DATA_SUBDIR = "output_obif"
MAX_ABS_SPEED_MS = 1_000_000
6

@dataclass
class DatasetFiles:
    suffix: str
    speed_out: Path
    position_out: Path
    linpos_out: Path
    gnss_out: Path
    balises_out: Path


def has_data_rows(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            _ = handle.readline()
            second = handle.readline()
        return bool(second.strip())
    except OSError:
        return False


def discover_dataset_files(base_dir: Path) -> Dict[str, Dict[str, Path]]:
    by_type: Dict[str, Dict[str, Path]] = {name: {} for name in REQUIRED_TYPES}

    for path in base_dir.iterdir():
        if not path.is_file():
            continue
        match = DATASET_RE.match(path.name)
        if not match:
            continue

        sensor_type, suffix = match.group(1), match.group(2)
        if sensor_type in by_type and has_data_rows(path):
            by_type[sensor_type][suffix] = path

    return by_type


def build_common_datasets(by_type: Dict[str, Dict[str, Path]]) -> Dict[str, DatasetFiles]:
    available_sets = [set(by_type[sensor].keys()) for sensor in REQUIRED_TYPES]
    if not available_sets:
        return {}

    common_suffixes = set.intersection(*available_sets)
    datasets: Dict[str, DatasetFiles] = {}

    for suffix in sorted(common_suffixes):
        datasets[suffix] = DatasetFiles(
            suffix=suffix,
            speed_out=by_type["speed_out"][suffix],
            position_out=by_type["position_out"][suffix],
            linpos_out=by_type["linpos_out"][suffix],
            gnss_out=by_type["gnss_out"][suffix],
            balises_out=by_type["balises_out"][suffix],
        )

    return datasets


def choose_dataset(datasets: Dict[str, DatasetFiles]) -> DatasetFiles:
    suffixes = sorted(datasets.keys())
    if not suffixes:
        raise RuntimeError("Keine vollständigen Datensätze gefunden.")

    print("\nVerfügbare Datensätze (striktes Suffix-Matching über speed/position/linpos/gnss/balises):")
    for index, suffix in enumerate(suffixes, start=1):
        print(f"  [{index:2d}] {suffix}")

    default_index = len(suffixes)
    while True:
        raw = input(f"\nDatensatz wählen [1-{len(suffixes)}] (Enter = {default_index}): ").strip()
        if not raw:
            return datasets[suffixes[default_index - 1]]
        if raw.isdigit():
            selected = int(raw)
            if 1 <= selected <= len(suffixes):
                return datasets[suffixes[selected - 1]]
        print("Ungültige Eingabe. Bitte Index aus der Liste eingeben.")


def parse_datetime_input(value: str) -> Optional[pd.Timestamp]:
    text = value.strip()
    if not text:
        return None

    try:
        parsed = pd.to_datetime(text, utc=True)
        if pd.isna(parsed):
            raise ValueError
        return parsed
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            "Zeitformat ungültig. Beispiel: 2026-02-19 11:23:00 oder 2026-02-19T11:23:00Z"
        ) from exc


def prompt_time_window() -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    print("\nOptionaler Zeitbereich (UTC). Leer lassen = gesamter Bereich.")
    print("Beispiel: 2026-02-19 11:23:00")

    while True:
        start_raw = input("Startzeit: ")
        end_raw = input("Endzeit: ")

        try:
            start = parse_datetime_input(start_raw)
            end = parse_datetime_input(end_raw)
            if start is not None and end is not None and start > end:
                print("Startzeit liegt nach Endzeit. Bitte erneut eingeben.")
                continue
            return start, end
        except ValueError as err:
            print(err)


def _to_datetime(series: pd.Series, unit: str) -> pd.Series:
    return pd.to_datetime(series, unit=unit, utc=True, errors="coerce")


def sanitize_speed(series: pd.Series, max_abs: float = MAX_ABS_SPEED_MS) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    numeric = numeric.where(numeric.abs() <= max_abs, np.nan)
    return numeric


def filter_time_range(
    df: pd.DataFrame,
    time_col: str,
    start: Optional[pd.Timestamp],
    end: Optional[pd.Timestamp],
) -> pd.DataFrame:
    if df.empty:
        return df

    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= df[time_col] >= start
    if end is not None:
        mask &= df[time_col] <= end
    return df.loc[mask].copy()


def load_speed_out(path: Path) -> pd.DataFrame:
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if len(row) < 3:
                continue
            rows.append((row[0], row[2]))

    if not rows:
        return pd.DataFrame(columns=["datetime", "speed_ms"])

    df = pd.DataFrame(rows, columns=["t_unix_ns", "speed_ms"])
    df["t_unix_ns"] = pd.to_numeric(df["t_unix_ns"], errors="coerce")
    df["speed_ms"] = sanitize_speed(df["speed_ms"])
    df = df.dropna(subset=["t_unix_ns", "speed_ms"])
    df["datetime"] = _to_datetime(df["t_unix_ns"], unit="ns")
    return df.dropna(subset=["datetime"]).sort_values("datetime")


def load_position_out(path: Path) -> pd.DataFrame:
    cols = ["time_ns", "speed_ms", "positining_arc_length_forwards"]
    df = pd.read_csv(path, usecols=cols)
    df["time_ns"] = pd.to_numeric(df["time_ns"], errors="coerce")
    df["speed_ms"] = sanitize_speed(df["speed_ms"])
    df["positining_arc_length_forwards"] = pd.to_numeric(
        df["positining_arc_length_forwards"], errors="coerce"
    )
    df = df.dropna(subset=["time_ns"])
    df["datetime"] = _to_datetime(df["time_ns"], unit="ns")
    return df.dropna(subset=["datetime"]).sort_values("datetime")


def load_linpos_out(path: Path) -> pd.DataFrame:
    cols = ["SYSTEM_TIMESTAMP", "MEASUREMENT_TIMESTAMP", "DISTANCE", "SPEED"]
    df = pd.read_csv(path, usecols=cols)
    for col in cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["SYSTEM_TIMESTAMP", "MEASUREMENT_TIMESTAMP"])
    df["datetime"] = _to_datetime(df["SYSTEM_TIMESTAMP"], unit="ms")
    df["linpos_speed_ms"] = sanitize_speed(df["SPEED"] / 100.0)
    df["linpos_distance_m"] = df["DISTANCE"] / 100.0
    df["linpos_system_period_ms"] = df["SYSTEM_TIMESTAMP"].diff()
    df["linpos_measurement_period_ms"] = df["MEASUREMENT_TIMESTAMP"].diff()
    return df.dropna(subset=["datetime"]).sort_values("datetime")


def load_gnss_out(path: Path) -> pd.DataFrame:
    cols = ["unix_ns", "speed_horizontal_ms", "vn_mps", "ve_mps"]
    df = pd.read_csv(path, usecols=lambda c: c in cols)
    if "unix_ns" not in df.columns:
        return pd.DataFrame(columns=["datetime", "gnss_speed_ms"])

    df["unix_ns"] = pd.to_numeric(df["unix_ns"], errors="coerce")

    if "speed_horizontal_ms" in df.columns:
        df["gnss_speed_ms"] = sanitize_speed(df["speed_horizontal_ms"])
    else:
        vn = pd.to_numeric(df.get("vn_mps"), errors="coerce")
        ve = pd.to_numeric(df.get("ve_mps"), errors="coerce")
        df["gnss_speed_ms"] = sanitize_speed(np.sqrt(vn.pow(2) + ve.pow(2)))

    df = df.dropna(subset=["unix_ns", "gnss_speed_ms"])
    df["datetime"] = _to_datetime(df["unix_ns"], unit="ns")
    return df.dropna(subset=["datetime"]).sort_values("datetime")


def load_balises_out(path: Path) -> pd.DataFrame:
    cols = ["epoch", "baliseId", "arc_lenth"]
    df = pd.read_csv(path, usecols=lambda c: c in cols)
    required = {"epoch", "arc_lenth"}
    if not required.issubset(df.columns):
        return pd.DataFrame(columns=["datetime", "arc_lenth", "baliseId"])

    df["epoch"] = pd.to_numeric(df["epoch"], errors="coerce")
    df["arc_lenth"] = pd.to_numeric(df["arc_lenth"], errors="coerce")
    df = df.dropna(subset=["epoch", "arc_lenth"])
    df["datetime"] = _to_datetime(df["epoch"], unit="ms")
    if "baliseId" not in df.columns:
        df["baliseId"] = "balise"
    return df.dropna(subset=["datetime"]).sort_values("datetime")


def compute_position_period(position_df: pd.DataFrame) -> pd.DataFrame:
    if position_df.empty:
        return pd.DataFrame(columns=["datetime", "position_period_ms"])

    period = position_df[["datetime", "time_ns"]].copy()
    period["position_period_ms"] = period["time_ns"].diff() / 1e6
    period = period.dropna(subset=["position_period_ms"])
    return period


def plot_speeds(
    speed_df: pd.DataFrame,
    position_df: pd.DataFrame,
    linpos_df: pd.DataFrame,
    gnss_df: pd.DataFrame,
) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    fig.canvas.manager.set_window_title("Geschwindigkeit über Zeit")

    if not speed_df.empty:
        ax.plot(speed_df["datetime"], speed_df["speed_ms"], label="speed_out.speed_ms", linewidth=1.1)
    if not position_df.empty:
        ax.plot(
            position_df["datetime"],
            position_df["speed_ms"],
            label="position_out.speed_ms",
            linewidth=1.1,
        )
    if not linpos_df.empty:
        ax.plot(
            linpos_df["datetime"],
            linpos_df["linpos_speed_ms"],
            label="linpos_out.SPEED/100",
            linewidth=1.1,
        )
    if not gnss_df.empty:
        ax.plot(
            gnss_df["datetime"],
            gnss_df["gnss_speed_ms"],
            label="gnss_out.speed_horizontal_ms",
            linewidth=1.1,
        )

    ax.set_title("Geschwindigkeit über Zeit")
    ax.set_xlabel("Zeit (UTC)")
    ax.set_ylabel("Geschwindigkeit [m/s]")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.autofmt_xdate()


def plot_periods(
    linpos_df: pd.DataFrame,
    position_period_df: pd.DataFrame,
) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    fig.canvas.manager.set_window_title("Periodenzeit über Zeit")

    if not linpos_df.empty:
        ax.plot(
            linpos_df["datetime"],
            linpos_df["linpos_system_period_ms"],
            label="linpos ΔSYSTEM_TIMESTAMP",
            linewidth=1.1,
        )
        ax.plot(
            linpos_df["datetime"],
            linpos_df["linpos_measurement_period_ms"],
            label="linpos ΔMEASUREMENT_TIMESTAMP",
            linewidth=1.1,
        )

    if not position_period_df.empty:
        ax.plot(
            position_period_df["datetime"],
            position_period_df["position_period_ms"],
            label="position_out Δtime_ns",
            linewidth=1.1,
        )

    ax.set_title("Periodenzeit über Zeit")
    ax.set_xlabel("Zeit (UTC)")
    ax.set_ylabel("Periodenzeit [ms]")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.autofmt_xdate()


def plot_distances(
    linpos_df: pd.DataFrame,
    position_df: pd.DataFrame,
    balises_df: pd.DataFrame,
) -> None:
    fig, ax = plt.subplots(figsize=(14, 6))
    fig.canvas.manager.set_window_title("Distanz über Zeit")

    if not linpos_df.empty:
        ax.plot(
            linpos_df["datetime"],
            linpos_df["linpos_distance_m"],
            label="linpos DISTANCE/100",
            linewidth=1.2,
        )

    if not position_df.empty:
        ax.plot(
            position_df["datetime"],
            position_df["positining_arc_length_forwards"],
            label="position positining_arc_length_forwards",
            linewidth=1.2,
        )

    if not balises_df.empty:
        ax.scatter(
            balises_df["datetime"],
            balises_df["arc_lenth"],
            label="balises arc_lenth",
            marker="x",
            s=45,
            c="red",
            zorder=4,
        )

    ax.set_title("Distanz über Zeit inkl. Balisen")
    ax.set_xlabel("Zeit (UTC)")
    ax.set_ylabel("Distanz [m]")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.autofmt_xdate()


def print_loaded_info(
    selected: DatasetFiles,
    start: Optional[pd.Timestamp],
    end: Optional[pd.Timestamp],
    speed_df: pd.DataFrame,
    position_df: pd.DataFrame,
    linpos_df: pd.DataFrame,
    gnss_df: pd.DataFrame,
    balises_df: pd.DataFrame,
) -> None:
    print("\n--- Auswahl ---")
    print(f"Suffix: {selected.suffix}")
    print(f"speed_out:    {selected.speed_out.name}")
    print(f"position_out: {selected.position_out.name}")
    print(f"linpos_out:   {selected.linpos_out.name}")
    print(f"gnss_out:     {selected.gnss_out.name}")
    print(f"balises_out:  {selected.balises_out.name}")

    if start is None and end is None:
        print("Zeitfenster: gesamter Bereich")
    else:
        print(f"Zeitfenster: {start} bis {end}")

    print("\n--- Zeilen nach Filter ---")
    print(f"speed_out:    {len(speed_df)}")
    print(f"position_out: {len(position_df)}")
    print(f"linpos_out:   {len(linpos_df)}")
    print(f"gnss_out:     {len(gnss_df)}")
    print(f"balises_out:  {len(balises_df)}")


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    preferred_data_dir = script_dir / DEFAULT_DATA_SUBDIR
    base_dir = preferred_data_dir if preferred_data_dir.is_dir() else script_dir

    if base_dir == preferred_data_dir:
        print(f"Datenordner: {base_dir}")
    else:
        print(
            f"Hinweis: Unterordner '{DEFAULT_DATA_SUBDIR}' nicht gefunden, nutze stattdessen {script_dir}"
        )

    by_type = discover_dataset_files(base_dir)
    datasets = build_common_datasets(by_type)

    if not datasets:
        print("Keine vollständigen Datensätze mit identischem Suffix und Datenzeilen gefunden.")
        return 1

    selected = choose_dataset(datasets)
    start, end = prompt_time_window()

    try:
        speed_df = load_speed_out(selected.speed_out)
        position_df = load_position_out(selected.position_out)
        linpos_df = load_linpos_out(selected.linpos_out)
        gnss_df = load_gnss_out(selected.gnss_out)
        balises_df = load_balises_out(selected.balises_out)
    except ValueError as err:
        print(f"Fehler beim Laden der Daten: {err}")
        return 1

    speed_df = filter_time_range(speed_df, "datetime", start, end)
    position_df = filter_time_range(position_df, "datetime", start, end)
    linpos_df = filter_time_range(linpos_df, "datetime", start, end)
    gnss_df = filter_time_range(gnss_df, "datetime", start, end)
    balises_df = filter_time_range(balises_df, "datetime", start, end)

    position_period_df = compute_position_period(position_df)

    print_loaded_info(
        selected,
        start,
        end,
        speed_df,
        position_df,
        linpos_df,
        gnss_df,
        balises_df,
    )

    if (
        speed_df.empty
        and position_df.empty
        and linpos_df.empty
        and gnss_df.empty
        and balises_df.empty
    ):
        print("Keine Daten im gewählten Zeitfenster vorhanden.")
        return 1

    plot_speeds(speed_df, position_df, linpos_df, gnss_df)
    plot_periods(linpos_df, position_period_df)
    plot_distances(linpos_df, position_df, balises_df)

    plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
