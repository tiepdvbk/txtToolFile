import tempfile
import unittest
from pathlib import Path

from app import DEFAULTS
from src.project import discover_project, execute_project, infer_root


class ProjectTests(unittest.TestCase):
    def settings(self, **overrides):
        return dict(DEFAULTS, max_chars="8", **overrides)

    def story(self, root, name="V1", encoding="utf-8"):
        folder = root / name
        folder.mkdir()
        (folder / "10-11.txt").write_text('“Cuối”! ', encoding=encoding)
        (folder / "2.txt").write_text("Đầu. ", encoding=encoding)
        return folder

    def test_case_insensitive_folders_and_auto_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.story(root)
            self.story(root, "RAW")
            (root / "V2").mkdir()
            project = discover_project(str(root))
            self.assertEqual(project.source.path, source)
            self.assertEqual(project.source.count, 2)
            self.assertEqual(project.source.first, "2.txt")
            self.assertEqual(project.merged, source / "all.txt")
            self.assertEqual(project.output, root / "V2")
            self.assertEqual(discover_project(str(root), "raw").source.name, "RAW")

    def test_missing_output_and_raw_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "v1").mkdir()
            source = self.story(root, "raw")
            project = discover_project(str(root))
            self.assertEqual(project.source.path, source)
            self.assertEqual(project.output, root / "v2")
            self.assertEqual(project.output_count, 0)
            self.assertFalse(project.output.exists())
            self.assertEqual(discover_project(str(root), "v1").source.count, 0)

    def test_pipeline_preserves_sources_and_sorts_and_cleans(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.story(root, encoding="utf-16")
            originals = {p.name: p.read_bytes() for p in source.iterdir()}
            project = discover_project(str(root))
            result = execute_project(project, "pipeline", self.settings(encoding="utf-16"))
            merged = project.merged.read_text(encoding="utf-8")
            self.assertEqual(merged, 'Đầu. \n\n“Cuối”! ')
            actual = "".join((project.output / f"{i}.txt").read_text(encoding="utf-8")
                             for i in range(1, result["parts"] + 1))
            self.assertEqual(actual, "Đầu. \n\nCuối! ")
            self.assertEqual(result["chapters"], 2)
            for name, content in originals.items():
                self.assertEqual((source / name).read_bytes(), content)
            self.assertFalse(list(root.glob(".textfile-work-*")))

    def test_conflict_does_not_publish_merge_or_partial_parts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.story(root)
            project = discover_project(str(root))
            project.output.mkdir()
            existing = project.output / "1.txt"
            existing.write_text("old result", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                execute_project(project, "pipeline", self.settings())
            self.assertFalse(project.merged.exists())
            self.assertEqual(existing.read_text(encoding="utf-8"), "old result")
            self.assertEqual(list(project.output.iterdir()), [existing])
            self.assertFalse(list(root.glob(".textfile-work-*")))

    def test_overwrite_retains_unrelated_files_and_old_extra_parts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.story(root)
            project = discover_project(str(root))
            project.output.mkdir()
            for name in ("1.txt", "99.txt", "1.mp3"):
                (project.output / name).write_bytes(b"old")
            project.merged.write_text("old merge", encoding="utf-8")
            execute_project(project, "pipeline", self.settings(overwrite=True))
            self.assertNotEqual((project.output / "1.txt").read_bytes(), b"old")
            self.assertEqual((project.output / "99.txt").read_bytes(), b"old")
            self.assertEqual((project.output / "1.mp3").read_bytes(), b"old")

    def test_merge_then_split_reads_generated_utf8(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.story(root, encoding="utf-16")
            project = discover_project(str(root))
            settings = self.settings(encoding="utf-16")
            execute_project(project, "merge", settings)
            result = execute_project(project, "split", settings)
            self.assertGreater(result["parts"], 0)

    def test_root_chapters_and_invalid_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "1.txt").write_text("Direct.", encoding="utf-8")
            project = discover_project(str(root))
            self.assertEqual(project.source.name, ".")
            self.assertEqual(project.merged, root / "all.txt")
            with self.assertRaises(ValueError):
                discover_project(str(root / "missing"))
            with self.assertRaises(ValueError):
                discover_project("")

    def test_legacy_config_infers_parent(self):
        base = Path("stories") / "Truyện"
        self.assertEqual(infer_root({"merge_input": str(base / "V1")}), str(base))
        self.assertEqual(infer_root({"split_input": str(base / "raw" / "all.txt")}), str(base))
        self.assertEqual(infer_root({"split_output": str(base / "v2")}), str(base))
        self.assertEqual(infer_root({"root_folder": "chosen", "merge_input": "old/v1"}), "chosen")


if __name__ == "__main__":
    unittest.main()
