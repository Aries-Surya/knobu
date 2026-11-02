"""Touchpad Gestures: multi-finger slide for volume, multi-finger taps for actions."""

import select
import threading

from knobu.modules.base import Module
from knobu.modules.touchpad.gestures import GestureConfig, GestureRecognizer
from knobu.system import media
from knobu.system.audio import Audio, system_max_volume
from knobu.system.osd import VolumeOsd

# Actions a tap can trigger: setting value -> label shown in the settings app.
TAP_ACTIONS = {
    "mute": "Mute / unmute",
    "play_pause": "Play / pause media",
    "next": "Next track",
    "previous": "Previous track",
    "none": "Nothing",
}
TAP_FINGERS = (3, 4)


class GestureActions:
    """Gesture listener: slides change volume, taps run the configured action."""

    def __init__(self, settings: dict, audio: Audio, osd: VolumeOsd, log):
        self.s = settings
        self.audio = audio
        self.osd = osd
        self.log = log
        self._base = 0
        self._max = 100
        self._last: int | None = None

    def max_volume(self) -> int:
        setting = self.s["max_volume"]
        return system_max_volume() if setting == "system" else int(setting)

    def on_drag_start(self) -> None:
        if not self.s["volume_drag"]:
            return
        self._base, muted = self.audio.get()
        self._max = self.max_volume()  # re-read so desktop setting changes apply at once
        if muted:
            self.audio.set_mute(False)
        self._last = None

    def on_drag(self, travel_mm: float) -> None:
        if not self.s["volume_drag"]:
            return
        sign = -1 if self.s["invert"] else 1
        delta = sign * travel_mm / 10 * self.s["percent_per_cm"]
        # Never pull a volume that's already above the limit down to it.
        limit = max(self._max, self._base)
        vol = max(0, min(limit, round(self._base + delta)))
        if vol != self._last:
            self.audio.set_volume(vol)
            self.osd.show(vol, self._max)
            self._last = vol

    def on_drag_end(self) -> None:
        if self.s["volume_drag"] and self._last is not None:
            self.log.info("volume %d%%", self._last)

    def on_tap(self, fingers: int) -> None:
        action = self.s.get(f"tap{fingers}_action", "none")
        if action == "mute":
            self.toggle_mute()
        elif action in ("play_pause", "next", "previous"):
            method = {"play_pause": "PlayPause", "next": "Next", "previous": "Previous"}[action]
            player = media.command(method)
            self.log.info("%s -> %s", method, player or "no media player running")

    def toggle_mute(self) -> None:
        vol, muted = self.audio.get()
        self.audio.set_mute(not muted)
        self.osd.show(vol if muted else 0, self.max_volume())
        self.log.info("unmuted" if muted else "muted")


class TouchpadModule(Module):
    id = "touchpad"
    name = "Touchpad Gestures"
    description = "Slide fingers on the touchpad to change volume, and tap to mute or control media."
    icon = "input-touchpad-symbolic"
    defaults = {
        "enabled": True,
        "fingers": 3,  # finger count for the volume slide
        "volume_drag": True,
        "percent_per_cm": 16,
        "invert": False,
        "max_volume": "system",  # or a number in percent
        "tap3_action": "mute",
        "tap4_action": "play_pause",
        "osd": True,
        "device": "",
    }

    def run(self, stop: threading.Event) -> None:
        # Imported here so the settings app can list this module without evdev access.
        from knobu.modules.touchpad import device

        s = self.settings
        actions = GestureActions(s, Audio(), VolumeOsd(s["osd"]), self.log)
        while not stop.is_set():
            try:
                dev = device.find_touchpad(s["device"])
                if dev is None:
                    self.log.warning("no touchpad found; retrying")
                    stop.wait(5)
                    continue
                self.log.info("listening on %s (%s)", dev.path, dev.name)
                recognizer = GestureRecognizer(
                    GestureConfig(drag_fingers=s["fingers"]), device.units_per_mm(dev), actions)
                tracker = device.FrameTracker(recognizer)
                try:
                    while not stop.is_set():
                        ready, _, _ = select.select([dev.fd], [], [], 0.5)
                        if ready:
                            for ev in dev.read():
                                tracker.feed(ev)
                finally:
                    dev.close()
            except OSError as err:
                # Device vanished (suspend/resume, driver reload) or access denied.
                self.log.warning("touchpad error: %s; retrying", err)
                stop.wait(2)
