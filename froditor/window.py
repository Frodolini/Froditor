"""Hovudvindauget i Froditor."""

import os
import time

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from . import fileio  # noqa: E402
from .settings import DEFAULT_FONT, Settings  # noqa: E402

UNTITLED = "Utan namn"
# (namn i fillista, filending, mønster)
FILE_TYPES = [
    ("Tekstfiler (*.txt)", ".txt", ["*.txt", "*.TXT"]),
    ("PowerShell-skript (*.ps1)", ".ps1", ["*.ps1", "*.PS1"]),
]
DEFAULT_SUFFIX = ".txt"
MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 72
MAX_HIGHLIGHTS = 5000

_window_counter = 0


def _home_short(path: str) -> str:
    home = os.path.expanduser("~")
    if path == home or path.startswith(home + os.sep):
        return "~" + path[len(home):]
    return path


class FroditorWindow(Gtk.ApplicationWindow):
    def __init__(self, application=None, settings: Settings | None = None):
        super().__init__(application=application)
        global _window_counter
        _window_counter += 1

        self.settings = settings or Settings()
        self.path: str | None = None
        self.document = fileio.Document("")
        self._close_confirmed = False
        self._status_timeout = 0
        self._highlight_timeout = 0
        self._css_provider: Gtk.CssProvider | None = None
        self._dialog_refs = []  # held på native dialogar så dei ikkje blir rydda bort

        self.set_default_size(self.settings.width, self.settings.height)
        self._build_ui(f"froditor-text-{_window_counter}")
        self._setup_actions()
        self._apply_font()
        self._apply_wrap()
        self._update_title()
        self._update_cursor_label()
        self._update_format_label()
        self.connect("close-request", self._on_close_request)
        self.textview.grab_focus()

    # ------------------------------------------------------------------ UI

    def _build_ui(self, text_name: str):
        header = Gtk.HeaderBar()
        self.title_label = Gtk.Label(ellipsize=Pango.EllipsizeMode.END)
        self.title_label.add_css_class("title")
        self.subtitle_label = Gtk.Label(ellipsize=Pango.EllipsizeMode.START)
        self.subtitle_label.add_css_class("subtitle")
        self.subtitle_label.add_css_class("dim-label")
        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        title_box.append(self.title_label)
        title_box.append(self.subtitle_label)
        header.set_title_widget(title_box)

        header.pack_start(Gtk.Button(label="Opne", action_name="win.open",
                                     tooltip_text="Opne fil (Ctrl+O)"))
        header.pack_start(Gtk.Button(icon_name="document-new-symbolic", action_name="win.new",
                                     tooltip_text="Nytt dokument (Ctrl+N)"))
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=self._build_menu(),
                                     tooltip_text="Meny")
        menu_button.set_primary(True)
        header.pack_end(menu_button)
        save_button = Gtk.Button(label="Lagre", action_name="win.save", tooltip_text="Lagre (Ctrl+S)")
        header.pack_end(save_button)
        self.set_titlebar(header)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root.append(self._build_search_bar())

        self.buffer = Gtk.TextBuffer(enable_undo=True)
        self.search_tag = self.buffer.create_tag("search-match", background="#f8e45c",
                                                 foreground="#000000")
        self.textview = Gtk.TextView(buffer=self.buffer, left_margin=14, right_margin=14,
                                     top_margin=10, bottom_margin=10, hexpand=True, vexpand=True)
        self.textview.set_name(text_name)
        scroller = Gtk.ScrolledWindow(child=self.textview, hexpand=True, vexpand=True)
        root.append(scroller)

        root.append(Gtk.Separator())
        status = Gtk.Box(spacing=18, margin_start=12, margin_end=12, margin_top=4, margin_bottom=4)
        self.status_label = Gtk.Label(xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
        self.cursor_label = Gtk.Label(xalign=1)
        self.format_label = Gtk.Label(xalign=1)
        for label in (self.status_label, self.cursor_label, self.format_label):
            label.add_css_class("dim-label")
            status.append(label)
        root.append(status)
        self.set_child(root)

        self.buffer.connect("modified-changed", lambda *_: self._update_title())
        self.buffer.connect("notify::cursor-position", lambda *_: self._update_cursor_label())
        self.buffer.connect("changed", lambda *_: self._schedule_highlight())

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self._on_key_pressed)
        self.add_controller(keys)

    def _build_menu(self) -> Gio.Menu:
        menu = Gio.Menu()
        sections = [
            [("Nytt vindauge", "app.new-window"), ("Lagre som …", "win.save-as")],
            [("Søk …", "win.find"), ("Søk og erstatt …", "win.replace")],
            [("Linjebryting", "win.wrap"), ("Skrifttype …", "win.font")],
            [("Større tekst", "win.zoom-in"), ("Mindre tekst", "win.zoom-out"),
             ("Vanleg tekststorleik", "win.zoom-reset")],
            [("Om Froditor", "app.about"), ("Avslutt", "app.quit")],
        ]
        for items in sections:
            section = Gio.Menu()
            for label, action in items:
                section.append(label, action)
            menu.append_section(None, section)
        return menu

    def _build_search_bar(self) -> Gtk.Widget:
        grid = Gtk.Grid(column_spacing=6, row_spacing=6, margin_start=12, margin_end=12,
                        margin_top=8, margin_bottom=8)

        self.find_entry = Gtk.Entry(placeholder_text="Finn …", hexpand=True,
                                    primary_icon_name="edit-find-symbolic")
        self.find_entry.connect("changed", self._on_find_changed)
        self.find_entry.connect("activate", lambda *_: self.find(forward=True))
        prev_button = Gtk.Button(icon_name="go-up-symbolic", tooltip_text="Førre treff (Shift+F3)")
        prev_button.connect("clicked", lambda *_: self.find(forward=False))
        next_button = Gtk.Button(icon_name="go-down-symbolic", tooltip_text="Neste treff (F3)")
        next_button.connect("clicked", lambda *_: self.find(forward=True))
        self.case_check = Gtk.CheckButton(label="Skil store/små bokstavar")
        self.case_check.connect("toggled", self._on_find_changed)
        self.match_label = Gtk.Label(width_chars=10, xalign=0)
        self.match_label.add_css_class("dim-label")
        close_button = Gtk.Button(icon_name="window-close-symbolic", tooltip_text="Lukk (Esc)")
        close_button.add_css_class("flat")
        close_button.connect("clicked", lambda *_: self.hide_search())

        grid.attach(self.find_entry, 0, 0, 1, 1)
        grid.attach(prev_button, 1, 0, 1, 1)
        grid.attach(next_button, 2, 0, 1, 1)
        grid.attach(self.case_check, 3, 0, 1, 1)
        grid.attach(self.match_label, 4, 0, 1, 1)
        grid.attach(close_button, 5, 0, 1, 1)

        self.replace_entry = Gtk.Entry(placeholder_text="Erstatt med …", hexpand=True,
                                       primary_icon_name="edit-find-replace-symbolic")
        self.replace_entry.connect("activate", lambda *_: self.replace_one())
        self.replace_button = Gtk.Button(label="Erstatt")
        self.replace_button.connect("clicked", lambda *_: self.replace_one())
        self.replace_all_button = Gtk.Button(label="Erstatt alle")
        self.replace_all_button.connect("clicked", lambda *_: self.replace_all())
        grid.attach(self.replace_entry, 0, 1, 1, 1)
        grid.attach(self.replace_button, 1, 1, 2, 1)
        grid.attach(self.replace_all_button, 3, 1, 1, 1)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(grid)
        box.append(Gtk.Separator())
        self.search_revealer = Gtk.Revealer(child=box, reveal_child=False)
        return self.search_revealer

    # -------------------------------------------------------------- actions

    def _setup_actions(self):
        simple = {
            "new": self.new_document,
            "open": self.open_dialog,
            "save": self.save,
            "save-as": self.save_as,
            "find": lambda: self.show_search(replace=False),
            "replace": lambda: self.show_search(replace=True),
            "find-next": lambda: self._find_from_shortcut(True),
            "find-prev": lambda: self._find_from_shortcut(False),
            "font": self.choose_font,
            "zoom-in": lambda: self.zoom(+1),
            "zoom-out": lambda: self.zoom(-1),
            "zoom-reset": lambda: self.zoom(0),
            "close": self.close,
        }
        for name, callback in simple.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, cb=callback: cb())
            self.add_action(action)

        wrap = Gio.SimpleAction.new_stateful("wrap", None, GLib.Variant.new_boolean(self.settings.wrap))
        wrap.connect("change-state", self._on_wrap_changed)
        self.add_action(wrap)

    def _on_key_pressed(self, _controller, keyval, _keycode, _state):
        if keyval == Gdk.KEY_Escape and self.search_revealer.get_reveal_child():
            self.hide_search()
            return True
        return False

    # ------------------------------------------------------- dokument/filer

    def is_pristine(self) -> bool:
        """Tomt, ulagra og urørt vindauge som kan gjenbrukast."""
        return self.path is None and not self.buffer.get_modified() and self.buffer.get_char_count() == 0

    def get_text(self) -> str:
        start, end = self.buffer.get_bounds()
        return self.buffer.get_text(start, end, True)

    def _set_text(self, text: str):
        self.buffer.begin_irreversible_action()
        self.buffer.set_text(text)
        self.buffer.end_irreversible_action()
        self.buffer.place_cursor(self.buffer.get_start_iter())
        self.buffer.set_modified(False)
        self.textview.scroll_to_mark(self.buffer.get_insert(), 0.0, False, 0.0, 0.0)

    def new_document(self):
        def reset():
            self.path = None
            self.document = fileio.Document("")
            self._set_text("")
            self._update_title()
            self._update_format_label()
            self.set_status("")
        self.confirm_discard(reset)

    def open_dialog(self):
        self.confirm_discard(lambda: self._choose_file(save=False, callback=self.load_file))

    def load_file(self, file):
        path = file.get_path() if isinstance(file, Gio.File) else os.fspath(file)
        if not path:
            self.show_error("Kan ikkje opne fila", "Froditor kan berre opne filer som ligg på denne maskina.")
            return False
        path = os.path.abspath(path)
        name = os.path.basename(path)
        try:
            document = fileio.read_text(path)
        except FileNotFoundError:
            document = None
        except IsADirectoryError:
            self.show_error("Kan ikkje opne mappe", f"«{name}» er ei mappe, ikkje ei fil.")
            return False
        except fileio.BinaryFileError:
            self.show_error("Ikkje ei tekstfil",
                            f"«{name}» ser ut til å vere ei binærfil (t.d. bilete eller program), "
                            "og kan ikkje opnast i Froditor.")
            return False
        except OSError as error:
            self.show_error("Kunne ikkje opne fila", f"«{name}»: {error.strerror or error}")
            return False

        self.path = path
        if document is None:
            self.document = fileio.Document("")
            self._set_text("")
            self.set_status("Ny fil – blir oppretta når du lagrar")
        else:
            self.document = document
            self._set_text(document.text)
            if document.converted:
                encoding = fileio.ENCODING_NAMES.get(document.encoding, document.encoding)
                self.set_status(f"Fila er i {encoding} og blir lagra som UTF-8", timeout=8)
            else:
                self.set_status("")
            self._add_recent(path)
        self._update_title()
        self._update_format_label()
        return True

    def save(self, callback=None):
        """Lagrar. callback(ok) blir kalla når lagringa er ferdig eller avbroten."""
        if self.path is None:
            self.save_as(callback)
            return
        ok = self._write(self.path)
        if callback:
            callback(ok)

    def save_as(self, callback=None):
        def chosen(file, suffix=DEFAULT_SUFFIX):
            if file is None:
                if callback:
                    callback(False)
                return
            path = file.get_path()
            if not path:
                self.show_error("Kan ikkje lagre her", "Vel ei mappe på denne maskina.")
                if callback:
                    callback(False)
                return
            # Utan filending: bruk den filtypen som er vald i lista.
            if not os.path.splitext(os.path.basename(path))[1]:
                path += suffix
                if os.path.exists(path):
                    def answer(index):
                        ok = index == 1 and self._write(path)
                        if callback:
                            callback(ok)
                    self.ask(f"«{os.path.basename(path)}» finst allereie",
                             "Vil du skrive over fila?",
                             [("Avbryt", None), ("Skriv over", "destructive-action")], answer)
                    return
            ok = self._write(path)
            if callback:
                callback(ok)
        self._choose_file(save=True, callback=chosen)

    def _save_encoding_for(self, path: str) -> str:
        encoding = self.document.save_encoding
        # Windows PowerShell 5.1 treng BOM for å lese æ, ø og å rett i UTF-8-skript.
        if path.lower().endswith(".ps1") and (self.document.converted or not os.path.exists(path)):
            encoding = fileio.UTF8_BOM
        return encoding

    def _write(self, path: str) -> bool:
        encoding = self._save_encoding_for(path)
        try:
            fileio.write_text(path, self.get_text(), encoding, self.document.newline)
        except OSError as error:
            self.show_error("Kunne ikkje lagre", f"«{os.path.basename(path)}»: {error.strerror or error}")
            return False
        converted = self.document.converted
        self.document.encoding = encoding
        self.path = os.path.abspath(path)
        self.buffer.set_modified(False)
        self._update_title()
        self._update_format_label()
        self._add_recent(self.path)
        message = f"Lagra kl. {time.strftime('%H:%M')}"
        if converted:
            message += " (som UTF-8)"
        self.set_status(message)
        return True

    def _add_recent(self, path: str):
        try:
            Gtk.RecentManager.get_default().add_item(Gio.File.new_for_path(path).get_uri())
        except Exception:  # noqa: BLE001 – «nyleg brukte» er berre ein bonus
            pass

    def confirm_discard(self, proceed):
        """Køyrer proceed() om det er trygt, elles spør vi om å lagre først."""
        if not self.buffer.get_modified():
            proceed()
            return

        def answer(index):
            if index == 1:
                proceed()
            elif index == 2:
                self.save(lambda ok: ok and proceed())

        name = os.path.basename(self.path) if self.path else UNTITLED
        self.ask(f"Vil du lagre endringane i «{name}»?",
                 "Endringar som ikkje er lagra, går tapte.",
                 [("Avbryt", None), ("Ikkje lagre", "destructive-action"), ("Lagre", "suggested-action")],
                 answer)

    def _on_close_request(self, _window):
        if self._close_confirmed or not self.buffer.get_modified():
            self._remember_size()
            return False

        def really_close():
            self._close_confirmed = True
            self.close()
        self.confirm_discard(really_close)
        return True

    def _remember_size(self):
        if not self.is_maximized() and self.get_width() > 0:
            self.settings.width = self.get_width()
            self.settings.height = self.get_height()
            self.settings.save()

    # ---------------------------------------------------------- fildialogar

    def _filters(self):
        """Returnerer [(filter, filending)], og «Alle filer» sist med filending None."""
        result = []
        for name, suffix, patterns in FILE_TYPES:
            file_filter = Gtk.FileFilter(name=name)
            for pattern in patterns:
                file_filter.add_pattern(pattern)
            result.append((file_filter, suffix))
        everything = Gtk.FileFilter(name="Alle filer")
        everything.add_pattern("*")
        result.append((everything, None))
        return result

    def _current_suffix(self) -> str:
        if self.path:
            suffix = os.path.splitext(self.path)[1].lower()
            if any(suffix == known for _n, known, _p in FILE_TYPES):
                return suffix
        return DEFAULT_SUFFIX

    def _choose_file(self, save: bool, callback):
        filters = self._filters()
        current = self._current_suffix()
        default_filter = next(f for f, suffix in filters if suffix == current)
        folder = os.path.dirname(self.path) if self.path else None

        if not save and hasattr(Gtk, "FileDialog"):  # GTK 4.10 og nyare
            dialog = Gtk.FileDialog(title="Opne fil", modal=True)
            store = Gio.ListStore.new(Gtk.FileFilter)
            for file_filter, _suffix in filters:
                store.append(file_filter)
            dialog.set_filters(store)
            dialog.set_default_filter(default_filter)
            if folder:
                dialog.set_initial_folder(Gio.File.new_for_path(folder))

            def finished(dlg, result):
                try:
                    file = dlg.open_finish(result)
                except GLib.Error:
                    return  # avbrote
                callback(file)
            dialog.open(self, None, finished)
            return

        # Lagring brukar FileChooserNative, fordi berre den fortel kva filtype som vart vald.
        action = Gtk.FileChooserAction.SAVE if save else Gtk.FileChooserAction.OPEN
        native = Gtk.FileChooserNative.new("Lagre som" if save else "Opne fil", self, action,
                                           "_Lagre" if save else "_Opne", "_Avbryt")
        for file_filter, _suffix in filters:
            native.add_filter(file_filter)
        native.set_filter(default_filter)
        if folder:
            native.set_current_folder(Gio.File.new_for_path(folder))
        if save:
            # Nytt dokument får namn utan filending; ho kjem frå filtypen som blir vald.
            native.set_current_name(os.path.basename(self.path) if self.path else UNTITLED)

        def response(dlg, response_id):
            file = dlg.get_file() if response_id == Gtk.ResponseType.ACCEPT else None
            chosen = dlg.get_filter()
            suffix = next((s for f, s in filters if f == chosen and s), DEFAULT_SUFFIX)
            self._dialog_refs.remove(dlg)
            if save:
                callback(file, suffix)
            elif file is not None:
                callback(file)
        native.connect("response", response)
        self._dialog_refs.append(native)
        native.show()

    # ------------------------------------------------------------ dialogar

    def ask(self, heading: str, body: str, buttons, on_answer):
        """Enkel modal dialog. buttons = [(tekst, css-klasse|None), ...].

        on_answer(indeks) blir kalla med indeksen til knappen. Esc/lukk = 0.
        """
        dialog = Gtk.Window(transient_for=self, modal=True, title="Froditor", resizable=False)
        answered = False

        def respond(index):
            nonlocal answered
            if answered:
                return
            answered = True
            dialog.destroy()
            on_answer(index)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin_start=24,
                      margin_end=24, margin_top=20, margin_bottom=20)
        heading_label = Gtk.Label(xalign=0, wrap=True, max_width_chars=48)
        heading_label.set_markup(f"<b>{GLib.markup_escape_text(heading)}</b>")
        box.append(heading_label)
        if body:
            box.append(Gtk.Label(label=body, xalign=0, wrap=True, max_width_chars=48))
        button_box = Gtk.Box(spacing=8, halign=Gtk.Align.END, margin_top=8)
        last = None
        for index, (label, css) in enumerate(buttons):
            button = Gtk.Button(label=label)
            if css:
                button.add_css_class(css)
            button.connect("clicked", lambda _b, i=index: respond(i))
            button_box.append(button)
            last = button
        box.append(button_box)
        dialog.set_child(box)
        dialog.set_default_widget(last)

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed",
                     lambda _c, keyval, *_: keyval == Gdk.KEY_Escape and (respond(0) or True))
        dialog.add_controller(keys)
        dialog.connect("close-request", lambda *_: respond(0) or True)
        dialog.present()
        if last is not None:
            last.grab_focus()
        return dialog

    def show_error(self, heading: str, body: str):
        self.ask(heading, body, [("OK", "suggested-action")], lambda _i: None)

    # ----------------------------------------------------------- statuslinje

    def _update_title(self):
        name = os.path.basename(self.path) if self.path else UNTITLED
        star = "*" if self.buffer.get_modified() else ""
        self.title_label.set_text(f"{star}{name}")
        self.set_title(f"{star}{name} – Froditor")
        folder = _home_short(os.path.dirname(self.path)) if self.path else ""
        self.subtitle_label.set_text(folder)
        self.subtitle_label.set_visible(bool(folder))

    def _update_cursor_label(self):
        it = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        self.cursor_label.set_text(f"Linje {it.get_line() + 1}, kolonne {it.get_line_offset() + 1}")

    def _update_format_label(self):
        encoding = fileio.ENCODING_NAMES.get(self.document.encoding, self.document.encoding)
        newline = fileio.NEWLINE_NAMES.get(self.document.newline, "")
        self.format_label.set_text(f"{encoding} · {newline}")

    def set_status(self, message: str, timeout: int = 5):
        self.status_label.set_text(message)
        if self._status_timeout:
            GLib.source_remove(self._status_timeout)
            self._status_timeout = 0
        if message and timeout:
            def clear():
                self._status_timeout = 0
                self.status_label.set_text("")
                return GLib.SOURCE_REMOVE
            self._status_timeout = GLib.timeout_add_seconds(timeout, clear)

    # ------------------------------------------------------- søk og erstatt

    def show_search(self, replace: bool = False):
        for widget in (self.replace_entry, self.replace_button, self.replace_all_button):
            widget.set_visible(replace)
        bounds = self.buffer.get_selection_bounds()
        if bounds:
            selected = self.buffer.get_text(bounds[0], bounds[1], False)
            if selected and "\n" not in selected:
                self.find_entry.set_text(selected)
        self.search_revealer.set_reveal_child(True)
        self.find_entry.grab_focus()
        self._highlight_matches()

    def hide_search(self):
        self.search_revealer.set_reveal_child(False)
        start, end = self.buffer.get_bounds()
        self.buffer.remove_tag(self.search_tag, start, end)
        self.find_entry.remove_css_class("error")
        self.textview.grab_focus()

    def _search_flags(self):
        flags = Gtk.TextSearchFlags.TEXT_ONLY
        if not self.case_check.get_active():
            flags |= Gtk.TextSearchFlags.CASE_INSENSITIVE
        return flags

    def _find_from_shortcut(self, forward: bool):
        if not self.find_entry.get_text():
            self.show_search()
            return
        self.find(forward)

    def find(self, forward: bool = True, from_selection_start: bool = False) -> bool:
        needle = self.find_entry.get_text()
        if not needle:
            return False
        flags = self._search_flags()
        bounds = self.buffer.get_selection_bounds()
        insert = self.buffer.get_iter_at_mark(self.buffer.get_insert())
        if forward:
            start = bounds[0] if (bounds and from_selection_start) else (bounds[1] if bounds else insert)
            match = start.forward_search(needle, flags, None)
            if match is None:
                match = self.buffer.get_start_iter().forward_search(needle, flags, None)
        else:
            start = bounds[0] if bounds else insert
            match = start.backward_search(needle, flags, None)
            if match is None:
                match = self.buffer.get_end_iter().backward_search(needle, flags, None)

        if match is None:
            self.find_entry.add_css_class("error")
            return False
        self.find_entry.remove_css_class("error")
        self.buffer.select_range(match[0], match[1])
        self.textview.scroll_to_mark(self.buffer.get_insert(), 0.15, False, 0.0, 0.0)
        return True

    def _selection_matches(self) -> bool:
        bounds = self.buffer.get_selection_bounds()
        needle = self.find_entry.get_text()
        if not bounds or not needle:
            return False
        selected = self.buffer.get_text(bounds[0], bounds[1], False)
        if self.case_check.get_active():
            return selected == needle
        return selected.casefold() == needle.casefold()

    def replace_one(self) -> bool:
        if not self._selection_matches():
            return self.find(forward=True)
        start, end = self.buffer.get_selection_bounds()
        self.buffer.begin_user_action()
        self.buffer.delete(start, end)
        self.buffer.insert(start, self.replace_entry.get_text())
        self.buffer.end_user_action()
        self.buffer.place_cursor(start)
        self.find(forward=True)
        return True

    def replace_all(self) -> int:
        needle = self.find_entry.get_text()
        if not needle:
            return 0
        replacement = self.replace_entry.get_text()
        flags = self._search_flags()
        count = 0
        it = self.buffer.get_start_iter()
        self.buffer.begin_user_action()
        while True:
            match = it.forward_search(needle, flags, None)
            if match is None:
                break
            start, end = match
            self.buffer.delete(start, end)
            self.buffer.insert(start, replacement)  # start peikar no etter den nye teksten
            it = start
            count += 1
        self.buffer.end_user_action()
        self.set_status(f"Erstatta {count} treff" if count else f"Fann ikkje «{needle}»")
        return count

    def _on_find_changed(self, *_):
        self._highlight_matches()
        if self.find_entry.get_text():
            self.find(forward=True, from_selection_start=True)
        else:
            self.find_entry.remove_css_class("error")

    def _schedule_highlight(self):
        if not self.search_revealer.get_reveal_child() or self._highlight_timeout:
            return

        def run():
            self._highlight_timeout = 0
            self._highlight_matches()
            return GLib.SOURCE_REMOVE
        self._highlight_timeout = GLib.timeout_add(150, run)

    def _highlight_matches(self) -> int:
        start, end = self.buffer.get_bounds()
        self.buffer.remove_tag(self.search_tag, start, end)
        needle = self.find_entry.get_text()
        if not needle:
            self.match_label.set_text("")
            return 0
        flags = self._search_flags()
        count = 0
        it = start
        while count < MAX_HIGHLIGHTS:
            match = it.forward_search(needle, flags, None)
            if match is None:
                break
            self.buffer.apply_tag(self.search_tag, match[0], match[1])
            it = match[1]
            count += 1
        if count == 0:
            self.match_label.set_text("Ingen treff")
        elif count >= MAX_HIGHLIGHTS:
            self.match_label.set_text(f"{MAX_HIGHLIGHTS}+ treff")
        else:
            self.match_label.set_text(f"{count} treff")
        self.find_entry.remove_css_class("error") if count else self.find_entry.add_css_class("error")
        return count

    # ------------------------------------------------- skrift og linjebryting

    def _on_wrap_changed(self, action, value):
        action.set_state(value)
        self.settings.wrap = value.get_boolean()
        self.settings.save()
        self._apply_wrap()

    def _apply_wrap(self):
        self.textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR if self.settings.wrap else Gtk.WrapMode.NONE)

    def _font_description(self) -> Pango.FontDescription:
        desc = Pango.FontDescription.from_string(self.settings.font or DEFAULT_FONT)
        if not desc.get_family():
            desc.set_family("Monospace")
        if desc.get_size() <= 0:
            desc.set_size(12 * Pango.SCALE)
        return desc

    def _apply_font(self):
        desc = self._font_description()
        families = ", ".join(f'"{name.strip()}"' for name in desc.get_family().split(",") if name.strip())
        style = {Pango.Style.ITALIC: "italic", Pango.Style.OBLIQUE: "oblique"}.get(desc.get_style(), "normal")
        css = (f"#{self.textview.get_name()} {{ font-family: {families}, monospace; "
               f"font-size: {desc.get_size() / Pango.SCALE:g}pt; "
               f"font-weight: {int(desc.get_weight())}; font-style: {style}; }}")
        provider = Gtk.CssProvider()
        if hasattr(provider, "load_from_string"):
            provider.load_from_string(css)
        else:
            provider.load_from_data(css.encode())
        display = Gdk.Display.get_default()
        if display is None:
            return
        if self._css_provider is not None:
            Gtk.StyleContext.remove_provider_for_display(display, self._css_provider)
        Gtk.StyleContext.add_provider_for_display(display, provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._css_provider = provider

    def zoom(self, step: int):
        desc = self._font_description()
        if step == 0:
            size = Pango.FontDescription.from_string(DEFAULT_FONT).get_size() / Pango.SCALE
        else:
            size = desc.get_size() / Pango.SCALE + step
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, round(size)))
        desc.set_size(int(size * Pango.SCALE))
        self.settings.font = desc.to_string()
        self.settings.save()
        self._apply_font()
        self.set_status(f"Tekststorleik {size} pt", timeout=2)

    def choose_font(self):
        def apply(desc):
            if desc is None:
                return
            self.settings.font = desc.to_string()
            self.settings.save()
            self._apply_font()

        if hasattr(Gtk, "FontDialog"):  # GTK 4.10 og nyare
            dialog = Gtk.FontDialog(title="Vel skrifttype", modal=True)

            def finished(dlg, result):
                try:
                    apply(dlg.choose_font_finish(result))
                except GLib.Error:
                    pass  # avbrote
            dialog.choose_font(self, self._font_description(), None, finished)
            return

        dialog = Gtk.FontChooserDialog(title="Vel skrifttype", transient_for=self, modal=True)
        dialog.set_font_desc(self._font_description())

        def response(dlg, response_id):
            if response_id == Gtk.ResponseType.OK:
                apply(dlg.get_font_desc())
            dlg.destroy()
        dialog.connect("response", response)
        dialog.present()
