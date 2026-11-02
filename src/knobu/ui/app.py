"""The Knobu settings application: a sidebar of pages, PowerToys-style."""

from gi.repository import Adw, Gio, GObject, Gtk

from knobu import APP_ID, __version__
from knobu.ui.pages import PAGES
from knobu.ui.store import SettingsStore


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(title="Knobu", default_width=900, default_height=640, **kwargs)
        self.store = SettingsStore()

        self.split = Adw.NavigationSplitView(min_sidebar_width=220)
        self.split.set_sidebar(self._build_sidebar())
        self.set_content(self.split)

        narrow = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 600sp"))
        narrow.add_setter(self.split, "collapsed", GObject.Value(GObject.TYPE_BOOLEAN, True))
        self.add_breakpoint(narrow)

        self.sidebar_list.select_row(self.sidebar_list.get_row_at_index(0))

    def _build_sidebar(self) -> Adw.NavigationPage:
        self.sidebar_list = Gtk.ListBox(css_classes=["navigation-sidebar"])
        for page_id, title, icon, _builder in PAGES:
            box = Gtk.Box(spacing=12, margin_start=6, margin_end=6, margin_top=6, margin_bottom=6)
            box.append(Gtk.Image.new_from_icon_name(icon))
            box.append(Gtk.Label(label=title, xalign=0))
            row = Gtk.ListBoxRow(child=box)
            row.page_id = page_id
            self.sidebar_list.append(row)
        self.sidebar_list.connect("row-selected", self._on_row_selected)

        menu = Gio.Menu()
        menu.append("About Knobu", "app.about")
        header = Adw.HeaderBar()
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                       tooltip_text="Main menu"))
        view = Adw.ToolbarView(content=Gtk.ScrolledWindow(child=self.sidebar_list))
        view.add_top_bar(header)
        return Adw.NavigationPage(title="Knobu", child=view)

    def _on_row_selected(self, _list, row) -> None:
        if row is None:
            return
        _id, title, _icon, builder = next(p for p in PAGES if p[0] == row.page_id)
        view = Adw.ToolbarView(content=builder(self.store))
        view.add_top_bar(Adw.HeaderBar())
        self.split.set_content(Adw.NavigationPage(title=title, child=view))
        self.split.set_show_content(True)


class KnobuApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_startup(self):
        Adw.Application.do_startup(self)
        for name, callback in (("about", self._on_about), ("quit", lambda *_: self.quit())):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
        self.set_accels_for_action("app.quit", ["<primary>q"])

    def do_activate(self):
        window = self.props.active_window or MainWindow(application=self)
        window.present()

    def _on_about(self, *_args):
        Adw.AboutDialog(
            application_name="Knobu",
            application_icon=APP_ID,
            version=__version__,
            developer_name="Knobu contributors",
            comments="PowerToys-style utilities for Ubuntu and its flavours.",
            license_type=Gtk.License.GPL_3_0,
        ).present(self.props.active_window)


def main(argv: list[str]) -> int:
    return KnobuApp().run(argv)
