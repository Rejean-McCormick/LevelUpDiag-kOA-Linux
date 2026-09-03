from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

SECRET_VALUE_RE = re.compile(
    r"(?i)(password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)"
    r"(\s*[:=]\s*)([^\s,;\]\[}\{]{4,})"
)
JSON_SECRET_RE = re.compile(
    r'''(?i)(["'](?:password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)["']\s*:\s*["'])([^"']{4,})(["'])'''
)
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def redact(text: str, replacement="<REDACTED>"):
    text = JSON_SECRET_RE.sub(lambda m: f"{m.group(1)}{replacement}{m.group(3)}", text)
    text = SECRET_VALUE_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}{replacement}", text)
    text = BEARER_RE.sub(f"Bearer {replacement}", text)
    return text


def tail_text(text: str, limit_bytes: int):
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= limit_bytes:
        return text
    return "<truncated>\n" + raw[-limit_bytes:].decode("utf-8", errors="replace")
