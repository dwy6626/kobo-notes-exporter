# `export-pr` Shortcut Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `uv run export-pr` as a safe, argument-preserving shortcut to `scripts/export_to_notes_repo.sh`.

**Architecture:** A focused Python console-entry-point module will locate the repository Bash script and execute it as a child process. The existing Bash script remains the only implementation of the Git, GitHub, and Kobo export workflow; the Python layer only delegates arguments and propagates the exit status.

**Tech Stack:** Python 3.14+, standard-library `pathlib`/`subprocess`, setuptools console scripts, uv, Bash, `unittest`/`unittest.mock`.

## Global Constraints

- Code identifiers and code comments must be written in English.
- README content must be written in Traditional Chinese.
- The project targets Kobo readers mounted on macOS, for example under `/Volumes`.
- Do not run `uv run export-pr` as a smoke test because it intentionally performs Git and GitHub operations.
- Do not add a dependency; the wrapper only needs the Python standard library.

## File Map

- Create: `src/kobo_notes_exporter/export_pr.py` — locate and run the existing Bash workflow while forwarding arguments and returning its exit status.
- Create: `tests/test_export_pr.py` — verify the console-script configuration and delegated command without executing the real workflow.
- Modify: `pyproject.toml` — register the `export-pr` console script.
- Modify: `README.md` — document the shortcut in Traditional Chinese.

---

### Task 1: Add and verify the `export-pr` entry point

**Files:**
- Create: `tests/test_export_pr.py`
- Create: `src/kobo_notes_exporter/export_pr.py`
- Modify: `pyproject.toml:14-16`

**Interfaces:**
- Consumes: repository script `scripts/export_to_notes_repo.sh`; optional CLI arguments from `sys.argv[1:]`.
- Produces: `kobo_notes_exporter.export_pr.main(argv: Sequence[str] | None = None) -> int`; console command `export-pr = "kobo_notes_exporter.export_pr:main"`.

- [x] **Step 1: Write failing configuration and delegation tests**

Create `tests/test_export_pr.py`:

```python
from pathlib import Path
from subprocess import CompletedProcess
import importlib
import tomllib
import unittest
from unittest.mock import patch


class ExportPrTests(unittest.TestCase):
    def import_export_pr(self):
        try:
            return importlib.import_module("kobo_notes_exporter.export_pr")
        except ModuleNotFoundError as error:
            self.fail(f"export-pr module is missing: {error}")

    def test_pyproject_exposes_export_pr_shortcut(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        with (project_root / "pyproject.toml").open("rb") as pyproject_file:
            pyproject = tomllib.load(pyproject_file)

        self.assertEqual(
            pyproject["project"]["scripts"].get("export-pr"),
            "kobo_notes_exporter.export_pr:main",
        )

    def test_main_runs_repository_script_with_forwarded_arguments(self) -> None:
        export_pr = self.import_export_pr()

        with (
            patch.object(export_pr.subprocess, "run") as run,
            patch.object(
                export_pr.sys,
                "argv",
                ["export-pr", "--device-root", "/Volumes/KOBOeReader"],
            ),
        ):
            run.return_value = CompletedProcess(args=[], returncode=0)
            exit_code = export_pr.main()

        expected_script = (
            Path(export_pr.__file__).resolve().parents[2]
            / "scripts"
            / "export_to_notes_repo.sh"
        )
        run.assert_called_once_with(
            [
                "bash",
                str(expected_script),
                "--device-root",
                "/Volumes/KOBOeReader",
            ],
            check=False,
        )
        self.assertEqual(exit_code, 0)

    def test_main_propagates_script_exit_code(self) -> None:
        export_pr = self.import_export_pr()

        with patch.object(export_pr.subprocess, "run") as run:
            run.return_value = CompletedProcess(args=[], returncode=17)
            exit_code = export_pr.main([])

        self.assertEqual(exit_code, 17)


if __name__ == "__main__":
    unittest.main()
```

- [x] **Step 2: Run the focused tests to verify the red state**

Run:

```bash
rtk uv run python -m unittest tests.test_export_pr
```

Expected: 3 assertion failures: the console-script value is `None`, and the two behavior tests report that the `export-pr` module is missing.

- [x] **Step 3: Implement the minimal delegating module**

Create `src/kobo_notes_exporter/export_pr.py`:

```python
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
```

Add this entry under `[project.scripts]` in `pyproject.toml`:

```toml
export-pr = "kobo_notes_exporter.export_pr:main"
```

- [x] **Step 4: Run focused tests to verify the green state**

Run:

```bash
rtk uv run python -m unittest tests.test_export_pr
```

Expected: `Ran 3 tests` followed by `OK`; no Git, GitHub, Kobo-device, or notes-repository operation occurs because `subprocess.run` is mocked.

- [x] **Step 5: Verify uv installed the console entry point without running it**

Run:

```bash
rtk uv run python -c "from importlib.metadata import entry_points; assert entry_points(group='console_scripts', name='export-pr')"
```

Expected: exit status `0` with no output. Do not invoke `uv run export-pr` during automated validation.

- [x] **Step 6: Commit the entry point and tests**

```bash
rtk git add pyproject.toml src/kobo_notes_exporter/export_pr.py tests/test_export_pr.py
rtk git commit -m "Add export-pr uv shortcut"
```

### Task 2: Document and regression-test the shortcut

**Files:**
- Modify: `README.md:39-78`
- Test: `tests/test_export_pr.py`

**Interfaces:**
- Consumes: console command `uv run export-pr` produced by Task 1.
- Produces: Traditional Chinese usage documentation; no new code interface.

- [x] **Step 1: Add the shortcut usage to README**

Insert this section after the `## 使用方式` introduction and before the numbered direct-export examples:

````markdown
### 匯出到 notes repo 並建立 PR

執行 `scripts/export_to_notes_repo.sh` 的短指令：

```bash
uv run export-pr
```

需要指定 Kobo 裝置時，可直接傳入匯出參數：

```bash
uv run export-pr --device-root /Volumes/KOBOeReader
```

此流程會操作相鄰的 `kobo-notes` repository，並建立 branch、commit、push 與 GitHub pull request。執行前請確認 working tree 乾淨且 GitHub CLI 已登入。
````

- [x] **Step 2: Run the complete test suite**

Run:

```bash
rtk uv run python -m unittest discover -s tests
```

Expected: all existing tests plus the 3 new `ExportPrTests` pass and the command ends with `OK`.

- [x] **Step 3: Check formatting and review the final diff**

Run:

```bash
rtk git diff --check
rtk git diff -- pyproject.toml src/kobo_notes_exporter/export_pr.py tests/test_export_pr.py README.md
```

Expected: `git diff --check` exits `0` without output; the diff contains only the shortcut wrapper, its registration/tests, and Traditional Chinese documentation.

- [x] **Step 4: Commit the documentation**

```bash
rtk git add README.md
rtk git commit -m "Document export-pr shortcut"
```
