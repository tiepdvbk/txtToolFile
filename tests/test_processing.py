import tempfile
import unittest
from pathlib import Path
from src.merge import merge_files
from src.split import split_file, split_text


class ProcessingTests(unittest.TestCase):
    def test_merge_ranges_over_5000_chapters(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            starts = list(range(1, 6001, 3))
            for start in reversed(starts):
                (folder / f"{start}-{start + 2}.txt").write_text(str(start), encoding="utf-8")
            output = folder / "all.txt"
            self.assertEqual(merge_files(folder, output)[0], 2000)
            self.assertEqual(output.read_text(encoding="utf-8").splitlines(), [str(n) for n in starts])

    def test_merge_mixed_ranges_and_numbers(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            expected = ["001-003", "4-6", "7", "8-9", "10-12", "100-102", "1000-1002", "5000-5002"]
            for name in reversed(expected):
                (folder / f"{name}.txt").write_text(name, encoding="utf-8")
            output = folder / "all.txt"
            merge_files(folder, output)
            self.assertEqual(output.read_text(encoding="utf-8").splitlines(), expected)

    def test_merge_numeric_order_and_exclusions(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            for name, text in [("10.txt", "mười"), ("2.txt", "hai"), ("1.txt", "một"), ("notes.txt", "skip"), ("3.csv", "skip")]:
                (folder / name).write_text(text, encoding="utf-8-sig")
            (folder / "4.txt").mkdir()
            output = folder / "all.txt"
            self.assertEqual(merge_files(folder, output)[0], 3)
            self.assertEqual(output.read_text(encoding="utf-8"), "một\nhai\nmười")
            with self.assertRaises(FileExistsError):
                merge_files(folder, output)

    def test_splitting_preserves_every_character(self):
        for text in [" a. b! c？\r\n cuối ", "x" * 41, "a", "", "1234.5678!"]:
            for mode in ["after", "strict"]:
                for size in [1, 4, 100]:
                    parts = list(split_text(text, size, mode=mode))
                    self.assertEqual("".join(parts), text)
                    if mode == "strict":
                        self.assertTrue(all(len(part) <= size for part in parts))
        self.assertEqual(list(split_text("abcd.ef", 3)), ["abcd.", "ef"])

    def test_cleaning_numbering_and_conflict(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            source = folder / "all.txt"
            source.write_text('“Xin” *>chào. Bạn!', encoding="utf-8")
            dest = folder / "parts"
            count, _ = split_file(source, dest, max_chars=5, start_index=8)
            actual = "".join((dest / f"{i}.txt").read_text(encoding="utf-8") for i in range(8, 8 + count))
            self.assertEqual(actual, "Xin chào. Bạn!")
            with self.assertRaises(FileExistsError):
                split_file(source, dest, max_chars=5, start_index=8)
            self.assertFalse(list(dest.glob(".textfile-*")))

    def test_source_protection(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "1.txt"
            source.write_text("original", encoding="utf-8")
            with self.assertRaises(ValueError):
                split_file(source, root, overwrite=True)
            self.assertEqual(source.read_text(), "original")


if __name__ == "__main__":
    unittest.main()
