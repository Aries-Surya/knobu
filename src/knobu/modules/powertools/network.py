"""Network & IP inspection helpers: active Wi-Fi/Ethernet/VPN, private IP, and cached public IP."""

from __future__ import annotations

from dataclasses import dataclass
import json
import shutil
import subprocess
import urllib.request


@dataclass(frozen=True)
class NetworkStatus:
    connection_name: str
    connection_type: str
    device: str
    private_ip: str
    gateway: str = ""
    vpn_ip: str = ""


def parse_network_info(nmcli_out: str, route_json: str, addr_json: str = "") -> NetworkStatus:
    """Parse nmcli dev + `ip -j route get` output into a NetworkStatus summary."""
    dev_map: dict[str, tuple[str, str]] = {}
    vpn_devs: list[tuple[str, str]] = []
    for line in nmcli_out.splitlines():
        parts = line.split(":", 3)
        if len(parts) < 4:
            continue
        dev, kind, state, conn = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[3].strip()
        if state.startswith("connected"):
            dev_map[dev] = (kind, conn or dev)
            if kind in ("tun", "wireguard", "vpn"):
                vpn_devs.append((dev, conn or dev))

    outbound_dev = ""
    private_ip = ""
    gateway = ""
    try:
        routes = json.loads(route_json) if route_json.strip() else []
        if routes and isinstance(routes, list):
            r = routes[0]
            outbound_dev = str(r.get("dev", ""))
            private_ip = str(r.get("prefsrc", ""))
            gateway = str(r.get("gateway", ""))
    except ValueError:
        pass

    # Map VPN IP from addr_json if active
    ip_by_dev: dict[str, str] = {}
    if addr_json.strip():
        try:
            for iface in json.loads(addr_json):
                ifname = iface.get("ifname", "")
                for info in iface.get("addr_info", []):
                    if info.get("family") == "inet" and info.get("local") and ifname not in ip_by_dev:
                        ip_by_dev[ifname] = str(info["local"])
        except ValueError:
            pass

    if not private_ip and outbound_dev:
        private_ip = ip_by_dev.get(outbound_dev, "")
    if not outbound_dev and dev_map:
        for d, (k, _c) in dev_map.items():
            if k in ("wifi", "ethernet"):
                outbound_dev = d
                private_ip = private_ip or ip_by_dev.get(d, "")
                break

    conn_type, conn_name = dev_map.get(outbound_dev, ("", ""))
    if not conn_name:
        conn_name = outbound_dev or ("Connected" if private_ip else "Offline")
        conn_type = conn_type or ("network" if private_ip else "offline")

    vpn_ip = ""
    for vdev, _ in vpn_devs:
        if vdev in ip_by_dev:
            vpn_ip = ip_by_dev[vdev]
            break

    return NetworkStatus(
        connection_name=conn_name,
        connection_type=conn_type,
        device=outbound_dev,
        private_ip=private_ip or "Unavailable",
        gateway=gateway,
        vpn_ip=vpn_ip,
    )


def _run_out(cmd: list[str]) -> str:
    if not shutil.which(cmd[0]):
        return ""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=2, check=False)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def get_network_status() -> NetworkStatus:
    """Query active network connection, private IP, gateway, and VPN IP."""
    nmcli_out = _run_out(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev"])
    route_json = _run_out(["ip", "-j", "route", "get", "1.1.1.1"])
    addr_json = _run_out(["ip", "-j", "-4", "addr", "show"])
    return parse_network_info(nmcli_out, route_json, addr_json)


def fetch_public_ip(timeout: float = 3.0) -> str | None:
    """Fetch public IPv4 address cleanly over HTTPS; returns None if offline."""
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "knobu/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ip = resp.read().decode("utf-8", errors="ignore").strip()
                if ip and len(ip) <= 45 and "." in ip:
                    return ip
        except Exception:
            continue
    return None
