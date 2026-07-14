#!/bin/bash

# bilibili-subtitle CLI — BBDown installer (curl version, no gh dependency)
# Downloads the latest BBDown release from GitHub into ~/.local/bin

set -e

BBDOWN_DRY_RUN="${BBDOWN_DRY_RUN:-}"
BBDOWN_FORCE_INSTALL="${BBDOWN_FORCE_INSTALL:-}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  BBDown Installer (curl)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# --- Platform detection ---
BBDOWN_OS="${BBDOWN_OS:-$(uname -s)}"
BBDOWN_ARCH="${BBDOWN_ARCH:-$(uname -m)}"
case "$BBDOWN_OS" in
    Darwin) BBDOWN_PLATFORM="osx" ;;
    Linux)  BBDOWN_PLATFORM="linux" ;;
    MINGW*|MSYS*|CYGWIN*) BBDOWN_PLATFORM="win" ;;
    *) echo -e "${RED}❌ 不支持的系统: $BBDOWN_OS${NC}"; exit 1 ;;
esac
case "$BBDOWN_ARCH" in
    x86_64|amd64) BBDOWN_ARCH_NAME="x64" ;;
    arm64|aarch64) BBDOWN_ARCH_NAME="arm64" ;;
    *) echo -e "${RED}❌ 不支持的架构: $BBDOWN_ARCH${NC}"; exit 1 ;;
esac
BBDOWN_KEYWORD="${BBDOWN_PLATFORM}-${BBDOWN_ARCH_NAME}"

if [ -n "$BBDOWN_DRY_RUN" ]; then
    echo "BBDOWN_KEYWORD=$BBDOWN_KEYWORD"
    exit 0
fi

# --- curl prerequisite ---
if ! command -v curl &> /dev/null; then
    echo -e "${RED}❌ 需要 curl 来下载 BBDown${NC}"
    exit 1
fi
if ! command -v unzip &> /dev/null; then
    echo -e "${RED}❌ 需要 unzip 来解压${NC}"
    exit 1
fi

# --- Fetch latest release info from GitHub API ---
echo -e "${YELLOW}[1/3] 获取 BBDown 最新版本...${NC}"
API_RESP=$(curl -fsSL -H "User-Agent: bilibili-subtitle-installer" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/nilaoda/BBDown/releases/latest" 2>/dev/null)

if [ -z "$API_RESP" ]; then
    echo -e "${RED}❌ 无法获取 BBDown release 信息（请检查网络）${NC}"
    exit 1
fi

BBDOWN_TAG=$(echo "$API_RESP" | /usr/bin/python3 -c "import sys,json; print(json.load(sys.stdin).get('tag_name',''))" 2>/dev/null || echo "")
if [ -z "$BBDOWN_TAG" ]; then
    echo -e "${RED}❌ 解析版本号失败${NC}"
    exit 1
fi
echo -e "${GREEN}✅ 最新版本: $BBDOWN_TAG${NC}"

# --- Pick matching asset ---
DOWNLOAD_URL=$(echo "$API_RESP" | /usr/bin/python3 -c "
import sys, json
data = json.load(sys.stdin)
keyword = '$BBDOWN_KEYWORD'
for a in data.get('assets', []):
    name = a.get('name', '')
    if keyword in name and name.lower().endswith('.zip'):
        print(a['browser_download_url'])
        break
" 2>/dev/null)

if [ -z "$DOWNLOAD_URL" ]; then
    echo -e "${RED}❌ 未找到匹配 $BBDOWN_KEYWORD 的资产${NC}"
    exit 1
fi
echo -e "${GREEN}✅ 匹配资产: $(basename "$DOWNLOAD_URL")${NC}"

# --- Download & install ---
BBDOWN_BIN="$HOME/.local/bin"
mkdir -p "$BBDOWN_BIN"

BBDOWN_TMP=$(mktemp -d)
trap 'rm -rf "$BBDOWN_TMP"' EXIT

echo -e "${YELLOW}[2/3] 下载 BBDown...${NC}"
curl -fsSL -o "$BBDOWN_TMP/bbdown.zip" "$DOWNLOAD_URL"

echo -e "${YELLOW}[3/3] 安装到 $BBDOWN_BIN...${NC}"
BBDOWN_EXTRACT="$BBDOWN_TMP/extract"
mkdir -p "$BBDOWN_EXTRACT"
unzip -q "$BBDOWN_TMP/bbdown.zip" -d "$BBDOWN_EXTRACT"

NEW_BIN="$BBDOWN_EXTRACT/BBDown"
if [ ! -f "$NEW_BIN" ]; then
    NEW_BIN=$(find "$BBDOWN_EXTRACT" -type f -name 'BBDown*' | head -n1)
fi
if [ -z "$NEW_BIN" ] || [ ! -f "$NEW_BIN" ]; then
    echo -e "${RED}❌ 压缩包中未找到 BBDown${NC}"
    exit 1
fi

chmod +x "$NEW_BIN"
OLD_BIN="$BBDOWN_BIN/BBDown"
if [ -f "$OLD_BIN" ] && [ -z "$BBDOWN_FORCE_INSTALL" ]; then
    if cmp -s "$NEW_BIN" "$OLD_BIN"; then
        echo -e "${GREEN}✅ BBDown 已是最新 ($BBDOWN_TAG)${NC}"
    else
        cp "$NEW_BIN" "$OLD_BIN"
        chmod +x "$OLD_BIN"
        echo -e "${GREEN}✅ BBDown 已更新到 $BBDOWN_TAG${NC}"
    fi
else
    cp "$NEW_BIN" "$OLD_BIN"
    chmod +x "$OLD_BIN"
    echo -e "${GREEN}✅ BBDown $BBDOWN_TAG 安装完成${NC}"
fi

if ! echo "$PATH" | grep -q "$BBDOWN_BIN"; then
    echo ""
    echo -e "${YELLOW}提示：请确保 $BBDOWN_BIN 在 PATH 中${NC}"
    echo "  export PATH=\"$BBDOWN_BIN:\$PATH\""
fi

echo ""
echo -e "${BLUE}🔐 BBDown 认证${NC}"
echo "首次下载字幕前建议登录："
echo -e "${GREEN}  BBDown login${NC}"
echo ""
echo -e "${BLUE}✅ 验证命令${NC}"
echo -e "${GREEN}  bilibili-subtitle --check${NC}"
echo ""
echo -e "${GREEN}✅ 安装完成！${NC}"
