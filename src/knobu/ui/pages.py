"""Pages of the settings window: Dashboard, one page per module, and General.

Each builder takes (store, navigate) and returns a widget; `navigate(page_id)` opens
another page.
"""

from pathlib import Path
import shutil
import subprocess
import threading
import time

from gi.repository import Adw, Gio, GLib, Gtk

from knobu import modules, service
from knobu.modules.automation import (
    ACTION_TYPES,
    CONDITION_TYPES,
    TRIGGER_TYPES,
    AutomationAction,
    AutomationModule,
    AutomationRule,
    load_history,
    load_rules,
    run_rule_now,
    save_rules,
)
from knobu.modules.awake import AwakeModule
from knobu.modules.clipboard import ClipboardModule
from knobu.modules.commandbar import (
    CommandBarModule,
    check_conflicts,
    override_os_shortcuts,
    restore_os_shortcuts,
)
from knobu.modules.hotkey_tools import ColorPickerModule, TextExtractorModule
from knobu.modules.keyboard import KeyboardModule
from knobu.modules.mouse import MouseModule
from knobu.modules.notifications import NotificationsModule
from knobu.modules.powertools import PowerToolsModule
from knobu.modules.sound import (
    SoundSuiteModule,
    cycle_output_sink,
    get_mic_status,
    list_audio_state,
    set_default_sink,
    set_stream_volume,
    toggle_mic_mute,
    toggle_stream_mute,
)
from knobu.modules.sysmon import SystemMonitorModule, collect_metrics
from knobu.modules.touchpad import GESTURE_ACTIONS, TAP_ACTIONS, TouchpadModule
from knobu.modules.windows import ZONE_PRESETS, WindowModule, maximize_active_window, toggle_always_on_top
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


def float_spin_row(store: SettingsStore, module_id: str, key: str, title: str, subtitle: str,
                   lower: float, upper: float, step: float = 0.1, digits: int = 1) -> Adw.SpinRow:
    row = Adw.SpinRow.new_with_range(lower, upper, step)
    row.set_use_markup(False)
    row.set_digits(digits)
    row.set_title(title)
    row.set_subtitle(subtitle)
    row.set_value(float(store.get(module_id, key)))
    row.connect("notify::value", lambda r, _: store.set(module_id, key, round(float(r.get_value()), digits)))
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
        return text("3 and 4-finger swipes · volume, media and multitasking")
    if module_id == KeyboardModule.id:
        n = len(store.get(module_id, "remaps", []))
        return text(f"{n} remap{'s' if n != 1 else ''}" if n else "Remaps, snippets and protection")
    if module_id == MouseModule.id:
        return text("Smooth scrolling and debounce filter")
    if module_id == CommandBarModule.id:
        hotkey = store.get(module_id, "hotkey", "alt+space")
        return keycaps(hotkey) if hotkey else text("Alt+Space")
    if module_id == AwakeModule.id:
        return text(awake_status(store))
    if module_id == NotificationsModule.id:
        return text("Top tray IP and AWS status · Mac-style notifications")
    if module_id in (ClipboardModule.id, PowerToolsModule.id, ColorPickerModule.id, TextExtractorModule.id):
        hotkey = store.get(module_id, "hotkey", "")
        return keycaps(hotkey) if hotkey else text("")
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

    bp_group = Adw.PreferencesGroup(
        title="Gaming and Passthrough",
        description="Temporarily pass raw touchpad events directly without gesture interception.",
    )
    bp_group.add(switch_row(store, mid, "bypass", "Bypass Touchpad Gestures",
                            "Allow standard touchpad gestures and pointer movement without Knobu actions"))
    bp_group.add(switch_row(store, mid, "grab_gestures", "Prevent OS Double-Trigger",
                            "Claim touchpad exclusively during 3 and 4-finger gestures so GNOME does not simultaneously trigger desktop gestures"))
    page.add(bp_group)

    gesture_opts = list(GESTURE_ACTIONS.items())
    tap_opts = list(TAP_ACTIONS.items())

    # 1. Three-Finger Gestures (Windows Precision style)
    three_group = Adw.PreferencesGroup(
        title="Three-Finger Gestures",
        description="Configure actions for 3-finger swipes and taps.",
    )
    three_group.add(choice_row(store, mid, "swipe3_up", "Swipe Up", "Action for 3-finger swipe up", gesture_opts))
    three_group.add(choice_row(store, mid, "swipe3_down", "Swipe Down", "Action for 3-finger swipe down", gesture_opts))
    three_group.add(choice_row(store, mid, "swipe3_left", "Swipe Left", "Action for 3-finger swipe left", gesture_opts))
    three_group.add(choice_row(store, mid, "swipe3_right", "Swipe Right", "Action for 3-finger swipe right", gesture_opts))
    three_group.add(choice_row(store, mid, "tap3_action", "Tap Action", "Action for 3-finger tap", tap_opts))
    page.add(three_group)

    # 2. Four-Finger Gestures (Windows Precision style)
    four_group = Adw.PreferencesGroup(
        title="Four-Finger Gestures",
        description="Configure actions for 4-finger swipes and taps.",
    )
    four_group.add(choice_row(store, mid, "swipe4_up", "Swipe Up", "Action for 4-finger swipe up", gesture_opts))
    four_group.add(choice_row(store, mid, "swipe4_down", "Swipe Down", "Action for 4-finger swipe down", gesture_opts))
    four_group.add(choice_row(store, mid, "swipe4_left", "Swipe Left", "Action for 4-finger swipe left", gesture_opts))
    four_group.add(choice_row(store, mid, "swipe4_right", "Swipe Right", "Action for 4-finger swipe right", gesture_opts))
    four_group.add(choice_row(store, mid, "tap4_action", "Tap Action", "Action for 4-finger tap", tap_opts))
    page.add(four_group)

    # 3. Audio & Sensitivity
    volume = Adw.PreferencesGroup(title="Volume Slide Sensitivity", description="Settings for continuous volume sliding.")
    volume.add(spin_row(store, mid, "percent_per_cm", "Speed",
                        "Volume change (%) per centimetre of vertical movement", 5, 50))
    volume.add(switch_row(store, mid, "invert", "Reverse direction", "Slide down to increase volume"))
    volume.add(choice_row(
        store, mid, "max_volume", "Maximum volume", "Above 100% amplifies and may distort",
        [("system", f"Same as system ({system_max_volume()}%)"),
         (100, "100%"), (125, "125%"), (150, "150%")]))
    volume.add(switch_row(store, mid, "osd", "Show volume pop-up",
                          "Uses your desktop on-screen volume indicator (GNOME and KDE Plasma)"))
    page.add(volume)

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

    bp_group = Adw.PreferencesGroup(
        title="Gaming and Passthrough",
        description="Temporarily disable keyboard remaps, snippets, and quit protection without stopping other tools.",
    )
    bp_group.add(switch_row(store, mid, "bypass", "Bypass Keyboard Customizations",
                            "Allow raw physical keystrokes to pass directly to applications"))
    page.add(bp_group)

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

    # 2. Text Snippets Expansion
    snip_group = Adw.PreferencesGroup(
        title="Text Snippets Expansion",
        description="Auto-expand abbreviations into full text as you type (e.g. ;email -> me@example.com, ;date -> {date}).",
    )
    snip_group.add(switch_row(store, mid, "enable_snippets", "Enable Text Snippets",
                              "Expand snippet triggers dynamically while typing"))

    snip_add_row = Adw.EntryRow(title="Add Snippet (trigger -> replacement)")
    add_snip_btn = Gtk.Button(icon_name="list-add-symbolic", valign=Gtk.Align.CENTER,
                              css_classes=["flat", "circular"], tooltip_text="Add snippet")
    snip_add_row.add_suffix(add_snip_btn)
    snip_group.add(snip_add_row)

    snip_rows: list[Gtk.Widget] = []

    def rebuild_snippets():
        for r in snip_rows:
            snip_group.remove(r)
        snip_rows.clear()
        snippets = store.get(mid, "snippets")
        if not snippets:
            row = Adw.ActionRow(title="No snippets defined",
                                subtitle="Type a snippet above like ';email -> you@domain.com'")
            snip_rows.append(row)
            snip_group.add(row)
            return

        for item in snippets:
            trig, _, rep = item.partition("->")
            row = Adw.ActionRow(title=trig.strip(), subtitle=rep.strip())
            del_btn = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Remove",
                                 css_classes=["flat", "circular"], valign=Gtk.Align.CENTER)
            del_btn.connect("clicked", lambda _b, s=item: remove_snippet(s))
            row.add_suffix(del_btn)
            snip_rows.append(row)
            snip_group.add(row)

    def remove_snippet(item: str):
        store.set(mid, "snippets", [s for s in store.get(mid, "snippets") if s != item])
        rebuild_snippets()

    def on_add_snippet(_w):
        text = snip_add_row.get_text().strip()
        if "->" in text:
            existing = store.get(mid, "snippets")
            trig, _, _ = text.partition("->")
            filtered = [s for s in existing if not s.startswith(trig.strip() + " ->")]
            store.set(mid, "snippets", filtered + [text])
            snip_add_row.set_text("")
            rebuild_snippets()

    add_snip_btn.connect("clicked", on_add_snippet)
    snip_add_row.connect("entry-activated", on_add_snippet)
    rebuild_snippets()
    page.add(snip_group)

    # 3. Quit & Close Protection
    quit_group = Adw.PreferencesGroup(
        title="Quit and Close Protection",
        description="Prevent accidental loss of work from Ctrl+Q or Ctrl+W.",
    )
    quit_group.add(switch_row(store, mid, "quit_protection", "Enable Quit and Close Protection",
                              "Require hold or double-press before closing applications or windows"))
    quit_group.add(choice_row(store, mid, "quit_protection_mode", "Confirmation Mode",
                              "How to verify you intended to quit or close",
                              [("hold", "Hold shortcut (e.g. 0.5s)"), ("double_press", "Double-press shortcut")]))
    quit_group.add(float_spin_row(store, mid, "quit_protection_delay", "Hold / Window Duration (seconds)",
                                  "Duration to hold or time window for double-press", 0.2, 2.0, 0.1, 1))
    page.add(quit_group)

    # 4. Key Chatter Filter
    deb_group = Adw.PreferencesGroup(
        title="Key Chatter Filter",
        description="Debounce keys to prevent multiple characters from failing switches.",
    )
    deb_group.add(switch_row(store, mid, "key_debounce", "Enable Key Debounce Filter",
                             "Drop mechanical contact chatter within the debounce threshold"))
    deb_group.add(spin_row(store, mid, "key_debounce_ms", "Debounce Threshold (ms)",
                           "Releases and re-presses faster than this window are suppressed", 10, 100, 5))
    page.add(deb_group)

    return page


