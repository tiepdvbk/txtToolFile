"""Gộp các file văn bản có tên là số theo thứ tự tăng dần."""
from pathlib import Path
import os
import re
import tempfile


def chapter_key(path):
    match = re.fullmatch(r"([0-9]+)(?:\s*-\s*([0-9]+))?", path.stem)
    if not match:
        return None
    start = int(match[1])
    end = int(match[2]) if match[2] else start
    if end < start:
        raise ValueError(f"Khoảng chương bị đảo ngược: {path.name}")
    return start, end, path.name


def chapter_files(input_dir, exclude=None):
    """Return eligible chapters in the same order used for merging."""
    folder = Path(input_dir)
    if not folder.is_dir():
        raise ValueError("Thư mục nguồn không tồn tại.")
    excluded = Path(exclude).resolve() if exclude is not None else None
    entries = []
    for path in folder.iterdir():
        if path.is_file() and path.suffix.lower() == ".txt" and path.resolve() != excluded:
            key = chapter_key(path)
            if key is not None:
                entries.append((key, path))
    return [path for key, path in sorted(entries, key=lambda item: item[0])]


def merge_files(input_dir, output_file, separator="\n", encoding="utf-8-sig", overwrite=False):
    folder, target = Path(input_dir), Path(output_file)
    files = chapter_files(folder, exclude=target)
    if not files:
        child_folders = []
        for child in folder.iterdir():
            if child.is_dir() and any(
                item.is_file() and item.suffix.lower() == ".txt" and chapter_key(item) is not None
                for item in child.iterdir()
            ):
                child_folders.append(child.name)
        message = (
            "Không tìm thấy file chương ngay trong thư mục đã chọn. "
            "Tên hợp lệ gồm 1.txt, 2.txt, 1-2.txt, 1-3.txt, 1-5.txt… "
            "Hãy chọn đúng thư mục chứa trực tiếp các file .txt."
        )
        if child_folders:
            message += " Có file chương trong thư mục con: " + ", ".join(child_folders) + "."
        raise ValueError(message)
    if target.exists() and not overwrite:
        raise FileExistsError("File đích đã tồn tại. Đổi tên hoặc bật cho phép ghi đè.")
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as out:
            for index, path in enumerate(files):
                if index:
                    out.write(separator)
                with path.open(encoding=encoding, newline="") as source:
                    while chunk := source.read(1024 * 1024):
                        out.write(chunk)
        if overwrite:
            os.replace(temp, target)
        else:
            os.rename(temp, target)  # Windows: không ghi đè file vừa xuất hiện.
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return len(files), str(target)
