import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font
import json
import re
import os
from typing import Optional, List, Tuple
from threading import Thread
import time
MIDNIGHT_THEME = {
    "bg_main": "#0f0f10",
    "bg_entry": "#1b1c20",
    "bg_output": "#1a1b1f",
    "fg_text": "#f8f8f2",
    "fg_entry": "#8be9fd",
    "fg_label": "#bd93f9",
    "btn_browse_bg": "#282a36",     # Used for "Load File"
    "btn_browse_fg": "#ff79c6",     # Used for "Load File" + "Save" + number highlight
    "btn_refresh_bg": "#44475a",     # Used for "Auto Repair" + "Clear"
    "btn_refresh_fg": "#50fa7b",     # Used for "Auto Repair" + "Clear" + string highlight
    "btn_copy_bg": "#6272a4",       # Used for "Search" + selection
    "btn_copy_fg": "#f8f8f2",       # Used for "Search"
    "diff_bg": "#D44545",
}
class TextWithLineNumbers(tk.Frame):
    """A custom tkinter frame that bundles a Text widget with line numbers."""
    def __init__(self, master, **kwargs):
        super().__init__(master)
        self.text_font = kwargs.get('font', ("Consolas", 10))
        if isinstance(self.text_font, str):
            self.text_font = font.Font(family="Consolas", size=10)
            kwargs['font'] = self.text_font
        self.line_numbers = tk.Text(
            self,
            width=4,
            state=tk.DISABLED,
            font=self.text_font,
            wrap=tk.NONE,
            borderwidth=0,
            relief=tk.FLAT
        )
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)
        self.text = tk.Text(self, **kwargs)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.v_scroll = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._yview)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.config(yscrollcommand=self.v_scroll.set)
        self.line_numbers.config(yscrollcommand=self.v_scroll.set)
        self.text.bind("<<Modified>>", self._on_text_change, add=True)
        self.text.bind("<Configure>", self._on_text_change, add=True)
        self.text.bind("<KeyRelease>", self._on_text_change, add=True)
        self.text.bind("<MouseWheel>", self._on_text_change, add=True)
        self._on_text_change() # Initial draw
    def _yview(self, *args):
        """Unified vertical scroll command."""
        self.text.yview(*args)
        self.line_numbers.yview(*args)
        self._on_text_change() # Redraw on scroll
        return "break"
    def _on_text_change(self, event=None):
        """Callback to redraw line numbers when text or view changes."""
        self.redraw_line_numbers()
        if event and str(event) == 'TkTextModify':
            self.text.event_generate("<<Modified>>")
    def redraw_line_numbers(self):
        """Updates the line number column."""
        self.line_numbers.config(state=tk.NORMAL)
        self.line_numbers.delete("1.0", tk.END)
        line_count = int(self.text.index("end-1c").split('.')[0])
        line_numbers_str = "\n".join(str(i) for i in range(1, line_count + 1))
        self.line_numbers.insert("1.0", line_numbers_str)
        self.line_numbers.yview_moveto(self.text.yview()[0])
        self.line_numbers.config(state=tk.DISABLED)
    def highlight_line(self, lineno: int, tag: str):
        """Highlights a specific line in both text and line numbers."""
        line_end = self.text.index(f"{lineno}.end")
        self.text.tag_add(tag, f"{lineno}.0", line_end)
        self.line_numbers.tag_add(tag, f"{lineno}.0", f"{lineno}.end")
    def clear_highlight(self, tag: str):
        """Removes all instances of a tag from both widgets."""
        self.text.tag_remove(tag, "1.0", tk.END)
        self.line_numbers.tag_remove(tag, "1.0", tk.END)
    def update_font(self, font: font.Font):
        """Updates the font for both text and line numbers."""
        self.text_font = font
        self.text.config(font=self.text_font)
        self.line_numbers.config(font=self.text_font, width=max(4, len(self.text.index("end-1c").split('.')[0]) + 1))
        self.redraw_line_numbers()
    def configure_colors(self, bg: str, fg: str, ln_bg: str, ln_fg: str, insert_fg: str):
        """Applies theme colors to the widgets."""
        self.text.config(background=bg, foreground=fg, insertbackground=insert_fg)
        self.line_numbers.config(background=ln_bg, foreground=ln_fg)
        self.config(bg=ln_bg) # Frame background
