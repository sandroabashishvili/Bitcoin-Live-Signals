from __future__ import annotations


def fmt_ts(seconds_total: float) -> str:
    ms = int(round((seconds_total - int(seconds_total)) * 1000))
    s0 = int(seconds_total) % 60
    m0 = (int(seconds_total) // 60) % 60
    h0 = int(seconds_total) // 3600
    return f"{h0:02d}:{m0:02d}:{s0:02d},{ms:03d}"


def write_srt(path: str, segments: list[tuple[float, float, str]]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for idx, (start, end, text) in enumerate(segments, start=1):
            handle.write(f"{idx}\n{fmt_ts(start)} --> {fmt_ts(end)}\n{text.strip()}\n\n")
