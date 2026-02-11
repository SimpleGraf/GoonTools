"""
Remote Backup Script

Beschreibung:
  Sichert Dateien von einem entfernten Linux-System via SSH/SFTP basierend auf ihrem Alter.
  Es werden nur Dateien kopiert,
    - deren Änderungsdatum zwischen (JETZT - DAYS_BACK) und JETZT liegt
    - die lokal noch nicht existieren oder deren lokale Größe kleiner ist als die entfernte
    - die nicht als "in Benutzung" erkannt wurden (Größe ändert sich zwischen zwei Checks)

Statistiken am Ende:
  - Anzahl kopierter Dateien
  - Gesamtvolumen (MB) kopiert
  - Prozentualer Anteil gegenüber potentiell kopierbaren Dateien
  - Datenrate (MB/s) und Dateirate (Dateien/s)

Konfiguration (Anpassen nach Bedarf):
"""
# ===================== CONFIG =====================
SSH_HOST = "10.10.66.150"
SSH_PORT = 22
SSH_USER = "ngpsuser"
SSH_PASSWORD = None  # Wenn key verwendet wird, auf None lassen. Wenn None und kein Key: interaktive Passwortabfrage.
PRIVATE_KEY_PATH = None  # z.B. r"C:/Users/USER/.ssh/id_rsa"
REMOTE_BASE_DIR = "/home/ngpsuser/NGPS"  # Kein abschließender Slash nötig
LOCAL_BASE_DIR = "NGPS"  # Relativ zum Skriptpfad oder absolut angeben
DAYS_BACK = 7  # Dateien mit mtime >= now - DAYS_BACK Tage
SECONDS_STABILITY_CHECK = 3  # Wartezeit zwischen zwei Größenchecks
MAX_PARALLEL_TRANSFERS = 2  # Einfaches Parallelitäts-Limit (Thread-Anzahl)
EXCLUDE_PATTERNS = [".tmp", ".swp"]  # Endungen oder Teilstrings die ignoriert werden
FOLLOW_SYMLINKS = True  # Symlinks auf Verzeichnisse folgen
LOG_EVERY_N_FILES = 20  # Fortschritts-Log
PRINT_DEBUG = True
# Zusätzliche Optionen für Fortschritt & Stabilität
SHOW_PER_FILE_PROGRESS = True  # Einzeldatei-Fortschritt anzeigen
PROGRESS_INTERVAL_SECONDS = 2  # Mindestabstand zwischen Progress-Ausgaben pro Datei
KEEPALIVE_INTERVAL = 30  # Sekunden für SSH Keepalive
MAX_RETRIES_PER_FILE = 3  # Anzahl Wiederholungen bei Transferfehler
STATUS_UPDATE_INTERVAL = 1.0  # Sekunden zwischen Status-Aktualisierungen
USE_SINGLE_LINE_STATUS = True  # Einzeilige dynamische Anzeige benutzen
SIZE_TOLERANCE_BYTES = 512  # Dateien gelten als identisch, wenn Differenz <= Toleranz
# Performance Optionen
USE_TAR_STREAM = True  # tar über SSH streamen statt Einzel-SFTP (wenn RSYNC nicht aktiv)
TAR_STREAM_COMPRESS = True  # gzip Kompression im tar Stream (-z)
USE_RSYNC = False  # rsync verwenden (falls auf Server verfügbar)
RSYNC_PATH = "/usr/bin/rsync"  # Pfad rsync Server
RSYNC_COMPRESS = False  # -z aktivieren
# ==================================================

import os
import sys
import time
import stat
import threading
import queue
import traceback
import getpass
from dataclasses import dataclass
from typing import List, Optional, Tuple, Any

try:
    import paramiko
except ImportError:
    print("Paramiko nicht installiert. Bitte zuerst installieren (siehe README).")
    paramiko = None  # Ermöglicht Syntaxcheck ohne Installation

@dataclass
class FileTask:
    remote_path: str
    relative_path: str
    size: int
    mtime: float

