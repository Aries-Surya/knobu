"""Preference rows bound directly to a SettingsStore key, and the shortcut recorder."""

from gi.repository import Adw, Gdk, Gtk

from knobu.system import keys
from knobu.ui.store import SettingsStore

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
    row = Adw.ActionRow(title=title, subtitle=subtitle)
    button = Gtk.Button(label=keys.pretty(store.get(module_id, key)), valign=Gtk.Align.CENTER)

    def on_recorded(text: str):
        store.set(module_id, key, text)
        button.set_label(keys.pretty(text))

    button.connect("clicked", lambda b: record_shortcut(b, title, on_recorded))
    row.add_suffix(button)
    row.set_activatable_widget(button)
    return row


def switch_row(store: SettingsStore, module_id: str, key: str, title: str,
               subtitle: str = "") -> Adw.SwitchRow:
    row = Adw.SwitchRow(title=title, subtitle=subtitle)
    row.set_active(store.get(module_id, key))
    row.connect("notify::active", lambda r, _: store.set(module_id, key, r.get_active()))
    return row


def spin_row(store: SettingsStore, module_id: str, key: str, title: str, subtitle: str,
             lower: int, upper: int, step: int = 1) -> Adw.SpinRow:
    row = Adw.SpinRow.new_with_range(lower, upper, step)
    row.set_title(title)
    row.set_subtitle(subtitle)
    row.set_value(store.get(module_id, key))
    row.connect("notify::value", lambda r, _: store.set(module_id, key, int(r.get_value())))
    return row


def choice_row(store: SettingsStore, module_id: str, key: str, title: str, subtitle: str,
               choices: list[tuple[object, str]]) -> Adw.ComboRow:
    """A dropdown over (stored value, label) pairs."""
    values = [v for v, _ in choices]
    row = Adw.ComboRow(title=title, subtitle=subtitle,
                       model=Gtk.StringList.new([label for _, label in choices]))
    current = store.get(module_id, key)
    row.set_selected(values.index(current) if current in values else 0)
    row.connect("notify::selected", lambda r, _: store.set(module_id, key, values[r.get_selected()]))
    return row
