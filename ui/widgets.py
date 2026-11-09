"""ui/widgets.py - reusable widgets: autosuggest entry and tag chips."""
import tkinter as tk
from tkinter import ttk

_NAV_KEYS = {"Up", "Down", "Return", "KP_Enter", "Escape", "Tab", "ISO_Left_Tab", "Left", "Right",
             "Home", "End", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"}


class AutoSuggestEntry(ttk.Frame):
    """Entry that shows a list of suggestions while typing.

    suggest_fn(text) -> list of strings. The typed text always wins on Enter; use the
    Down arrow or the mouse to pick a suggestion.
    on_select(text): a suggestion was picked.   on_commit(text): Enter pressed on typed text.
    """

    def __init__(self, parent, suggest_fn, on_select=None, on_commit=None, width=30,
                 max_rows=8, show_button=False):
        super().__init__(parent)
        self.suggest_fn = suggest_fn
        self.on_select = on_select
        self.on_commit = on_commit
        self.max_rows = max_rows
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, width=width)
        self.entry.pack(side="left", fill="x", expand=True)
        if show_button:
            ttk.Button(self, text="\u25be", width=2, takefocus=0,
                       command=self.show_all).pack(side="left", padx=(2, 0))
        self._list = None
        self._items = []
        e = self.entry
        e.bind("<KeyRelease>", self._on_key_release)
        e.bind("<Down>", self._on_down)
        e.bind("<Up>", self._on_up)
        e.bind("<Return>", self._on_return)
        e.bind("<KP_Enter>", self._on_return)
        e.bind("<Escape>", self._on_escape)
        e.bind("<FocusOut>", lambda ev: self.hide(), add="+")
        e.bind("<Tab>", lambda ev: self.hide(), add="+")

    # --- public
    def get(self):
        return self.var.get()

    def set(self, text):
        self.var.set(text)
        self.hide()

    def focus_entry(self):
        self.entry.focus_set()

    def visible(self):
        return self._list is not None and self._list.winfo_ismapped()

    def show_all(self):
        self.entry.focus_set()
        self.show_suggestions(query="")

    def hide(self):
        if self._list is not None:
            self._list.place_forget()

    def show_suggestions(self, query=None):
        text = self.var.get() if query is None else query
        items = list(self.suggest_fn(text))
        if not items:
            self.hide()
            return
        self._items = items
        top = self.winfo_toplevel()
        if self._list is None:
            self._list = tk.Listbox(top, activestyle="none", exportselection=False, takefocus=0,
                                    relief="solid", borderwidth=1)
            self._list.bind("<Button-1>", self._on_click)
        lb = self._list
        lb.delete(0, "end")
        for it in items:
            lb.insert("end", it)
        lb.configure(height=min(len(items), self.max_rows))
        lb.update_idletasks()
        x = self.entry.winfo_rootx() - top.winfo_rootx()
        y = self.entry.winfo_rooty() - top.winfo_rooty() + self.entry.winfo_height()
        h = lb.winfo_reqheight()
        if y + h > top.winfo_height():
            y = max(0, self.entry.winfo_rooty() - top.winfo_rooty() - h)
        lb.place(x=x, y=y, width=self.entry.winfo_width())
        lb.lift()

    # --- events
    def _on_key_release(self, ev):
        if ev.keysym in _NAV_KEYS:
            return
        self.show_suggestions()

    def _move(self, step):
        lb = self._list
        cur = lb.curselection()
        idx = (cur[0] + step) if cur else (0 if step > 0 else -1)
        lb.selection_clear(0, "end")
        if 0 <= idx < len(self._items):
            lb.selection_set(idx)
            lb.activate(idx)
            lb.see(idx)

    def _on_down(self, ev):
        if self.visible():
            self._move(1)
        else:
            self.show_suggestions()
        return "break"

    def _on_up(self, ev):
        if self.visible():
            self._move(-1)
            return "break"

    def _on_return(self, ev):
        if self.visible() and self._list.curselection():
            self._pick(self._list.curselection()[0])
        else:
            self.hide()
            if self.on_commit:
                self.on_commit(self.var.get())
        return "break"

    def _on_escape(self, ev):
        if self.visible():
            self.hide()
            return "break"

    def _on_click(self, ev):
        idx = self._list.nearest(ev.y)
        if 0 <= idx < len(self._items):
            self._pick(idx)
        return "break"          # keep keyboard focus in the entry

    def _pick(self, idx):
        text = self._items[idx]
        self.hide()
        self.var.set(text)
        self.entry.icursor("end")
        if self.on_select:
            self.on_select(text)


