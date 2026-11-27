"""System Tools and Desktop Customization / Preferences pages (Milestones 13 & 14)."""

from __future__ import annotations

from pathlib import Path
import threading

from gi.repository import Adw, GLib, Gtk

from knobu import config, service
from knobu.ui.store import SettingsStore
from knobu.ui.widgets import tile


def _run_bg(work, on_done) -> None:
    def worker():
        res = work()
        GLib.idle_add(lambda: on_done(res) and False)
    threading.Thread(target=worker, daemon=True).start()


def _pick_single(parent_widget: Gtk.Widget, title: str, on_file) -> None:
    dlg = Gtk.FileDialog(title=title)
    root = parent_widget.get_root()

    def cb(d, res):
        try:
            f = d.open_finish(res)
            if f and f.get_path():
                on_file(Path(f.get_path()))
        except GLib.Error:
            pass

    dlg.open(root if isinstance(root, Gtk.Window) else None, None, cb)


def _btn_row(title: str, label: str, callback, subtitle: str = "") -> Adw.ActionRow:
    row = Adw.ActionRow(use_markup=False, title=title, subtitle=subtitle)
    btn = Gtk.Button(label=label, valign=Gtk.Align.CENTER, css_classes=["pill"])
    btn.connect("clicked", lambda _b: callback())
    row.add_suffix(btn)
    row.set_activatable_widget(btn)
    return row


def _combo(title: str, subtitle: str, options: list[str], current: str, on_change) -> Adw.ComboRow:
    items = list(options)
    if current and current not in items:
        items.insert(0, current)
    if not items:
        items = [current or "default"]
    row = Adw.ComboRow(use_markup=False, title=title, subtitle=subtitle, model=Gtk.StringList.new(items))
    row.set_selected(items.index(current) if current in items else 0)
    row.connect("notify::selected", lambda r, _p: on_change(items[r.get_selected()]))
    return row


def systools_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    """Dedicated System Tools page: Cleaner, Package Uninstaller, Env Vars, File Locksmith."""
    from knobu.modules.powertools import (
        EnvEntry,
        available_package_sources,
        clean_target,
        find_file_locks,
        format_bytes,
        is_valid_key,
        kill_process,
        list_installed_packages,
        load_profiles,
        save_profiles,
        scan_cleanup_targets,
        system_env_snapshot,
        uninstall_package,
    )

    page = Adw.PreferencesPage()
    hero = Gtk.Box(spacing=18, css_classes=["hero"])
    hero.append(tile("utilities-terminal-symbolic", "large"))
    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER, hexpand=True)
    text.append(Gtk.Label(label="System Tools", xalign=0, css_classes=["title-2"]))
    text.append(Gtk.Label(
        label="System-level cleanup, multi-source package uninstaller, environment variables, and File Locksmith.",
        xalign=0, wrap=True, css_classes=["dim-label", "hero-subtitle"],
    ))
    hero.append(text)
    header = Adw.PreferencesGroup()
    header.add(hero)
    page.add(header)

    # Feature Bypass Mode
    bp_group = Adw.PreferencesGroup()
    bp_sw = Adw.SwitchRow(
        use_markup=False,
        title="Bypass System Tools Customizations",
        subtitle="Skip syncing Knobu environment overrides when troubleshooting native OS behavior",
    )
    bp_sw.set_active(bool(store.data.get("systools", {}).get("bypass", False)))

    def on_bp(sw, _p):
        store.data.setdefault("systools", {})["bypass"] = sw.get_active()
        config.save(store.data)
    bp_sw.connect("notify::active", on_bp)
    bp_group.add(bp_sw)
    page.add(bp_group)

    # 1. System Cleaner
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

            _run_bg(lambda: clean_target(tid), done)

        c_btn.connect("clicked", on_clean)
        t_row.add_suffix(c_btn)
        target_rows[t.id] = t_row
        cleaner_group.add(t_row)

    cleaner_group.add(cleaner_status)
    page.add(cleaner_group)

    # 2. Package Uninstaller
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
                _run_bg(lambda: uninstall_package(name, src), lambda res: (r.set_subtitle(res[1]), refresh_packages()))

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

    # 3. Environment Variables Manager
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
                r.connect("notify::active", lambda sw, _p, ent=item: setattr(ent, "enabled", sw.get_active()))
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
        if bool(store.data.get("systools", {}).get("bypass", False)):
            env_status.set_subtitle("Bypass active: skipped live session sync")
            return
        env_status.set_subtitle("Syncing environment...")
        _run_bg(lambda: save_profiles(env_active, env_profiles, apply_live=True),
                lambda res: env_status.set_subtitle(res[1]))

    env_add_btn.connect("clicked", on_add_env)
    env_sync_btn.connect("clicked", on_sync_env)
    rebuild_env()
    page.add(env_group)

    # 4. File Locksmith
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

            def on_lk_kill(b, pid=lk.pid, row=r):
                b.set_sensitive(False)
                _run_bg(lambda: kill_process(pid), lambda res: (row.set_subtitle(res[1]), inspect_locks(target)))

            k_btn.connect("clicked", on_lk_kill)
            r.add_suffix(k_btn)
            lock_group.add(r)
            lock_rows.append(r)

    lock_btn = Gtk.Button(label="Check File", valign=Gtk.Align.CENTER, css_classes=["pill"])
    lock_btn.connect("clicked", lambda _b: _pick_single(page, "Select File to Check Locks", inspect_locks))
    lock_status.add_suffix(lock_btn)
    lock_group.add(lock_status)
    page.add(lock_group)

    return page


