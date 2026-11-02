"""Media player control over MPRIS, the D-Bus interface every Linux desktop player speaks
(Spotify, browsers, VLC, Rhythmbox, Elisa, ...). Works the same on every flavour."""

import subprocess

PREFIX = "org.mpris.MediaPlayer2."
PATH = "/org/mpris/MediaPlayer2"
IFACE = "org.mpris.MediaPlayer2.Player"


def _busctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["busctl", "--user", *args], capture_output=True, text=True,
                          timeout=2, check=False)


def players() -> list[str]:
    out = _busctl("list", "--no-pager", "--no-legend").stdout
    return [line.split()[0] for line in out.splitlines() if line.startswith(PREFIX)]


def status(player: str) -> str:
    """'Playing', 'Paused', 'Stopped', or '' if the player won't say."""
    r = _busctl("get-property", player, PATH, IFACE, "PlaybackStatus")
    return r.stdout.split('"')[1] if r.returncode == 0 and '"' in r.stdout else ""


def active_player() -> str | None:
    """The player a play/pause should go to: whatever is playing, else the paused one."""
    found = {status(p): p for p in reversed(players())}  # first match wins per status
    return found.get("Playing") or found.get("Paused") or next(iter(found.values()), None)


def command(method: str) -> str | None:
    """Send PlayPause / Next / Previous to the active player; returns its name."""
    player = active_player()
    if player:
        _busctl("call", player, PATH, IFACE, method)
    return player
