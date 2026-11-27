// Knobu Window Bridge — GNOME Shell extension (GNOME 45+, ESM).
// Exposes org.knobu.WindowBridge on session D-Bus for native Wayland window control.

import Gio from 'gi://Gio';
import Meta from 'gi://Meta';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

const BUS_NAME = 'org.knobu.WindowBridge';
const OBJECT_PATH = '/org/knobu/WindowBridge';

const IFACE_XML = `
<node>
  <interface name="org.knobu.WindowBridge">
    <method name="ToggleAlwaysOnTop">
      <arg type="b" direction="out" name="ok"/>
      <arg type="s" direction="out" name="message"/>
    </method>
    <method name="SnapWindow">
      <arg type="i" direction="in" name="x"/>
      <arg type="i" direction="in" name="y"/>
      <arg type="i" direction="in" name="w"/>
      <arg type="i" direction="in" name="h"/>
      <arg type="b" direction="out" name="ok"/>
      <arg type="s" direction="out" name="message"/>
    </method>
    <method name="MaximizeWindow">
      <arg type="b" direction="out" name="ok"/>
      <arg type="s" direction="out" name="message"/>
    </method>
    <method name="GetFocusedTitle">
      <arg type="s" direction="out" name="title"/>
    </method>
    <method name="GetCursorPosition">
      <arg type="i" direction="out" name="x"/>
      <arg type="i" direction="out" name="y"/>
    </method>
  </interface>
</node>`;

function activeWindow() {
    const win = global.display.get_focus_window();
    if (win)
        return win;
    try {
        const ws = global.workspace_manager.get_active_workspace();
        const list = global.display.get_tab_list(Meta.TabList.NORMAL, ws);
        for (const w of list) {
            if (w && w.window_type === Meta.WindowType.NORMAL && !w.is_skip_taskbar())
                return w;
        }
    } catch (e) {}
    return null;
}

export default class KnobuWindowBridgeExtension extends Extension {
    enable() {
        this._dbusImpl = Gio.DBusExportedObject.wrapJSObject(IFACE_XML, this);
        this._dbusImpl.export(Gio.DBus.session, OBJECT_PATH);
        this._ownerId = Gio.bus_own_name(
            Gio.BusType.SESSION,
            BUS_NAME,
            Gio.BusNameOwnerFlags.NONE,
            null,
            null,
            null
        );
    }

    disable() {
        if (this._ownerId) {
            Gio.bus_unown_name(this._ownerId);
            this._ownerId = 0;
        }
        if (this._dbusImpl) {
            this._dbusImpl.unexport();
            this._dbusImpl = null;
        }
    }

    ToggleAlwaysOnTop() {
        const win = activeWindow();
        if (!win)
            return [false, 'No active window'];
        const title = win.get_title() || 'Window';
        if (win.is_above()) {
            win.unmake_above();
            return [true, `Unpinned ${title}`];
        }
        win.make_above();
        return [true, `Pinned ${title} Always on Top`];
    }

    SnapWindow(x, y, w, h) {
        const win = activeWindow();
        if (!win)
            return [false, 'No active window'];
        try {
            if (win.get_maximized())
                win.unmaximize(Meta.MaximizeFlags.BOTH);
            win.move_resize_frame(true, x, y, w, h);
            return [true, `Snapped ${win.get_title() || 'window'}`];
        } catch (e) {
            return [false, String(e)];
        }
    }

    MaximizeWindow() {
        const win = activeWindow();
        if (!win)
            return [false, 'No active window'];
        try {
            win.maximize(Meta.MaximizeFlags.BOTH);
            return [true, `Maximized ${win.get_title() || 'window'}`];
        } catch (e) {
            return [false, String(e)];
        }
    }

    GetFocusedTitle() {
        const win = activeWindow();
        return win ? (win.get_title() || '') : '';
    }

    GetCursorPosition() {
        const [x, y] = global.get_pointer();
        return [Math.round(x), Math.round(y)];
    }
}
