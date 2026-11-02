"""Command line entry point: `knobu` opens the settings app; subcommands for the rest."""

import argparse
import re
import sys
import time

from knobu import __version__


def parse_duration(text: str) -> int:
    """'90' / '90m' -> 90 minutes, '2h' -> 120, '1h30m' -> 90."""
    m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m?)?", text.strip().lower())
    if not m or not any(m.groups()):
        raise argparse.ArgumentTypeError(f"not a duration: {text!r} (try 30m, 2h or 1h30m)")
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)


def awake(arg: str) -> None:
    from knobu import config, service
    data = config.load()
    s = data.setdefault("awake", {})
    if arg == "off":
        s["enabled"] = False
        msg = "Awake is off."
    elif arg == "on":
        s.update(enabled=True, mode="indefinite")
        msg = "Keeping awake until you run `knobu awake off`."
    else:
        minutes = parse_duration(arg)
        until = time.time() + minutes * 60
        s.update(enabled=True, mode="timed", minutes=minutes, until=until)
        msg = time.strftime("Keeping awake until %H:%M.", time.localtime(until))
    config.save(data)
    if not service.is_active():
        msg += " (The Knobu service isn't running; start it with `knobu enable`.)"
    service.reload()
    print(msg)


def main() -> None:
    parser = argparse.ArgumentParser(prog="knobu", description="PowerToys-style utilities for Ubuntu")
    parser.add_argument("--version", action="version", version=f"knobu {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("settings", help="open the settings app (default)")
    sub.add_parser("daemon", help="run the background service in the foreground")
    sub.add_parser("status", help="show whether the background service is running")
    sub.add_parser("enable", help="start the background service now and at every login")
    sub.add_parser("disable", help="stop the background service and remove it from login")
    p = sub.add_parser("awake", help="keep the computer awake: on, off, or a duration (30m, 2h)")
    p.add_argument("state", help="on | off | DURATION")
    sub.add_parser("pick-color", help="pick a colour from the screen")
    sub.add_parser("extract-text", help="select a screen area and copy its text")
    args = parser.parse_args()

    if args.command == "daemon":
        from knobu.daemon import main as daemon_main
        daemon_main()
    elif args.command == "status":
        from knobu import service
        print(f"service: {'running' if service.is_active() else 'stopped'}, "
              f"start at login: {'yes' if service.is_enabled() else 'no'}")
    elif args.command == "enable":
        from knobu import service
        service.set_autostart(True)
        service.start()
        print("Knobu is running and will start at login.")
    elif args.command == "disable":
        from knobu import service
        service.uninstall_unit()
        print("Knobu is stopped and removed from login.")
    elif args.command == "awake":
        try:
            awake(args.state.lower())
        except argparse.ArgumentTypeError as err:
            parser.error(str(err))
    elif args.command == "pick-color":
        from knobu.ui.colorpicker import main as picker_main
        sys.exit(picker_main())
    elif args.command == "extract-text":
        from knobu.ui.textextractor import main as extractor_main
        sys.exit(extractor_main())
    else:
        from knobu.ui.app import main as ui_main
        sys.exit(ui_main(sys.argv[:1]))