def mouse_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    mid = MouseModule.id
    notices = input_notice()
    if not permissions.can_write_uinput():
        notices.append(notice(
            "One-time setup needed",
            "Mouse utilities need permission to create a virtual pointing device. Run this in a terminal:",
            permissions.FIX_UINPUT))
    page = ModulePage(store, MouseModule, notices=notices)

    bp_group = Adw.PreferencesGroup(
        title="Gaming and Passthrough",
        description="Temporarily pass raw mouse wheel and button events directly without modification.",
    )
    bp_group.add(switch_row(store, mid, "bypass", "Bypass Mouse Customizations",
                            "Allow physical mouse input to pass directly to applications"))
    page.add(bp_group)

    # 1. Smooth & Independent Scrolling
    scroll_group = Adw.PreferencesGroup(
        title="Smooth and Independent Scrolling",
        description="Configure mouse wheel scrolling independently of touchpad desktop settings.",
    )
    scroll_group.add(switch_row(store, mid, "invert_wheel", "Invert Mouse Wheel Direction",
                                "Reverse vertical mouse wheel scroll direction independently of the touchpad"))
    scroll_group.add(switch_row(store, mid, "invert_hwheel", "Invert Horizontal Scroll",
                                "Reverse horizontal tilt wheel direction"))
    scroll_group.add(float_spin_row(store, mid, "scroll_multiplier", "Scroll Speed Multiplier",
                                    "Adjust mouse wheel speed multiplier (1.0 = standard speed)", 0.25, 5.0, 0.25, 2))
    page.add(scroll_group)

    # 2. Hardware Debounce Filter
    deb_group = Adw.PreferencesGroup(
        title="Hardware Debounce Filter",
        description="Filter accidental double-clicks caused by worn mouse microswitches.",
    )
    deb_group.add(switch_row(store, mid, "mouse_debounce", "Enable Mouse Debounce Filter",
                             "Suppress spurious click bounces within the debounce threshold"))
    deb_group.add(spin_row(store, mid, "mouse_debounce_ms", "Debounce Threshold (ms)",
                           "Clicks released and re-pressed faster than this window are suppressed", 10, 150, 5))
    page.add(deb_group)

    # 3. Pointer Locator (Find My Mouse)
    ptr_group = Adw.PreferencesGroup(
        title="Pointer Locator (Find My Mouse)",
        description="Locate your cursor instantly with GNOME Ctrl ring or a fullscreen spotlight.",
    )
    ptr_group.add(switch_row(store, mid, "find_my_mouse", "Enable Find My Mouse",
                             "Syncs GNOME Ctrl cursor-locator ring and enables mouse-shake spotlight"))
    ptr_group.add(switch_row(store, mid, "mouse_shake_trigger", "Trigger Spotlight on Shake",
                             "Rapidly shake the mouse side-to-side to launch Find My Mouse spotlight"))
    ptr_group.add(shortcut_row(store, mid, "find_my_mouse_hotkey", "Spotlight Shortcut",
                               "Global shortcut to summon Find My Mouse spotlight"))
    ptr_group.add(button_row("Try it now", "Spotlight Cursor", lambda: launch.knobu("find-mouse"),
                             "Opens the spotlight overlay around your pointer"))
    page.add(ptr_group)

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

    bypass_group = Adw.PreferencesGroup(
        title="Bypass and OS Customization",
        description="Temporarily bypass hardware grabs, input interception, and restore native OS shortcuts.",
    )
    bypass_switch = Adw.SwitchRow(
        title="Master Bypass Mode",
        subtitle="Temporarily suspend all hardware grabs, key remaps, and shortcuts (gaming and raw passthrough)",
    )
    gen_data = store.data.get("general", {})
    bypass_switch.set_active(bool(gen_data.get("bypass", False)))

    def on_bypass_change(sw, _p):
        store.data.setdefault("general", {})["bypass"] = sw.get_active()
        config.save(store.data)
        service.reload()

    bypass_switch.connect("notify::active", on_bypass_change)
    bypass_group.add(bypass_switch)

    from knobu.modules.commandbar.os_shortcuts import restore_os_shortcuts
    restore_row = button_row(
        "Default OS Shortcuts",
        "Restore Original",
        lambda: restore_os_shortcuts(),
        "Restore standard GNOME / KDE window menu and search shortcuts if overridden by Knobu",
    )
    bypass_group.add(restore_row)
    page.add(bypass_group)

    backup_group = Adw.PreferencesGroup(
        title="Configuration Backup & Restore",
        description="Export all module settings, shortcuts, and customizations to JSON or restore from a backup.",
    )
    backup_status = Adw.ActionRow(
        use_markup=False,
        title="Backup & Restore",
        subtitle="Saved to ~/.config/knobu/knobu-backup.json or custom file",
    )

    backup_btn = Gtk.Button(
        icon_name="document-save-symbolic",
        tooltip_text="Export Backup (JSON)",
        valign=Gtk.Align.CENTER,
        css_classes=["flat"],
    )
    restore_btn = Gtk.Button(
        icon_name="document-open-symbolic",
        tooltip_text="Restore from JSON Backup",
        valign=Gtk.Align.CENTER,
        css_classes=["flat"],
    )

    def on_export_backup(_b):
        dlg = Gtk.FileDialog(title="Save Configuration Backup", initial_name="knobu-backup.json")
        parent = page.get_root()
        def cb(d, res):
            try:
                f = d.save_finish(res)
                if f:
                    out = config.export_json(Path(f.get_path()))
                    backup_status.set_subtitle(f"Exported to {out.name}")
            except Exception as err:
                backup_status.set_subtitle(f"Export failed: {err}")
        dlg.save(parent, None, cb)

    def on_import_backup(_b):
        dlg = Gtk.FileDialog(title="Select JSON Backup to Restore")
        parent = page.get_root()
        def cb(d, res):
            try:
                f = d.open_finish(res)
                if f:
                    src = Path(f.get_path())
                    new_data = config.import_json(src)
                    store.data = new_data
                    service.reload()
                    backup_status.set_subtitle(f"Successfully restored from {src.name}")
            except Exception as err:
                backup_status.set_subtitle(f"Restore failed: {err}")
        dlg.open(parent, None, cb)

    backup_btn.connect("clicked", on_export_backup)
    restore_btn.connect("clicked", on_import_backup)
    backup_status.add_suffix(backup_btn)
    backup_status.add_suffix(restore_btn)
    backup_group.add(backup_status)
    page.add(backup_group)

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


def commandbar_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    mid = CommandBarModule.id
    page = ModulePage(store, CommandBarModule)

    # 1. Shortcut and OS Conflict Management
    sc_group = Adw.PreferencesGroup(title="Shortcut and OS Integration")
    sc_group.add(shortcut_row(store, mid, "hotkey", "Command Bar Shortcut",
                              "Global hotkey to summon the launcher (default Alt+Space)"))
    sc_group.add(switch_row(store, mid, "exclusive", "Exclusive Hardware Grab",
                            "Intercept Alt+Space via evdev kernel driver so background apps never see it"))
    sc_group.add(switch_row(store, mid, "override_os_shortcut", "Auto-override OS Shortcut",
                            "Automatically unbind conflicting Alt+Space in GNOME / KDE settings on startup"))

    conflicts = check_conflicts()
    if conflicts:
        conflict_names = ", ".join(c["name"] for c in conflicts)
        sc_group.add(button_row("Conflicting OS Shortcut Detected", "Override Now",
                                lambda: override_os_shortcuts(),
                                f"Alt+Space is currently bound by: {conflict_names}. Click to free it for Knobu."))
    else:
        sc_group.add(button_row("Desktop OS Shortcut Status", "Restore Original",
                                lambda: restore_os_shortcuts(),
                                "No desktop environment conflicts active. Click to restore original OS bindings if needed."))

    page.add(sc_group)

    # 2. Search Providers
    prov_group = Adw.PreferencesGroup(title="Search Providers")
    prov_group.add(switch_row(store, mid, "enable_apps", "Applications",
                              "Search and launch desktop applications (.desktop entries)"))
    prov_group.add(switch_row(store, mid, "enable_calc", "Calculator",
                              "Evaluate math expressions directly (e.g. 25*4, sqrt(144), 15% of 200)"))
    prov_group.add(switch_row(store, mid, "enable_shell", "Terminal Commands",
                              "Run shell commands prefixed with '>' (e.g. > top, > ping 8.8.8.8)"))
    prov_group.add(switch_row(store, mid, "enable_paths", "Files and Paths",
                              "Search and navigate folders and files starting with ~/ or /"))
    prov_group.add(switch_row(store, mid, "enable_web", "Web and URLs",
                              "Open URLs directly or search the web with '? search query'"))
    prov_group.add(switch_row(store, mid, "enable_system", "System Actions",
                              "Quick commands for lock screen, sleep, restart, and Knobu tools"))
    prov_group.add(switch_row(store, mid, "enable_converter", "Unit and Currency Converter",
                              "Convert units and currencies (e.g. 100 USD in EUR, 50 miles in km, 100 C in F)"))
    prov_group.add(switch_row(store, mid, "enable_emoji", "Emoji Picker",
                              "Search and copy emojis prefixed with ':' (e.g. :fire, :rocket, :check)"))
    prov_group.add(switch_row(store, mid, "enable_windows", "Window and Tab Switcher",
                              "Switch to open windows and browser tabs, prefixed with '<' (e.g. < code, < cliq)"))
    page.add(prov_group)

    # 3. Preferences
    disp_group = Adw.PreferencesGroup(title="Display")
    disp_group.add(spin_row(store, mid, "max_results", "Maximum Results",
                            "Number of search results to display simultaneously", 3, 15, 1))
    page.add(disp_group)

    # 4. Actions
    try_it = Adw.PreferencesGroup(title="Actions")
    try_it.add(button_row("Try it now", "Open Command Bar", lambda: launch.knobu("command-bar"),
                          "Launch the floating search bar directly"))
    page.add(try_it)

    return page


