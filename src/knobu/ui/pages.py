"""Pages of the settings window: Dashboard, one page per module, and General.

Each builder takes (store, navigate) and returns a widget; `navigate(page_id)` opens
another page.
"""

import shutil
import subprocess
import time

from gi.repository import Adw, GLib, Gtk

from knobu import modules, service
from knobu.modules.awake import AwakeModule
from knobu.modules.clipboard import ClipboardModule
from knobu.modules.hotkey_tools import ColorPickerModule, TextExtractorModule
from knobu.modules.keyboard import KeyboardModule
from knobu.modules.touchpad import TAP_ACTIONS, TouchpadModule
from knobu.system import keys, launch, permissions
from knobu.system.audio import system_max_volume
from knobu.ui.store import SettingsStore
from knobu.ui.textextractor import INSTALL_TESSERACT
from knobu.ui.widgets import (ModulePage, app_icon, choice_row, keycaps, notice, record_shortcut,
                              shortcut_row, spin_row, switch_row, tile)


def button_row(title: str, label: str, callback, subtitle: str = "") -> Adw.ActionRow:
    row = Adw.ActionRow(use_markup=False)
    row.set_title(title)
    row.set_subtitle(subtitle)
    button = Gtk.Button(label=label, valign=Gtk.Align.CENTER, css_classes=["pill"])
    button.connect("clicked", lambda _b: callback())
    row.add_suffix(button)
    row.set_activatable_widget(button)
    return row


def input_notice() -> list:
    if permissions.in_input_group():
        return []
    return [notice("Input access needed",
                   "Knobu can't read your touchpad and keyboard yet. Run this in a terminal, "
                   "then log out and back in.", permissions.FIX_INPUT_GROUP)]


# ---------------------------------------------------------------------- Awake helpers

def awake_status(store: SettingsStore) -> str:
    mid = AwakeModule.id
    until = store.get(mid, "until")
    if not store.get(mid, "enabled"):
        return "Off"
    if store.get(mid, "mode") != "timed":
        return "Awake until you turn it off"
    if until > time.time():
        return time.strftime("Awake until %-I:%M %p", time.localtime(until))
    return time.strftime("Timer ended at %-I:%M %p", time.localtime(until))


def restart_awake_timer(store: SettingsStore) -> None:
    mid = AwakeModule.id
    if store.get(mid, "mode") == "timed":
        store.set(mid, "until", time.time() + store.get(mid, "minutes") * 60)


def set_awake(store: SettingsStore, on: bool) -> None:
    store.set(AwakeModule.id, "enabled", on)
    if on:
        restart_awake_timer(store)


# ---------------------------------------------------------------------- Dashboard

def module_summary(store: SettingsStore, module_id: str) -> Gtk.Widget:
    """A one-line live summary shown on the module's dashboard card."""
    def text(label: str) -> Gtk.Widget:
        return Gtk.Label(label=label, xalign=0, css_classes=["dim-label", "summary"])

    if module_id == TouchpadModule.id:
        fingers = store.get(module_id, "fingers")
        return text(f"{fingers}-finger slide for volume · taps for mute and media")
    if module_id == KeyboardModule.id:
        n = len(store.get(module_id, "remaps"))
        return text(f"{n} remap{'s' if n != 1 else ''}" if n else "No remaps yet")
    if module_id == AwakeModule.id:
        return text(awake_status(store))
    if module_id in (ClipboardModule.id, ColorPickerModule.id, TextExtractorModule.id):
        return keycaps(store.get(module_id, "hotkey"))
    return text("")


def module_card(store: SettingsStore, cls) -> Gtk.Widget:
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                   css_classes=["card", "module-card"])
    top = Gtk.Box(spacing=12)
    top.append(tile(cls.icon, "medium"))
    top.append(Gtk.Box(hexpand=True))
    switch = Gtk.Switch(valign=Gtk.Align.CENTER, active=store.get(cls.id, "enabled"),
                        tooltip_text=f"Turn {cls.name} on or off")
    top.append(switch)
    card.append(top)
    card.append(Gtk.Label(label=cls.name, xalign=0, css_classes=["heading"]))
    # max_width_chars keeps the natural width small so cards sit side by side in the grid.
    desc = Gtk.Label(label=cls.description, xalign=0, wrap=True, lines=3, max_width_chars=26,
                     ellipsize=3, css_classes=["dim-label"], vexpand=True, valign=Gtk.Align.START)
    card.append(desc)
    summary = Gtk.Box()
    summary.append(module_summary(store, cls.id))
    card.append(summary)

    def on_switch(sw, _pspec):
        if cls.id == AwakeModule.id:
            set_awake(store, sw.get_active())
        else:
            store.set(cls.id, "enabled", sw.get_active())
        summary.remove(summary.get_first_child())
        summary.append(module_summary(store, cls.id))
    switch.connect("notify::active", on_switch)
    card.set_cursor_from_name("pointer")
    card.module_id = cls.id
    return card


