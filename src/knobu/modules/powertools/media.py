"""Local media utilities powered by FFmpeg: video compression, GIF creation, batch image conversion."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

IMAGE_FORMATS = ("webp", "png", "jpg", "avif", "bmp")

IMAGE_RESIZE_PRESETS = (
    ("small", "Small (fit 854 px)", 854),
    ("medium", "Medium (fit 1366 px)", 1366),
    ("large", "Large (fit 1920 px)", 1920),
    ("half", "50% Scale", -50),
)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _unique_output(target: Path) -> Path:
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    idx = 1
    while True:
        cand = target.with_name(f"{stem}_{idx}{suffix}")
        if not cand.exists():
            return cand
        idx += 1


def build_compress_cmd(src: Path, dst: Path, crf: int = 24) -> list[str]:
    return [
        "ffmpeg", "-y", "-i", str(src),
        "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        str(dst),
    ]


def build_gif_cmd(src: Path, dst: Path, fps: int = 12, width: int = 640) -> list[str]:
    vf = (
        f"fps={fps},scale={width}:-1:flags=lanczos,"
        "split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse"
    )
    return ["ffmpeg", "-y", "-i", str(src), "-vf", vf, "-loop", "0", str(dst)]


def build_image_convert_cmd(src: Path, dst: Path) -> list[str]:
    return ["ffmpeg", "-y", "-i", str(src), str(dst)]


def build_image_resize_cmd(src: Path, dst: Path, size_spec: int) -> list[str]:
    if size_spec < 0:
        pct = abs(size_spec) / 100.0
        vf = f"scale=round(iw*{pct}):round(ih*{pct})"
    else:
        vf = f"scale='min(iw,{size_spec})':-2"
    return ["ffmpeg", "-y", "-i", str(src), "-vf", vf, str(dst)]


def _run_ffmpeg(cmd: list[str], timeout: int = 600) -> tuple[bool, str]:
    if not ffmpeg_available():
        return False, "ffmpeg is not installed (sudo apt install ffmpeg)."
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        if r.returncode == 0:
            return True, ""
        lines = [ln.strip() for ln in r.stderr.splitlines() if ln.strip()]
        return False, lines[-1] if lines else "ffmpeg failed."
    except (OSError, subprocess.TimeoutExpired) as err:
        return False, str(err)


def compress_video(src: Path, crf: int = 24) -> tuple[bool, str, Path | None]:
    dst = _unique_output(src.with_name(f"{src.stem}_compressed.mp4"))
    ok, err = _run_ffmpeg(build_compress_cmd(src, dst, crf=crf))
    if not ok:
        return False, err, None
    return True, f"Saved {dst.name}", dst


def video_to_gif(src: Path, fps: int = 12, width: int = 640) -> tuple[bool, str, Path | None]:
    dst = _unique_output(src.with_suffix(".gif"))
    ok, err = _run_ffmpeg(build_gif_cmd(src, dst, fps=fps, width=width))
    if not ok:
        return False, err, None
    return True, f"Saved {dst.name}", dst


def convert_images(files: list[Path], fmt: str) -> tuple[bool, str, list[Path]]:
    target_fmt = fmt.lower().lstrip(".")
    if target_fmt not in IMAGE_FORMATS:
        return False, f"Unsupported format: {fmt}", []
    outputs: list[Path] = []
    for src in files:
        dst = _unique_output(src.with_suffix(f".{target_fmt}"))
        ok, err = _run_ffmpeg(build_image_convert_cmd(src, dst), timeout=120)
        if not ok:
            return False, f"{src.name}: {err}", outputs
        outputs.append(dst)
    return True, f"Converted {len(outputs)} image(s) to .{target_fmt}", outputs


def resize_images(files: list[Path], preset: str = "medium") -> tuple[bool, str, list[Path]]:
    preset_map = {k: v for k, _, v in IMAGE_RESIZE_PRESETS}
    if preset not in preset_map:
        return False, f"Unknown resize preset: {preset}", []
    size_spec = preset_map[preset]
    outputs: list[Path] = []
    for src in files:
        dst = _unique_output(src.with_name(f"{src.stem}_{preset}{src.suffix}"))
        ok, err = _run_ffmpeg(build_image_resize_cmd(src, dst, size_spec), timeout=120)
        if not ok:
            return False, f"{src.name}: {err}", outputs
        outputs.append(dst)
    return True, f"Resized {len(outputs)} image(s) ({preset})", outputs
