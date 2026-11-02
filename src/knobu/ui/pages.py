"""Pages of the settings window: General plus one page per module."""

import shutil
import subprocess
import time

from gi.repository import Adw, GLib, Gtk

from knobu import service
from knobu.modules.awake import AwakeModule
from knobu.modules.hotkey_tools import ColorPickerModule, TextExtractorModule
from knobu.modules.keyboard import KeyboardModule
from knobu.modules.touchpad import TAP_ACTIONS, TouchpadModule
from knobu.system import keys, launch, permissions
from knobu.ui.store import SettingsStore
from knobu.ui.textextractor import INSTALL_TESSERACT
from knobu.ui.widgets import choice_row, record_shortcut, shortcut_row, spin_row, switch_row


def command_warning(title: str, description: str, command: str) -> Adw.PreferencesGroup:
    """A warning group with a copyable terminal command."""
    group = Adw.PreferencesGroup(title=title, description=description)
    row = Adw.ActionRow(title=command, title_selectable=True)
    row.add_css_class("monospace")
    row.add_prefix(Gtk.Image.new_from_icon_name("dialog-warning-symbolic"))
    group.add(row)
    return group


def button_row(title: str, label: str, callback) -> Adw.ActionRow:
    row = Adw.ActionRow(title=title)
    button = Gtk.Button(label=label, valign=Gtk.Align.CENTER)
    button.connect("clicked", lambda _b: callback())
    row.add_suffix(button)
    row.set_activatable_widget(button)
    return row


def general_page(store: SettingsStore) -> Adw.PreferencesPage:
    page = Adw.PreferencesPage()

    if not permissions.in_input_group():
        page.add(command_warning(
            "Input access needed",
            "Knobu can't read your touchpad and keyboard yet. Run this command in a terminal, "
            "then log out and back in:", permissions.FIX_INPUT_GROUP))

    group = Adw.PreferencesGroup(
        title="Background service",
        description="Knobu runs quietly in the background so gestures, shortcuts and "
                    "remaps work everywhere.")
    status = Adw.ActionRow(title="Status")
    button = Gtk.Button(valign=Gtk.Align.CENTER)
    status.add_suffix(button)
    autostart = Adw.SwitchRow(title="Start at login")
    group.add(status)
    group.add(autostart)
    page.add(group)

    def refresh() -> bool:
        running = service.is_active()
        status.set_subtitle("Running" if running else "Stopped")
        button.set_label("Stop" if running else "Start")
        for cls in ("suggested-action", "destructive-action"):
            button.remove_css_class(cls)
        button.add_css_class("destructive-action" if running else "suggested-action")
        autostart.handler_block(autostart_handler)
        autostart.set_active(service.is_enabled())
        autostart.handler_unblock(autostart_handler)
        return GLib.SOURCE_REMOVE

    def on_button(_btn) -> None:
        service.stop() if service.is_active() else service.start()
        GLib.timeout_add(600, refresh)  # give systemd a moment to change state

    def on_autostart(row, _pspec) -> None:
        service.set_autostart(row.get_active())
        refresh()

    button.connect("clicked", on_button)
    autostart_handler = autostart.connect("notify::active", on_autostart)
    refresh()
    return page


def touchpad_page(store: SettingsStore) -> Adw.PreferencesPage:
    mid = TouchpadModule.id
    page = Adw.PreferencesPage()

    top = Adw.PreferencesGroup(description=TouchpadModule.description)
    top.add(switch_row(store, mid, "enabled", "Enable Touchpad Gestures"))
    page.add(top)

    volume = Adw.PreferencesGroup(title="Volume", description="Slide up or down to change volume.")
    volume.add(switch_row(store, mid, "volume_drag", "Slide to change volume"))
    volume.add(choice_row(store, mid, "fingers", "Slide with", "",
                          [(3, "3 fingers"), (4, "4 fingers")]))
    volume.add(spin_row(store, mid, "percent_per_cm", "Speed",
                        "Volume change (%) per centimetre of movement", 5, 50))
    volume.add(switch_row(store, mid, "invert", "Reverse direction", "Slide down to make it louder"))
    volume.add(spin_row(store, mid, "max_volume", "Maximum volume",
                        "Values above 100% amplify and may distort", 50, 150, 5))
    page.add(volume)

    taps = Adw.PreferencesGroup(title="Taps", description="A quick tap with several fingers.")
    actions = list(TAP_ACTIONS.items())
    taps.add(choice_row(store, mid, "tap3_action", "3-finger tap",
                        "Linux also sends a middle-click on this tap", actions))
    taps.add(choice_row(store, mid, "tap4_action", "4-finger tap", "", actions))
    page.add(taps)

    feedback = Adw.PreferencesGroup(title="Feedback")
    feedback.add(switch_row(store, mid, "osd", "Show volume pop-up",
                            "Uses your desktop's own volume display (KDE Plasma for now)"))
    page.add(feedback)
    return page


