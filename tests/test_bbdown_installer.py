"""Tests for bbdown_installer platform detection and asset matching."""

from bilibili_subtitle.bbdown_installer import (
    PlatformAsset,
    detect_platform,
    pick_asset,
)


def test_detect_platform_returns_valid_keyword() -> None:
    """detect_platform must return one of the known asset keywords."""
    pf = detect_platform()
    assert pf.keyword in {
        "osx-x64",
        "osx-arm64",
        "linux-x64",
        "linux-arm64",
        "win-x64",
        "win-arm64",
    }
    assert pf.label  # non-empty human-readable label


def test_pick_asset_matches_osx_x64() -> None:
    """pick_asset finds the osx-x64 asset among release assets."""
    release = {
        "tag_name": "1.6.3",
        "assets": [
            {"name": "BBDown_1.6.3_20240814_linux-arm64.zip", "browser_download_url": "u1"},
            {"name": "BBDown_1.6.3_20240814_osx-x64.zip", "browser_download_url": "u2"},
            {"name": "BBDown_1.6.3_20240814_osx-arm64.zip", "browser_download_url": "u3"},
            {"name": "BBDown_1.6.3_20240814_win-x64.zip", "browser_download_url": "u4"},
        ],
    }
    name, url = pick_asset(release, PlatformAsset("osx-x64", "macOS Intel"))
    assert name == "BBDown_1.6.3_20240814_osx-x64.zip"
    assert url == "u2"


def test_pick_asset_matches_osx_arm64() -> None:
    release = {
        "tag_name": "1.6.3",
        "assets": [
            {"name": "BBDown_1.6.3_20240814_osx-arm64.zip", "browser_download_url": "u"},
        ],
    }
    name, url = pick_asset(release, PlatformAsset("osx-arm64", "macOS ARM"))
    assert "osx-arm64" in name
    assert url == "u"


def test_pick_asset_no_match_raises() -> None:
    import pytest

    release = {
        "tag_name": "1.6.3",
        "assets": [
            {"name": "BBDown_1.6.3_20240814_linux-x64.zip", "browser_download_url": "u"},
        ],
    }
    with pytest.raises(Exception):
        pick_asset(release, PlatformAsset("osx-x64", "macOS Intel"))


def test_pick_asset_ignores_non_zip() -> None:
    """Non-zip files with the keyword in the name must be ignored."""
    release = {
        "tag_name": "1.6.3",
        "assets": [
            {"name": "BBDown_osx-x64.txt", "browser_download_url": "u1"},
            {"name": "BBDown_1.6.3_20240814_osx-x64.zip", "browser_download_url": "u2"},
        ],
    }
    name, url = pick_asset(release, PlatformAsset("osx-x64", "macOS Intel"))
    assert name.endswith(".zip")
    assert url == "u2"
