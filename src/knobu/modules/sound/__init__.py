"""Per-App Volume Mixer & Sound Suite (Milestone 2): PipeWire/wpctl streams, mic mute, sink switcher."""

from __future__ import annotations

from dataclasses import dataclass
import re
import shutil
import subprocess
import threading

from knobu.modules.base import Module
from knobu.system import hotkeys, keys, launch, notify


@dataclass(frozen=True)
class AudioDevice:
    id: int
    name: str
    volume: int
    muted: bool
    is_default: bool


@dataclass(frozen=True)
class AudioStream:
    id: int
    app_name: str
    volume: int
    muted: bool


def _run_wpctl(*args: str) -> tuple[int, str]:
    if not shutil.which("wpctl"):
        return 1, ""
    try:
        r = subprocess.run(["wpctl", *args], capture_output=True, text=True, timeout=2, check=False)
        return r.returncode, r.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""


def _parse_vol_line(rest: str) -> tuple[int, bool]:
    m = re.search(r"\[vol:\s*([\d.]+)(\s+MUTED)?\]", rest)
    if not m:
        return 100, False
    return round(float(m.group(1)) * 100), bool(m.group(2))


def parse_wpctl_status(text: str) -> tuple[list[AudioDevice], list[AudioDevice], list[AudioStream]]:
    """Parse `wpctl status` output into (sinks, sources, playback_streams)."""
    sinks: list[AudioDevice] = []
    sources: list[AudioDevice] = []
    streams: list[AudioStream] = []

    section = ""
    subsection = ""
    for raw in text.splitlines():
        clean = raw.replace("├─", "").replace("│", "").replace("└─", "").strip()
        if clean in ("Audio", "Video", "Settings"):
            section = clean
            subsection = ""
            continue
        if section != "Audio":
            continue
        if clean.startswith(("Devices:", "Sinks:", "Sources:", "Filters:", "Streams:")):
            subsection = clean.rstrip(":")
            continue

        if subsection in ("Sinks", "Sources"):
            m = re.match(r"^(\*)?\s*(\d+)\.\s+(.+?)\s*(\[vol:.*\])?$", clean)
            if m:
                is_def = bool(m.group(1))
                dev_id = int(m.group(2))
                name = m.group(3).strip()
                vol, muted = _parse_vol_line(m.group(4) or "")
                dev = AudioDevice(id=dev_id, name=name, volume=vol, muted=muted, is_default=is_def)
                (sinks if subsection == "Sinks" else sources).append(dev)
        elif subsection == "Streams":
            # Stream header lines look like: "84. Chromium" (no '>' channel routing)
            if ">" in clean:
                continue
            m = re.match(r"^(\d+)\.\s+(.+)$", clean)
            if m:
                sid = int(m.group(1))
                app_name = m.group(2).strip()
                streams.append(AudioStream(id=sid, app_name=app_name, volume=100, muted=False))
    return sinks, sources, streams


def get_node_volume(node_id: int | str) -> tuple[int, bool]:
    rc, out = _run_wpctl("get-volume", str(node_id))
    if rc != 0:
        return 100, False
    m = re.search(r"([\d.]+)", out)
    return (round(float(m.group(1)) * 100) if m else 100), ("MUTED" in out)


def list_audio_state() -> tuple[list[AudioDevice], list[AudioDevice], list[AudioStream]]:
    rc, out = _run_wpctl("status")
    if rc != 0:
        return [], [], []
    sinks, sources, raw_streams = parse_wpctl_status(out)
    streams = []
    for st in raw_streams:
        vol, muted = get_node_volume(st.id)
        streams.append(AudioStream(id=st.id, app_name=st.app_name, volume=vol, muted=muted))
    return sinks, sources, streams


def set_stream_volume(node_id: int, percent: int) -> tuple[bool, str]:
    pct = max(0, min(150, int(percent)))
    rc, _ = _run_wpctl("set-volume", "-l", "1.5", str(node_id), f"{pct}%")
    return rc == 0, f"Set stream {node_id} volume to {pct}%"


