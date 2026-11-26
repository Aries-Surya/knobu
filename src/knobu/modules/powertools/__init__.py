"""Power Tools module package: Port Manager, Cleaning Mode, System Cleaner, and Media Tools."""

from knobu.modules.hotkey_tools import HotkeyToolModule
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
from knobu.modules.powertools.media import (
    IMAGE_FORMATS,
    build_compress_cmd,
    build_gif_cmd,
    build_image_convert_cmd,
    compress_video,
    convert_images,
    ffmpeg_available,
    video_to_gif,
)
from knobu.modules.powertools.ports import (
    PortEntry,
    kill_process,
    list_listening_ports,
    parse_ss_output,
)

__all__ = [
    "PowerToolsModule",
    "PortEntry",
    "parse_ss_output",
    "list_listening_ports",
    "kill_process",
    "CleanupTarget",
    "PackageInfo",
    "available_package_sources",
    "format_bytes",
    "scan_cleanup_targets",
    "clean_target",
    "list_installed_packages",
    "uninstall_package",
    "IMAGE_FORMATS",
    "ffmpeg_available",
    "build_compress_cmd",
    "build_gif_cmd",
    "build_image_convert_cmd",
    "compress_video",
    "video_to_gif",
    "convert_images",
]


class PowerToolsModule(HotkeyToolModule):
    id = "powertools"
    name = "Power Tools"
    description = "Port manager, hardware cleaning lock, system cleaner, and media tools."
    icon = "applications-utilities-symbolic"
    command = "cleaning-mode"
    defaults = {
        "enabled": True,
        "hotkey": "super+alt+k",
        "cleaning_duration": 30,
    }
