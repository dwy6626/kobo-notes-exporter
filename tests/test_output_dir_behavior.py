from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from kobo_notes_exporter.cli import parse_args, prepare_output_dir


class OutputDirBehaviorTests(unittest.TestCase):
    def test_parse_args_default_out_exists_is_raise(self) -> None:
        args = parse_args([])
        self.assertEqual(args.out_exists, "raise")

    def test_prepare_output_dir_raise_when_existing_path(self) -> None:
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "existing"
            out_dir.mkdir()
            with self.assertRaises(SystemExit):
                prepare_output_dir(out_dir, "raise")

    def test_prepare_output_dir_overwrite_keeps_existing_directory(self) -> None:
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "existing"
            out_dir.mkdir()
            sentinel = out_dir / "sentinel.txt"
            sentinel.write_text("keep", encoding="utf-8")

            prepare_output_dir(out_dir, "overwrite")

            self.assertTrue(out_dir.is_dir())
            self.assertTrue(sentinel.exists())

    def test_prepare_output_dir_rename_moves_existing_directory(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "existing"
            out_dir.mkdir()
            sentinel = out_dir / "sentinel.txt"
            sentinel.write_text("move", encoding="utf-8")

            prepare_output_dir(out_dir, "rename")

            self.assertTrue(out_dir.is_dir())
            self.assertFalse((out_dir / "sentinel.txt").exists())
            backups = sorted(root.glob("existing.bak.*"))
            self.assertEqual(len(backups), 1)
            self.assertTrue((backups[0] / "sentinel.txt").exists())


if __name__ == "__main__":
    unittest.main()