class FlowFrame(tk.Frame):
    """Lays child widgets out left-to-right and wraps them onto new rows."""

    def __init__(self, parent, gap=4, **kw):
        super().__init__(parent, **kw)
        self.gap = gap
        self.items = []
        self._width = 0
        self.bind("<Configure>", self._on_configure)

    def add(self, widget):
        self.items.append(widget)
        self.reflow()

    def remove(self, widget):
        if widget in self.items:
            self.items.remove(widget)
        widget.destroy()
        self.reflow()

    def clear(self):
        for w in self.items:
            w.destroy()
        self.items = []
        self.reflow()

    def _on_configure(self, ev):
        if ev.width != self._width:
            self._width = ev.width
            self.reflow()

    def reflow(self):
        width = self.winfo_width()
        if width <= 1:
            width = 300
        x = y = row_h = 0
        for w in self.items:
            w.update_idletasks()
            rw, rh = w.winfo_reqwidth(), w.winfo_reqheight()
            if x > 0 and x + rw > width:
                x, y, row_h = 0, y + row_h + self.gap, 0
            w.place(x=x, y=y)
            x += rw + self.gap
            row_h = max(row_h, rh)
        self.configure(height=max(y + row_h, 1))


class TagInput(ttk.Frame):
    """Tag chips with an autosuggest entry. suggest_fn(text, exclude=tuple) -> list of names."""

    BG, EDGE = "#dbe7ff", "#9db8f0"

    def __init__(self, parent, suggest_fn, width=40):
        super().__init__(parent)
        self.tags = []
        self._chips = {}
        self.chips = FlowFrame(self)
        self.chips.pack(fill="x")
        self.entry = AutoSuggestEntry(
            self, lambda text: suggest_fn(text, exclude=tuple(self.tags)),
            on_select=self.add_tag, on_commit=self.add_tag, width=width)
        self.entry.pack(fill="x", pady=(3, 0))
        self.entry.entry.bind("<BackSpace>", self._on_backspace, add="+")
        self.entry.entry.bind("<KeyRelease>", self._on_key_release, add="+")

    def get_tags(self):
        return list(self.tags)

    def set_tags(self, tags):
        self.tags = []
        self._chips = {}
        self.chips.clear()
        for t in tags:
            self.add_tag(t)

    def add_tag(self, text):
        for part in str(text).split(","):
            t = " ".join(part.split())
            if not t or any(t.casefold() == x.casefold() for x in self.tags):
                continue
            self.tags.append(t)
            chip = self._make_chip(t)
            self._chips[t] = chip
            self.chips.add(chip)
        self.entry.var.set("")
        self.entry.hide()

    def remove_tag(self, tag):
        if tag in self.tags:
            self.tags.remove(tag)
            self.chips.remove(self._chips.pop(tag))

    def _make_chip(self, tag):
        chip = tk.Frame(self.chips, bg=self.BG, highlightthickness=1, highlightbackground=self.EDGE)
        tk.Label(chip, text=tag, bg=self.BG, padx=5).pack(side="left")
        x = tk.Label(chip, text="\u00d7", bg=self.BG, cursor="hand2", padx=4)
        x.pack(side="left")
        x.bind("<Button-1>", lambda ev, t=tag: self.remove_tag(t))
        return chip

    def _on_backspace(self, ev):
        if not self.entry.var.get() and self.tags:
            self.remove_tag(self.tags[-1])

    def _on_key_release(self, ev):
        if "," in self.entry.var.get():
            self.add_tag(self.entry.var.get())
