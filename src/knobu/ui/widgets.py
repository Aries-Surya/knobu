"""Building blocks for the settings window: preference rows bound to a SettingsStore key,
the shortcut recorder, icon tiles, keycaps, notices and the module page header."""

from pathlib import Path

from gi.repository import Adw, Gdk, GLib, Gtk

import knobu
from knobu import APP_ID
from knobu.system import keys
from knobu.ui.store import SettingsStore
from knobu.ui.tools import copy_text

GDK_MODS = {
    Gdk.ModifierType.CONTROL_MASK: "ctrl",
    Gdk.ModifierType.ALT_MASK: "alt",
    Gdk.ModifierType.SHIFT_MASK: "shift",
    Gdk.ModifierType.SUPER_MASK: "super",
}


def record_shortcut(parent: Gtk.Widget, title: str, on_done, description: str = "") -> None:
    """Show a dialog that captures the next key or shortcut, then call on_done(text)."""
    dialog = Adw.Dialog(title=title, content_width=380)
    status = Adw.StatusPage(
        icon_name="input-keyboard-symbolic", title="Press the keys",
        description=description or "Hold Ctrl, Alt, Shift or Super if needed, then press a key.")
    view = Adw.ToolbarView(content=status)
    view.add_top_bar(Adw.HeaderBar())
    dialog.set_child(view)

    lone_mod = {"code": None}  # a modifier pressed on its own, recorded on release

    def finish(text: str):
        dialog.close()
        on_done(text)

    def on_pressed(_ctrl, _keyval, keycode, state):
        code = keycode - 8  # GDK hardware keycodes are evdev codes + 8
        if code in keys.MOD_OF_CODE:
            alone = not any(state & m for m in GDK_MODS) and lone_mod["code"] is None
            lone_mod["code"] = code if alone else -1
            return True
        lone_mod["code"] = -1
        mods = frozenset(name for mask, name in GDK_MODS.items() if state & mask)
        finish(str(keys.Chord(mods, code)))
        return True

    def on_released(_ctrl, _keyval, keycode, _state):
        if lone_mod["code"] == keycode - 8:
            finish(keys.key_name(keycode - 8))
        elif lone_mod["code"] == -1 and keycode - 8 in keys.MOD_OF_CODE:
            lone_mod["code"] = None

    # Capture phase, so keys like Escape are recorded instead of closing the dialog.
    controller = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
    controller.connect("key-pressed", on_pressed)
    controller.connect("key-released", on_released)
    dialog.add_controller(controller)
    dialog.present(parent)


def shortcut_row(store: SettingsStore, module_id: str, key: str, title: str,
                 subtitle: str = "") -> Adw.ActionRow:
    row = Adw.ActionRow(use_markup=False)
    row.set_title(title)
    row.set_subtitle(subtitle or "Click to change")
    button = Gtk.Button(child=keycaps(store.get(module_id, key)), valign=Gtk.Align.CENTER,
                        css_classes=["flat"], tooltip_text="Change shortcut")

    def on_recorded(text: str):
        store.set(module_id, key, text)
        button.set_child(keycaps(text))

    button.connect("clicked", lambda b: record_shortcut(b, title, on_recorded))
    row.add_suffix(button)
    row.set_activatable_widget(button)
    return row


def switch_row(store: SettingsStore, module_id: str, key: str, title: str,
               subtitle: str = "") -> Adw.SwitchRow:
    row = Adw.SwitchRow(use_markup=False)  # before the text, which is plain, not markup
    row.set_title(title)
    row.set_subtitle(subtitle)
    row.set_active(store.get(module_id, key))
    row.connect("notify::active", lambda r, _: store.set(module_id, key, r.get_active()))
    return row


def spin_row(store: SettingsStore, module_id: str, key: str, title: str, subtitle: str,
             lower: int, upper: int, step: int = 1) -> Adw.SpinRow:
    row = Adw.SpinRow.new_with_range(lower, upper, step)
    row.set_use_markup(False)
    row.set_title(title)
    row.set_subtitle(subtitle)
    row.set_value(store.get(module_id, key))
    row.connect("notify::value", lambda r, _: store.set(module_id, key, int(r.get_value())))
    return row


def choice_row(store: SettingsStore, module_id: str, key: str, title: str, subtitle: str,
               choices: list[tuple[object, str]]) -> Adw.ComboRow:
    """A dropdown over (stored value, label) pairs."""
    values = [v for v, _ in choices]
    row = Adw.ComboRow(use_markup=False, model=Gtk.StringList.new([label for _, label in choices]))
    row.set_title(title)
    row.set_subtitle(subtitle)
    current = store.get(module_id, key)
    row.set_selected(values.index(current) if current in values else 0)
    row.connect("notify::selected", lambda r, _: store.set(module_id, key, values[r.get_selected()]))
    return row


