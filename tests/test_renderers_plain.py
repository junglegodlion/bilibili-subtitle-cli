from bilibili_subtitle.renderers.markdown import render_plain_markdown
from bilibili_subtitle.segment import Segment


def test_render_plain_basic() -> None:
    s = render_plain_markdown([Segment(0, 1000, "a"), Segment(1000, 2000, "b")])
    # No timestamps, just paragraphs separated by blank lines.
    assert "00:00:00" not in s
    assert "00:00:01" not in s
    assert "a\n\nb\n" in s


def test_render_plain_with_title() -> None:
    s = render_plain_markdown([Segment(0, 1000, "hello")], title="My Video")
    assert s.startswith("# My Video\n")
    assert "hello" in s
    # No timestamp heading anywhere.
    assert "## " not in s


def test_render_plain_no_title() -> None:
    s = render_plain_markdown([Segment(0, 1000, "hello")])
    assert not s.startswith("# ")
    assert s.strip() == "hello"


def test_render_plain_bilingual() -> None:
    zh = [Segment(0, 1000, "你好")]
    en = [Segment(0, 1000, "Hello")]
    s = render_plain_markdown(zh, segments_en=en)
    assert "你好\n\nHello" in s
    assert "## " not in s


def test_render_plain_bilingual_mismatched_length() -> None:
    import pytest

    zh = [Segment(0, 1000, "你好")]
    en = [Segment(0, 1000, "Hello"), Segment(1000, 2000, "World")]
    with pytest.raises(ValueError):
        render_plain_markdown(zh, segments_en=en)
