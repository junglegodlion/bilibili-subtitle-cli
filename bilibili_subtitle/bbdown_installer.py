"""Install BBDown binary from GitHub Releases.

Pure stdlib (urllib + zipfile + platform) to keep the package zero-dependency.
Used by ``bilibili-subtitle --install-bbdown`` so that ``uv tool install`` users
can bootstrap BBDown without cloning the repo or installing gh CLI.
"""

from __future__ import annotations

import json
import platform
import stat
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

GITHUB_API = "https://api.github.com/repos/nilaoda/BBDown/releases/latest"
USER_AGENT = "bilibili-subtitle-installer/0.2"


class InstallerError(Exception):
    """Raised when BBDown installation fails."""


@dataclass(frozen=True, slots=True)
class PlatformAsset:
    """Maps the host platform to a BBDown release asset keyword."""

    keyword: str  # e.g. "osx-x64", matched against asset filenames
    label: str    # human-readable, e.g. "macOS (Intel)"


def detect_platform() -> PlatformAsset:
    """Detect the host platform and return the matching asset keyword.

    Raises InstallerError on unsupported platforms.
    """
    os_name = platform.system()
    machine = platform.machine().lower()

    if os_name == "Darwin":
        if machine in ("x86_64", "amd64"):
            return PlatformAsset("osx-x64", "macOS (Intel)")
        if machine in ("arm64", "aarch64"):
            return PlatformAsset("osx-arm64", "macOS (Apple Silicon)")
    elif os_name == "Linux":
        if machine in ("x86_64", "amd64"):
            return PlatformAsset("linux-x64", "Linux (x64)")
        if machine in ("arm64", "aarch64"):
            return PlatformAsset("linux-arm64", "Linux (arm64)")
    elif os_name == "Windows":
        if machine in ("x86_64", "amd64"):
            return PlatformAsset("win-x64", "Windows (x64)")
        if machine in ("arm64", "aarch64"):
            return PlatformAsset("win-arm64", "Windows (arm64)")

    raise InstallerError(
        f"Unsupported platform: {os_name} {machine}. "
        "Please install BBDown manually from https://github.com/nilaoda/BBDown/releases"
    )


def _api_get(url: str) -> dict:
    """Fetch JSON from GitHub API with a User-Agent (required by GitHub)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_latest_release() -> dict:
    """Return the latest BBDown release dict from GitHub API.

    Raises InstallerError on network/API failure.
    """
    try:
        return _api_get(GITHUB_API)
    except Exception as exc:
        raise InstallerError(
            f"Failed to fetch BBDown release info: {exc}. "
            "Check network or install BBDown manually from "
            "https://github.com/nilaoda/BBDown/releases"
        ) from exc


def pick_asset(release: dict, platform_asset: PlatformAsset) -> tuple[str, str]:
    """Pick the matching asset from a release.

    Returns (asset_name, download_url). Asset filenames look like
    ``BBDown_1.6.3_20240814_osx-x64.zip`` — we match the trailing keyword.

    Raises InstallerError if no matching asset is found.
    """
    keyword = platform_asset.keyword
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        # Match "osx-x64" in "BBDown_1.6.3_20240814_osx-x64.zip"
        if keyword in name and name.lower().endswith(".zip"):
            return name, asset["browser_download_url"]
    raise InstallerError(
        f"No BBDown asset matching '{keyword}' in release {release.get('tag_name', '?')}. "
        "Available assets: "
        + ", ".join(a.get("name", "?") for a in release.get("assets", []))
    )


def _download(url: str, dest: Path) -> None:
    """Stream-download a URL to dest with progress dots."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as f:
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)


def _find_bbdown_binary(extract_dir: Path) -> Path:
    """Locate the BBDown executable inside the extracted zip."""
    # On Windows the binary is BBDown.exe; elsewhere just BBDown.
    candidates = list(extract_dir.rglob("BBDown*"))
    # Prefer an exact "BBDown" (no extension) on non-Windows.
    exact = [p for p in candidates if p.name == "BBDown" or p.name == "BBDown.exe"]
    if exact:
        return exact[0]
    if candidates:
        return candidates[0]
    raise InstallerError("BBDown binary not found inside the downloaded zip")


def install_bbdown(target_dir: Path | None = None, *, verbose: bool = False) -> Path:
    """Download and install the latest BBDown binary.

    Args:
        target_dir: Where to place the BBDown binary. Defaults to ~/.local/bin.
        verbose: Print progress to stderr.

    Returns the installed binary path.
    Raises InstallerError on any failure.
    """
    import shutil
    import sys
    import tempfile

    target_dir = target_dir or (Path.home() / ".local" / "bin")
    target_dir.mkdir(parents=True, exist_ok=True)
    dest = target_dir / ("BBDown.exe" if platform.system() == "Windows" else "BBDown")

    pf = detect_platform()
    if verbose:
        print(f"📥 Detected platform: {pf.label} ({pf.keyword})", file=sys.stderr)

    release = fetch_latest_release()
    tag = release.get("tag_name", "unknown")
    if verbose:
        print(f"🏷️  Latest BBDown release: {tag}", file=sys.stderr)

    asset_name, download_url = pick_asset(release, pf)
    if verbose:
        print(f"📦 Asset: {asset_name}", file=sys.stderr)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / asset_name
        if verbose:
            print(f"⬇️  Downloading {download_url}", file=sys.stderr)
        _download(download_url, zip_path)

        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()
        if verbose:
            print(f"📂 Unzipping...", file=sys.stderr)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)

        src = _find_bbdown_binary(extract_dir)
        shutil.copy2(src, dest)
        # chmod +x (no-op on Windows, but harmless)
        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    if verbose:
        print(f"✅ BBDown installed to {dest}", file=sys.stderr)
        if not _is_on_path(target_dir):
            print(
                f"⚠️  {target_dir} is not on your PATH. Add it:\n"
                f"    export PATH=\"{target_dir}:$PATH\"",
                file=sys.stderr,
            )
    return dest


def _is_on_path(directory: Path) -> bool:
    import os
    paths = [Path(p) for p in os.environ.get("PATH", "").split(os.pathsep)]
    return directory in paths or str(directory) in {str(p) for p in paths}