class JSONRepairApp:
    def __init__(self, root):
        self.root = root
        self.root.title("JSON Auto Repair & Viewer")
        self.root.geometry("1200x700")
        self.root.minsize(900, 600)
        self.current_data = None
        self.last_input_time = 0
        self.debounce_delay = 500  # ms
        self.font_size = 10
        self.text_font = font.Font(family="Consolas", size=self.font_size)
        self.create_widgets()
        self.setup_bindings()
        self.setup_styles() # Apply the MIDNIGHT_THEME
    def setup_styles(self):
        """Configures all widgets and styles using MIDNIGHT_THEME."""
        style = ttk.Style()
        style.theme_use('clam')
        self.root.configure(bg=MIDNIGHT_THEME["bg_main"])
        style.configure('.', 
            background=MIDNIGHT_THEME["bg_main"], 
            foreground=MIDNIGHT_THEME["fg_text"], 
            fieldbackground=MIDNIGHT_THEME["bg_entry"])
        style.configure('TButton', 
            background=MIDNIGHT_THEME["btn_refresh_bg"], 
            foreground=MIDNIGHT_THEME["btn_refresh_fg"],
            font=("Segoe UI", 9, "bold"),
            borderwidth=0,
            relief=tk.FLAT)
        style.map('TButton', 
            background=[('active', MIDNIGHT_THEME["btn_copy_bg"])])
        style.configure('Browse.TButton', 
            background=MIDNIGHT_THEME["btn_browse_bg"], 
            foreground=MIDNIGHT_THEME["btn_browse_fg"])
        style.configure('Save.TButton', 
            background=MIDNIGHT_THEME["btn_browse_bg"], 
            foreground=MIDNIGHT_THEME["btn_browse_fg"])
        style.configure('Refresh.TButton', 
            background=MIDNIGHT_THEME["btn_refresh_bg"], 
            foreground=MIDNIGHT_THEME["btn_refresh_fg"])
        style.configure('Copy.TButton', 
            background=MIDNIGHT_THEME["btn_copy_bg"], 
            foreground=MIDNIGHT_THEME["btn_copy_fg"])
        style.configure('Treeview', 
            background=MIDNIGHT_THEME["bg_output"], 
            fieldbackground=MIDNIGHT_THEME["bg_output"], 
            foreground=MIDNIGHT_THEME["fg_text"],
            borderwidth=0,
            relief=tk.FLAT)
        style.map('Treeview', 
            background=[('selected', MIDNIGHT_THEME["btn_copy_bg"])],
            foreground=[('selected', MIDNIGHT_THEME["fg_text"])])
        style.configure('TScrollbar', 
            background=MIDNIGHT_THEME["bg_entry"], 
            troughcolor=MIDNIGHT_THEME["bg_main"], 
            bordercolor=MIDNIGHT_THEME["bg_main"],
            arrowcolor=MIDNIGHT_THEME["fg_label"],
            relief=tk.FLAT)
        style.map('TScrollbar', 
            background=[('active', MIDNIGHT_THEME["btn_copy_bg"])])
        style.configure('TPanedWindow', 
            background=MIDNIGHT_THEME["bg_main"])
        style.configure('TLabelframe', 
            background=MIDNIGHT_THEME["bg_main"], 
            foreground=MIDNIGHT_THEME["fg_label"],
            relief=tk.FLAT,
            borderwidth=0,
            font=("Segoe UI", 10, "bold"))
        style.configure('TLabelframe.Label', 
            background=MIDNIGHT_THEME["bg_main"], 
            foreground=MIDNIGHT_THEME["fg_label"])
        style.configure('TEntry', 
            fieldbackground=MIDNIGHT_THEME["bg_entry"], 
            foreground=MIDNIGHT_THEME["fg_entry"],
            insertcolor=MIDNIGHT_THEME["fg_text"], # Cursor color
            borderwidth=1,
            relief=tk.FLAT)
        style.configure('TNotebook', 
            background=MIDNIGHT_THEME["bg_main"],
            borderwidth=0,
            relief=tk.FLAT)
        style.configure('TNotebook.Tab', 
            background=MIDNIGHT_THEME["btn_refresh_bg"], 
            foreground=MIDNIGHT_THEME["fg_label"],
            font=("Segoe UI", 9, "bold"),
            padding=[10, 5],
            borderwidth=0,
            relief=tk.FLAT)
        style.map('TNotebook.Tab', 
            background=[('selected', MIDNIGHT_THEME["btn_copy_bg"])], 
            foreground=[('selected', MIDNIGHT_THEME["fg_text"])])
        style.configure('TFrame', background=MIDNIGHT_THEME["bg_main"])
        self.input_text_widget.configure_colors(
            bg=MIDNIGHT_THEME["bg_entry"], 
            fg=MIDNIGHT_THEME["fg_text"],
            ln_bg=MIDNIGHT_THEME["bg_main"], 
            ln_fg=MIDNIGHT_THEME["fg_label"],
            insert_fg=MIDNIGHT_THEME["fg_text"]
        )
        self.input_text.tag_configure("error", background=MIDNIGHT_THEME["diff_bg"])
        self.input_text_widget.line_numbers.tag_configure("error", 
            background=MIDNIGHT_THEME["diff_bg"], 
            foreground=MIDNIGHT_THEME["fg_text"])
        self.output_text.config(
            background=MIDNIGHT_THEME["bg_output"], 
            foreground=MIDNIGHT_THEME["fg_text"],
            insertbackground=MIDNIGHT_THEME["fg_text"]
        )
        self.tree_menu.config(
            bg=MIDNIGHT_THEME["btn_refresh_bg"],
            fg=MIDNIGHT_THEME["fg_text"],
            activebackground=MIDNIGHT_THEME["btn_copy_bg"],
            activeforeground=MIDNIGHT_THEME["fg_text"],
            relief=tk.FLAT,
            borderwidth=0
        )
        self.status_bar.config(
            background=MIDNIGHT_THEME["bg_main"],
            foreground=MIDNIGHT_THEME["fg_label"],
            relief=tk.FLAT
        )
        self.apply_text_tags()
    def create_widgets(self):
        toolbar = ttk.Frame(self.root, style='TFrame')
        toolbar.pack(fill=tk.X, padx=10, pady=(5, 0))
        ttk.Button(toolbar, text="Load File", command=self.load_file, style='Browse.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Save Fixed", command=self.save_file, style='Save.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Auto Repair", command=self.trigger_auto_repair, style='Refresh.TButton').pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Clear", command=self.clear_all, style='Refresh.TButton').pack(side=tk.LEFT, padx=2)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=20)
        search_entry.pack(side=tk.RIGHT, padx=2)
        search_entry.bind("<Return>", lambda e: self.search_tree())
        ttk.Button(toolbar, text="Search", command=self.search_tree, style='Copy.TButton').pack(side=tk.RIGHT, padx=2)
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        input_tab_frame = ttk.Frame(notebook, style='TFrame')
        notebook.add(input_tab_frame, text="  Input  ")
        input_frame = ttk.LabelFrame(input_tab_frame, text="Malformed JSON (Input)")
        input_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.input_text_widget = TextWithLineNumbers(
            input_frame, wrap=tk.NONE, font=self.text_font,
            borderwidth=0, relief=tk.FLAT
        )
        self.input_text_widget.pack(fill=tk.BOTH, expand=True)
        self.input_text = self.input_text_widget.text 
        input_scroll_x = ttk.Scrollbar(input_tab_frame, orient=tk.HORIZONTAL, command=self.input_text.xview)
        input_scroll_x.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=(0,5))
        self.input_text.config(xscrollcommand=input_scroll_x.set)
        output_tab_frame = ttk.Frame(notebook, style='TFrame')
        notebook.add(output_tab_frame, text="  Output & Tree  ")
        paned = ttk.PanedWindow(output_tab_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        output_pane_frame = ttk.Frame(paned, style='TFrame')
        paned.add(output_pane_frame, weight=3)
        output_frame = ttk.LabelFrame(output_pane_frame, text="Repaired JSON (Output)")
        output_frame.pack(fill=tk.BOTH, expand=True)
        self.output_text = tk.Text(output_frame, wrap=tk.NONE, font=self.text_font, state=tk.DISABLED,
                                   borderwidth=0, relief=tk.FLAT)
        self.output_text.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        output_scroll_y = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.output_text.yview)
        output_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.config(yscrollcommand=output_scroll_y.set)
        output_scroll_x = ttk.Scrollbar(output_pane_frame, orient=tk.HORIZONTAL, command=self.output_text.xview)
        output_scroll_x.pack(fill=tk.X, side=tk.BOTTOM)
        self.output_text.config(xscrollcommand=output_scroll_x.set)
        right_frame = ttk.LabelFrame(paned, text="JSON Structure")
        paned.add(right_frame, weight=2)
        self.tree = ttk.Treeview(right_frame, show="tree")
        self.tree.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        tree_scroll = ttk.Scrollbar(right_frame, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.config(yscrollcommand=tree_scroll.set)
        self.tree_menu = tk.Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="Copy JSON Path", command=self.tree_copy_path)
        self.tree_menu.add_command(label="Copy Value", command=self.tree_copy_value)
        self.tree_menu.add_command(label="Reveal in Editor", command=self.tree_reveal_in_editor)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Expand All", command=self.tree_expand_all)
        self.tree_menu.add_command(label="Collapse All", command=self.tree_collapse_all)
        self.tree.bind("<Button-3>", self.on_tree_context)  # Right-click
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.status = tk.StringVar(value="Ready")
        self.status_bar = ttk.Label(self.root, textvariable=self.status, anchor=tk.W)
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=(0, 5))
    def setup_bindings(self):
        self.input_text.bind("<KeyRelease>", self.on_input_change)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Control-plus>", self.increase_font)
        self.root.bind("<Control-equal>", self.increase_font) 
        self.root.bind("<Control-minus>", self.decrease_font)
        self.root.bind("<Control-MouseWheel>", self.zoom_font)
    def on_close(self):
        self.root.quit()
    def log(self, msg, duration=3000):
        self.status.set(msg)
        if duration > 0:
            self.root.after(duration, lambda: self.status.set("Ready"))
    def update_font_size(self):
        self.text_font.configure(size=self.font_size)
        self.input_text_widget.update_font(self.text_font)
        self.output_text.config(font=self.text_font)
    def increase_font(self, event=None):
        self.font_size = min(30, self.font_size + 1)
        self.update_font_size()
        return "break"
    def decrease_font(self, event=None):
        self.font_size = max(6, self.font_size - 1)
        self.update_font_size()
        return "break"
    def zoom_font(self, event):
        if event.delta > 0:
            self.increase_font()
        else:
            self.decrease_font()
        return "break"
    def _get_parse_error(self, s: str) -> Optional[json.JSONDecodeError]:
        """Tries to parse a string, returns the error if it fails."""
        try:
            json.loads(s)
            return None
        except json.JSONDecodeError as e:
            return e
        except Exception:
            return None 
    def _strip_json_comments(self, s: str) -> str:
        pattern = re.compile(r'("(?:\\.|[^"\\])*")|(//.*)|(/\*[\s\S]*?\*/)', re.DOTALL)
        return pattern.sub(lambda m: m.group(1) or "", s)
    def _normalize_single_quotes(self, s: str) -> str:
        def repl(m):
            if m.group(1): return m.group(1) 
            inner = m.group(2)[1:-1]
            inner = inner.replace('\\"', '"').replace("\\'", "'") 
            inner = inner.replace('"', '\\"')
            return f'"{inner}"'
        pattern = re.compile(r'("(?:\\.|[^"\\])*")|(\'(?:\\.|[^\'\\])*\')')
        return pattern.sub(repl, s)
    def _remove_trailing_commas(self, s: str) -> str:
        return re.sub(r',\s*([\]}])', r'\1', s)
    def _quote_unquoted_keys(self, s: str) -> str:
        return re.sub(r'(?<=[\{\,])\s*([a-zA-Z_][a-zA-Z0-9_\-]*)\s*(?=:)', r' "\1"', s)
    def _fix_keywords(self, s: str) -> str:
        """Converts Python None/True/False to JSON null/true/false."""
        s = re.sub(r'\bNone\b', 'null', s)
        s = re.sub(r'\bTrue\b', 'true', s)
        s = re.sub(r'\bFalse\b', 'false', s)
        return s
    def _fix_nan_inf(self, s: str) -> str:
        """Converts NaN/Infinity to null."""
        return re.sub(r'\b(NaN|Infinity|-Infinity)\b', 'null', s)
    def repair_pipeline(self, text: str) -> Tuple[Optional[str], List[str]]:
        report = []
        if not self._get_parse_error(text):
            return text, ["already valid"]
        steps = [
            (self._fix_keywords, "fixed Python keywords (None/True/False)"),
            (self._fix_nan_inf, "converted NaN/Infinity to null"),
            (self._strip_json_comments, "removed comments"),
            (self._normalize_single_quotes, "normalized single quotes"),
            (self._remove_trailing_commas, "removed trailing commas"),
            (self._quote_unquoted_keys, "quoted unquoted keys"),
        ]
        current = text
        for func, msg in steps:
            candidate = func(current)
            if not self._get_parse_error(candidate):
                report.append(msg)
                return candidate, report 
            elif candidate != current:
                report.append(msg)
                current = candidate 
        if not self._get_parse_error(current):
             return current, report
        stripped = current.strip()
        if not stripped.startswith(('{', '[')) and re.search(r"^\s*[a-zA-Z_]", stripped, re.M):
            wrapped = "{\n" + stripped + "\n}"
            if not self._get_parse_error(wrapped):
                report.append("wrapped in {}")
                return wrapped, report
        return None, []
    def auto_repair(self):
        self.input_text_widget.clear_highlight("error")
        raw = self.input_text.get("1.0", tk.END).strip()
        if not raw:
            return
        repaired, report = self.repair_pipeline(raw)
        if repaired:
            try:
                parsed = json.loads(repaired)
                pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
                self.output_text.config(state=tk.NORMAL)
                self.output_text.delete("1.0", tk.END)
                self.output_text.insert("1.0", pretty)
                self.output_text.config(state=tk.DISABLED)
                self.current_data = parsed
                self.populate_tree(parsed)
                self.log(f"Auto-repair success: {', '.join(report)}")
                self.apply_syntax_highlighting()
                return
            except Exception as e:
                self.log(f"Post-repair parse failed: {e}")
        self.log("Auto-repair failed. Checking for error...", duration=0)
        error = self._get_parse_error(raw) 
        if error:
            self.input_text_widget.highlight_line(error.lineno, "error")
            self.log(f"Auto-repair failed: {error.msg} (line {error.lineno}, col {error.colno})", duration=5000)
        else:
            self.log("Auto-repair failed. Could not parse input.")
    def trigger_auto_repair(self):
        self.auto_repair()
    def on_input_change(self, event=None):
        self.last_input_time = time.time() * 1000
        self.root.after(self.debounce_delay, self.process_input)
    def process_input(self):
        if (time.time() * 1000 - self.last_input_time) < self.debounce_delay:
            return
        self.auto_repair()
    def apply_syntax_highlighting(self):
        text_widget = self.output_text
        text_widget.config(state=tk.NORMAL)
        tags = ["key", "string", "number", "keyword"]
        for tag in tags:
            text_widget.tag_remove(tag, "1.0", tk.END)
        text = text_widget.get("1.0", tk.END)
        for match in re.finditer(r'"([^"\\]|\\.)*"\s*:', text):
            start = text_widget.index(f"1.0 + {match.start()} chars")
            end = text_widget.index(f"1.0 + {match.start() + len(match.group(1)) + 2} chars")
            text_widget.tag_add("key", start, end)
        for match in re.finditer(r':\s*"([^"\\]|\\.)*"', text):
            start = text_widget.index(f"1.0 + {match.start() + match.group().find('"')} chars")
            end = text_widget.index(f"1.0 + {match.end()} chars")
            text_widget.tag_add("string", start, end)
        for match in re.finditer(r':\s*(-?\d+\.?\d*([eE][-+]?\d+)?)', text):
            start = text_widget.index(f"1.0 + {match.start() + match.group().find(match.group(1))} chars")
            end = text_widget.index(f"1.0 + {match.end()} chars")
            text_widget.tag_add("number", start, end)
        for kw in ["true", "false", "null"]:
            for match in re.finditer(rf':\s*\b{kw}\b', text):
                start = text_widget.index(f"1.0 + {match.start() + match.group().find(kw)} chars")
                end = text_widget.index(f"1.0 + {match.end()} chars")
                text_widget.tag_add("keyword", start, end)
        text_widget.tag_config("key", foreground=MIDNIGHT_THEME["fg_entry"])
        text_widget.tag_config("string", foreground=MIDNIGHT_THEME["btn_refresh_fg"])
        text_widget.tag_config("number", foreground=MIDNIGHT_THEME["btn_browse_fg"])
        text_widget.tag_config("keyword", foreground=MIDNIGHT_THEME["fg_label"])
        text_widget.config(state=tk.DISABLED)
    def apply_text_tags(self):
        if self.current_data:
            self.apply_syntax_highlighting()
    def populate_tree(self, data, parent=""):
        self.tree.delete(*self.tree.get_children())
        def insert(node, value, key=""):
            if isinstance(value, dict):
                node_text = f"{key}: {{...}}" if key else "{...}"
                nid = self.tree.insert(node, "end", text=node_text, values=("object",))
                for k, v in value.items():
                    insert(nid, v, str(k))
            elif isinstance(value, list):
                node_text = f"{key}: [...]" if key else "[...]"
                nid = self.tree.insert(node, "end", text=node_text, values=("array",))
                for i, v in enumerate(value):
                    insert(nid, v, f"[{i}]")
            else:
                display_val = repr(value)
                if len(display_val) > 40:
                    display_val = display_val[:40] + "..."
                display = f"{key}: {display_val}" if key else display_val
                self.tree.insert(node, "end", text=display, values=("value",))
        insert(parent, data)
        for child in self.tree.get_children():
            self.tree.item(child, open=True)
    def get_tree_path(self, iid):
        path = []
        while iid:
            text = self.tree.item(iid, "text")
            key_part = text.split(":", 1)[0].strip()
            if key_part.startswith("[") and key_part.endswith("]"):
                path.append(key_part)
            elif "..." in key_part: 
                if key_part not in ("{...}", "[...]"):
                    path.append(f".{key_part.replace(': {...}', '').replace(': [...]', '')}")
            elif ":" in text: 
                 path.append(f".{key_part}")
            iid = self.tree.parent(iid)
        path.reverse()
        json_path = "".join(path).replace(".[", "[")
        if not json_path.startswith("["):
            json_path = "$" + json_path
        return json_path.replace("$.", "$.")
    def on_tree_context(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid)
            self.tree_menu.tk_popup(event.x_root, event.y_root)
    def tree_copy_path(self):
        sel = self.tree.selection()
        if sel:
            path = self.get_tree_path(sel[0])
            self.root.clipboard_clear()
            self.root.clipboard_append(path)
            self.log(f"Copied Path: {path}")
    def _get_value_from_path(self, jsonpath: str):
        """Safely get value using simple JSONPath (dot + bracket notation)."""
        if not self.current_data or not jsonpath:
            return None
        value = self.current_data
        path = jsonpath
        if path.startswith('$'):
            path = path[1:]
        path = path.lstrip('.')
        pattern = r'(?:\.([a-zA-Z_][a-zA-Z0-9_\-]*)|\["([^"]+)"\]|\[\'([^\']+)\'\]|\[(\d+)\])'
        if not path.startswith(('.', '[')):
             path = f".{path}"
        matches = re.finditer(pattern, path)
        try:
            temp_value = self.current_data
            for match in matches:
                key_part = match.group(1) or match.group(2) or match.group(3) or match.group(4)
                if key_part.isdigit():
                    temp_value = temp_value[int(key_part)]
                else:
                    temp_value = temp_value[key_part]
            if not match:
                 if path.isdigit():
                     temp_value = value[int(path)]
                 else:
                     temp_value = value[path]
            value = temp_value
        except (KeyError, IndexError, TypeError, ValueError):
            self.log(f"Could not resolve path: {jsonpath}")
            return None
        return value
    def tree_copy_value(self):
        sel = self.tree.selection()
        if sel:
            path = self.get_tree_path(sel[0])
            value = self._get_value_from_path(path)
            if value is not None:
                try:
                    value_str = json.dumps(value, indent=2, ensure_ascii=False)
                except:
                    value_str = str(value)
                self.root.clipboard_clear()
                self.root.clipboard_append(value_str)
                self.log(f"Copied Value")
    def _tree_recursive_open(self, item, open_state: bool):
        if self.tree.item(item, "values") in [("object",), ("array",)]:
            self.tree.item(item, open=open_state)
            for child in self.tree.get_children(item):
                self._tree_recursive_open(child, open_state)
    def tree_expand_all(self):
        for item in self.tree.get_children():
            self._tree_recursive_open(item, open_state=True)
    def tree_collapse_all(self):
        for item in self.tree.get_children():
            self._tree_recursive_open(item, open_state=False)
    def tree_reveal_in_editor(self):
        sel = self.tree.selection()
        if not sel:
            return
        path = self.get_tree_path(sel[0])
        self.highlight_in_output(path, flash=False)
    def on_tree_select(self, _):
        sel = self.tree.selection()
        if sel:
            path = self.get_tree_path(sel[0])
            self.highlight_in_output(path, flash=True)
    def highlight_in_output(self, jsonpath, flash=False):
        if not self.current_data:
            return
        try:
            value = self.current_data
            search_key = None
            parts = re.findall(r"\.([a-zA-Z0-9_]+)|\[(\d+)\]", jsonpath)
            for key, index in parts:
                if key:
                    search_key = key
                    value = value[key]
                elif index:
                    search_key = int(index)
                    value = value[int(index)]
            text_widget = self.output_text
            text_widget.tag_remove("flash", "1.0", tk.END) 
            search_term = ""
            end_len = 0
            if isinstance(search_key, str):
                search_term = f'"{search_key}":'
                end_len = len(search_term)
            elif isinstance(search_key, int):
                if isinstance(value, (dict, list)):
                    self.log("Cannot highlight complex objects in arrays yet.")
                    return 
                search_term = json.dumps(value, ensure_ascii=False)
                end_len = len(search_term)
            if not search_term:
                return
            start = text_widget.search(search_term, "1.0")
            if start:
                end = f"{start} + {end_len} chars"
                text_widget.see(start)
                if flash:
                    tag = "flash"
                    text_widget.tag_add(tag, start, end)
                    flash_bg = MIDNIGHT_THEME["btn_browse_fg"]
                    flash_fg = MIDNIGHT_THEME["bg_main"]
                    text_widget.tag_config(tag, background=flash_bg, foreground=flash_fg)
                    self.root.after(800, lambda: text_widget.tag_remove(tag, "1.0", tk.END))
                else:
                    text_widget.tag_add(tk.SEL, start, end)
                    text_widget.focus_set()
        except Exception as e:
            print(f"Highlight error: {e}")
            pass
    def search_tree(self):
        query = self.search_var.get().lower()
        if not query:
            return
        def recursive_search(item):
            if query in self.tree.item(item, "text").lower():
                return item
            self.tree.item(item, open=True) 
            for child in self.tree.get_children(item):
                found = recursive_search(child)
                if found:
                    return found
            return None
        found_item = None
        for item in self.tree.get_children():
            found_item = recursive_search(item)
            if found_item:
                self.tree.see(found_item)
                self.tree.selection_set(found_item)
                self.log(f"Found: {self.tree.item(found_item, 'text')}")
                break
        if not found_item:
            self.log("Search query not found.")
    def load_file(self):
        path = filedialog.askopenfilename(filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")])
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.input_text.delete("1.0", tk.END)
                self.input_text.insert("1.0", content)
                self.log(f"Loaded: {os.path.basename(path)}")
                self.auto_repair()
            except Exception as e:
                messagebox.showerror("Error Loading File", f"Could not read file:\n{e}")
                self.log("File load error")
    def save_file(self):
        if not self.current_data:
            messagebox.showwarning("No Data", "No valid JSON to save.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON Files", "*.json")])
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(self.current_data, f, indent=2, ensure_ascii=False)
                self.log(f"Saved: {os.path.basename(path)}")
            except Exception as e:
                messagebox.showerror("Error Saving File", f"Could not save file:\n{e}")
                self.log("File save error")
    def clear_all(self):
        self.input_text.delete("1.0", tk.END)
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state=tk.DISABLED)
        self.tree.delete(*self.tree.get_children())
        self.current_data = None
        self.input_text_widget.clear_highlight("error")
        self.log("Cleared")
if __name__ == "__main__":
    root = tk.Tk()
    app = JSONRepairApp(root)
    root.mainloop()