# ---------------------------------------------------------------------- visual pieces

def tile(icon: str, size: str = "small") -> Gtk.Widget:
    """A softly shaded rounded square holding a symbolic icon."""
    pixel_size = {"small": 14, "medium": 20, "large": 32}[size]
    # A centre box (not hexpand, which would make the tile stretch in its row).
    image = Gtk.Image(icon_name=icon, pixel_size=pixel_size)
    box = Gtk.CenterBox(css_classes=["tile", size],
                        halign=Gtk.Align.START, valign=Gtk.Align.CENTER, hexpand=False)
    box.set_center_widget(image)
    return box


def keycaps(shortcut: str) -> Gtk.Widget:
    """'super+shift+c' -> [Super] [Shift] [C] as keyboard keys."""
    box = Gtk.Box(spacing=4, valign=Gtk.Align.CENTER)
    for part in keys.pretty(shortcut).split("+"):
        box.append(Gtk.Label(label=part, css_classes=["keycap"]))
    return box


def app_icon(size: int) -> Gtk.Image:
    """The Knobu icon from the icon theme, or from the source tree when not installed."""
    theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
    if theme.has_icon(APP_ID):
        return Gtk.Image(icon_name=APP_ID, pixel_size=size)
    svg = Path(knobu.__file__).resolve().parents[2] / "data" / "icons" / f"{APP_ID}.svg"
    image = Gtk.Image.new_from_file(str(svg)) if svg.exists() else Gtk.Image(
        icon_name="application-x-executable")
    image.set_pixel_size(size)
    return image


def notice(title: str, description: str, command: str) -> Adw.PreferencesGroup:
    """A soft warning card with a one-click copyable terminal command."""
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["notice"])
    head = Gtk.Box(spacing=10)
    head.append(Gtk.Image(icon_name="dialog-warning-symbolic", css_classes=["warning"]))
    head.append(Gtk.Label(label=title, xalign=0, hexpand=True, css_classes=["heading"]))
    copy = Gtk.Button(label="Copy command", css_classes=["pill", "small"], valign=Gtk.Align.CENTER)
    head.append(copy)
    card.append(head)
    card.append(Gtk.Label(label=description, xalign=0, wrap=True, css_classes=["dim-label"]))
    card.append(Gtk.Label(label=command, xalign=0, wrap=True, selectable=True,
                          css_classes=["command"]))

    def on_copy(button):
        copy_text(button, command)
        button.set_label("Copied")
        GLib.timeout_add(1500, lambda: button.set_label("Copy command") or False)

    copy.connect("clicked", on_copy)
    group = Adw.PreferencesGroup()
    group.add(card)
    return group


class ModulePage(Adw.PreferencesPage):
    """A module's settings page with a header: big icon tile, name, description and the
    module's on/off switch. Settings groups added below grey out while it's off."""

    def __init__(self, store: SettingsStore, module_cls, notices=(), on_toggle=None,
                 dim_when_off: bool = True):
        super().__init__()
        self.dim_when_off = dim_when_off
        self.groups: list[Gtk.Widget] = []
        for n in notices:
            super().add(n)

        hero = Gtk.Box(spacing=18, css_classes=["hero"])
        hero.append(tile(module_cls.icon, "large"))
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4,
                       valign=Gtk.Align.CENTER, hexpand=True)
        text.append(Gtk.Label(label=module_cls.name, xalign=0, css_classes=["title-2"]))
        text.append(Gtk.Label(label=module_cls.description, xalign=0, wrap=True,
                              css_classes=["dim-label", "hero-subtitle"]))
        hero.append(text)
        self.switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=store.get(module_cls.id, "enabled"),
                                 tooltip_text=f"Turn {module_cls.name} on or off")
        hero.append(self.switch)
        header = Adw.PreferencesGroup()
        header.add(hero)
        super().add(header)

        def on_switch(switch, _pspec):
            if on_toggle:
                on_toggle(switch.get_active())
            else:
                store.set(module_cls.id, "enabled", switch.get_active())
            self._sync()
        self.switch.connect("notify::active", on_switch)

    def add(self, group: Gtk.Widget) -> None:
        super().add(group)
        self.groups.append(group)
        self._sync()

    def _sync(self) -> None:
        if self.dim_when_off:
            for group in self.groups:
                group.set_sensitive(self.switch.get_active())
