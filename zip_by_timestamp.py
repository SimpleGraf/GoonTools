"""Zip-Auswahl nach Zeitstempel

Dieses Skript sammelt Dateien unterhalb des Basisordners (standard: NGPS),
deren Dateinamen einen eingebetteten Zeitstempel im Format
        YYYY-MM-DD_HH-MM-SS
enthalten (Beispiel: cabdir_changes_2025-11-04_13-00-03.csv)
und packt nur diejenigen in ein ZIP, deren Zeitstempel zwischen den unten
konfigurierten Werten FROM_STR und TO_STR (inklusive) liegt. Die relative
Ordnerstruktur wird beibehalten.

Konfiguration oben im Skript anpassen und einfach ausführen:
    python zip_by_timestamp.py

Akzeptierte Zeitformate für FROM_STR / TO_STR:
    "YYYY-MM-DD HH:MM:SS" oder "YYYY-MM-DD_HH-MM-SS"

Hinweis: Originaldateien bleiben unverändert.
"""
from __future__ import annotations
import os
import re
import sys
from datetime import datetime
from zipfile import ZipFile, ZIP_DEFLATED
from typing import Optional, List

# ===================== CONFIG =====================
BASE_DIR = "NGPS"          # Quellbasisordner
DEST_DIR = "NGPS_ZIP"      # Zielordner für ZIP-Dateien
FROM_STR = "2026-02-05 0:00:00"  # Start-Zeit (inklusive)
TO_STR = "2026-02-05 23:59:00"    # End-Zeit (inklusive)
OUTPUT_NAME = None          # Optional fester ZIP-Dateiname, oder None für auto
DRY_RUN = False             # True: nur anzeigen, nichts schreiben
# Fortschritt
SHOW_PROGRESS = True
SINGLE_LINE_PROGRESS = True
PROGRESS_EVERY_N = 5  # bei mehrzeiliger Ausgabe: alle N Dateien
# ==================================================

TIMESTAMP_REGEX = re.compile(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})")
TIMESTAMP_FORMAT = "%Y-%m-%d_%H-%M-%S"


def parse_config_dt(value: str) -> datetime:
    """Parst konfigurierten Zeitstring.
    Akzeptiert Varianten:
      YYYY-MM-DD HH:MM:SS
      YYYY-MM-DD_HH:MM:SS
      YYYY-MM-DD_HH-MM-SS
      YYYY-MM-DD H:MM:SS (einstellige Stunde)
    Intern wird alles normalisiert auf TIMESTAMP_FORMAT (mit Bindestrichen) und zweistellige Teile.
    """
    raw = value.strip().replace(" ", "_")
    if '_' not in raw:
        raise ValueError(f"Zeitformat ohne '_' zwischen Datum und Zeit: {value}")
    date_part, time_part = raw.split('_', 1)
    # Ersetze Doppelpunkte durch Bindestriche zur Vereinheitlichung
    time_part = time_part.replace(':', '-')
    comps = time_part.split('-')
    if len(comps) != 3:
        raise ValueError(f"Zeitteil hat nicht 3 Komponenten: {time_part}")
    hour, minute, second = comps
    hour = hour.zfill(2)
    minute = minute.zfill(2)
    second = second.zfill(2)
    normalized = f"{date_part}_{hour}-{minute}-{second}"
    return datetime.strptime(normalized, TIMESTAMP_FORMAT)


def extract_timestamp(filename: str) -> Optional[datetime]:
    m = TIMESTAMP_REGEX.search(filename)
    if not m:
        return None
    stamp = m.group(1)
    try:
        return datetime.strptime(stamp, TIMESTAMP_FORMAT)
    except ValueError:
        return None


def find_matching_files(base_dir: str, dt_from: datetime, dt_to: datetime) -> List[str]:
    matches: List[str] = []
    for root, dirs, files in os.walk(base_dir):
        for fn in files:
            ts = extract_timestamp(fn)
            if ts is None:
                continue
            if dt_from <= ts <= dt_to:
                full_path = os.path.join(root, fn)
                matches.append(full_path)
    return matches


def build_output_name(dt_from: datetime, dt_to: datetime) -> str:
    return f"export_{dt_from.strftime(TIMESTAMP_FORMAT)}_to_{dt_to.strftime(TIMESTAMP_FORMAT)}.zip"


