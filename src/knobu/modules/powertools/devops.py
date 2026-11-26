"""Cloud, DevOps and Network Diagnostics utilities for Knobu (Milestone 10)."""

from __future__ import annotations

from dataclasses import dataclass
import datetime
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import socket
import ssl
import subprocess
import time
import urllib.request


@dataclass(frozen=True)
class DnsRecord:
    record_type: str
    name: str
    value: str
    ttl: int = 0


@dataclass(frozen=True)
class SslCertInfo:
    host: str
    port: int
    issuer: str
    expiry_date: str
    days_left: int
    sans: list[str]
    is_valid: bool = True
    error: str = ""


@dataclass(frozen=True)
class HttpTimingResult:
    url: str
    status_code: int
    total_ms: float
    error: str = ""


@dataclass(frozen=True)
class SubnetCalculation:
    cidr: str
    network_address: str
    broadcast_address: str
    netmask: str
    total_ips: int
    usable_hosts: int
    first_host: str
    last_host: str


@dataclass(frozen=True)
class ContainerInfo:
    id: str
    name: str
    image: str
    status: str
    ports: str


# ---------------------------------------------------------------------- 1. DNS Lookup

def query_dns(domain: str, record_type: str = "A", resolver: str = "") -> tuple[bool, list[DnsRecord], str]:
    """Query DNS records via dig; falls back to socket.getaddrinfo if dig is unavailable."""
    domain = domain.strip().lower()
    record_type = record_type.strip().upper() or "A"
    if not domain:
        return False, [], "Domain cannot be empty"

    if shutil.which("dig"):
        cmd = ["dig", "+noall", "+answer", "+nocomments", domain, record_type]
        if resolver.strip():
            srv = resolver.strip()
            cmd.append(f"@{srv}" if not srv.startswith("@") else srv)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=4, check=False)
            records: list[DnsRecord] = []
            for line in r.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 5:
                    r_name = parts[0].rstrip(".")
                    try:
                        r_ttl = int(parts[1])
                    except ValueError:
                        r_ttl = 0
                    r_type = parts[3].upper()
                    r_val = " ".join(parts[4:])
                    records.append(DnsRecord(record_type=r_type, name=r_name, value=r_val, ttl=r_ttl))
            return True, records, f"{len(records)} record(s) found" if records else "No records found"
        except (OSError, subprocess.TimeoutExpired) as err:
            return False, [], str(err)

    # Pure python fallback for A records
    try:
        infos = socket.getaddrinfo(domain, None)
        seen = set()
        records = []
        for info in infos:
            ip = info[4][0]
            if ip not in seen:
                seen.add(ip)
                records.append(DnsRecord(record_type="A" if ":" not in ip else "AAAA", name=domain, value=ip))
        return True, records, f"{len(records)} address(es) resolved"
    except Exception as err:
        return False, [], str(err)


# ---------------------------------------------------------------------- 2. SSL/TLS Inspector

def inspect_ssl_cert(host: str, port: int = 443, timeout: float = 3.5) -> SslCertInfo:
    """Check SSL certificate expiry, issuer, and SANs via native SSL/socket."""
    host = host.strip()
    if ":" in host and not host.startswith("["):
        parts = host.split(":", 1)
        host = parts[0]
        try:
            port = int(parts[1])
        except ValueError:
            pass

    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                if not cert:
                    return SslCertInfo(host, port, "", "", 0, [], is_valid=False, error="No certificate presented")
                exp_str = cert.get("notAfter", "")
                issuer_dict = dict(x[0] for x in cert.get("issuer", []))
                issuer_name = str(issuer_dict.get("organizationName") or issuer_dict.get("commonName") or "Unknown")
                sans = [str(val) for key, val in cert.get("subjectAltName", []) if key == "DNS"]

                days_left = 0
                if exp_str:
                    try:
                        # e.g. 'Apr 27 08:44:48 2026 GMT'
                        exp_dt = datetime.datetime.strptime(exp_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=datetime.timezone.utc)
                        now_dt = datetime.datetime.now(datetime.timezone.utc)
                        days_left = (exp_dt - now_dt).days
                    except Exception:
                        pass

                return SslCertInfo(
                    host=host,
                    port=port,
                    issuer=issuer_name,
                    expiry_date=exp_str,
                    days_left=days_left,
                    sans=sans[:20],
                    is_valid=(days_left >= 0),
                )
    except Exception as err:
        return SslCertInfo(host, port, "", "", 0, [], is_valid=False, error=str(err))


# ---------------------------------------------------------------------- 3. TCP Port Ping & HTTP Timing

def tcp_ping(host: str, port: int, timeout: float = 2.0) -> tuple[bool, float, str]:
    """Test TCP port connectivity and round-trip latency in milliseconds."""
    t0 = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ms = round((time.monotonic() - t0) * 1000, 2)
            return True, ms, f"Connected to {host}:{port} in {ms}ms"
    except Exception as err:
        ms = round((time.monotonic() - t0) * 1000, 2)
        return False, ms, str(err)


