"""GitHub Gist Cloud Backup & Sync for Knobu configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
import os
from pathlib import Path
import threading
import time
import urllib.error
import urllib.request

from knobu import __version__, config, service

log = logging.getLogger("knobu.cloud_backup")
BACKUP_FILENAME = "knobu-config-backup.json"
GITHUB_API = "https://api.github.com"

_sync_timer_lock = threading.Lock()
_sync_timer: threading.Timer | None = None


@dataclass
class CloudSyncConfig:
    github_token: str = ""
    github_user: str = ""
    gist_id: str = ""
    auto_sync_on_change: bool = False
    sync_interval_minutes: int = 0
    last_sync_at: float = 0.0


def sync_config_path() -> Path:
    return config.config_path().parent / "cloud_sync.json"


def load_sync_config(path: Path | None = None) -> CloudSyncConfig:
    p = path or sync_config_path()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return CloudSyncConfig()
        return CloudSyncConfig(
            github_token=str(raw.get("github_token", "")),
            github_user=str(raw.get("github_user", "")),
            gist_id=str(raw.get("gist_id", "")),
            auto_sync_on_change=bool(raw.get("auto_sync_on_change", False)),
            sync_interval_minutes=int(raw.get("sync_interval_minutes", 0)),
            last_sync_at=float(raw.get("last_sync_at", 0.0)),
        )
    except (FileNotFoundError, ValueError):
        return CloudSyncConfig()


def save_sync_config(cfg: CloudSyncConfig, path: Path | None = None) -> None:
    """Persist sync credentials separately from config.toml with strict 0600 mode."""
    p = path or sync_config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(cfg), indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(p)


def build_backup_bundle(cfg_dir: Path | None = None) -> dict:
    """Assemble full non-secret Knobu configuration bundle for JSON/Gist backup."""
    base_dir = cfg_dir or config.config_path().parent
    toml_path = base_dir / "config.toml"
    bundle: dict = {
        "schema": "knobu-backup-v1",
        "version": __version__,
        "exported_at": time.time(),
        "config": config.load(toml_path),
    }
    for key, fname in (("automations", "automations.json"), ("workspaces", "workspaces.json")):
        fp = base_dir / fname
        if fp.is_file():
            try:
                bundle[key] = json.loads(fp.read_text(encoding="utf-8"))
            except ValueError:
                pass
    return bundle


def apply_backup_bundle(bundle: dict, cfg_dir: Path | None = None) -> dict:
    """Restore full v1 bundle or legacy flat config dictionary."""
    if not isinstance(bundle, dict):
        raise ValueError("Invalid backup format: root must be a JSON object")
    base_dir = cfg_dir or config.config_path().parent
    base_dir.mkdir(parents=True, exist_ok=True)

    if bundle.get("schema") == "knobu-backup-v1" and isinstance(bundle.get("config"), dict):
        cfg_data = bundle["config"]
        config.save(cfg_data, base_dir / "config.toml")
        for key, fname in (("automations", "automations.json"), ("workspaces", "workspaces.json")):
            if key in bundle and isinstance(bundle[key], list):
                (base_dir / fname).write_text(
                    json.dumps(bundle[key], indent=2) + "\n", encoding="utf-8"
                )
        return cfg_data

    config.save(bundle, base_dir / "config.toml")
    return bundle


def _github_request(method: str, endpoint: str, token: str, payload: dict | None = None) -> tuple[int, dict]:
    headers = {
        "Authorization": f"Bearer {token.strip()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": f"knobu/{__version__}",
    }
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(f"{GITHUB_API}{endpoint}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.getcode(), json.loads(body) if body else {}
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except ValueError:
            parsed = {"message": body or err.reason}
        return err.code, parsed


def verify_github_token(token: str) -> tuple[bool, str]:
    tok = token.strip()
    if not tok:
        return False, "GitHub Personal Access Token cannot be empty"
    try:
        code, body = _github_request("GET", "/user", tok)
        if code == 200 and body.get("login"):
            return True, f"Authenticated as @{body['login']}"
        return False, body.get("message", f"GitHub API error (HTTP {code})")
    except Exception as err:
        return False, str(err)


def push_to_gist(
    token: str = "",
    gist_id: str = "",
    sync_path: Path | None = None,
    cfg_dir: Path | None = None,
) -> tuple[bool, str, str]:
    """Create or update a secret GitHub Gist with the current Knobu bundle."""
    cfg = load_sync_config(sync_path)
    tok = (token or cfg.github_token).strip()
    gid = (gist_id or cfg.gist_id).strip()
    if not tok:
        return False, gid, "No GitHub PAT configured"

    bundle = build_backup_bundle(cfg_dir)
    payload = {
        "description": "Knobu Workstation Configuration Backup",
        "public": False,
        "files": {
            BACKUP_FILENAME: {
                "content": json.dumps(bundle, indent=2, ensure_ascii=False) + "\n",
            }
        },
    }
    try:
        if gid:
            code, resp = _github_request("PATCH", f"/gists/{gid}", tok, payload)
        else:
            code, resp = _github_request("POST", "/gists", tok, payload)
        if code in (200, 201) and resp.get("id"):
            new_gid = str(resp["id"])
            cfg.github_token = tok
            cfg.gist_id = new_gid
            cfg.last_sync_at = time.time()
            owner = resp.get("owner") or {}
            if owner.get("login"):
                cfg.github_user = str(owner["login"])
            save_sync_config(cfg, sync_path)
            return True, new_gid, f"Synced to Gist {new_gid[:10]}..."
        return False, gid, resp.get("message", f"Gist sync failed (HTTP {code})")
    except Exception as err:
        return False, gid, str(err)


def pull_from_gist(
    token: str = "",
    gist_id: str = "",
    sync_path: Path | None = None,
    cfg_dir: Path | None = None,
    reload_service: bool = True,
) -> tuple[bool, dict, str]:
    """Fetch Knobu backup JSON from GitHub Gist and restore local configuration."""
    cfg = load_sync_config(sync_path)
    tok = (token or cfg.github_token).strip()
    gid = (gist_id or cfg.gist_id).strip()
    if not tok or not gid:
        return False, {}, "Both GitHub PAT and Gist ID are required"

    try:
        code, resp = _github_request("GET", f"/gists/{gid}", tok)
        if code != 200:
            return False, {}, resp.get("message", f"Failed to fetch Gist (HTTP {code})")
        files = resp.get("files") or {}
        target = files.get(BACKUP_FILENAME) or next(iter(files.values()), None)
        if not target or "content" not in target:
            return False, {}, f"Backup file {BACKUP_FILENAME} not found in Gist"
        bundle = json.loads(target["content"])
        restored = apply_backup_bundle(bundle, cfg_dir)
        cfg.github_token = tok
        cfg.gist_id = gid
        cfg.last_sync_at = time.time()
        save_sync_config(cfg, sync_path)
        if reload_service:
            service.reload()
        return True, restored, f"Restored configuration from Gist {gid[:10]}..."
    except Exception as err:
        return False, {}, str(err)


def trigger_auto_sync(delay_sec: float = 4.0) -> None:
    """Schedule a debounced cloud push if auto_sync_on_change is enabled."""
    cfg = load_sync_config()
    if not cfg.auto_sync_on_change or not cfg.github_token or not cfg.gist_id:
        return

    def _run():
        ok, _gid, msg = push_to_gist()
        if not ok:
            log.warning("Auto-sync to GitHub Gist failed: %s", msg)

    with _sync_timer_lock:
        global _sync_timer
        if _sync_timer is not None:
            _sync_timer.cancel()
        _sync_timer = threading.Timer(delay_sec, _run)
        _sync_timer.daemon = True
        _sync_timer.start()


_last_tick_check = 0.0


def maybe_periodic_sync() -> None:
    """Push to GitHub Gist if periodic sync interval has elapsed."""
    global _last_tick_check
    now = time.monotonic()
    if (now - _last_tick_check) < 30.0:
        return
    _last_tick_check = now
    cfg = load_sync_config()
    if cfg.sync_interval_minutes <= 0 or not cfg.github_token:
        return
    if (time.time() - cfg.last_sync_at) >= cfg.sync_interval_minutes * 60:
        ok, _gid, msg = push_to_gist()
        if ok:
            log.info("Periodic cloud backup: %s", msg)
        else:
            log.warning("Periodic cloud backup failed: %s", msg)
