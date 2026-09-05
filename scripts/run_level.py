"""Compatibility launcher for Koali Control Panel 2.4.x.

New integrations should invoke ``python levelupdiag.py run <selection>`` directly.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from levelupdiag_core.cli import main as levelupdiag_main


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    # Legacy --console only controlled presentation; v2 CLI always prints a summary.
    raw = [item for item in raw if item != "--console"]
    if "--campaign" in raw:
        idx = raw.index("--campaign")
        try:
            selection = raw[idx + 1]
        except IndexError:
            print("LevelUpDiag compatibility launcher: --campaign requires a value", file=sys.stderr)
            return 64
        tail = raw[:idx] + raw[idx + 2:]
        return levelupdiag_main(["run", selection, *tail])
    if "--all" in raw:
        tail = [item for item in raw if item != "--all"]
        return levelupdiag_main(["run", "release", *tail])
    selection = raw[0] if raw else "stabilization"
    tail = raw[1:] if raw else []
    return levelupdiag_main(["run", selection, *tail])


if __name__ == "__main__":
    raise SystemExit(main())