def service_status(on_change=None) -> Gtk.Widget:
    """A 'Running'/'Stopped' pill with a Start/Stop button."""
    box = Gtk.Box(spacing=10, valign=Gtk.Align.CENTER)
    pill = Gtk.Label(css_classes=["pill"])
    button = Gtk.Button(valign=Gtk.Align.CENTER, css_classes=["pill"])
    box.append(pill)
    box.append(button)

    def refresh() -> bool:
        running = service.is_active()
        pill.set_label("● Running" if running else "● Stopped")
        pill.set_css_classes(["pill", "running" if running else "stopped"])
        button.set_label("Stop" if running else "Start")
        button.set_css_classes(["pill"] if running else ["pill", "suggested-action"])
        if on_change:
            on_change(running)
        return GLib.SOURCE_REMOVE

    def on_click(_b):
        service.stop() if service.is_active() else service.start()
        GLib.timeout_add(600, refresh)  # give systemd a moment to change state

    button.connect("clicked", on_click)
    refresh()
    return box


def dashboard_page(store: SettingsStore, navigate) -> Gtk.Widget:
    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                      margin_top=24, margin_bottom=32, margin_start=12, margin_end=12)

    hero = Gtk.Box(spacing=20, css_classes=["hero"])
    hero.append(app_icon(72))
    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER,
                   hexpand=True)
    text.append(Gtk.Label(label="Knobu", xalign=0, css_classes=["title-1"]))
    text.append(Gtk.Label(label="Power tools for your Ubuntu desktop.", xalign=0,
                          css_classes=["dim-label", "hero-subtitle"]))
    hero.append(text)
    hero.append(service_status())
    content.append(hero)

    for n in input_notice():
        content.append(n)

    content.append(Gtk.Label(label="Modules", xalign=0, css_classes=["title-4"]))
    grid = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                       min_children_per_line=1, max_children_per_line=3,
                       activate_on_single_click=True, column_spacing=12, row_spacing=12,
                       css_classes=["module-grid"])
    for cls in modules.MODULES:
        grid.append(module_card(store, cls))
    grid.connect("child-activated", lambda _g, child: navigate(child.get_child().module_id))
    content.append(grid)

    clamp = Adw.Clamp(maximum_size=980, tightening_threshold=700, child=content)
    return Gtk.ScrolledWindow(child=clamp, hscrollbar_policy=Gtk.PolicyType.NEVER)


# ---------------------------------------------------------------------- module pages

def touchpad_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    mid = TouchpadModule.id
    page = ModulePage(store, TouchpadModule, notices=input_notice())

    volume = Adw.PreferencesGroup(title="Volume", description="Slide up or down to change volume.")
    volume.add(switch_row(store, mid, "volume_drag", "Slide to change volume"))
    volume.add(choice_row(store, mid, "fingers", "Slide with", "",
                          [(3, "3 fingers"), (4, "4 fingers")]))
    volume.add(spin_row(store, mid, "percent_per_cm", "Speed",
                        "Volume change (%) per centimetre of movement", 5, 50))
    volume.add(switch_row(store, mid, "invert", "Reverse direction", "Slide down to make it louder"))
    volume.add(choice_row(
        store, mid, "max_volume", "Maximum volume", "Above 100% amplifies and may distort",
        [("system", f"Same as system ({system_max_volume()}%)"),
         (100, "100%"), (125, "125%"), (150, "150%")]))
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


def keyboard_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    mid = KeyboardModule.id
    notices = input_notice()
    if not permissions.can_write_uinput():
        notices.append(notice(
            "One-time setup needed",
            "Remapping needs permission to create a virtual keyboard. Run this in a terminal:",
            permissions.FIX_UINPUT))
    page = ModulePage(store, KeyboardModule, notices=notices)

    group = Adw.PreferencesGroup(
        title="Remaps",
        description="A single key changes everywhere, even inside shortcuts "
                    "(e.g. CapsLock → Ctrl). A shortcut only changes as a whole.")
    add = Gtk.Button(valign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"],
                     tooltip_text="Add a remap")
    add_box = Gtk.Box(spacing=6)
    add_box.append(Gtk.Image(icon_name="list-add-symbolic"))
    add_box.append(Gtk.Label(label="Add remap"))
    add.set_child(add_box)
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
                                      subtitle="Add one to change what a key or shortcut does"))
        for text in remaps:
            src, _, dst = text.partition("->")
            row = Adw.ActionRow()
            mapping = Gtk.Box(spacing=10, valign=Gtk.Align.CENTER, margin_top=6, margin_bottom=6)
            mapping.append(keycaps(src.strip()))
            mapping.append(Gtk.Image(icon_name="go-next-symbolic", css_classes=["dim-label"]))
            mapping.append(keycaps(dst.strip()))
            row.add_prefix(mapping)
            delete = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Remove",
                                css_classes=["flat", "circular"], valign=Gtk.Align.CENTER)
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


