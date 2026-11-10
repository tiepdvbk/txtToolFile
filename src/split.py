"""Tách văn bản theo ngưỡng ký tự, giữ nguyên nội dung sau làm sạch."""
from pathlib import Path
import os
import tempfile


def split_text(content, max_chars, endings=".!?。！？", mode="after"):
    if max_chars < 1:
        raise ValueError("Số ký tự phải lớn hơn 0.")
    if mode not in ("after", "strict"):
        raise ValueError("Chế độ tách không hợp lệ.")
    start = 0
    while start < len(content):
        end = min(start + max_chars, len(content))
        if end < len(content):
            if mode == "after":
                while end < len(content) and content[end - 1] not in endings:
                    end += 1
            else:
                boundary = max((content.rfind(c, start, end) for c in endings), default=-1)
                if boundary >= start:
                    end = boundary + 1
        yield content[start:end]
        start = end


def split_file(input_file, output_dir, max_chars=285000, start_index=1,
               remove_chars='"*>“”', endings=".!?。！？", mode="after",
               encoding="utf-8-sig", overwrite=False):
    source, folder = Path(input_file), Path(output_dir)
    if not source.is_file():
        raise ValueError("File nguồn không tồn tại.")
    if start_index < 0:
        raise ValueError("Số thứ tự bắt đầu không được âm.")
    if max_chars < 1:
        raise ValueError("Số ký tự phải lớn hơn 0.")
    with source.open(encoding=encoding, newline="") as stream:
        content = stream.read()
    content = content.translate(str.maketrans("", "", remove_chars))
    if not content:
        raise ValueError("Nội dung trống sau khi làm sạch.")
    folder.mkdir(parents=True, exist_ok=True)
    targets = []
    # Chuẩn bị toàn bộ file trước khi công bố kết quả.
    with tempfile.TemporaryDirectory(dir=folder, prefix=".textfile-") as staging:
        for index, part in enumerate(split_text(content, max_chars, endings, mode), start_index):
            target = folder / f"{index}.txt"
            if target.resolve() == source.resolve():
                raise ValueError("File đầu ra trùng file nguồn. Hãy chọn thư mục khác.")
            if target.exists() and not overwrite:
                raise FileExistsError(f"{target.name} đã tồn tại. Đổi thư mục hoặc bật ghi đè.")
            staged = Path(staging) / target.name
            with staged.open("w", encoding="utf-8", newline="") as stream:
                stream.write(part)
            targets.append((staged, target))
        for staged, target in targets:
            if overwrite:
                os.replace(staged, target)
            else:
                os.rename(staged, target)
    return len(targets), str(folder)
