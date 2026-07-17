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