def awake_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    mid = AwakeModule.id
    status = Adw.ActionRow(title="Status")

    def refresh():
        minutes.set_sensitive(store.get(mid, "mode") == "timed")
        status.set_subtitle(awake_status(store))

    def on_toggle(on: bool):
        set_awake(store, on)
        refresh()

    # Settings stay usable while off, so a timer can be set up before switching on.
    page = ModulePage(store, AwakeModule, on_toggle=on_toggle, dim_when_off=False)
    state = Adw.PreferencesGroup()
    state.add(status)
    page.add(state)

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

    def on_mode(row, _pspec):
        store.set(mid, "mode", modes[row.get_selected()])
        restart_awake_timer(store)
        refresh()

    def on_minutes(row, _pspec):
        store.set(mid, "minutes", int(row.get_value()))
        restart_awake_timer(store)
        refresh()

    mode.connect("notify::selected", on_mode)
    minutes.connect("notify::value", on_minutes)
    refresh()
    return page


def colorpicker_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    mid = ColorPickerModule.id
    page = ModulePage(store, ColorPickerModule)
    group = Adw.PreferencesGroup(title="Picking")
    group.add(shortcut_row(store, mid, "hotkey", "Shortcut"))
    group.add(choice_row(store, mid, "format", "Copy as", "Copied automatically after picking",
                         [("hex", "HEX  #1E90FF"), ("rgb", "RGB  rgb(30, 144, 255)"),
                          ("hsl", "HSL  hsl(210, 100%, 56%)")]))
    page.add(group)
    try_it = Adw.PreferencesGroup()
    try_it.add(button_row("Try it now", "Pick a colour", lambda: launch.knobu("pick-color"),
                          "Opens the picker without the shortcut"))
    page.add(try_it)
    return page


def tesseract_languages() -> list[str]:
    if not shutil.which("tesseract"):
        return []
    out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout
    return [line.strip() for line in out.splitlines()[1:] if line.strip() and line.strip() != "osd"]


def textextractor_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    mid = TextExtractorModule.id
    languages = tesseract_languages()
    notices = [] if languages else [notice(
        "Text recognition isn't installed",
        "Text Extractor uses Tesseract to read text. Install it with:", INSTALL_TESSERACT)]
    page = ModulePage(store, TextExtractorModule, notices=notices)

    group = Adw.PreferencesGroup(title="Extracting")
    group.add(shortcut_row(store, mid, "hotkey", "Shortcut"))
    if languages:
        group.add(choice_row(store, mid, "language", "Language",
                             "More with: sudo apt install tesseract-ocr-<language code>",
                             [(lang, lang) for lang in languages]))
    page.add(group)
    try_it = Adw.PreferencesGroup()
    try_it.add(button_row("Try it now", "Select an area", lambda: launch.knobu("extract-text"),
                          "Opens the selection without the shortcut"))
    page.add(try_it)
    return page


# ---------------------------------------------------------------------- General

def general_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    page = Adw.PreferencesPage()
    for n in input_notice():
        page.add(n)

    hero = Gtk.Box(spacing=18, css_classes=["hero"])
    hero.append(tile("knobu-general-symbolic", "large"))
    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER,
                   hexpand=True)
    text.append(Gtk.Label(label="General", xalign=0, css_classes=["title-2"]))
    text.append(Gtk.Label(label="Knobu runs quietly in the background so gestures, shortcuts "
                                "and remaps work everywhere.", xalign=0, wrap=True,
                          css_classes=["dim-label", "hero-subtitle"]))
    hero.append(text)
    header = Adw.PreferencesGroup()
    header.add(hero)
    page.add(header)

    group = Adw.PreferencesGroup(title="Background service")
    status = Adw.ActionRow(title="Status")
    status.add_suffix(service_status())
    autostart = Adw.SwitchRow(title="Start at login",
                              subtitle="Start Knobu automatically when you log in")
    autostart.set_active(service.is_enabled())
    autostart.connect("notify::active", lambda row, _p: service.set_autostart(row.get_active()))
    group.add(status)
    group.add(autostart)
    page.add(group)

    about = Adw.PreferencesGroup(title="About")
    about.add(button_row("Knobu", "About", lambda: page.activate_action("app.about", None),
                         "Version, credits and license"))
    page.add(about)
    return page


