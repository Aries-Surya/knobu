"""Power Tools module package: Cleaning Mode, Screen Ruler, Ports, Cleaner, EnvVars, Hosts, Locksmith, Media."""

from __future__ import annotations

import threading

from knobu.modules.base import Module
from knobu.modules.powertools.cleaner import (
    CleanupTarget,
    PackageInfo,
    available_package_sources,
    clean_target,
    format_bytes,
    list_installed_packages,
    scan_cleanup_targets,
    uninstall_package,
)
from knobu.modules.powertools.envvars import (
    EnvEntry,
    is_valid_key,
    join_path_value,
    load_profiles,
    parse_env_file,
    render_env_file,
    save_profiles,
    split_path_value,
    system_env_snapshot,
)
from knobu.modules.powertools.hosts import (
    HostEntry,
    load_hosts,
    parse_hosts,
    render_hosts,
    save_hosts,
    validate_host_entry,
)
from knobu.modules.powertools.locksmith import FileLock, find_file_locks
from knobu.modules.powertools.media import (
    IMAGE_FORMATS,
    IMAGE_RESIZE_PRESETS,
    build_compress_cmd,
    build_gif_cmd,
    build_image_convert_cmd,
    build_image_resize_cmd,
    compress_video,
    convert_images,
    ffmpeg_available,
    resize_images,
    video_to_gif,
)
from knobu.modules.powertools.devops import (
    ContainerInfo,
    DnsRecord,
    HttpTimingResult,
    SslCertInfo,
    SubnetCalculation,
    calculate_cidr,
    get_aws_caller_identity,
    get_docker_containers,
    get_kube_contexts,
    http_timing_probe,
    inspect_ssl_cert,
    query_dns,
    stop_docker_container,
    switch_kube_context,
    tcp_ping,
)
from knobu.modules.powertools.ports import (
    PortEntry,
    kill_process,
    list_listening_ports,
    parse_ss_output,
)
from knobu.system import hotkeys, keys, launch

__all__ = [
    "PowerToolsModule",
    "PortEntry", "parse_ss_output", "list_listening_ports", "kill_process",
    "CleanupTarget", "PackageInfo", "available_package_sources", "format_bytes",
    "scan_cleanup_targets", "clean_target", "list_installed_packages", "uninstall_package",
    "EnvEntry", "is_valid_key", "split_path_value", "join_path_value", "parse_env_file",
    "render_env_file", "load_profiles", "save_profiles", "system_env_snapshot",
    "HostEntry", "validate_host_entry", "parse_hosts", "render_hosts", "load_hosts", "save_hosts",
    "FileLock", "find_file_locks",
    "IMAGE_FORMATS", "IMAGE_RESIZE_PRESETS", "ffmpeg_available", "build_compress_cmd",
    "build_gif_cmd", "build_image_convert_cmd", "build_image_resize_cmd",
    "compress_video", "video_to_gif", "convert_images", "resize_images",
    "DnsRecord", "query_dns", "SslCertInfo", "inspect_ssl_cert",
    "tcp_ping", "HttpTimingResult", "http_timing_probe",
    "SubnetCalculation", "calculate_cidr",
    "ContainerInfo", "get_docker_containers", "stop_docker_container",
    "get_kube_contexts", "switch_kube_context", "get_aws_caller_identity",
]


class PowerToolsModule(Module):
    id = "powertools"
    name = "Power Tools"
    description = "Cleaning mode, screen ruler, ports, cleaner, env vars, hosts, locksmith, and media tools."
    icon = "applications-utilities-symbolic"
    defaults = {
        "enabled": True,
        "hotkey": "super+alt+k",
        "ruler_hotkey": "super+shift+m",
        "shortcut_guide_hotkey": "super+shift+slash",
        "zoomit_hotkey": "super+alt+z",
        "cleaning_duration": 30,
        "light_switch_enabled": False,
        "light_switch_light_start": "07:00",
        "light_switch_dark_start": "19:00",
    }

    def run(self, stop: threading.Event) -> None:
        from knobu.modules.powertools.theme import get_theme, scheduled_theme_for_time, set_theme

        bindings = []
        shortcuts = [
            ("hotkey", "cleaning-mode"),
            ("ruler_hotkey", "screen-ruler"),
            ("shortcut_guide_hotkey", "shortcut-guide"),
            ("zoomit_hotkey", "zoomit"),
        ]
        for key, cmd in shortcuts:
            raw = self.settings.get(key, "").strip()
            if not raw:
                continue
            try:
                chord = keys.parse(raw)
                bindings.append(hotkeys.service().register(chord, lambda c=cmd: launch.knobu(c)))
                self.log.info("registered %s -> knobu %s", keys.pretty(raw), cmd)
            except ValueError as err:
                self.log.error("bad shortcut for %s: %s", key, err)

        try:
            while not stop.is_set():
                if bool(self.settings.get("light_switch_enabled", False)):
                    target = scheduled_theme_for_time(
                        light_start=str(self.settings.get("light_switch_light_start", "07:00")),
                        dark_start=str(self.settings.get("light_switch_dark_start", "19:00")),
                    )
                    if get_theme() != target:
                        set_theme(target)
                        self.log.info("Light Switch applied %s theme", target)
                stop.wait(60)
        finally:
            for b in bindings:
                hotkeys.service().unregister(b)