@dataclass
class Stats:
    potential_files: int = 0
    potential_bytes: int = 0
    copied_files: int = 0
    copied_bytes: int = 0
    skipped_existing_files: int = 0
    skipped_existing_bytes: int = 0
    start_time: float = time.time()

    def finalize(self) -> dict:
        duration = max(time.time() - self.start_time, 0.0001)
        pct = (self.copied_files / self.potential_files * 100) if self.potential_files else 0.0
        mb_copied = self.copied_bytes / (1024 * 1024)
        potential_mb = self.potential_bytes / (1024 * 1024)
        return {
            "copied_files": self.copied_files,
            "copied_mb": round(mb_copied, 2),
            "potential_files": self.potential_files,
            "potential_mb": round(potential_mb, 2),
            "percent_of_potential": round(pct, 2),
            "file_rate_per_s": round(self.copied_files / duration, 2),
            "data_rate_mb_per_s": round(mb_copied / duration, 2),
            "duration_s": round(duration, 2),
        }


def debug(msg: str):
    if PRINT_DEBUG:
        print(f"[DEBUG] {msg}")


def connect_ssh() -> Tuple[Any, Any]:
    """Stellt eine SSH/SFTP Verbindung her.

    Auth Reihenfolge:
      1. Private Key (wenn PRIVATE_KEY_PATH gesetzt)
      2. Passwort aus Konfiguration (SSH_PASSWORD)
      3. Interaktive Passwortabfrage (getpass) falls weder Key noch Passwort gesetzt
    """
    if paramiko is None:
        raise RuntimeError("Paramiko nicht verfügbar.")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    password_to_use = SSH_PASSWORD
    if not PRIVATE_KEY_PATH and password_to_use is None:
        try:
            password_to_use = getpass.getpass(f"SSH Passwort für {SSH_USER}@{SSH_HOST}: ")
        except Exception:
            print("Verdeckte Eingabe nicht möglich, Passwort wird mit Echo angezeigt:")
            password_to_use = input("Passwort: ")

    try:
        if PRIVATE_KEY_PATH:
            key = paramiko.RSAKey.from_private_key_file(PRIVATE_KEY_PATH)
            client.connect(SSH_HOST, port=SSH_PORT, username=SSH_USER, pkey=key, look_for_keys=False, allow_agent=False)
        else:
            client.connect(
                SSH_HOST,
                port=SSH_PORT,
                username=SSH_USER,
                password=password_to_use,
                look_for_keys=False,
                allow_agent=False,
            )
    except paramiko.AuthenticationException as e:
        raise RuntimeError(f"Authentifizierung fehlgeschlagen: {e}")
    except Exception:
        raise

    sftp = client.open_sftp()
    try:
        transport = client.get_transport()
        if transport and KEEPALIVE_INTERVAL > 0:
            transport.set_keepalive(KEEPALIVE_INTERVAL)
    except Exception:
        pass
    return client, sftp

def run_tar_stream(client: Any, stats: Stats, tasks: List[FileTask]):
    """Schneller Transfer via tar über SSH.
    Erwartet bereits vorab gescannte "tasks" (scan_remote wurde in main ausgeführt).
    Ablauf:
      1. Chunked Liste relativer Pfade verwenden (kein erneutes Listing)
      2. Remote tar (optional gzip) ausführen und Stream lokal entpacken
      3. Dateien schreiben, Stats aktualisieren (ohne doppelte Skip-Zählung)
    """
    if not tasks:
        return
    rel_paths = [t.relative_path for t in tasks]
    import tarfile, gzip
    CHUNK_SIZE = 2000
    global CURRENT_FILE
    for i in range(0, len(rel_paths), CHUNK_SIZE):
        chunk = rel_paths[i:i + CHUNK_SIZE]
        tar_flag = "cf -"
        cmd = f"cd {REMOTE_BASE_DIR} && tar {tar_flag} " + " ".join(chunk)
        if TAR_STREAM_COMPRESS:
            cmd += " | gzip -c"
        transport = client.get_transport()
        session = transport.open_session()
        session.exec_command(cmd)
        stream = session.makefile("rb")
        if TAR_STREAM_COMPRESS:
            stream = gzip.GzipFile(fileobj=stream)
        tar = tarfile.open(fileobj=stream, mode="r|")
        for member in tar:
            if not member.isreg():
                continue
            rel_path = member.name
            CURRENT_FILE = rel_path
            local_path = os.path.join(LOCAL_BASE_DIR, rel_path.replace('/', os.sep))
            ensure_local_dir(os.path.dirname(local_path))
            # Sollte normalerweise immer kopiert werden; erneuter Check nur zur Sicherheit (kein erneutes Hochzählen von skipped)
            if not should_copy(local_path, member.size):
                continue
            f = tar.extractfile(member)
            if f is None:
                continue
            with open(local_path, 'wb') as out:
                while True:
                    buf = f.read(1024 * 128)
                    if not buf:
                        break
                    out.write(buf)
            stats.copied_files += 1
            stats.copied_bytes += member.size
        tar.close()
        stream.close()
        session.close()