def powertools_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    from knobu.modules.powertools import (
        IMAGE_FORMATS,
        IMAGE_RESIZE_PRESETS,
        EnvEntry,
        HostEntry,
        available_package_sources,
        clean_target,
        compress_video,
        convert_images,
        ffmpeg_available,
        find_file_locks,
        format_bytes,
        is_valid_key,
        kill_process,
        list_installed_packages,
        list_listening_ports,
        load_hosts,
        load_profiles,
        resize_images,
        save_hosts,
        save_profiles,
        scan_cleanup_targets,
        system_env_snapshot,
        uninstall_package,
        validate_host_entry,
        video_to_gif,
    )

    mid = PowerToolsModule.id
    notices = input_notice()
    if not ffmpeg_available():
        notices.append(notice(
            "FFmpeg not found",
            "Media Tools require ffmpeg. Install it in a terminal:",
            "sudo apt install ffmpeg",
        ))
    page = ModulePage(store, PowerToolsModule, notices=notices)

    def run_bg(work, on_done) -> None:
        def worker():
            res = work()
            GLib.idle_add(lambda: on_done(res) and False)
        threading.Thread(target=worker, daemon=True).start()

    # 1. Cleaning Mode
    clean_mode = Adw.PreferencesGroup(
        title="Cleaning Mode",
        description="Fullscreen hardware lock overlay so you can wipe your keyboard, touchpad, and screen safely.",
    )
    clean_mode.add(shortcut_row(store, mid, "hotkey", "Cleaning Mode Shortcut",
                                "Global shortcut to trigger Cleaning Mode"))
    clean_mode.add(spin_row(store, mid, "cleaning_duration", "Auto-Unlock Timer (seconds)",
                            "Safety countdown before inputs automatically unlock", 10, 120, 5))
    clean_mode.add(button_row("Hardware Lock", "Start Cleaning Mode",
                              lambda: launch.knobu("cleaning-mode"),
                              "Hold Esc for 2 seconds or wait for countdown to exit"))
    clean_mode.add(shortcut_row(store, mid, "ruler_hotkey", "Screen Ruler Shortcut",
                                "Global shortcut to measure pixel widths, heights, and diagonals"))
    clean_mode.add(button_row("Screen Ruler", "Measure Screen",
                              lambda: launch.knobu("screen-ruler"),
                              "Drag anywhere on screen to measure and copy pixel dimensions"))
    page.add(clean_mode)

    # 2. Port Manager
    port_group = Adw.PreferencesGroup(
        title="Port Manager",
        description="Inspect active listening TCP/UDP ports and terminate stuck processes.",
    )
    port_refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic", css_classes=["flat"],
                                  valign=Gtk.Align.CENTER, tooltip_text="Refresh listening ports")
    port_group.set_header_suffix(port_refresh_btn)

    port_filter = Adw.EntryRow(title="Filter by port or process")
    port_group.add(port_filter)
    port_rows: list[Gtk.Widget] = []

    def refresh_ports(*_args) -> None:
        q = port_filter.get_text().strip().lower()
        for r in port_rows:
            port_group.remove(r)
        port_rows.clear()

        entries = [
            e for e in list_listening_ports()
            if not q or q in str(e.port) or q in e.process.lower() or q in e.proto
        ]
        if not entries:
            empty = Adw.ActionRow(use_markup=False, title="No matching listening ports")
            port_group.add(empty)
            port_rows.append(empty)
            return

        for entry in entries[:40]:
            pid_txt = f"PID {entry.pid}" if entry.pid else "system"
            row = Adw.ActionRow(
                use_markup=False,
                title=f"{entry.proto.upper()} :{entry.port} — {entry.process}",
                subtitle=f"{entry.address} ({pid_txt})",
            )
            if entry.pid is not None:
                kill_btn = Gtk.Button(label="Kill", valign=Gtk.Align.CENTER,
                                      css_classes=["pill", "destructive-action"])
                def on_kill(_b, pid=entry.pid, r=row):
                    _b.set_sensitive(False)
                    run_bg(lambda: kill_process(pid), lambda res: (r.set_subtitle(res[1]), refresh_ports()))
                kill_btn.connect("clicked", on_kill)
                row.add_suffix(kill_btn)
            port_group.add(row)
            port_rows.append(row)

    port_refresh_btn.connect("clicked", refresh_ports)
    port_filter.connect("changed", refresh_ports)
    refresh_ports()
    page.add(port_group)

    # 3. Cleaner & Uninstaller
    cleaner_group = Adw.PreferencesGroup(
        title="System Cleaner",
        description="Safely reclaim space from user caches, thumbnails, crash reports, and APT residue.",
    )
    cleaner_status = Adw.ActionRow(use_markup=False, title="Cleanup Status", subtitle="Ready")
    target_rows: dict[str, Adw.ActionRow] = {}

    def refresh_cleaner_sizes() -> None:
        for t in scan_cleanup_targets():
            row = target_rows.get(t.id)
            if row is not None:
                admin_note = " (admin)" if t.requires_admin else ""
                row.set_subtitle(f"{t.description} · {format_bytes(t.size_bytes)}{admin_note}")

    for t in scan_cleanup_targets():
        admin_note = " (admin)" if t.requires_admin else ""
        t_row = Adw.ActionRow(
            use_markup=False,
            title=t.name,
            subtitle=f"{t.description} · {format_bytes(t.size_bytes)}{admin_note}",
        )
        c_btn = Gtk.Button(label="Clean", valign=Gtk.Align.CENTER, css_classes=["pill"])
        def on_clean(btn, tid=t.id):
            btn.set_sensitive(False)
            cleaner_status.set_subtitle(f"Cleaning {tid}...")
            def done(res):
                _ok, msg, _freed = res
                cleaner_status.set_subtitle(msg)
                refresh_cleaner_sizes()
                btn.set_sensitive(True)
            run_bg(lambda: clean_target(tid), done)
        c_btn.connect("clicked", on_clean)
        t_row.add_suffix(c_btn)
        target_rows[t.id] = t_row
        cleaner_group.add(t_row)

    cleaner_group.add(cleaner_status)
    page.add(cleaner_group)

    sources = available_package_sources()
    pkg_group = Adw.PreferencesGroup(
        title="Package Uninstaller",
        description=f"Detected sources: {', '.join(s.upper() for s in sources) or 'none'}",
    )
    src_choices = [("all", "All Sources")] + [(s, s.upper()) for s in sources]
    src_row = Adw.ComboRow(use_markup=False, title="Package Source",
                           model=Gtk.StringList.new([lbl for _, lbl in src_choices]))
    pkg_group.add(src_row)
    pkg_search = Adw.EntryRow(title="Search installed packages")
    pkg_group.add(pkg_search)
    pkg_rows: list[Gtk.Widget] = []

    def refresh_packages(*_args) -> None:
        q = pkg_search.get_text()
        sel_src = src_choices[src_row.get_selected()][0]
        for r in pkg_rows:
            pkg_group.remove(r)
        pkg_rows.clear()
        pkgs = list_installed_packages(q, source=sel_src, limit=20)
        if not pkgs:
            empty = Adw.ActionRow(use_markup=False, title="No matching packages found")
            pkg_group.add(empty)
            pkg_rows.append(empty)
            return
        for pkg in pkgs:
            meta = f"{pkg.size_kb / 1024:.1f} MB" if pkg.size_kb else (pkg.version or pkg.source)
            p_row = Adw.ActionRow(
                use_markup=False,
                title=f"[{pkg.source.upper()}] {pkg.name} ({meta})",
                subtitle=pkg.summary or f"Installed via {pkg.source}",
            )
            rm_btn = Gtk.Button(label="Uninstall", valign=Gtk.Align.CENTER,
                                css_classes=["pill", "destructive-action"])
            def on_remove(btn, name=pkg.name, src=pkg.source, r=p_row):
                btn.set_sensitive(False)
                r.set_subtitle(f"Uninstalling {name} ({src})...")
                run_bg(lambda: uninstall_package(name, src), lambda res: (r.set_subtitle(res[1]), refresh_packages()))
            rm_btn.connect("clicked", on_remove)
            p_row.add_suffix(rm_btn)
            pkg_group.add(p_row)
            pkg_rows.append(p_row)

    src_row.connect("notify::selected", refresh_packages)
    pkg_search.connect("entry-activated", refresh_packages)
    pkg_search_btn = Gtk.Button(icon_name="system-search-symbolic", css_classes=["flat"],
                                valign=Gtk.Align.CENTER, tooltip_text="Search packages")
    pkg_search_btn.connect("clicked", refresh_packages)
    pkg_group.set_header_suffix(pkg_search_btn)
    refresh_packages()
    page.add(pkg_group)

    # 4. Media Tools (FFmpeg)
    media_group = Adw.PreferencesGroup(
        title="Media Tools",
        description="Local video compression, GIF creation, and batch image conversion via FFmpeg.",
    )
    media_status = Adw.ActionRow(use_markup=False, title="Task Output", subtitle="Select files below to process")

    crf_presets = [(24, "Balanced (CRF 24)"), (20, "High Quality (CRF 20)"), (28, "Small File (CRF 28)")]
    crf_row = Adw.ComboRow(use_markup=False, title="Video Compression Quality",
                           model=Gtk.StringList.new([lbl for _, lbl in crf_presets]))
    media_group.add(crf_row)

    def pick_single(title: str, on_file) -> None:
        dlg = Gtk.FileDialog(title=title)
        parent = page.get_root()
        def cb(d, res):
            try:
                f = d.open_finish(res)
                if f and f.get_path():
                    on_file(Path(f.get_path()))
            except GLib.Error:
                pass
        dlg.open(parent if isinstance(parent, Gtk.Window) else None, None, cb)

    def pick_multiple(title: str, on_files) -> None:
        dlg = Gtk.FileDialog(title=title)
        parent = page.get_root()
        def cb(d, res):
            try:
                model = d.open_multiple_finish(res)
                paths = [Path(model.get_item(i).get_path()) for i in range(model.get_n_items()) if model.get_item(i).get_path()]
                if paths:
                    on_files(paths)
            except GLib.Error:
                pass
        dlg.open_multiple(parent if isinstance(parent, Gtk.Window) else None, None, cb)

    def on_compress_video() -> None:
        crf = crf_presets[crf_row.get_selected()][0]
        def start(path: Path):
            media_status.set_subtitle(f"Compressing {path.name}...")
            run_bg(lambda: compress_video(path, crf=crf),
                   lambda res: media_status.set_subtitle(res[1]))
        pick_single("Select Video to Compress", start)

    def on_make_gif() -> None:
        def start(path: Path):
            media_status.set_subtitle(f"Creating GIF from {path.name}...")
            run_bg(lambda: video_to_gif(path),
                   lambda res: media_status.set_subtitle(res[1]))
        pick_single("Select Video for GIF", start)

    fmt_row = Adw.ComboRow(use_markup=False, title="Target Image Format",
                           model=Gtk.StringList.new([f.upper() for f in IMAGE_FORMATS]))

    def on_convert_images() -> None:
        fmt = IMAGE_FORMATS[fmt_row.get_selected()]
        def start(paths: list[Path]):
            media_status.set_subtitle(f"Converting {len(paths)} image(s) to {fmt.upper()}...")
            run_bg(lambda: convert_images(paths, fmt),
                   lambda res: media_status.set_subtitle(res[1]))
        pick_multiple("Select Images to Convert", start)

    resize_row = Adw.ComboRow(use_markup=False, title="Image Resize Preset",
                              model=Gtk.StringList.new([lbl for _, lbl, _ in IMAGE_RESIZE_PRESETS]))

    def on_resize_images() -> None:
        preset = IMAGE_RESIZE_PRESETS[resize_row.get_selected()][0]
        def start(paths: list[Path]):
            media_status.set_subtitle(f"Resizing {len(paths)} image(s) ({preset})...")
            run_bg(lambda: resize_images(paths, preset=preset),
                   lambda res: media_status.set_subtitle(res[1]))
        pick_multiple("Select Images to Resize", start)

    media_group.add(button_row("Compress Video", "Choose Video", on_compress_video,
                               "Re-encodes to fast-start H.264/AAC MP4 beside source file"))
    media_group.add(button_row("Video to GIF", "Choose Video", on_make_gif,
                               "Two-pass Lanczos palette GIF beside source file"))
    media_group.add(fmt_row)
    media_group.add(button_row("Batch Convert Images", "Choose Images", on_convert_images,
                               "Convert multiple PNG/JPG/WebP/AVIF files at once"))
    media_group.add(resize_row)
    media_group.add(button_row("Batch Resize Images", "Choose Images", on_resize_images,
                               "Scale batches of images to preset dimensions"))
    media_group.add(media_status)
    page.add(media_group)

    # 5. Environment Variables Manager
    env_active, env_profiles = load_profiles()
    env_group = Adw.PreferencesGroup(
        title="Environment Variables",
        description="Manage ~/.config/environment.d/90-knobu.conf with live systemd user session sync.",
    )
    env_status = Adw.ActionRow(use_markup=False, title="Active Profile", subtitle=f"Profile: {env_active}")
    env_key_in = Adw.EntryRow(title="Variable Name (e.g. JAVA_HOME or PATH)")
    env_val_in = Adw.EntryRow(title="Value")
    env_add_btn = Gtk.Button(label="Add / Update", valign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"])
    env_val_in.add_suffix(env_add_btn)
    env_sync_btn = Gtk.Button(label="Save and Sync", valign=Gtk.Align.CENTER, css_classes=["pill"])
    env_status.add_suffix(env_sync_btn)
    env_group.add(env_status)
    env_group.add(env_key_in)
    env_group.add(env_val_in)
    env_rows: list[Gtk.Widget] = []

    def rebuild_env() -> None:
        for r in env_rows:
            env_group.remove(r)
        env_rows.clear()
        entries = env_profiles.get(env_active, [])
        if not entries:
            empty = Adw.ActionRow(use_markup=False, title="No custom user variables configured")
            env_group.add(empty)
            env_rows.append(empty)
        else:
            for item in entries:
                r = Adw.SwitchRow(use_markup=False, title=item.key, subtitle=item.value)
                r.set_active(item.enabled)
                def on_tgl(sw, _p, entry=item):
                    entry.enabled = sw.get_active()
                r.connect("notify::active", on_tgl)
                del_btn = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                                     css_classes=["flat", "circular"], tooltip_text="Remove variable")
                def on_del(_b, entry=item):
                    env_profiles[env_active].remove(entry)
                    rebuild_env()
                del_btn.connect("clicked", on_del)
                r.add_suffix(del_btn)
                env_group.add(r)
                env_rows.append(r)

        sys_exp = Adw.ExpanderRow(use_markup=False, title="Inherited Session Variables (Read-only)")
        for sk, sv in system_env_snapshot()[:20]:
            sys_exp.add_row(Adw.ActionRow(use_markup=False, title=sk, subtitle=sv))
        env_group.add(sys_exp)
        env_rows.append(sys_exp)

    def on_add_env(*_args) -> None:
        k = env_key_in.get_text().strip()
        v = env_val_in.get_text().strip()
        if not is_valid_key(k):
            env_status.set_subtitle(f"Invalid variable name: {k!r}")
            return
        lst = env_profiles.setdefault(env_active, [])
        for existing in lst:
            if existing.key == k:
                existing.value = v
                existing.enabled = True
                break
        else:
            lst.append(EnvEntry(key=k, value=v, enabled=True))
        env_key_in.set_text("")
        env_val_in.set_text("")
        rebuild_env()

    def on_sync_env(_b) -> None:
        env_status.set_subtitle("Syncing environment...")
        run_bg(lambda: save_profiles(env_active, env_profiles, apply_live=True),
               lambda res: env_status.set_subtitle(res[1]))

    env_add_btn.connect("clicked", on_add_env)
    env_sync_btn.connect("clicked", on_sync_env)
    rebuild_env()
    page.add(env_group)

    # 6. Hosts File Editor
    host_entries, host_preserved = load_hosts()
    hosts_group = Adw.PreferencesGroup(
        title="Hosts File Editor",
        description="Toggle or add /etc/hosts entries safely with automatic backup.",
    )
    hosts_status = Adw.ActionRow(use_markup=False, title="/etc/hosts", subtitle=f"{len(host_entries)} entries loaded")
    hosts_save_btn = Gtk.Button(label="Save /etc/hosts", valign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"])
    hosts_status.add_suffix(hosts_save_btn)
    hosts_group.add(hosts_status)

    h_ip_in = Adw.EntryRow(title="IP Address (e.g. 127.0.0.1)")
    h_name_in = Adw.EntryRow(title="Hostname(s) (e.g. api.local)")
    h_add_btn = Gtk.Button(label="Add", valign=Gtk.Align.CENTER, css_classes=["pill"])
    h_name_in.add_suffix(h_add_btn)
    hosts_group.add(h_ip_in)
    hosts_group.add(h_name_in)
    host_rows: list[Gtk.Widget] = []

    def rebuild_hosts() -> None:
        for r in host_rows:
            hosts_group.remove(r)
        host_rows.clear()
        for entry in host_entries[:25]:
            sub = f"{' '.join(entry.hosts)}{(' · #' + entry.comment) if entry.comment else ''}"
            r = Adw.SwitchRow(use_markup=False, title=entry.ip, subtitle=sub)
            r.set_active(entry.enabled)
            def on_h_tgl(sw, _p, ent=entry):
                ent.enabled = sw.get_active()
            r.connect("notify::active", on_h_tgl)
            del_b = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                               css_classes=["flat", "circular"], tooltip_text="Delete host entry")
            def on_h_del(_b, ent=entry):
                host_entries.remove(ent)
                rebuild_hosts()
            del_b.connect("clicked", on_h_del)
            r.add_suffix(del_b)
            hosts_group.add(r)
            host_rows.append(r)

    def on_add_host(*_args) -> None:
        ip = h_ip_in.get_text().strip()
        names = h_name_in.get_text().split()
        err = validate_host_entry(ip, names)
        if err:
            hosts_status.set_subtitle(err)
            return
        host_entries.append(HostEntry(ip=ip, hosts=names, comment="knobu", enabled=True))
        h_ip_in.set_text("")
        h_name_in.set_text("")
        rebuild_hosts()

    def on_save_hosts(_b) -> None:
        hosts_status.set_subtitle("Saving /etc/hosts...")
        run_bg(lambda: save_hosts(host_entries, host_preserved),
               lambda res: hosts_status.set_subtitle(res[1]))

    h_add_btn.connect("clicked", on_add_host)
    hosts_save_btn.connect("clicked", on_save_hosts)
    rebuild_hosts()
    page.add(hosts_group)

    # 7. File Locksmith
    lock_group = Adw.PreferencesGroup(
        title="File Locksmith",
        description="Find processes holding open handles on a file and terminate them safely.",
    )
    lock_status = Adw.ActionRow(use_markup=False, title="Target File", subtitle="Choose a file to inspect open locks")
    lock_rows: list[Gtk.Widget] = []

    def inspect_locks(target: Path) -> None:
        for r in lock_rows:
            lock_group.remove(r)
        lock_rows.clear()
        lock_status.set_subtitle(str(target))
        locks = find_file_locks(target)
        if not locks:
            empty = Adw.ActionRow(use_markup=False, title="No locking processes found",
                                  subtitle="No readable processes hold an open file descriptor to this target")
            lock_group.add(empty)
            lock_rows.append(empty)
            return
        for lk in locks[:20]:
            r = Adw.ActionRow(use_markup=False, title=f"{lk.process} (PID {lk.pid})",
                              subtitle=f"fd {lk.fd} · {lk.path}")
            k_btn = Gtk.Button(label="Kill", valign=Gtk.Align.CENTER, css_classes=["pill", "destructive-action"])
            def on_lk_kill(_b, pid=lk.pid, row=r):
                _b.set_sensitive(False)
                run_bg(lambda: kill_process(pid), lambda res: (row.set_subtitle(res[1]), inspect_locks(target)))
            k_btn.connect("clicked", on_lk_kill)
            r.add_suffix(k_btn)
            lock_group.add(r)
            lock_rows.append(r)

    lock_btn = Gtk.Button(label="Check File", valign=Gtk.Align.CENTER, css_classes=["pill"])
    lock_btn.connect("clicked", lambda _b: pick_single("Select File to Check Locks", inspect_locks))
    lock_status.add_suffix(lock_btn)
    lock_group.add(lock_status)
    page.add(lock_group)

    # 8. Extended PowerToys (Shortcut Guide, ZoomIt, Quick Accent, Light Switch, Workspaces)
    from knobu.modules.powertools.theme import get_theme, set_theme
    from knobu.modules.powertools.workspaces import WorkspaceGroup, launch_workspace, load_workspaces, save_workspaces

    ext_group = Adw.PreferencesGroup(
        title="Extended PowerToys Utilities",
        description="Shortcut Guide overlay, ZoomIt freeze-annotate, Quick Accent picker, and Light Switch theme.",
    )
    ext_group.add(shortcut_row(store, mid, "shortcut_guide_hotkey", "Shortcut Guide Shortcut",
                               "Interactive overlay listing all configured Knobu and desktop shortcuts"))
    ext_group.add(button_row("Shortcut Guide", "Open Guide", lambda: launch.knobu("shortcut-guide"),
                             "View all keyboard shortcuts in one searchable window"))
    ext_group.add(shortcut_row(store, mid, "zoomit_hotkey", "ZoomIt Annotation Shortcut",
                               "Freeze screen, zoom with scroll wheel, and draw pen/arrow/box annotations"))
    ext_group.add(button_row("ZoomIt", "Start ZoomIt", lambda: launch.knobu("zoomit"),
                             "Launch screen zoom and annotation overlay now"))
    ext_group.add(button_row("Quick Accent", "Open Picker", lambda: launch.knobu("quick-accent"),
                             "Pick accented characters and symbols to paste"))
    ext_group.add(switch_row(store, mid, "light_switch_enabled", "Light Switch (Auto Theme)",
                             "Automatically switch GNOME / KDE dark and light theme on schedule"))
    ext_group.add(button_row("Desktop Theme", "Toggle Dark/Light",
                             lambda: set_theme("toggle"),
                             f"Current theme: {get_theme().capitalize()}"))
    page.add(ext_group)

    # 9. Workspaces Launcher
    ws_group = Adw.PreferencesGroup(
        title="Workspaces Launcher",
        description="Save named app and command groups and launch them together in one click.",
    )
    ws_name_entry = Adw.EntryRow(title="Workspace Name (e.g. Dev Ops)")
    ws_cmds_entry = Adw.EntryRow(title="Commands (semicolon-separated, e.g. code; gnome-terminal)")
    ws_add_btn = Gtk.Button(label="Save Workspace", valign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"])
    ws_cmds_entry.add_suffix(ws_add_btn)
    ws_group.add(ws_name_entry)
    ws_group.add(ws_cmds_entry)
    ws_rows: list[Gtk.Widget] = []

    def rebuild_workspaces() -> None:
        for r in ws_rows:
            ws_group.remove(r)
        ws_rows.clear()
        for idx, g in enumerate(load_workspaces()):
            row = Adw.ActionRow(use_markup=False, title=g.name, subtitle=", ".join(g.commands))
            launch_b = Gtk.Button(label="Launch", valign=Gtk.Align.CENTER, css_classes=["pill"])
            launch_b.connect("clicked", lambda _b, n=g.name, r=row: r.set_subtitle(launch_workspace(n)[1]))
            del_b = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER, css_classes=["flat"])
            def on_del_ws(_b, i=idx):
                groups = load_workspaces()
                if 0 <= i < len(groups):
                    groups.pop(i)
                    save_workspaces(groups)
                rebuild_workspaces()
            del_b.connect("clicked", on_del_ws)
            row.add_suffix(launch_b)
            row.add_suffix(del_b)
            ws_group.add(row)
            ws_rows.append(row)

    def on_add_ws(_b) -> None:
        name = ws_name_entry.get_text().strip()
        cmds = [c.strip() for c in ws_cmds_entry.get_text().split(";") if c.strip()]
        if not name or not cmds:
            return
        groups = [g for g in load_workspaces() if g.name.lower() != name.lower()]
        groups.append(WorkspaceGroup(name=name, commands=cmds))
        save_workspaces(groups)
        ws_name_entry.set_text("")
        ws_cmds_entry.set_text("")
        rebuild_workspaces()

    ws_add_btn.connect("clicked", on_add_ws)
    rebuild_workspaces()
    page.add(ws_group)

    return page


