"""
CLI entry point for bilibili-subtitle.

Usage:
    bilibili-subtitle "BV1234567890"
    bilibili-subtitle --check
    bilibili-subtitle "URL" --language zh-Hans -o ./output
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from .bbdown_client import BBDownClient, BBDownError
from .bbdown_installer import InstallerError, install_bbdown
from .contract import ExitCode, ExecutionResult, SubtitleOutput
from .errors import (
    InvalidURLError,
    NoSubtitleError,
    OutputWriteError,
    SkillError,
    SubtitleContentError,
    exit_code_for_error,
)
from .languages import normalize_lang
from .preflight import run_preflight
from .renderers.markdown import render_plain_markdown, render_transcript_markdown
from .renderers.srt import render_srt
from .renderers.vtt import render_vtt
from .subtitle_loader import load_segments_from_subtitle_file
from .url_parser import parse_bilibili_ref

# Matches the language tag in BBDown subtitle filenames.
# BBDown names AI subtitles as "{video_id}.ai-{lang}.srt" and plain subtitles
# as "{video_id}.{lang}.srt". We capture the trailing tag after the last dot.
_LANG_TAG_RE = re.compile(r"\.(ai-)?([a-zA-Z]{2,3}(?:-[a-zA-Z0-9]+)?)$", re.IGNORECASE)

# Language codes that should all be treated as Chinese for matching purposes.
_ZH_LANG_CODES = {"zh", "zh-hans", "zh-hant", "zh-cn", "zh-tw", "zh-sg"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bilibili_subtitle",
        description="Extract Bilibili subtitles with BBDown and render SRT/VTT/Markdown outputs.",
    )
    parser.add_argument("input", nargs="?", help="Bilibili URL, BV ID, or av ID")
    parser.add_argument("-o", "--output-dir", default="./output", help="Output directory")
    parser.add_argument(
        "--language",
        default="zh-Hans",
        help="BBDown subtitle language selector, for example zh-Hans, zh-Hant, en",
    )
    parser.add_argument(
        "--json-output", action="store_true", help="Print machine-readable JSON result"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--check", action="store_true", help="Run preflight checks")
    parser.add_argument(
        "--check-json", action="store_true", help="Output preflight checks as JSON"
    )
    parser.add_argument(
        "--install-bbdown",
        action="store_true",
        help="Download and install the latest BBDown binary to ~/.local/bin",
    )
    return parser


def _safe_filename(value: str | None, fallback: str) -> str:
    name = (value or fallback).strip() or fallback
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:120] or fallback


def _extract_lang_from_filename(path: Path) -> str | None:
    """Extract the language code from a BBDown subtitle filename.

    BBDown naming conventions observed:
      - AI subtitles:    "{video_id}.ai-{lang}.srt"  e.g. BV1xDTb6jEHp.ai-zh.srt
      - Plain subtitles: "{video_id}.{lang}.srt"     e.g. BV123.zh-Hans.srt
      - Single subtitle: "{video_id}.srt"            (no language tag)

    Returns the normalized language code (e.g. "zh", "en", "zh-Hans") or
    None when no language tag is present.
    """
    # Match against the stem (extension stripped) so that a plain
    # "{video_id}.srt" file is not misread as language code "srt".
    match = _LANG_TAG_RE.search(path.stem)
    if not match:
        return None
    return match.group(2).lower()


def _lang_matches(file_lang: str | None, preferred: str) -> bool:
    """Check whether a subtitle file's language matches the user's preference.

    Both sides are normalized via ``normalize_lang``. All Chinese variants
    (zh, zh-Hans, zh-Hant, zh-CN, zh-TW, ...) are treated as mutually
    compatible, since Bilibili AI subtitles typically only expose ``zh``
    while users commonly pass ``zh-Hans`` / ``zh-Hant``.
    """
    if not file_lang:
        return False
    norm_file = normalize_lang(file_lang).lower()
    norm_preferred = normalize_lang(preferred).lower()
    if norm_preferred in _ZH_LANG_CODES:
        return norm_file in _ZH_LANG_CODES
    return norm_file == norm_preferred


def _select_subtitle_file(files: list[Path], preferred_lang: str) -> Path:
    """Pick the best subtitle file from a list of downloaded files.

    Priority:
      1. A file whose language matches the user-requested ``preferred_lang``.
      2. A Chinese file (zh / zh-Hans / zh-Hant), as a sane default for the
         predominantly Chinese Bilibili catalog.
      3. The lexicographically first file, preserving prior behavior as a
         last-resort fallback.

    Raises ``NoSubtitleError`` if ``files`` is empty.
    """
    if not files:
        raise NoSubtitleError("video")

    # 1. Exact preferred-language match (stable order for determinism).
    for path in sorted(files, key=lambda p: p.name):
        if _lang_matches(_extract_lang_from_filename(path), preferred_lang):
            return path

    # 2. Fall back to any Chinese subtitle.
    for path in sorted(files, key=lambda p: p.name):
        if _lang_matches(_extract_lang_from_filename(path), "zh-Hans"):
            return path

    # 3. Last-resort: lexicographically first file.
    return sorted(files, key=lambda p: p.name)[0]


def _write_outputs(
    *,
    segments: list,
    output_dir: Path,
    basename: str,
    title: str | None,
) -> dict[str, Path]:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputWriteError(str(output_dir), str(exc)) from exc

    files = {
        "srt": output_dir / f"{basename}.srt",
        "vtt": output_dir / f"{basename}.vtt",
        "transcript": output_dir / f"{basename}.transcript.md",
        "plain": output_dir / f"{basename}.plain.md",
    }
    try:
        files["srt"].write_text(render_srt(segments), encoding="utf-8")
        files["vtt"].write_text(render_vtt(segments), encoding="utf-8")
        files["transcript"].write_text(
            render_transcript_markdown(segments, title=title), encoding="utf-8"
        )
        files["plain"].write_text(
            render_plain_markdown(segments, title=title), encoding="utf-8"
        )
    except OSError as exc:
        raise OutputWriteError(str(output_dir), str(exc)) from exc
    return files


def run_extraction(
    url_or_id: str,
    *,
    output_dir: Path,
    language: str = "zh-Hans",
    verbose: bool = False,
) -> ExecutionResult:
    ref = parse_bilibili_ref(url_or_id)
    if not ref.video_id:
        raise InvalidURLError(url_or_id)

    url = ref.canonical_url or ref.input_value
    client = BBDownClient()

    if verbose:
        print(f"📥 Downloading subtitles via BBDown: {url}", file=sys.stderr)
    info = client.get_video_info(url, output_dir, lang=language)
    if not info.subtitle_files:
        raise NoSubtitleError(ref.video_id or "video")

    subtitle_file = _select_subtitle_file(info.subtitle_files, language)
    loaded = load_segments_from_subtitle_file(subtitle_file, title=info.title)
    if not loaded.segments:
        raise SubtitleContentError("parsed subtitle file contains no segments")

    video_id = info.video_id or ref.video_id or "bilibili"
    basename = _safe_filename(info.title, video_id)
    files = _write_outputs(
        segments=loaded.segments,
        output_dir=output_dir,
        basename=basename,
        title=info.title,
    )

    warnings: list[str] = []
    if not loaded.relevant:
        warnings.append("Subtitle content may not match the video title")

    return ExecutionResult(
        exit_code=ExitCode.SUCCESS,
        output=SubtitleOutput(
            video_id=video_id,
            title=info.title,
            transcript=files["transcript"],
            srt=files["srt"],
            vtt=files["vtt"],
            plain=files["plain"],
        ),
        warnings=warnings,
        errors=[],
    )


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.check:
        report = run_preflight()
        if args.check_json or args.json_output:
            print(report.to_json())
        else:
            report.print_report()
            print()
            print("✅ Ready to proceed" if report.can_proceed else "❌ Fix errors before proceeding")
        return 0 if report.can_proceed else 1

    if args.install_bbdown:
        try:
            install_bbdown(verbose=args.verbose)
        except InstallerError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            return 1
        return 0

    if not args.input:
        parser.error("input is required unless --check or --install-bbdown is used")

    try:
        result = run_extraction(
            args.input,
            output_dir=Path(args.output_dir),
            language=args.language,
            verbose=args.verbose,
        )
    except BBDownError as exc:
        error = NoSubtitleError() if "no subtitle" in str(exc).lower() else None
        if args.json_output:
            _print_json(
                {
                    "exit_code": 1,
                    "success": False,
                    "error": {
                        "code": error.code if error else "E003",
                        "message": str(exc),
                    },
                }
            )
        else:
            print(f"❌ BBDown error: {exc}", file=sys.stderr)
        return 1
    except SkillError as exc:
        code = exit_code_for_error(exc)
        if args.json_output:
            _print_json({"exit_code": code, "success": False, "error": exc.to_json()})
        else:
            print(f"❌ {exc}", file=sys.stderr)
        return code
    except Exception as exc:  # pragma: no cover - last-resort CLI guard
        if args.json_output:
            _print_json(
                {
                    "exit_code": 1,
                    "success": False,
                    "error": {"code": "E999", "message": str(exc)},
                }
            )
        else:
            print(f"❌ Unexpected error: {exc}", file=sys.stderr)
        return 1

    if args.json_output:
        _print_json(result.to_json())
    else:
        print("✅ Subtitles extracted")
        if result.output:
            print(f"📄 Transcript: {result.output.transcript}")
            print(f"📄 Plain: {result.output.plain}")
            print(f"🎬 SRT: {result.output.srt}")
            print(f"🎬 VTT: {result.output.vtt}")
        for warning in result.warnings:
            print(f"⚠️  {warning}")
    return result.exit_code.value


def cli() -> None:
    """Console-script entry point (registered via [project.scripts])."""
    sys.exit(main())


if __name__ == "__main__":
    sys.exit(main())