def preferences_page(store: SettingsStore, _navigate) -> Gtk.Widget:
    """Milestone 14: Startup Apps, Fonts, Appearance, Display Scaling, Sound Profiles, Notifications."""
    from knobu.modules.system_prefs import (
        add_startup_app,
        apply_monitor_config,
        discover_sound_themes,
        discover_themes,
        get_appearance_settings,
        get_font_settings,
        get_monitors,
        get_notification_prefs,
        get_sound_prefs,
        list_app_notifications,
        list_font_families,
        list_startup_apps,
        preview_sound,
        remove_startup_app,
        set_app_notification_enabled,
        set_interface_key,
        set_notification_pref,
        set_sound_pref,
        set_startup_app_enabled,
        set_wallpaper,
        set_wallpaper_options,
    )

    page = Adw.PreferencesPage()
    hero = Gtk.Box(spacing=18, css_classes=["hero"])
    hero.append(tile("preferences-desktop-theme-symbolic", "large"))
    text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER, hexpand=True)
    text.append(Gtk.Label(label="Appearance & System", xalign=0, css_classes=["title-2"]))
    text.append(Gtk.Label(
        label="Startup apps, fonts, cursors, icons, GTK legacy theme, wallpaper, display zoom, sound profiles, and notifications.",
        xalign=0, wrap=True, css_classes=["dim-label", "hero-subtitle"],
    ))
    hero.append(text)
    header = Adw.PreferencesGroup()
    header.add(hero)
    page.add(header)

    # 1. Startup Applications Manager
    start_group = Adw.PreferencesGroup(
        title="Startup Applications",
        description="Manage applications started automatically on login (~/.config/autostart).",
    )
    sa_name = Adw.EntryRow(title="App Name (e.g. Docker Tray)")
    sa_cmd = Adw.EntryRow(title="Command (e.g. /usr/bin/my-app --minimized)")
    sa_add = Gtk.Button(label="Add Startup App", valign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"])
    sa_cmd.add_suffix(sa_add)
    start_group.add(sa_name)
    start_group.add(sa_cmd)
    start_rows: list[Gtk.Widget] = []

    def rebuild_startup() -> None:
        for r in start_rows:
            start_group.remove(r)
        start_rows.clear()
        apps = list_startup_apps()
        if not apps:
            empty = Adw.ActionRow(use_markup=False, title="No autostart entries found")
            start_group.add(empty)
            start_rows.append(empty)
            return
        for app in apps[:30]:
            r = Adw.SwitchRow(use_markup=False, title=app.name, subtitle=app.exec_cmd or app.desktop_id)
            r.set_active(app.enabled)
            r.connect("notify::active", lambda sw, _p, did=app.desktop_id: set_startup_app_enabled(did, sw.get_active()))
            if app.is_user:
                del_b = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                                   css_classes=["flat", "circular"], tooltip_text="Remove startup entry")
                del_b.connect("clicked", lambda _b, did=app.desktop_id: (remove_startup_app(did), rebuild_startup()))
                r.add_suffix(del_b)
            start_group.add(r)
            start_rows.append(r)

    def on_add_sa(_b) -> None:
        ok, _msg = add_startup_app(sa_name.get_text(), sa_cmd.get_text())
        if ok:
            sa_name.set_text("")
            sa_cmd.set_text("")
            rebuild_startup()

    sa_add.connect("clicked", on_add_sa)
    rebuild_startup()
    page.add(start_group)

    # 2. Typography & System Fonts
    font_cfg = get_font_settings()
    families = list_font_families()
    font_group = Adw.PreferencesGroup(
        title="Fonts &amp; Typography",
        description="Customize interface, document, monospace fonts, text scaling, antialiasing, and hinting.",
    )

    def _font_row(gkey: str, title: str, cur_full: str) -> Adw.ComboRow:
        parts = cur_full.rsplit(" ", 1)
        fam = parts[0] if len(parts) == 2 and parts[1].isdigit() else cur_full
        size = int(parts[1]) if len(parts) == 2 and parts[1].isdigit() else 11
        return _combo(title, f"Current: {cur_full}", families[:120], fam,
                      lambda chosen: set_interface_key(gkey, f"'{chosen} {size}'"))

    font_group.add(_font_row("font-name", "Interface Font", str(font_cfg["font-name"])))
    font_group.add(_font_row("document-font-name", "Document Font", str(font_cfg["document-font-name"])))
    font_group.add(_font_row("monospace-font-name", "Monospace Font", str(font_cfg["monospace-font-name"])))

    scale_row = Adw.SpinRow.new_with_range(0.75, 2.0, 0.05)
    scale_row.set_use_markup(False)
    scale_row.set_digits(2)
    scale_row.set_title("Text Zoom / Scaling Factor")
    scale_row.set_subtitle("Adjust global font magnification across desktop windows")
    scale_row.set_value(float(font_cfg["text-scaling-factor"]))
    scale_row.connect("notify::value", lambda r, _p: set_interface_key("text-scaling-factor", round(r.get_value(), 2)))
    font_group.add(scale_row)

    font_group.add(_combo("Antialiasing", "Subpixel font smoothing method", ["rgba", "grayscale", "none"],
                          str(font_cfg["font-antialiasing"]), lambda v: set_interface_key("font-antialiasing", v)))
    font_group.add(_combo("Hinting", "Glyph grid alignment crispness", ["none", "slight", "medium", "full"],
                          str(font_cfg["font-hinting"]), lambda v: set_interface_key("font-hinting", v)))
    page.add(font_group)

    # 3. Appearance & Desktop Theming
    app_cfg = get_appearance_settings()
    app_group = Adw.PreferencesGroup(
        title="Appearance, Cursors, Icons &amp; Background",
        description="Configure color scheme, cursor theme/size, icon theme, legacy GTK theme, and wallpapers.",
    )
    app_group.add(_combo("Color Scheme", "Desktop Light / Dark preference", ["prefer-dark", "default", "prefer-light"],
                         str(app_cfg["color-scheme"]), lambda v: set_interface_key("color-scheme", v)))

    cursor_themes = discover_themes("cursor") or ["Yaru", "Adwaita"]
    app_group.add(_combo("Cursor Theme", "Mouse pointer theme", cursor_themes,
                         str(app_cfg["cursor-theme"]), lambda v: set_interface_key("cursor-theme", v)))
    app_group.add(_combo("Cursor Size", "Mouse pointer size in pixels", ["24", "32", "48", "64"],
                         str(app_cfg["cursor-size"]), lambda v: set_interface_key("cursor-size", int(v))))

    icon_themes = discover_themes("icon") or ["Yaru", "Adwaita"]
    app_group.add(_combo("Icon Theme", "Application and folder icon pack", icon_themes,
                         str(app_cfg["icon-theme"]), lambda v: set_interface_key("icon-theme", v)))

    gtk_themes = discover_themes("gtk") or ["Yaru-dark", "Yaru", "Adwaita"]
    app_group.add(_combo("Legacy Applications (GTK Theme)", "Theme for GTK3 / legacy desktop apps", gtk_themes,
                         str(app_cfg["gtk-theme"]), lambda v: set_interface_key("gtk-theme", v)))

    app_group.add(_combo("Background Fit / Ratio", "Wallpaper sizing mode",
                         ["zoom", "scaled", "centered", "stretched", "spanned", "wallpaper"],
                         str(app_cfg["picture-options"]), set_wallpaper_options))

    wp_light_row = Adw.ActionRow(use_markup=False, title="Light Mode Wallpaper", subtitle=str(app_cfg["picture-uri"] or "Default"))
    wp_l_btn = Gtk.Button(label="Choose Image", valign=Gtk.Align.CENTER, css_classes=["pill"])
    wp_l_btn.connect("clicked", lambda _b: _pick_single(page, "Choose Light Wallpaper",
                     lambda p: (set_wallpaper(str(p), "light"), wp_light_row.set_subtitle(str(p)))))
    wp_light_row.add_suffix(wp_l_btn)
    app_group.add(wp_light_row)

    wp_dark_row = Adw.ActionRow(use_markup=False, title="Dark Mode Wallpaper", subtitle=str(app_cfg["picture-uri-dark"] or "Default"))
    wp_d_btn = Gtk.Button(label="Choose Image", valign=Gtk.Align.CENTER, css_classes=["pill"])
    wp_d_btn.connect("clicked", lambda _b: _pick_single(page, "Choose Dark Wallpaper",
                     lambda p: (set_wallpaper(str(p), "dark"), wp_dark_row.set_subtitle(str(p)))))
    wp_dark_row.add_suffix(wp_d_btn)
    app_group.add(wp_dark_row)
    page.add(app_group)

    # 4. Display Resolution, Zoom & Scaling Adjustments
    _serial, monitors = get_monitors()
    disp_group = Adw.PreferencesGroup(
        title="Display Resolution &amp; Scaling",
        description="Adjust monitor resolution, refresh rate, and display zoom scale with automatic 15s revert safety.",
    )
    if not monitors:
        disp_group.add(Adw.ActionRow(use_markup=False, title="No active monitors detected"))
    else:
        for mon in monitors:
            mode_labels = [f"{m.width}x{m.height} @ {m.refresh:.0f}Hz ({m.mode_id})" for m in mon.modes]
            mode_ids = [m.mode_id for m in mon.modes]
            cur_idx = mode_ids.index(mon.current_mode) if mon.current_mode in mode_ids else 0
            cur_mode_obj = mon.modes[cur_idx] if mon.modes else None
            scales = [str(s) for s in (cur_mode_obj.supported_scales if cur_mode_obj else [1.0, 1.25, 1.5, 2.0])]

            mode_row = Adw.ComboRow(use_markup=False, title=f"Resolution ({mon.connector})",
                                    subtitle=f"Current: {mon.current_mode}",
                                    model=Gtk.StringList.new(mode_labels or [mon.current_mode]))
            mode_row.set_selected(cur_idx)

            scale_sel = Adw.ComboRow(use_markup=False, title=f"Display Scale ({mon.connector})",
                                     subtitle="Zoom ratio (1.0 = 100%, 1.25 = 125%, 2.0 = 200%)",
                                     model=Gtk.StringList.new(scales))
            cur_sc_str = str(round(mon.current_scale, 2))
            if cur_sc_str in scales:
                scale_sel.set_selected(scales.index(cur_sc_str))

            apply_row = Adw.ActionRow(use_markup=False, title=f"Apply to {mon.connector}",
                                      subtitle="Prompts confirmation; automatically reverts in 15s if not confirmed")
            apply_btn = Gtk.Button(label="Apply Display", valign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"])

            def on_apply_disp(_b, m=mon, m_ids=mode_ids, mr=mode_row, scs=scales, sr=scale_sel, ar=apply_row):
                prev_mode = m.current_mode
                prev_scale = m.current_scale
                new_mode = m_ids[mr.get_selected()] if m_ids else prev_mode
                new_scale = float(scs[sr.get_selected()])
                ok, msg = apply_monitor_config(m.connector, new_mode, new_scale)
                ar.set_subtitle(msg)
                if not ok:
                    return

                reverted = {"done": False}
                dlg = Adw.AlertDialog(
                    heading="Keep Display Settings?",
                    body="Reverting automatically in 15 seconds unless you confirm.",
                )
                dlg.add_response("revert", "Revert Now")
                dlg.add_response("keep", "Keep Changes")
                dlg.set_response_appearance("keep", Adw.ResponseAppearance.SUGGESTED)

                def on_resp(_d, resp):
                    reverted["done"] = True
                    if resp != "keep":
                        apply_monitor_config(m.connector, prev_mode, prev_scale)
                        ar.set_subtitle("Reverted display settings")

                dlg.connect("response", on_resp)
                root = page.get_root()
                if isinstance(root, Gtk.Window):
                    dlg.present(root)

                def timeout_revert():
                    if not reverted["done"]:
                        reverted["done"] = True
                        dlg.close()
                        apply_monitor_config(m.connector, prev_mode, prev_scale)
                        ar.set_subtitle("Auto-reverted display settings after 15s timeout")
                    return GLib.SOURCE_REMOVE

                GLib.timeout_add_seconds(15, timeout_revert)

            apply_btn.connect("clicked", on_apply_disp)
            apply_row.add_suffix(apply_btn)
            disp_group.add(mode_row)
            disp_group.add(scale_sel)
            disp_group.add(apply_row)
    page.add(disp_group)

    # 5. Sound Profiles & Notification Ringtones
    snd_cfg = get_sound_prefs()
    snd_themes = discover_sound_themes()
    snd_group = Adw.PreferencesGroup(
        title="Sound Profiles &amp; Notification Ringtones",
        description="Configure system sound profile themes, over-amplification, and custom notification chimes.",
    )
    snd_group.add(_combo("Sound Profile Theme", "System event sound theme", snd_themes,
                         str(snd_cfg["theme-name"]), lambda v: set_sound_pref("theme-name", v)))

    def _snd_sw(key: str, title: str, sub: str) -> Adw.SwitchRow:
        r = Adw.SwitchRow(use_markup=False, title=title, subtitle=sub)
        r.set_active(bool(snd_cfg[key]))
        r.connect("notify::active", lambda sw, _p: set_sound_pref(key, sw.get_active()))
        return r

    snd_group.add(_snd_sw("event-sounds", "System Event Alerts", "Play sound effects for desktop notifications and alerts"))
    snd_group.add(_snd_sw("input-feedback-sounds", "Input Feedback Sounds", "Play subtle clicks on button/UI interactions"))
    snd_group.add(_snd_sw("allow-volume-above-100-percent", "Allow Volume Over-Amplification", "Permit system volume boost past 100%"))

    cur_ring = str(store.get("notifications", "custom_ringtone", "") or "")
    ring_row = Adw.ActionRow(use_markup=False, title="Custom Notification Ringtone",
                             subtitle=cur_ring or "Using default sound theme chime")
    ring_pick = Gtk.Button(label="Choose Audio", valign=Gtk.Align.CENTER, css_classes=["pill"])
    ring_test = Gtk.Button(icon_name="media-playback-start-symbolic", valign=Gtk.Align.CENTER,
                           css_classes=["flat"], tooltip_text="Preview ringtone")

    def on_pick_ring(p: Path):
        store.set("notifications", "custom_ringtone", str(p))
        ring_row.set_subtitle(str(p))

    ring_pick.connect("clicked", lambda _b: _pick_single(page, "Choose Ringtone (.ogg / .wav)", on_pick_ring))
    ring_test.connect("clicked", lambda _b: preview_sound(str(store.get("notifications", "custom_ringtone", "") or "")))
    ring_row.add_suffix(ring_test)
    ring_row.add_suffix(ring_pick)
    snd_group.add(ring_row)
    page.add(snd_group)

    # 6. Notification Preferences & Per-App Permissions
    notif_cfg = get_notification_prefs()
    notif_group = Adw.PreferencesGroup(
        title="Desktop Notification Permissions",
        description="Control banner popups, lock-screen visibility, and per-application notification permissions.",
    )
    for key, title, sub in (
        ("show-banners", "Show Notification Banners", "Display desktop popup banners for incoming alerts"),
        ("show-in-lock-screen", "Show on Lock Screen", "Allow notification previews while workstation is locked"),
    ):
        sw = Adw.SwitchRow(use_markup=False, title=title, subtitle=sub)
        sw.set_active(bool(notif_cfg[key]))
        sw.connect("notify::active", lambda s, _p, k=key: set_notification_pref(k, s.get_active()))
        notif_group.add(sw)

    apps_exp = Adw.ExpanderRow(use_markup=False, title="Per-Application Notification Controls",
                               subtitle="Enable or silence notifications for individual apps")
    for app_pref in list_app_notifications():
        ar = Adw.SwitchRow(use_markup=False, title=app_pref.label, subtitle=app_pref.app_id)
        ar.set_active(app_pref.enabled)
        ar.connect("notify::active", lambda s, _p, aid=app_pref.app_id: set_app_notification_enabled(aid, s.get_active()))
        apps_exp.add_row(ar)
    notif_group.add(apps_exp)
    page.add(notif_group)

    return page
