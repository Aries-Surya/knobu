"""Desktop Status Tray (org.kde.StatusNotifierItem + com.canonical.dbusmenu) over Gio.DBus."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from pathlib import Path
import threading
import time

from gi.repository import Gio, GLib

from knobu import APP_ID, config, service
from knobu.modules.powertools.aws_cli import (
    get_active_aws_profile,
    load_aws_profiles,
    set_active_aws_profile,
)
from knobu.modules.powertools.network import NetworkStatus, fetch_public_ip, get_network_status
from knobu.system import launch, notify
from knobu.system.clipboard import set_clipboard

log = logging.getLogger("knobu.tray")

ICONS_DIR = str(Path(__file__).resolve().parent.parent / "ui" / "icons")
TRAY_BUS_NAME = f"{APP_ID}.Tray"
SNI_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"

SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <method name="Activate"><arg type="i" name="x" direction="in"/><arg type="i" name="y" direction="in"/></method>
    <method name="SecondaryActivate"><arg type="i" name="x" direction="in"/><arg type="i" name="y" direction="in"/></method>
    <signal name="NewIcon"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus"><arg type="s" name="status"/></signal>
  </interface>
</node>
"""

MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg type="i" name="parentId" direction="in"/>
      <arg type="i" name="recursionDepth" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="u" name="revision" direction="out"/>
      <arg type="(ia{sv}av)" name="layout" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="as" name="propertyNames" direction="in"/>
      <arg type="a(ia{sv})" name="properties" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="name" direction="in"/>
      <arg type="v" name="value" direction="out"/>
    </method>
    <method name="Event">
      <arg type="i" name="id" direction="in"/>
      <arg type="s" name="eventId" direction="in"/>
      <arg type="v" name="data" direction="in"/>
      <arg type="u" name="timestamp" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg type="a(isvu)" name="events" direction="in"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <method name="AboutToShow">
      <arg type="i" name="id" direction="in"/>
      <arg type="b" name="needUpdate" direction="out"/>
    </method>
    <method name="AboutToShowGroup">
      <arg type="ai" name="ids" direction="in"/>
      <arg type="ai" name="updatesNeeded" direction="out"/>
      <arg type="ai" name="idErrors" direction="out"/>
    </method>
    <signal name="LayoutUpdated"><arg type="u" name="revision"/><arg type="i" name="parent"/></signal>
    <signal name="ItemsPropertiesUpdated"><arg type="a(ia{sv})"/><arg type="a(ias)"/></signal>
  </interface>