def notifications_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    from knobu.modules.notifications.store import NotificationHistory
    from knobu.modules.powertools.aws_cli import get_active_aws_profile, load_aws_profiles, set_active_aws_profile
    from knobu.modules.powertools.network import fetch_public_ip, get_network_status

    mid = NotificationsModule.id
    page = ModulePage(store, NotificationsModule)

    tray_group = Adw.PreferencesGroup(
        title="Top Notification Tray and HUD",
        description="Display Knobu in your top bar with quick toggles, IP status, AWS profile switcher, and alerts.",
    )
    tray_group.add(switch_row(store, mid, "show_tray", "Show Top Notification Tray Icon",
                              "Publish StatusNotifierItem dropdown menu for GNOME AppIndicator and KDE Plasma"))
    tray_group.add(switch_row(store, mid, "show_public_ip", "Show Public IP in Tray Menu",
                              "Fetch and display your current public IPv4 address with 1-click copy"))
    tray_group.add(switch_row(store, mid, "show_hud", "Enable Mac-Style HUD Capsule",
                              "Display compact Dynamic Island floating banner on incoming desktop notifications"))
    tray_group.add(switch_row(store, mid, "dnd", "Do Not Disturb",
                              "Still record incoming notifications while suppressing floating HUD banners"))
    page.add(tray_group)

    net = get_network_status()
    net_group = Adw.PreferencesGroup(
        title="Live Network and AWS CLI Status",
        description="Same live readout shown in your top notification tray dropdown.",
    )
    net_group.add(Adw.ActionRow(use_markup=False, title=f"Connection ({net.connection_type or 'network'})",
                                subtitle=f"{net.connection_name}"))
    if net.vpn_active and net.vpn_ip:
        vpn_dev_label = f" ({net.vpn_device})" if net.vpn_device and net.vpn_device != net.vpn_name else ""
        net_group.add(Adw.ActionRow(use_markup=False, title=f"VPN Service: {net.vpn_name}{vpn_dev_label}",
                                    subtitle=f"Active Tunnel · IP: {net.vpn_ip}"))

    from knobu.system.clipboard import set_clipboard

    def make_ip_row(title: str, initial: str, fetch_fn) -> Adw.ActionRow:
        row = Adw.ActionRow(use_markup=False, title=title, subtitle=initial)
        state = {"val": initial}

        copy_btn = Gtk.Button(
            icon_name="edit-copy-symbolic",
            tooltip_text="Copy IP",
            valign=Gtk.Align.CENTER,
            css_classes=["flat"],
        )

        def on_copy(_b):
            val = state["val"]
            if val and val not in ("Unavailable", "Offline", "Click Refresh to load", "Refreshing..."):
                set_clipboard(val)
                row.set_subtitle(f"{val} (copied)")

        copy_btn.connect("clicked", on_copy)
        row.add_suffix(copy_btn)
        row._state = state
        row._fetch_fn = fetch_fn
        return row

    row_private = make_ip_row("Private IP", net.private_ip, lambda: get_network_status().private_ip)
    net_group.add(row_private)

    row_public = make_ip_row("Public IP", "Click Refresh to load", lambda: fetch_public_ip() or "Offline")
    net_group.add(row_public)

    row_vpn = None
    if net.vpn_active and net.vpn_ip:
        row_vpn = make_ip_row(f"VPN IP ({net.vpn_name})", net.vpn_ip, lambda: get_network_status().vpn_ip or "Disconnected")
        net_group.add(row_vpn)

    # Standalone large refresh button row clearly separated from Copy actions
    refresh_row = Adw.ActionRow(
        use_markup=False,
        title="Network and IP Refresh",
        subtitle="Re-query local interfaces, active VPN tunnel, and fetch live public IP",
    )
    refresh_all_btn = Gtk.Button(
        icon_name="view-refresh-symbolic",
        tooltip_text="Refresh all IPs",
        valign=Gtk.Align.CENTER,
        css_classes=["flat"],
    )

    def on_refresh_all(_b):
        refresh_all_btn.set_sensitive(False)
        row_private.set_subtitle("Refreshing...")
        row_public.set_subtitle("Refreshing...")
        if row_vpn:
            row_vpn.set_subtitle("Refreshing...")

        def worker():
            fresh_net = get_network_status()
            fresh_pub = fetch_public_ip() or "Offline"
            row_private._state["val"] = fresh_net.private_ip
            row_public._state["val"] = fresh_pub
            if row_vpn:
                row_vpn._state["val"] = fresh_net.vpn_ip or "Disconnected"

            def apply_ui():
                row_private.set_subtitle(fresh_net.private_ip)
                row_public.set_subtitle(fresh_pub)
                if row_vpn:
                    row_vpn.set_subtitle(fresh_net.vpn_ip or "Disconnected")
                refresh_all_btn.set_sensitive(True)
                return False

            GLib.idle_add(apply_ui)

        threading.Thread(target=worker, daemon=True).start()

    refresh_all_btn.connect("clicked", on_refresh_all)
    refresh_row.add_suffix(refresh_all_btn)
    net_group.add(refresh_row)

    active_aws = get_active_aws_profile()
    profiles = load_aws_profiles()
    aws_row = Adw.ActionRow(use_markup=False, title="Active AWS CLI Profile",
                            subtitle=f"{active_aws} ({len(profiles)} configured in ~/.aws)")
    if profiles:
        names = [p.name for p in profiles]
        sel = Adw.ComboRow(use_markup=False, title="Switch Active AWS Profile",
                           model=Gtk.StringList.new(names))
        if active_aws in names:
            sel.set_selected(names.index(active_aws))
        def on_aws_sel(r, _p):
            chosen = profiles[r.get_selected()]
            ok, msg = set_active_aws_profile(chosen.name, chosen.region)
            aws_row.set_subtitle(f"{chosen.name} — {msg}" if ok else msg)
        sel.connect("notify::selected", on_aws_sel)
        net_group.add(aws_row)
        net_group.add(sel)
    else:
        net_group.add(aws_row)
    page.add(net_group)

    hist = NotificationHistory()
    hist_group = Adw.PreferencesGroup(title="Notification Center")
    hist_row = Adw.ActionRow(use_markup=False, title="Recorded Notifications",
                             subtitle=f"{hist.count()} notification(s) saved")
    open_btn = Gtk.Button(label="Open Drawer", valign=Gtk.Align.CENTER, css_classes=["pill"])
    open_btn.connect("clicked", lambda _b: launch.knobu("notifications"))
    hist_row.add_suffix(open_btn)
    hist_group.add(hist_row)
    page.add(hist_group)

    return page


