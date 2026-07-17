from collections.abc import Sequence
from pathlib import Path
import subprocess
import sys


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    project_root = Path(__file__).resolve().parents[2]
    script = project_root / "scripts" / "export_to_notes_repo.sh"
    completed = subprocess.run(
        ["bash", str(script), *arguments],
        check=False,
    )
    return completed.returncode