def toggle_stream_mute(node_id: int) -> tuple[bool, str]:
    rc, _ = _run_wpctl("set-mute", str(node_id), "toggle")
    return rc == 0, f"Toggled mute for stream {node_id}"


def get_mic_status() -> tuple[int, bool]:
    return get_node_volume("@DEFAULT_AUDIO_SOURCE@")


def toggle_mic_mute() -> tuple[bool, str]:
    rc, _ = _run_wpctl("set-mute", "@DEFAULT_AUDIO_SOURCE@", "toggle")
    _vol, muted = get_mic_status()
    msg = "Microphone Muted" if muted else "Microphone Unmuted"
    return rc == 0, msg


def set_default_sink(sink_id: int) -> tuple[bool, str]:
    rc, _ = _run_wpctl("set-default", str(sink_id))
    return rc == 0, f"Switched default output to sink {sink_id}"


def cycle_output_sink() -> tuple[bool, str]:
    sinks, _, _ = list_audio_state()
    if len(sinks) < 2:
        name = sinks[0].name if sinks else "None"
        return False, f"Only one output device available ({name})"
    cur_idx = next((i for i, s in enumerate(sinks) if s.is_default), 0)
    nxt = sinks[(cur_idx + 1) % len(sinks)]
    ok, _ = set_default_sink(nxt.id)
    return ok, f"Output switched to {nxt.name}"


class SoundSuiteModule(Module):
    id = "sound"
    name = "Sound Suite"
    description = "Per-app volume mixer (up to 150%), global mic mute, output switcher, and headphone safety."
    icon = "audio-speakers-symbolic"
    defaults = {
        "enabled": True,
        "mic_mute_hotkey": "super+shift+a",
        "switch_output_hotkey": "super+shift+o",
        "auto_lower_on_disconnect": True,
        "safe_speaker_volume": 35,
        "block_bt_music_autostart": False,
        "blocked_music_apps": ["spotify", "rhythmbox", "vlc"],
    }

    def run(self, stop: threading.Event) -> None:
        bindings = []
        hot_map = [
            ("mic_mute_hotkey", self._on_mic_mute),
            ("switch_output_hotkey", self._on_switch_output),
        ]
        for key, fn in hot_map:
            raw = str(self.settings.get(key, "")).strip()
            if not raw:
                continue
            try:
                chord = keys.parse(raw)
                bindings.append(hotkeys.service().register(chord, fn))
                self.log.info("registered %s for %s", keys.pretty(raw), key)
            except ValueError as err:
                self.log.error("bad hotkey %s: %s", key, err)

        prev_sinks, _, _ = list_audio_state()
        prev_default = next((s.name for s in prev_sinks if s.is_default), "")

        try:
            while not stop.wait(4):
                sinks, _, _ = list_audio_state()
                cur_default = next((s.name for s in sinks if s.is_default), "")
                if prev_default and cur_default and cur_default != prev_default:
                    was_headphone = any(k in prev_default.lower() for k in ("headphone", "bluetooth", "bluez", "buds", "airpods"))
                    now_speaker = any(k in cur_default.lower() for k in ("speaker", "built-in", "analog"))
                    if bool(self.settings.get("auto_lower_on_disconnect", True)) and was_headphone and now_speaker:
                        safe_vol = int(self.settings.get("safe_speaker_volume", 35))
                        _run_wpctl("set-volume", "@DEFAULT_AUDIO_SINK@", f"{safe_vol}%")
                        notify.notify("Sound Safety", f"Headphones disconnected; speaker volume lowered to {safe_vol}%", timeout_ms=2500)
                if cur_default:
                    prev_default = cur_default
        finally:
            for b in bindings:
                hotkeys.service().unregister(b)

    def _on_mic_mute(self) -> None:
        _ok, msg = toggle_mic_mute()
        notify.notify("Microphone", msg, timeout_ms=2000)

    def _on_switch_output(self) -> None:
        ok, msg = cycle_output_sink()
        notify.notify("Audio Output", msg, timeout_ms=2000)