</node>
"""


@dataclass
class MenuItem:
    id: int
    label: str = ""
    enabled: bool = True
    item_type: str = ""  # "", "separator"
    toggle_type: str = ""  # "", "checkmark", "radio"
    toggle_state: int = 0
    action: object = None
    children: list["MenuItem"] = field(default_factory=list)

    def signature(self) -> tuple:
        return (
            self.id,
            self.label,
            self.enabled,
            self.item_type,
            self.toggle_type,
            self.toggle_state,
            tuple(c.signature() for c in self.children),
        )

    def to_props(self) -> dict[str, GLib.Variant]:
        if self.item_type == "separator":
            return {"type": GLib.Variant("s", "separator")}
        props: dict[str, GLib.Variant] = {
            "label": GLib.Variant("s", self.label),
            "enabled": GLib.Variant("b", self.enabled),
            "visible": GLib.Variant("b", True),
        }
        if self.toggle_type:
            props["toggle-type"] = GLib.Variant("s", self.toggle_type)
            props["toggle-state"] = GLib.Variant("i", self.toggle_state)
        if self.children:
            props["children-display"] = GLib.Variant("s", "submenu")
        return props

    def to_variant(self, depth: int = -1) -> GLib.Variant:
        child_vars = (
            [c.to_variant(depth - 1 if depth > 0 else -1) for c in self.children]
            if (depth != 0 and self.children)
            else []
        )
        return GLib.Variant("(ia{sv}av)", (self.id, self.to_props(), child_vars))


class StatusTray:
    """Publishes Knobu's top-bar StatusNotifierItem and dynamic configuration dropdown."""

    def __init__(self, history=None, show_public_ip: bool = True):
        if history is None:
            from knobu.modules.notifications.store import NotificationHistory
            history = NotificationHistory()
        self.history = history
        self.show_public_ip = show_public_ip
        self._conn: Gio.DBusConnection | None = None
        self._sni_reg = 0
        self._menu_reg = 0
        self._name_id = 0
        self._watch_id = 0
        self._revision = 1
        self._net = NetworkStatus("Checking...", "network", "", "...")
        self._public_ip: str = "..."
        self._last_ip_fetch = 0.0
        self._items_by_id: dict[int, MenuItem] = {}
        self._root = MenuItem(0)
        self._last_sig: tuple = ()
        self._lock = threading.Lock()

    def start(self) -> None:
        self._conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        sni_info = Gio.DBusNodeInfo.new_for_xml(SNI_XML).interfaces[0]
        menu_info = Gio.DBusNodeInfo.new_for_xml(MENU_XML).interfaces[0]

        self._sni_reg = self._conn.register_object(
            SNI_PATH, sni_info, self._on_sni_call, self._on_sni_get_prop, None
        )
        self._menu_reg = self._conn.register_object(
            MENU_PATH, menu_info, self._on_menu_call, self._on_menu_get_prop, None
        )
        self._name_id = Gio.bus_own_name_on_connection(
            self._conn, TRAY_BUS_NAME, Gio.BusNameOwnerFlags.NONE, None, None
        )
        self._watch_id = Gio.bus_watch_name_on_connection(
            self._conn,
            "org.kde.StatusNotifierWatcher",
            Gio.BusNameWatcherFlags.NONE,
            lambda *_a: self._register_watcher(),
            None,
        )
        self.rebuild_menu()
        self.refresh_network_async(force_public=True)

    def stop(self) -> None:
        if self._watch_id:
            Gio.bus_unwatch_name(self._watch_id)
            self._watch_id = 0
        if self._name_id:
            Gio.bus_unown_name(self._name_id)
            self._name_id = 0
        if self._conn:
            if self._sni_reg:
                self._conn.unregister_object(self._sni_reg)
                self._sni_reg = 0
            if self._menu_reg:
                self._conn.unregister_object(self._menu_reg)
                self._menu_reg = 0
            self._conn = None

    def _register_watcher(self) -> None:
        if not self._conn:
            return
        try:
            self._conn.call_sync(
                "org.kde.StatusNotifierWatcher",
                "/StatusNotifierWatcher",
                "org.kde.StatusNotifierWatcher",
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (SNI_PATH,)),
                None,
                Gio.DBusCallFlags.NONE,
                2000,
                None,
            )
            log.info("registered StatusNotifierItem at %s", SNI_PATH)
        except GLib.Error as err:
            log.debug("StatusNotifierWatcher registration skipped: %s", err)

    def refresh_network_async(self, force_public: bool = False) -> None:
        def worker():
            net = get_network_status()
            pub = self._public_ip
            now = time.monotonic()
            if self.show_public_ip and (force_public or (now - self._last_ip_fetch) > 90 or pub in ("...", "Offline")):
                fetched = fetch_public_ip()
                pub = fetched or "Offline"
                self._last_ip_fetch = now
            elif not self.show_public_ip:
                pub = "Disabled"
            with self._lock:
                self._net = net
                self._public_ip = pub
            GLib.idle_add(self._emit_layout_if_changed)
        threading.Thread(target=worker, name="tray-net", daemon=True).start()

    def _emit_layout_if_changed(self) -> bool:
        changed = self._rebuild_if_changed()
        if changed and self._conn:
            try:
                self._conn.emit_signal(
                    None, MENU_PATH, "com.canonical.dbusmenu", "LayoutUpdated",
                    GLib.Variant("(ui)", (self._revision, 0)),
                )
            except GLib.Error:
                pass
        return GLib.SOURCE_REMOVE

    def _refresh_and_copy_private_ip(self) -> None:
        net = get_network_status()
        with self._lock:
            self._net = net
        GLib.idle_add(self._emit_layout_if_changed)
        self._copy_with_toast("Private IP", net.private_ip)

    def _refresh_and_copy_public_ip(self) -> None:
        if not self.show_public_ip:
            return
        ip = fetch_public_ip() or "Offline"
        with self._lock:
            self._public_ip = ip
            self._last_ip_fetch = time.monotonic()
        GLib.idle_add(self._emit_layout_if_changed)
        self._copy_with_toast("Public IP", ip)

    def _copy_with_toast(self, label: str, value: str) -> None:
        if not value or value in ("...", "Unavailable", "Offline", "Disabled"):
            return
        set_clipboard(value)
        notify.notify("Copied to Clipboard", f"{label}: {value}", timeout_ms=2000)

    def _toggle_bypass(self) -> None:
        data = config.load()
        gen = data.setdefault("general", {})
        gen["bypass"] = not bool(gen.get("bypass", False))
        config.save(data)
        service.reload()
        GLib.idle_add(self._emit_layout_if_changed)

    def _set_awake(self, mode: str, minutes: int = 0) -> None:
        data = config.load()
        s = data.setdefault("awake", {})
        if mode == "off":
            s["enabled"] = False
        elif mode == "indefinite":
            s.update(enabled=True, mode="indefinite")
        else:
            s.update(enabled=True, mode="timed", minutes=minutes, until=time.time() + minutes * 60)
        config.save(data)
        service.reload()
        GLib.idle_add(self._emit_layout_if_changed)

    def _toggle_dnd(self) -> None:
        data = config.load()
        s = data.setdefault("notifications", {})
        s["dnd"] = not bool(s.get("dnd", False))
        config.save(data)
        service.reload()
        GLib.idle_add(self._emit_layout_if_changed)

    def _switch_aws(self, name: str, region: str) -> None:
        ok, msg = set_active_aws_profile(name, region)
        notify.notify("AWS CLI Profile" if ok else "AWS CLI Error", msg, timeout_ms=2500)
        GLib.idle_add(self._emit_layout_if_changed)

    def rebuild_menu(self) -> MenuItem:
        self._rebuild_if_changed()
        with self._lock:
            return self._root

    def _rebuild_if_changed(self) -> bool:
        """Build menu tree with deterministic fixed IDs; returns True only if layout changed."""
        cfg = config.load()
        bypassed = bool(cfg.get("general", {}).get("bypass", False))
        dnd = bool(cfg.get("notifications", {}).get("dnd", False))
        awake_cfg = cfg.get("awake", {})
        awake_on = bool(awake_cfg.get("enabled", False))
        awake_mode = awake_cfg.get("mode", "indefinite") if awake_on else "off"
        aws_active = get_active_aws_profile()
        aws_profiles = load_aws_profiles()
        recent_notifs = self.history.list_recent(limit=6)

        with self._lock:
            net = self._net
            pub = self._public_ip

        by_id: dict[int, MenuItem] = {}

        def item(item_id: int, label: str = "", enabled: bool = True, item_type: str = "",
                 toggle_type: str = "", toggle_state: int = 0, action=None,
                 children: list[MenuItem] | None = None) -> MenuItem:
            m = MenuItem(
                id=item_id, label=label, enabled=enabled, item_type=item_type,
                toggle_type=toggle_type, toggle_state=toggle_state, action=action,
                children=children or [],
            )
            by_id[item_id] = m
            return m

        status_lbl = f"Knobu · {'Bypassed' if bypassed else 'Active'}"
        if awake_on:
            status_lbl += " · Awake"

        conn_prefix = {"wifi": "Wi-Fi", "ethernet": "Ethernet", "tun": "VPN"}.get(net.connection_type, "Network")
        net_label = f"{conn_prefix}: {net.connection_name}"
        if net.vpn_ip:
            net_label += f" (VPN {net.vpn_ip})"

        aws_children = []
        if aws_profiles:
            for idx, prof in enumerate(aws_profiles[:40]):
                reg = f" ({prof.region})" if prof.region else ""
                aws_children.append(item(
                    100 + idx,
                    f"{prof.name}{reg}",
                    toggle_type="radio",
                    toggle_state=1 if prof.name == aws_active else 0,
                    action=lambda p=prof: self._switch_aws(p.name, p.region),
                ))
        else:
            aws_children.append(item(199, "No ~/.aws/config profiles found", enabled=False))

        notif_children = [
            item(401, "Open Notification Center", action=lambda: launch.knobu("notifications")),
            item(402, "Clear All Notifications", action=lambda: (self.history.clear(), GLib.idle_add(self._emit_layout_if_changed))),
            item(403, item_type="separator"),
        ]
        if recent_notifs:
            for idx, n in enumerate(recent_notifs):
                t_str = time.strftime("%-I:%M %p", time.localtime(n.timestamp))
                summary = (n.summary[:42] + "...") if len(n.summary) > 42 else n.summary
                notif_children.append(item(410 + idx, f"[{t_str}] {n.app_name}: {summary}", enabled=False))
        else:
            notif_children.append(item(499, "No recent notifications", enabled=False))

        children = [
            item(1, status_lbl, enabled=False),
            item(2, item_type="separator"),
            item(3, net_label, enabled=False),
            item(4, f"Private IP: {net.private_ip}  ⟳ Copy",
                 action=self._refresh_and_copy_private_ip),
            item(5, f"Public IP: {pub}  ⟳ Copy",
                 action=self._refresh_and_copy_public_ip),
            item(7, item_type="separator"),
            item(10, f"AWS Profile: {aws_active}", children=aws_children),
            item(11, item_type="separator"),
            item(20, "Master Bypass Mode", toggle_type="checkmark", toggle_state=1 if bypassed else 0,
                 action=self._toggle_bypass),
            item(21, "Awake", children=[
                item(210, "Off", toggle_type="radio", toggle_state=1 if not awake_on else 0,
                     action=lambda: self._set_awake("off")),
                item(211, "Indefinite", toggle_type="radio", toggle_state=1 if (awake_on and awake_mode == "indefinite") else 0,
                     action=lambda: self._set_awake("indefinite")),
                item(212, "30 Minutes", action=lambda: self._set_awake("timed", 30)),
                item(213, "1 Hour", action=lambda: self._set_awake("timed", 60)),
                item(214, "2 Hours", action=lambda: self._set_awake("timed", 120)),
            ]),
            item(22, "Do Not Disturb (HUD)", toggle_type="checkmark", toggle_state=1 if dnd else 0,
                 action=self._toggle_dnd),
            item(23, item_type="separator"),
            item(30, "Quick Tools", children=[
                item(301, "Command Bar (Alt+Space)", action=lambda: launch.knobu("command-bar")),
                item(302, "Clipboard History (Super+V)", action=lambda: launch.knobu("clipboard")),
                item(303, "Cleaning Mode (Super+Alt+K)", action=lambda: launch.knobu("cleaning-mode")),
                item(304, "Screen Ruler (Super+Shift+M)", action=lambda: launch.knobu("screen-ruler")),
                item(305, "Find My Mouse (Super+Alt+F)", action=lambda: launch.knobu("find-mouse")),
                item(306, "Color Picker", action=lambda: launch.knobu("pick-color")),
                item(307, "Text Extractor", action=lambda: launch.knobu("extract-text")),
            ]),
            item(40, f"Notifications ({len(recent_notifs)})", children=notif_children),
            item(41, item_type="separator"),
            item(90, "Open Knobu Settings", action=lambda: launch.knobu()),
            item(91, "Reload Knobu Service", action=service.reload),
        ]

        root = MenuItem(0, children=children)
        by_id[0] = root
        new_sig = root.signature()

        with self._lock:
            changed = new_sig != self._last_sig
            self._root = root
            self._items_by_id = by_id
            if changed:
                self._last_sig = new_sig
                self._revision += 1
        return changed

    def _on_sni_get_prop(self, _conn, _sender, _path, _iface, prop: str) -> GLib.Variant | None:
        net = self._net
        props = {
            "Category": GLib.Variant("s", "SystemServices"),
            "Id": GLib.Variant("s", "knobu"),
            "Title": GLib.Variant("s", "Knobu"),
            "Status": GLib.Variant("s", "Active"),
            "IconName": GLib.Variant("s", "knobu-dashboard-symbolic"),
            "IconThemePath": GLib.Variant("s", ICONS_DIR),
            "Menu": GLib.Variant("o", MENU_PATH),
            "ItemIsMenu": GLib.Variant("b", True),
            "ToolTip": GLib.Variant(
                "(sa(iiay)ss)",
                ("knobu-dashboard-symbolic", [], "Knobu", f"{net.connection_name} · Private {net.private_ip}"),
            ),
        }
        return props.get(prop)

    def _on_sni_call(self, _conn, _sender, _path, _iface, method: str, _params, invocation) -> None:
        if method in ("Activate", "SecondaryActivate"):
            self.refresh_network_async(force_public=False)
        invocation.return_value(None)

    def _on_menu_get_prop(self, _conn, _sender, _path, _iface, prop: str) -> GLib.Variant | None:
        props = {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", [ICONS_DIR]),
        }
        return props.get(prop)

    def _dispatch_action(self, item_id: int) -> None:
        with self._lock:
            it = self._items_by_id.get(item_id)
            act = it.action if it else None
        if callable(act):
            def run_safe():
                try:
                    act()
                except Exception as err:
                    log.warning("tray action %d failed: %s", item_id, err)
            threading.Thread(target=run_safe, daemon=True).start()

    def _on_menu_call(self, _conn, _sender, _path, _iface, method: str, params, invocation) -> None:
        if method == "AboutToShow":
            item_id = params.unpack()[0]
            changed = False
            if item_id == 0:
                changed = self._rebuild_if_changed()
                if (time.monotonic() - self._last_ip_fetch) > 60:
                    self.refresh_network_async(force_public=False)
            invocation.return_value(GLib.Variant("(b)", (changed,)))
        elif method == "AboutToShowGroup":
            ids = params.unpack()[0]
            changed = self._rebuild_if_changed() if 0 in ids else False
            invocation.return_value(GLib.Variant("(aiai)", ([0] if changed else [], [])))
        elif method == "GetLayout":
            parent_id, depth, _prop_names = params.unpack()
            with self._lock:
                node = self._items_by_id.get(parent_id, self._root)
                rev = self._revision
                layout_var = node.to_variant(depth)
            invocation.return_value(GLib.Variant.new_tuple(GLib.Variant.new_uint32(rev), layout_var))
        elif method == "GetGroupProperties":
            ids, _prop_names = params.unpack()
            with self._lock:
                res = [(i, self._items_by_id[i].to_props()) for i in ids if i in self._items_by_id]
            invocation.return_value(GLib.Variant("(a(ia{sv}))", (res,)))
        elif method == "GetProperty":
            item_id, name = params.unpack()
            with self._lock:
                it = self._items_by_id.get(item_id)
                val = it.to_props().get(name, GLib.Variant("s", "")) if it else GLib.Variant("s", "")
            invocation.return_value(GLib.Variant("(v)", (val,)))
        elif method == "Event":
            item_id, ev_id, _data, _ts = params.unpack()
            if ev_id == "clicked":
                self._dispatch_action(item_id)
            invocation.return_value(None)
        elif method == "EventGroup":
            events = params.unpack()[0]
            for item_id, ev_id, _data, _ts in events:
                if ev_id == "clicked":
                    self._dispatch_action(item_id)
            invocation.return_value(GLib.Variant("(ai)", ([],)))
        else:
            invocation.return_value(None)