def devops_page(_store: SettingsStore, _navigate) -> Gtk.Widget:
    from knobu.modules.powertools.aws_cli import get_active_aws_profile, load_aws_profiles, set_active_aws_profile
    from knobu.modules.powertools.cron import (
        add_cron_job,
        cron_service_status,
        list_cron_jobs,
        remove_cron_job,
        toggle_cron_job,
    )
    from knobu.modules.powertools.devops import (
        calculate_cidr,
        get_aws_caller_identity,
        get_docker_containers,
        get_kube_contexts,
        inspect_ssl_cert,
        query_dns,
        switch_kube_context,
    )

    page = Adw.PreferencesPage()

    hero = Gtk.Box(spacing=18, css_classes=["hero"])
    hero.append(tile("network-server-symbolic", "large"))
    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER, hexpand=True)
    text.append(Gtk.Label(label="DevOps on Cloud", xalign=0, css_classes=["title-2"]))
    text.append(Gtk.Label(
        label="AWS CLI profiles, Kubernetes & Docker contexts, network diagnostics, and local cron jobs.",
        xalign=0, wrap=True, css_classes=["dim-label", "hero-subtitle"],
    ))
    hero.append(text)
    header = Adw.PreferencesGroup()
    header.add(hero)
    page.add(header)

    # 1. AWS CLI & Caller Identity
    aws_group = Adw.PreferencesGroup(title="AWS CLI and Identity")
    active_aws = get_active_aws_profile()
    profiles = load_aws_profiles()
    aws_row = Adw.ActionRow(use_markup=False, title="Active AWS CLI Profile",
                            subtitle=f"{active_aws} ({len(profiles)} configured in ~/.aws)")
    aws_group.add(aws_row)
    if profiles:
        names = [p.name for p in profiles]
        sel = Adw.ComboRow(use_markup=False, title="Switch Active AWS Profile",
                           model=Gtk.StringList.new(names))
        if active_aws in names:
            sel.set_selected(names.index(active_aws))
        def on_aws_sel(r, _p):
            chosen = profiles[r.get_selected()]
            ok, msg = set_active_aws_profile(chosen.name, chosen.region)
            aws_row.set_subtitle(f"{chosen.name} — {msg}" if ok else msg)
        sel.connect("notify::selected", on_aws_sel)
        aws_group.add(sel)

    ident_row = Adw.ActionRow(
        use_markup=False,
        title="AWS Caller Identity",
        subtitle="Click Verify to inspect active Account ID and User/Role ARN",
    )
    verify_aws_btn = Gtk.Button(
        icon_name="security-high-symbolic",
        tooltip_text="Verify active AWS identity (STS)",
        valign=Gtk.Align.CENTER,
        css_classes=["flat"],
    )
    def on_verify_aws(_b):
        ident_row.set_subtitle("Checking AWS STS...")
        def worker():
            ident = get_aws_caller_identity()
            msg = f"Error: {ident['error']}" if "error" in ident else f"Account {ident.get('Account')} · {ident.get('Arn')}"
            GLib.idle_add(lambda: (ident_row.set_subtitle(msg), False)[1])
        threading.Thread(target=worker, daemon=True).start()
    verify_aws_btn.connect("clicked", on_verify_aws)
    ident_row.add_suffix(verify_aws_btn)
    aws_group.add(ident_row)
    page.add(aws_group)

    # 2. Containers & Kubernetes Context
    infra_group = Adw.PreferencesGroup(title="Kubernetes and Containers")
    cur_kube, all_kubes = get_kube_contexts()
    if all_kubes:
        kube_row = Adw.ComboRow(use_markup=False, title="Active Kubernetes Context",
                                model=Gtk.StringList.new(all_kubes))
        if cur_kube in all_kubes:
            kube_row.set_selected(all_kubes.index(cur_kube))
        kube_row.connect("notify::selected", lambda r, _p: switch_kube_context(all_kubes[r.get_selected()]))
        infra_group.add(kube_row)
    else:
        infra_group.add(Adw.ActionRow(use_markup=False, title="Kubernetes Context",
                                      subtitle="No active kubectl contexts configured"))

    conts = get_docker_containers()
    docker_sub = f"{len(conts)} container(s): {', '.join(c.name for c in conts[:4])}" if conts else "No active Docker containers"
    infra_group.add(Adw.ActionRow(use_markup=False, title="Docker Containers", subtitle=docker_sub))
    page.add(infra_group)

    # 3. Network & DevOps Diagnostics
    diag_group = Adw.PreferencesGroup(
        title="Network and DevOps Diagnostics",
        description="Live DNS query, SSL certificate inspection, and CIDR subnet calculation.",
    )

    dns_row = Adw.ActionRow(use_markup=False, title="DNS Lookup", subtitle="Query A, AAAA, CNAME, MX records")
    dns_entry = Gtk.Entry(placeholder_text="domain (e.g. google.com)", valign=Gtk.Align.CENTER, width_request=220)
    dns_btn = Gtk.Button(icon_name="system-search-symbolic", tooltip_text="Query DNS", valign=Gtk.Align.CENTER, css_classes=["flat"])
    def on_dns(_b):
        dom = dns_entry.get_text().strip()
        if not dom:
            return
        dns_row.set_subtitle("Querying...")
        def worker():
            ok, recs, msg = query_dns(dom, "A")
            sub = f"{dom} -> {', '.join(r.value for r in recs[:3])}" if ok and recs else f"{dom}: {msg}"
            GLib.idle_add(lambda: (dns_row.set_subtitle(sub), False)[1])
        threading.Thread(target=worker, daemon=True).start()
    dns_btn.connect("clicked", on_dns)
    dns_row.add_suffix(dns_entry)
    dns_row.add_suffix(dns_btn)
    diag_group.add(dns_row)

    ssl_row = Adw.ActionRow(use_markup=False, title="SSL/TLS Certificate", subtitle="Check certificate expiration and issuer")
    ssl_entry = Gtk.Entry(placeholder_text="host (e.g. github.com)", valign=Gtk.Align.CENTER, width_request=220)
    ssl_btn = Gtk.Button(icon_name="channel-secure-symbolic", tooltip_text="Inspect SSL", valign=Gtk.Align.CENTER, css_classes=["flat"])
    def on_ssl(_b):
        host = ssl_entry.get_text().strip()
        if not host:
            return
        ssl_row.set_subtitle("Connecting...")
        def worker():
            res = inspect_ssl_cert(host)
            sub = (f"{res.issuer} · {res.days_left} day(s) left (Expires: {res.expiry_date})"
                   if res.is_valid else f"Invalid/Error: {res.error or 'Expired'}")
            GLib.idle_add(lambda: (ssl_row.set_subtitle(sub), False)[1])
        threading.Thread(target=worker, daemon=True).start()
    ssl_btn.connect("clicked", on_ssl)
    ssl_row.add_suffix(ssl_entry)
    ssl_row.add_suffix(ssl_btn)
    diag_group.add(ssl_row)

    cidr_row = Adw.ActionRow(use_markup=False, title="CIDR Subnet Calculator", subtitle="Calculate network mask, broadcast, and usable host capacity")
    cidr_entry = Gtk.Entry(placeholder_text="CIDR (e.g. 10.0.0.0/16)", valign=Gtk.Align.CENTER, width_request=220)
    cidr_btn = Gtk.Button(icon_name="accessories-calculator-symbolic", tooltip_text="Calculate", valign=Gtk.Align.CENTER, css_classes=["flat"])
    def on_cidr(_b):
        c_str = cidr_entry.get_text().strip()
        if not c_str:
            return
        ok, res, msg = calculate_cidr(c_str)
        sub = (f"{res.cidr}: {res.usable_hosts:,} usable hosts ({res.first_host} - {res.last_host}) · Netmask {res.netmask}"
               if ok and res else f"Error: {msg}")
        cidr_row.set_subtitle(sub)
    cidr_btn.connect("clicked", on_cidr)
    cidr_row.add_suffix(cidr_entry)
    cidr_row.add_suffix(cidr_btn)
    diag_group.add(cidr_row)
    page.add(diag_group)

    # 4. Local Cron Jobs & Scheduler
    cron_active, cron_msg = cron_service_status()
    cron_group = Adw.PreferencesGroup(
        title="Local Cron Jobs and Scheduler",
        description=f"Cron Daemon: {'Running' if cron_active else 'Inactive'} ({cron_msg})",
    )
    cron_sched = Adw.EntryRow(title="Schedule (e.g. 0 12 * * * or @daily)")
    cron_cmd = Adw.EntryRow(title="Command (e.g. /path/to/backup.sh)")
    cron_comment = Adw.EntryRow(title="Description (optional)")
    cron_add_btn = Gtk.Button(label="Add Cron Job", valign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"])
    cron_comment.add_suffix(cron_add_btn)
    cron_status = Adw.ActionRow(use_markup=False, title="Crontab Status", subtitle="Ready")

    cron_group.add(cron_sched)
    cron_group.add(cron_cmd)
    cron_group.add(cron_comment)
    cron_group.add(cron_status)

    cron_rows: list[Gtk.Widget] = []

    def rebuild_cron() -> None:
        for r in cron_rows:
            cron_group.remove(r)
        cron_rows.clear()
        jobs = list_cron_jobs()
        if not jobs:
            empty = Adw.ActionRow(use_markup=False, title="No user cron jobs configured",
                                  subtitle="Add a cron job above to schedule recurring local tasks")
            cron_group.add(empty)
            cron_rows.append(empty)
            return
        for idx, job in enumerate(jobs):
            title = f"{job.schedule} — {job.comment}" if job.comment else job.schedule
            row = Adw.ActionRow(
                use_markup=False,
                title=GLib.markup_escape_text(title, -1),
                subtitle=GLib.markup_escape_text(job.command, -1),
            )
            sw = Gtk.Switch(active=job.enabled, valign=Gtk.Align.CENTER, tooltip_text="Enable or pause cron job")
            sw.connect("notify::active", lambda _s, _p, i=idx: (toggle_cron_job(i), rebuild_cron()))
            del_b = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                               tooltip_text="Remove cron job", css_classes=["flat"])
            del_b.connect("clicked", lambda _b, i=idx: (remove_cron_job(i), rebuild_cron()))
            row.add_suffix(sw)
            row.add_suffix(del_b)
            cron_group.add(row)
            cron_rows.append(row)

    def on_add_cron(_b) -> None:
        ok, msg = add_cron_job(cron_sched.get_text(), cron_cmd.get_text(), cron_comment.get_text())
        cron_status.set_subtitle(msg)
        if ok:
            cron_sched.set_text("")
            cron_cmd.set_text("")
            cron_comment.set_text("")
            rebuild_cron()

    cron_add_btn.connect("clicked", on_add_cron)
    rebuild_cron()
    page.add(cron_group)

    return page


