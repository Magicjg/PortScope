from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .benchmark import (
    DEFAULT_FILE_SIZE_MB,
    DEFAULT_PASSES,
    BenchmarkCancelled,
    run_storage_benchmark,
)
from .exporters import export_snapshot_csv_bundle, export_snapshot_json
from .history import (
    append_history,
    clear_history,
    export_history_csv,
    load_history,
    load_settings,
    save_settings,
)
from .logger import read_recent_logs
from .system_info import PortSnapshot, collect_snapshot


THEMES = {
    "light": {
        "bg": "#eef3f8",
        "panel": "#fdfefe",
        "panel_alt": "#f4f8fc",
        "panel_soft": "#edf4fb",
        "header": "#10304d",
        "header_text": "#f8fbff",
        "header_muted": "#bfd3e7",
        "text": "#142235",
        "muted": "#61758d",
        "border": "#d8e4ef",
        "accent": "#0e7490",
        "accent_alt": "#d97706",
        "accent_soft": "#dff3f8",
        "button": "#2563eb",
        "button_text": "#ffffff",
        "button_alt": "#dbe8f5",
        "button_alt_text": "#17324d",
        "button_disabled": "#d6e0ea",
        "button_disabled_text": "#8aa0b6",
        "danger_soft": "#fff0ec",
        "info_bar": "#dfeaf5",
        "info_text": "#4e637a",
        "input": "#ffffff",
        "tree_bg": "#fbfdff",
        "tree_fg": "#142235",
        "tree_selected": "#dff3f8",
        "progress_trough": "#d9e5ef",
        "success": "#1f8a5c",
        "warning": "#b45309",
        "shadow": "#d7e1eb",
    },
    "dark": {
        "bg": "#0b1220",
        "panel": "#121c2e",
        "panel_alt": "#18253a",
        "panel_soft": "#1d2d45",
        "header": "#060d18",
        "header_text": "#f8fbff",
        "header_muted": "#9fb7cf",
        "text": "#e6f0fa",
        "muted": "#9bb0c7",
        "border": "#24364f",
        "accent": "#38bdf8",
        "accent_alt": "#f59e0b",
        "accent_soft": "#113447",
        "button": "#2563eb",
        "button_text": "#ffffff",
        "button_alt": "#22324a",
        "button_alt_text": "#edf6ff",
        "button_disabled": "#1a2638",
        "button_disabled_text": "#5d7089",
        "danger_soft": "#3b1f28",
        "info_bar": "#122136",
        "info_text": "#cfe0f1",
        "input": "#0f1727",
        "tree_bg": "#10192a",
        "tree_fg": "#e6f0fa",
        "tree_selected": "#133849",
        "progress_trough": "#22344c",
        "success": "#41d392",
        "warning": "#f4a259",
        "shadow": "#08101b",
    },
}


class PortScopeApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PortScope")
        self.root.geometry("1340x880")
        self.root.minsize(1120, 740)
        self.release_version = "PortScope Release 0.5.0"

        self.settings = load_settings()
        self.theme_name = str(self.settings.get("theme", "light"))
        if self.theme_name not in THEMES:
            self.theme_name = "light"
        self.snapshot: PortSnapshot | None = None
        self.benchmark_queue: queue.Queue = queue.Queue()
        self.snapshot_queue: queue.Queue = queue.Queue()
        self.history_entries = load_history()
        self.target_map: dict[str, str] = {}
        self.card_frames: list[tk.Frame] = []
        self.notebook: ttk.Notebook | None = None
        self.quick_summary_label: tk.Label | None = None
        self.home_info_label: tk.Label | None = None
        self.module_status_container: tk.Frame | None = None
        self.previous_connected_ids: set[str] = set()
        self.connected_tree: ttk.Treeview | None = None
        self.connected_changes_label: tk.Label | None = None
        self.cancel_benchmark_event = threading.Event()
        self.active_benchmark_passes = DEFAULT_PASSES
        self.active_benchmark_file_size_mb = DEFAULT_FILE_SIZE_MB

        self.selected_folder = tk.StringVar(value=self.settings.get("last_folder", ""))
        self.selected_target = tk.StringVar()
        self.file_size_mb = tk.IntVar(
            value=int(self.settings.get("last_file_size_mb", DEFAULT_FILE_SIZE_MB))
        )
        self.pass_count = tk.IntVar(
            value=int(self.settings.get("last_pass_count", DEFAULT_PASSES))
        )
        self.usb_filter = tk.StringVar()
        self.net_filter = tk.StringVar()
        self.disk_filter = tk.StringVar()
        self.summary_text = tk.StringVar(value="Cargando informacion del sistema...")
        self.info_text = tk.StringVar(value="Preparando lectura inicial del equipo.")
        self.benchmark_text = tk.StringVar(value="Selecciona una carpeta o una unidad para comenzar.")
        self.progress_text = tk.StringVar(value="Sin pruebas en ejecucion")
        self.theme_button_text = tk.StringVar(
            value="Modo claro" if self.theme_name == "dark" else "Modo nocturno"
        )

        self.refresh_button: tk.Button | None = None
        self.theme_button: tk.Button | None = None
        self.run_button: tk.Button | None = None
        self.cancel_button: tk.Button | None = None
        self.progress: ttk.Progressbar | None = None
        self.notes_text: tk.Text | None = None
        self.alerts_container: tk.Frame | None = None
        self.history_tree: ttk.Treeview | None = None
        self.target_combo: ttk.Combobox | None = None
        self.usb_tree: ttk.Treeview | None = None
        self.net_tree: ttk.Treeview | None = None
        self.disk_tree: ttk.Treeview | None = None
        self.benchmark_result_label: tk.Label | None = None
        self.benchmark_metrics_container: tk.Frame | None = None
        self.benchmark_metric_cards: dict[str, tuple[tk.Label, tk.Label]] = {}
        self.benchmark_canvas: tk.Canvas | None = None
        self.benchmark_scrollbar: ttk.Scrollbar | None = None
        self.benchmark_inner: tk.Frame | None = None
        self.benchmark_window_id: int | None = None
        self.benchmark_row: tk.Frame | None = None
        self.benchmark_left_panel: tk.Frame | None = None
        self.benchmark_right_panel: tk.Frame | None = None
        self.benchmark_layout_mode = "wide"
        self.benchmark_mousewheel_bound = False

        self._build_ui()
        self._refresh_history_tree()
        self.load_snapshot()
        self._bind_state_tracking()

    @property
    def colors(self) -> dict[str, str]:
        return THEMES[self.theme_name]

    def _bind_state_tracking(self) -> None:
        self.selected_folder.trace_add("write", lambda *_: self._save_preferences())
        self.file_size_mb.trace_add("write", lambda *_: self._save_preferences())
        self.pass_count.trace_add("write", lambda *_: self._save_preferences())

    def _save_preferences(self) -> None:
        self.settings.update(
            {
                "theme": self.theme_name,
                "last_folder": self.selected_folder.get().strip(),
                "last_file_size_mb": int(self.file_size_mb.get()),
                "last_pass_count": int(self.pass_count.get()),
            }
        )
        save_settings(self.settings)

    def _build_ui(self) -> None:
        for child in self.root.winfo_children():
            child.destroy()
        self.card_frames.clear()
        self.root.configure(bg=self.colors["bg"])
        self._configure_styles()
        self._build_menu()

        header = tk.Frame(self.root, bg=self.colors["header"], padx=30, pady=24)
        header.pack(fill="x", padx=18, pady=(16, 10))

        title_row = tk.Frame(header, bg=self.colors["header"])
        title_row.pack(fill="x")

        left = tk.Frame(title_row, bg=self.colors["header"])
        left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text="PortScope", font=("Segoe UI", 28, "bold"), bg=self.colors["header"], fg=self.colors["header_text"]).pack(anchor="w")
        tk.Label(left, text="Diagnostico de puertos, enlaces y pruebas reales de transferencia.", font=("Segoe UI", 11), bg=self.colors["header"], fg=self.colors["header_muted"]).pack(anchor="w", pady=(6, 0))

        actions = tk.Frame(title_row, bg=self.colors["header"])
        actions.pack(side="right")
        self.refresh_button = self._make_button(actions, "Actualizar inventario", self.load_snapshot, primary=True)
        self.refresh_button.pack(side="left")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=18, pady=(2, 18))

        home_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        insights_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        connected_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        usb_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        net_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        disk_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        bench_tab = tk.Frame(self.notebook, bg=self.colors["bg"])
        self.notebook.add(home_tab, text="Inicio")
        self.notebook.add(insights_tab, text="Hallazgos")
        self.notebook.add(connected_tab, text="Conectados ahora")
        self.notebook.add(usb_tab, text="USB")
        self.notebook.add(net_tab, text="Red")
        self.notebook.add(disk_tab, text="Unidades")
        self.notebook.add(bench_tab, text="Benchmark")

        self._build_home_tab(home_tab)
        self._build_insights_tab(insights_tab)
        self.connected_tree = self._build_connected_tab(connected_tab)
        self.usb_tree = self._build_tree(
            usb_tab,
            ("categoria", "nombre", "fabricante", "estado", "velocidad", "energia"),
            {"categoria": "Categoria", "nombre": "Nombre", "fabricante": "Fabricante", "estado": "Estado", "velocidad": "Velocidad", "energia": "Energia"},
            "Busca por nombre o fabricante",
            self.usb_filter,
            self._refresh_usb_view,
        )
        self.net_tree = self._build_tree(
            net_tab,
            ("nombre", "tipo", "estado", "conexion", "velocidad", "mac"),
            {"nombre": "Nombre", "tipo": "Tipo", "estado": "Estado", "conexion": "Conexion", "velocidad": "LinkSpeed", "mac": "MAC"},
            "Busca por nombre o tipo",
            self.net_filter,
            self._refresh_net_view,
        )
        self.disk_tree = self._build_tree(
            disk_tab,
            ("unidad", "etiqueta", "tipo", "salud", "libre", "tamano"),
            {"unidad": "Unidad", "etiqueta": "Etiqueta", "tipo": "Tipo", "salud": "Salud", "libre": "Libre", "tamano": "Tamano"},
            "Busca por unidad o etiqueta",
            self.disk_filter,
            self._refresh_disk_view,
        )
        self._build_benchmark_tab(bench_tab)

        if self.snapshot is not None:
            self._refresh_usb_view()
            self._refresh_net_view()
            self._refresh_disk_view()
            self._update_dashboard()
            self._load_targets()
        self._refresh_history_tree()

    def _configure_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook", background=self.colors["bg"], borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            padding=(20, 13),
            font=("Segoe UI", 10, "bold"),
            background=self.colors["panel_alt"],
            foreground=self.colors["muted"],
            borderwidth=1,
            lightcolor=self.colors["border"],
            darkcolor=self.colors["border"],
            bordercolor=self.colors["border"],
        )
        style.map(
            "TNotebook.Tab",
            background=[
                ("selected", self.colors["accent_soft"]),
                ("active", self.colors["panel"]),
            ],
            foreground=[
                ("selected", self.colors["accent"]),
                ("active", self.colors["text"]),
            ],
        )
        style.configure(
            "Treeview",
            rowheight=32,
            font=("Segoe UI", 10),
            background=self.colors["tree_bg"],
            fieldbackground=self.colors["tree_bg"],
            foreground=self.colors["tree_fg"],
            bordercolor=self.colors["border"],
            relief="flat",
        )
        style.configure(
            "Treeview.Heading",
            font=("Segoe UI", 10, "bold"),
            background=self.colors["panel_alt"],
            foreground=self.colors["text"],
            relief="flat",
            borderwidth=0,
        )
        style.map("Treeview", background=[("selected", self.colors["tree_selected"])], foreground=[("selected", self.colors["text"])])
        style.configure(
            "TCombobox",
            fieldbackground=self.colors["input"],
            background=self.colors["panel_alt"],
            foreground=self.colors["text"],
            bordercolor=self.colors["border"],
            arrowcolor=self.colors["text"],
            relief="flat",
            padding=7,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", self.colors["input"])],
            selectbackground=[("readonly", self.colors["panel_soft"])],
            selectforeground=[("readonly", self.colors["text"])],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=self.colors["panel_alt"],
            troughcolor=self.colors["bg"],
            bordercolor=self.colors["bg"],
            arrowcolor=self.colors["muted"],
        )
        style.configure(
            "Port.Horizontal.TProgressbar",
            troughcolor=self.colors["progress_trough"],
            background=self.colors["accent"],
            bordercolor=self.colors["progress_trough"],
            lightcolor=self.colors["accent"],
            darkcolor=self.colors["accent"],
        )

    def _make_panel(
        self,
        parent: tk.Widget,
        *,
        fill: str = "both",
        expand: bool = False,
        side: str | None = None,
        anchor: str | None = None,
        padx=0,
        pady=0,
        inner_padx: int = 18,
        inner_pady: int = 16,
        soft: bool = False,
    ) -> tk.Frame:
        outer = tk.Frame(parent, bg=self.colors["shadow"], bd=0, highlightthickness=0)
        pack_kwargs = {"fill": fill, "expand": expand, "padx": padx, "pady": pady}
        if side is not None:
            pack_kwargs["side"] = side
        if anchor is not None:
            pack_kwargs["anchor"] = anchor
        outer.pack(**pack_kwargs)
        inner = tk.Frame(
            outer,
            bg=self.colors["panel_soft"] if soft else self.colors["panel"],
            bd=0,
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            padx=inner_padx,
            pady=inner_pady,
        )
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        inner._portscope_shell = outer
        return inner

    def _build_menu(self) -> None:
        menu = tk.Menu(self.root)

        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label="Actualizar inventario", command=self.load_snapshot)
        file_menu.add_command(label="Exportar historial CSV", command=self.export_history)
        file_menu.add_command(label="Exportar inventario JSON", command=self.export_inventory_json)
        file_menu.add_command(label="Exportar inventario CSV", command=self.export_inventory_csv)
        file_menu.add_command(label="Limpiar historial benchmark", command=self.clear_benchmark_history)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self.root.destroy)
        menu.add_cascade(label="Archivo", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=0)
        edit_menu.add_command(label="Limpiar filtros", command=self._clear_all_filters)
        edit_menu.add_command(label="Reiniciar benchmark", command=self._reset_benchmark_form)
        edit_menu.add_command(label="Usar ultimo destino del historial", command=self._use_latest_history_target)
        menu.add_cascade(label="Edicion", menu=edit_menu)

        settings_menu = tk.Menu(menu, tearoff=0)
        settings_menu.add_command(label=self.theme_button_text.get(), command=self.toggle_theme)
        settings_menu.add_command(label="Restaurar preferencias visuales", command=self._reset_preferences)
        menu.add_cascade(label="Configuracion", menu=settings_menu)

        info_menu = tk.Menu(menu, tearoff=0)
        info_menu.add_command(label="Notas tecnicas", command=self._show_notes_dialog)
        info_menu.add_command(label="Logs recientes", command=self._show_logs_dialog)
        info_menu.add_command(label="Informacion de release", command=self._show_release_dialog)
        info_menu.add_command(label="Acerca de PortScope", command=self._show_about_dialog)
        menu.add_cascade(label="Info", menu=info_menu)

        for current_menu in (menu, file_menu, edit_menu, settings_menu, info_menu):
            current_menu.configure(
                bg=self.colors["panel"],
                fg=self.colors["text"],
                activebackground=self.colors["accent_soft"],
                activeforeground=self.colors["text"],
                bd=0,
                relief="flat",
            )

        self.root.configure(menu=menu)

    def _make_button(self, parent: tk.Widget, text: str, command, primary: bool) -> tk.Button:
        bg = self.colors["button"] if primary else self.colors["button_alt"]
        fg = self.colors["button_text"] if primary else self.colors["button_alt_text"]
        active_bg = self.colors["accent"] if primary else self.colors["accent_soft"]
        button = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", 10, "bold"),
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            padx=16,
            pady=10,
            cursor="hand2",
            highlightthickness=0,
            disabledforeground=self.colors["button_disabled_text"],
        )
        button._portscope_primary = primary
        return button

    def _set_button_enabled(self, button: tk.Button | None, enabled: bool) -> None:
        if button is None:
            return
        primary = bool(getattr(button, "_portscope_primary", False))
        normal_bg = self.colors["button"] if primary else self.colors["button_alt"]
        normal_fg = self.colors["button_text"] if primary else self.colors["button_alt_text"]
        active_bg = self.colors["accent"] if primary else self.colors["accent_soft"]
        button.configure(
            state="normal" if enabled else "disabled",
            bg=normal_bg if enabled else self.colors["button_disabled"],
            fg=normal_fg if enabled else self.colors["button_disabled_text"],
            activebackground=active_bg if enabled else self.colors["button_disabled"],
            activeforeground=normal_fg if enabled else self.colors["button_disabled_text"],
            cursor="hand2" if enabled else "arrow",
        )

    def _make_entry(self, parent: tk.Widget, textvariable: tk.StringVar, width: int) -> tk.Entry:
        return tk.Entry(parent, textvariable=textvariable, font=("Segoe UI", 10), width=width, bg=self.colors["input"], fg=self.colors["text"], insertbackground=self.colors["text"], relief="flat", bd=0, highlightthickness=1, highlightbackground=self.colors["border"], highlightcolor=self.colors["accent"])

    def _create_benchmark_metric_cards(self) -> None:
        if self.benchmark_metrics_container is None:
            return
        self.benchmark_metric_cards.clear()
        metrics = [
            ("write", "Write prom."),
            ("read", "Read prom."),
            ("best", "Mejor pico"),
            ("passes", "Pasadas"),
        ]
        for index, (key, title) in enumerate(metrics):
            shell = tk.Frame(self.benchmark_metrics_container, bg=self.colors["shadow"], bd=0, highlightthickness=0)
            shell.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 10, 0))
            card = tk.Frame(
                shell,
                bg=self.colors["panel_alt"],
                bd=0,
                highlightthickness=1,
                highlightbackground=self.colors["border"],
                padx=12,
                pady=10,
            )
            card.pack(fill="both", expand=True, padx=1, pady=1)
            title_label = tk.Label(card, text=title, font=("Segoe UI", 9, "bold"), bg=self.colors["panel_alt"], fg=self.colors["muted"])
            title_label.pack(anchor="w")
            value_label = tk.Label(card, text="--", font=("Segoe UI", 14, "bold"), bg=self.colors["panel_alt"], fg=self.colors["text"])
            value_label.pack(anchor="w", pady=(6, 0))
            self.benchmark_metric_cards[key] = (title_label, value_label)
            self.benchmark_metrics_container.grid_columnconfigure(index, weight=1)

    def _render_benchmark_metrics(self, result: dict[str, str] | None = None) -> None:
        defaults = {
            "write": "--",
            "read": "--",
            "best": "--",
            "passes": "--",
        }
        if result:
            defaults.update(
                {
                    "write": f"{result.get('write_avg_mb_s', '--')} MB/s",
                    "read": f"{result.get('read_avg_mb_s', '--')} MB/s",
                    "best": f"{max(result.get('write_best_mb_s', 0), result.get('read_best_mb_s', 0))} MB/s",
                    "passes": str(result.get("passes", "--")),
                }
            )
        for key, (_, value_label) in self.benchmark_metric_cards.items():
            value_label.configure(text=defaults[key])

    def _build_home_tab(self, parent: tk.Frame) -> None:
        wrapper = tk.Frame(parent, bg=self.colors["bg"], padx=8, pady=8)
        wrapper.pack(fill="both", expand=True)

        info_bar = self._make_panel(wrapper, fill="x", soft=True, inner_padx=18, inner_pady=12)
        tk.Label(
            info_bar,
            textvariable=self.summary_text,
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["info_bar"],
            fg=self.colors["text"],
        ).pack(anchor="w")
        self.home_info_label = tk.Label(
            info_bar,
            text="Preparando lectura inicial del equipo.",
            font=("Segoe UI", 10),
            bg=self.colors["info_bar"],
            fg=self.colors["info_text"],
            wraplength=1040,
            justify="left",
        )
        self.home_info_label.pack(anchor="w", pady=(4, 0))

        hero = self._make_panel(wrapper, fill="x", pady=(14, 0), inner_padx=20, inner_pady=16)
        hero_row = tk.Frame(hero, bg=self.colors["panel"])
        hero_row.pack(fill="x")
        hero_text = tk.Frame(hero_row, bg=self.colors["panel"])
        hero_text.pack(side="left", fill="x", expand=True)
        tk.Label(hero_text, text="Resumen rapido", font=("Segoe UI", 16, "bold"), bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w")
        tk.Label(
            hero_text,
            text="Encuentra rapido un dispositivo y corre pruebas sin navegar de mas.",
            font=("Segoe UI", 10),
            bg=self.colors["panel"],
            fg=self.colors["muted"],
            wraplength=700,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))
        quick_actions = tk.Frame(hero_row, bg=self.colors["panel"])
        quick_actions.pack(side="right", anchor="ne")
        self._make_button(quick_actions, "Ir a Benchmark", self._go_to_benchmark, primary=True).pack(side="left", padx=(0, 8))
        self._make_button(quick_actions, "Conectados ahora", self._go_to_connected, primary=False).pack(side="left", padx=(0, 8))
        self._make_button(quick_actions, "Ver Unidades", self._go_to_units, primary=False).pack(side="left")
        self.quick_summary_label = tk.Label(
            hero,
            text="Preparando sugerencias y proximos pasos...",
            font=("Segoe UI", 9),
            bg=self.colors["panel"],
            fg=self.colors["success"],
            justify="left",
            wraplength=920,
        )
        self.quick_summary_label.pack(anchor="w", pady=(10, 0))

        module_panel = self._make_panel(wrapper, fill="x", pady=(12, 0), soft=True, inner_padx=16, inner_pady=14)
        tk.Label(
            module_panel,
            text="Estado de modulos",
            font=("Segoe UI", 11, "bold"),
            bg=self.colors["panel_soft"],
            fg=self.colors["text"],
        ).pack(anchor="w")
        self.module_status_container = tk.Frame(module_panel, bg=self.colors["panel_soft"])
        self.module_status_container.pack(fill="x", pady=(10, 0))

        cards = tk.Frame(wrapper, bg=self.colors["bg"])
        cards.pack(fill="x", pady=(12, 0))
        for index in range(3):
            card_shell = tk.Frame(cards, bg=self.colors["shadow"], bd=0, highlightthickness=0)
            card_shell.pack(side="left", fill="x", expand=True, padx=(0 if index == 0 else 12, 0))
            card = tk.Frame(card_shell, bg=self.colors["panel"], bd=0, padx=16, pady=12, highlightbackground=self.colors["border"], highlightthickness=1)
            card.pack(fill="both", expand=True, padx=1, pady=1)
            tk.Label(card, text="--", font=("Segoe UI", 10, "bold"), bg=self.colors["panel"], fg=self.colors["muted"], name="title").pack(anchor="w")
            tk.Label(card, text="0", font=("Segoe UI", 20, "bold"), bg=self.colors["panel"], fg=self.colors["text"], name="value").pack(anchor="w", pady=(6, 2))
            tk.Label(card, text="", font=("Segoe UI", 9), bg=self.colors["panel"], fg=self.colors["muted"], name="caption").pack(anchor="w")
            self.card_frames.append(card)

    def _build_insights_tab(self, parent: tk.Frame) -> None:
        wrapper = tk.Frame(parent, bg=self.colors["bg"], padx=8, pady=8)
        wrapper.pack(fill="both", expand=True)

        left = self._make_panel(wrapper, fill="x", anchor="n", inner_padx=20, inner_pady=20)

        tk.Label(left, text="Alertas y hallazgos", font=("Segoe UI", 16, "bold"), bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w")
        tk.Label(left, text="Lo mas importante para actuar rapido. Las notas tecnicas completas estan arriba en Info.", font=("Segoe UI", 10), bg=self.colors["panel"], fg=self.colors["muted"]).pack(anchor="w", pady=(4, 10))
        self.alerts_container = tk.Frame(left, bg=self.colors["panel"])
        self.alerts_container.pack(fill="x", pady=(14, 0), anchor="n")
        self.notes_text = None

    def _build_connected_tab(self, parent: tk.Frame) -> ttk.Treeview:
        wrapper = tk.Frame(parent, bg=self.colors["bg"], padx=8, pady=8)
        wrapper.pack(fill="both", expand=True)

        top = self._make_panel(wrapper, fill="x", pady=(0, 12), inner_padx=18, inner_pady=16)
        tk.Label(top, text="Conectados ahora", font=("Segoe UI", 16, "bold"), bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w")
        tk.Label(top, text="Aqui veras lo que PortScope identifica como dispositivos conectados de usuario, con nombres mas utiles para tus pruebas.", font=("Segoe UI", 10), bg=self.colors["panel"], fg=self.colors["muted"], wraplength=980, justify="left").pack(anchor="w", pady=(4, 10))
        self.connected_changes_label = tk.Label(top, text="Aun no hay cambios detectados en esta sesion.", font=("Segoe UI", 10), bg=self.colors["panel"], fg=self.colors["success"], justify="left", wraplength=980)
        self.connected_changes_label.pack(anchor="w")

        return self._build_tree(
            wrapper,
            ("tipo", "nombre", "fabricante", "estado", "velocidad"),
            {"tipo": "Tipo", "nombre": "Nombre", "fabricante": "Fabricante", "estado": "Estado", "velocidad": "Velocidad"},
            "Busca por nombre, tipo o fabricante",
            tk.StringVar(),
            lambda: self._refresh_connected_view(),
        )

    def _build_tree(
        self,
        parent: tk.Frame,
        columns: tuple[str, ...],
        headings: dict[str, str],
        placeholder: str,
        filter_var: tk.StringVar,
        on_filter,
    ) -> ttk.Treeview:
        container = tk.Frame(parent, bg=self.colors["bg"], padx=8, pady=8)
        container.pack(fill="both", expand=True)
        filter_row = self._make_panel(container, fill="x", pady=(0, 10), soft=True, inner_padx=14, inner_pady=12)
        tk.Label(
            filter_row,
            text="Filtro",
            font=("Segoe UI", 10, "bold"),
            bg=self.colors["panel_soft"],
            fg=self.colors["muted"],
        ).pack(side="left", padx=(0, 10))
        entry = self._make_entry(filter_row, filter_var, 52)
        entry.pack(side="left", fill="x", expand=True)
        entry.insert(0, "")
        entry.bind("<KeyRelease>", lambda _event: on_filter())
        tk.Button(
            filter_row,
            text="Limpiar",
            command=lambda: self._clear_filter(filter_var, on_filter),
            font=("Segoe UI", 9, "bold"),
            bg=self.colors["button_alt"],
            fg=self.colors["button_alt_text"],
            relief="flat",
            bd=0,
            padx=10,
            pady=7,
            cursor="hand2",
        ).pack(side="left", padx=(10, 0))
        tk.Label(
            filter_row,
            text=placeholder,
            font=("Segoe UI", 9),
            bg=self.colors["panel_soft"],
            fg=self.colors["muted"],
        ).pack(side="left", padx=(12, 0))
        frame = self._make_panel(container, fill="both", expand=True, inner_padx=0, inner_pady=0)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for column in columns:
            tree.heading(column, text=headings[column])
            width = 150
            if column in {"nombre", "energia"}:
                width = 330
            elif column in {"fabricante", "etiqueta"}:
                width = 180
            tree.column(column, width=width, anchor="w")
        return tree

    def _build_benchmark_tab(self, parent: tk.Frame) -> None:
        wrapper = tk.Frame(parent, bg=self.colors["bg"], padx=8, pady=8)
        wrapper.pack(fill="both", expand=True)

        self.benchmark_canvas = tk.Canvas(
            wrapper,
            bg=self.colors["bg"],
            highlightthickness=0,
            bd=0,
        )
        self.benchmark_scrollbar = ttk.Scrollbar(
            wrapper,
            orient="vertical",
            command=self.benchmark_canvas.yview,
        )
        self.benchmark_canvas.configure(yscrollcommand=self.benchmark_scrollbar.set)
        self.benchmark_canvas.pack(side="left", fill="both", expand=True)
        self.benchmark_scrollbar.pack(side="right", fill="y")

        self.benchmark_inner = tk.Frame(self.benchmark_canvas, bg=self.colors["bg"])
        self.benchmark_window_id = self.benchmark_canvas.create_window(
            (0, 0),
            window=self.benchmark_inner,
            anchor="nw",
        )
        self.benchmark_inner.bind("<Configure>", self._on_benchmark_frame_configure)
        self.benchmark_canvas.bind("<Configure>", self._on_benchmark_canvas_configure)
        self._bind_benchmark_mousewheel()

        row = tk.Frame(self.benchmark_inner, bg=self.colors["bg"])
        row.pack(fill="both", expand=True)
        left = self._make_panel(row, side="left", fill="both", expand=True, inner_padx=20, inner_pady=20)
        right = self._make_panel(row, side="left", fill="both", padx=(14, 0), inner_padx=16, inner_pady=16)
        self.benchmark_row = row
        self.benchmark_left_panel = left
        self.benchmark_right_panel = right

        tk.Label(left, text="Benchmark de transferencia", font=("Segoe UI", 16, "bold"), bg=self.colors["panel"], fg=self.colors["text"]).grid(row=0, column=0, columnspan=4, sticky="w")
        tk.Label(left, text="Elige una unidad o carpeta y PortScope hara la prueba en una carpeta segura automaticamente.", font=("Segoe UI", 10), bg=self.colors["panel"], fg=self.colors["muted"]).grid(row=1, column=0, columnspan=4, sticky="w", pady=(4, 10))
        tk.Label(left, text="Unidad detectada", font=("Segoe UI", 10, "bold"), bg=self.colors["panel"], fg=self.colors["muted"]).grid(row=2, column=0, sticky="w", pady=(18, 6))
        self.target_combo = ttk.Combobox(left, textvariable=self.selected_target, state="readonly", width=62)
        self.target_combo.grid(row=3, column=0, columnspan=2, sticky="we", padx=(0, 12))
        self.target_combo.bind("<<ComboboxSelected>>", self._use_selected_target)
        tk.Label(left, text="O carpeta manual", font=("Segoe UI", 10, "bold"), bg=self.colors["panel"], fg=self.colors["muted"]).grid(row=4, column=0, sticky="w", pady=(18, 6))
        self._make_entry(left, self.selected_folder, 70).grid(row=5, column=0, sticky="we", padx=(0, 12))
        self._make_button(left, "Elegir carpeta", self.choose_folder, primary=False).grid(row=5, column=1, sticky="w")
        helper = tk.Frame(left, bg=self.colors["panel_soft"], bd=0, relief="flat", highlightbackground=self.colors["border"], highlightthickness=1, padx=14, pady=12)
        helper.grid(row=6, column=0, columnspan=3, sticky="we", pady=(16, 4))
        tk.Label(helper, text="Configuracion recomendada", font=("Segoe UI", 10, "bold"), bg=self.colors["panel_soft"], fg=self.colors["text"]).pack(anchor="w")
        tk.Label(helper, text="256 MB y 2 pasadas suelen dar un resultado estable sin tardar demasiado.", font=("Segoe UI", 9), bg=self.colors["panel_soft"], fg=self.colors["muted"]).pack(anchor="w", pady=(4, 0))
        tk.Label(left, text="Tamano del archivo (MB)", font=("Segoe UI", 10, "bold"), bg=self.colors["panel"], fg=self.colors["muted"]).grid(row=7, column=0, sticky="w", pady=(18, 6))
        ttk.Combobox(left, values=[64, 128, 256, 512, 1024], textvariable=self.file_size_mb, state="readonly", width=12).grid(row=8, column=0, sticky="w")
        tk.Label(left, text="Pasadas", font=("Segoe UI", 10, "bold"), bg=self.colors["panel"], fg=self.colors["muted"]).grid(row=7, column=1, sticky="w", pady=(18, 6))
        ttk.Combobox(left, values=[1, 2, 3], textvariable=self.pass_count, state="readonly", width=8).grid(row=8, column=1, sticky="w")
        self.run_button = self._make_button(left, "Iniciar prueba", self.start_benchmark, primary=True)
        self.run_button.grid(row=8, column=2, sticky="w", padx=(16, 0))
        self.cancel_button = self._make_button(left, "Cancelar", self.cancel_benchmark, primary=False)
        self.cancel_button.grid(row=8, column=3, sticky="w", padx=(10, 0))
        self._set_button_enabled(self.cancel_button, False)
        self.progress = ttk.Progressbar(left, style="Port.Horizontal.TProgressbar", mode="determinate", maximum=100)
        self.progress.grid(row=9, column=0, columnspan=4, sticky="we", pady=(18, 6))
        tk.Label(left, textvariable=self.progress_text, font=("Segoe UI", 10), bg=self.colors["panel"], fg=self.colors["muted"]).grid(row=10, column=0, columnspan=4, sticky="w")
        tk.Label(right, text="Resultado", font=("Segoe UI", 14, "bold"), bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w")
        self.benchmark_metrics_container = tk.Frame(right, bg=self.colors["panel"])
        self.benchmark_metrics_container.pack(fill="x", pady=(10, 10))
        self._create_benchmark_metric_cards()
        self.benchmark_result_label = tk.Label(right, textvariable=self.benchmark_text, justify="left", anchor="nw", font=("Segoe UI", 10), bg=self.colors["panel_alt"], fg=self.colors["text"], padx=14, pady=12, wraplength=360, bd=0, relief="flat", highlightbackground=self.colors["border"], highlightthickness=1)
        self.benchmark_result_label.pack(fill="x", pady=(0, 14))
        tk.Label(right, text="Historial", font=("Segoe UI", 14, "bold"), bg=self.colors["panel"], fg=self.colors["text"]).pack(anchor="w")
        tk.Label(right, text="Reusa una prueba anterior si quieres repetirla rapido.", font=("Segoe UI", 9), bg=self.colors["panel"], fg=self.colors["muted"]).pack(anchor="w", pady=(4, 10))
        self.history_tree = ttk.Treeview(right, columns=("fecha", "destino", "write", "read"), show="headings", height=12)
        for key, text, width in (("fecha", "Fecha", 140), ("destino", "Destino", 210), ("write", "Write MB/s", 110), ("read", "Read MB/s", 110)):
            self.history_tree.heading(key, text=text)
            self.history_tree.column(key, width=width, anchor="w")
        self.history_tree.pack(fill="both", expand=True, pady=(12, 12))
        history_actions = tk.Frame(right, bg=self.colors["panel"])
        history_actions.pack(fill="x")
        self._make_button(history_actions, "Exportar CSV", self.export_history, primary=True).pack(side="left")
        self._make_button(history_actions, "Usar destino", self.use_history_target, primary=False).pack(side="left", padx=(10, 0))
        self._make_button(history_actions, "Limpiar historial", self.clear_benchmark_history, primary=False).pack(side="left", padx=(10, 0))
        left.grid_columnconfigure(0, weight=1)
        left.grid_columnconfigure(1, weight=0)
        left.grid_columnconfigure(2, weight=0)
        left.grid_columnconfigure(3, weight=0)
        self.root.after(50, self._update_benchmark_scrollbar)

    def _bind_benchmark_mousewheel(self) -> None:
        if self.benchmark_mousewheel_bound:
            return
        self.root.bind_all("<MouseWheel>", self._on_benchmark_mousewheel, add="+")
        self.root.bind_all("<Button-4>", self._on_benchmark_mousewheel_linux, add="+")
        self.root.bind_all("<Button-5>", self._on_benchmark_mousewheel_linux, add="+")
        self.benchmark_mousewheel_bound = True

    def _is_benchmark_widget(self, widget: tk.Widget | None) -> bool:
        current = widget
        while current is not None:
            if current is self.benchmark_canvas or current is self.benchmark_inner:
                return True
            current = current.master
        return False

    def _can_scroll_benchmark_from_pointer(self) -> bool:
        if self.notebook is None or self.benchmark_canvas is None:
            return False
        try:
            current_tab = self.notebook.tab(self.notebook.select(), "text")
        except tk.TclError:
            return False
        if current_tab != "Benchmark":
            return False
        pointer_widget = self.root.winfo_containing(
            self.root.winfo_pointerx(),
            self.root.winfo_pointery(),
        )
        return self._is_benchmark_widget(pointer_widget)

    def _scroll_benchmark(self, units: int) -> None:
        if self.benchmark_canvas is None:
            return
        self.benchmark_canvas.yview_scroll(units, "units")
        self._update_benchmark_scrollbar()

    def _on_benchmark_mousewheel(self, event) -> None:
        if not self._can_scroll_benchmark_from_pointer():
            return
        delta = event.delta
        if delta == 0:
            return
        units = -1 * int(delta / 120) if abs(delta) >= 120 else (-1 if delta > 0 else 1)
        self._scroll_benchmark(units)

    def _on_benchmark_mousewheel_linux(self, event) -> None:
        if not self._can_scroll_benchmark_from_pointer():
            return
        units = -1 if getattr(event, "num", 0) == 4 else 1
        self._scroll_benchmark(units)

    def _on_benchmark_frame_configure(self, _event=None) -> None:
        if self.benchmark_canvas is not None:
            self.benchmark_canvas.configure(scrollregion=self.benchmark_canvas.bbox("all"))
        self._update_benchmark_scrollbar()

    def _on_benchmark_canvas_configure(self, event) -> None:
        if self.benchmark_canvas is not None and self.benchmark_window_id is not None:
            self.benchmark_canvas.itemconfigure(self.benchmark_window_id, width=event.width)
        self._refresh_benchmark_layout(event.width, event.height)
        self._update_benchmark_scrollbar()

    def _refresh_benchmark_layout(self, width: int, height: int) -> None:
        if self.benchmark_left_panel is None or self.benchmark_right_panel is None:
            return
        left_shell = getattr(self.benchmark_left_panel, "_portscope_shell", None)
        right_shell = getattr(self.benchmark_right_panel, "_portscope_shell", None)
        if left_shell is None or right_shell is None:
            return

        stacked = width < 1180 or height < 700
        compact = height < 700
        new_mode = "stacked" if stacked else "wide"
        if stacked:
            right_shell.pack_propagate(True)
        else:
            right_shell.configure(width=380)
            right_shell.pack_propagate(False)

        if new_mode != self.benchmark_layout_mode:
            left_shell.pack_forget()
            right_shell.pack_forget()
            if stacked:
                left_shell.pack(fill="both", expand=True)
                right_shell.pack(fill="both", expand=True, pady=(14, 0))
            else:
                left_shell.pack(side="left", fill="both", expand=True)
                right_shell.pack(side="left", fill="y", padx=(14, 0))
            self.benchmark_layout_mode = new_mode

        if self.history_tree is not None:
            self.history_tree.configure(height=8 if compact else 12)
        if self.benchmark_result_label is not None:
            wrap = 300 if stacked else 360
            self.benchmark_result_label.configure(wraplength=wrap)

    def _update_benchmark_scrollbar(self) -> None:
        if (
            self.benchmark_canvas is None
            or self.benchmark_scrollbar is None
            or self.benchmark_inner is None
        ):
            return
        self.root.update_idletasks()
        content_height = self.benchmark_inner.winfo_reqheight()
        canvas_height = self.benchmark_canvas.winfo_height()
        if content_height > canvas_height + 4:
            if not self.benchmark_scrollbar.winfo_ismapped():
                self.benchmark_scrollbar.pack(side="right", fill="y")
        else:
            self.benchmark_canvas.yview_moveto(0)
            if self.benchmark_scrollbar.winfo_ismapped():
                self.benchmark_scrollbar.pack_forget()

    def toggle_theme(self) -> None:
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.theme_button_text.set("Modo claro" if self.theme_name == "dark" else "Modo nocturno")
        self._save_preferences()
        self._build_ui()

    def _go_to_benchmark(self) -> None:
        if self.notebook is not None:
            self.notebook.select(6)

    def _go_to_connected(self) -> None:
        if self.notebook is not None:
            self.notebook.select(2)

    def _go_to_units(self) -> None:
        if self.notebook is not None:
            self.notebook.select(5)

    def _clear_filter(self, filter_var: tk.StringVar, on_filter) -> None:
        filter_var.set("")
        on_filter()

    def _clear_all_filters(self) -> None:
        self.usb_filter.set("")
        self.net_filter.set("")
        self.disk_filter.set("")
        self._refresh_usb_view()
        self._refresh_net_view()
        self._refresh_disk_view()

    def _reset_benchmark_form(self) -> None:
        self.selected_target.set("")
        self.selected_folder.set("")
        self.cancel_benchmark_event.clear()
        self.active_benchmark_passes = DEFAULT_PASSES
        self.active_benchmark_file_size_mb = DEFAULT_FILE_SIZE_MB
        self.file_size_mb.set(DEFAULT_FILE_SIZE_MB)
        self.pass_count.set(DEFAULT_PASSES)
        self.progress_text.set("Sin pruebas en ejecucion")
        self.benchmark_text.set("Selecciona una carpeta o una unidad para comenzar.")
        self._render_benchmark_metrics()
        if self.progress is not None:
            self.progress.configure(value=0)
        self._set_button_enabled(self.cancel_button, False)

    def _use_latest_history_target(self) -> None:
        if not self.history_entries:
            messagebox.showinfo("PortScope", "Todavia no hay historial disponible.")
            return
        latest = self.history_entries[-1]
        selected_path = str(latest.get("requested_target") or latest.get("target", ""))
        self.selected_folder.set(selected_path)
        self.selected_target.set("")
        self._go_to_benchmark()

    def _reset_preferences(self) -> None:
        self.theme_name = "light"
        self.theme_button_text.set("Modo nocturno")
        self.settings = {}
        save_settings(self.settings)
        self.selected_folder.set("")
        self.file_size_mb.set(DEFAULT_FILE_SIZE_MB)
        self.pass_count.set(DEFAULT_PASSES)
        self._build_ui()

    def _show_text_dialog(self, title: str, body: str) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg=self.colors["bg"])
        dialog.geometry("720x460")
        dialog.minsize(540, 360)
        dialog.transient(self.root)

        wrapper = self._make_panel(dialog, fill="both", expand=True, padx=16, pady=16, inner_padx=18, inner_pady=18)

        tk.Label(
            wrapper,
            text=title,
            font=("Segoe UI", 16, "bold"),
            bg=self.colors["panel"],
            fg=self.colors["text"],
        ).pack(anchor="w")

        text = tk.Text(
            wrapper,
            wrap="word",
            font=("Segoe UI", 11),
            bg=self.colors["panel_alt"],
            fg=self.colors["text"],
            relief="flat",
            padx=14,
            pady=14,
            insertbackground=self.colors["text"],
            highlightthickness=0,
        )
        text.pack(fill="both", expand=True, pady=(14, 0))
        text.insert("1.0", body)
        text.configure(state="disabled")

    def _show_notes_dialog(self) -> None:
        if not self.snapshot:
            messagebox.showinfo("PortScope", "Primero actualiza el inventario para generar notas.")
            return
        body = "\n".join(f"- {note}" for note in self.snapshot.notes)
        self._show_text_dialog("Notas tecnicas", body)

    def _show_logs_dialog(self) -> None:
        self._show_text_dialog("Logs recientes", read_recent_logs())

    def _show_release_dialog(self) -> None:
        body = "\n".join(
            [
                self.release_version,
                "",
                "Cambios destacados:",
                "- Fallos aislados por modulo: USB, red y unidades ya no tumban toda la lectura.",
                "- Logs locales para revisar errores y benchmarks recientes.",
                "- Cancelacion limpia de benchmark sin dejar carpeta de prueba.",
                "- Mejor asociacion entre destino elegido e historial.",
                "- Scroll vertical dinamico para pantallas pequenas.",
                "- Modo claro y modo nocturno.",
                "- Historial persistente y exportacion CSV.",
                "- Exportacion de inventario a JSON y CSV.",
                "- Tests automatizados incluidos en el proyecto.",
            ]
        )
        self._show_text_dialog("Informacion de release", body)

    def _show_about_dialog(self) -> None:
        body = "\n".join(
            [
                "PortScope",
                "",
                "Herramienta de escritorio para revisar puertos, enlaces y rendimiento de transferencia en Windows.",
                "",
                "La app busca ser clara para uso diario: inventario rapido, hallazgos utiles y pruebas de velocidad sin configuraciones complicadas.",
            ]
        )
        self._show_text_dialog("Acerca de PortScope", body)

    def choose_folder(self) -> None:
        folder = filedialog.askdirectory(title="Selecciona una carpeta para benchmark")
        if folder:
            self.selected_folder.set(folder)
            self.selected_target.set("")

    def _use_selected_target(self, _event=None) -> None:
        label = self.selected_target.get().strip()
        if label in self.target_map:
            self.selected_folder.set(self.target_map[label])

    def _resolve_source_label(self, folder: str) -> str:
        selected_label = self.selected_target.get().strip()
        if selected_label and self.target_map.get(selected_label) == folder:
            return selected_label
        for label, path in self.target_map.items():
            if path == folder:
                return label
        if self.snapshot is not None:
            for item in self.snapshot.disk_items:
                unit = item.get("unidad", "")
                if unit and folder.upper().startswith(unit.upper()):
                    return f"{unit}  |  {item.get('tipo', 'Ruta')}  |  {item.get('etiqueta', 'Sin etiqueta')}"
        return folder

    def load_snapshot(self) -> None:
        self._set_button_enabled(self.refresh_button, False)
        self.summary_text.set("Actualizando inventario de puertos y dispositivos...")
        self.info_text.set("Leyendo USB, red, unidades y hallazgos tecnicos desde Windows.")
        threading.Thread(target=self._load_snapshot_worker, daemon=True).start()
        self.root.after(120, self._poll_snapshot_queue)

    def _load_snapshot_worker(self) -> None:
        try:
            self.snapshot_queue.put(("done", collect_snapshot()))
        except Exception as exc:
            self.snapshot_queue.put(("error", str(exc)))

    def _poll_snapshot_queue(self) -> None:
        try:
            message = self.snapshot_queue.get_nowait()
        except queue.Empty:
            self.root.after(120, self._poll_snapshot_queue)
            return
        if message[0] == "error":
            messagebox.showerror("PortScope", f"No se pudo leer el inventario.\n\n{message[1]}")
            self.summary_text.set("No fue posible leer la informacion del sistema.")
            self.info_text.set("La lectura del hardware fallo. Revisa permisos o disponibilidad de los cmdlets de Windows.")
            self._set_button_enabled(self.refresh_button, True)
            return
        self.snapshot = message[1]
        self._refresh_usb_view()
        self._refresh_net_view()
        self._refresh_disk_view()
        self._update_dashboard()
        self._load_targets()
        self._set_button_enabled(self.refresh_button, True)

    def _fill_tree(self, tree: ttk.Treeview | None, rows: list[dict[str, str]], columns: tuple[str, ...]) -> None:
        if tree is None:
            return
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", "end", values=[row.get(column, "") for column in columns])

    def _filter_rows(self, rows: list[dict[str, str]], filter_var: tk.StringVar) -> list[dict[str, str]]:
        term = filter_var.get().strip().lower()
        if not term:
            return rows
        filtered = []
        for row in rows:
            haystack = " ".join(str(value) for value in row.values()).lower()
            if term in haystack:
                filtered.append(row)
        return filtered

    def _refresh_usb_view(self) -> None:
        if not self.snapshot:
            return
        rows = self._filter_rows(self.snapshot.usb_items, self.usb_filter)
        self._fill_tree(
            self.usb_tree,
            rows,
            ("categoria", "nombre", "fabricante", "estado", "velocidad", "energia"),
        )

    def _refresh_net_view(self) -> None:
        if not self.snapshot:
            return
        rows = self._filter_rows(self.snapshot.net_items, self.net_filter)
        self._fill_tree(
            self.net_tree,
            rows,
            ("nombre", "tipo", "estado", "conexion", "velocidad", "mac"),
        )

    def _refresh_disk_view(self) -> None:
        if not self.snapshot:
            return
        rows = self._filter_rows(self.snapshot.disk_items, self.disk_filter)
        self._fill_tree(
            self.disk_tree,
            rows,
            ("unidad", "etiqueta", "tipo", "salud", "libre", "tamano"),
        )

    def _refresh_connected_view(self) -> None:
        if not self.snapshot:
            return
        self._fill_tree(
            self.connected_tree,
            self.snapshot.connected_items,
            ("tipo", "nombre", "fabricante", "estado", "velocidad"),
        )

    def _describe_connected_changes(self, current_items: list[dict[str, str]]) -> str:
        current_ids = {item["id"] for item in current_items}
        if not self.previous_connected_ids:
            self.previous_connected_ids = current_ids
            return "Primera lectura de la sesion. Conecta o desconecta algo y luego actualiza para ver cambios."
        added = current_ids - self.previous_connected_ids
        removed = self.previous_connected_ids - current_ids
        self.previous_connected_ids = current_ids
        changes = []
        if added:
            names = [item["nombre"] for item in current_items if item["id"] in added]
            changes.append("Conectado: " + ", ".join(names))
        if removed:
            changes.append(f"Desconectado: {len(removed)} dispositivo(s)")
        return " | ".join(changes) if changes else "Sin cambios desde la ultima actualizacion."

    def _update_dashboard(self) -> None:
        if not self.snapshot:
            return
        self.summary_text.set(f"USB detectados: {len(self.snapshot.usb_items)} | Red: {len(self.snapshot.net_items)} | Unidades: {len(self.snapshot.disk_items)}")
        notes_line = " | ".join(self.snapshot.notes[:2])
        self.info_text.set(notes_line)
        self._refresh_connected_view()
        if self.home_info_label is not None:
            self.home_info_label.configure(
                text=f"{self.summary_text.get()} | {notes_line}"
            )
        for card_frame, card in zip(self.card_frames, self.snapshot.summary_cards):
            card_frame.children["title"].configure(text=card["title"], bg=self.colors["panel"], fg=self.colors["muted"])
            card_frame.children["value"].configure(text=card["value"], bg=self.colors["panel"], fg=self.colors["text"])
            card_frame.children["caption"].configure(text=card["caption"], bg=self.colors["panel"], fg=self.colors["muted"])
        self._render_module_statuses()
        body = [
            "Notas tecnicas de esta lectura\n",
            *[f"- {note}" for note in self.snapshot.notes],
            "",
            "Consejo practico",
            "- Ejecuta el benchmark sobre la raiz de una memoria USB, SSD externo o carpeta de red para medir velocidad real del trayecto.",
            "- Si un dispositivo aparece limitado a USB 2.0, revisa cable, adaptador o el puerto usado.",
        ]
        if self.notes_text is not None:
            self.notes_text.configure(state="normal")
            self.notes_text.delete("1.0", "end")
            self.notes_text.insert("1.0", "\n".join(body))
            self.notes_text.configure(state="disabled")
        if self.alerts_container is not None:
            for child in self.alerts_container.winfo_children():
                child.destroy()
            alerts = self.snapshot.alerts or ["No se detectaron alertas importantes en esta lectura."]
            for alert in alerts:
                shell = tk.Frame(self.alerts_container, bg=self.colors["shadow"], bd=0, highlightthickness=0)
                shell.pack(fill="x", pady=(0, 10), anchor="n")
                card_bg = self.colors["danger_soft"] if "no " in alert.lower() or "fallo" in alert.lower() else self.colors["panel_soft"]
                card = tk.Frame(shell, bg=card_bg, bd=0, relief="flat", highlightbackground=self.colors["border"], highlightthickness=1, padx=12, pady=10)
                card.pack(fill="x", padx=1, pady=1)
                headline = "Atencion" if card_bg == self.colors["danger_soft"] else "Dato util"
                tk.Label(
                    card,
                    text=headline,
                    font=("Segoe UI", 9, "bold"),
                    bg=card_bg,
                    fg=self.colors["warning"] if headline == "Atencion" else self.colors["accent"],
                ).pack(anchor="w", pady=(0, 4))
                tk.Label(
                    card,
                    text=alert,
                    font=("Segoe UI", 10),
                    bg=card_bg,
                    fg=self.colors["text"],
                    justify="left",
                    wraplength=980,
                ).pack(anchor="w")
        if self.quick_summary_label is not None:
            usb_devices = sum(1 for item in self.snapshot.usb_items if item["categoria"] == "Dispositivo")
            units_ready = len(self.snapshot.benchmark_targets)
            self.quick_summary_label.configure(
                text=(
                    f"Listo para usar: {usb_devices} dispositivo(s) USB visibles y {units_ready} destino(s) listos para benchmark.\n"
                    "Si quieres una prueba rapida, abre Benchmark y usa el destino sugerido."
                )
            )
        if self.connected_changes_label is not None:
            self.connected_changes_label.configure(
                text=self._describe_connected_changes(self.snapshot.connected_items)
            )

    def _render_module_statuses(self) -> None:
        if self.module_status_container is None or self.snapshot is None:
            return
        for child in self.module_status_container.winfo_children():
            child.destroy()
        for index, item in enumerate(self.snapshot.module_statuses):
            shell = tk.Frame(self.module_status_container, bg=self.colors["shadow"], bd=0, highlightthickness=0)
            shell.pack(side="left", fill="x", expand=True, padx=(0 if index == 0 else 10, 0))
            card_bg = self.colors["danger_soft"] if item["estado"] == "Error" else self.colors["panel"]
            card = tk.Frame(shell, bg=card_bg, bd=0, highlightthickness=1, highlightbackground=self.colors["border"], padx=12, pady=10)
            card.pack(fill="both", expand=True, padx=1, pady=1)
            accent = self.colors["warning"] if item["estado"] == "Error" else self.colors["success"]
            tk.Label(card, text=item["modulo"], font=("Segoe UI", 9, "bold"), bg=card_bg, fg=self.colors["muted"]).pack(anchor="w")
            tk.Label(card, text=item["estado"], font=("Segoe UI", 13, "bold"), bg=card_bg, fg=accent).pack(anchor="w", pady=(4, 2))
            tk.Label(card, text=item["detalle"], font=("Segoe UI", 9), bg=card_bg, fg=self.colors["text"], wraplength=260, justify="left").pack(anchor="w")

    def _load_targets(self) -> None:
        if self.target_combo is None or not self.snapshot:
            return
        self.target_map = {item["label"]: item["path"] for item in self.snapshot.benchmark_targets}
        labels = list(self.target_map.keys())
        self.target_combo["values"] = labels
        current_folder = self.selected_folder.get().strip()
        matching_label = next(
            (label for label, path in self.target_map.items() if path == current_folder),
            "",
        )
        if matching_label:
            self.selected_target.set(matching_label)
        elif labels and not current_folder:
            self.selected_target.set(labels[0])
            self.selected_folder.set(self.target_map[labels[0]])

    def start_benchmark(self) -> None:
        folder = self.selected_folder.get().strip()
        if not folder:
            messagebox.showwarning("PortScope", "Selecciona primero una carpeta o unidad donde se hara la prueba.")
            return
        source_label = self._resolve_source_label(folder)
        file_size_mb = int(self.file_size_mb.get())
        pass_count = int(self.pass_count.get())
        self.cancel_benchmark_event.clear()
        self.active_benchmark_file_size_mb = file_size_mb
        self.active_benchmark_passes = pass_count
        self._save_preferences()
        self._set_button_enabled(self.run_button, False)
        self._set_button_enabled(self.cancel_button, True)
        if self.progress is not None:
            self.progress.configure(value=0)
        self.progress_text.set("Preparando benchmark...")
        self.benchmark_text.set(
            "La prueba esta en ejecucion.\n\n"
            f"Destino asociado: {source_label}\n"
            f"Ruta elegida: {folder}\n"
            f"Archivo configurado: {file_size_mb} MB en {pass_count} pasada(s)\n"
            "Se usara una carpeta segura de trabajo dentro del destino elegido y se limpiara al terminar."
        )
        threading.Thread(
            target=self._benchmark_worker,
            args=(folder, source_label, file_size_mb, pass_count),
            daemon=True,
        ).start()
        self.root.after(120, self._poll_benchmark_queue)

    def cancel_benchmark(self) -> None:
        if self.cancel_button and str(self.cancel_button["state"]) != "disabled":
            self.cancel_benchmark_event.set()
            self.progress_text.set("Cancelando benchmark...")
            self.benchmark_text.set(
                "PortScope esta deteniendo la prueba y limpiando la carpeta temporal del benchmark."
            )

    def _benchmark_worker(
        self,
        folder: str,
        source_label: str,
        file_size_mb: int,
        pass_count: int,
    ) -> None:
        try:
            result = run_storage_benchmark(
                folder,
                file_size_mb,
                pass_count,
                progress_callback=self._enqueue_progress,
                cancel_check=self.cancel_benchmark_event.is_set,
                source_label=source_label,
            )
            self.benchmark_queue.put(("done", result))
        except BenchmarkCancelled as exc:
            self.benchmark_queue.put(("cancelled", str(exc)))
        except Exception as exc:
            self.benchmark_queue.put(("error", str(exc)))

    def _enqueue_progress(self, stage: str, pass_index: int, fraction: float) -> None:
        self.benchmark_queue.put(("progress", stage, pass_index, max(0.0, min(fraction, 1.0))))

    def _poll_benchmark_queue(self) -> None:
        pending = False
        try:
            while True:
                message = self.benchmark_queue.get_nowait()
                if message[0] == "progress":
                    _, stage, pass_index, fraction = message
                    total_passes = max(int(self.active_benchmark_passes), 1)
                    pass_span = 100 / total_passes
                    value = ((pass_index - 1) * pass_span) + (fraction * (pass_span / 2))
                    if stage == "read":
                        value += pass_span / 2
                    if self.progress is not None:
                        self.progress.configure(value=value)
                    label = "Escritura" if stage == "write" else "Lectura"
                    self.progress_text.set(f"Pasada {pass_index}/{total_passes}: {label} {value:.0f}%")
                    pending = True
                elif message[0] == "done":
                    result = message[1]
                    self.history_entries = append_history(result)
                    self._refresh_history_tree()
                    if self.progress is not None:
                        self.progress.configure(value=100)
                    self.progress_text.set("Prueba completada")
                    self._render_benchmark_metrics(result)
                    self.benchmark_text.set("\n".join([
                        f"Unidad asociada: {result['source_label']}",
                        f"Ruta de prueba: {result['target']}",
                        f"Destino pedido: {result['requested_target']}",
                        f"Archivo de prueba: {result['file_size_mb']} MB",
                        f"Pasadas: {result['passes']}",
                        f"Escritura promedio: {result['write_avg_mb_s']} MB/s",
                        f"Lectura promedio: {result['read_avg_mb_s']} MB/s",
                        f"Mejor escritura: {result['write_best_mb_s']} MB/s | Peor escritura: {result['write_worst_mb_s']} MB/s",
                        f"Mejor lectura: {result['read_best_mb_s']} MB/s | Peor lectura: {result['read_worst_mb_s']} MB/s",
                        f"Espacio libre antes: {result['free_space_before']} | despues: {result['free_space_after']}",
                    ]))
                    self._set_button_enabled(self.run_button, True)
                    self._set_button_enabled(self.cancel_button, False)
                    self._save_preferences()
                elif message[0] == "cancelled":
                    if self.progress is not None:
                        self.progress.configure(value=0)
                    self.progress_text.set("Prueba cancelada")
                    self._render_benchmark_metrics()
                    self.benchmark_text.set(
                        "El benchmark se cancelo correctamente.\n\n"
                        "La carpeta temporal de prueba se limpio para no dejar rastro."
                    )
                    self._set_button_enabled(self.run_button, True)
                    self._set_button_enabled(self.cancel_button, False)
                elif message[0] == "error":
                    if self.progress is not None:
                        self.progress.configure(value=0)
                    self.progress_text.set("La prueba fallo")
                    self._render_benchmark_metrics()
                    self.benchmark_text.set(f"No se pudo completar el benchmark.\n\n{message[1]}")
                    self._set_button_enabled(self.run_button, True)
                    self._set_button_enabled(self.cancel_button, False)
        except queue.Empty:
            pass
        if self.run_button and str(self.run_button["state"]) == "disabled":
            self.root.after(120, self._poll_benchmark_queue)
        elif pending:
            self.root.after(120, self._poll_benchmark_queue)

    def _refresh_history_tree(self) -> None:
        if self.history_tree is None:
            return
        self.history_tree.delete(*self.history_tree.get_children())
        for entry in reversed(self.history_entries[-12:]):
            destination = entry.get("source_label") or entry.get("requested_target") or entry.get("target", "")
            selected_path = entry.get("requested_target") or entry.get("target", "")
            self.history_tree.insert(
                "",
                "end",
                values=(entry.get("timestamp", ""), destination, entry.get("write_avg_mb_s", ""), entry.get("read_avg_mb_s", "")),
                tags=(selected_path,),
            )

    def use_history_target(self) -> None:
        if self.history_tree is None:
            return
        selection = self.history_tree.selection()
        if not selection:
            return
        selected_path = ""
        item = self.history_tree.item(selection[0])
        tags = item.get("tags", ())
        if tags:
            selected_path = str(tags[0])
        if selected_path:
            self.selected_folder.set(selected_path)
            self.selected_target.set("")
            if self.notebook is not None:
                self.notebook.select(6)

    def clear_benchmark_history(self) -> None:
        if not self.history_entries:
            messagebox.showinfo("PortScope", "No hay historial de benchmark para limpiar.")
            return
        confirmed = messagebox.askyesno(
            "Limpiar historial",
            "Se borrara todo el historial guardado de benchmarks.\n\n¿Quieres continuar?",
        )
        if not confirmed:
            return
        try:
            clear_history()
        except OSError as exc:
            messagebox.showerror(
                "PortScope",
                f"No se pudo limpiar el historial de benchmark.\n\n{exc}",
            )
            return
        self.history_entries = []
        self._refresh_history_tree()
        messagebox.showinfo("PortScope", "El historial de benchmark se limpio correctamente.")

    def export_history(self) -> None:
        if not self.history_entries:
            messagebox.showinfo("PortScope", "Todavia no hay historial para exportar.")
            return
        target = filedialog.asksaveasfilename(title="Exportar historial", defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="portscope-history.csv")
        if not target:
            return
        try:
            export_history_csv(self.history_entries, target)
            messagebox.showinfo("PortScope", "Historial exportado correctamente.")
        except OSError as exc:
            messagebox.showerror("PortScope", f"No se pudo exportar el historial.\n\n{exc}")

    def export_inventory_json(self) -> None:
        if not self.snapshot:
            messagebox.showinfo("PortScope", "Primero actualiza el inventario para exportarlo.")
            return
        target = filedialog.asksaveasfilename(
            title="Exportar inventario JSON",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="portscope-inventory.json",
        )
        if not target:
            return
        try:
            export_snapshot_json(self.snapshot, target)
            messagebox.showinfo("PortScope", "Inventario exportado en JSON correctamente.")
        except OSError as exc:
            messagebox.showerror("PortScope", f"No se pudo exportar el inventario JSON.\n\n{exc}")

    def export_inventory_csv(self) -> None:
        if not self.snapshot:
            messagebox.showinfo("PortScope", "Primero actualiza el inventario para exportarlo.")
            return
        target = filedialog.askdirectory(title="Selecciona una carpeta para exportar el inventario CSV")
        if not target:
            return
        try:
            files = export_snapshot_csv_bundle(self.snapshot, target)
            messagebox.showinfo(
                "PortScope",
                "Inventario exportado correctamente.\n\n" + "\n".join(files),
            )
        except OSError as exc:
            messagebox.showerror("PortScope", f"No se pudo exportar el inventario CSV.\n\n{exc}")


def main() -> None:
    root = tk.Tk()
    PortScopeApp(root)
    root.mainloop()

