"""Mac-style Dynamic Island Toast & Notification Center Drawer."""

from __future__ import annotations

import argparse
import sys
import time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from knobu import APP_ID, config, service
from knobu.modules.notifications.store import NotificationHistory, NotificationRecord
from knobu.ui import style

HUD_CSS = """
.knobu-hud-pill {
  background-color: #141418;
  color: #f4f4f8;
  border: 1px solid #353540;
  border-radius: 22px;
  padding: 10px 16px;
}
.knobu-drawer-win {
  background-color: #16161a;
  color: #f4f4f8;
}
"""


class NotificationDrawerWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Knobu Notification Center", default_width=440, default_height=560)
        style.apply()
        self.history = NotificationHistory()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        header = Adw.HeaderBar()

        cfg = config.load()
        dnd_sw = Gtk.Switch(active=bool(cfg.get("notifications", {}).get("dnd", False)),
                            valign=Gtk.Align.CENTER, tooltip_text="Do Not Disturb")
        def on_dnd(sw, _p):
            d = config.load()
            d.setdefault("notifications", {})["dnd"] = sw.get_active()
            config.save(d)
            service.reload()
        dnd_sw.connect("notify::active", on_dnd)
        dnd_box = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        dnd_box.append(Gtk.Label(label="DND", css_classes=["dim-label"]))
        dnd_box.append(dnd_sw)
        header.pack_start(dnd_box)

        clear_btn = Gtk.Button(label="Clear All", css_classes=["flat"])
        clear_btn.connect("clicked", lambda _b: (self.history.clear(), self._rebuild()))
        header.pack_end(clear_btn)
        box.append(header)

        self.list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        self.list_box.set_margin_top(12)
        self.list_box.set_margin_bottom(12)
        self.list_box.set_margin_start(12)
        self.list_box.set_margin_end(12)
        scroll = Gtk.ScrolledWindow(vexpand=True, child=self.list_box)
        box.append(scroll)
        self.set_content(box)
        self._rebuild()

    def _rebuild(self) -> None:
        while child := self.list_box.get_first_child():
            self.list_box.remove(child)
        records = self.history.list_recent(40)
        if not records:
            self.list_box.append(Adw.ActionRow(use_markup=False, title="No notifications yet",
                                               subtitle="Incoming desktop notifications appear here automatically."))
            return
        for rec in records:
            t_str = time.strftime("%-I:%M %p", time.localtime(rec.timestamp))
            row = Adw.ActionRow(
                use_markup=False,
                title=f"{rec.app_name} · {rec.summary}" if rec.summary else rec.app_name,
                subtitle=f"[{t_str}] {rec.body}".strip(),
            )
            self.list_box.append(row)


class HudToastWindow(Gtk.Window):
    def __init__(self, app: Adw.Application, rec: NotificationRecord):
        super().__init__(application=app, decorated=False, title="Knobu Notification")
        self.set_default_size(380, -1)
        style.apply()
        provider = Gtk.CssProvider()
        provider.load_from_string(HUD_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 10
        )
        self.set_css_classes(["knobu-hud-pill"])

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                      margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)
        icon = Gtk.Image.new_from_icon_name(rec.icon or "preferences-system-notifications-symbolic")
        icon.set_pixel_size(28)
        row.append(icon)

        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
        text.append(Gtk.Label(label=f"{rec.app_name} · {rec.summary}" if rec.summary else rec.app_name,
                              xalign=0, css_classes=["heading"]))
        if rec.body:
            lbl = Gtk.Label(label=rec.body, xalign=0, css_classes=["dim-label"])
            lbl.set_ellipsize(3)
            text.append(lbl)
        row.append(text)
        self.set_child(row)

        click = Gtk.GestureClick()
        click.connect("released", lambda *_a: self.close())
        row.add_controller(click)
        GLib.timeout_add_seconds(4, lambda: (self.close(), GLib.SOURCE_REMOVE)[1])


class NotificationsApp(Adw.Application):
    def __init__(self, toast_id: int | None = None):
        super().__init__(application_id=f"{APP_ID}.notifications", flags=Gio.ApplicationFlags.NON_UNIQUE)
        self.toast_id = toast_id

    def do_activate(self):
        if self.toast_id is not None:
            recs = [r for r in NotificationHistory().list_recent(10) if r.id == self.toast_id]
            if recs:
                win = HudToastWindow(self, recs[0])
                win.present()
                return
        NotificationDrawerWindow(self).present()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="knobu notifications")
    parser.add_argument("--toast", type=int, default=None)
    args = parser.parse_args(argv or [])
    return NotificationsApp(toast_id=args.toast).run([])