def keyboard_page(store: SettingsStore) -> Adw.PreferencesPage:
    mid = KeyboardModule.id
    page = Adw.PreferencesPage()

    if not permissions.can_write_uinput():
        page.add(command_warning(
            "One-time setup needed",
            "Remapping needs permission to create a virtual keyboard. Run this in a terminal:",
            permissions.FIX_UINPUT))

    top = Adw.PreferencesGroup(description=KeyboardModule.description)
    top.add(switch_row(store, mid, "enabled", "Enable Keyboard Manager"))
    page.add(top)

    group = Adw.PreferencesGroup(
        title="Remaps",
        description="A single key changes everywhere, even inside shortcuts "
                    "(e.g. CapsLock → Ctrl). A shortcut only changes as a whole.")
    add = Gtk.Button(icon_name="list-add-symbolic", tooltip_text="Add a remap",
                     css_classes=["flat"], valign=Gtk.Align.CENTER)
    group.set_header_suffix(add)
    page.add(group)
    rows: list[Gtk.Widget] = []

    def rebuild():
        for row in rows:
            group.remove(row)
        rows.clear()
        remaps = store.get(mid, "remaps")
        if not remaps:
            rows.append(Adw.ActionRow(title="No remaps yet",
                                      subtitle="Click + to remap a key or shortcut"))
        for text in remaps:
            src, _, dst = text.partition("->")
            row = Adw.ActionRow(title=f"{keys.pretty(src.strip())}  →  {keys.pretty(dst.strip())}")
            delete = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Remove",
                                css_classes=["flat"], valign=Gtk.Align.CENTER)
            delete.connect("clicked", lambda _b, t=text: remove(t))
            row.add_suffix(delete)
            rows.append(row)
        for row in rows:
            group.add(row)

    def remove(text: str):
        store.set(mid, "remaps", [r for r in store.get(mid, "remaps") if r != text])
        rebuild()

    def on_add(_button):
        def got_source(src: str):
            def got_target(dst: str):
                remaps = [r for r in store.get(mid, "remaps") if not r.startswith(src + " ->")]
                store.set(mid, "remaps", remaps + [f"{src} -> {dst}"])
                rebuild()
            GLib.idle_add(lambda: record_shortcut(
                add, "New remap", got_target,
                f"Now press what {keys.pretty(src)} should become.") and False)
        record_shortcut(add, "New remap", got_source,
                        "Press the key or shortcut you want to change.")

    add.connect("clicked", on_add)
    rebuild()
    return page