def automation_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    import uuid
    page = ModulePage(store, AutomationModule)

    builder = Adw.PreferencesGroup(
        title="New Automation Rule",
        description="Build Mac Shortcuts-style rules: When [Trigger] -> If [Condition] -> Then [Action].",
    )
    name_row = Adw.EntryRow(title="Rule Name (e.g. Office Wi-Fi Setup)")
    trig_row = Adw.ComboRow(use_markup=False, title="When (Trigger)",
                            model=Gtk.StringList.new([lbl for _, lbl in TRIGGER_TYPES]))
    trig_val = Adw.EntryRow(title="Trigger Value (SSID, %, app, path, or HH:MM)")
    cond_row = Adw.ComboRow(use_markup=False, title="If (Condition)",
                            model=Gtk.StringList.new([lbl for _, lbl in CONDITION_TYPES]))
    cond_val = Adw.EntryRow(title="Condition Value (optional)")
    act_row = Adw.ComboRow(use_markup=False, title="Then (Action)",
                           model=Gtk.StringList.new([lbl for _, lbl in ACTION_TYPES]))
    act_val = Adw.EntryRow(title="Action Value (message, profile, dark/light, or command)")

    add_btn = Gtk.Button(label="Add Rule", valign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"])
    act_val.add_suffix(add_btn)
    for w in (name_row, trig_row, trig_val, cond_row, cond_val, act_row, act_val):
        builder.add(w)
    page.add(builder)

    rules_group = Adw.PreferencesGroup(title="Active Automation Rules")
    rules_rows: list[Gtk.Widget] = []

    hist_group = Adw.PreferencesGroup(title="Execution History")
    hist_rows: list[Gtk.Widget] = []

    def rebuild_history() -> None:
        for r in hist_rows:
            hist_group.remove(r)
        hist_rows.clear()
        entries = load_history(limit=10)
        if not entries:
            empty = Adw.ActionRow(use_markup=False, title="No executions yet",
                                  subtitle="Rules run automatically in the background or via Test Run")
            hist_group.add(empty)
            hist_rows.append(empty)
            return
        for ent in entries:
            ts = time.strftime("%H:%M:%S", time.localtime(ent.timestamp))
            row = Adw.ActionRow(use_markup=False, title=f"[{ts}] {ent.rule_name}",
                                subtitle=f"{ent.trigger} -> {ent.result}")
            hist_group.add(row)
            hist_rows.append(row)

    def rebuild_rules() -> None:
        for r in rules_rows:
            rules_group.remove(r)
        rules_rows.clear()
        rules = load_rules()
        if not rules:
            empty = Adw.ActionRow(use_markup=False, title="No automation rules configured")
            rules_group.add(empty)
            rules_rows.append(empty)
            return
        for idx, rule in enumerate(rules):
            act_desc = ", ".join(f"{a.type}({a.value})" for a in rule.actions)
            row = Adw.ActionRow(
                use_markup=False,
                title=rule.name,
                subtitle=f"When {rule.trigger_type}={rule.trigger_value or '*'} -> {act_desc}",
            )
            sw = Gtk.Switch(active=rule.enabled, valign=Gtk.Align.CENTER)
            def on_toggle(s, _p, i=idx):
                cur = load_rules()
                if 0 <= i < len(cur):
                    cur[i].enabled = s.get_active()
                    save_rules(cur)
            sw.connect("notify::active", on_toggle)

            test_b = Gtk.Button(label="Test Run", valign=Gtk.Align.CENTER, css_classes=["pill"])
            def on_test(_b, r_obj=rule, r_widget=row):
                _ok, msg = run_rule_now(r_obj)
                r_widget.set_subtitle(f"Last test: {msg}")
                rebuild_history()
            test_b.connect("clicked", on_test)

            del_b = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER, css_classes=["flat"])
            def on_del(_b, i=idx):
                cur = load_rules()
                if 0 <= i < len(cur):
                    cur.pop(i)
                    save_rules(cur)
                rebuild_rules()
            del_b.connect("clicked", on_del)

            row.add_suffix(sw)
            row.add_suffix(test_b)
            row.add_suffix(del_b)
            rules_group.add(row)
            rules_rows.append(row)

    def on_add_rule(_b) -> None:
        r_name = name_row.get_text().strip() or "New Rule"
        t_type = TRIGGER_TYPES[trig_row.get_selected()][0]
        c_type = CONDITION_TYPES[cond_row.get_selected()][0]
        a_type = ACTION_TYPES[act_row.get_selected()][0]
        rules = load_rules()
        rules.append(AutomationRule(
            id=uuid.uuid4().hex[:8],
            name=r_name,
            enabled=True,
            trigger_type=t_type,
            trigger_value=trig_val.get_text().strip(),
            condition_type=c_type,
            condition_value=cond_val.get_text().strip(),
            actions=[AutomationAction(type=a_type, value=act_val.get_text().strip())],
        ))
        save_rules(rules)
        name_row.set_text("")
        trig_val.set_text("")
        cond_val.set_text("")
        act_val.set_text("")
        rebuild_rules()

    add_btn.connect("clicked", on_add_rule)
    rebuild_rules()
    rebuild_history()
    page.add(rules_group)
    page.add(hist_group)
    return page


