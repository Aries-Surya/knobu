"""The Knobu settings application: a sidebar of pages, PowerToys-style."""

from gi.repository import Adw, Gio, GLib, GObject, Gtk

from knobu import APP_ID, __version__, service
from knobu.ui import style
from knobu.ui.pages import PAGES
from knobu.ui.store import SettingsStore
from knobu.ui.widgets import tile


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(title="Knobu", default_width=1040, default_height=720, **kwargs)
        self.store = SettingsStore()
        self.store.listeners.append(self._on_setting_changed)
        self.rows: dict[str, Gtk.ListBoxRow] = {}
        self.dots: dict[str, Gtk.Widget] = {}

        self.split = Adw.NavigationSplitView(min_sidebar_width=240, max_sidebar_width=280)
        self.split.set_sidebar(self._build_sidebar())
        self.set_content(self.split)

        narrow = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 640sp"))
        narrow.add_setter(self.split, "collapsed", GObject.Value(GObject.TYPE_BOOLEAN, True))
        self.add_breakpoint(narrow)

        self.navigate("dashboard")
        GLib.timeout_add_seconds(3, self._refresh_footer)

    # ------------------------------------------------------------------ sidebar

    def _build_sidebar(self) -> Adw.NavigationPage:
        self.lists = []
        top = self._nav_list([p for p in PAGES if p[4] == "top"])
        mods = self._nav_list([p for p in PAGES if p[4] == "modules"], dots=True)
        bottom = self._nav_list([p for p in PAGES if p[4] == "bottom"])

        body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.append(top)
        body.append(Gtk.Label(label="MODULES", xalign=0, css_classes=["sidebar-heading", "dim-label"]))
        body.append(mods)

        footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        footer.append(Gtk.Separator())
        footer.append(bottom)
        status = Gtk.Box(spacing=8, css_classes=["sidebar-footer"])
        self.footer_dot = Gtk.Box(css_classes=["dot"], valign=Gtk.Align.CENTER)
        self.footer_label = Gtk.Label(xalign=0, css_classes=["dim-label"])
        status.append(self.footer_dot)
        status.append(self.footer_label)
        footer.append(status)
        self._refresh_footer()

        menu = Gio.Menu()
        menu.append("About Knobu", "app.about")
        menu.append("Quit", "app.quit")
        header = Adw.HeaderBar()
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu,
                                       tooltip_text="Main menu"))
        view = Adw.ToolbarView(content=Gtk.ScrolledWindow(
            child=body, hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True))
        view.add_top_bar(header)
        view.add_bottom_bar(footer)
        return Adw.NavigationPage(title="Knobu", child=view)

    def _nav_list(self, pages, dots: bool = False) -> Gtk.ListBox:
        listbox = Gtk.ListBox(css_classes=["navigation-sidebar"])
        for page_id, title, icon, _builder, _section in pages:
            box = Gtk.Box(spacing=12, margin_top=3, margin_bottom=3)
            box.append(tile(icon, "small"))
            box.append(Gtk.Label(label=title, xalign=0, hexpand=True))
            if dots:
                dot = Gtk.Box(css_classes=["dot"], valign=Gtk.Align.CENTER,
                              tooltip_text="On" if self.store.get(page_id, "enabled") else "Off")
                if self.store.get(page_id, "enabled"):
                    dot.add_css_class("on")
                self.dots[page_id] = dot
                box.append(dot)
            row = Gtk.ListBoxRow(child=box)
            row.page_id = page_id
            self.rows[page_id] = row
            listbox.append(row)
        listbox.connect("row-selected", self._on_row_selected)
        self.lists.append(listbox)
        return listbox

    def _refresh_footer(self) -> bool:
        running = service.is_active()
        self.footer_label.set_label("Service running" if running else "Service stopped")
        self.footer_dot.set_css_classes(["dot", "on"] if running else ["dot"])
        return GLib.SOURCE_CONTINUE

    def _on_setting_changed(self, module_id: str, key: str, value) -> None:
        if key == "enabled" and module_id in self.dots:
            dot = self.dots[module_id]
            dot.set_css_classes(["dot", "on"] if value else ["dot"])
            dot.set_tooltip_text("On" if value else "Off")

    # ------------------------------------------------------------------ pages

    def navigate(self, page_id: str) -> None:
        row = self.rows[page_id]
        row.get_parent().select_row(row)

    def _on_row_selected(self, listbox, row) -> None:
        if row is None:
            return
        for other in self.lists:  # one selection across all sidebar sections
            if other is not listbox:
                other.unselect_all()
        _id, title, _icon, builder, _section = next(p for p in PAGES if p[0] == row.page_id)
        view = Adw.ToolbarView(content=builder(self.store, self.navigate))
        view.add_top_bar(Adw.HeaderBar(show_title=row.page_id != "dashboard"))
        self.split.set_content(Adw.NavigationPage(title=title, child=view))
        self.split.set_show_content(True)
        self._refresh_footer()


class KnobuApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_startup(self):
        Adw.Application.do_startup(self)
        style.apply()
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
            website="https://github.com/Aries-Surya/knobu",
            issue_url="https://github.com/Aries-Surya/knobu/issues",
            comments="PowerToys-style utilities for Ubuntu and its flavours.",
            license_type=Gtk.License.GPL_3_0,
        ).present(self.props.active_window)


def main(argv: list[str]) -> int:
    return KnobuApp().run(argv)
