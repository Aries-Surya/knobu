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
    p_notif = sub.add_parser("notifications", help="open Notification Center or toast")
    p_notif.add_argument("--toast", type=int, default=None, help=argparse.SUPPRESS)
    sub.add_parser("ports", help="list listening TCP/UDP ports")
    p_bp = sub.add_parser("bypass", help="temporarily bypass all hardware grabs and customizations (e.g. for gaming)")
    p_bp.add_argument("state", nargs="?", default="status", choices=["on", "off", "toggle", "status"],
                      help="on | off | toggle | status (default: status)")
    sub.add_parser("restore-os-shortcuts", help="restore default OS shortcuts overridden by Knobu (GNOME / KDE)")
    p_backup = sub.add_parser("backup", help="export all Knobu configurations to a JSON backup file")
    p_backup.add_argument("file", nargs="?", default=None, help="destination JSON path (default: ~/.config/knobu/knobu-backup.json)")
    p_restore = sub.add_parser("restore", help="restore Knobu configurations from a JSON backup file")
    p_restore.add_argument("file", help="path to source JSON backup file")
    p_dns = sub.add_parser("dns", help="query DNS records (A, AAAA, CNAME, MX, TXT)")
    p_dns.add_argument("domain", help="domain to query")
    p_dns.add_argument("type", nargs="?", default="A", help="record type (default: A)")
    p_dns.add_argument("--server", default="", help="custom resolver (e.g. 1.1.1.1 or 8.8.8.8)")
    p_ssl = sub.add_parser("ssl-check", help="inspect SSL/TLS certificate expiry, issuer, and SANs")
    p_ssl.add_argument("host", help="hostname to inspect (e.g. google.com or host:port)")
    p_ssl.add_argument("port", nargs="?", type=int, default=443, help="port (default: 443)")
    p_cidr = sub.add_parser("cidr", help="calculate IPv4/IPv6 CIDR network range and usable hosts")
    p_cidr.add_argument("prefix", help="CIDR prefix (e.g. 192.168.1.0/24 or 10.0.0.0/16)")
    sub.add_parser("aws-whoami", help="display active AWS caller identity (Account ID, ARN, UserId)")
    sub.add_parser("containers", help="list Docker containers status and ports")
    sub.add_parser("shortcut-guide", help="open the interactive Shortcut Guide overlay")
    sub.add_parser("zoomit", help="freeze screen for zoom & pen/arrow/box annotation")
    sub.add_parser("quick-accent", help="open the Quick Accent character picker popup")
    p_theme = sub.add_parser("theme", help="switch or inspect desktop light/dark theme")
    p_theme.add_argument("mode", nargs="?", default="status", choices=["light", "dark", "toggle", "status"])
    p_ws = sub.add_parser("workspace", help="launch a saved workspace app group (or list groups)")
    p_ws.add_argument("name", nargs="?", default=None, help="workspace name to launch")
    sub.add_parser("automations", help="list configured automation rules")
    p_ra = sub.add_parser("run-automation", help="manually run an automation rule by name or ID")
    p_ra.add_argument("rule", help="rule name or ID")
    sub.add_parser("cron", help="show local cron service status and list user cron jobs")
    p_ca = sub.add_parser("cron-add", help="add a new user cron job")
    p_ca.add_argument("schedule", help="cron schedule (e.g. '0 12 * * *' or '@daily')")
    p_ca.add_argument("cmd", help="shell command to run")
    p_ca.add_argument("--comment", default="", help="optional description comment")
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
    elif args.command == "notifications":
        from knobu.ui.hud import main as hud_main
        sys.exit(hud_main(["--toast", str(args.toast)] if args.toast is not None else []))
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
    elif args.command == "backup":
        from pathlib import Path
        from knobu import config
        target = Path(args.file).resolve() if args.file else None
        out = config.export_json(target)
        print(f"Configuration backed up successfully to: {out}")
    elif args.command == "restore":
        from pathlib import Path
        from knobu import config, service
        src = Path(args.file).resolve()
        if not src.exists():
            print(f"Error: backup file not found: {src}", file=sys.stderr)
            sys.exit(1)
        try:
            config.import_json(src)
            service.reload()
            print(f"Configuration successfully restored from: {src}")
        except Exception as err:
            print(f"Failed to restore configuration: {err}", file=sys.stderr)
            sys.exit(1)
    elif args.command == "dns":
        from knobu.modules.powertools.devops import query_dns
        ok, records, msg = query_dns(args.domain, args.type, args.server)
        if not ok:
            print(f"DNS lookup error: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"DNS {args.type.upper()} records for {args.domain}:")
        for r in records:
            print(f"  {r.name:<32} {r.record_type:<6} {r.value:<32} (TTL {r.ttl}s)")
    elif args.command == "ssl-check":
        from knobu.modules.powertools.devops import inspect_ssl_cert
        info = inspect_ssl_cert(args.host, args.port)
        if not info.is_valid and info.error:
            print(f"SSL certificate check failed for {args.host}:{info.port}: {info.error}", file=sys.stderr)
            sys.exit(1)
        print(f"SSL Certificate for {info.host}:{info.port}:")
        print(f"  Issuer:      {info.issuer}")
        print(f"  Expires:     {info.expiry_date} ({info.days_left} day(s) remaining)")
        print(f"  Status:      {'VALID' if info.days_left >= 0 else 'EXPIRED'}")
        if info.sans:
            print(f"  SANs:        {', '.join(info.sans[:8])}")
    elif args.command == "cidr":
        from knobu.modules.powertools.devops import calculate_cidr
        ok, c, msg = calculate_cidr(args.prefix)
        if not ok or not c:
            print(f"CIDR calculation error: {msg}", file=sys.stderr)
            sys.exit(1)
        print(f"CIDR Network: {c.cidr}")
        print(f"  Network Address:   {c.network_address}")
        print(f"  Netmask:           {c.netmask}")
        print(f"  Broadcast Address: {c.broadcast_address}")
        print(f"  Total IPs:         {c.total_ips:,}")
        print(f"  Usable Hosts:      {c.usable_hosts:,}")
        print(f"  Host Range:        {c.first_host} -> {c.last_host}")
    elif args.command == "aws-whoami":
        from knobu.modules.powertools.devops import get_aws_caller_identity
        ident = get_aws_caller_identity()
        if "error" in ident:
            print(f"AWS identity error: {ident['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"Active AWS Identity:")
        print(f"  Account ID: {ident.get('Account')}")
        print(f"  ARN:        {ident.get('Arn')}")
        print(f"  UserId:     {ident.get('UserId')}")
    elif args.command == "containers":
        from knobu.modules.powertools.devops import get_docker_containers
        conts = get_docker_containers()
        if not conts:
            print("No active Docker containers found (or Docker daemon not running).")
        else:
            print(f"{'CONTAINER ID':<14} {'NAME':<20} {'IMAGE':<24} {'STATUS':<16} {'PORTS'}")
            for c in conts:
                print(f"{c.id:<14} {c.name[:19]:<20} {c.image[:23]:<24} {c.status[:15]:<16} {c.ports}")
    elif args.command == "shortcut-guide":
        from knobu.ui.shortcut_guide import main as guide_main
        sys.exit(guide_main())
    elif args.command == "zoomit":
        from knobu.ui.zoomit import main as zoomit_main
        sys.exit(zoomit_main())
    elif args.command == "quick-accent":
        from knobu.ui.quick_accent import main as qa_main
        sys.exit(qa_main())
    elif args.command == "theme":
        from knobu.modules.powertools.theme import get_theme, set_theme
        if args.mode == "status":
            print(f"Current desktop theme: {get_theme()}")
        else:
            ok, msg = set_theme(args.mode)
            print(msg)
            sys.exit(0 if ok else 1)
    elif args.command == "workspace":
        from knobu.modules.powertools.workspaces import launch_workspace, load_workspaces
        if not args.name:
            groups = load_workspaces()
            if not groups:
                print("No workspaces configured.")
            for g in groups:
                print(f"{g.name}: {', '.join(g.commands)}")
        else:
            ok, msg = launch_workspace(args.name)
            print(msg)
            sys.exit(0 if ok else 1)
    elif args.command == "automations":
        from knobu.modules.automation import load_rules
        rules = load_rules()
        if not rules:
            print("No automation rules configured.")
        for r in rules:
            st = "ON" if r.enabled else "OFF"
            print(f"[{st}] {r.id} | {r.name} | When {r.trigger_type}={r.trigger_value}")
    elif args.command == "run-automation":
        from knobu.modules.automation import load_rules, run_rule_now
        rules = load_rules()
        q = args.rule.strip().lower()
        target = next((r for r in rules if r.id.lower() == q or r.name.lower() == q), None)
        if not target:
            print(f"Automation rule not found: {args.rule}", file=sys.stderr)
            sys.exit(1)
        ok, msg = run_rule_now(target)
        print(msg)
        sys.exit(0 if ok else 1)
    elif args.command == "cron":
        from knobu.modules.powertools.cron import cron_service_status, list_cron_jobs
        active, status_msg = cron_service_status()
        print(f"Cron service: {'running' if active else 'inactive'} ({status_msg})")
        jobs = list_cron_jobs()
        if not jobs:
            print("No user cron jobs configured.")
        for idx, j in enumerate(jobs, 1):
            st = "ON " if j.enabled else "OFF"
            desc = f" # {j.comment}" if j.comment else ""
            print(f"  {idx}. [{st}] {j.schedule:<15} {j.command}{desc}")
    elif args.command == "cron-add":
        from knobu.modules.powertools.cron import add_cron_job
        ok, msg = add_cron_job(args.schedule, args.cmd, args.comment)
        print(msg)
        sys.exit(0 if ok else 1)
    else:
        from knobu.ui.app import main as ui_main
        sys.exit(ui_main(sys.argv[:1]))
