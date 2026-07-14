"""Tests for language-aware subtitle selection in __main__.py.

Covers the regression where ``sorted(files, key=extension)[0]`` always picked
the lexicographically-first AI subtitle (Arabic) regardless of ``--language``,
because all files share the ``.srt`` extension and language codes sort as
``ar < en < es < ja < pt < zh``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from bilibili_subtitle.__main__ import (
    _extract_lang_from_filename,
    _lang_matches,
    _select_subtitle_file,
)
from bilibili_subtitle.errors import NoSubtitleError


# ── _extract_lang_from_filename ──

class TestExtractLang:
    @pytest.mark.parametrize("filename,expected", [
        ("BV1xDTb6jEHp.ai-zh.srt", "zh"),
        ("BV1xDTb6jEHp.ai-ar.srt", "ar"),
        ("BV1xDTb6jEHp.ai-en.vtt", "en"),
        ("BV1xDTb6jEHp.ai-ja.srt", "ja"),
        ("BV1xDTb6jEHp.ai-pt.srt", "pt"),
        ("BV123.zh-Hans.srt", "zh-hans"),
        ("BV123.zh-Hant.srt", "zh-hant"),
        ("BV123.en.srt", "en"),
    ])
    def test_extracts_lang(self, filename: str, expected: str):
        assert _extract_lang_from_filename(Path(filename)) == expected

    @pytest.mark.parametrize("filename", [
        "BV1xDTb6jEHp.srt",      # single subtitle, no language tag
        "BV1xDTb6jEHp.vtt",
        "BV123.srt",
    ])
    def test_no_lang_tag_returns_none(self, filename: str):
        assert _extract_lang_from_filename(Path(filename)) is None


# ── _lang_matches ──

class TestLangMatches:
    @pytest.mark.parametrize("file_lang,preferred", [
        ("zh", "zh-Hans"),       # AI subtitle zh vs. user default zh-Hans
        ("zh", "zh-Hant"),
        ("zh", "zh"),
        ("zh-hans", "zh-Hans"),
        ("zh-hant", "zh-Hant"),
        ("zh", "zh-CN"),
        ("en", "en"),
        ("ja", "ja"),
    ])
    def test_matches(self, file_lang: str | None, preferred: str):
        assert _lang_matches(file_lang, preferred) is True

    @pytest.mark.parametrize("file_lang,preferred", [
        ("ar", "zh-Hans"),       # the original bug: ar must not match zh
        ("en", "zh-Hans"),
        ("zh", "en"),
        ("ja", "en"),
        (None, "zh-Hans"),
        (None, "en"),
    ])
    def test_no_match(self, file_lang: str | None, preferred: str):
        assert _lang_matches(file_lang, preferred) is False


# ── _select_subtitle_file ──

# Realistic file set observed for BV1xDTb6jEHp (6 AI translations, all .srt).
_REALISTIC_FILES = [
    Path("BV1xDTb6jEHp.ai-ar.srt"),
    Path("BV1xDTb6jEHp.ai-en.srt"),
    Path("BV1xDTb6jEHp.ai-es.srt"),
    Path("BV1xDTb6jEHp.ai-ja.srt"),
    Path("BV1xDTb6jEHp.ai-pt.srt"),
    Path("BV1xDTb6jEHp.ai-zh.srt"),
]


class TestSelectSubtitleFile:
    def test_default_zh_hans_picks_zh_not_ar(self):
        """Regression: with the old logic this returned the ar file."""
        chosen = _select_subtitle_file(_REALISTIC_FILES, "zh-Hans")
        assert chosen.name == "BV1xDTb6jEHp.ai-zh.srt"

    def test_explicit_zh_picks_zh(self):
        chosen = _select_subtitle_file(_REALISTIC_FILES, "zh")
        assert chosen.name == "BV1xDTb6jEHp.ai-zh.srt"

    def test_explicit_zh_hant_picks_zh(self):
        chosen = _select_subtitle_file(_REALISTIC_FILES, "zh-Hant")
        assert chosen.name == "BV1xDTb6jEHp.ai-zh.srt"

    def test_explicit_en_picks_en(self):
        chosen = _select_subtitle_file(_REALISTIC_FILES, "en")
        assert chosen.name == "BV1xDTb6jEHp.ai-en.srt"

    def test_explicit_ja_picks_ja(self):
        chosen = _select_subtitle_file(_REALISTIC_FILES, "ja")
        assert chosen.name == "BV1xDTb6jEHp.ai-ja.srt"

    def test_unavailable_language_falls_back_to_zh(self):
        """Korean is not in the file set; fall back to Chinese."""
        chosen = _select_subtitle_file(_REALISTIC_FILES, "ko")
        assert chosen.name == "BV1xDTb6jEHp.ai-zh.srt"

    def test_no_zh_available_falls_back_to_first(self):
        """If neither preferred nor zh exists, return lexicographically first."""
        files = [
            Path("BV1.ai-ar.srt"),
            Path("BV1.ai-en.srt"),
            Path("BV1.ai-es.srt"),
        ]
        chosen = _select_subtitle_file(files, "ko")
        assert chosen.name == "BV1.ai-ar.srt"

    def test_single_subtitle_no_lang_tag(self):
        """A plain {video_id}.srt with no language tag is returned as-is."""
        files = [Path("BV12345.srt")]
        chosen = _select_subtitle_file(files, "zh-Hans")
        assert chosen.name == "BV12345.srt"

    def test_plain_subtitle_with_lang_tag(self):
        """Non-AI subtitles named {video_id}.{lang}.srt also work."""
        files = [
            Path("BV123.zh-Hans.srt"),
            Path("BV123.en.srt"),
        ]
        chosen = _select_subtitle_file(files, "en")
        assert chosen.name == "BV123.en.srt"

    def test_empty_list_raises(self):
        with pytest.raises(NoSubtitleError):
            _select_subtitle_file([], "zh-Hans")

    def test_selection_is_deterministic(self):
        """Repeated calls with shuffled input yield the same result."""
        import random
        files = list(_REALISTIC_FILES)
        results = set()
        for _ in range(10):
            shuffled = files[:]
            random.shuffle(shuffled)
            chosen = _select_subtitle_file(shuffled, "zh-Hans")
            results.add(chosen.name)
        assert results == {"BV1xDTb6jEHp.ai-zh.srt"}
