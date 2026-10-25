"""Programmet: held styr på vindauge, menyhandlingar og snarvegar."""

import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from . import APP_ID, BIRTH_DATE, RELEASE_DATE, REPO_URL, __version__, format_date  # noqa: E402
from .settings import Settings  # noqa: E402
from .window import FroditorWindow  # noqa: E402

ACCELS = {
    "win.new": ["<Control>n"],
    "win.open": ["<Control>o"],
    "win.save": ["<Control>s"],
    "win.save-as": ["<Control><Shift>s"],
    "win.find": ["<Control>f"],
    "win.replace": ["<Control>h"],
    "win.find-next": ["F3", "<Control>g"],
    "win.find-prev": ["<Shift>F3", "<Control><Shift>g"],
    "win.zoom-in": ["<Control>plus", "<Control>equal", "<Control>KP_Add"],
    "win.zoom-out": ["<Control>minus", "<Control>KP_Subtract"],
    "win.zoom-reset": ["<Control>0", "<Control>KP_0"],
    "win.close": ["<Control>w"],
    "app.new-window": ["<Control><Shift>n"],
    "app.quit": ["<Control>q"],
}


class FroditorApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        GLib.set_application_name("Froditor")
        self.settings = Settings.load()

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Gtk.Window.set_default_icon_name(APP_ID)
        for name, callback in (
            ("new-window", lambda *_: self.new_window().present()),
            ("about", lambda *_: self.show_about()),
            ("quit", lambda *_: self.quit_all()),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
        for action, accels in ACCELS.items():
            self.set_accels_for_action(action, accels)

    def do_activate(self):
        window = self.get_active_window() or self.new_window()
        window.present()

    def do_open(self, files, n_files, hint):
        for gfile in files:
            window = self.get_active_window()
            if not (isinstance(window, FroditorWindow) and window.is_pristine()):
                window = self.new_window()
            window.load_file(gfile)
            window.present()

    def new_window(self) -> FroditorWindow:
        return FroditorWindow(application=self, settings=self.settings)

    def quit_all(self):
        # Kvart vindauge spør sjølv om ulagra endringar før det lukkar seg.
        for window in list(self.get_windows()):
            window.close()

    def show_about(self):
        dialog = Gtk.AboutDialog(
            transient_for=self.get_active_window(),
            modal=True,
            program_name="Froditor",
            version=__version__,
            comments=("Den beste teksthandsamar for tekstfiler og PowerShell-skript\n\n"
                      f"Fødd: {format_date(BIRTH_DATE)}\n"
                      f"Sist oppdatert: {format_date(RELEASE_DATE)}"),
            website=REPO_URL,
            website_label="Froditor på GitHub",
            logo_icon_name=APP_ID,
            authors=["Frode"],
            license_type=Gtk.License.MIT_X11,
        )
        dialog.present()


def main(argv=None) -> int:
    return FroditorApp().run(argv if argv is not None else sys.argv)