def create_zip(base_dir: str, dest_dir: str, files: List[str], output_name: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    zip_path = os.path.join(dest_dir, output_name)
    total_bytes = 0
    sizes: List[int] = []
    for fp in files:
        try:
            sz = os.path.getsize(fp)
        except OSError:
            sz = 0
        sizes.append(sz)
        total_bytes += sz
    start_time = datetime.now()
    processed_bytes = 0
    processed_files = 0
    last_line_len = 0
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for idx, fp in enumerate(files):
            arcname = os.path.relpath(fp, base_dir)
            try:
                zf.write(fp, arcname)
            except Exception as e:
                print(f"Fehler beim Hinzufügen: {arcname}: {e}")
                continue
            processed_files += 1
            processed_bytes += sizes[idx]
            if SHOW_PROGRESS:
                pct = (processed_bytes / total_bytes * 100) if total_bytes else 100.0
                mb_done = processed_bytes / (1024*1024)
                mb_total = total_bytes / (1024*1024)
                elapsed = (datetime.now() - start_time).total_seconds()
                rate_mb_s = (processed_bytes / (1024*1024) / elapsed) if elapsed > 0 else 0.0
                remaining_files = len(files) - processed_files
                if SINGLE_LINE_PROGRESS:
                    line = (f"Datei: {os.path.basename(fp)} | {processed_files}/{len(files)} ({pct:.2f}%) | "
                            f"Daten: {mb_done:.2f}/{mb_total:.2f} MB | Rate: {rate_mb_s:.2f} MB/s | Verbleibend: {remaining_files}")
                    print("\r" + line.ljust(140), end="", flush=True)
                else:
                    if processed_files % PROGRESS_EVERY_N == 0 or processed_files == len(files):
                        print(f"Fortschritt: {processed_files}/{len(files)} Dateien ({pct:.2f}%) | Daten: {mb_done:.2f}/{mb_total:.2f} MB")
    if SHOW_PROGRESS and SINGLE_LINE_PROGRESS:
        print()  # Zeilenumbruch nach letzter Statuszeile
    return zip_path


def main():
    try:
        dt_from = parse_config_dt(FROM_STR)
        dt_to = parse_config_dt(TO_STR)
    except Exception as e:
        print(f"Fehler beim Parsen der Zeiten: {e}")
        return 2
    if dt_from > dt_to:
        print("Start-Datum liegt nach End-Datum.")
        return 3
    if not os.path.isdir(BASE_DIR):
        print(f"Basisordner nicht gefunden: {BASE_DIR}")
        return 4
    print(f"Suche Dateien in '{BASE_DIR}' mit Zeitstempel zwischen {dt_from} und {dt_to} ...")
    files = find_matching_files(BASE_DIR, dt_from, dt_to)
    print(f"Gefundene passende Dateien: {len(files)}")
    output_name = OUTPUT_NAME or build_output_name(dt_from, dt_to)
    if not files:
        print("Keine passenden Dateien gefunden.")
        if DRY_RUN:
            return 0
        # leere ZIP trotzdem erzeugen
    if DRY_RUN:
        print("Dry-Run aktiv. Würde ZIP erstellen:")
        print(f"  Zielordner: {DEST_DIR}")
        print(f"  ZIP-Datei: {output_name}")
        for fp in files[:20]:
            print("  +", os.path.relpath(fp, BASE_DIR))
        if len(files) > 20:
            print(f"  ... {len(files)-20} weitere Dateien")
        return 0
    start_zip = datetime.now()
    zip_path = create_zip(BASE_DIR, DEST_DIR, files, output_name)
    end_zip = datetime.now()
    total_bytes = sum(os.path.getsize(f) for f in files) if files else 0
    duration = (end_zip - start_zip).total_seconds()
    rate_mb_s = (total_bytes/1024/1024 / duration) if duration > 0 else 0.0
    print(f"ZIP erstellt: {zip_path}")
    print(f"Dateien: {len(files)} | Gesamtgröße: {total_bytes/1024/1024:.2f} MB | Dauer: {duration:.2f} s | Rate: {rate_mb_s:.2f} MB/s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