def clipboard_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    mid = ClipboardModule.id
    page = ModulePage(store, ClipboardModule)
    from knobu.modules.clipboard import ClipboardStorage
    storage = ClipboardStorage()

    # 1. Overview & Statistics Group
    stats_group = Adw.PreferencesGroup(title="Status and Storage")
    stats = storage.get_stats()
    status_row = Adw.ActionRow(use_markup=False, title="Clipboard database")
    status_row.set_subtitle(f"{stats['total']} clips saved ({stats['pinned']} pinned, {stats['images']} images)")

    clear_btn = Gtk.Button(label="Clear History", valign=Gtk.Align.CENTER, css_classes=["pill"])
    def on_clear():
        storage.clear_all()
        s = storage.get_stats()
        status_row.set_subtitle(f"{s['total']} clips saved ({s['pinned']} pinned, {s['images']} images)")
    clear_btn.connect("clicked", lambda _b: on_clear())
    status_row.add_suffix(clear_btn)
    stats_group.add(status_row)
    page.add(stats_group)

    # 2. Capacity & History Limit Group
    capacity_group = Adw.PreferencesGroup(title="History Capacity")
    capacity_group.add(spin_row(store, mid, "max_items", "History limit",
                                "Maximum number of clipboard clips maintained before older ones are pruned",
                                10, 500, 10))
    page.add(capacity_group)

    # 3. Content Types Group
    content_group = Adw.PreferencesGroup(title="Allowed Content Types")
    content_group.add(switch_row(store, mid, "store_text", "Store text clips",
                                 "Save copied text, code snippets, and URLs"))
    content_group.add(switch_row(store, mid, "store_images", "Store image clips",
                                 "Save copied screenshots, graphics, and images as visual clips"))
    page.add(content_group)

    # 4. Sanitization & Privacy Group
    sanit_group = Adw.PreferencesGroup(title="Sanitization and Privacy")
    sanit_group.add(switch_row(store, mid, "clean_urls", "Clean tracking URLs",
                               "Strip tracking parameters (utm_source, fbclid, gclid, etc.) when copying links"))
    sanit_group.add(switch_row(store, mid, "strip_whitespace", "Strip trailing whitespace",
                               "Trim excessive trailing whitespace and blank lines from copied text"))
    sanit_group.add(switch_row(store, mid, "ignore_passwords", "Ignore password manager copies",
                               "Skip storing sensitive passwords and credentials marked by password managers"))
    page.add(sanit_group)

    # 5. Shortcuts Group
    shortcuts_group = Adw.PreferencesGroup(title="Shortcuts")
    shortcuts_group.add(shortcut_row(store, mid, "hotkey", "Clipboard History",
                                     "Open the searchable history palette (default Super+V)"))
    shortcuts_group.add(shortcut_row(store, mid, "plain_hotkey", "Paste as Plain Text",
                                     "Optional shortcut to strip rich formatting and paste immediately"))
    shortcuts_group.add(switch_row(store, mid, "exclusive", "Exclusive shortcut grab",
                                   "Swallow shortcut so focused applications never receive Super+V"))
    page.add(shortcuts_group)

    # 6. Test Group
    try_it = Adw.PreferencesGroup(title="Actions")
    try_it.add(button_row("Try it now", "Open Clipboard History", lambda: launch.knobu("clipboard"),
                          "Opens the history popup palette directly"))
    page.add(try_it)

    return page


# (id, title, icon, builder, section). Add new module pages here.
PAGES = [
    ("dashboard", "Dashboard", "knobu-dashboard-symbolic", dashboard_page, "top"),
    (TouchpadModule.id, TouchpadModule.name, TouchpadModule.icon, touchpad_page, "modules"),
    (KeyboardModule.id, KeyboardModule.name, KeyboardModule.icon, keyboard_page, "modules"),
    (AwakeModule.id, AwakeModule.name, AwakeModule.icon, awake_page, "modules"),
    (ClipboardModule.id, ClipboardModule.name, ClipboardModule.icon, clipboard_page, "modules"),
    (ColorPickerModule.id, ColorPickerModule.name, ColorPickerModule.icon, colorpicker_page,
     "modules"),
    (TextExtractorModule.id, TextExtractorModule.name, TextExtractorModule.icon,
     textextractor_page, "modules"),
    ("general", "General", "knobu-general-symbolic", general_page, "bottom"),
]
