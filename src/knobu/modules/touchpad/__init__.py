"""Touchpad Gestures: Windows Precision-style 3-finger and 4-finger swipes and taps."""

import logging
import select
import threading
import time

import evdev
from evdev import ecodes as e

from knobu.modules.base import Module
from knobu.modules.touchpad.gestures import GestureConfig, GestureRecognizer
from knobu.system import launch, media
from knobu.system.audio import Audio, system_max_volume
from knobu.system.osd import VolumeOsd

log = logging.getLogger("knobu.touchpad")

GESTURE_ACTIONS = {
    "volume_slide": "Volume Slide (Smooth continuous)",
    "volume_up": "Volume Up (+5%)",
    "volume_down": "Volume Down (-5%)",
    "mute": "Mute / Unmute",
    "play_pause": "Play / Pause Media",
    "next_track": "Next Track",
    "previous_track": "Previous Track",
    "overview": "Overview / Task View (Super)",
    "show_desktop": "Show Desktop (Super+D)",
    "workspace_left": "Switch Workspace Left",
    "workspace_right": "Switch Workspace Right",
    "workspace_up": "Switch Workspace Up",
    "workspace_down": "Switch Workspace Down",
    "switch_app": "Next Application (Alt+Tab)",
    "switch_app_prev": "Previous Application (Alt+Shift+Tab)",
    "command_bar": "Command Bar (Alt+Space)",
    "none": "Nothing",
}

TAP_ACTIONS = {
    "mute": "Mute / Unmute",
    "play_pause": "Play / Pause Media",
    "next_track": "Next Track",
    "previous_track": "Previous Track",
    "overview": "Overview / Task View (Super)",
    "show_desktop": "Show Desktop (Super+D)",
    "command_bar": "Command Bar (Alt+Space)",
    "none": "Nothing",
}


class GestureActions:
    """Dispatches touchpad swipes, continuous drags, and taps to desktop actions."""

    def __init__(self, settings: dict, audio: Audio, osd: VolumeOsd, logger=None):
        self.s = settings
        self.audio = audio
        self.osd = osd
        self.log = logger or log
        self._base = 0
        self._max = 100
        self._last: int | None = None
        self._uinput: evdev.UInput | None = None

    def max_volume(self) -> int:
        setting = self.s.get("max_volume", "system")
        return system_max_volume() if setting == "system" else int(setting)

    def _get_uinput(self) -> evdev.UInput | None:
        if self._uinput is None:
            try:
                keys = [
                    e.KEY_LEFTMETA, e.KEY_LEFTCTRL, e.KEY_LEFTALT, e.KEY_LEFTSHIFT,
                    e.KEY_D, e.KEY_TAB, e.KEY_LEFT, e.KEY_RIGHT, e.KEY_UP, e.KEY_DOWN,
                    e.KEY_PAGEUP, e.KEY_PAGEDOWN, e.KEY_SPACE, e.KEY_S,
                ]
                self._uinput = evdev.UInput({e.EV_KEY: keys}, name="Knobu Gesture Injector")
            except Exception as err:
                self.log.warning("cannot initialize uinput for gesture actions: %s", err)
                self._uinput = None
        return self._uinput

    def emit_keys(self, key_codes: list[int]) -> None:
        ui = self._get_uinput()
        if not ui:
            return
        for k in key_codes:
            ui.write(e.EV_KEY, k, 1)
        ui.syn()
        time.sleep(0.015)
        for k in reversed(key_codes):
            ui.write(e.EV_KEY, k, 0)
        ui.syn()

    def execute_action(self, action: str) -> None:
        if action == "volume_up":
            vol, muted = self.audio.get()
            if muted:
                self.audio.set_mute(False)
            new_vol = min(self.max_volume(), vol + 5)
            self.audio.set_volume(new_vol)
            self.osd.show(new_vol, self.max_volume())
            self.log.info("gesture volume up: %d%%", new_vol)
        elif action == "volume_down":
            vol, muted = self.audio.get()
            if muted:
                self.audio.set_mute(False)
            new_vol = max(0, vol - 5)
            self.audio.set_volume(new_vol)
            self.osd.show(new_vol, self.max_volume())
            self.log.info("gesture volume down: %d%%", new_vol)
        elif action == "mute":
            self.toggle_mute()
        elif action in ("play_pause", "next", "previous", "next_track", "previous_track"):
            cmd_map = {
                "play_pause": "PlayPause",
                "next": "Next",
                "next_track": "Next",
                "previous": "Previous",
                "previous_track": "Previous",
            }
            method = cmd_map.get(action, "PlayPause")
            player = media.command(method)
            self.log.info("gesture %s -> %s", method, player or "no media player")
        elif action == "overview":
            self.emit_keys([e.KEY_LEFTMETA])
            self.log.info("gesture: toggle overview (Super)")
        elif action == "show_desktop":
            self.emit_keys([e.KEY_LEFTMETA, e.KEY_D])
            self.log.info("gesture: show desktop (Super+D)")
        elif action in ("workspace_left", "workspace_up"):
            self.emit_keys([e.KEY_LEFTMETA, e.KEY_PAGEUP])
            self.log.info("gesture: workspace left/up (Super+PageUp)")
        elif action in ("workspace_right", "workspace_down"):
            self.emit_keys([e.KEY_LEFTMETA, e.KEY_PAGEDOWN])
            self.log.info("gesture: workspace right/down (Super+PageDown)")
        elif action == "switch_app":
            self.emit_keys([e.KEY_LEFTALT, e.KEY_TAB])
            self.log.info("gesture: switch app (Alt+Tab)")
        elif action == "switch_app_prev":
            self.emit_keys([e.KEY_LEFTALT, e.KEY_LEFTSHIFT, e.KEY_TAB])
            self.log.info("gesture: switch app prev (Alt+Shift+Tab)")
        elif action == "command_bar":
            launch.knobu("command-bar")
            self.log.info("gesture: open command bar")

    def on_swipe(self, fingers: int, direction: str) -> None:
        key = f"swipe{fingers}_{direction}"
        action = self.s.get(key, "none")
        if action and action != "none" and action != "volume_slide":
            self.log.info("%d-finger swipe %s -> %s", fingers, direction, action)
            self.execute_action(action)

    def on_drag_start(self, fingers: int = 3) -> None:
        up_act = self.s.get(f"swipe{fingers}_up", "volume_slide" if fingers == 3 else "none")
        down_act = self.s.get(f"swipe{fingers}_down", "volume_slide" if fingers == 3 else "none")
        if up_act == "volume_slide" or down_act == "volume_slide":
            self._base, muted = self.audio.get()
            self._max = self.max_volume()
            if muted:
                self.audio.set_mute(False)
            self._last = None

    def on_drag(self, fingers: int = 3, travel_mm: float = 0.0) -> None:
        up_act = self.s.get(f"swipe{fingers}_up", "volume_slide" if fingers == 3 else "none")
        down_act = self.s.get(f"swipe{fingers}_down", "volume_slide" if fingers == 3 else "none")
        if up_act == "volume_slide" or down_act == "volume_slide":
            sign = -1 if self.s.get("invert", False) else 1
            delta = sign * travel_mm / 10 * self.s.get("percent_per_cm", 16)
            limit = max(self._max, self._base)
            vol = max(0, min(limit, round(self._base + delta)))
            if vol != self._last:
                self.audio.set_volume(vol)
                self.osd.show(vol, self._max)
                self._last = vol

    def on_drag_end(self, fingers: int = 3) -> None:
        if self._last is not None:
            self.log.info("volume %d%%", self._last)

    def on_tap(self, fingers: int) -> None:
        action = self.s.get(f"tap{fingers}_action", "none")
        if action and action != "none":
            self.log.info("%d-finger tap -> %s", fingers, action)
            self.execute_action(action)

    def toggle_mute(self) -> None:
        vol, muted = self.audio.get()
        self.audio.set_mute(not muted)
        self.osd.show(vol if muted else 0, self.max_volume())
        self.log.info("unmuted" if muted else "muted")

    def close(self) -> None:
        if self._uinput:
            try:
                self._uinput.close()
            except Exception:
                pass
            self._uinput = None