def sound_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    mid = SoundSuiteModule.id
    page = ModulePage(store, SoundSuiteModule)

    ctrl_group = Adw.PreferencesGroup(
        title="Microphone and Output Controls",
        description="Global microphone mute, output device switcher, and hearing protection.",
    )
    ctrl_group.add(shortcut_row(store, mid, "mic_mute_hotkey", "Global Mic Mute Shortcut",
                                "Toggle default microphone mute with OSD feedback"))
    ctrl_group.add(shortcut_row(store, mid, "switch_output_hotkey", "Switch Output Device Shortcut",
                                "Cycle between headphones and speakers"))
    ctrl_group.add(switch_row(store, mid, "auto_lower_on_disconnect", "Headphone Disconnect Safety",
                              "Automatically lower speaker volume when Bluetooth/wired headphones disconnect"))
    ctrl_group.add(spin_row(store, mid, "safe_speaker_volume", "Safe Speaker Volume (%)",
                            "Target volume percentage when switching back to speakers", 5, 80, 5))
    ctrl_group.add(switch_row(store, mid, "block_bt_music_autostart", "Music App Blocker",
                              "Prevent unintended media player launches on Bluetooth reconnect"))

    _mic_vol, mic_muted = get_mic_status()
    mic_row = Adw.ActionRow(use_markup=False, title="Microphone Status",
                            subtitle="Muted" if mic_muted else "Active (Live)")
    mic_btn = Gtk.Button(label="Toggle Mic Mute", valign=Gtk.Align.CENTER, css_classes=["pill"])
    def on_mic_btn(_b):
        _ok, msg = toggle_mic_mute()
        mic_row.set_subtitle(msg)
    mic_btn.connect("clicked", on_mic_btn)
    mic_row.add_suffix(mic_btn)
    ctrl_group.add(mic_row)
    page.add(ctrl_group)

    sinks, _sources, streams = list_audio_state()
    if sinks:
        sink_group = Adw.PreferencesGroup(title="Output Devices")
        names = [s.name for s in sinks]
        sel = Adw.ComboRow(use_markup=False, title="Default Output Sink",
                           model=Gtk.StringList.new(names))
        def_idx = next((i for i, s in enumerate(sinks) if s.is_default), 0)
        sel.set_selected(def_idx)
        sel.connect("notify::selected", lambda r, _p: set_default_sink(sinks[r.get_selected()].id))
        sink_group.add(sel)
        page.add(sink_group)

    mixer_group = Adw.PreferencesGroup(
        title="Per-App Volume Mixer (up to 150%)",
        description="Independent volume sliders and mute toggles for active playback streams.",
    )
    mixer_rows: list[Gtk.Widget] = []

    def rebuild_mixer(*_args) -> None:
        for r in mixer_rows:
            mixer_group.remove(r)
        mixer_rows.clear()
        _, _, cur_streams = list_audio_state()
        if not cur_streams:
            empty = Adw.ActionRow(use_markup=False, title="No active application audio streams",
                                  subtitle="Play audio in a browser or media app, then refresh")
            mixer_group.add(empty)
            mixer_rows.append(empty)
            return
        for st in cur_streams:
            row = Adw.ActionRow(use_markup=False, title=st.app_name,
                                subtitle=f"{st.volume}%{' (Muted)' if st.muted else ''}")
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 150, 5)
            scale.set_value(st.volume)
            scale.set_size_request(180, -1)
            scale.set_valign(Gtk.Align.CENTER)
            def on_slide(sc, sid=st.id, r=row):
                val = int(sc.get_value())
                set_stream_volume(sid, val)
                r.set_subtitle(f"{val}%")
            scale.connect("value-changed", on_slide)

            mute_b = Gtk.Button(
                icon_name="audio-volume-muted-symbolic",
                tooltip_text="Toggle mute",
                valign=Gtk.Align.CENTER,
                css_classes=["flat"],
            )
            mute_b.connect("clicked", lambda _b, sid=st.id: (toggle_stream_mute(sid), rebuild_mixer()))
            row.add_suffix(scale)
            row.add_suffix(mute_b)
            mixer_group.add(row)
            mixer_rows.append(row)

    ref_row = Adw.ActionRow(use_markup=False, title="Active Streams", subtitle="Refresh PipeWire application streams")
    ref_b = Gtk.Button(icon_name="view-refresh-symbolic", valign=Gtk.Align.CENTER, css_classes=["flat"])
    ref_b.connect("clicked", rebuild_mixer)
    ref_row.add_suffix(ref_b)
    mixer_group.add(ref_row)
    rebuild_mixer()
    page.add(mixer_group)

    return page


