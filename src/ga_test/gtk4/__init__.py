import sys

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import GLib, Gtk  # noqa: E402


class Application(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id='com.example.MyGtkApplication')
        GLib.set_application_name('My Gtk Application')

    def do_activate(self) -> None:
        window = Gtk.ApplicationWindow(application=self, title='Hello World')
        window.present()


def start() -> int:
    app = Application()
    return app.run(sys.argv)
