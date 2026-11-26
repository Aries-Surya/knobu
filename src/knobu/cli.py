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
        msg = time.strftime("Keeping awake until %-I:%M %p.", time.localtime(until))
    config.save(data)
    if not service.is_active():
        msg += " (The Knobu service isn't running; start it with `knobu enable`.)"
    service.reload()
    print(msg)


def bypass_command(arg: str) -> None:
    from knobu import config, service
    data = config.load()
    gen = data.setdefault("general", {})
    current = bool(gen.get("bypass", False))
    if arg == "on":
        target = True
    elif arg == "off":
        target = False
    elif arg == "toggle":
        target = not current
    else:  # status
        print(f"Bypass Mode: {'ON (hardware grabs and customizations bypassed)' if current else 'OFF (Knobu active)'}")
        return

    gen["bypass"] = target
    config.save(data)
    service.reload()
    print(f"Bypass Mode is now {'ON (hardware grabs and customizations bypassed)' if target else 'OFF (Knobu active)'}.")



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
    sub.add_parser("clipboard", help="open the clipboard history popup")
    sub.add_parser("paste-plain", help="paste current clipboard content as plain text")
    sub.add_parser("command-bar", help="open the Command Bar quick launcher")
    sub.add_parser("run", help="alias for command-bar")
    sub.add_parser("cleaning-mode", help="lock keyboard, mouse, and touchpad inputs for cleaning")
    sub.add_parser("screen-ruler", help="measure pixel dimensions and spacing on screen")
    sub.add_parser("find-mouse", help="spotlight pointer location on screen")
    sub.add_parser("ports", help="list listening TCP/UDP ports")
    p_bp = sub.add_parser("bypass", help="temporarily bypass all hardware grabs and customizations (e.g. for gaming)")
    p_bp.add_argument("state", nargs="?", default="status", choices=["on", "off", "toggle", "status"],
                      help="on | off | toggle | status (default: status)")
    sub.add_parser("restore-os-shortcuts", help="restore default OS shortcuts overridden by Knobu (GNOME / KDE)")
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
    elif args.command == "clipboard":
        from knobu.ui.clipboard import main as clipboard_main
        sys.exit(clipboard_main())
    elif args.command == "paste-plain":
        import re
        from knobu.modules.clipboard import get_clipboard, set_clipboard, simulate_paste
        raw = get_clipboard()
        if raw:
            plain = re.sub(r"<[^>]+>", "", raw)
            set_clipboard(plain)
            simulate_paste()
    elif args.command in ("command-bar", "run"):
        from knobu.ui.commandbar import main as commandbar_main
        sys.exit(commandbar_main())
    elif args.command == "cleaning-mode":
        from knobu.ui.cleaning import main as cleaning_main
        sys.exit(cleaning_main())
    elif args.command == "screen-ruler":
        from knobu.ui.ruler import main as ruler_main
        sys.exit(ruler_main())
    elif args.command == "find-mouse":
        from knobu.ui.pointer_fx import main as pointer_main
        sys.exit(pointer_main())
    elif args.command == "ports":
        from knobu.modules.powertools import list_listening_ports
        for p in list_listening_ports():
            pid_s = str(p.pid) if p.pid is not None else "-"
            print(f"{p.proto:<4} {p.port:<6} {p.address:<24} {p.process} (pid={pid_s})")
    elif args.command == "bypass":
        bypass_command(args.state.lower())
    elif args.command == "restore-os-shortcuts":
        from knobu.modules.commandbar.os_shortcuts import restore_os_shortcuts
        restored = restore_os_shortcuts()
        print("Restored original OS shortcuts." if restored else "No overridden OS shortcuts to restore.")
    else:
        from knobu.ui.app import main as ui_main
        sys.exit(ui_main(sys.argv[:1]))