class TouchpadModule(Module):
    id = "touchpad"
    name = "Touchpad Gestures"
    description = "Windows Precision-style 3-finger and 4-finger swipes for volume, multitasking, and media."
    icon = "knobu-touchpad-symbolic"
    defaults = {
        "enabled": True,
        "bypass": False,
        "grab_gestures": True,
        "percent_per_cm": 16,
        "invert": False,
        "max_volume": "system",
        "osd": True,
        "device": "",
        # 3-Finger Gestures (Media & Volume)
        "swipe3_up": "volume_slide",
        "swipe3_down": "volume_slide",
        "swipe3_left": "previous_track",
        "swipe3_right": "next_track",
        "tap3_action": "mute",
        # 4-Finger Gestures (Multitasking & Workspaces)
        "swipe4_up": "overview",
        "swipe4_down": "show_desktop",
        "swipe4_left": "workspace_left",
        "swipe4_right": "workspace_right",
        "tap4_action": "play_pause",
    }

    def run(self, stop: threading.Event) -> None:
        if bool(self.settings.get("bypass", False)):
            self.log.info("Touchpad Gestures bypassed by user configuration")
            return

        from knobu.modules.touchpad import device

        s = self.settings
        actions = GestureActions(s, Audio(), VolumeOsd(s.get("osd", True)), self.log)

        # Collect finger counts configured for continuous drag
        drag_fingers = set()
        for f in (3, 4):
            if s.get(f"swipe{f}_up") == "volume_slide" or s.get(f"swipe{f}_down") == "volume_slide":
                drag_fingers.add(f)

        while not stop.is_set():
            try:
                dev = device.find_touchpad(s.get("device", ""))
                if dev is None:
                    self.log.warning("no touchpad found; retrying")
                    stop.wait(5)
                    continue

                self.log.info("listening on %s (%s)", dev.path, dev.name)
                recognizer = GestureRecognizer(
                    GestureConfig(drag_fingers=drag_fingers),
                    device.units_per_mm(dev),
                    actions,
                )
                tracker = device.FrameTracker(recognizer)

                grab_gestures = bool(s.get("grab_gestures", True))
                grabbed = False

                try:
                    while not stop.is_set():
                        ready, _, _ = select.select([dev.fd], [], [], 0.3)
                        if ready:
                            for ev in dev.read():
                                tracker.feed(ev)
                                if grab_gestures:
                                    if tracker.fingers in (3, 4) and not grabbed:
                                        try:
                                            dev.grab()
                                            grabbed = True
                                        except OSError as e:
                                            self.log.debug("touchpad grab failed: %s", e)
                                    elif tracker.fingers < 3 and grabbed:
                                        try:
                                            dev.ungrab()
                                        except OSError:
                                            pass
                                        grabbed = False
                finally:
                    if grabbed:
                        try:
                            dev.ungrab()
                        except OSError:
                            pass
                    actions.close()
                    dev.close()
            except OSError as err:
                self.log.warning("touchpad error: %s; retrying", err)
                stop.wait(2)