def run_rsync(stats: Stats):
    """Verwendet rsync über SSH für fehlende Dateien. Erwartet rsync auf Remote und lokal."""
    # rsync Befehl zusammenbauen
    compress_flag = "-z" if RSYNC_COMPRESS else ""
    delete_flag = ""  # optional
    # Filter nach DAYS_BACK: schwer direkt in rsync -> wir nutzen vorerst komplettes Verzeichnis
    cmd = (
        f"{RSYNC_PATH} -av {compress_flag} --ignore-existing "
        f"-e \"ssh -p {SSH_PORT}\" {SSH_USER}@{SSH_HOST}:{REMOTE_BASE_DIR.rstrip('/')} {LOCAL_BASE_DIR}".strip()
    )
    debug(f"Starte rsync: {cmd}")
    # Ausführen
    import subprocess
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    global CURRENT_FILE
    for line in proc.stdout:
        line = line.strip()
        if line.endswith('/'):
            continue
        if line and not line.startswith('sending incremental'):  # einfache Heuristik
            CURRENT_FILE = line
        if PRINT_DEBUG:
            print("[RSYNC] " + line)
    proc.wait()
    # Nachlauf: wir können Stats aktualisieren indem wir erneut scannen und Größen vergleichen
    _, sftp = connect_ssh()
    tasks = scan_remote(sftp, stats)
    sftp.close()
    # Kopierstatistiken approximieren (Annahme: alles was jetzt fehlt ist kopiert)
    # Diese einfache Methode wird nicht erneut schon kopierte Bytes addieren
    # Für Genauigkeit müsste rsync Ausgabe geparst werden -> ausgelassen für erste Version



def is_excluded(name: str) -> bool:
    lname = name.lower()
    for pat in EXCLUDE_PATTERNS:
        if pat.lower() in lname:
            return True
    return False


def scan_remote(sftp: Any, stats: Stats) -> List[FileTask]:
    cutoff = time.time() - DAYS_BACK * 86400

    tasks: List[FileTask] = []

    def walk(remote_dir: str, rel_prefix: str = ""):
        try:
            entries = sftp.listdir_attr(remote_dir)
        except IOError as e:
            debug(f"Kann Verzeichnis nicht lesen: {remote_dir} ({e})")
            return
        for entry in entries:
            name = entry.filename
            if is_excluded(name):
                continue
            mode = entry.st_mode
            remote_path = f"{remote_dir}/{name}" if not remote_dir.endswith('/') else f"{remote_dir}{name}"
            if stat.S_ISDIR(mode):
                if stat.S_ISLNK(mode) and not FOLLOW_SYMLINKS:
                    continue
                walk(remote_path, f"{rel_prefix}{name}/")
            elif stat.S_ISREG(mode):
                mtime = entry.st_mtime
                size = entry.st_size
                if mtime >= cutoff:
                    rel_path = f"{rel_prefix}{name}"
                    # Lokale Prüfung vor Aufnahme in Liste
                    local_path = os.path.join(LOCAL_BASE_DIR, rel_path.replace('/', os.sep))
                    take = True
                    if os.path.exists(local_path):
                        try:
                            lsize = os.path.getsize(local_path)
                            if abs(lsize - size) <= SIZE_TOLERANCE_BYTES or lsize >= size:
                                take = False
                                stats.skipped_existing_files += 1
                                stats.skipped_existing_bytes += size
                        except Exception:
                            pass
                    if take:
                        tasks.append(FileTask(remote_path=remote_path, relative_path=rel_path, size=size, mtime=mtime))
                        stats.potential_files += 1
                        stats.potential_bytes += size
            else:
                continue

    walk(REMOTE_BASE_DIR.rstrip('/'))
    return tasks


def file_in_use(sftp: Any, remote_path: str, initial_size: int) -> bool:
    try:
        time.sleep(SECONDS_STABILITY_CHECK)
        st = sftp.stat(remote_path)
        return st.st_size != initial_size
    except IOError:
        return False