def awake_page(store: SettingsStore) -> Adw.PreferencesPage:
    mid = AwakeModule.id
    page = Adw.PreferencesPage()

    group = Adw.PreferencesGroup(description=AwakeModule.description)
    toggle = Adw.SwitchRow(title="Keep awake", active=store.get(mid, "enabled"))
    status = Adw.ActionRow(title="Status")
    group.add(toggle)
    group.add(status)
    page.add(group)

    timing = Adw.PreferencesGroup(title="Duration")
    modes = ["indefinite", "timed"]
    mode = Adw.ComboRow(title="Keep awake", model=Gtk.StringList.new(
        ["Until I turn it off", "For a set time"]))
    mode.set_selected(modes.index(store.get(mid, "mode")))
    minutes = Adw.SpinRow.new_with_range(5, 24 * 60, 5)
    minutes.set_title("Minutes")
    minutes.set_value(store.get(mid, "minutes"))
    timing.add(mode)
    timing.add(minutes)
    page.add(timing)

    screen = Adw.PreferencesGroup(title="Display")
    screen.add(switch_row(store, mid, "keep_screen_on", "Keep screen on",
                          "Otherwise the screen may still turn off while the computer stays awake"))
    page.add(screen)

    def refresh():
        timed = store.get(mid, "mode") == "timed"
        minutes.set_sensitive(timed)
        until = store.get(mid, "until")
        if not store.get(mid, "enabled"):
            text = "Off"
        elif not timed:
            text = "Awake until you turn it off"
        elif until > time.time():
            text = time.strftime("Awake until %H:%M", time.localtime(until))
        else:
            text = time.strftime("Timer ended at %H:%M", time.localtime(until))
        status.set_subtitle(text)

    def restart_timer():
        if store.get(mid, "mode") == "timed":
            store.set(mid, "until", time.time() + store.get(mid, "minutes") * 60)

    def on_toggle(row, _pspec):
        store.set(mid, "enabled", row.get_active())
        if row.get_active():
            restart_timer()
        refresh()

    def on_mode(row, _pspec):
        store.set(mid, "mode", modes[row.get_selected()])
        restart_timer()
        refresh()

    def on_minutes(row, _pspec):
        store.set(mid, "minutes", int(row.get_value()))
        restart_timer()
        refresh()

    toggle.connect("notify::active", on_toggle)
    mode.connect("notify::selected", on_mode)
    minutes.connect("notify::value", on_minutes)
    refresh()
    return page


def colorpicker_page(store: SettingsStore) -> Adw.PreferencesPage:
    mid = ColorPickerModule.id
    page = Adw.PreferencesPage()
    group = Adw.PreferencesGroup(description=ColorPickerModule.description)
    group.add(switch_row(store, mid, "enabled", "Enable Color Picker"))
    group.add(shortcut_row(store, mid, "hotkey", "Shortcut"))
    group.add(choice_row(store, mid, "format", "Copy as", "Copied automatically after picking",
                         [("hex", "HEX  #1E90FF"), ("rgb", "RGB  rgb(30, 144, 255)"),
                          ("hsl", "HSL  hsl(210, 100%, 56%)")]))
    group.add(button_row("Try it", "Pick a colour", lambda: launch.knobu("pick-color")))
    page.add(group)
    return page


def tesseract_languages() -> list[str]:
    if not shutil.which("tesseract"):
        return []
    out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
    return [line.strip() for line in out.splitlines()[1:] if line.strip() and line.strip() != "osd"]


def textextractor_page(store: SettingsStore) -> Adw.PreferencesPage:
    mid = TextExtractorModule.id
    page = Adw.PreferencesPage()
    languages = tesseract_languages()
    if not languages:
        page.add(command_warning(
            "Text recognition isn't installed",
            "Text Extractor uses Tesseract to read text. Install it with:", INSTALL_TESSERACT))

    group = Adw.PreferencesGroup(description=TextExtractorModule.description)
    group.add(switch_row(store, mid, "enabled", "Enable Text Extractor"))
    group.add(shortcut_row(store, mid, "hotkey", "Shortcut"))
    if languages:
        group.add(choice_row(store, mid, "language", "Language",
                             "More with: sudo apt install tesseract-ocr-<language code>",
                             [(lang, lang) for lang in languages]))
    group.add(button_row("Try it", "Select an area", lambda: launch.knobu("extract-text")))
    page.add(group)
    return page


# (id, title, icon, builder). Add new module pages here.
PAGES = [
    ("general", "General", "preferences-system-symbolic", general_page),
    (TouchpadModule.id, TouchpadModule.name, TouchpadModule.icon, touchpad_page),
    (KeyboardModule.id, KeyboardModule.name, KeyboardModule.icon, keyboard_page),
    (AwakeModule.id, AwakeModule.name, AwakeModule.icon, awake_page),
    (ColorPickerModule.id, ColorPickerModule.name, ColorPickerModule.icon, colorpicker_page),
    (TextExtractorModule.id, TextExtractorModule.name, TextExtractorModule.icon,
     textextractor_page),
]
