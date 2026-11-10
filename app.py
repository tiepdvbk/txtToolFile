"""TextFile: one project folder, automatic destinations."""
import codecs
import json
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from src.project import SEPARATORS, discover_project, execute_project, infer_root

ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
CONFIG = ROOT / "config.json"
DEFAULTS = dict(root_folder="", source_folder="", operation="pipeline", separator="Một dòng trống",
                max_chars="285000", start_index="1", remove_chars='"*>“”', endings=".!?。！？",
                mode="Sau dấu kết thúc câu", encoding="utf-8-sig", overwrite=False)
BG, INK, MUTED, BLUE, BORDER, NAV = "#f4f6fa", "#17243c", "#728096", "#4263eb", "#e2e7f0", "#142239"
OPERATIONS = {
    "pipeline": ("Gộp & tách", "Từ các file chương đến văn bản sẵn dùng, chỉ trong một lần chạy.", "Gộp & tách ngay"),
    "merge": ("Gộp văn bản", "Ghép các file chương theo đúng thứ tự vào một file tổng hợp.", "Gộp file ngay"),
    "split": ("Tách văn bản", "Chia file tổng hợp thành các phần theo độ dài bạn chọn.", "Tách file ngay"),
}


def load_settings():
    settings, error = DEFAULTS.copy(), None
    try:
        if CONFIG.exists():
            loaded = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
            if not isinstance(loaded, dict):
                raise ValueError("Cấu hình phải là một object JSON.")
            for key, default in settings.items():
                if isinstance(loaded.get(key), type(default)):
                    settings[key] = loaded[key]
            settings["root_folder"] = infer_root(loaded)
            if "source_folder" not in loaded and isinstance(loaded.get("merge_input"), str):
                settings["source_folder"] = Path(loaded["merge_input"]).name
    except (OSError, ValueError) as exc:
        error = str(exc)
    for key, choices in (("operation", OPERATIONS), ("separator", SEPARATORS),
                         ("mode", ("Sau dấu kết thúc câu", "Giới hạn cứng"))):
        if settings[key] not in choices:
            settings[key] = DEFAULTS[key]
    return settings, error


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("TextFile • Không gian xử lý văn bản")
        self.configure(bg=BG)
        width, height = min(1120, self.winfo_screenwidth() - 80), min(880, self.winfo_screenheight() - 100)
        self.geometry(f"{width}x{height}")
        self.minsize(min(960, width), min(680, height))
        settings, config_error = load_settings()
        self.vars = {k: tk.BooleanVar(value=v) if isinstance(v, bool) else tk.StringVar(value=v)
                     for k, v in settings.items()}
        self.busy, self.updating = False, False
        self.project = self.last_output = self.scan_timer = self.settings_window = None
        self.events, self.scan_id, self.controls = queue.Queue(), 0, []
        self.status = tk.StringVar(value="Chọn thư mục gốc để bắt đầu.")
        self.project_name = tk.StringVar(value="Chưa chọn thư mục")
        self.setup_styles()
        self.build_sidebar()
        self.build_workspace()
        self.select_operation(settings["operation"])
        for key in ("root_folder", "source_folder"):
            self.vars[key].trace_add("write", self.schedule_scan)
        for key in ("max_chars", "mode"):
            self.vars[key].trace_add("write", self.update_option_hint)
        self.bind("<Control-Return>", lambda event: self.run())
        self.bind("<Control-o>", lambda event: self.browse())
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(100, self.poll)
        self.schedule_scan()
        if config_error:
            self.after(300, lambda: messagebox.showwarning("Không đọc được cấu hình", config_error, parent=self))

    def setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TEntry", padding=(10, 9), font=("Segoe UI", 10), fieldbackground="white",
                        foreground=INK, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        style.map("TEntry", bordercolor=[("focus", BLUE)])
        style.configure("TCombobox", padding=(9, 8), font=("Segoe UI", 10), fieldbackground="white",
                        background="white", foreground=INK, bordercolor=BORDER, arrowsize=12)
        style.map("TCombobox", fieldbackground=[("readonly", "white"), ("disabled", BG)],
                  foreground=[("readonly", INK)], selectbackground=[("readonly", "white")],
                  selectforeground=[("readonly", INK)])
        style.configure("TButton", font=("Segoe UI", 10), padding=(14, 9), background="white",
                        foreground=INK, bordercolor=BORDER, lightcolor="white", darkcolor="white")
        style.map("TButton", background=[("active", "#edf1ff"), ("disabled", BG)], foreground=[("disabled", "#a0a9b9")])
        style.configure("Small.TButton", padding=(10, 4))
        style.configure("Accent.TButton", background=BLUE, foreground="white", bordercolor=BLUE,
                        lightcolor=BLUE, darkcolor=BLUE, font=("Segoe UI", 11, "bold"), padding=(22, 12))
        style.map("Accent.TButton", background=[("disabled", "#c6cfe9"), ("active", "#3452d5")],
                  foreground=[("disabled", "#f7f8fc")])
        style.configure("TCheckbutton", background=BG, foreground=INK, font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", BG)])
        style.configure("TProgressbar", background=BLUE, troughcolor="#e8edf6", borderwidth=0,
                        lightcolor=BLUE, darkcolor=BLUE, thickness=4)
        style.configure("Vertical.TScrollbar", background="#d6deeb", troughcolor=BG, borderwidth=0, arrowsize=10)
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))

    def label(self, parent, text="", size=10, color=INK, bold=False, **kwargs):
        return tk.Label(parent, text=text, font=("Segoe UI", size, "bold" if bold else "normal"),
                        fg=color, bg=kwargs.pop("bg", parent.cget("bg")), anchor="w", **kwargs)

    def button(self, parent, text, command, accent=False, **kwargs):
        widget = ttk.Button(parent, text=text, command=command,
                            style="Accent.TButton" if accent else "TButton", **kwargs)
        self.controls.append((widget, "normal"))
        return widget

    def build_sidebar(self):
        side = tk.Frame(self, bg=NAV, width=205)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        brand = tk.Frame(side, bg=NAV)
        brand.pack(fill="x", padx=24, pady=(30, 5))
        self.label(brand, "T", 18, "white", True, bg=BLUE, padx=12, pady=3).pack(side="left")
        self.label(brand, "TextFile", 17, "white", True).pack(side="left", padx=(10, 0))
        self.label(side, "GỌN TỪNG CHƯƠNG CHỮ", 8, "#91a2bb").pack(anchor="w", padx=24, pady=(8, 38))
        self.label(side, "CÔNG CỤ", 8, "#91a2bb", True).pack(anchor="w", padx=24, pady=(0, 10))
        self.nav_buttons = {}
        for key, text in (("pipeline", "01    Gộp & tách"), ("merge", "02    Chỉ gộp file"), ("split", "03    Chỉ tách file")):
            btn = tk.Button(side, text=text, command=lambda k=key: self.select_operation(k), anchor="w",
                            font=("Segoe UI", 10), bg=NAV, fg="#b5c2d6", activebackground="#273955",
                            activeforeground="white", relief="flat", borderwidth=0, padx=18, pady=13,
                            cursor="hand2", takefocus=True)
            btn.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[key] = btn
            self.controls.append((btn, "normal"))
        bottom = tk.Frame(side, bg=NAV)
        bottom.pack(side="bottom", fill="x", padx=24, pady=26)
        self.label(bottom, "MỘT THƯ MỤC LÀ ĐỦ", 8, "#a9b9d3", True).pack(anchor="w")
        self.label(bottom, "Chọn gốc truyện.\nĐường dẫn tự sắp xếp.\nSẵn sàng để xử lý.", 10,
                   "#8397b5", justify="left", pady=10).pack(anchor="w")
        tk.Frame(bottom, bg="#2b3b53", height=1).pack(fill="x", pady=(10, 16))
        self.label(bottom, "UTF-8  /  XỬ LÝ TRÊN MÁY", 8, "#8397b5").pack(anchor="w")

    def build_workspace(self):
        workspace = tk.Frame(self, bg=BG)
        workspace.pack(side="left", fill="both", expand=True)
        workspace.columnconfigure(0, weight=1)
        workspace.rowconfigure(1, weight=1)
        header = tk.Frame(workspace, bg=BG)
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=(26, 18))
        headrow = tk.Frame(header, bg=BG)
        headrow.pack(fill="x")
        self.heading = self.label(headrow, size=24, bold=True)
        self.heading.pack(side="left")
        self.button(headrow, "Tùy chỉnh", self.show_settings).pack(side="right", padx=(12, 0))
        self.subtitle = self.label(header, color=MUTED, wraplength=730, justify="left")
        self.subtitle.pack(anchor="w", pady=(6, 0))
        scroll_area = tk.Frame(workspace, bg=BG)
        scroll_area.grid(row=1, column=0, sticky="nsew", padx=(30, 15))
        self.canvas = tk.Canvas(scroll_area, bg=BG, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(scroll_area, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(self.canvas, bg=BG)
        body_id = self.canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(body_id, width=event.width))
        self.bind_all("<MouseWheel>", self.scroll_body, add=True)

        card = tk.Frame(body, bg="white", highlightbackground=BORDER, highlightthickness=1, padx=20, pady=18)
        card.pack(fill="x", padx=(0, 12))
        self.label(card, "01  /  THƯ MỤC TRUYỆN", 9, BLUE, True).pack(anchor="w")
        self.label(card, textvariable=self.project_name, size=14, bold=True).pack(fill="x", pady=(8, 12))
        row = tk.Frame(card, bg="white")
        row.pack(fill="x")
        entry = ttk.Entry(row, textvariable=self.vars["root_folder"])
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda event: self.scan_now())
        entry.bind("<Control-Return>", lambda event: self.run() or "break")
        self.controls.append((entry, "normal"))
        self.button(row, "Chọn thư mục…", self.browse).pack(side="right", padx=(10, 0))
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", padx=(0, 12), pady=(18, 10))
        self.label(row, "02  /  ĐƯỜNG DẪN TỰ ĐỘNG", 9, MUTED, True).pack(side="left")
        scan_button = self.button(row, "Quét lại", self.scan_now)
        scan_button.configure(style="Small.TButton")
        scan_button.pack(side="right")
        self.source_combo = ttk.Combobox(row, textvariable=self.vars["source_folder"], state="readonly", width=9)
        self.source_combo.pack(side="right", padx=(8, 10))
        self.controls.append((self.source_combo, "readonly"))
        self.label(row, "Nguồn", color=MUTED, size=9).pack(side="right")
        stages = tk.Frame(body, bg=BG)
        stages.pack(fill="x", padx=(0, 12))
        self.stage_labels = []
        for index, (caption, title, detail) in enumerate((
                ("NGUỒN CHƯƠNG", "—", "Chưa chọn thư mục"),
                ("FILE TỔNG HỢP", "all.txt", "Được tạo khi gộp"),
                ("THƯ MỤC KẾT QUẢ", "v2", "Được tạo khi tách"))):
            stages.columnconfigure(index, weight=1, uniform="stage")
            tile = tk.Frame(stages, bg="white", highlightbackground=BORDER, highlightthickness=1, padx=16, pady=12)
            tile.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 10, 0))
            self.label(tile, f"{index + 1:02d}   {caption}", 8, MUTED, True).pack(anchor="w")
            title_label = self.label(tile, title, 18, BLUE if index == 2 else INK, True)
            title_label.pack(anchor="w", pady=(8, 5))
            path_label = self.label(tile, "—", 9, MUTED, justify="left")
            path_label.pack(fill="x")
            detail_label = self.label(tile, detail, 9, MUTED, justify="left")
            detail_label.pack(fill="x", pady=(8, 0))
            for label in (path_label, detail_label):
                label.bind("<Configure>", lambda event, w=label: w.configure(wraplength=max(100, event.width)))
            self.stage_labels.append((title_label, path_label, detail_label))
        self.plan_note = self.label(body, color=MUTED, size=9, justify="left", wraplength=710)
        self.plan_note.pack(fill="x", padx=(2, 15), pady=(8, 12))
        split = tk.Frame(body, bg="white", highlightbackground=BORDER, highlightthickness=1, padx=20, pady=12)
        split.pack(fill="x", padx=(0, 12))
        self.label(split, "03  /  CÁCH CHIA VĂN BẢN", 9, MUTED, True).pack(anchor="w", pady=(0, 12))
        row = tk.Frame(split, bg="white")
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=2)
        self.label(row, "Ký tự mỗi phần", color=MUTED).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.label(row, "Điểm ngắt", color=MUTED).grid(row=0, column=1, sticky="w", padx=(20, 0), pady=(0, 6))
        limit = ttk.Entry(row, textvariable=self.vars["max_chars"], width=16)
        limit.grid(row=1, column=0, sticky="ew")
        mode = ttk.Combobox(row, textvariable=self.vars["mode"], state="readonly",
                            values=["Sau dấu kết thúc câu", "Giới hạn cứng"])
        mode.grid(row=1, column=1, sticky="ew", padx=(20, 0))
        self.split_controls = [(limit, "normal"), (mode, "readonly")]
        self.controls.extend(self.split_controls)
        self.option_hint = self.label(split, color=MUTED, size=9, wraplength=680, justify="left")
        self.option_hint.pack(anchor="w", pady=(10, 0))
        self.update_option_hint()

        footer = tk.Frame(workspace, bg=BG)
        footer.grid(row=2, column=0, sticky="ew", padx=30, pady=(18, 20))
        row = tk.Frame(footer, bg=BG)
        row.pack(fill="x", pady=(0, 12))
        overwrite = ttk.Checkbutton(row, text="Ghi đè file trùng tên", variable=self.vars["overwrite"])
        overwrite.pack(side="left")
        self.controls.append((overwrite, "normal"))
        self.label(row, "Tự lưu cấu hình khi chạy", 9, MUTED).pack(side="right")
        row = tk.Frame(footer, bg=BG)
        row.pack(fill="x")
        self.run_button = self.button(row, "Gộp & tách ngay", self.run, accent=True, state="disabled")
        self.run_button.pack(side="left")
        self.label(row, "Ctrl + Enter", 9, MUTED).pack(side="left", padx=14)
        self.open_button = ttk.Button(row, text="Mở kết quả ↗", command=self.open_result, state="disabled")
        self.open_button.pack(side="right")
        self.progress = ttk.Progressbar(footer, mode="indeterminate")
        self.progress.pack(fill="x", pady=(16, 10))
        self.label(footer, textvariable=self.status, color=MUTED, size=9,
                   wraplength=740, justify="left").pack(fill="x")

    def scroll_body(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget == self.canvas:
                if self.canvas.bbox("all")[3] > self.canvas.winfo_height():
                    self.canvas.yview_scroll(-int(event.delta / 120), "units")
                return
            widget = getattr(widget, "master", None)

    def select_operation(self, operation):
        if self.busy:
            return
        self.vars["operation"].set(operation)
        title, subtitle, action = OPERATIONS[operation]
        self.heading.configure(text=title)
        self.subtitle.configure(text=subtitle)
        self.run_button.configure(text=action)
        for key, button in self.nav_buttons.items():
            button.configure(bg="#2b4164" if key == operation else NAV,
                             fg="white" if key == operation else "#a7b7cf")
        for widget, state in self.split_controls:
            widget.configure(state="disabled" if operation == "merge" else state)
        self.update_plan_note()
        self.update_run_state()

    def update_option_hint(self, *_):
        try:
            number = f"{int(self.vars['max_chars'].get()):,}".replace(",", ".")
        except ValueError:
            number = "…"
        text = (f"Khoảng {number} ký tự/phần; chờ hết câu nên có thể dài hơn ngưỡng."
                if self.vars["mode"].get() != "Giới hạn cứng" else
                f"Mỗi phần tối đa {number} ký tự; ưu tiên ngắt tại dấu câu.")
        self.option_hint.configure(text=text)

    def update_plan_note(self):
        if not self.project:
            self.plan_note.configure(text="Các đường dẫn sẽ xuất hiện sau khi chọn thư mục gốc.")
            return
        source = self.project.source.name if self.project.source.name != "." else "gốc truyện"
        texts = {
            "pipeline": f"{source}  →  {source}/all.txt  →  {self.project.output.name}/1.txt, 2.txt…",
            "merge": "Gộp theo số chương: 1.txt, 2.txt, 1-3.txt… Bỏ qua file khác và thư mục con.",
            "split": f"Dùng file có sẵn: {source}/all.txt  →  {self.project.output.name}/1.txt, 2.txt…",
        }
        self.plan_note.configure(text=texts[self.vars["operation"].get()])

    def browse(self):
        if self.busy:
            return
        value = self.vars["root_folder"].get().strip().strip('"')
        initial = value if value and Path(value).is_dir() else str(ROOT)
        folder = filedialog.askdirectory(parent=self, title="Chọn thư mục gốc chứa v1, raw, v2…", initialdir=initial)
        if folder:
            self.vars["root_folder"].set(folder)

    def schedule_scan(self, *_):
        if self.updating or self.busy:
            return
        self.scan_id += 1
        self.project = self.last_output = None
        self.open_button.configure(state="disabled")
        self.update_run_state()
        if self.scan_timer:
            self.after_cancel(self.scan_timer)
        self.status.set("Đang nhận diện thư mục…" if self.vars["root_folder"].get().strip() else "Chọn thư mục gốc để bắt đầu.")
        self.scan_timer = self.after(400, self.start_scan)

    def scan_now(self):
        if not self.busy:
            self.schedule_scan()
            self.after_cancel(self.scan_timer)
            self.start_scan()

    def start_scan(self):
        self.scan_timer = None
        scan_id, root, source = self.scan_id, self.vars["root_folder"].get(), self.vars["source_folder"].get()
        def worker():
            try:
                self.events.put(("scan", scan_id, discover_project(root, source), None))
            except Exception as exc:
                self.events.put(("scan", scan_id, None, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def show_project(self, project, error=None, keep_status=False):
        self.project = project
        if project is None:
            self.project_name.set("Chưa nhận diện được thư mục")
            self.source_combo.configure(values=[])
            for title, path, detail in self.stage_labels:
                title.configure(text="—")
                path.configure(text="Chưa nhận diện")
                detail.configure(text="Chọn thư mục gốc")
            if not keep_status:
                self.status.set(error or "Chọn thư mục gốc để bắt đầu.")
        else:
            self.updating = True
            try:
                self.vars["root_folder"].set(str(project.root))
                self.vars["source_folder"].set(project.source.name)
                self.source_combo.configure(values=[s.name for s in project.sources])
            finally:
                self.updating = False
            name = project.root.name
            self.project_name.set(name if len(name) <= 64 else name[:61] + "…")
            self.stage_labels[0][0].configure(text=project.source.name if project.source.name != "." else "Gốc truyện")
            self.stage_labels[0][1].configure(text=f"{project.source.count:,} file chương".replace(",", "."))
            self.stage_labels[0][2].configure(text=project.source.error or (
                f"{project.source.first} → {project.source.last}" if project.source.count else "Chưa có file chương"))
            self.stage_labels[1][0].configure(text="all.txt")
            self.stage_labels[1][1].configure(text=str(project.merged.relative_to(project.root)))
            self.stage_labels[1][2].configure(text="Đã có file tổng hợp" if project.merged.is_file() else "Sẽ được tạo khi gộp")
            self.stage_labels[2][0].configure(text=project.output.name)
            self.stage_labels[2][1].configure(text=f"{project.output.name}/1.txt, 2.txt…")
            self.stage_labels[2][2].configure(text=f"Hiện có {project.output_count} file .txt" if project.output.exists()
                                            else "Tự tạo khi lưu kết quả")
            if not keep_status:
                self.status.set(project.source.error or "Sẵn sàng · Đường dẫn đã tự động · Đầu ra UTF-8")
        self.update_plan_note()
        self.update_run_state()

    def update_run_state(self):
        ready = self.project is not None and not self.busy
        if ready:
            ready = (self.project.merged.is_file() if self.vars["operation"].get() == "split" else
                     self.project.source.count > 0 and not self.project.source.error)
        self.run_button.configure(state="normal" if ready else "disabled")

    def data(self):
        return {k: v.get() for k, v in self.vars.items()}

    def save(self):
        try:
            temp = CONFIG.with_suffix(".json.tmp")
            temp.write_text(json.dumps(self.data(), ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temp, CONFIG)
            return True
        except OSError as exc:
            messagebox.showerror("Không lưu được cấu hình", str(exc), parent=self)
            return False

    def validate(self, data, operation=None):
        codecs.lookup(data["encoding"])
        if data["separator"] not in SEPARATORS:
            raise ValueError("Kiểu ngăn cách không hợp lệ.")
        if operation != "merge":
            try:
                limit, start = int(data["max_chars"]), int(data["start_index"])
            except ValueError:
                raise ValueError("Số ký tự và số bắt đầu phải là số nguyên.") from None
            if limit < 1 or start < 0:
                raise ValueError("Số ký tự phải lớn hơn 0; số bắt đầu phải từ 0 trở lên.")
            if not data["endings"] and data["mode"] != "Giới hạn cứng":
                raise ValueError("Hãy nhập dấu kết thúc câu hoặc chọn Giới hạn cứng.")

    def set_busy(self, busy):
        self.busy = busy
        for widget, state in self.controls:
            widget.configure(state="disabled" if busy else state)
        if not busy:
            self.select_operation(self.vars["operation"].get())
        self.update_run_state()

    def run(self):
        if self.busy or self.project is None:
            return
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        data, project = self.data(), self.project
        operation = data["operation"]
        try:
            self.validate(data, operation)
            if operation != "split" and (project.source.error or not project.source.count):
                raise ValueError(project.source.error or "Nguồn chưa có file chương hợp lệ (1.txt, 1-3.txt…).")
            if operation == "split" and not project.merged.is_file():
                raise ValueError(f"Chưa có {project.merged}.\nChọn Gộp & tách để tạo file tổng hợp trước.")
        except (ValueError, LookupError) as exc:
            messagebox.showerror("Kiểm tra cấu hình", str(exc), parent=self)
            return
        if not self.save():
            return
        self.set_busy(True)
        self.last_output = None
        self.open_button.configure(state="disabled")
        self.progress.start(12)
        self.status.set("Đang chuẩn bị xử lý…")
        def worker():
            try:
                result = execute_project(project, operation, data,
                                         lambda text: self.events.put(("progress", text)))
                self.events.put(("done", True, result, project, operation))
            except Exception as exc:
                self.events.put(("done", False, str(exc), project, operation))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "scan" and event[1] == self.scan_id:
                    self.show_project(event[2], event[3])
                elif event[0] == "progress":
                    self.status.set(event[1])
                elif event[0] == "done":
                    _, success, result, project, operation = event
                    self.progress.stop()
                    self.set_busy(False)
                    if success:
                        self.last_output = result["output"]
                        self.open_button.configure(state="normal")
                        if operation == "pipeline":
                            text = f"Hoàn tất · Đã gộp {result['chapters']} file chương và tạo {result['parts']} phần trong {project.output.name}."
                        elif operation == "merge":
                            text = f"Hoàn tất · Đã gộp {result['chapters']} file chương → {project.source.name}/all.txt."
                        else:
                            text = f"Hoàn tất · Đã tạo {result['parts']} phần trong {project.output.name}."
                        self.status.set(text)
                        self.refresh_counts(project)
                    else:
                        self.status.set("Chưa hoàn tất · " + result.splitlines()[0])
                        messagebox.showerror("Không thể xử lý", result, parent=self)
                elif event[0] == "refresh" and event[1] == self.scan_id:
                    self.show_project(event[2], keep_status=True)
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def refresh_counts(self, project):
        self.scan_id += 1
        scan_id = self.scan_id
        def worker():
            try:
                updated = discover_project(str(project.root), project.source.name)
                self.events.put(("refresh", scan_id, updated))
            except (OSError, ValueError):
                pass
        threading.Thread(target=worker, daemon=True).start()

    def show_settings(self):
        if self.busy:
            return
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        dialog = self.settings_window = tk.Toplevel(self)
        dialog.title("Tùy chỉnh văn bản")
        dialog.configure(bg=BG)
        dialog.transient(self)
        dialog.resizable(False, False)
        body = tk.Frame(dialog, bg=BG, padx=26, pady=24)
        body.pack(fill="both", expand=True)
        self.label(body, "Tùy chỉnh văn bản", 19, bold=True).pack(anchor="w")
        self.label(body, "Áp dụng cho truyện hiện tại và những lần xử lý tiếp theo.", color=MUTED).pack(anchor="w", pady=(6, 20))
        snapshot, fields = self.data(), tk.Frame(body, bg=BG)
        fields.pack(fill="x")
        fields.columnconfigure(1, weight=1)
        specs = [("Ngăn cách khi gộp", "separator", list(SEPARATORS)),
                 ("Ký tự mỗi phần", "max_chars", None), ("Đánh số phần từ", "start_index", None),
                 ("Điểm ngắt khi tách", "mode", ["Sau dấu kết thúc câu", "Giới hạn cứng"]),
                 ("Ký tự cần xóa", "remove_chars", None), ("Dấu kết thúc câu", "endings", None),
                 ("Mã hóa file chương", "encoding", ["utf-8-sig", "utf-8", "utf-16", "cp1258"])]
        for row, (caption, key, choices) in enumerate(specs):
            self.label(fields, caption).grid(row=row, column=0, sticky="w", padx=(0, 22), pady=6)
            widget = (ttk.Combobox(fields, textvariable=self.vars[key], values=choices,
                                   state="normal" if key == "encoding" else "readonly", width=27)
                      if choices else ttk.Entry(fields, textvariable=self.vars[key], width=29))
            widget.grid(row=row, column=1, sticky="ew", pady=6)
        self.label(body, "Để trống ký tự cần xóa để giữ nguyên văn bản.\nĐầu ra luôn là UTF-8. Ghi đè chỉ thay file trùng tên,\nkhông xóa các phần cũ còn dư.",
                   9, MUTED, justify="left").pack(anchor="w", pady=(15, 18))
        actions = tk.Frame(body, bg=BG)
        actions.pack(fill="x")
        def cancel():
            for _, key, _ in specs:
                self.vars[key].set(snapshot[key])
            dialog.destroy()
            self.settings_window = None
        def apply():
            try:
                self.validate(self.data())
            except (ValueError, LookupError) as exc:
                messagebox.showerror("Kiểm tra tùy chỉnh", str(exc), parent=dialog)
                return
            if self.save():
                dialog.destroy()
                self.settings_window = None
                self.status.set("Đã lưu tùy chỉnh.")
        ttk.Button(actions, text="Hủy", command=cancel).pack(side="left")
        ttk.Button(actions, text="Lưu tùy chỉnh", style="Accent.TButton", command=apply).pack(side="right")
        dialog.protocol("WM_DELETE_WINDOW", cancel)
        dialog.bind("<Escape>", lambda event: cancel())
        dialog.update_idletasks()
        x = max(0, self.winfo_rootx() + (self.winfo_width() - dialog.winfo_reqwidth()) // 2)
        y = max(0, self.winfo_rooty() + (self.winfo_height() - dialog.winfo_reqheight()) // 2)
        dialog.geometry(f"+{x}+{y}")
        dialog.grab_set()

    def open_result(self):
        if self.last_output:
            try:
                path = Path(self.last_output)
                os.startfile(str(path.parent if path.is_file() else path))
            except OSError as exc:
                messagebox.showerror("Không mở được kết quả", str(exc), parent=self)

    def close(self):
        if self.busy:
            messagebox.showinfo("Đang xử lý", "Vui lòng chờ xử lý xong trước khi đóng ứng dụng.", parent=self)
        elif self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
        elif self.save():
            self.destroy()


if __name__ == "__main__":
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    App().mainloop()
