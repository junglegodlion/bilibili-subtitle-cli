# bilibili-subtitle

BBDown-only Bilibili subtitle extractor CLI. Downloads Bilibili subtitles (including Bilibili AI subtitles) via [BBDown](https://github.com/nilaoda/BBDown) and renders Markdown / SRT / VTT transcripts.

## Features

- Parse Bilibili URLs, BV IDs, and av IDs
- Download regular or AI subtitles via BBDown
- Render Markdown transcript, SRT, and VTT outputs
- JSON output mode for programmatic invocation
- Preflight checks for BBDown and login state

## Requirements

| Requirement | Purpose |
| --- | --- |
| Python >= 3.11 | Runtime |
| BBDown | Subtitle download (external binary) |
| gh CLI | Used by `install_bbdown.sh` to download BBDown nightly |

## Install

### Quick install for users (via uv, recommended for sharing)

The simplest way to install on a new machine — `uv` automatically manages the
Python 3.11+ runtime, no manual Python version juggling required:

```bash
# 1. Install uv (one time)
brew install uv                  # macOS
#   or: curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Install bilibili-subtitle from git (uv pulls the right Python automatically)
uv tool install git+https://github.com/junglegodlion/bilibili-subtitle-cli.git

# 3. Install BBDown binary (built-in, downloads from GitHub Releases, no gh needed)
bilibili-subtitle --install-bbdown

# 4. Verify
bilibili-subtitle --check
```

After step 2, the `bilibili-subtitle` command is on your PATH (uv wires it up
automatically). Step 3 downloads the latest BBDown release into `~/.local/bin`.

### Install from source (for development)

```bash
git clone https://github.com/junglegodlion/bilibili-subtitle-cli.git
cd bilibili-subtitle
pip install -e .[dev]            # needs Python 3.11+ already installed
```

### Install BBDown (alternative: shell script)

If you prefer not to use the built-in `--install-bbdown` subcommand:

```bash
./install_bbdown.sh
```

This downloads the latest BBDown release from GitHub into `~/.local/bin/BBDown`
via `curl` (no `gh` CLI dependency).

Ensure `~/.local/bin` is on your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

### Login (recommended)

Restricted videos require Bilibili authentication:

```bash
BBDown login
```

Scan the QR code; the cookie is saved to `BBDown.data`.

### Verify

```bash
bilibili-subtitle --check
```

## Usage

```bash
# Basic extraction
bilibili-subtitle "BV1xx411c7mD" -o ./output

# From URL with language selection
bilibili-subtitle "https://www.bilibili.com/video/BV..." --language zh-Hans

# JSON output for scripting
bilibili-subtitle "BV1xx411c7mD" -o /tmp/output --json-output

# Preflight checks
bilibili-subtitle --check
bilibili-subtitle --check-json

# Install BBDown binary
bilibili-subtitle --install-bbdown

# Verbose
bilibili-subtitle "BV1xx411c7mD" -v
```

## Outputs

For each video, the CLI writes to the output directory:

- `{title}.transcript.md` — Markdown transcript (with timestamps)
- `{title}.plain.md` — Markdown transcript (without timestamps, pure text)
- `{title}.srt` — SRT subtitle
- `{title}.vtt` — WebVTT subtitle

## Exit Codes

| Code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Fatal error (BBDown missing, auth required, invalid URL, write failure) |
| 2 | Recoverable error (download failed, no subtitles, invalid content) |

## JSON Contract

With `--json-output`, stdout contains:

```json
{
  "exit_code": 0,
  "success": true,
  "output": {
    "video_id": "BV...",
    "title": "Video Title",
    "files": {
      "transcript": "/tmp/output/Video.transcript.md",
      "plain": "/tmp/output/Video.plain.md",
      "srt": "/tmp/output/Video.srt",
      "vtt": "/tmp/output/Video.vtt"
    }
  },
  "warnings": [],
  "errors": []
}
```

## Error Codes

| Code | Level | Meaning | Remediation |
| --- | --- | --- | --- |
| E001 | FATAL | BBDown missing | Run `./install_bbdown.sh` |
| E002 | FATAL | BBDown auth required | Run `BBDown login` |
| E003 | RECOVERABLE | Download failed | Check URL/network/login/language |
| E004 | RECOVERABLE | No downloadable subtitles | Try another language or video |
| E005 | FATAL | Invalid URL/ID | Provide a Bilibili URL, BV ID, or av ID |
| E006 | FATAL | Output write failed | Check output directory permissions |
| E007 | RECOVERABLE | Invalid subtitle content | Retry or inspect BBDown output |

## Development

```bash
pip install -e .[dev]
pytest -q
```

## Troubleshooting

- `BBDown not found`: run `./install_bbdown.sh` and ensure `~/.local/bin` is on `PATH`
- `BBDown authentication required`: run `BBDown login`
- No subtitle files: confirm the video has downloadable subtitles or try `--language zh-Hans`

## Notes

This tool only works for videos that have downloadable subtitles exposed by BBDown. There is no ASR fallback.
