"""Discover a story project and run its automatic text workflow."""
from dataclasses import dataclass
import os
from pathlib import Path
import tempfile

from .merge import chapter_files, merge_files
from .split import split_file

SEPARATORS = {"Một dòng mới": "\n", "Một dòng trống": "\n\n", "Không thêm": ""}
SOURCE_NAMES = ("v1", "raw", "raw_tach")


@dataclass(frozen=True)
class Source:
    name: str
    path: Path
    count: int
    first: str = ""
    last: str = ""
    error: str = ""


@dataclass(frozen=True)
class Project:
    root: Path
    sources: tuple
    source: Source
    merged: Path
    output: Path
    output_count: int


def infer_root(settings):
    """Migrate the old four-path configuration without touching story files."""
    root_value = settings.get("root_folder", "")
    if isinstance(root_value, str) and root_value.strip():
        return root_value
    for key in ("merge_input", "split_input", "split_output"):
        value = settings.get(key, "")
        if isinstance(value, str) and value.strip():
            path = Path(value)
            if key == "split_input":
                path = path.parent
            if path.name.casefold() in (*SOURCE_NAMES, "v2"):
                path = path.parent
            return str(path)
    return ""


def inspect_source(name, path):
    try:
        files = chapter_files(path)
        return Source(name, path, len(files), files[0].name if files else "",
                      files[-1].name if files else "")
    except (ValueError, OSError) as exc:
        return Source(name, path, 0, error=str(exc))


def discover_project(root_folder, preferred=""):
    value = root_folder.strip().strip('"')
    if not value:
        raise ValueError("Chọn thư mục gốc của truyện để bắt đầu.")
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Thư mục gốc không tồn tại hoặc không truy cập được.")
    folders = {p.name.casefold(): p for p in root.iterdir() if p.is_dir()}
    sources = [inspect_source(folders[name].name, folders[name])
               for name in SOURCE_NAMES if name in folders]
    direct = inspect_source(".", root)
    if direct.count or (root / "all.txt").is_file():
        sources.append(direct)
    if not sources:
        sources.append(Source("v1", root / "v1", 0,
                              error="Chưa tìm thấy v1, raw hoặc raw_tach trong thư mục gốc."))
    selected = next((s for s in sources if s.name.casefold() == preferred.casefold()), None)
    if selected is None:
        selected = next((s for s in sources if s.count), sources[0])
    output = folders.get("v2", root / "v2")
    output_count = sum(p.is_file() and p.suffix.lower() == ".txt" for p in output.iterdir()) if output.is_dir() else 0
    return Project(root, tuple(sources), selected, selected.path / "all.txt", output, output_count)


def execute_project(project, operation, settings, notify=lambda message: None):
    if operation not in ("pipeline", "merge", "split"):
        raise ValueError("Tác vụ không hợp lệ.")
    if project.source.path.resolve() == project.output.resolve():
        raise ValueError("Nguồn và thư mục tách không được trùng nhau.")
    if operation != "merge" and project.output.exists() and not project.output.is_dir():
        raise ValueError(f"Đích phải là thư mục: {project.output}")
    overwrite = settings["overwrite"]
    merge_options = dict(separator=SEPARATORS[settings["separator"]], encoding=settings["encoding"])
    if operation == "merge":
        notify("Đang gộp các file chương…")
        count, _ = merge_files(project.source.path, project.merged, overwrite=overwrite, **merge_options)
        return dict(chapters=count, parts=0, output=str(project.merged))
    split_options = dict(max_chars=int(settings["max_chars"]), start_index=int(settings["start_index"]),
                         remove_chars=settings["remove_chars"], endings=settings["endings"],
                         mode="strict" if settings["mode"] == "Giới hạn cứng" else "after")
    if operation == "split":
        notify("Đang tách all.txt thành các phần…")
        count, output = split_file(project.merged, project.output, encoding="utf-8-sig",
                                   overwrite=overwrite, **split_options)
        return dict(chapters=0, parts=count, output=output)
    # Prepare both steps before replacing any existing result. A split conflict
    # must not leave a newly overwritten all.txt behind.
    with tempfile.TemporaryDirectory(dir=project.root, prefix=".textfile-work-") as staging:
        staging = Path(staging)
        merged = staging / "all.txt"
        notify("Bước 1/2 · Đang gộp các file chương…")
        chapters, _ = merge_files(project.source.path, merged, **merge_options)
        notify("Bước 2/2 · Đang tách văn bản…")
        parts, _ = split_file(merged, staging / "parts", encoding="utf-8", **split_options)
        targets = [(merged, project.merged)] + [
            (staging / "parts" / f"{i}.txt", project.output / f"{i}.txt")
            for i in range(split_options["start_index"], split_options["start_index"] + parts)]
        for _, target in targets:
            if target.exists() and (not overwrite or not target.is_file()):
                raise FileExistsError(f"Đích đã tồn tại: {target}\nBật ghi đè file trùng tên nếu cần thay kết quả cũ.")
        notify("Đang lưu kết quả…")
        for parent in {target.parent for _, target in targets}:
            parent.mkdir(parents=True, exist_ok=True)
        for staged, target in targets:
            if overwrite:
                os.replace(staged, target)
            else:
                os.rename(staged, target)
    return dict(chapters=chapters, parts=parts, output=str(project.output))
