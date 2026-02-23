#!/usr/bin/env python3
"""
LinPos UDP listener:
- Listens on a configured IP/port (UDP)
- Extracts LinPos frames (DLE STX ... DLE ETX)
- Unescapes DLE (0x10 doubled inside payload)
- Verifies CRC (XOR over payload fields Distance..SDMU inclusive)
- Decodes fields (big-endian) and appends rows to a CSV file

No CLI arguments; configure everything in CONFIG below.
"""

import csv
import os
import socket
import struct
import time
from typing import List, Optional

# =========================
# CONFIG (edit me)
# =========================
CONFIG = {
    "listen_ip": "127.0.0.1",
    "listen_port": 45045,
    "csv_path": "linpos_log_replay20260202.csv",
    "flush_every_n_rows": 1,  # 1 = flush each row (safer), higher = faster
    "print_each_packet": False,
}

DLE = 0x10
STX = 0x02
ETX = 0x03

FRAME_START = bytes([DLE, STX])
FRAME_END = bytes([DLE, ETX])

# Payload lengths (after unescape), including CRC byte at the end
PAYLOAD_NOCRC_LEN = 28
PAYLOAD_WITH_CRC_LEN = 29

FILLER_EXPECTED = bytes.fromhex("0009e1100b00841a")


def _extract_frames(datagram: bytes) -> List[bytes]:
    """Extract all frames from one UDP datagram."""
    frames = []
    i = 0
    while True:
        s = datagram.find(FRAME_START, i)
        if s < 0:
            break
        e = datagram.find(FRAME_END, s + len(FRAME_START))
        if e < 0:
            break
        frames.append(datagram[s : e + len(FRAME_END)])
        i = e + len(FRAME_END)
    return frames


def _unescape_dle(payload_escaped: bytes) -> bytes:
    """
    Reverse escaping:
    - Sender duplicates any 0x10 byte in the payload stream.
    - Receiver collapses doubled 0x10 back to single 0x10.
    """
    out = bytearray()
    i = 0
    n = len(payload_escaped)
    while i < n:
        b = payload_escaped[i]
        if b == DLE and i + 1 < n and payload_escaped[i + 1] == DLE:
            out.append(DLE)
            i += 2
            continue
        out.append(b)
        i += 1
    return bytes(out)


def _xor_crc(data: bytes) -> int:
    """Compute XOR CRC over the given bytes."""
    crc = 0
    for b in data:
        crc ^= b
    return crc & 0xFF


def _decode_linpos_frame(frame: bytes) -> Optional[dict]:
    """Decode a full frame (including DLE STX ... DLE ETX)."""
    if not (frame.startswith(FRAME_START) and frame.endswith(FRAME_END)):
        return None

    payload_escaped = frame[len(FRAME_START) : -len(FRAME_END)]
    payload = _unescape_dle(payload_escaped)

    if len(payload) != PAYLOAD_WITH_CRC_LEN:
        return None

    payload_nocrc = payload[:PAYLOAD_NOCRC_LEN]
    crc_rx = payload[PAYLOAD_NOCRC_LEN]
    crc_calc = _xor_crc(payload_nocrc)
    crc_ok = (crc_calc == crc_rx)

    try:
        # Big-endian decoding per spec
        dist_cm = struct.unpack(">i", payload_nocrc[0:4])[0]         # signed 32
        dist_err_cm = struct.unpack(">I", payload_nocrc[4:8])[0]     # unsigned 32
        speed_cm_s = struct.unpack(">h", payload_nocrc[8:10])[0]     # signed 16
        time_0_1ms = struct.unpack(">I", payload_nocrc[10:14])[0]    # unsigned 32
        time_err = payload_nocrc[14]                                 # uint8
        seq = payload_nocrc[15]                                      # uint8
        filler = payload_nocrc[16:24]                                # 8 bytes
        sdmudist_cm = struct.unpack(">I", payload_nocrc[24:28])[0]   # unsigned 32
    except Exception:
        return None

    return {
        "DISTANCE": dist_cm,
        "DISTANCE_ERROR": dist_err_cm,
        "SPEED": speed_cm_s,
        "TIME": time_0_1ms,
        "TIME_ERROR": time_err,
        "SEQUENCE_NUMBER": seq,
        "FILLER": filler.hex(),
        "SDMU_DISTANCE": sdmudist_cm,
        "crc_ok": crc_ok,
    }


def _ensure_csv_with_header(csv_path: str, header: List[str]) -> None:
    """Create CSV file with header if it doesn't exist or is empty."""
    needs_header = (not os.path.exists(csv_path)) or (os.path.getsize(csv_path) == 0)
    if needs_header:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)


def main() -> None:
    listen_ip = CONFIG["listen_ip"]
    listen_port = int(CONFIG["listen_port"])
    csv_path = CONFIG["csv_path"]
    flush_every = max(1, int(CONFIG["flush_every_n_rows"]))
    print_each = bool(CONFIG["print_each_packet"])

    # Requested header (exact order/names)
    header = [
        "SYSTEM_TIMESTAMP",
        "MEASUREMENT_TIMESTAMP",
        "DISTANCE",
        "DISTANCE_ERROR",
        "SPEED",
        "TIME",
        "TIME_ERROR",
        "SEQUENCE_NUMBER",
        "FILLER",
        "SDMU_DISTANCE",
    ]
    _ensure_csv_with_header(csv_path, header)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((listen_ip, listen_port))

    print(f"Listening UDP on {listen_ip}:{listen_port} -> logging to {csv_path}")

    rows_since_flush = 0
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        while True:
            datagram, _addr = sock.recvfrom(65535)

            frames = _extract_frames(datagram)
            if not frames:
                continue

            # SYSTEM_TIMESTAMP: wall-clock seconds since epoch (float)
            system_ts = time.time()

            for frame in frames:
                decoded = _decode_linpos_frame(frame)
                if decoded is None:
                    continue

                # MEASUREMENT_TIMESTAMP: derived from TIME field (0.1ms ticks -> seconds)
                meas_ts_s = decoded["TIME"] * 1e-4

                row = [
                    f"{system_ts:.6f}",
                    f"{meas_ts_s:.6f}",
                    decoded["DISTANCE"],
                    decoded["DISTANCE_ERROR"],
                    decoded["SPEED"],
                    decoded["TIME"],
                    decoded["TIME_ERROR"],
                    decoded["SEQUENCE_NUMBER"],
                    decoded["FILLER"],
                    decoded["SDMU_DISTANCE"],
                ]
                writer.writerow(row)
                rows_since_flush += 1

                if print_each:
                    print(
                        f"SYSTEM={system_ts:.6f} MEAS={meas_ts_s:.6f} "
                        f"D={decoded['DISTANCE']}cm V={decoded['SPEED']}cm/s "
                        f"SEQ={decoded['SEQUENCE_NUMBER']} CRC_OK={decoded['crc_ok']}"
                    )

                if rows_since_flush >= flush_every:
                    f.flush()
                    rows_since_flush = 0


if __name__ == "__main__":
    main()
