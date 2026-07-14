from __future__ import annotations

from ..segment import Segment
from ._time import format_timestamp_vtt


def render_transcript_markdown(
    segments_zh: list[Segment],
    *,
    segments_en: list[Segment] | None = None,
    title: str | None = None,
) -> str:
    if segments_en is not None and len(segments_en) != len(segments_zh):
        raise ValueError("Bilingual output requires equal-length zh/en segment lists.")

    lines: list[str] = []
    if title:
        lines.append(f"# {title}")
        lines.append("")

    for i, zh in enumerate(segments_zh):
        start = format_timestamp_vtt(zh.start_ms)
        end = format_timestamp_vtt(zh.end_ms)
        if segments_en is not None:
            en = segments_en[i]
            if (en.start_ms, en.end_ms) != (zh.start_ms, zh.end_ms):
                raise ValueError("Bilingual zh/en segments must share timestamps.")
            text = f"{zh.text}\n\n{en.text}"
        else:
            text = zh.text
        lines.append(f"## {start} - {end}")
        lines.append(text)
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def render_plain_markdown(
    segments_zh: list[Segment],
    *,
    segments_en: list[Segment] | None = None,
    title: str | None = None,
) -> str:
    """Render segments as a plain Markdown transcript without timestamps.

    Keeps the H1 title and joins each segment's text as its own paragraph.
    Bilingual output stacks zh text above en text within each paragraph.
    """
    if segments_en is not None and len(segments_en) != len(segments_zh):
        raise ValueError("Bilingual output requires equal-length zh/en segment lists.")

    lines: list[str] = []
    if title:
        lines.append(f"# {title}")
        lines.append("")

    for i, zh in enumerate(segments_zh):
        if segments_en is not None:
            en = segments_en[i]
            if (en.start_ms, en.end_ms) != (zh.start_ms, zh.end_ms):
                raise ValueError("Bilingual zh/en segments must share timestamps.")
            text = f"{zh.text}\n\n{en.text}"
        else:
            text = zh.text
        lines.append(text)
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"