def windows_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    mid = WindowModule.id
    page = ModulePage(store, WindowModule)

    aot_group = Adw.PreferencesGroup(
        title="Always on Top",
        description="Pin or unpin the active window above all other windows.",
    )
    aot_group.add(shortcut_row(store, mid, "always_on_top_hotkey", "Always on Top Shortcut",
                               "Toggle keep-above state on the active window"))
    aot_group.add(button_row("Pin Active Window", "Toggle Always on Top",
                             lambda: toggle_always_on_top(store.get(mid, "excluded_apps", [])),
                             "Pin or unpin the focused window immediately"))
    page.add(aot_group)

    fz_group = Adw.PreferencesGroup(
        title="FancyZones Grid Snapping",
        description="Snap windows into structured zone layouts with configurable padding.",
    )
    fz_group.add(choice_row(store, mid, "zone_preset", "Active Zone Layout",
                            "Preset used by FancyZones overlay and quick-snap shortcuts", ZONE_PRESETS))
    fz_group.add(spin_row(store, mid, "zone_gap", "Zone Padding / Gap (px)",
                          "Spacing around and between window zones", 0, 48, 2))
    fz_group.add(shortcut_row(store, mid, "fancyzones_hotkey", "Zone Overlay Shortcut",
                              "Open the interactive FancyZones picker overlay"))
    fz_group.add(shortcut_row(store, mid, "snap_left_hotkey", "Snap to Left / Primary Zone",
                              "Snap active window to Zone 1"))
    fz_group.add(shortcut_row(store, mid, "snap_right_hotkey", "Snap to Right / Secondary Zone",
                              "Snap active window to Zone 2"))
    fz_group.add(shortcut_row(store, mid, "maximize_hotkey", "Window Maximize Shortcut",
                              "Maximize window to fill active screen area cleanly"))
    fz_group.add(button_row("Zone Layout Editor", "Open FancyZones",
                            lambda: launch.knobu("fancyzones"),
                            "Launch interactive visual zone grid"))
    fz_group.add(button_row("Maximize Window", "Maximize Active",
                            lambda: maximize_active_window(),
                            "Fill active monitor cleanly without fullscreen displacement"))
    page.add(fz_group)

    return page


def sysmon_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    mid = SystemMonitorModule.id
    page = ModulePage(store, SystemMonitorModule)

    live_group = Adw.PreferencesGroup(
        title="Live Hardware Metrics",
        description="Real-time CPU, per-core load, memory pressure, thermal sensors, and network throughput.",
    )
    cpu_row = Adw.ActionRow(use_markup=False, title="CPU Load", subtitle="Measuring...")
    mem_row = Adw.ActionRow(use_markup=False, title="Memory Usage", subtitle="Measuring...")
    temp_row = Adw.ActionRow(use_markup=False, title="Thermal Peak", subtitle="Measuring...")
    net_row = Adw.ActionRow(use_markup=False, title="Network Throughput", subtitle="Measuring...")
    bat_row = Adw.ActionRow(use_markup=False, title="Power and Battery", subtitle="Measuring...")

    def refresh_metrics(*_args) -> None:
        def worker():
            m = collect_metrics(sample_sec=0.15)
            cores_str = " ".join(f"{c:.0f}%" for c in m.per_core[:8])
            GLib.idle_add(lambda: (
                cpu_row.set_subtitle(f"{m.cpu_percent:.1f}% (Cores: {cores_str})"),
                mem_row.set_subtitle(f"{m.mem_used_gb:.2f} / {m.mem_total_gb:.2f} GB ({m.mem_percent:.1f}%)"),
                temp_row.set_subtitle(f"{m.max_temp_c:.1f} °C"),
                net_row.set_subtitle(f"Down: {m.net_rx_kbps:.1f} KB/s · Up: {m.net_tx_kbps:.1f} KB/s"),
                bat_row.set_subtitle(f"{m.battery_percent}% ({'AC Connected' if m.ac_online else 'Discharging'})"),
                False,
            )[-1])
        threading.Thread(target=worker, daemon=True).start()

    ref_row = Adw.ActionRow(use_markup=False, title="Sample Hardware", subtitle="Re-poll live CPU, RAM, and sensors")
    ref_b = Gtk.Button(icon_name="view-refresh-symbolic", valign=Gtk.Align.CENTER, css_classes=["flat"])
    ref_b.connect("clicked", refresh_metrics)
    ref_row.add_suffix(ref_b)

    for r in (cpu_row, mem_row, temp_row, net_row, bat_row, ref_row):
        live_group.add(r)
    refresh_metrics()
    page.add(live_group)

    alert_group = Adw.PreferencesGroup(
        title="Health Alerts and Tray Metrics",
        description="Configure hardware alert thresholds and top tray RAM readout.",
    )
    alert_group.add(switch_row(store, mid, "top_bar_metrics", "Show Metrics in Tray Header",
                               "Display live RAM percentage in the top notification tray status line"))
    alert_group.add(switch_row(store, mid, "alerts_enabled", "Enable Hardware Health Alerts",
                               "Send desktop alerts for sustained CPU load, high memory pressure, or low battery"))
    alert_group.add(spin_row(store, mid, "cpu_alert_percent", "CPU Alert Threshold (%)",
                             "Trigger alert when sustained CPU load exceeds this percentage", 50, 99, 5))
    alert_group.add(spin_row(store, mid, "mem_alert_percent", "Memory Alert Threshold (%)",
                             "Trigger alert when RAM usage exceeds this percentage", 60, 99, 5))
    alert_group.add(spin_row(store, mid, "battery_alert_percent", "Low Battery Alert (%)",
                             "Trigger alert when discharging below this battery percentage", 5, 40, 5))
    page.add(alert_group)

    return page


# (id, title, icon, builder, section). Add new module pages here.
PAGES = [
    ("dashboard", "Dashboard", "knobu-dashboard-symbolic", dashboard_page, "top"),
    ("devops", "DevOps on Cloud", "network-server-symbolic", devops_page, "top"),
    (TouchpadModule.id, TouchpadModule.name, TouchpadModule.icon, touchpad_page, "modules"),
    (KeyboardModule.id, KeyboardModule.name, KeyboardModule.icon, keyboard_page, "modules"),
    (MouseModule.id, MouseModule.name, MouseModule.icon, mouse_page, "modules"),
    (AwakeModule.id, AwakeModule.name, AwakeModule.icon, awake_page, "modules"),
    (ClipboardModule.id, ClipboardModule.name, ClipboardModule.icon, clipboard_page, "modules"),
    (CommandBarModule.id, CommandBarModule.name, CommandBarModule.icon, commandbar_page, "modules"),
    (NotificationsModule.id, NotificationsModule.name, NotificationsModule.icon, notifications_page, "modules"),
    (SoundSuiteModule.id, SoundSuiteModule.name, SoundSuiteModule.icon, sound_page, "modules"),
    (WindowModule.id, WindowModule.name, WindowModule.icon, windows_page, "modules"),
    (SystemMonitorModule.id, SystemMonitorModule.name, SystemMonitorModule.icon, sysmon_page, "modules"),
    (AutomationModule.id, AutomationModule.name, AutomationModule.icon, automation_page, "modules"),
    (PowerToolsModule.id, PowerToolsModule.name, PowerToolsModule.icon, powertools_page, "modules"),
    (ColorPickerModule.id, ColorPickerModule.name, ColorPickerModule.icon, colorpicker_page,
     "modules"),
    (TextExtractorModule.id, TextExtractorModule.name, TextExtractorModule.icon,
     textextractor_page, "modules"),
    ("general", "General", "knobu-general-symbolic", general_page, "bottom"),
]
