import os
import json
import zipfile
import shutil
import subprocess
import base64
import tempfile
import uuid
import tkinter as tk
from math import sin, cos, radians
import math
from tkinter import messagebox, filedialog, ttk

try:
    from PIL import Image, ImageTk, ImageDraw
    try:
        import numpy as np
        import cv2
        CV_AVAILABLE = True
    except Exception:
        np = None
        cv2 = None
        CV_AVAILABLE = False
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


def _read_texture_png(path):
    if not path or not os.path.isfile(path):
        return None
    try:
        if PIL_AVAILABLE:
            from PIL import Image
            img = Image.open(path).convert("RGBA")
            return img
        return tk.PhotoImage(file=path)
    except Exception:
        try:
            return tk.PhotoImage(file=path)
        except Exception:
            return None

import tkinter as _tk
from tkinter import filedialog as _fd

try:
    from PIL import Image as _PILImage, ImageTk as _ImageTk
    _PIL_AVAILABLE = True
except Exception:
    _PILImage = None
    _ImageTk = None
    _PIL_AVAILABLE = False

_texture_slots = []


def add_texture_slot(parent, slot_index=None):
    """Add one independent texture slot and let the user choose a PNG."""
    idx = len(_texture_slots) if slot_index is None else slot_index

    frame = _tk.Frame(parent, bd=1, relief="solid", padx=4, pady=4)
    frame.pack(side="left", padx=4, pady=4)

    title = _tk.Label(frame, text=f"Текстура #{idx}", font=("Arial", 9, "bold"))
    title.pack()

    preview = _tk.Label(frame, text="PNG", width=12, height=6)
    preview.pack()

    def choose():
        path = _fd.askopenfilename(
            title=f"Выбрать текстуру #{idx}",
            filetypes=[("PNG texture", "*.png"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            if not _PIL_AVAILABLE:
                raise RuntimeError("Pillow не установлен")
            im = _PILImage.open(path).convert("RGBA")
            im.thumbnail((96, 96), _PILImage.Resampling.NEAREST)
            photo = _ImageTk.PhotoImage(im)
            preview.configure(image=photo, text="")
            preview.image = photo
        except Exception as e:
            preview.configure(image="", text=f"Ошибка\n{e}")

        slot = {"index": idx, "path": path, "image": im if 'im' in locals() else None}
        if idx < len(_texture_slots):
            _texture_slots[idx] = slot
        else:
            while len(_texture_slots) < idx:
                _texture_slots.append({"index": len(_texture_slots), "path": "", "image": None})
            _texture_slots.append(slot)

    _tk.Button(frame, text="Выбрать PNG", command=choose).pack(fill="x", pady=(4, 0))
    _texture_slots.append({"index": idx, "path": "", "image": None})
    return frame


def get_texture_slots_data():
    """Return selected texture-slot data in stable #0, #1, #2... order."""
    return [s for s in _texture_slots if s.get("path")]


def get_texture_slots():
    """Return selected texture paths in stable #0, #1, #2... order."""
    return [s["path"] for s in get_texture_slots_data()]


def build_texture_panel(parent, max_slots=32):
    """Create the texture area with explicit '+ Текстура 2', '+ Текстура 3'... buttons."""
    panel = _tk.Frame(parent)
    panel.pack(fill="x", expand=False)

    slots_frame = _tk.Frame(panel)
    slots_frame.pack(fill="x")

    controls = _tk.Frame(panel)
    controls.pack(fill="x", pady=6)

    def add_next():
        n = len(_texture_slots)
        if n >= max_slots:
            return
        add_texture_slot(slots_frame, n)
        refresh_buttons()

    def refresh_buttons():
        for w in controls.winfo_children():
            w.destroy()
        n = len(_texture_slots)
        _tk.Button(
            controls,
            text=f"➕ Добавить текстуру #{n + 1}",
            command=add_next
        ).pack(side="left", padx=3)
        if n:
            _tk.Label(
                controls,
                text=f"Добавлено текстур: {n}"
            ).pack(side="left", padx=10)

    add_texture_slot(slots_frame, 0)
    refresh_buttons()

    return panel


def setup_multiple_textures_ui(parent):
    """
    Call this where the old single-texture 'Инвентарь' preview panel was created.
    It creates:
      Текстура #0 + Выбрать PNG
      ➕ Добавить текстуру #2
      ➕ Добавить текстуру #3
      ...
    """
    return build_texture_panel(parent)


class MultiItemRPBuilderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Multi-Item Minecraft RP & Geyser Builder")
        self.root.geometry("1000x860")
        self.root.minsize(900, 780)
        self.root.config(bg="#2b2b2b")

        # Список добавленных предметов: каждый элемент - словарь
        self.items_list = []
        self.imported_pack_dir = ""
        self.preview_item = None
        self.preview_photo = None
        self.preview_photo_animated = None
        self.preview_angle = 0.0
        self.preview_running = False
        self.preview_after_id = None
        self.pil_available = PIL_AVAILABLE
        self.texture_slots = []
        self.bbmodel_source = ""

        self.create_widgets()

    def create_widgets(self):
        # Верхняя панель: выбор версии
        top_frame = tk.Frame(self.root, bg="#3c3f41", padx=10, pady=10)
        top_frame.pack(fill="x", padx=10, pady=10)

        tk.Label(top_frame, text="Версия Minecraft для Java-пака:", fg="#ffffff", bg="#3c3f41", font=("Arial", 10, "bold")).pack(side="left", padx=5)
        self.version_combobox = ttk.Combobox(top_frame, values=[
            "26.1.2 (pack_format 84, item_model)",
            "1.21.4 - 1.21.11 (pack_format 46-81, item_model)",
            "1.21 / 1.20 (Классический CustomModelData)"
        ], state="readonly", width=42)
        self.version_combobox.pack(side="left", padx=5)
        self.version_combobox.current(0) # По умолчанию новая

        # Основной контейнер (Слева - форма ввода, Справа - список предметов)
        main_container = tk.Frame(self.root, bg="#2b2b2b")
        main_container.pack(fill="both", expand=True, padx=10, pady=5)

        # Левая часть: Форма добавления предмета
        form_frame = tk.LabelFrame(main_container, text=" Параметры предмета ", bg="#3c3f41", fg="#ffffff", font=("Arial", 10, "bold"), padx=10, pady=10)
        form_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

        tk.Label(form_frame, text="ID предмета (напр. coocnat):", fg="#ffffff", bg="#3c3f41", anchor="w").pack(fill="x")
        self.entry_id = tk.Entry(form_frame, bg="#2b2b2b", fg="#ffffff", insertbackground="white")
        self.entry_id.pack(fill="x", pady=(0, 8))

        tk.Label(form_frame, text="РП Название (&bКокос):", fg="#ffffff", bg="#3c3f41", anchor="w").pack(fill="x")
        self.entry_name = tk.Entry(form_frame, bg="#2b2b2b", fg="#ffffff", insertbackground="white")
        self.entry_name.pack(fill="x", pady=(0, 8))
        self.entry_name.insert(0, "&bКокос")

        tk.Label(form_frame, text="Базовый предмет (напр. cookie):", fg="#ffffff", bg="#3c3f41", anchor="w").pack(fill="x")
        self.entry_base = tk.Entry(form_frame, bg="#2b2b2b", fg="#ffffff", insertbackground="white")
        self.entry_base.pack(fill="x", pady=(0, 8))
        self.entry_base.insert(0, "cookie")

        tk.Label(form_frame, text="CustomModelData (напр. 1001):", fg="#ffffff", bg="#3c3f41", anchor="w").pack(fill="x")
        self.entry_cmd = tk.Entry(form_frame, bg="#2b2b2b", fg="#ffffff", insertbackground="white")
        self.entry_cmd.pack(fill="x", pady=(0, 8))
        self.entry_cmd.insert(0, "1001")

        # Модель: обычный Minecraft JSON или Blockbench .bbmodel
        btn_model = tk.Button(
            form_frame, text="🧩 Добавить модель (.json / .bbmodel)",
            command=self.select_model, bg="#585858", fg="#ffffff"
        )
        btn_model.pack(fill="x", pady=2)
        self.lbl_model = tk.Label(form_frame, text="Не выбрано", fg="#aaaaaa", bg="#3c3f41", anchor="w")
        self.lbl_model.pack(fill="x", pady=(0, 8))
        self.model_path = ""

        # Основная текстура (для обычной модели с одной текстурой)
        btn_texture = tk.Button(
            form_frame, text="🖼 Выбрать основную .png текстуру",
            command=self.select_texture, bg="#585858", fg="#ffffff"
        )
        btn_texture.pack(fill="x", pady=2)
        self.lbl_texture = tk.Label(form_frame, text="Не выбрано", fg="#aaaaaa", bg="#3c3f41", anchor="w")
        self.lbl_texture.pack(fill="x", pady=(0, 8))
        self.texture_path = ""

        # Текстуры этого предмета
        self.texture_editor_frame = tk.LabelFrame(
            form_frame, text=" Текстуры модели ",
            bg="#3c3f41", fg="#ffffff", padx=6, pady=6
        )
        self.texture_editor_frame.pack(fill="x", pady=(2, 8))
        self._build_item_texture_editor(self.texture_editor_frame)

        # Кнопка добавления в общий список
        btn_add = tk.Button(form_frame, text="➕ Добавить предмет в список", command=self.add_item_to_list, bg="#4CAF50", fg="#ffffff", font=("Arial", 10, "bold"), pady=6)
        btn_add.pack(fill="x", pady=10)

        # Правая часть: Список созданных предметов
        right_frame = tk.LabelFrame(main_container, text=" Список предметов для сборки ", bg="#3c3f41", fg="#ffffff", font=("Arial", 10, "bold"), padx=10, pady=10)
        right_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

        # Таблица (Treeview)
        columns = ("id", "texture", "base", "cmd")
        self.tree = ttk.Treeview(right_frame, columns=columns, show="headings", height=12)
        self.tree.heading("id", text="ID")
        self.tree.heading("texture", text="Текстура")
        self.tree.heading("base", text="База")
        self.tree.heading("cmd", text="CMD")
        self.tree.column("id", width=110)
        self.tree.column("texture", width=150)
        self.tree.column("base", width=90)
        self.tree.column("cmd", width=60)
        self.tree.pack(fill="both", expand=True, pady=(0, 8))

        btn_remove = tk.Button(right_frame, text="🗑 Удалить выбранный", command=self.remove_item, bg="#f44336", fg="#ffffff", font=("Arial", 9))
        btn_remove.pack(fill="x", pady=(0, 8))

        edit_controls = tk.Frame(right_frame, bg="#3c3f41")
        edit_controls.pack(fill="x", pady=(0, 6))
        tk.Button(edit_controls, text="🖼 Изменить текстуру", command=self.replace_selected_texture, bg="#585858", fg="#ffffff", font=("Arial", 8)).pack(side="left", expand=True, fill="x", padx=(0, 3))
        tk.Button(edit_controls, text="🧩 Изменить модель", command=self.replace_selected_model, bg="#585858", fg="#ffffff", font=("Arial", 8)).pack(side="left", expand=True, fill="x", padx=(3, 0))

        # Отдельная панель текстур выбранного предмета будет открываться кнопкой.
        tk.Button(
            right_frame, text="🖼 Открыть текстуры выбранной модели",
            command=self.show_selected_textures_window,
            bg="#585858", fg="#ffffff", font=("Arial", 9)
        ).pack(fill="x", pady=(0, 6))

        preview_label = tk.Label(right_frame, text="Превью предмета", fg="#ffffff", bg="#3c3f41", anchor="w", font=("Arial", 9, "bold"))
        preview_label.pack(fill="x")
        
        # Исправлено: включен параметр pack(..., width=...) и ограничение области рисования (клиппинг через канвас)
        self.preview_canvas = tk.Canvas(right_frame, width=280, height=140, bg="#2b2b2b", highlightthickness=1, highlightbackground="#555555")
        self.preview_canvas.pack(fill="x", expand=False)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # Нижняя панель компиляции
        compile_frame = tk.Frame(self.root, bg="#2b2b2b", padx=10, pady=10)
        compile_frame.pack(fill="x", padx=10)

        btn_java = tk.Button(compile_frame, text="🚀 Скомпилировать РП для Java (.zip)", command=self.build_java, bg="#2196F3", fg="#ffffff", font=("Arial", 11, "bold"), pady=10)
        btn_java.pack(side="left", expand=True, fill="x", padx=(0, 5))

        btn_geyser = tk.Button(compile_frame, text="📱 Скомпилировать для Geyser (Bedrock)", command=self.build_geyser, bg="#FF9800", fg="#ffffff", font=("Arial", 11, "bold"), pady=10)
        btn_geyser.pack(side="right", expand=True, fill="x", padx=(5, 0))

        # Нижняя панель — открыть папку / посмотреть структуру собранного пака
        utils_frame = tk.Frame(self.root, bg="#2b2b2b", padx=10, pady=10)
        utils_frame.pack(fill="x", padx=10)

        buttons_row = tk.Frame(utils_frame, bg="#2b2b2b")
        buttons_row.pack(fill="x")

        btn_import = tk.Button(buttons_row, text="📥 Импортировать RP", command=self.import_existing_resource_pack, bg="#585858", fg="#ffffff", font=("Arial", 9))
        btn_import.pack(side="left", expand=True, fill="x", padx=(0, 5))

        btn_open_folder = tk.Button(buttons_row, text="📂 Открыть готовый РП", command=self.open_ready_pack, bg="#585858", fg="#ffffff", font=("Arial", 9))
        btn_open_folder.pack(side="left", expand=True, fill="x", padx=(0, 5))

        btn_rebuild_imported = tk.Button(buttons_row, text="🧱 Пересобрать импортированный RP", command=self.rebuild_imported_pack, bg="#585858", fg="#ffffff", font=("Arial", 9))
        btn_rebuild_imported.pack(side="left", expand=True, fill="x", padx=(0, 5))

        btn_show_structure = tk.Button(buttons_row, text="🗂 Показать структуру РП", command=self.show_rp_structure, bg="#585858", fg="#ffffff", font=("Arial", 9))
        btn_show_structure.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.lbl_imported = tk.Label(utils_frame, text="Не импортировано", fg="#aaaaaa", bg="#2b2b2b", anchor="w")
        self.lbl_imported.pack(fill="x", pady=(8, 0))

    def _bbmodel_texture_path(self, bb_path, tex, index):
        """Extract one Blockbench texture to a local PNG and return its path."""
        root = os.path.join(os.path.dirname(bb_path), ".blockbench_import")
        os.makedirs(root, exist_ok=True)

        name = tex.get("name") or tex.get("path") or f"texture_{index}.png"
        name = os.path.basename(str(name)).replace("\\", "_").replace("/", "_")
        if not name.lower().endswith(".png"):
            name += ".png"
        out = os.path.join(root, f"{index}_{name}")

        source = tex.get("source") or ""
        if isinstance(source, str) and source.startswith("data:image"):
            try:
                encoded = source.split(",", 1)[1]
                with open(out, "wb") as fh:
                    fh.write(base64.b64decode(encoded))
                return out
            except Exception:
                pass

        # Некоторые версии Blockbench хранят внешний путь.
        candidates = []
        path_value = tex.get("path") or ""
        if path_value:
            candidates.append(os.path.join(os.path.dirname(bb_path), path_value))
        if tex.get("name"):
            candidates.append(os.path.join(os.path.dirname(bb_path), str(tex["name"])))
        for candidate in candidates:
            candidate = os.path.abspath(candidate)
            if os.path.isfile(candidate):
                try:
                    shutil.copy(candidate, out)
                    return out
                except Exception:
                    return candidate
        return ""

    def _convert_bbmodel_to_json(self, bb_path):
        """Convert a Blockbench .bbmodel into a Minecraft Java item model."""
        try:
            with open(bb_path, "r", encoding="utf-8") as fh:
                bb = json.load(fh)
        except Exception as exc:
            raise ValueError(f"Не удалось прочитать .bbmodel: {exc}")

        if not isinstance(bb, dict):
            raise ValueError("Файл .bbmodel имеет неверный формат.")

        textures = bb.get("textures") or []
        texture_paths = []
        texture_refs = {}

        for i, tex in enumerate(textures):
            if not isinstance(tex, dict):
                continue
            path = self._bbmodel_texture_path(bb_path, tex, i)
            if path:
                texture_paths.append({
                    "index": i,
                    "path": path,
                    "name": os.path.basename(path)
                })
            texture_refs[i] = str(i)

        elements = []
        for element in bb.get("elements") or []:
            if not isinstance(element, dict):
                continue
            e = {
                "from": element.get("from", [0, 0, 0]),
                "to": element.get("to", [16, 16, 16]),
                "faces": {}
            }
            if isinstance(element.get("rotation"), dict):
                e["rotation"] = element["rotation"]
            if isinstance(element.get("faces"), dict):
                for face_name, face in element["faces"].items():
                    if not isinstance(face, dict):
                        continue
                    nf = {}
                    if isinstance(face.get("uv"), list) and len(face["uv"]) == 4:
                        nf["uv"] = face["uv"]
                    rot = face.get("rotation", 0)
                    if rot:
                        nf["rotation"] = rot

                    tex_ref = face.get("texture")
                    # В .bbmodel texture обычно является индексом в textures[].
                    if isinstance(tex_ref, int):
                        nf["texture"] = f"#{tex_ref}"
                    elif isinstance(tex_ref, str):
                        if tex_ref.startswith("#"):
                            nf["texture"] = tex_ref
                        elif tex_ref.isdigit():
                            nf["texture"] = f"#{tex_ref}"
                        else:
                            # Имя texture UUID: сопоставляем с UUID из массива.
                            found_idx = None
                            for idx, tex in enumerate(textures):
                                if isinstance(tex, dict) and str(tex.get("uuid", "")) == tex_ref:
                                    found_idx = idx
                                    break
                            nf["texture"] = f"#{found_idx if found_idx is not None else 0}"
                    elif tex_ref is not None:
                        nf["texture"] = "#0"
                    else:
                        nf["texture"] = "#0"
                    e["faces"][face_name] = nf
            if e["faces"]:
                elements.append(e)

        if not elements:
            raise ValueError("В .bbmodel не найдены элементы модели.")

        # Minecraft JSON использует отдельный texture_size.
        tex_width = bb.get("texture_width", 16) or 16
        tex_height = bb.get("texture_height", 16) or 16

        model = {
            "credit": "Imported from Blockbench",
            "texture_size": [tex_width, tex_height],
            "textures": {str(i): f"minecraft:item/__BLOCKBENCH_SLOT_{i}__"
                         for i in range(len(textures))},
            "elements": elements
        }

        # Имя файла модели не должно зависеть от исходного пути.
        root = os.path.join(os.path.dirname(bb_path), ".blockbench_import")
        os.makedirs(root, exist_ok=True)
        safe = os.path.splitext(os.path.basename(bb_path))[0]
        json_path = os.path.join(root, f"{safe}_minecraft.json")
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(model, fh, indent=4, ensure_ascii=False)

        return json_path, texture_paths

    def select_model(self):
        file_path = filedialog.askopenfilename(
            title="Выберите модель",
            filetypes=[
                ("Blockbench model", "*.bbmodel"),
                ("Minecraft JSON model", "*.json"),
                ("All model files", "*.bbmodel *.json"),
                ("All files", "*.*")
            ]
        )
        if not file_path:
            return

        try:
            self.texture_slots = []
            self.texture_path = ""
            self.lbl_texture.config(text="Не выбрано", fg="#aaaaaa")
            self.bbmodel_source = ""

            if file_path.lower().endswith(".bbmodel"):
                json_path, slots = self._convert_bbmodel_to_json(file_path)
                self.model_path = json_path
                self.bbmodel_source = file_path
                self.texture_slots = slots
                self.lbl_model.config(
                    text=f"{os.path.basename(file_path)} → импортирован",
                    fg="#76ff03"
                )
                if slots and os.path.isfile(slots[0]["path"]):
                    self.texture_path = slots[0]["path"]
            else:
                self.model_path = file_path
                self.lbl_model.config(text=os.path.basename(file_path), fg="#76ff03")
                self._load_json_texture_slots(file_path)

            self._refresh_item_texture_editor()
            if self.texture_slots and not self.texture_path:
                self.texture_path = self.texture_slots[0].get("path", "")
        except Exception as exc:
            self.model_path = ""
            self.texture_slots = []
            messagebox.showerror("Ошибка импорта модели", str(exc))

    def _load_json_texture_slots(self, model_path):
        """Build texture slots from a normal Minecraft/Blockbench-exported JSON."""
        self.texture_slots = []
        data = self._model_json(model_path)
        textures = data.get("textures", {}) if isinstance(data, dict) else {}
        if not isinstance(textures, dict):
            return
        for key, ref in textures.items():
            if not isinstance(ref, str):
                continue
            resolved = ref
            seen = set()
            while isinstance(resolved, str) and resolved.startswith("#"):
                token = resolved[1:]
                if token in seen:
                    break
                seen.add(token)
                resolved = textures.get(token, "")
            path = self._guess_texture_from_reference(resolved, model_path) if resolved else ""
            self.texture_slots.append({
                "index": str(key),
                "path": path,
                "name": os.path.basename(path) if path else str(ref)
            })

    def select_texture(self):
        paths = filedialog.askopenfilenames(
            title="Выберите текстуры .png",
            filetypes=[("PNG files", "*.png")]
        )
        if not paths:
            return

        # Если выбрано несколько PNG, создаём слоты 0..N-1.
        self.texture_slots = [
            {"index": i, "path": path, "name": os.path.basename(path)}
            for i, path in enumerate(paths)
        ]
        self.texture_path = paths[0]
        self.lbl_texture.config(
            text=f"{len(paths)} текстур выбрано",
            fg="#76ff03"
        )
        self._refresh_item_texture_editor()

    def _build_item_texture_editor(self, parent):
        self.texture_slots_container = tk.Frame(parent, bg="#3c3f41")
        self.texture_slots_container.pack(fill="x")
        tk.Button(
            parent, text="➕ Добавить PNG-текстуры",
            command=self.select_texture, bg="#585858", fg="#ffffff"
        ).pack(fill="x", pady=(5, 0))
        self._refresh_item_texture_editor()

    def _refresh_item_texture_editor(self):
        container = getattr(self, "texture_slots_container", None)
        if container is None:
            return
        for w in container.winfo_children():
            w.destroy()

        if not self.texture_slots:
            tk.Label(
                container, text="Текстуры не назначены",
                fg="#aaaaaa", bg="#3c3f41"
            ).pack(fill="x")
            return

        for pos, slot in enumerate(self.texture_slots):
            path = slot.get("path", "")
            label = slot.get("name") or (os.path.basename(path) if path else f"slot {pos}")
            row = tk.Frame(container, bg="#3c3f41")
            row.pack(fill="x", pady=2)

            tk.Label(
                row, text=f"#{slot.get('index', pos)}",
                width=5, fg="#ffffff", bg="#3c3f41"
            ).pack(side="left")
            tk.Label(
                row, text=label, fg="#dddddd", bg="#3c3f41",
                anchor="w"
            ).pack(side="left", fill="x", expand=True)

            tk.Button(
                row, text="👁",
                width=3, command=lambda s=slot: self.open_texture_window(s),
                bg="#585858", fg="#ffffff"
            ).pack(side="right")
            tk.Button(
                row, text="Выбрать",
                command=lambda s=slot: self.replace_texture_slot(s),
                bg="#585858", fg="#ffffff"
            ).pack(side="right", padx=3)

    def replace_texture_slot(self, slot):
        path = filedialog.askopenfilename(
            title=f"Текстура #{slot.get('index')}",
            filetypes=[("PNG files", "*.png")]
        )
        if path:
            slot["path"] = path
            slot["name"] = os.path.basename(path)
            if not self.texture_path:
                self.texture_path = path
            self._refresh_item_texture_editor()

    def open_texture_window(self, slot):
        path = slot.get("path", "")
        if not path or not os.path.isfile(path):
            messagebox.showwarning("Текстура", "Для этого слота PNG ещё не назначен.")
            return

        win = tk.Toplevel(self.root)
        win.title(f"Текстура #{slot.get('index')} — {os.path.basename(path)}")
        win.geometry("620x620")
        win.configure(bg="#252525")

        title = tk.Label(
            win, text=f"#{slot.get('index')}  {os.path.basename(path)}",
            fg="#ffffff", bg="#252525", font=("Arial", 11, "bold")
        )
        title.pack(fill="x", padx=10, pady=10)

        try:
            if PIL_AVAILABLE:
                img = Image.open(path).convert("RGBA")
                max_size = 540
                img.thumbnail((max_size, max_size), Image.Resampling.NEAREST)
                photo = ImageTk.PhotoImage(img)
            else:
                photo = tk.PhotoImage(file=path)
            label = tk.Label(win, image=photo, bg="#252525")
            label.image = photo
            label.pack(expand=True, fill="both", padx=20, pady=20)
        except Exception as exc:
            tk.Label(
                win, text=f"Ошибка открытия текстуры:\n{exc}",
                fg="#ff7777", bg="#252525"
            ).pack(expand=True)

    def _refresh_item_texture_row(self, item):
        if not item:
            return
        for child in self.tree.get_children():
            values = self.tree.item(child, "values")
            if values and values[0] == item.get("id"):
                first_path = ""
                slots = item.get("texture_slots") or []
                if slots:
                    first_path = next((s.get("path", "") for s in slots if s.get("path")), "")
                if not first_path:
                    first_path = item.get("texture_path", "")
                self.tree.item(child, values=(item.get("id", ""), self._texture_label(first_path), item.get("base", ""), item.get("cmd", "")))
                break

    def _normalize_texture_slots(self, item):
        slots = item.get("texture_slots") or []
        normalized = []
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            idx = slot.get("index")
            try:
                idx_num = int(idx)
            except Exception:
                idx_num = len(normalized)
            normalized.append({
                "index": idx_num,
                "path": slot.get("path", ""),
                "name": slot.get("name") or os.path.basename(slot.get("path", ""))
            })
        if not normalized:
            path = item.get("texture_path") or ""
            if path:
                normalized = [{"index": 0, "path": path, "name": os.path.basename(path)}]
        normalized.sort(key=lambda s: (int(s.get("index", 0)) if str(s.get("index", 0)).lstrip("-").isdigit() else 999999, s.get("name", "")))
        item["texture_slots"] = normalized
        return normalized

    def _ensure_item_texture_slots(self, item):
        return self._normalize_texture_slots(item)

    def add_texture_slot_to_item(self, item):
        slots = self._ensure_item_texture_slots(item)
        used_indexes = {int(s.get("index")) for s in slots if isinstance(s.get("index"), (int, float)) and str(s.get("index")).isdigit()}
        next_index = 0
        while next_index in used_indexes:
            next_index += 1

        path = filedialog.askopenfilename(
            title=f"Выбрать PNG для слота #{next_index}",
            filetypes=[("PNG files", "*.png")]
        )
        if not path:
            return False

        slots.append({"index": next_index, "path": path, "name": os.path.basename(path)})
        item["texture_slots"] = slots
        item["texture_path"] = path
        self._refresh_item_texture_row(item)
        self.show_selected_preview()
        return True

    def remove_texture_slot_from_item(self, item, slot):
        slots = item.get("texture_slots") or []
        if not slots:
            return False
        item["texture_slots"] = [s for s in slots if s is not slot]
        if not item.get("texture_slots"):
            item["texture_path"] = ""
        else:
            first_path = next((s.get("path", "") for s in item["texture_slots"] if s.get("path")), "")
            item["texture_path"] = first_path
        self._refresh_item_texture_row(item)
        self.show_selected_preview()
        return True

    def replace_texture_slot_in_item(self, item, slot):
        path = filedialog.askopenfilename(
            title=f"Заменить текстуру #{slot.get('index')}",
            filetypes=[("PNG files", "*.png")]
        )
        if not path:
            return False

        old_path = slot.get("path", "")
        slot["path"] = path
        slot["name"] = os.path.basename(path)
        if not item.get("texture_path") or item.get("texture_path") == old_path:
            item["texture_path"] = path
        self._refresh_item_texture_row(item)
        self.show_selected_preview()
        return True

    def show_selected_textures_window(self):
        item = self._get_selected_item()
        if not item:
            messagebox.showwarning("Текстуры", "Сначала выберите предмет из списка.")
            return

        slots = self._ensure_item_texture_slots(item)
        if not slots:
            path = item.get("texture_path") or ""
            if path:
                slots = [{"index": 0, "path": path, "name": os.path.basename(path)}]
                item["texture_slots"] = slots
        else:
            # Always rebuild from the current item state so reopening the window
            # shows all slots, not a stale copy from the previous open.
            slots = list(item.get("texture_slots") or [])

        win = tk.Toplevel(self.root)
        win.title(f"Текстуры модели: {item.get('id', 'item')}")
        win.geometry("760x520")
        win.configure(bg="#2b2b2b")

        canvas = tk.Canvas(win, bg="#2b2b2b", highlightthickness=0)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg="#2b2b2b")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        top_bar = tk.Frame(inner, bg="#2b2b2b")
        top_bar.pack(fill="x", padx=10, pady=8)
        tk.Button(
            top_bar, text="➕ Добавить новый слот",
            command=lambda: (self.add_texture_slot_to_item(item) and (win.destroy(), self.show_selected_textures_window())),
            bg="#4CAF50", fg="#ffffff"
        ).pack(side="left")

        def refresh_window():
            try:
                win.destroy()
            except Exception:
                pass
            self.show_selected_textures_window()

        for slot in slots:
            path = slot.get("path", "")
            card = tk.Frame(inner, bg="#3c3f41", bd=1, relief="solid", padx=8, pady=8)
            card.pack(fill="x", padx=10, pady=6)
            tk.Label(
                card, text=f"Слот #{slot.get('index')} — {slot.get('name') or os.path.basename(path)}",
                fg="#ffffff", bg="#3c3f41", font=("Arial", 9, "bold")
            ).pack(anchor="w")

            if path and os.path.isfile(path):
                try:
                    if PIL_AVAILABLE:
                        img = Image.open(path).convert("RGBA")
                        img.thumbnail((180, 180), Image.Resampling.NEAREST)
                        photo = ImageTk.PhotoImage(img)
                    else:
                        photo = tk.PhotoImage(file=path)
                    pic = tk.Label(card, image=photo, bg="#3c3f41")
                    pic.image = photo
                    pic.pack(side="left", padx=8, pady=6)
                    button_row = tk.Frame(card, bg="#3c3f41")
                    button_row.pack(side="left", padx=10)
                    tk.Button(
                        button_row, text="Открыть отдельно",
                        command=lambda s=slot: self.open_texture_window(s),
                        bg="#585858", fg="#ffffff"
                    ).pack(side="top", pady=2, fill="x")
                    tk.Button(
                        button_row, text="Заменить",
                        command=lambda s=slot: (self.replace_texture_slot_in_item(item, s) and refresh_window()),
                        bg="#4CAF50", fg="#ffffff"
                    ).pack(side="top", pady=2, fill="x")
                    tk.Button(
                        button_row, text="Удалить",
                        command=lambda s=slot: (self.remove_texture_slot_from_item(item, s) and refresh_window()),
                        bg="#f44336", fg="#ffffff"
                    ).pack(side="top", pady=2, fill="x")
                except Exception:
                    tk.Label(card, text="Не удалось показать PNG", fg="#ff7777", bg="#3c3f41").pack()
            else:
                tk.Label(card, text="PNG не найден", fg="#aaaaaa", bg="#3c3f41").pack(anchor="w")
                button_row = tk.Frame(card, bg="#3c3f41")
                button_row.pack(side="left", padx=10)
                tk.Button(
                    button_row, text="Заменить",
                    command=lambda s=slot: (self.replace_texture_slot_in_item(item, s) and refresh_window()),
                    bg="#4CAF50", fg="#ffffff"
                ).pack(side="top", pady=2, fill="x")
                tk.Button(
                    button_row, text="Удалить",
                    command=lambda s=slot: (self.remove_texture_slot_from_item(item, s) and refresh_window()),
                    bg="#f44336", fg="#ffffff"
                ).pack(side="top", pady=2, fill="x")

    def _texture_label(self, texture_path):
        if not texture_path or not os.path.isfile(texture_path):
            return "—"
        return os.path.basename(texture_path)

    def _get_selected_item(self):
        selected = self.tree.selection()
        if not selected:
            return None
        item_id = self.tree.item(selected[0], "values")[0]
        for item in self.items_list:
            if item.get("id") == item_id:
                return item
        return None

    def replace_selected_texture(self):
        item = self._get_selected_item()
        if not item:
            messagebox.showwarning("Внимание", "Сначала выберите предмет из списка.")
            return
        file_path = filedialog.askopenfilename(title="Выберите новую текстуру .png", filetypes=[("PNG files", "*.png")])
        if not file_path:
            return
        item["texture_path"] = file_path
        slots = item.get("texture_slots") or []
        if slots:
            slots[0]["path"] = file_path
            slots[0]["name"] = os.path.basename(file_path)
        else:
            item["texture_slots"] = [{"index": 0, "path": file_path, "name": os.path.basename(file_path)}]
        self.tree.item(self.tree.selection()[0], values=(item["id"], self._texture_label(file_path), item["base"], item["cmd"]))
        self.show_selected_preview()
        messagebox.showinfo("Готово", "Текстура предмета обновлена.")

    def replace_selected_model(self):
        item = self._get_selected_item()
        if not item:
            messagebox.showwarning("Внимание", "Сначала выберите предмет из списка.")
            return
        file_path = filedialog.askopenfilename(title="Выберите новую модель .json", filetypes=[("JSON files", "*.json")])
        if not file_path:
            return
        item["model_path"] = file_path
        self.tree.item(self.tree.selection()[0], values=(item["id"], self._texture_label(item.get("texture_path", "")), item["base"], item["cmd"]))
        self.show_selected_preview()
        messagebox.showinfo("Готово", "Модель предмета обновлена.")

    def on_tree_select(self, event=None):
        self.show_selected_preview()

    def show_selected_preview(self):
        if self.preview_after_id is not None:
            try:
                self.root.after_cancel(self.preview_after_id)
            except Exception:
                pass
            self.preview_after_id = None

        selected = self.tree.selection()
        if not selected:
            self.preview_item = None
            self._clear_preview()
            return

        item_id = self.tree.item(selected[0], "values")[0]
        for item in self.items_list:
            if item.get("id") == item_id:
                self.preview_item = item
                self.preview_angle = 25.0
                self._render_preview(item)
                return

        self.preview_item = None
        self._clear_preview()

    def _clear_preview(self):
        self.preview_canvas.delete("all")
        self.preview_canvas.create_text(140, 70, text="Нет превью", fill="#aaaaaa", font=("Arial", 10, "bold"))

    def _resolve_texture_for_preview(self, item):
        texture_path = item.get("texture_path") or ""
        if texture_path and os.path.isfile(texture_path):
            return texture_path

        slots = item.get("texture_slots") or []
        if slots:
            for slot in slots:
                slot_path = slot.get("path") or ""
                if slot_path and os.path.isfile(slot_path):
                    return slot_path

        model_path = item.get("model_path") or ""
        if model_path and os.path.isfile(model_path):
            try:
                with open(model_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception:
                return ""

            textures = data.get("textures", {})
            if isinstance(textures, dict):
                for key in ("layer0", "texture", "all"):
                    value = textures.get(key)
                    if isinstance(value, str):
                        texture_candidate = self._guess_texture_from_reference(value, model_path)
                        if texture_candidate and os.path.isfile(texture_candidate):
                            return texture_candidate
                for value in textures.values():
                    if isinstance(value, str):
                        texture_candidate = self._guess_texture_from_reference(value, model_path)
                        if texture_candidate and os.path.isfile(texture_candidate):
                            return texture_candidate

        return ""

    def _guess_texture_from_reference(self, texture_ref, model_path):
        if not texture_ref:
            return ""
        texture_ref = texture_ref.replace("minecraft:", "")
        if texture_ref.startswith("item/"):
            texture_ref = texture_ref[5:]
        if texture_ref.startswith("models/"):
            texture_ref = texture_ref[7:]
        if texture_ref.startswith("textures/"):
            texture_ref = texture_ref[9:]

        base_name = os.path.splitext(os.path.basename(model_path))[0]
        texture_name = texture_ref.split("/")[-1] or base_name

        candidates = []
        if model_path and os.path.isfile(model_path):
            model_dir = os.path.dirname(model_path)
            candidates.append(os.path.join(model_dir, f"{texture_name}.png"))
            candidates.append(os.path.join(model_dir, os.pardir, os.pardir, "textures", "item", f"{texture_name}.png"))
            candidates.append(os.path.join(model_dir, os.pardir, os.pardir, os.pardir, "textures", "item", f"{texture_name}.png"))
            candidates.append(os.path.join(model_dir, "..", "..", "textures", "item", f"{texture_name}.png"))
            candidates.append(os.path.join(model_dir, "..", "..", "..", "textures", "item", f"{texture_name}.png"))
            candidates.append(os.path.join(os.getcwd(), "assets", "minecraft", "textures", "item", f"{texture_name}.png"))
            candidates.append(os.path.join(os.getcwd(), "assets", "minecraft", "textures", "item", f"{base_name}.png"))
            candidates.append(os.path.join(os.getcwd(), "Imported_RP_Work", "assets", "minecraft", "textures", "item", f"{texture_name}.png"))
            candidates.append(os.path.join(os.getcwd(), "Imported_RP_Work", "assets", "minecraft", "textures", "item", f"{base_name}.png"))
            candidates.append(os.path.join(os.getcwd(), "Imported_RP_Work", "textures", "item", f"{texture_name}.png"))
            candidates.append(os.path.join(os.getcwd(), "Imported_RP_Work", "textures", "item", f"{base_name}.png"))

        for candidate in candidates:
            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

        search_roots = []
        for root in [os.getcwd(), os.path.join(os.getcwd(), "Imported_RP_Work")]:
            if os.path.isdir(root):
                search_roots.append(root)
        for root in search_roots:
            for current_root, _, files in os.walk(root):
                for file_name in files:
                    if file_name.lower().endswith(".png") and (file_name[:-4].lower() == texture_name.lower() or file_name[:-4].lower() == base_name.lower()):
                        return os.path.abspath(os.path.join(current_root, file_name))
        return ""

    # --------------------------- 3D preview ---------------------------
    def _model_json(self, path):
        if not path or not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _apply_texture_slots_to_model(self, item, item_id, model_path, model_out_path, textures_item_dir):
        """Copy every selected texture and bind it to the model's texture slot."""
        model_data = self._model_json(model_path)
        if not isinstance(model_data, dict):
            model_data = {}

        textures = model_data.get("textures", {})
        if not isinstance(textures, dict):
            textures = {}

        slots = self._normalize_texture_slots(item)
        exported_refs = {}

        for pos, slot in enumerate(slots):
            slot_path = slot.get("path") or ""
            slot_idx = slot.get("index", pos)
            if not slot_path or not os.path.isfile(slot_path):
                continue

            slot_key = str(slot_idx)
            safe_key = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in slot_key)
            slot_name = item_id if safe_key in ("0", "layer0") else f"{item_id}_slot{safe_key}"
            out_path = os.path.join(textures_item_dir, f"{slot_name}.png")
            try:
                shutil.copy2(slot_path, out_path)
            except Exception:
                continue
            exported_refs[slot_key] = f"minecraft:item/{slot_name}"

        if not exported_refs and item.get("texture_path") and os.path.isfile(item["texture_path"]):
            out_path = os.path.join(textures_item_dir, f"{item_id}.png")
            shutil.copy2(item["texture_path"], out_path)
            exported_refs["0"] = f"minecraft:item/{item_id}"

        updated = {}
        for key, ref in textures.items():
            key_str = str(key)
            if key_str in exported_refs:
                updated[key_str] = exported_refs[key_str]
            elif key_str in ("layer0", "texture", "all") and exported_refs.get("0"):
                updated[key_str] = exported_refs["0"]
            else:
                updated[key_str] = ref

        # Ensure every selected slot exists in the exported model.
        for key, ref in exported_refs.items():
            if key not in updated:
                updated[key] = ref

        # Also expose a plain layer0 alias for the first slot so simple models render.
        if exported_refs.get("0") and "layer0" not in updated:
            updated["layer0"] = exported_refs["0"]
        if exported_refs.get("0") and "0" not in updated:
            updated["0"] = exported_refs["0"]
        if not updated and exported_refs.get("0"):
            updated["layer0"] = exported_refs["0"]

        model_data["textures"] = updated

        # Convert our internal Blockbench placeholder names into exported refs.
        for key, value in list(model_data["textures"].items()):
            if isinstance(value, str) and value.startswith("minecraft:item/__BLOCKBENCH_SLOT_"):
                slot_key = value.split("__BLOCKBENCH_SLOT_", 1)[1].split("__", 1)[0]
                if slot_key in exported_refs:
                    model_data["textures"][key] = exported_refs[slot_key]

        with open(model_out_path, "w", encoding="utf-8") as f:
            json.dump(model_data, f, indent=4, ensure_ascii=False)

    def _resolve_model_texture_map(self, item):
        """Resolve every texture declared by a Blockbench/Minecraft JSON model.

        Blockbench commonly exports:
            "textures": {"0": "namespace:item/body", "1": "namespace:item/detail"}
        and faces refer to them as "#0" / "#1".
        We keep the mapping per texture slot instead of applying one PNG to every face.
        """
        model_path = item.get("model_path") or ""
        data = self._model_json(model_path)
        textures = data.get("textures", {}) if isinstance(data, dict) else {}
        if not isinstance(textures, dict):
            textures = {}
        result = {}
        direct = item.get("texture_path") or ""
        for slot in item.get("texture_slots") or []:
            slot_path = slot.get("path") or ""
            slot_idx = slot.get("index")
            if slot_path and os.path.isfile(slot_path) and slot_idx is not None:
                result[str(slot_idx)] = slot_path
        # A manually selected PNG is used as a fallback only when the model has
        # one texture slot (otherwise it would incorrectly replace all Blockbench textures).
        for key, ref in textures.items():
            if not isinstance(ref, str):
                continue
            resolved = ref
            seen=set()
            for _ in range(16):
                if not isinstance(resolved, str) or not resolved.startswith("#"):
                    break
                token=resolved[1:]
                if token in seen:
                    resolved=""
                    break
                seen.add(token)
                resolved=textures.get(token, "")
            found=self._guess_texture_from_reference(resolved, model_path) if resolved else ""
            if found and os.path.isfile(found):
                result[str(key)] = found
        if len(textures) <= 1 and direct and os.path.isfile(direct):
            key = next(iter(textures.keys()), "layer0")
            result[str(key)] = direct
        return result

    def _preview_texture(self, item, ref=None):
        model_path = item.get("model_path") or ""
        data = self._model_json(model_path)
        textures = data.get("textures", {}) if isinstance(data, dict) else {}
        if not isinstance(textures, dict):
            textures = {}
        direct = item.get("texture_path") or ""
        if not ref:
            ref = textures.get("layer0") or textures.get("all") or textures.get("texture")
        if isinstance(ref, str) and ref.startswith("#"):
            ref = textures.get(ref[1:], "")
        for _ in range(16):
            if not isinstance(ref, str) or not ref.startswith("#"):
                break
            ref = textures.get(ref[1:], "")
        # If the model has only one texture slot, the selected PNG overrides it.
        if len(textures) <= 1 and direct and os.path.isfile(direct):
            return direct
        slots = item.get("texture_slots") or []
        if slots:
            for slot in slots:
                slot_path = slot.get("path") or ""
                if slot_path and os.path.isfile(slot_path):
                    return slot_path
        if isinstance(ref, str) and ref:
            found = self._guess_texture_from_reference(ref, model_path)
            if found and os.path.isfile(found):
                return found
        return self._resolve_texture_for_preview(item)

    @staticmethod
    def _solve8(m, b):
        a=[list(row)+[b[i]] for i,row in enumerate(m)]
        n=8
        for c in range(n):
            r=max(range(c,n), key=lambda q: abs(a[q][c]))
            if abs(a[r][c])<1e-10: return None
            a[c],a[r]=a[r],a[c]
            d=a[c][c]
            for j in range(c,n+1): a[c][j]/=d
            for r in range(n):
                if r==c: continue
                k=a[r][c]
                if abs(k)>1e-12:
                    for j in range(c,n+1): a[r][j]-=k*a[c][j]
        return [a[i][n] for i in range(n)]

    def _minecraft_face_vertices(self, e, face_name):
        """Вершины грани в том же порядке, в котором Minecraft читает UV.

        Для Java item/block JSON порядок вершин важен: просто перечислить
        четыре угла куба недостаточно, потому что south/west/up/down имеют
        другое направление UV. Здесь UV-углы идут как TL, TR, BR, BL.
        """
        f = e.get("from", [0, 0, 0])
        t = e.get("to", [16, 16, 16])
        x1, y1, z1 = map(float, f)
        x2, y2, z2 = map(float, t)
        return {
            # UV: [u1,v1] -> [u2,v1] -> [u2,v2] -> [u1,v2]
            "north": [(x2,y1,z1), (x1,y1,z1), (x1,y2,z1), (x2,y2,z1)],
            "south": [(x1,y1,z2), (x2,y1,z2), (x2,y2,z2), (x1,y2,z2)],
            "west":  [(x1,y1,z1), (x1,y1,z2), (x1,y2,z2), (x1,y2,z1)],
            "east":  [(x2,y1,z2), (x2,y1,z1), (x2,y2,z1), (x2,y2,z2)],
            "up":    [(x1,y1,z1), (x2,y1,z1), (x2,y1,z2), (x1,y1,z2)],
            "down":  [(x1,y2,z2), (x2,y2,z2), (x2,y2,z1), (x1,y2,z1)],
        }.get(face_name, [])

    def _apply_element_rotation(self, p, rotation):
        """Minecraft BlockElement rotation: axis x/y/z, origin, angle."""
        if not isinstance(rotation, dict):
            return p
        axis = rotation.get("axis")
        angle = float(rotation.get("angle", 0) or 0)
        if axis not in ("x", "y", "z") or abs(angle) < 1e-9:
            return p
        origin = rotation.get("origin", [8, 8, 8])
        ox, oy, oz = map(float, origin)
        x, y, z = map(float, p)
        x -= ox; y -= oy; z -= oz
        a = radians(angle)
        ca, sa = cos(a), sin(a)
        if axis == "x":
            y, z = y*ca - z*sa, y*sa + z*ca
        elif axis == "y":
            x, z = x*ca + z*sa, -x*sa + z*ca
        else:
            x, y = x*ca - y*sa, x*sa + y*ca
        return (x + ox, y + oy, z + oz)

    def _rotate_uv_image(self, image, rotation):
        rot = int(rotation or 0) % 360
        if rot == 90:
            return image.transpose(Image.Transpose.ROTATE_90)
        if rot == 180:
            return image.transpose(Image.Transpose.ROTATE_180)
        if rot == 270:
            return image.transpose(Image.Transpose.ROTATE_270)
        return image

    def _warp_quad(self, target, texture, points, uv, face_rotation=0, texture_size=None):
        """Точное наложение Minecraft UV на экранную грань."""
        if not (PIL_AVAILABLE and CV_AVAILABLE):
            return
        try:
            texture = texture.convert("RGBA")
            tw, th = texture.size
            # В Java JSON texture_size задаёт систему координат UV.
            # Если его нет, Minecraft использует 16x16.
            if not isinstance(texture_size, (list, tuple)) or len(texture_size) != 2:
                texture_size = [16, 16]
            model_tw = float(texture_size[0] or 16)
            model_th = float(texture_size[1] or 16)
            if not isinstance(uv, (list, tuple)) or len(uv) != 4:
                uv = [0, 0, model_tw, model_th]
            u1,v1,u2,v2 = [float(x) for x in uv]

            # Переводим UV из координат модели в реальные пиксели PNG.
            sx = tw / model_tw
            sy = th / model_th
            u1 *= sx; u2 *= sx; v1 *= sy; v2 *= sy

            # Отрицательные/перевёрнутые UV в Minecraft являются зеркальными.
            flip_x = u2 < u1
            flip_y = v2 < v1
            left, right = sorted((u1, u2))
            top, bottom = sorted((v1, v2))

            # Для превью ограничиваем crop размером изображения, но не меняем
            # геометрию грани. Это особенно важно для texture_size != 16.
            left=max(0,min(tw-1,left)); top=max(0,min(th-1,top))
            right=max(left+1,min(tw,right)); bottom=max(top+1,min(th,bottom))
            if right-left < 0.01 or bottom-top < 0.01:
                return

            crop = texture.crop((int(math.floor(left)), int(math.floor(top)),
                                 max(int(math.ceil(right)), int(math.floor(left))+1),
                                 max(int(math.ceil(bottom)), int(math.floor(top))+1)))
            if flip_x:
                crop = crop.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            if flip_y:
                crop = crop.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
            crop = self._rotate_uv_image(crop, face_rotation)

            src=np.float32([[0,0],[crop.width-1,0],[crop.width-1,crop.height-1],[0,crop.height-1]])
            dst=np.float32([[float(x),float(y)] for x,y in points])
            H=cv2.getPerspectiveTransform(src,dst)
            minx=max(0,int(math.floor(dst[:,0].min()))-2)
            miny=max(0,int(math.floor(dst[:,1].min()))-2)
            maxx=min(target.width,int(math.ceil(dst[:,0].max()))+3)
            maxy=min(target.height,int(math.ceil(dst[:,1].max()))+3)
            if maxx<=minx or maxy<=miny:return
            T=np.array([[1.,0.,-minx],[0.,1.,-miny],[0.,0.,1.]],dtype=np.float64)
            rgba=np.array(crop,dtype=np.uint8)
            warped=cv2.warpPerspective(rgba,T@H,(maxx-minx,maxy-miny),flags=cv2.INTER_NEAREST,borderMode=cv2.BORDER_CONSTANT,borderValue=(0,0,0,0))
            mask=np.zeros((maxy-miny,maxx-minx),dtype=np.uint8)
            poly=np.int32([[round(x-minx),round(y-miny)] for x,y in points])
            cv2.fillConvexPoly(mask,poly,255)
            warped[:,:,3]=((warped[:,:,3].astype(np.uint16)*mask.astype(np.uint16))//255).astype(np.uint8)
            target.alpha_composite(Image.fromarray(warped,"RGBA"),(minx,miny))
        except Exception:
            return

    def _face_vertices(self, e, face):
        return self._minecraft_face_vertices(e, face)

    def _project_point3(self, p, yaw, pitch, cx, cy, scale):
        """Orthographic Minecraft-like preview projection.
        Returns screen x/y and camera-space depth. Keeping depth separately
        lets the renderer draw intersecting/side faces without them breaking.
        """
        x, y, z = map(float, p)
        y = -y
        ca, sa = cos(yaw), sin(yaw)
        x, z = x*ca - z*sa, x*sa + z*ca
        ca, sa = cos(pitch), sin(pitch)
        y, z = y*ca - z*sa, y*sa + z*ca
        return cx + x*scale, cy - y*scale, z

    def _project_preview(self,p,yaw,pitch,cx,cy,scale):
        x,y,z = self._project_point3(p,yaw,pitch,cx,cy,scale)
        return x,y

    def _minecraft_uv_corners(self, uv, texture_size, tex_size, rotation=0):
        """Return four pixel UV points corresponding to the four Minecraft
        face vertices.  The important part is that UV rotation changes the
        mapping of the corners, not the geometry. This avoids the broken side
        faces caused by rotating an already-cropped image before perspective
        warping.
        """
        tw, th = tex_size
        if not isinstance(texture_size, (list, tuple)) or len(texture_size) != 2:
            texture_size = (16, 16)
        mw, mh = float(texture_size[0] or 16), float(texture_size[1] or 16)
        if not isinstance(uv, (list, tuple)) or len(uv) != 4:
            uv = (0, 0, mw, mh)
        u1,v1,u2,v2 = map(float, uv)
        sx, sy = tw/mw, th/mh
        corners = [
            (u1*sx, v1*sy),
            (u2*sx, v1*sy),
            (u2*sx, v2*sy),
            (u1*sx, v2*sy),
        ]
        # Minecraft face rotation is clockwise when viewed from the face.
        rot = int(rotation or 0) % 360
        if rot == 90:
            corners = [corners[3], corners[0], corners[1], corners[2]]
        elif rot == 180:
            corners = [corners[2], corners[3], corners[0], corners[1]]
        elif rot == 270:
            corners = [corners[1], corners[2], corners[3], corners[0]]
        return corners

    def _raster_triangle(self, canvas, zbuf, tex, pts, uvs, shade=1.0):
        """Fast nearest-neighbour affine texture rasterizer.
        The preview uses an orthographic camera, so affine UV interpolation is
        exact for each triangle. A per-pixel depth buffer fixes side-face
        overlap at all rotation angles.
        """
        if np is None:
            return
        h,w = canvas.shape[:2]
        p=np.asarray(pts,dtype=np.float32)
        uv=np.asarray(uvs,dtype=np.float32)
        minx=max(0,int(np.floor(p[:,0].min())))
        maxx=min(w-1,int(np.ceil(p[:,0].max())))
        miny=max(0,int(np.floor(p[:,1].min())))
        maxy=min(h-1,int(np.ceil(p[:,1].max())))
        if maxx<minx or maxy<miny: return
        x0,y0=p[0]; x1,y1=p[1]; x2,y2=p[2]
        den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
        if abs(float(den))<1e-7: return
        yy,xx=np.mgrid[miny:maxy+1,minx:maxx+1]
        a=((y1-y2)*(xx-x2)+(x2-x1)*(yy-y2))/den
        b=((y2-y0)*(xx-x2)+(x0-x2)*(yy-y2))/den
        c=1.0-a-b
        inside=(a>=-1e-4)&(b>=-1e-4)&(c>=-1e-4)
        if not inside.any(): return

        # Affine UV interpolation.
        uu=a*uv[0,0]+b*uv[1,0]+c*uv[2,0]
        vv=a*uv[0,1]+b*uv[1,1]+c*uv[2,1]
        tex_h,tex_w=tex.shape[:2]
        ui=np.clip(np.rint(uu).astype(np.int32),0,tex_w-1)
        vi=np.clip(np.rint(vv).astype(np.int32),0,tex_h-1)
        sampled=tex[vi,ui].copy()
        if shade != 1.0:
            sampled[:,:,:3]=(sampled[:,:,:3].astype(np.float32)*shade).astype(np.uint8)
        alpha=sampled[:,:,3]
        # Only overwrite where the triangle is closer to camera and texture is
        # actually opaque. Semi-transparent pixels are alpha-composited below.
        # Camera depth is supplied separately by the caller in canvas depth.
        return (minx,maxx,miny,maxy,inside,sampled,alpha)

    def _draw_textured_face(self, canvas, zbuf, tex_img, pts, depths, uv_corners, shade=1.0):
        if np is None or tex_img is None: return
        tex=np.asarray(tex_img.convert("RGBA"),dtype=np.uint8)
        p=[(float(x),float(y)) for x,y in pts]
        # Split quad exactly along the same diagonal every time.
        triangles=((0,1,2),(0,2,3))
        for tri in triangles:
            ids=list(tri)
            result=self._raster_triangle(canvas,zbuf,tex,[p[i] for i in ids],[uv_corners[i] for i in ids],shade)
            if result is None: continue
            minx,maxx,miny,maxy,inside,sampled,alpha=result
            depth_vals=np.asarray([depths[i] for i in ids],dtype=np.float32)
            # Same barycentric interpolation used for UVs.
            yy,xx=np.mgrid[miny:maxy+1,minx:maxx+1]
            x0,y0=np.asarray(p[ids[0]],dtype=np.float32)
            x1,y1=np.asarray(p[ids[1]],dtype=np.float32)
            x2,y2=np.asarray(p[ids[2]],dtype=np.float32)
            den=(y1-y2)*(x0-x2)+(x2-x1)*(y0-y2)
            a=((y1-y2)*(xx-x2)+(x2-x1)*(yy-y2))/den
            b=((y2-y0)*(xx-x2)+(x0-x2)*(yy-y2))/den
            c=1.0-a-b
            depth=a*depth_vals[0]+b*depth_vals[1]+c*depth_vals[2]
            current=zbuf[miny:maxy+1,minx:maxx+1]
            valid=inside & (depth < current)
            if not valid.any(): continue
            # Alpha composite against current canvas. Fully transparent texels
            # do not claim depth, which prevents holes from cutting side faces.
            valid &= alpha>0
            if not valid.any(): continue
            dst=canvas[miny:maxy+1,minx:maxx+1]
            al=(alpha.astype(np.float32)/255.0)
            aa=(al*valid.astype(np.float32))[...,None]
            dst_rgb=dst[:,:,:3].astype(np.float32)
            src_rgb=sampled[:,:,:3].astype(np.float32)
            dst[:,:,:3]=np.clip(src_rgb*aa + dst_rgb*(1-aa),0,255).astype(np.uint8)
            dst[:,:,3]=np.clip((aa[:,:,0] + dst[:,:,3].astype(np.float32)/255.0*(1-aa[:,:,0]))*255,0,255).astype(np.uint8)
            current[valid]=depth[valid]

    def _render_3d_preview(self,item,w,h):
        if not PIL_AVAILABLE: return None
        data=self._model_json(item.get("model_path") or "")
        elements=data.get("elements") if isinstance(data,dict) else None
        generated_preview=not isinstance(elements,list) or not elements
        if generated_preview:
            elements=[{
                "from":[0,0,7.72], "to":[16,16,8.28],
                "faces":{
                    "north":{"texture":"__FULL__"}, "south":{"texture":"__FULL__"},
                    "west":{"texture":"__EDGE__"}, "east":{"texture":"__EDGE__"},
                    "up":{"texture":"__EDGE__"}, "down":{"texture":"__EDGE__"}
                }}]

        # RGBA canvas + real depth buffer. This is deliberately separate from
        # the old cv2 perspective warp: that approach made thin side faces tear
        # or receive the wrong texture when the model rotated.
        canvas=np.zeros((h,w,4),dtype=np.uint8) if np is not None else None
        if canvas is None:
            return None
        yaw=radians(self.preview_angle); pitch=radians(-22)
        cx,cy=w/2,h/2+2
        ext=[]
        for e in elements:
            f=e.get("from",[0,0,0]); t=e.get("to",[16,16,16])
            ext += [max(abs(float(v)-8) for v in f),max(abs(float(v)-8) for v in t)]
        scale=min(w,h)*0.38/max(ext+[8])
        zbuf=np.full((h,w),np.inf,dtype=np.float32)
        faces=[]
        for e in elements:
            for name in ("north","south","west","east","up","down"):
                face=e.get("faces",{}).get(name) if isinstance(e.get("faces"),dict) else None
                if not isinstance(face,dict): continue
                raw=self._face_vertices(e,name)
                elem_rot=e.get("rotation") if isinstance(e.get("rotation"),dict) else None
                if elem_rot: raw=[self._apply_element_rotation(v,elem_rot) for v in raw]
                projected=[]; depths=[]
                for x,y,z in raw:
                    sx,sy,sz=self._project_point3((x-8,y-8,z-8),yaw,pitch,cx,cy,scale)
                    projected.append((sx,sy)); depths.append(sz)
                faces.append((sum(depths)/4.0,name,face,projected,depths))
        # Painter order is only a fallback; the z-buffer is authoritative.
        faces.sort(key=lambda q:q[0],reverse=True)

        selected_texture=item.get("texture_path") or ""
        selected_img=_read_texture_png(selected_texture) if selected_texture and os.path.isfile(selected_texture) else None
        texture_map=self._resolve_model_texture_map(item)
        texture_images={k:_read_texture_png(v) for k,v in texture_map.items() if v and os.path.isfile(v)}
        texture_size=data.get("texture_size",[16,16]) if isinstance(data,dict) else [16,16]
        light={"up":1.0,"north":.92,"east":.82,"south":.76,"west":.65,"down":.52}

        # Shadow.
        yy,xx=np.mgrid[0:h,0:w]
        ex=(xx-cx)/(max(1,scale*8)); ey=(yy-(cy+scale*9))/(max(1,scale*1.8))
        shadow=np.exp(-(ex*ex+ey*ey)*2.2)*0.30
        shadow_mask=(shadow*255).astype(np.uint8)
        canvas[:,:,0]=canvas[:,:,1]=canvas[:,:,2]=0
        canvas[:,:,3]=shadow_mask

        for _,name,face,pts,depths in faces:
            if generated_preview and selected_img is not None:
                if name in ("north","south"):
                    tex=selected_img
                    uv=[(0,0),(tex.width-1,0),(tex.width-1,tex.height-1),(0,tex.height-1)]
                else:
                    # Minecraft's generated-item extrusion gets side pixels from
                    # the sprite boundary. Use the nearest non-transparent edge
                    # rather than blindly taking column 0, which caused white
                    # broken sides for sprites with transparent padding.
                    tex=selected_img
                    a=np.asarray(tex)[:,:,3]
                    ys,xs=np.where(a>8)
                    if len(xs):
                        if name in ("west","east"):
                            edge_x=int(xs.min() if name=="west" else xs.max())
                            edge=tex.crop((edge_x,0,edge_x+1,tex.height))
                        else:
                            edge_y=int(ys.min() if name=="up" else ys.max())
                            edge=tex.crop((0,edge_y,tex.width,edge_y+1))
                    else:
                        edge=tex.crop((0,0,max(1,tex.width),max(1,tex.height)))
                    tex=edge
                    uv=[(0,0),(tex.width-1,0),(tex.width-1,tex.height-1),(0,tex.height-1)]
                self._draw_textured_face(canvas,zbuf,tex,pts,depths,uv,light.get(name,.8))
            else:
                face_ref=face.get("texture")
                tex=None
                # Resolve Blockbench texture slots such as #0, #1, #side.
                if isinstance(face_ref,str) and face_ref.startswith("#"):
                    slot=face_ref[1:]
                    tex=texture_images.get(slot)
                elif isinstance(face_ref,str) and face_ref in texture_images:
                    tex=texture_images.get(face_ref)
                # For models with a single texture, keep the manually selected PNG
                # as the final fallback.
                if tex is None and len(texture_images)<=1:
                    tex=selected_img
                if tex is None:
                    tex_path=self._preview_texture(item,face_ref)
                    tex=_read_texture_png(tex_path) if tex_path else None
                if tex is not None:
                    uv=face.get("uv")
                    uv_corners=self._minecraft_uv_corners(uv,texture_size,tex.size,face.get("rotation",0))
                    self._draw_textured_face(canvas,zbuf,tex,pts,depths,uv_corners,light.get(name,.8))
                else:
                    # Solid fallback if no texture can be found.
                    col=int(160*light.get(name,.8))
                    poly=Image.new("RGBA",(w,h),(col,col,col,255))
                    mask=Image.new("L",(w,h),0)
                    ImageDraw.Draw(mask).polygon([(int(x),int(y)) for x,y in pts],fill=255)
                    arr=np.asarray(poly).copy(); ma=np.asarray(mask)
                    canvas[ma>0]=arr[ma>0]

            # Thin dark outline helps the Minecraft-style silhouette without
            # corrupting the textured side faces.
            # Drawn after all texture mapping, only one pixel wide.
            outline=ImageDraw.Draw(Image.fromarray(canvas,"RGBA"))

        # Rebuild a small outline on top without touching texture interiors.
        out=Image.fromarray(canvas,"RGBA")
        od=ImageDraw.Draw(out)
        for _,name,face,pts,depths in faces:
            od.line([(int(x),int(y)) for x,y in pts+[pts[0]]],fill=(15,15,15,170),width=1)
        return out

    def _render_preview(self,item):
        self.preview_canvas.delete("all")
        cw=max(280,self.preview_canvas.winfo_width() or 280)
        ch=max(140,self.preview_canvas.winfo_height() or 140)
        split=cw//2; top=22; bottom=ch-12; cy=(top+bottom)//2
        self.preview_canvas.create_rectangle(10,bottom-18,cw-10,bottom,fill="#6b6b6b",outline="#505050")
        self.preview_canvas.create_line(split,top,split,bottom-18,fill="#555555")
        self.preview_canvas.create_text(split//2,12,text="Инвентарь",fill="#fff",font=("Arial",9,"bold"))
        self.preview_canvas.create_text(split+(cw-split)//2,12,text="Выброшенный предмет",fill="#fff",font=("Arial",9,"bold"))

        # Left: обычная текстура через Tkinter. PIL здесь НЕ нужен.
        tex_path=self._resolve_texture_for_preview(item)
        if tex_path and os.path.isfile(tex_path):
            try:
                tk_img=tk.PhotoImage(file=tex_path)
                # Удерживаем ссылку, иначе Tk удалит изображение.
                max_side=56
                factor=max(1, int(max(tk_img.width(), tk_img.height())/max_side))
                if factor>1:
                    tk_img=tk_img.subsample(factor, factor)
                self.preview_photo=tk_img
                self.preview_canvas.create_image(split//2,cy,image=self.preview_photo,anchor="center")
            except Exception:
                self.preview_canvas.create_text(split//2,cy,text=item.get("id","item"),fill="#fff",font=("Arial",10,"bold"))
        else:
            self.preview_canvas.create_text(split//2,cy,text=item.get("id","item"),fill="#fff",font=("Arial",10,"bold"))

        # Right: только здесь используется Pillow: JSON-модель + наложение PNG + вращение.
        if PIL_AVAILABLE:
            try:
                rendered=self._render_3d_preview(item,max(100,cw-split-20),max(80,ch-35))
                if rendered is not None:
                    self.preview_photo_animated=ImageTk.PhotoImage(rendered)
                    self.preview_canvas.create_image(split+(cw-split)//2,cy,image=self.preview_photo_animated,anchor="center")
                else:
                    self.preview_canvas.create_text(split+(cw-split)//2,cy,text="Нет модели",fill="#aaa",font=("Arial",8))
            except Exception as exc:
                self.preview_canvas.create_text(split+(cw-split)//2,cy,text="Ошибка 3D превью",fill="#aaa",font=("Arial",8))
        else:
            self.preview_canvas.create_text(split+(cw-split)//2,cy,text="Установите Pillow",fill="#aaa",font=("Arial",8))

        if self.preview_item and self.preview_item.get("id")==item.get("id"):
            self.preview_angle=(self.preview_angle+5.0)%360.0
            self.preview_after_id=self.root.after(50,self._animate_preview)

    def _animate_preview(self):
        self.preview_after_id=None
        if self.preview_item:
            self._render_preview(self.preview_item)

    def add_item_to_list(self):
        item_id = self.entry_id.get().strip()
        item_name = self.entry_name.get().strip()
        vanilla_base = self.entry_base.get().strip()
        cmd_val = self.entry_cmd.get().strip()

        if not item_id or not vanilla_base or not cmd_val:
            messagebox.showerror("Ошибка", "Заполните ID, базовый предмет и CustomModelData!")
            return

        if any(i['id'] == item_id for i in self.items_list):
            messagebox.showerror("Ошибка", f"Предмет с ID '{item_id}' уже есть в списке!")
            return

        item_data = {
            "id": item_id,
            "name": item_name,
            "base": vanilla_base,
            "cmd": int(cmd_val),
            "model_path": self.model_path,
            "texture_path": self.texture_path,
            "texture_slots": [dict(slot) for slot in self.texture_slots]
        }

        self.items_list.append(item_data)
        texture_label = self._texture_label(self.texture_path)
        self.tree.insert("", "end", values=(item_id, texture_label, vanilla_base, cmd_val))
        self.show_selected_preview()

        self.entry_id.delete(0, tk.END)
        self.model_path = ""
        self.texture_path = ""
        self.texture_slots = []
        self.bbmodel_source = ""
        self.lbl_model.config(text="Не выбрано", fg="#aaaaaa")
        self.lbl_texture.config(text="Не выбрано", fg="#aaaaaa")
        self._refresh_item_texture_editor()
        messagebox.showinfo("Успешно", f"Предмет {item_id} добавлен в очередь!")

    def remove_item(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("Внимание", "Выберите предмет в списке для удаления.")
            return
        for sel in selected_items:
            vals = self.tree.item(sel, "values")
            item_id = vals[0]
            self.items_list = [i for i in self.items_list if i['id'] != item_id]
            self.tree.delete(sel)

    def build_java(self):
        if not self.items_list:
            messagebox.showerror("Ошибка", "Список предметов пуст! Добавьте хотя бы один предмет.")
            return

        selected_version = self.version_combobox.get()
        is_new_format = "Классический" not in selected_version

        pack_dir = "Generated_Java_RP"
        assets_dir = os.path.join(pack_dir, "assets", "minecraft")
        models_item_dir = os.path.join(assets_dir, "models", "item")
        textures_item_dir = os.path.join(assets_dir, "textures", "item")
        items_def_dir = os.path.join(assets_dir, "items")

        if os.path.exists(pack_dir):
            shutil.rmtree(pack_dir)

        os.makedirs(models_item_dir, exist_ok=True)
        os.makedirs(textures_item_dir, exist_ok=True)
        if is_new_format:
            os.makedirs(items_def_dir, exist_ok=True)

        if selected_version.startswith("26.1.2"):
            pack_format = 84
        elif is_new_format:
            pack_format = 46
        else:
            pack_format = 34
        mcmeta_path = os.path.join(pack_dir, "pack.mcmeta")

        # С версии 1.21.9 (и весь ряд 26.x) Minecraft использует min_format/max_format
        # вместо старого одиночного pack_format. Старое поле в новых версиях
        # приводит к тому, что пак считается несовместимым и НЕ загружается целиком.
        uses_range_format = selected_version.startswith("26.") or pack_format >= 80

        if uses_range_format:
            mcmeta_data = {
                "pack": {
                    "description": f"Multi-Item Java RP Pack ({selected_version})",
                    "min_format": pack_format,
                    "max_format": 999
                }
            }
        else:
            mcmeta_data = {
                "pack": {
                    "pack_format": pack_format,
                    "description": f"Multi-Item Java RP Pack ({selected_version})"
                }
            }
        with open(mcmeta_path, "w", encoding="utf-8") as f:
            json.dump(mcmeta_data, f, indent=4, ensure_ascii=False)

        base_items_map = {}

        for item in self.items_list:
            item_id = item['id']
            vanilla_base = item['base']
            cmd = item['cmd']

            if item['texture_path'] and os.path.exists(item['texture_path']):
                shutil.copy(item['texture_path'], os.path.join(textures_item_dir, f"{item_id}.png"))

            if item['model_path'] and os.path.exists(item['model_path']):
                model_out_path = os.path.join(models_item_dir, f"{item_id}.json")
                self._apply_texture_slots_to_model(item, item_id, item['model_path'], model_out_path, textures_item_dir)
            else:
                if item.get("texture_slots"):
                    first_slot = next((slot for slot in item.get("texture_slots", []) if slot.get("path") and os.path.exists(slot.get("path"))), None)
                    if first_slot and first_slot.get("path"):
                        shutil.copy(first_slot["path"], os.path.join(textures_item_dir, f"{item_id}.png"))
                default_model = {
                    "parent": "minecraft:item/generated",
                    "textures": {"layer0": f"minecraft:item/{item_id}"}
                }
                with open(os.path.join(models_item_dir, f"{item_id}.json"), "w", encoding="utf-8") as mf:
                    json.dump(default_model, mf, indent=4, ensure_ascii=False)

            if vanilla_base not in base_items_map:
                base_items_map[vanilla_base] = []
            base_items_map[vanilla_base].append({
                "cmd": cmd,
                "model_id": item_id
            })

        for vanilla_base, entries in base_items_map.items():
            if is_new_format:
                sorted_entries = sorted(entries, key=lambda x: x["cmd"])
                dispatch_entries = []
                fallback_model = {
                    "type": "minecraft:model",
                    "model": f"minecraft:item/{vanilla_base}"
                }
                for entry in sorted_entries:
                    cmd_val = entry["cmd"]
                    # Точное совпадение на пороге
                    dispatch_entries.append({
                        "threshold": cmd_val,
                        "model": {
                            "type": "minecraft:model",
                            "model": f"minecraft:item/{entry['model_id']}"
                        }
                    })
                    # Сразу после точного значения — сброс на фоллбек,
                    # чтобы не "залипало" на следующие большие числа (эффект "и выше")
                    dispatch_entries.append({
                        "threshold": cmd_val + 0.001,
                        "model": fallback_model
                    })
                item_def_data = {
                    "model": {
                        "type": "minecraft:range_dispatch",
                        "property": "minecraft:custom_model_data",
                        "index": 0,
                        "fallback": fallback_model,
                        "entries": dispatch_entries
                    }
                }
                with open(os.path.join(items_def_dir, f"{vanilla_base}.json"), "w", encoding="utf-8") as f:
                    json.dump(item_def_data, f, indent=4, ensure_ascii=False)
            else:
                override_json_path = os.path.join(models_item_dir, f"{vanilla_base}.json")
                if os.path.exists(override_json_path):
                    with open(override_json_path, "r", encoding="utf-8") as f:
                        base_data = json.load(f)
                else:
                    base_data = {
                        "parent": "minecraft:item/handheld",
                        "textures": {"layer0": f"minecraft:item/{vanilla_base}"},
                        "overrides": []
                    }

                if "overrides" not in base_data:
                    base_data["overrides"] = []

                for entry in entries:
                    cmd = entry["cmd"]
                    model_id = entry["model_id"]
                    new_override = {
                        "predicate": {"custom_model_data": cmd},
                        "model": f"minecraft:item/{model_id}"
                    }
                    base_data["overrides"] = [o for o in base_data["overrides"] if o.get("predicate", {}).get("custom_model_data") != cmd]
                    base_data["overrides"].append(new_override)

                with open(override_json_path, "w", encoding="utf-8") as f:
                    json.dump(base_data, f, indent=4, ensure_ascii=False)

        zip_name = "server_resourcepack_java.zip"
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(pack_dir):
                for file in files:
                    full_p = os.path.join(root, file)
                    rel_p = os.path.relpath(full_p, pack_dir)
                    zipf.write(full_p, rel_p)

        messagebox.showinfo("Java Успех", f"Ресурспак успешно собран ({len(self.items_list)} предметов)!\nАрхив: {zip_name}")

    def _geyser_collect_textures(self, item):
        """Collect the actual PNGs used by the Java/Blockbench model.

        The Java model may reference textures as #0/#1/...; the Bedrock
        attachable uses one atlas so all those references can coexist in a
        single geometry file without losing the original UV mapping.
        """
        result = self._resolve_model_texture_map(item)

        # Imported/hand-created items sometimes have no texture declarations
        # in the JSON but do have texture_slots.
        for slot in self._normalize_texture_slots(item):
            path = slot.get("path") or ""
            idx = slot.get("index")
            if path and os.path.isfile(path) and idx is not None:
                result[str(idx)] = path

        direct = item.get("texture_path") or ""
        if not result and direct and os.path.isfile(direct):
            result["0"] = direct

        # Keep deterministic ordering: numeric slots first, then names.
        def sort_key(k):
            try:
                return (0, int(k))
            except Exception:
                return (1, str(k))
        return {k: result[k] for k in sorted(result, key=sort_key)}

    def _geyser_make_texture_atlas(self, texture_map, atlas_path):
        """Create a vertical atlas and return slot -> atlas placement data."""
        if not PIL_AVAILABLE:
            raise RuntimeError("Для создания Bedrock 3D-моделей нужен Pillow.")

        from PIL import Image

        images = {}
        for key, path in texture_map.items():
            if not path or not os.path.isfile(path):
                continue
            try:
                images[key] = Image.open(path).convert("RGBA")
            except Exception:
                continue

        if not images:
            raise RuntimeError("Не найдены PNG-текстуры для Blockbench-модели.")

        # Reuse identical files instead of duplicating them in the atlas.
        unique = []
        path_to_key = {}
        placements = {}
        
        for key, img in images.items():
            real = os.path.abspath(texture_map[key])
            if real in path_to_key:
                # Это дубликат - мы обработаем его после первого
                continue
            path_to_key[real] = key
            unique.append((key, img))

        atlas_w = max(img.width for _, img in unique)
        atlas_h = sum(img.height for _, img in unique)
        atlas = Image.new("RGBA", (max(1, atlas_w), max(1, atlas_h)), (0, 0, 0, 0))

        y = 0
        for key, img in unique:
            atlas.alpha_composite(img, (0, y))
            placements[key] = {
                "x": 0,
                "y": y,
                "width": img.width,
                "height": img.height,
            }
            y += img.height

        # Теперь добавляем дубликаты
        for key, img in images.items():
            real = os.path.abspath(texture_map[key])
            if real in path_to_key and path_to_key[real] != key:
                # Это дубликат - скопируем placement первого файла
                placements[key] = placements[path_to_key[real]]

        os.makedirs(os.path.dirname(atlas_path), exist_ok=True)
        atlas.save(atlas_path, "PNG")
        return placements, (atlas.width, atlas.height)

    @staticmethod
    def _geyser_face_uv(face, placement, model_texture_size):
        """Convert Java face UV coordinates into Bedrock atlas UV coordinates."""
        mw, mh = model_texture_size
        try:
            mw = float(mw or 16)
            mh = float(mh or 16)
        except Exception:
            mw, mh = 16.0, 16.0

        uv = face.get("uv") if isinstance(face, dict) else None
        if not isinstance(uv, (list, tuple)) or len(uv) != 4:
            u1, v1, u2, v2 = 0.0, 0.0, float(mw), float(mh)
        else:
            u1, v1, u2, v2 = [float(v) for v in uv]

        # Java's UV coordinates are in model texture coordinates. Convert them
        # to real PNG pixels first, then add the atlas offset.
        sx = placement["width"] / mw
        sy = placement["height"] / mh
        au = placement["x"] + u1 * sx
        av = placement["y"] + v1 * sy
        bu = placement["x"] + u2 * sx
        bv = placement["y"] + v2 * sy
        return [au, av], [bu - au, bv - av]

    def _geyser_java_element_to_cube(self, element, placements, model_texture_size, default_slot="0"):
        """Convert one Java BlockElement cube to Bedrock geometry."""
        f = element.get("from", [0, 0, 0])
        t = element.get("to", [16, 16, 16])
        fx, fy, fz = [float(v) for v in f]
        tx, ty, tz = [float(v) for v in t]

        # Java item coordinates are X-right/Y-down/Z-forward. Bedrock entity
        # coordinates are X-right/Y-up/Z-forward. Center the Java 0..16 cube
        # around the item-slot bone while flipping Y.
        cube = {
            "origin": [fx - 8.0, 8.0 - ty, fz - 8.0],
            "size": [tx - fx, ty - fy, tz - fz],
        }

        rotation = element.get("rotation")
        if isinstance(rotation, dict):
            axis = rotation.get("axis")
            if axis in ("x", "y", "z"):
                origin = rotation.get("origin", [8, 8, 8])
                px, py, pz = [float(v) for v in origin]
                cube["pivot"] = [px - 8.0, 8.0 - py, pz - 8.0]
                angle = float(rotation.get("angle", 0) or 0)
                # Reflection of the Y axis changes handedness for X/Z axes.
                if axis in ("x", "z"):
                    angle = -angle
                rot = [0.0, 0.0, 0.0]
                rot["xyz".index(axis)] = angle
                cube["rotation"] = rot

            if rotation.get("rescale"):
                # Java's rescale is not directly equivalent to Bedrock cube
                # inflation. Keeping the original cube is safer than changing
                # its dimensions unexpectedly.
                pass

        faces = element.get("faces") if isinstance(element.get("faces"), dict) else {}
        bedrock_uv = {}
        for face_name in ("north", "south", "east", "west", "up", "down"):
            face = faces.get(face_name)
            if not isinstance(face, dict):
                continue
            ref = face.get("texture", f"#{default_slot}")
            if isinstance(ref, str) and ref.startswith("#"):
                slot = ref[1:]
            elif isinstance(ref, str):
                slot = ref
            else:
                slot = default_slot
            placement = placements.get(slot) or placements.get(default_slot)
            if not placement:
                continue
            uv, uv_size = self._geyser_face_uv(face, placement, model_texture_size)
            uv_entry = {"uv": uv, "uv_size": uv_size}
            rot = int(face.get("rotation", 0) or 0) % 360
            if rot in (90, 180, 270):
                uv_entry["uv_rotation"] = rot
            bedrock_uv[face_name] = uv_entry

        if bedrock_uv:
            cube["uv"] = bedrock_uv
        else:
            placement = placements.get(default_slot)
            if placement:
                cube["uv"] = {
                    "north": {"uv": [placement["x"], placement["y"]], "uv_size": [placement["width"], placement["height"]]},
                    "south": {"uv": [placement["x"], placement["y"]], "uv_size": [placement["width"], placement["height"]]},
                    "east":  {"uv": [placement["x"], placement["y"]], "uv_size": [placement["width"], placement["height"]]},
                    "west":  {"uv": [placement["x"], placement["y"]], "uv_size": [placement["width"], placement["height"]]},
                    "up":    {"uv": [placement["x"], placement["y"]], "uv_size": [placement["width"], placement["height"]]},
                    "down":  {"uv": [placement["x"], placement["y"]], "uv_size": [placement["width"], placement["height"]]},
                }
        return cube

    def _geyser_build_geometry(self, item, geometry_path, atlas_size):
        """Convert the Java model generated from Blockbench into Bedrock geo."""
        model_path = item.get("model_path") or ""
        data = self._model_json(model_path)
        elements = data.get("elements") if isinstance(data, dict) else None
        if not isinstance(elements, list) or not elements:
            raise ValueError(f"У предмета {item.get('id', 'item')} нет Java BlockElement-ов для конвертации.")

        texture_map = self._geyser_collect_textures(item)
        if not texture_map:
            raise ValueError(f"У предмета {item.get('id', 'item')} не найдены текстуры.")

        atlas_path = os.path.splitext(geometry_path)[0] + "_atlas.png"
        placements, actual_atlas_size = self._geyser_make_texture_atlas(texture_map, atlas_path)
        # The caller expects the atlas at textures/items, not beside the model.
        # atlas_path is therefore supplied by build_geyser.

        texture_size = data.get("texture_size", [16, 16])
        if not isinstance(texture_size, (list, tuple)) or len(texture_size) != 2:
            texture_size = [16, 16]

        cubes = []
        for element in elements:
            if not isinstance(element, dict):
                continue
            try:
                cubes.append(self._geyser_java_element_to_cube(
                    element, placements, texture_size,
                    default_slot=next(iter(texture_map.keys()), "0")
                ))
            except Exception:
                continue

        if not cubes:
            raise ValueError(f"Не удалось преобразовать модель {item.get('id', 'item')} в Bedrock geometry.")

        identifier = f"geometry.rppack.{item['id']}"
        geometry = {
            "format_version": "1.21.0",
            "minecraft:geometry": [{
                "description": {
                    "identifier": identifier,
                    "texture_width": int(actual_atlas_size[0]),
                    "texture_height": int(actual_atlas_size[1]),
                    "visible_bounds_width": 3.0,
                    "visible_bounds_height": 3.0,
                    "visible_bounds_offset": [0.0, 0.0, 0.0]
                },
                "bones": [{
                    "name": "rppack_item",
                    "pivot": [0, 0, 0],
                    "binding": "q.item_slot_to_bone_name(context.item_slot)",
                    "cubes": cubes
                }]
            }]
        }
        with open(geometry_path, "w", encoding="utf-8") as fh:
            json.dump(geometry, fh, indent=2, ensure_ascii=False)

        return atlas_path, identifier, actual_atlas_size

    def _geyser_write_item_assets(self, item, rp_root):
        """Create icon, atlas, geometry, attachable and the icon mapping data."""
        item_id = item["id"]
        bedrock_identifier = f"rppack:{item_id}"
        safe_id = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in item_id)
        textures_dir = os.path.join(rp_root, "textures", "items")
        geometry_dir = os.path.join(rp_root, "models", "entity")
        attachables_dir = os.path.join(rp_root, "attachables")
        animations_dir = os.path.join(rp_root, "animations")
        os.makedirs(textures_dir, exist_ok=True)
        os.makedirs(geometry_dir, exist_ok=True)
        os.makedirs(attachables_dir, exist_ok=True)
        os.makedirs(animations_dir, exist_ok=True)

        texture_map = self._geyser_collect_textures(item)
        if not texture_map:
            model_path = item.get("model_path") or "(не указано)"
            texture_path = item.get("texture_path") or "(не указано)"
            raise ValueError(
                f"Для '{item_id}' не найдена ни одна PNG-текстура!\n"
                f"Это обязательно. Проверьте:\n"
                f"  1. Выбрана ли текстура: {texture_path}\n"
                f"  2. Файл существует на диске\n"
                f"  3. Добавлены ли слоты текстур в интерфейсе\n"
                f"\nМодель может быть опциональна (будет простой куб): {model_path}"
            )
        first_texture = next(iter(texture_map.values()))

        icon_path = os.path.join(textures_dir, f"{safe_id}_icon.png")
        # Слоты текстур в многослойных Blockbench-моделях обычно относятся
        # к РАЗНЫМ граням/частям модели (не всегда накладываются друг на
        # друга), поэтому для иконки в инвентаре надёжнее выбрать самый
        # детализированный слой (не однотонную подложку), а не слот "0"
        # и не наивно "склеивать" все слои вместе.
        icon_source = first_texture
        if PIL_AVAILABLE and len(texture_map) > 1:
            try:
                from PIL import Image
                best_variety = -1
                for key, path in texture_map.items():
                    if not path or not os.path.isfile(path):
                        continue
                    try:
                        img = Image.open(path).convert("RGBA")
                        sample = img.resize((32, 32)) if img.width > 32 or img.height > 32 else img
                        variety = len(set(sample.getdata()))
                        if variety > best_variety:
                            best_variety = variety
                            icon_source = path
                    except Exception:
                        continue
            except Exception:
                icon_source = first_texture
        shutil.copy2(icon_source, icon_path)

        # Build atlas directly in the final RP folder.
        atlas_path = os.path.join(textures_dir, f"{safe_id}_atlas.png")
        placements, atlas_size = self._geyser_make_texture_atlas(texture_map, atlas_path)

        data = self._model_json(item.get("model_path") or "")
        elements = data.get("elements") if isinstance(data, dict) else None
        texture_size = data.get("texture_size", [16, 16]) if isinstance(data, dict) else [16, 16]
        if not isinstance(texture_size, (list, tuple)) or len(texture_size) != 2:
            texture_size = [16, 16]

        cubes = []
        default_slot = next(iter(texture_map.keys()), "0")
        
        # Если нету модели или элементов - создать простой плоский предмет из текстуры
        if not isinstance(elements, list) or not elements:
            # UV должен покрывать ВЕСЬ атлас (Bedrock-геометрия сэмплирует
            # напрямую из атласа, а не из отдельного файла-слота). Раньше тут
            # был хардкод [16, 16], из-за чего при текстурах больше 16x16
            # (например 512x512) куб "смотрел" в маленький пустой уголок
            # атласа и предмет становился невидимым в руке.
            atlas_uv_w, atlas_uv_h = int(atlas_size[0]), int(atlas_size[1])
            flat_cube = {
                "origin": [0, 0, 0],
                "size": [16, 16, 16],
                "uv": {
                    "north": {"uv": [0, 0], "uv_size": [atlas_uv_w, atlas_uv_h], "texture": default_slot},
                    "south": {"uv": [0, 0], "uv_size": [atlas_uv_w, atlas_uv_h], "texture": default_slot},
                    "east": {"uv": [0, 0], "uv_size": [atlas_uv_w, atlas_uv_h], "texture": default_slot},
                    "west": {"uv": [0, 0], "uv_size": [atlas_uv_w, atlas_uv_h], "texture": default_slot},
                    "up": {"uv": [0, 0], "uv_size": [atlas_uv_w, atlas_uv_h], "texture": default_slot},
                    "down": {"uv": [0, 0], "uv_size": [atlas_uv_w, atlas_uv_h], "texture": default_slot}
                }
            }
            cubes.append(flat_cube)
        else:
            for element in elements:
                if isinstance(element, dict):
                    cubes.append(self._geyser_java_element_to_cube(element, placements, texture_size, default_slot))
        
        if not cubes:
            raise ValueError(f"Не удалось преобразовать модель {item_id}.")

        geometry_identifier = f"geometry.rppack.{safe_id}"
        geometry = {
            "format_version": "1.21.0",
            "minecraft:geometry": [{
                "description": {
                    "identifier": geometry_identifier,
                    "texture_width": int(atlas_size[0]),
                    "texture_height": int(atlas_size[1]),
                    "visible_bounds_width": 3.0,
                    "visible_bounds_height": 3.0,
                    "visible_bounds_offset": [0.0, 0.0, 0.0]
                },
                "bones": [{
                    "name": "rppack_item",
                    "pivot": [0, 0, 0],
                    "binding": "q.item_slot_to_bone_name(context.item_slot)",
                    "cubes": cubes
                }]
            }]
        }
        geometry_path = os.path.join(geometry_dir, f"{safe_id}.geo.json")
        with open(geometry_path, "w", encoding="utf-8") as fh:
            json.dump(geometry, fh, indent=2, ensure_ascii=False)

        # Reuse the vanilla attachable item controller. The geometry is bound
        # to main_hand/off_hand through q.item_slot_to_bone_name, matching the
        # supported Geyser/Bedrock attachable pattern.
        attachable = {
            "format_version": "1.20.30",
            "minecraft:attachable": {
                "description": {
                    "identifier": bedrock_identifier,
                    "item": {
                        bedrock_identifier: "query.is_owner_identifier_any('minecraft:player')"
                    },
                    "materials": {
                        "default": "entity",
                        "enchanted": "entity_alphatest_glint"
                    },
                    "textures": {
                        "default": f"textures/items/{safe_id}_atlas",
                        "enchanted": "textures/misc/enchanted_item_glint"
                    },
                    "geometry": {
                        "default": geometry_identifier
                    },
                    "animations": {
                        "hold_first_person": "animation.rppack.{0}.hold_first_person".format(safe_id),
                        "hold_third_person": "animation.rppack.{0}.hold_third_person".format(safe_id)
                    },
                    "scripts": {
                        "animate": [
                            {"hold_first_person": "context.is_first_person == 1.0"},
                            {"hold_third_person": "context.is_first_person == 0.0"}
                        ]
                    },
                    "render_controllers": ["controller.render.item_default"]
                }
            }
        }
        attachable_path = os.path.join(attachables_dir, f"{safe_id}.attachable.json")
        with open(attachable_path, "w", encoding="utf-8") as fh:
            json.dump(attachable, fh, indent=2, ensure_ascii=False)

        # Neutral animations: the binding handles main/off hand placement;
        # these files make the attachable definition self-contained and allow
        # future per-item display tuning without changing the mapping.
        anim = {
            "format_version": "1.8.0",
            "animations": {
                f"animation.rppack.{safe_id}.hold_first_person": {
                    "loop": True,
                    "bones": {}
                },
                f"animation.rppack.{safe_id}.hold_third_person": {
                    "loop": True,
                    "bones": {}
                }
            }
        }
        anim_path = os.path.join(animations_dir, f"{safe_id}.animation.json")
        with open(anim_path, "w", encoding="utf-8") as fh:
            json.dump(anim, fh, indent=2, ensure_ascii=False)

        return {
            "icon_shorthand": bedrock_identifier.replace(":", ".").replace("/", "_"),
            "icon_path": icon_path,
            "atlas_path": atlas_path,
            "geometry_path": geometry_path,
            "attachable_path": attachable_path,
            "animation_path": anim_path,
            "atlas_size": atlas_size,
            "geometry_identifier": geometry_identifier,
        }

    def build_geyser(self):
        if not self.items_list:
            messagebox.showerror("Ошибка", "Список предметов пуст! Добавьте хотя бы один предмет.")
            return

        geyser_dir = "Geyser_Bridge_Output"
        packs_bedrock = os.path.join(geyser_dir, "packs")
        mappings_dir = os.path.join(geyser_dir, "custom_mappings")
        rp_root = os.path.join(geyser_dir, "bedrock_rp")

        if os.path.exists(geyser_dir):
            shutil.rmtree(geyser_dir)

        os.makedirs(packs_bedrock, exist_ok=True)
        os.makedirs(mappings_dir, exist_ok=True)
        os.makedirs(rp_root, exist_ok=True)

        mappings_by_java_item = {}
        item_texture_data = {}
        generated = []

        try:
            for idx, item in enumerate(self.items_list):
                item_id = item["id"]
                item_name = item.get("name") or item_id
                vanilla_base = item["base"]
                cmd = item["cmd"]
                bedrock_identifier = f"rppack:{item_id}"
                icon_shorthand = bedrock_identifier.replace(":", ".").replace("/", "_")

                try:
                    assets = self._geyser_write_item_assets(item, rp_root)
                    generated.append(assets)
                except Exception as item_exc:
                    raise RuntimeError(
                        f"Ошибка при обработке предмета #{idx+1} '{item_id}':\n"
                        f"{str(item_exc)}"
                    )

                definition = {
                    "type": "legacy",
                    "custom_model_data": cmd,
                    "bedrock_identifier": bedrock_identifier,
                    "display_name": item_name.replace("&", "\u00a7"),
                    "bedrock_options": {
                        "icon": icon_shorthand,
                        "display_handheld": True
                    }
                }
                java_key = f"minecraft:{vanilla_base}"
                mappings_by_java_item.setdefault(java_key, []).append(definition)

                item_texture_data[icon_shorthand] = {
                    "textures": [f"textures/items/{os.path.basename(assets['icon_path'])[:-4]}"]
                }

        except Exception as exc:
            import traceback
            error_detail = traceback.format_exc()
            messagebox.showerror(
                "Ошибка Geyser",
                "Не удалось создать Bedrock 3D-пак:\n\n" + error_detail
            )
            return

        mappings_file = {
            "format_version": 2,
            "items": mappings_by_java_item
        }
        mappings_path = os.path.join(mappings_dir, "rppack_mappings.json")
        with open(mappings_path, "w", encoding="utf-8") as f:
            json.dump(mappings_file, f, indent=4, ensure_ascii=False)

        # Valid unique UUIDs are important when the pack is regenerated.
        pack_uuid = str(uuid.uuid4())
        module_uuid = str(uuid.uuid4())
        manifest_data = {
            "format_version": 2,
            "header": {
                "name": "RP Pack - Geyser Bridge 3D",
                "description": "Auto-generated Bedrock 3D items from Blockbench/Java models",
                "uuid": pack_uuid,
                "version": [1, 0, 0],
                "min_engine_version": [1, 21, 0]
            },
            "modules": [{
                "description": "Resources",
                "type": "resources",
                "uuid": module_uuid,
                "version": [1, 0, 0]
            }]
        }

        # Copy the generated RP into the .mcpack root.
        mcpack_path = os.path.join(packs_bedrock, "all_items_bedrock_pack.mcpack")
        with zipfile.ZipFile(mcpack_path, "w", zipfile.ZIP_DEFLATED) as mcpack_zip:
            mcpack_zip.writestr("manifest.json", json.dumps(manifest_data, indent=2, ensure_ascii=False))

            item_texture_json = {
                "resource_pack_name": "rppack",
                "texture_name": "atlas.items",
                "texture_data": item_texture_data
            }
            mcpack_zip.writestr(
                "textures/item_texture.json",
                json.dumps(item_texture_json, indent=2, ensure_ascii=False)
            )

            # Include every generated RP asset, preserving its relative path.
            for root, dirs, files in os.walk(rp_root):
                for file_name in files:
                    full_path = os.path.join(root, file_name)
                    rel = os.path.relpath(full_path, rp_root).replace(os.sep, "/")
                    mcpack_zip.write(full_path, rel)

        messagebox.showinfo(
            "Geyser Успех",
            f"Bedrock/Geyser 3D-пак успешно собран ({len(self.items_list)} предметов)!\n\n"
            f"Создано:\n"
            f"• .mcpack с geometry + attachables + atlas-текстурами\n"
            f"• mappings: {mappings_path}\n\n"
            f"Скопируй:\n"
            f"1) {mappings_path} → custom_mappings/ Geyser\n"
            f"2) {mcpack_path} → packs/ Geyser\n"
            f"3) enable-custom-content: true\n"
            f"4) Перезапусти Geyser/сервер"
        )

    def _pick_existing_pack_dir(self):
        java_dir = "Generated_Java_RP"
        geyser_dir = "Geyser_Bridge_Output"
        imported_dir = self.imported_pack_dir if self.imported_pack_dir and os.path.isdir(self.imported_pack_dir) else ""
        java_exists = os.path.isdir(java_dir)
        geyser_exists = os.path.isdir(geyser_dir)
        imported_exists = bool(imported_dir)

        if imported_exists:
            return imported_dir

        if not java_exists and not geyser_exists:
            messagebox.showwarning(
                "Нет собранного пака",
                "Сначала собери пак кнопкой «Скомпилировать РП для Java» "
                "или «Скомпилировать для Geyser» — тогда появится, что открывать."
            )
            return None

        if java_exists and geyser_exists:
            choice = messagebox.askyesnocancel(
                "Какую папку?",
                "Да — Java-пак (Generated_Java_RP)\n"
                "Нет — Geyser-мост (Geyser_Bridge_Output)\n"
                "Отмена — ничего не делать"
            )
            if choice is None:
                return None
            return java_dir if choice else geyser_dir

        return java_dir if java_exists else geyser_dir

    def _resolve_imported_asset_path(self, pack_root, asset_path, kind="auto"):
        if not asset_path:
            return ""

        clean_path = str(asset_path).strip().replace("minecraft:", "")
        clean_path = clean_path.replace("\\", "/")
        clean_path = clean_path.lstrip("/")

        if clean_path.startswith("item/"):
            item_name = clean_path[len("item/"):]
        elif clean_path.startswith("models/"):
            item_name = clean_path[len("models/"):]
        elif clean_path.startswith("textures/"):
            item_name = clean_path[len("textures/"):]
        else:
            item_name = clean_path

        if item_name.startswith("item/"):
            item_name = item_name[len("item/"):]

        item_name = os.path.splitext(os.path.basename(item_name))[0]

        candidates = []
        if kind == "texture":
            candidates.append(os.path.join(pack_root, "assets", "minecraft", "textures", "item", f"{item_name}.png"))
            candidates.append(os.path.join(pack_root, "assets", "minecraft", "textures", "item", f"{item_name}.json"))
        elif kind == "model":
            candidates.append(os.path.join(pack_root, "assets", "minecraft", "models", "item", f"{item_name}.json"))
        else:
            candidates.append(os.path.join(pack_root, "assets", "minecraft", "models", "item", f"{item_name}.json"))
            candidates.append(os.path.join(pack_root, "assets", "minecraft", "textures", "item", f"{item_name}.png"))

        if clean_path.startswith(("models/", "textures/", "item/")):
            candidates.append(os.path.join(pack_root, "assets", "minecraft", clean_path.replace("/", os.sep)))

        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate
        return ""

    def _add_imported_item_to_list(self, item_id, base, cmd, model_file, texture_file):
        if any(i["id"] == item_id for i in self.items_list):
            return

        item_data = {
            "id": item_id,
            "name": "",
            "base": base,
            "cmd": int(cmd),
            "model_path": model_file,
            "texture_path": texture_file
        }
        self.items_list.append(item_data)
        texture_label = self._texture_label(texture_file)
        item_iid = self.tree.insert("", "end", values=(item_id, texture_label, base, cmd))
        self.tree.selection_set(item_iid)
        self.tree.focus(item_iid)
        self.show_selected_preview()

    def _populate_items_from_imported_pack(self, pack_root):
        self.items_list = []
        self.tree.delete(*self.tree.get_children())

        items_def_dir = os.path.join(pack_root, "assets", "minecraft", "items")
        if os.path.isdir(items_def_dir):
            for file_name in sorted(os.listdir(items_def_dir)):
                if not file_name.endswith(".json"):
                    continue
                base_item = os.path.splitext(file_name)[0]
                file_path = os.path.join(items_def_dir, file_name)
                try:
                    with open(file_path, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                except Exception:
                    continue

                model_data = data.get("model", {})
                model_type = model_data.get("type")

                if model_type == "minecraft:range_dispatch":
                    for entry in model_data.get("entries", []):
                        threshold = entry.get("threshold")
                        model_ref = entry.get("model", {}).get("model")
                        if threshold is None or not model_ref:
                            continue
                        model_id = model_ref.split("minecraft:item/")[-1]
                        # Пропускаем служебные "сброс"-записи, указывающие обратно на ванильный предмет
                        if model_id == base_item:
                            continue
                        # Пропускаем дробные пороги-сбросы (1001.001 и т.п.) на всякий случай
                        cmd_int = int(round(threshold))
                        model_file = self._resolve_imported_asset_path(pack_root, model_ref, kind="model")
                        texture_file = self._resolve_imported_asset_path(pack_root, f"minecraft:item/{model_id}", kind="texture")
                        self._add_imported_item_to_list(model_id, base_item, cmd_int, model_file, texture_file)

                elif model_type == "minecraft:select":
                    for case in model_data.get("cases", []):
                        when_val = case.get("when")
                        model_ref = case.get("model", {}).get("model")
                        if when_val is None or not model_ref:
                            continue
                        model_id = model_ref.split("minecraft:item/")[-1]
                        if model_id == base_item:
                            continue
                        try:
                            cmd_int = int(round(float(when_val)))
                        except (TypeError, ValueError):
                            continue
                        model_file = self._resolve_imported_asset_path(pack_root, model_ref, kind="model")
                        texture_file = self._resolve_imported_asset_path(pack_root, f"minecraft:item/{model_id}", kind="texture")
                        self._add_imported_item_to_list(model_id, base_item, cmd_int, model_file, texture_file)

        models_dir = os.path.join(pack_root, "assets", "minecraft", "models", "item")
        if os.path.isdir(models_dir):
            for file_name in sorted(os.listdir(models_dir)):
                if not file_name.endswith(".json"):
                    continue
                item_id = os.path.splitext(file_name)[0]
                model_file = os.path.join(models_dir, file_name)
                texture_file = os.path.join(pack_root, "assets", "minecraft", "textures", "item", f"{item_id}.png")
                if os.path.isfile(texture_file):
                    self._add_imported_item_to_list(item_id, item_id, 1001, model_file, texture_file)

        if self.tree.get_children():
            first_item = self.tree.get_children()[0]
            self.tree.selection_set(first_item)
            self.tree.focus(first_item)
            self.show_selected_preview()

    def import_existing_resource_pack(self):
        selected_path = filedialog.askdirectory(title="Выберите папку существующего ресурс-пака")
        if not selected_path:
            selected_path = filedialog.askopenfilename(
                title="Выберите .zip архив существующего ресурс-пака",
                filetypes=[("ZIP files", "*.zip")]
            )

        if not selected_path:
            return

        target_dir = os.path.join(os.getcwd(), "Imported_RP_Work")
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        os.makedirs(target_dir, exist_ok=True)

        if os.path.isdir(selected_path):
            shutil.copytree(selected_path, target_dir, dirs_exist_ok=True)
        else:
            with zipfile.ZipFile(selected_path, "r") as zf:
                zf.extractall(target_dir)

        self.imported_pack_dir = target_dir
        self._populate_items_from_imported_pack(target_dir)
        self.lbl_imported.config(text=f"Импортировано: {os.path.basename(selected_path)}", fg="#76ff03")
        messagebox.showinfo(
            "Импортировано",
            f"Ресурс-пак загружен в рабочую папку:\n{target_dir}\n\n"
            "Теперь можно удалить лишние файлы/папки вручную и пересобрать его обратно."
        )

    def rebuild_imported_pack(self):
        if not self.imported_pack_dir or not os.path.isdir(self.imported_pack_dir):
            messagebox.showwarning("Нет импортированного RP", "Сначала импортируйте существующий ресурс-пак.")
            return

        output_zip = os.path.join(os.getcwd(), "imported_resourcepack_repacked.zip")
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.imported_pack_dir):
                for file_name in files:
                    full_path = os.path.join(root, file_name)
                    rel_path = os.path.relpath(full_path, self.imported_pack_dir)
                    zipf.write(full_path, rel_path)

        messagebox.showinfo("Пересобрано", f"Импортированный RP пересобран в архив:\n{output_zip}")

    def open_ready_pack(self):
        candidates = []

        if self.imported_pack_dir and os.path.isdir(self.imported_pack_dir):
            candidates.append(self.imported_pack_dir)

        java_zip = "server_resourcepack_java.zip"
        if os.path.isfile(java_zip):
            candidates.append(java_zip)

        java_dir = "Generated_Java_RP"
        if os.path.isdir(java_dir):
            candidates.append(java_dir)

        bedrock_pack = os.path.join("Geyser_Bridge_Output", "packs", "all_items_bedrock_pack.mcpack")
        if os.path.isfile(bedrock_pack):
            candidates.append(bedrock_pack)

        geyser_dir = "Geyser_Bridge_Output"
        if os.path.isdir(geyser_dir):
            candidates.append(geyser_dir)

        if not candidates:
            messagebox.showwarning(
                "Нет готового пака",
                "Сначала собери пакет кнопкой «Скомпилировать РП для Java» или «Скомпилировать для Geyser» или импортируй существующий RP."
            )
            return

        target_path = candidates[0]
        abs_path = os.path.abspath(target_path)
        try:
            if os.name == "nt":
                os.startfile(abs_path)
            elif shutil.which("xdg-open"):
                subprocess.Popen(["xdg-open", abs_path])
            elif shutil.which("open"):
                subprocess.Popen(["open", abs_path])
            else:
                messagebox.showinfo("Путь к паку", abs_path)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть готовый пакет:\n{e}\n\nПуть: {abs_path}")

    def show_rp_structure(self):
        target_dir = self._pick_existing_pack_dir()
        if not target_dir:
            return

        lines = [f"{target_dir}/"]

        def walk(dir_path, prefix=""):
            try:
                entries = sorted(os.listdir(dir_path))
            except OSError:
                return
            dirs = [e for e in entries if os.path.isdir(os.path.join(dir_path, e))]
            files = [e for e in entries if not os.path.isdir(os.path.join(dir_path, e))]
            ordered = dirs + files
            for i, entry in enumerate(ordered):
                full_path = os.path.join(dir_path, entry)
                is_last = (i == len(ordered) - 1)
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{entry}")
                if os.path.isdir(full_path):
                    extension = "    " if is_last else "│   "
                    walk(full_path, prefix + extension)

        walk(target_dir)

        win = tk.Toplevel(self.root)
        win.title(f"Структура пака — {target_dir}")
        win.geometry("500x500")
        win.config(bg="#2b2b2b")

        text_widget = tk.Text(win, bg="#1e1e1e", fg="#d4d4d4", insertbackground="white",
                               font=("Consolas", 10), wrap="none")
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)
        text_widget.insert("1.0", "\n".join.join(lines) if hasattr(lines, 'join') else "\n".join(lines))
        text_widget.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = MultiItemRPBuilderApp(root)
    root.mainloop()