def ensure_local_dir(path: str):
    os.makedirs(path, exist_ok=True)


def should_copy(local_path: str, remote_size: int) -> bool:
    if not os.path.exists(local_path):
        return True
    try:
        local_size = os.path.getsize(local_path)
    except OSError:
        return True
    # Kopieren nur wenn lokale Datei deutlich kleiner ist (Toleranz beachten)
    if local_size >= remote_size:
        return False
    if abs(local_size - remote_size) <= SIZE_TOLERANCE_BYTES:
        return False
    return True


def create_sftp_session() -> Any:
    """Erzeugt neue SFTP Session auf bestehender SSH Verbindung (Transport wird geteilt)."""
    # Diese Funktion erwartet, dass ein globaler Client existiert
    global _GLOBAL_SSH_CLIENT
    transport = _GLOBAL_SSH_CLIENT.get_transport()
    return paramiko.SFTPClient.from_transport(transport)


CURRENT_FILE = None  # global für Statusanzeige
_STOP_STATUS = False

def _format_status(stats: Stats) -> str:
    remaining_files = max(stats.potential_files - stats.copied_files, 0)
    pct_files = (stats.copied_files / stats.potential_files * 100) if stats.potential_files else 0.0
    duration = max(time.time() - stats.start_time, 0.001)
    data_mb = stats.copied_bytes / (1024*1024)
    rate_mb_s = data_mb / duration
    rate_files_s = stats.copied_files / duration
    current_name = os.path.basename(CURRENT_FILE) if CURRENT_FILE else "-"
    return (f"Datei: {current_name} | Kopiert: {stats.copied_files}/{stats.potential_files} ({pct_files:.2f}%) | "
            f"Verbleibend: {remaining_files} | Übersprungen: {stats.skipped_existing_files} | Daten: {data_mb:.2f} MB | "
            f"Rate: {rate_mb_s:.2f} MB/s | Dateien/s: {rate_files_s:.2f}")

def status_loop(stats: Stats):
    while not _STOP_STATUS:
        line = _format_status(stats)
        if USE_SINGLE_LINE_STATUS:
            # Carriage Return ohne neue Zeile
            print("\r" + line.ljust(140), end="", flush=True)
        else:
            print(line)
        time.sleep(STATUS_UPDATE_INTERVAL)
    # Abschluss: finale Zeile
    final = _format_status(stats)
    if USE_SINGLE_LINE_STATUS:
        print("\r" + final.ljust(140))
    else:
        print(final)

def worker(sftp: Any, q: 'queue.Queue[FileTask]', stats: Stats, lock: threading.Lock):
    while True:
        try:
            task = q.get(timeout=1)
        except queue.Empty:
            return
        remote_path = task.remote_path
        local_path = os.path.join(LOCAL_BASE_DIR, task.relative_path.replace('/', os.sep))
        local_dir = os.path.dirname(local_path)
        ensure_local_dir(local_dir)
        if not should_copy(local_path, task.size):
            q.task_done()
            continue
        if file_in_use(sftp, remote_path, task.size):
            debug(f"Übersprungen (in Benutzung): {remote_path}")
            q.task_done()
            continue
        def do_transfer():
            debug(f"Kopiere: {remote_path} -> {local_path} (Größe: {task.size/1024/1024:.2f} MB)")
            start_file = time.time()
            last_print = 0.0
            last_bytes = 0
            retry = 0
            current_sftp = sftp
            global CURRENT_FILE
            CURRENT_FILE = remote_path
            while retry <= MAX_RETRIES_PER_FILE:
                transferred_error = None
                try:
                    def progress_callback(transferred: int, total: int = task.size):
                        # Einzeldatei Fortschritt ausgeblendet für Single-Line Status
                        return
                    current_sftp.get(remote_path, local_path, callback=progress_callback)
                    break
                except Exception as e:
                    transferred_error = e
                    retry += 1
                    debug(f"Fehler Transfer Versuch {retry} für {remote_path}: {e}")
                    if "Garbage packet" in str(e):
                        try:
                            current_sftp.close()
                        except Exception:
                            pass
                        try:
                            current_sftp = create_sftp_session()
                            debug("Neue SFTP Session nach Garbage packet aufgebaut")
                        except Exception as reinit_e:
                            debug(f"Fehler beim Neuaufbau SFTP Session: {reinit_e}")
                    if retry <= MAX_RETRIES_PER_FILE:
                        time.sleep(2 * retry)
                if transferred_error and retry > MAX_RETRIES_PER_FILE:
                    raise transferred_error

            with lock:
                stats.copied_files += 1
                stats.copied_bytes += task.size
                pct_files = (stats.copied_files / stats.potential_files * 100) if stats.potential_files else 0.0
                pct_bytes = (stats.copied_bytes / stats.potential_bytes * 100) if stats.potential_bytes else 0.0
                duration = max(time.time() - stats.start_time, 0.001)
                current_rate_mb_s = (stats.copied_bytes / (1024 * 1024)) / duration
                if stats.copied_files % LOG_EVERY_N_FILES == 0 or stats.copied_files == stats.potential_files:
                    print(
                        f"Fortschritt: {stats.copied_files}/{stats.potential_files} Dateien "
                        f"({pct_files:.2f}%) | Volumen: {stats.copied_bytes / (1024*1024):.2f}/"
                        f"{stats.potential_bytes / (1024*1024):.2f} MB ({pct_bytes:.2f}%) | Gesamt Rate: {current_rate_mb_s:.2f} MB/s | "
                        f"Übersprungen (vorhanden): {stats.skipped_existing_files}"
                    )

        try:
            do_transfer()
        except Exception as e:
            debug(f"Fehler beim Kopieren {remote_path}: {e}\n{traceback.format_exc()}")
        finally:
            q.task_done()


