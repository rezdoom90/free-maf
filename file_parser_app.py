#!/usr/bin/env python3
"""
File Parser GUI Application for Multi-Agent Framework
Stage 1: Foundation – Project Scanner & Shell
Stage 3: Button Handlers & Clipboard Assembly
Stage 4: Robustness & User Experience
"""

import os
import sys
import json
import subprocess
import traceback
import chardet
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

# ----------------------------------------------------------------------
# T1: Project Root Detection & Tree Builder
# ----------------------------------------------------------------------

def get_project_root() -> Path:
    """Return absolute path to project root (parent of agent/).
    When frozen by PyInstaller and placed in agent/, sys.executable
    points to agent/FileParserGui.exe -> .parent.parent is project root.
    When running as a script, __file__ is agent/file_parser_app.py -> .parent.parent.
    """
    if getattr(sys, 'frozen', False):
        # Running as a bundled .exe inside agent/
        return Path(sys.executable).resolve().parent.parent
    else:
        return Path(__file__).resolve().parent.parent

def scan_directory(root: Path) -> dict:
    """
    Recursively scan root, skipping ignored patterns.
    Returns nested dict:
        {"type": "dir", "name": "...", "children": [...]}
        or {"type": "file", "name": "...", "path": "relative/to/project"}
    """
    IGNORE_DIRS = {'.git', '__pycache__', 'node_modules', 'venv', '.idea'}
    IGNORE_SUFFIXES = ('.db-shm', '.db-wal')

    def _scan(current: Path, rel_parent: str = '') -> dict:
        try:
            entries = sorted(current.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return None  # skip inaccessible directories

        children = []
        for entry in entries:
            if entry.name in IGNORE_DIRS:
                continue
            if entry.name.endswith(IGNORE_SUFFIXES):
                continue

            rel_path = str(Path(rel_parent) / entry.name) if rel_parent else entry.name

            if entry.is_dir():
                result = _scan(entry, rel_path)
                if result is not None:
                    children.append({"type": "dir", "name": entry.name, "children": result.get("children", [])})
                else:
                    children.append({"type": "dir", "name": entry.name, "children": []})  # empty inaccessible dir
            else:
                children.append({"type": "file", "name": entry.name, "path": rel_path})
        return {"type": "dir", "name": current.name, "children": children}

    root_scan = _scan(root, '')
    if root_scan is None:
        return {"type": "dir", "name": root.name, "children": []}
    return root_scan

def flatten_tree(tree_dict: dict, parent: str = '') -> list:
    flat = []
    idx = 0
    root_children = tree_dict.get("children", [])

    def _flatten(children: list, parent_iid: str, depth: int = 0):
        nonlocal idx
        for child in children:
            iid = f"item{idx}"
            idx += 1
            is_dir = child["type"] == "dir"
            name = child["name"]
            rel_path = child.get("path", "")
            if is_dir:
                flat.append((parent_iid, iid, name, True, rel_path if rel_path else ''))
                _flatten(child.get("children", []), iid, depth + 1)
            else:
                flat.append((parent_iid, iid, name, False, rel_path))

    _flatten(root_children, parent)
    return flat

# ----------------------------------------------------------------------
# T2: MAP Generation Fallback
# ----------------------------------------------------------------------

def generate_map(project_root: Path) -> bool:
    """Generate MAP.md into agent/project/ using Python fallback. Always succeeds or raises."""
    generate_map_python(project_root)
    return True

def generate_map_python(project_root: Path):
    """Generate MAP.md in agent/project/MAP.md using text tree format."""
    lines = ["# PROJECT STRUCTURE MAP", "", "Source of Truth for LLM-agents. Reflects the actual codebase structure.", "", "```text"]

    def build_tree_lines(dir_path: Path, prefix: str = '', is_last: bool = True, is_root: bool = True):
        if is_root:
            # Root: output name without connector, then iterate children
            lines.append(f"+-- {dir_path.name}")
            try:
                entries = sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
            except PermissionError:
                return
            dirs = [e for e in entries if e.is_dir() and e.name not in {'.git', '__pycache__', 'node_modules', 'venv', '.idea'}]
            files = [e for e in entries if e.is_file() and not e.name.endswith(('.db-shm', '.db-wal'))]
            all_items = dirs + files
            for i, entry in enumerate(all_items):
                is_last_item = (i == len(all_items) - 1)
                connector = '\\-- ' if is_last_item else '+-- '
                if entry.is_dir():
                    lines.append(f"|   {connector}{entry.name}")
                    build_tree_lines(entry, '|   ' + ('    ' if is_last_item else '|   '), is_last_item, is_root=False)
                else:
                    lines.append(f"|   {connector}{entry.name}")
        else:
            try:
                entries = sorted(dir_path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
            except PermissionError:
                return
            dirs = [e for e in entries if e.is_dir() and e.name not in {'.git', '__pycache__', 'node_modules', 'venv', '.idea'}]
            files = [e for e in entries if e.is_file() and not e.name.endswith(('.db-shm', '.db-wal'))]
            all_items = dirs + files
            for i, entry in enumerate(all_items):
                is_last_item = (i == len(all_items) - 1)
                connector = '\\-- ' if is_last_item else '+-- '
                if entry.is_dir():
                    lines.append(f"{prefix}{connector}{entry.name}")
                    build_tree_lines(entry, prefix + ('    ' if is_last_item else '|   '), is_last_item, is_root=False)
                else:
                    lines.append(f"{prefix}{connector}{entry.name}")

    build_tree_lines(project_root)
    lines.append("```")
    # Write to agent/core/MAP.md
    map_path = project_root / 'agent' / 'project' / 'MAP.md'
    map_path.parent.mkdir(parents=True, exist_ok=True)
    with open(map_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

# ----------------------------------------------------------------------
# T3: ToolTip Class (Stage 4 T1)
# ----------------------------------------------------------------------

class ToolTip:
    """Create a tooltip for a given widget with consistent show/hide behavior."""
    def __init__(self, widget, text, delay_ms=400):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tip_window = None
        self._after_id = None
        widget.bind('<Enter>', self._schedule)
        widget.bind('<Leave>', self._cancel)

    def _schedule(self, event=None):
        self._cancel()  # Cancel any pending hide/show
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _cancel(self, event=None):
        if self._after_id is not None:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
        self._hide()

    def _show(self):
        self._hide()
        # Position near mouse pointer — robust for all widget types
        x = self.widget.winfo_pointerx() + 15
        y = self.widget.winfo_pointery() + 10
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        # Use app-level tooltip font if available, fallback to default
        try:
            app = self.widget.winfo_toplevel().children.get('!fileparserapp')
            if app is None:
                for child in self.widget.winfo_toplevel().winfo_children():
                    if isinstance(child, tk.Tk):
                        app = child
                        break
            tooltip_font = getattr(app, '_tooltip_font', ("tahoma", 8, "normal"))
        except Exception:
            tooltip_font = ("tahoma", 8, "normal")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=tooltip_font)
        label.pack()

    def _hide(self):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

# ----------------------------------------------------------------------
# T4: FileParserApp (with Stage 3 & 4 additions)
# ----------------------------------------------------------------------

class FileParserApp:
    _MAP_EXCLUDED_BUTTONS = {"get_files_only", "kickoff_new", "web_analyst"}

    REQUIRED_FILES = {
        "kickoff_new": [
            "agent/rules/GENERAL_RULES.md",
            "agent/rules/ANALYST_RULES.md"
        ],
        "kickoff_existing": [
            "agent/rules/GENERAL_RULES.md",
            "agent/rules/ANALYST_RULES.md",
            "agent/project/MAP.md"
        ],
        "analyst": [
            "agent/rules/GENERAL_RULES.md",
            "agent/rules/ANALYST_RULES.md",
            "agent/project/INFRASTRUCTURE.md",
            "agent/project/PROJECT_STATE.md",
            "agent/project/MAP.md"
        ],
        "web_analyst": [
            "agent/rules/GENERAL_RULES.md",
            "agent/rules/WEB_ANALYST_RULES.md",
            "agent/project/QUERY.md"
        ],
        "planner": [
            "agent/rules/GENERAL_RULES.md",
            "agent/rules/PLANNER_RULES.md",
            "agent/project/PROJECT_STATE.md",
            "agent/project/INFRASTRUCTURE.md",
            "agent/project/MAP.md"
        ],
        "executor": [
            "agent/rules/GENERAL_RULES.md",
            "agent/rules/EXECUTOR_RULES.md",
            "agent/project/PROJECT_STATE.md",
            "agent/project/INFRASTRUCTURE.md",
            "agent/project/MAP.md",
            "agent/project/PLAN.md"
        ],
        "judge_plan": [
            "agent/rules/GENERAL_RULES.md",
            "agent/rules/JUDGE_RULES.md",
            "agent/project/INFRASTRUCTURE.md",
            "agent/project/PROJECT_STATE.md",
            "agent/project/PLAN.md",
            "agent/project/MAP.md"
        ],
        "judge_master": [
            "agent/rules/GENERAL_RULES.md",
            "agent/rules/JUDGE_RULES.md",
            "agent/project/INFRASTRUCTURE.md",
            "agent/project/PROJECT_STATE.md",
            "agent/project/MASTER_PLAN.md",
            "agent/project/MAP.md"
        ],
        "judge_executor": [
            "agent/rules/GENERAL_RULES.md",
            "agent/rules/JUDGE_RULES.md",
            "agent/project/INFRASTRUCTURE.md",
            "agent/project/PROJECT_STATE.md",
            "agent/project/PLAN.md",
            "agent/project/MAP.md"
        ],
        "get_files_only": [],
        "get_files_with_map": []
    }

    def _apply_dark_theme(self):
        style = ttk.Style()
        # Use a theme that allows extensive colour configuration (clam)
        style.theme_use('clam')

        BG_DARK = "#2E2E2E"
        FG_LIGHT = "#DCDCDC"
        SELECT_BG = "#3E3E3E"
        BUTTON_BG = "#3C3C3C"
        TREE_BG = "#2E2E2E"
        TREE_FIELD_BG = "#333333"
        TREE_FG = "#DCDCDC"

        # General widgets
        style.configure('.', background=BG_DARK, foreground=FG_LIGHT, fieldbackground=TREE_FIELD_BG)
        style.configure('TFrame', background=BG_DARK)
        style.configure('TLabel', background=BG_DARK, foreground=FG_LIGHT)
        style.configure('TPanedwindow', background=BG_DARK)

        style.configure('TButton',
                        background=BUTTON_BG,
                        foreground=FG_LIGHT,
                        borderwidth=1,
                        relief='flat',
                        focusthickness=2,
                        focuscolor='#555')
        style.map('TButton',
                  background=[('active', '#4A4A4A'), ('pressed', '#2A2A2A')],
                  foreground=[('active', '#FFFFFF')])

        # Treeview
        style.configure('Treeview',
                        background=TREE_BG,
                       foreground=TREE_FG,
                        fieldbackground=TREE_FIELD_BG,
                        bordercolor='#555',
                        borderwidth=1)
        style.configure('Treeview.Heading',
                        background='#3E3E3E',
                        foreground=FG_LIGHT,
                        relief='flat')
        style.map('Treeview.Heading',
                  background=[('active', '#4A4A4A')])

        # Scrollbar (if any)
        style.configure('Vertical.TScrollbar',
                        background=BUTTON_BG,
                        troughcolor='#1E1E1E',
                        arrowcolor=FG_LIGHT)

        # Console frame background
        self.root.configure(bg=BG_DARK)

    def _style_console_widgets(self):
        """Apply dark theme to console frame widgets after they are created."""
        # console_frame and its children are styled via ttk, but tk.Text needs direct config.
        # The tk.Text widget is already configured with dark colors at creation time.
        # This method exists for any post-creation adjustments if needed.
        pass

    def __init__(self, root):
        self._insert_row_index = 0   # reset on every populate
        self.root = root
        self.root.title("File Parser for Multi-Agent")
        self.root.geometry("1300x700")
        self.root.minsize(900, 700)
        self._apply_dark_theme()
        self.root.resizable(True, True)

        self.check_states = {}
        self.locked_items = set()
        self.folder_was_checked = {}
        self.iid_to_relpath = {}
        self._saved_displaycolumns = None
        self.flat_list = []          # used for async populating
        self.progressbar = None
        self.tree_visible = True
        self._poll_interval_ms = 3000
        self._opening_file = False
        self.font_scale_index = 1
        self._tooltip_font = ("tahoma", 8, "normal")

        paned = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(paned, width=500)
        paned.add(left_frame, weight=1)

        ttk.Label(left_frame, text="Project Files").pack(anchor=tk.W, padx=5, pady=5)

        # Treeview inside left_frame
        self.tree = ttk.Treeview(left_frame, columns=("check",), show="tree headings")
        self.tree.heading("#0", text="Name")
        self.tree.heading("check", text="Check")
        self.tree.column("#0", width=400, stretch=True)
        self.tree.column("check", width=50, anchor=tk.CENTER, stretch=False)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_double_click)

        # Zebra tags (placed here to have access to TREE_BG, TREE_FG)
        self.tree.tag_configure('even', background="#2E2E2E", foreground="#DCDCDC")
        self.tree.tag_configure('odd', background="#393939", foreground="#DCDCDC")

        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(btn_frame, text="Clear", command=self.on_clear).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="All", command=self.on_select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="A−", width=3, command=lambda: self._change_font_scale(-1)).pack(side=tk.RIGHT, padx=1)
        ttk.Button(btn_frame, text="A+", width=3, command=lambda: self._change_font_scale(1)).pack(side=tk.RIGHT, padx=1)

        right_frame = ttk.Frame(paned, width=400)
        paned.add(right_frame, weight=0)

        ttk.Label(right_frame, text="Actions").pack(anchor=tk.W, padx=10, pady=10)

        action_buttons = [
            ("Kick-off (New)", "kickoff_new"),
            ("Kick-off (Existing)", "kickoff_existing"),
            ("Analyst", "analyst"),
            ("Web-Analyst", "web_analyst"),
            ("Planner", "planner"),
            ("Executor", "executor"),
            ("Judge Plan", "judge_plan"),
            ("Judge Master Plan", "judge_master"),
            ("Judge Executor", "judge_executor"),
            ("Get Files", "get_files_only"),
            ("Get Files + MAP.md", "get_files_with_map")
        ]
        for label, button_id in action_buttons:
            btn = ttk.Button(right_frame, text=label, width=30,
                             command=lambda bid=button_id: self._on_button_click(bid))
            btn.pack(pady=2, padx=10, fill=tk.X)
            tooltip_text = self._build_tooltip_text(button_id)
            ToolTip(btn, tooltip_text)

        # --- "Get MAP.md" independent button ---
        btn_map_only = ttk.Button(right_frame, text="Get MAP.md", width=30,
                                  command=self.on_get_map_only)
        btn_map_only.pack(pady=2, padx=10, fill=tk.X)
        ToolTip(btn_map_only, "Regenerate and copy MAP.md only (ignores file selection)")

        self.status_label = ttk.Label(right_frame, text="Double-click a file to open | Ready")
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        self.project_root = get_project_root()

        # --- Console Frame (PowerShell) ---
        console_frame = ttk.Frame(paned, width=350)
        paned.add(console_frame, weight=0)

        ttk.Label(console_frame, text="PowerShell Console").pack(anchor=tk.W, padx=5, pady=(10, 5))

        btn_row = ttk.Frame(console_frame)
        btn_row.pack(pady=2, padx=5, fill=tk.X)

        apply_btn = ttk.Button(btn_row, text="Apply Script", width=20,
                               command=self._on_apply_script)
        apply_btn.pack(side=tk.LEFT, padx=(0, 2))

        copy_console_btn = ttk.Button(btn_row, text="📋", width=3,
                                      command=self._on_copy_console_output)
        copy_console_btn.pack(side=tk.LEFT)
        ToolTip(copy_console_btn, "Copy output of last console command to clipboard")

        console_text_frame = ttk.Frame(console_frame)
        console_text_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.console_text = tk.Text(console_text_frame, wrap=tk.WORD, state=tk.NORMAL,
                                    bg="#1E1E1E", fg="#DCDCDC", insertbackground="#DCDCDC",
                                    selectbackground="#4A4A4A", font=("Consolas", 9))
        console_scrollbar = ttk.Scrollbar(console_text_frame, orient=tk.VERTICAL,
                                          command=self.console_text.yview)
        self.console_text.configure(yscrollcommand=console_scrollbar.set)

        self.console_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        console_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Configure console text tags
        self.console_text.tag_configure("stdout", foreground="#DCDCDC")
        self.console_text.tag_configure("stderr", foreground="#FF6B6B")

        # Insert initial PS prompt and set marks
        self.console_text.insert(tk.END, "PS>")
        prompt_start = self.console_text.index("end-1c linestart")
        self.console_text.mark_set("ps_prompt", prompt_start)
        self.console_text.mark_gravity("ps_prompt", tk.LEFT)
        # read-only boundary: everything before this mark is protected (PS> itself)
        boundary_pos = self.console_text.index(f"{prompt_start} + 3c")
        self.console_text.mark_set("readonly_boundary", boundary_pos)
        self.console_text.mark_gravity("readonly_boundary", tk.LEFT)

        # Track current working directory for manual commands (reset by Apply Script)
        self._console_cwd = str(self.project_root)

        # Bind Enter key and protection keys in console
        self.console_text.bind("<Return>", self._on_console_enter)
        self.console_text.bind("<BackSpace>", self._on_console_key_protect)
        self.console_text.bind("<Delete>", self._on_console_key_protect)
        self.console_text.bind("<Key>", self._on_console_key_protect)
        self.console_text.bind("<<Cut>>", lambda e: "break")
        self.console_text.bind("<Control-x>", lambda e: "break")
        self.populate_tree()
        self._start_polling()

    # -----------------------------------------------------------------
    # Tooltip helper
    # -----------------------------------------------------------------
    def _build_tooltip_text(self, button_id):
        if button_id == "get_files_only":
            return "Copy selected files only (no MAP.md)"
        if button_id == "get_files_with_map":
            return "Copy selected files + regenerated MAP.md"
        if button_id == "kickoff_new":
            lines = ["Required files (initial framework setup — no state files yet):"]
            for f in self.REQUIRED_FILES.get("kickoff_new", []):
                lines.append(f"• {f}")
            return "\n".join(lines)
        if button_id == "kickoff_existing":
            lines = ["Required files (initial framework setup — PROJECT_STATE.md and INFRASTRUCTURE.md are NOT included; Analyst will generate them):"]
            for f in self.REQUIRED_FILES.get("kickoff_existing", []):
                lines.append(f"• {f}")
            return "\n".join(lines)
        if button_id == "analyst":
            lines = ["Required files (PROJECT_STATE.md and INFRASTRUCTURE.md are attached only if they exist):"]
            for f in self.REQUIRED_FILES.get("analyst", []):
                lines.append(f"• {f}")
            return "\n".join(lines)
        if button_id == "web_analyst":
            lines = ["Required files (QUERY.md is attached by default; if absent, other files are still copied):"]
            for f in self.REQUIRED_FILES.get("web_analyst", []):
                lines.append(f"• {f}")
            return "\n".join(lines)
        files = self.REQUIRED_FILES.get(button_id, [])
        lines = ["Required files (PROJECT_STATE.md and INFRASTRUCTURE.md are attached only if they exist):"]
        for f in files:
            lines.append(f"• {f}")
        return "\n".join(lines)

    # -----------------------------------------------------------------
    # Tree population (async if needed)
    # -----------------------------------------------------------------
    def populate_tree(self):
        self._insert_row_index = 0
        """Scan directory and fill Treeview, asynchronously if large."""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.flat_list = []
        self.check_states.clear()
        self.locked_items.clear()
        self.folder_was_checked.clear()
        self.iid_to_relpath.clear()

        t0 = time.time()
        tree_data = scan_directory(self.project_root)
        self.flat_list = flatten_tree(tree_data, parent='')
        scan_time = time.time() - t0

        # If scanning + flattening was fast, insert synchronously
        if scan_time < 0.2 or len(self.flat_list) < 50:
            self._insert_all_sync()
        else:
            self._start_async_populate()

    def _insert_all_sync(self):
        self._insert_row_index = 0
        for parent_iid, iid, name, is_dir, rel_path in self.flat_list:
            parent = parent_iid if parent_iid else ''
            tag_list = ["dir" if is_dir else "file"]
            tag_list.append("even" if self._insert_row_index % 2 == 0 else "odd")
            self.tree.insert(parent, tk.END, iid=iid, text=name, values=("☐",),
                             tags=tuple(tag_list))
            self.iid_to_relpath[iid] = rel_path if not is_dir else ''
            self._insert_row_index += 1
        self._finalize_populate()

    def _start_async_populate(self):
        """Hide tree, show progressbar, and start chunked insertion."""
        self.tree.pack_forget()
        self.tree_visible = False
        left_frame = self.tree.master
        self.progressbar = ttk.Progressbar(left_frame, mode='determinate', maximum=len(self.flat_list))
        self.progressbar.pack(fill=tk.X, padx=5, pady=5)
        self.root.update_idletasks()
        self._insert_row_index = 0
        self._insert_chunk(0)

    def _insert_chunk(self, start_idx, chunk_size=50):
        end = min(start_idx + chunk_size, len(self.flat_list))
        for i in range(start_idx, end):
            parent_iid, iid, name, is_dir, rel_path = self.flat_list[i]
            parent = parent_iid if parent_iid else ''
            tag_list = ["dir" if is_dir else "file"]
            tag_list.append("even" if self._insert_row_index % 2 == 0 else "odd")
            self.tree.insert(parent, tk.END, iid=iid, text=name, values=("☐",),
                             tags=tuple(tag_list))
            self.iid_to_relpath[iid] = rel_path if not is_dir else ''
            self._insert_row_index += 1
        self.progressbar['value'] = end
        self.root.update_idletasks()
        if end < len(self.flat_list):
            self.root.after(10, lambda: self._insert_chunk(end, chunk_size))
        else:
            self._finalize_async_populate()

    def _finalize_async_populate(self):
        """Clean up progressbar, show tree, finalize states."""
        if self.progressbar:
            self.progressbar.destroy()
            self.progressbar = None
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.tree_visible = True
        self._finalize_populate()

    def _finalize_populate(self):
        """Set check states, open root nodes, etc."""
        for _, iid, _, is_dir, _ in self.flat_list:
            self.check_states[iid] = False
            if is_dir:
                self.folder_was_checked[iid] = False
        for root_iid in self.tree.get_children(''):
            self.tree.item(root_iid, open=True)
        self.status_label.config(text="Double-click a file to open | Ready")

    # -----------------------------------------------------------------
    # Event handler
    # -----------------------------------------------------------------
    def _on_tree_click(self, event):
        try:
            region = self.tree.identify_region(event.x, event.y)
            if region != "cell":
                return
            column = self.tree.identify_column(event.x)
            if column != "#1":
                return
            iid = self.tree.identify_row(event.y)
            if not iid:
                return
            if iid in self.locked_items:
                return
            self._toggle_item(iid)
        except Exception as e:
            print(f"[ERROR] Tree click handler: {e}")

    TEXT_EXTENSIONS = {'.md', '.py', '.java', '.xml', '.json', '.bat', '.ps1', '.txt', '.yml', '.properties', '.cfg', '.config'}

    def _on_double_click(self, event):
        """Open file on double-click with debouncing and extension filtering."""
        if self._opening_file:
            return
        try:
            iid = self.tree.identify_row(event.y)
            if not iid:
                return
            tags = self.tree.item(iid, "tags")
            if "dir" in tags:
                return
            rel_path = self.iid_to_relpath.get(iid, "")
            if not rel_path:
                return
            ext = os.path.splitext(rel_path)[1].lower()
            if ext not in self.TEXT_EXTENSIONS:
                return
            self._opening_file = True
            abs_path = self.project_root / rel_path
            if sys.platform == 'win32':
                os.startfile(abs_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(abs_path)])
            else:
                subprocess.run(['xdg-open', str(abs_path)])
            self.status_label.config(text=f"Opened: {rel_path}")
            self.root.after(500, self._reset_opening_flag)
        except Exception as e:
            self._opening_file = False
            print(f"[ERROR] Double-click handler: {e}")

    def _reset_opening_flag(self):
        self._opening_file = False
        self.status_label.config(text="Double-click a file to open | Ready")

    def _change_font_scale(self, delta):
        self.font_scale_index = max(0, min(3, self.font_scale_index + delta))
        self._apply_font_scale()

    def _apply_font_scale(self):
        scales = (0.8, 1.0, 1.25, 1.5)
        scale = scales[self.font_scale_index]
        tree_font_size = max(6, int(9 * scale))
        button_font_size = max(6, int(9 * scale))
        label_font_size = max(6, int(9 * scale))
        console_font_size = max(6, int(9 * scale))
        status_font_size = max(6, int(8 * scale))
        tooltip_font_size = max(6, int(8 * scale))

        style = ttk.Style()
        style.configure('TButton', font=('TkDefaultFont', button_font_size))
        style.configure('TLabel', font=('TkDefaultFont', label_font_size))
        style.configure('Treeview', font=('TkDefaultFont', tree_font_size))
        style.configure('Treeview.Heading', font=('TkDefaultFont', tree_font_size))

        self.console_text.configure(font=('Consolas', console_font_size))
        self._tooltip_font = ('tahoma', tooltip_font_size, 'normal')

    def _toggle_item(self, iid):
        current = self.check_states.get(iid, False)
        if current == "partial":
            was_checked = self.folder_was_checked.get(iid, False)
            new_full_state = not was_checked
            self._set_item_state(iid, new_full_state, lock_children=True)
            self.folder_was_checked[iid] = new_full_state
        else:
            new_state = not current
            is_dir = self.tree.item(iid, "tags")[0] == "dir"
            self._set_item_state(iid, new_state, lock_children=is_dir and new_state)
            if is_dir:
                self.folder_was_checked[iid] = new_state
            parent_iid = self.tree.parent(iid)
            while parent_iid:
                self._update_parent_state(parent_iid)
                parent_iid = self.tree.parent(parent_iid)

    def _set_item_state(self, iid, state, lock_children=False):
        self.check_states[iid] = state
        symbol = "☑" if state else "☐"
        self.tree.set(iid, "check", symbol)
        current_tags = list(self.tree.item(iid, "tags"))
        if iid in self.locked_items:
            if "locked" not in current_tags:
                current_tags.append("locked")
        else:
            if "locked" in current_tags:
                current_tags.remove("locked")
        self.tree.item(iid, tags=tuple(current_tags))
        if self.tree.item(iid, "tags")[0] == "dir":
            self._apply_to_children(iid, state, lock_children)

    def _apply_to_children(self, parent_iid, target_state, lock):
        children = self.tree.get_children(parent_iid)
        for child_iid in children:
            self.check_states[child_iid] = target_state
            symbol = "☑" if target_state else "☐"
            self.tree.set(child_iid, "check", symbol)
            if lock:
                self.locked_items.add(child_iid)
            else:
                self.locked_items.discard(child_iid)
            tags = list(self.tree.item(child_iid, "tags"))
            if lock:
                if "locked" not in tags:
                    tags.append("locked")
            else:
                if "locked" in tags:
                    tags.remove("locked")
            self.tree.item(child_iid, tags=tuple(tags))
            if self.tree.item(child_iid, "tags")[0] == "dir":
                self._apply_to_children(child_iid, target_state, lock)

    def _update_parent_state(self, parent_iid):
        children = self.tree.get_children(parent_iid)
        if not children:
            return
        all_true = True
        all_false = True
        for child in children:
            child_state = self.check_states.get(child, False)
            if child_state == "partial" or (child_state is True and not all_false):
                all_false = False
                all_true = False
            elif child_state is True:
                all_false = False
            elif child_state is False:
                all_true = False
        if all_true:
            self.check_states[parent_iid] = True
            self.tree.set(parent_iid, "check", "☑")
        elif all_false:
            self.check_states[parent_iid] = False
            self.tree.set(parent_iid, "check", "☐")
        else:
            self.check_states[parent_iid] = "partial"
            self.tree.set(parent_iid, "check", "◐")

    def _suspend_redraw(self):
        self._saved_displaycolumns = self.tree.cget("displaycolumns")
        self.tree.configure(displaycolumns=())

    def _resume_redraw(self):
        if self._saved_displaycolumns is not None:
            self.tree.configure(displaycolumns=self._saved_displaycolumns)

    # -----------------------------------------------------------------
    # Bulk operations (updated with status)
    # -----------------------------------------------------------------
    def on_clear(self):
        self.status_label.config(text="Clearing...")
        self.root.update_idletasks()
        self._suspend_redraw()
        try:
            for iid in self.check_states:
                self.check_states[iid] = False
                self.tree.set(iid, "check", "☐")
                tags = list(self.tree.item(iid, "tags"))
                if "locked" in tags:
                    tags.remove("locked")
                    self.tree.item(iid, tags=tuple(tags))
            self.locked_items.clear()
            for iid in self.check_states:
                if self.tree.item(iid, "tags")[0] == "dir":
                    self._update_parent_state(iid)
        finally:
            self._resume_redraw()
            self.status_label.config(text="Ready")

    def on_select_all(self):
        self.status_label.config(text="Selecting all...")
        self.root.update_idletasks()
        self._suspend_redraw()
        try:
            for root_iid in self.tree.get_children(''):
                if self.check_states.get(root_iid) is not True:
                    self._set_item_state(root_iid, True, lock_children=True)
                    self.folder_was_checked[root_iid] = True
        finally:
            self._resume_redraw()
            self.status_label.config(text="Ready")

    # ============ STAGE 3 METHODS ============

    def _start_polling(self):
        self.root.after(self._poll_interval_ms, self._poll_refresh)

    def _get_current_file_set(self) -> frozenset:
        """Return frozenset of all relative file paths using os.walk, respecting ignore rules."""
        IGNORE_DIRS = {'.git', '__pycache__', 'node_modules', 'venv', '.idea'}
        IGNORE_SUFFIXES = ('.db-shm', '.db-wal')
        file_set = set()
        for dirpath, dirnames, filenames in os.walk(self.project_root):
            dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
            for f in filenames:
                if f.endswith(IGNORE_SUFFIXES):
                    continue
                abs_path = os.path.join(dirpath, f)
                rel_path = os.path.relpath(abs_path, self.project_root)
                file_set.add(rel_path)
        return frozenset(file_set)

    def _poll_refresh(self):
        """Check for filesystem changes and rebuild tree if mismatch detected."""
        try:
            current_files = self._get_current_file_set()
            tree_files = {rel for rel in self.iid_to_relpath.values() if rel}
            if current_files != tree_files:
                added = current_files - tree_files
                removed = tree_files - current_files
                change_count = len(added) + len(removed)
                self._rebuild_tree_preserving_selection()
                self.status_label.config(text=f"Tree refreshed – {change_count} changes detected")
                self.root.after(3000, lambda: self.status_label.config(text="Ready"))
        except Exception as e:
            print(f"[Poll] Error during refresh: {e}")
        finally:
            self.root.after(self._poll_interval_ms, self._poll_refresh)

    def _rebuild_tree_preserving_selection(self):
        """Synchronously rebuild tree while restoring checked files that still exist."""
        # Save checked file paths
        checked_paths = set()
        for iid, rel in self.iid_to_relpath.items():
            if rel and self.check_states.get(iid, False) is True:
                checked_paths.add(rel)

        # Clear tree synchronously
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.flat_list = []
        self.check_states.clear()
        self.locked_items.clear()
        self.folder_was_checked.clear()
        self.iid_to_relpath.clear()

        # Re-scan and insert synchronously
        tree_data = scan_directory(self.project_root)
        self.flat_list = flatten_tree(tree_data, parent='')
        self._insert_all_sync()

        # Restore checked files that still exist
        for iid, rel in self.iid_to_relpath.items():
            if rel and rel in checked_paths:
                self.check_states[iid] = True
                self.tree.set(iid, "check", "☑")

        # Update parent folder states
        for iid in list(self.iid_to_relpath.keys()):
            if self.tree.item(iid, "tags")[0] == "dir":
                self._update_parent_state(iid)

    def _get_checked_files(self) -> list[str]:
        checked = []
        for iid, state in self.check_states.items():
            if state is not True:
                continue
            tags = self.tree.item(iid, "tags")
            if "dir" in tags:
                continue
            rel_path = self.iid_to_relpath.get(iid, "")
            if rel_path:
                checked.append(rel_path)
        return checked

    def _read_file_safe(self, rel_path: str) -> str:
        abs_path = self.project_root / rel_path
        try:
            with open(abs_path, 'rb') as f:
                raw = f.read()
            result = chardet.detect(raw)
            encoding = result.get('encoding')
            confidence = result.get('confidence', 0)
            if encoding and confidence > 0.7:
                try:
                    content = raw.decode(encoding)
                    print(f"[OK] {rel_path} ({encoding}, confidence={confidence:.2f})")
                    return content
                except (UnicodeDecodeError, LookupError):
                    pass
            # Fallback to sequential encoding detection
            encodings = ['utf-8-sig', 'utf-16', 'windows-1251', 'latin-1']
            last_error = None
            for enc in encodings:
                try:
                    content = raw.decode(enc)
                    print(f"[OK] {rel_path} ({enc})")
                    return content
                except UnicodeDecodeError as e:
                    last_error = e
                    continue
            print(f"[SKIP] {rel_path}: {type(last_error).__name__} — {last_error}")
            raise IOError(f"Failed to read {rel_path}: {last_error}")
        except Exception as e:
            print(f"[SKIP] {rel_path}: {type(e).__name__} — {e}")
            raise IOError(f"Failed to read {rel_path}: {e}")

    def _copy_to_clipboard(self, text: str):
        """Copy text to system clipboard."""
        try:
            import pyperclip
            pyperclip.copy(text)
        except ImportError:
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
            except tk.TclError as e:
                messagebox.showwarning("Clipboard Error", f"Could not access clipboard: {e}")
        except Exception as e:
            messagebox.showwarning("Clipboard Error", f"Could not copy to clipboard: {e}")

    def _on_button_click(self, button_id: str):
        cursor_changed = False
        try:
            self.root.config(cursor="watch")
            self.root.update_idletasks()
            cursor_changed = True

            required = [p.replace('\\', '/') for p in self.REQUIRED_FILES.get(button_id, [])]
            raw_user_files = self._get_checked_files()
            user_files = [p.replace('\\', '/') for p in raw_user_files]
            is_get_files_button = button_id.startswith('get_files_')

            if button_id in ("get_files_only", "get_files_with_map") and not user_files:
                messagebox.showerror("No Files Selected",
                                     "Please check at least one file in the tree before using this button.")
                return

            if button_id == "get_files_with_map":
                required = ["agent/project/MAP.md"]
            elif button_id == "get_files_only":
                required = []

            # --- Single linear pipeline: deduplicate, filter existence, resolve ---
            # Phase 1: merge required + user_files into a deduplicated candidate list
            candidates = []
            seen_rel = set()
            for path in required:
                if path not in seen_rel:
                    candidates.append(path)
                    seen_rel.add(path)
            for path in user_files:
                if path not in seen_rel:
                    candidates.append(path)
                    seen_rel.add(path)

            # Dump candidates to console so user can identify the source of stale paths
            print(f"[DEBUG] Button: {button_id} | Candidates ({len(candidates)}):")
            for c in candidates:
                print(f"  {c}")

            # Phase 2: generate MAP if needed (before existence check — MAP.md will be created)
            map_needed = (button_id not in self._MAP_EXCLUDED_BUTTONS and "agent/project/MAP.md" in candidates)
            if map_needed:
                try:
                    generate_map(self.project_root)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to generate MAP.md:\n{str(e)}")
                    return

            # Phase 3: resolve, filter existence, deduplicate by absolute path
            all_files_existing = []
            seen_resolved = set()
            for rel_path in candidates:
                abs_path = self.project_root / rel_path
                if not abs_path.exists():
                    # Required files that don't exist: silently skip (state files may be absent)
                    continue
                try:
                    resolved = abs_path.resolve()
                except Exception:
                    resolved = abs_path
                if resolved in seen_resolved:
                    print(f"[WARN] Duplicate absolute path — skipped: {rel_path} -> {resolved}")
                    continue
                seen_resolved.add(resolved)
                all_files_existing.append(rel_path)

            # Phase 4: read and assemble
            output_parts = []
            files_read_ok = 0
            skipped_status = []
            failed_required = []

            for rel_path in all_files_existing:
                try:
                    content = self._read_file_safe(rel_path)
                except Exception as e:
                    if rel_path in required:
                        failed_required.append((rel_path, str(e)))
                        continue
                    else:
                        skipped_status.append(rel_path)
                        continue

                output_parts.append(f'<file name="{rel_path}">\n{content}\n</file>\n')
                files_read_ok += 1

            # Only error out if GENERAL_RULES.md or the role-specific RULES file failed to read.
            # These are strictly mandatory for agent operation.
            STRICTLY_MANDATORY_SUFFIXES = ('GENERAL_RULES.md', '_RULES.md')
            critical_failures = [p for p, _ in failed_required if p.endswith(STRICTLY_MANDATORY_SUFFIXES)]
            if critical_failures:
                details = "\n".join(f"• {p}: {msg}" for p, msg in failed_required if p in critical_failures)
                messagebox.showerror("Critical File Read Error",
                                     "The following mandatory files could not be read:\n" + details +
                                     "\n\nNo content was copied to clipboard.")
                return

            # Non-critical missing files (PROJECT_STATE.md, INFRASTRUCTURE.md, QUERY.md, MAP.md) are silently skipped.

            print(f"Прочитано: {files_read_ok}, пропущено: {len(skipped_status)}")

            if skipped_status and files_read_ok > 0:
                detail_lines = [f"• {p}" for p in skipped_status[:3]]
                if len(skipped_status) > 3:
                    detail_lines.append(f"…и ещё {len(skipped_status) - 3} файлов")
                messagebox.showwarning(
                    "Пропущены файлы",
                    "Не удалось прочитать следующие файлы:\n" + "\n".join(detail_lines)
                )

            if skipped_status:
                self.status_label.config(text=f"Skipped {len(skipped_status)} unreadable file(s): {', '.join(skipped_status[:3])}...")
                self.root.update_idletasks()
                self.root.after(5000, lambda: self.status_label.config(text="Ready"))

            if files_read_ok == 0:
                msg = "Не удалось прочитать ни одного файла."
                if skipped_status:
                    msg += f" {len(skipped_status)} файл(ов) пропущено — подробности в окне предупреждения."
                messagebox.showinfo("Nothing to copy", msg)
                return

            final_text = "".join(output_parts)

            # Validate each assembled block (not content)
            for i, part in enumerate(output_parts):
                if not (part.startswith('<file name="') and part.rstrip().endswith('</file>')):
                    messagebox.showerror("Internal Error",
                                         f"Malformed block for file index {i}. Clipboard not updated.")
                    return

            # Debug: print summary of final output
            tag_count = final_text.count('<file name="')
            print(f"[DEBUG] Final output: {tag_count} <file> blocks, {len(final_text)} chars")
            print(f"[DEBUG] First 150 chars: {final_text[:150]}")

            self._copy_to_clipboard(final_text)

            self.status_label.config(text=f"Copied {files_read_ok} files to clipboard")
            self.root.after(3000, lambda: self.status_label.config(text="Ready"))

        except Exception as e:
            messagebox.showerror("Unexpected Error", traceback.format_exc())
        finally:
            if cursor_changed:
                self.root.config(cursor="")
                self.root.update_idletasks()

    def on_get_map_only(self):
        """Regenerate MAP.md and copy it to clipboard, ignoring all checkboxes."""
        try:
            self.root.config(cursor="watch")
            self.root.update_idletasks()
            generate_map(self.project_root)
            map_path = self.project_root / 'agent' / 'project' / 'MAP.md'
            if not map_path.exists():
                messagebox.showerror("Error", "MAP.md was not created.")
                return
            content = self._read_file_safe('agent/project/MAP.md')
            wrapped = f'<file name="agent/project/MAP.md">\n{content}\n</file>\n'
            self._copy_to_clipboard(wrapped)
            self.status_label.config(text="MAP.md copied to clipboard")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate MAP.md:\n{e}")
        finally:
            self.root.config(cursor="")
            self.root.update_idletasks()

    def _on_copy_console_output(self):
        """Copy output of the last command (text between the last two PS> prompts)."""
        import pyperclip
        full_text = self.console_text.get("1.0", tk.END)
        last_ps = full_text.rfind("PS>")
        if last_ps == -1:
            output = full_text.rstrip("\n")
        else:
            # Find the previous PS> (the command that produced the output)
            prev_ps = full_text.rfind("PS>", 0, last_ps)
            if prev_ps == -1:
                # Only one PS> in console — copy everything after its line
                nl = full_text.find("\n", last_ps)
                output = full_text[nl + 1:last_ps].rstrip("\n") if nl != -1 else ""
            else:
                # Output is everything after the previous PS> line, before the last PS>
                nl = full_text.find("\n", prev_ps)
                if nl != -1 and nl < last_ps:
                    output = full_text[nl + 1:last_ps].rstrip("\n")
                else:
                    output = ""
        if output:
            pyperclip.copy(output)
            self.status_label.config(text="Console output copied to clipboard")
            self.root.after(3000, lambda: self.status_label.config(text="Ready"))
        else:
            self.status_label.config(text="No console output to copy")
            self.root.after(3000, lambda: self.status_label.config(text="Ready"))

    def _on_apply_script(self):
        """Read clipboard, save as code_mutation.ps1, execute with async poll."""
        import pyperclip
        script_content = pyperclip.paste()

        # Append to existing log with separator (user preference: do not clear console)
        self.console_text.insert(tk.END, "\n" + "─" * 50 + "\nRunning code_mutation.ps1...\n", "stdout")
        self.console_text.see(tk.END)
        self.root.update_idletasks()

        # Reset manual console cwd to project root for script execution
        self._console_cwd = str(self.project_root)

        # Save script to file
        script_path = self.project_root / "code_mutation.ps1"
        try:
            with open(script_path, 'w', encoding='utf-8-sig') as f:
                f.write(script_content)
        except Exception as e:
            self.console_text.insert(tk.END, f"[Error] Failed to write script: {e}\n", "stderr")
            self.console_text.see(tk.END)
            return

        # Execute with async poll as required by PLAN.md step 3.2
        try:
            encoding = 'cp866' if sys.platform == 'win32' else 'utf-8'
            process = subprocess.Popen(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", ".\\code_mutation.ps1"],
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding=encoding,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
        except Exception as e:
            self.console_text.insert(tk.END, f"[Error] Failed to start PowerShell: {e}\n", "stderr")
            self.console_text.see(tk.END)
            return

        self._process = process
        self._read_process_output()

    def _read_process_output(self):
        """Poll process pipes and append to console_text asynchronously."""
        process = self._process
        if process is None:
            return
        while True:
            line = process.stdout.readline()
            if line:
                self.console_text.insert(tk.END, line, "stdout")
                self.console_text.see(tk.END)
            else:
                break
        while True:
            line = process.stderr.readline()
            if line:
                self.console_text.insert(tk.END, line, "stderr")
                self.console_text.see(tk.END)
            else:
                break
        exit_code = process.poll()
        if exit_code is not None:
            if exit_code == 0:
                self.console_text.insert(tk.END, f"\n[Script completed with exit code {exit_code}]\n", "stdout")
            else:
                self.console_text.insert(tk.END, f"\n[Script failed with exit code {exit_code}]\n", "stderr")
            self.console_text.insert(tk.END, "PS>")
            prompt_start = self.console_text.index("end-1c linestart")
            self.console_text.mark_set("ps_prompt", prompt_start)
            self.console_text.mark_gravity("ps_prompt", tk.LEFT)
            boundary_pos = self.console_text.index(f"{prompt_start} + 3c")
            self.console_text.mark_set("readonly_boundary", boundary_pos)
            self.console_text.mark_gravity("readonly_boundary", tk.LEFT)
            self.console_text.see(tk.END)
            self._process = None
        else:
            self.root.after(100, self._read_process_output)

    def _on_console_enter(self, event):
        """Execute the command typed after the last PS> prompt asynchronously."""
        # Extract command: from after "PS>" (3 chars) to end-1c
        try:
            cmd_start = self.console_text.index("ps_prompt + 3c")
            cmd_end = self.console_text.index("end-1c")
            cmd = self.console_text.get(cmd_start, cmd_end)
        except tk.TclError:
            cmd = ""
        cmd = cmd.strip()
        if not cmd:
            return "break"

        # Move to a new line for output — no command echo (it's already visible in the input line)
        self.console_text.insert(tk.END, "\n")
        self.console_text.see(tk.END)

        # Capture current cwd for the thread
        current_cwd = self._console_cwd

        import threading
        def run_command():
            try:
                kwargs = dict(
                    cwd=current_cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                if sys.platform == 'win32':
                    kwargs['encoding'] = 'cp866'
                process = subprocess.Popen(["powershell", "-Command", cmd], **kwargs)
                stdout, stderr = process.communicate()
                # If it was a cd command, update the working directory for subsequent commands
                cmd_lower = cmd.strip().lower()
                if cmd_lower.startswith('cd ') or cmd_lower == 'cd':
                    parts = cmd.strip().split(maxsplit=1)
                    if len(parts) > 1:
                        new_dir = parts[1].strip().strip('"').strip("'")
                    else:
                        new_dir = str(self.project_root)
                    if not Path(new_dir).is_absolute():
                        new_dir = str(Path(current_cwd) / new_dir)
                    new_dir = str(Path(new_dir).resolve())
                    if Path(new_dir).is_dir():
                        new_cwd = new_dir
                    else:
                        new_cwd = current_cwd
                        stderr = (stderr or '') + f"Set-Location : Cannot find path '{new_dir}'\n"
                else:
                    new_cwd = current_cwd
            except Exception as e:
                stdout = ""
                stderr = str(e)
                new_cwd = current_cwd
            self.root.after(0, lambda: self._finish_console_command(stdout, stderr, new_cwd))

        threading.Thread(target=run_command, daemon=True).start()
        return "break"

    def _on_console_key_protect(self, event):
        """Prevent deletion/modification of the PS> prompt and read-only history."""
        # Allowed keys: regular input, arrows, clipboard, etc.
        # We block BackSpace/Delete if they would affect the protected area.
        if event.keysym in ('BackSpace', 'Delete'):
            try:
                sel_start = self.console_text.index(tk.SEL_FIRST)
                sel_end = self.console_text.index(tk.SEL_LAST)
            except tk.TclError:
                sel_start = self.console_text.index(tk.INSERT)
                sel_end = sel_start

            boundary = self.console_text.index("readonly_boundary")
            # If the selection or insertion point touches the read-only area, block
            if self.console_text.compare(sel_start, "<", boundary) or \
                    self.console_text.compare(sel_end, "<=", boundary):
                # But allow delete if the whole selection is after boundary
                if event.keysym == 'Delete' and self.console_text.compare(sel_start, ">=", boundary):
                    pass  # allow
                else:
                    return "break"
        elif event.char and len(event.char) > 0:
            # Check insertion point
            insert = self.console_text.index(tk.INSERT)
            boundary = self.console_text.index("readonly_boundary")
            if self.console_text.compare(insert, "<", boundary):
                # Move cursor to the end and insert there
                self.console_text.mark_set(tk.INSERT, "end-1c")
        # Allow the event

    def _finish_console_command(self, stdout, stderr, new_cwd):
        """Called in main thread after async command completes."""
        if stdout:
            self.console_text.insert(tk.END, stdout, "stdout")
        if stderr:
            self.console_text.insert(tk.END, stderr, "stderr")
        # Update current working directory (cd is tracked, reset only by Apply Script)
        self._console_cwd = new_cwd
        # Append fresh prompt
        self.console_text.insert(tk.END, "PS>")
        prompt_start = self.console_text.index("end-1c linestart")
        self.console_text.mark_set("ps_prompt", prompt_start)
        self.console_text.mark_gravity("ps_prompt", tk.LEFT)
        # Update read-only boundary: protect PS> itself
        boundary_pos = self.console_text.index(f"{prompt_start} + 3c")
        self.console_text.mark_set("readonly_boundary", boundary_pos)
        self.console_text.mark_gravity("readonly_boundary", tk.LEFT)
        self.console_text.see(tk.END)

def main():
    root = tk.Tk()
    app = FileParserApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()