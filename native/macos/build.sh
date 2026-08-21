#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export KOREAN_TECH_WIRE_SOURCE_REVISION="$(git -C "$ROOT" rev-parse HEAD)"
exec "${PYTHON:-python3}" -m PyInstaller --noconfirm --clean --windowed --paths "$ROOT/src" --name "Korean Tech Wire" --onedir --distpath "$ROOT/native/macos/dist" --workpath "$ROOT/native/macos/build" --osx-bundle-identifier com.clank.koreantechwire.fieldtest --add-data "$ROOT/config:config" "$ROOT/native/macos/launcher.py"