def main():
    stats = Stats()
    start_wall = time.time()

    try:
        client, sftp = connect_ssh()
        # Globale Referenz für neue SFTP Sessions in Threads
        global _GLOBAL_SSH_CLIENT
        _GLOBAL_SSH_CLIENT = client
    except Exception as e:
        print(f"SSH Verbindung fehlgeschlagen: {e}")
        sys.exit(1)

    # Modusabhängige Vorbereitung
    if USE_RSYNC:
        # Einmaliges Listing nur für Anzeige
        _, temp_sftp = connect_ssh()
        scan_remote(temp_sftp, stats)
        temp_sftp.close()
        status_thread = threading.Thread(target=status_loop, args=(stats,), daemon=True)
        status_thread.start()
        print("Nutze rsync für Transfer ...")
        run_rsync(stats)
    elif USE_TAR_STREAM:
        # Listing einmal für tasks + Anzeige
        tasks = scan_remote(sftp, stats)
        print(f"Gefundene potentielle Dateien (tar): {stats.potential_files}")
        status_thread = threading.Thread(target=status_loop, args=(stats,), daemon=True)
        status_thread.start()
        print("Nutze tar Stream für Transfer ...")
        run_tar_stream(client, stats, tasks)
    else:
        # SFTP Standard
        tasks = scan_remote(sftp, stats)
        print(f"Gefundene potentielle Dateien: {stats.potential_files}")
        status_thread = threading.Thread(target=status_loop, args=(stats,), daemon=True)
        status_thread.start()
        q: 'queue.Queue[FileTask]' = queue.Queue()
        for t in tasks:
            q.put(t)
        lock = threading.Lock()
        threads = []
        for _ in range(max(1, MAX_PARALLEL_TRANSFERS)):
            thread_sftp = sftp if _ == 0 else create_sftp_session()
            th = threading.Thread(target=worker, args=(thread_sftp, q, stats, lock), daemon=True)
            th.start()
            threads.append(th)
        q.join()
        for th in threads:
            th.join(timeout=0.1)

    try:
        sftp.close()
        client.close()
    except Exception:
        pass

    # Status Loop stoppen
    global _STOP_STATUS
    _STOP_STATUS = True
    status_thread.join(timeout=2)

    results = stats.finalize()
    print("\nBackup abgeschlossen.")
    print(f"Dateien kopiert: {results['copied_files']} / {results['potential_files']} ({results['percent_of_potential']}%)")
    print(f"Volumen kopiert: {results['copied_mb']} MB von {results['potential_mb']} MB")
    print(f"Dauer: {results['duration_s']} s")
    print(f"Dateirate: {results['file_rate_per_s']} Dateien/s")
    print(f"Datenrate: {results['data_rate_mb_per_s']} MB/s")


if __name__ == "__main__":
    main()