def http_timing_probe(url: str, timeout: float = 4.0) -> HttpTimingResult:
    """Measure HTTP response status and latency breakdown."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "knobu-devops/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ms = round((time.monotonic() - t0) * 1000, 2)
            return HttpTimingResult(url=url, status_code=resp.getcode(), total_ms=ms)
    except urllib.error.HTTPError as err:
        ms = round((time.monotonic() - t0) * 1000, 2)
        return HttpTimingResult(url=url, status_code=err.code, total_ms=ms, error=err.reason)
    except Exception as err:
        ms = round((time.monotonic() - t0) * 1000, 2)
        return HttpTimingResult(url=url, status_code=0, total_ms=ms, error=str(err))


# ---------------------------------------------------------------------- 4. CIDR Subnet Calculator

def calculate_cidr(cidr_str: str) -> tuple[bool, SubnetCalculation | None, str]:
    """Pure-python IPv4/IPv6 CIDR subnet calculator."""
    cidr_str = cidr_str.strip()
    try:
        net = ipaddress.ip_network(cidr_str, strict=False)
        total = net.num_addresses
        usable = max(0, total - 2) if net.version == 4 and total > 2 else total
        hosts = list(net.hosts()) if total <= 1024 else []
        first_h = str(hosts[0]) if hosts else str(net.network_address)
        last_h = str(hosts[-1]) if hosts else str(net.broadcast_address)

        calc = SubnetCalculation(
            cidr=str(net),
            network_address=str(net.network_address),
            broadcast_address=str(net.broadcast_address),
            netmask=str(net.netmask),
            total_ips=total,
            usable_hosts=usable,
            first_host=first_h,
            last_host=last_h,
        )
        return True, calc, f"Calculated {net}"
    except ValueError as err:
        return False, None, str(err)


# ---------------------------------------------------------------------- 5. Containers & Kubernetes Context

def get_docker_containers() -> list[ContainerInfo]:
    """List local Docker containers with names, image, and status."""
    if not shutil.which("docker"):
        return []
    try:
        r = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.ID}}|{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}"],
            capture_output=True, text=True, timeout=3, check=False,
        )
        if r.returncode != 0:
            return []
        items = []
        for line in r.stdout.splitlines():
            parts = line.split("|", 4)
            if len(parts) == 5:
                items.append(ContainerInfo(
                    id=parts[0].strip(),
                    name=parts[1].strip(),
                    image=parts[2].strip(),
                    status=parts[3].strip(),
                    ports=parts[4].strip(),
                ))
        return items
    except (OSError, subprocess.TimeoutExpired):
        return []


def stop_docker_container(container_id_or_name: str) -> tuple[bool, str]:
    """Stop a Docker container cleanly."""
    if not shutil.which("docker"):
        return False, "docker command not found"
    try:
        r = subprocess.run(["docker", "stop", container_id_or_name],
                           capture_output=True, text=True, timeout=12, check=False)
        return (r.returncode == 0, r.stdout.strip() if r.returncode == 0 else r.stderr.strip())
    except Exception as err:
        return False, str(err)


def get_kube_contexts() -> tuple[str, list[str]]:
    """Return active kubectl context and list of all available contexts."""
    if not shutil.which("kubectl"):
        return "", []
    try:
        r = subprocess.run(["kubectl", "config", "get-contexts", "-o", "name"],
                           capture_output=True, text=True, timeout=3, check=False)
        contexts = [c.strip() for c in r.stdout.splitlines() if c.strip()]
        cur_r = subprocess.run(["kubectl", "config", "current-context"],
                               capture_output=True, text=True, timeout=2, check=False)
        cur = cur_r.stdout.strip() if cur_r.returncode == 0 else ""
        return cur, contexts
    except (OSError, subprocess.TimeoutExpired):
        return "", []


def switch_kube_context(context_name: str) -> tuple[bool, str]:
    """Switch active kubectl context."""
    if not shutil.which("kubectl"):
        return False, "kubectl command not found"
    try:
        r = subprocess.run(["kubectl", "config", "use-context", context_name],
                           capture_output=True, text=True, timeout=4, check=False)
        return (r.returncode == 0, r.stdout.strip() if r.returncode == 0 else r.stderr.strip())
    except Exception as err:
        return False, str(err)


# ---------------------------------------------------------------------- 6. AWS STS Identity & SSO

def get_aws_caller_identity() -> dict[str, str]:
    """Get AWS account ID, User/Role ARN, and UserId via aws sts get-caller-identity."""
    if not shutil.which("aws"):
        return {"error": "AWS CLI not installed"}
    try:
        r = subprocess.run(["aws", "sts", "get-caller-identity", "--output", "json"],
                           capture_output=True, text=True, timeout=5, check=False)
        if r.returncode == 0:
            return json.loads(r.stdout)
        return {"error": r.stderr.strip() or "Failed to query STS identity"}
    except Exception as err:
        return {"error": str(err)}
