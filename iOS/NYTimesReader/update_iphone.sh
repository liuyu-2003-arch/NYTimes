#!/bin/bash
# Build and install the app directly to the paired iPhone via devicectl.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_IPA="$HOME/Desktop/双语头条.ipa"
DEVICE="${DEVICE_ID:-${DEVICE_NAME:-iPhone}}"
INSTALL_TIMEOUT="${INSTALL_TIMEOUT:-180}"

read -r NEXT_MARKETING_VERSION NEXT_BUILD_VERSION < <("$SCRIPT_DIR/bump_version.sh" patch --dry-run)
export MARKETING_VERSION_OVERRIDE="$NEXT_MARKETING_VERSION"
export CURRENT_PROJECT_VERSION_OVERRIDE="$NEXT_BUILD_VERSION"

echo "==> 本次版本: $NEXT_MARKETING_VERSION ($NEXT_BUILD_VERSION)"
"$SCRIPT_DIR/build_ipa.sh"

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/nytimesreader-install.XXXXXX")"
trap 'rm -rf "$WORK_DIR"' EXIT
BACKUP_DIR="$WORK_DIR/backup"
mkdir -p "$BACKUP_DIR"

echo "==> 解压 IPA"
unzip -q "$OUTPUT_IPA" -d "$WORK_DIR"

APP_PATH="$(find "$WORK_DIR/Payload" -maxdepth 1 -name '*.app' -print -quit)"
if [[ -z "$APP_PATH" ]]; then
    echo "错误: IPA 中未找到 .app" >&2
    exit 1
fi

BUNDLE_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$APP_PATH/Info.plist")"
USER_DATA_BACKUP="$BACKUP_DIR/user-data.json"
PREFERENCES_BACKUP="$BACKUP_DIR/$BUNDLE_ID.plist"
HAS_USER_DATA_BACKUP=false
HAS_PREFERENCES_BACKUP=false

echo "==> 备份收藏和单词本"
if xcrun devicectl device copy from \
    --device "$DEVICE" \
    --domain-type appDataContainer \
    --domain-identifier "$BUNDLE_ID" \
    --source "Documents/user-data.json" \
    --destination "$USER_DATA_BACKUP" >/dev/null 2>&1; then
    HAS_USER_DATA_BACKUP=true
fi
if xcrun devicectl device copy from \
    --device "$DEVICE" \
    --domain-type appDataContainer \
    --domain-identifier "$BUNDLE_ID" \
    --source "Library/Preferences/$BUNDLE_ID.plist" \
    --destination "$PREFERENCES_BACKUP" >/dev/null 2>&1; then
    HAS_PREFERENCES_BACKUP=true
fi
if [[ "$HAS_USER_DATA_BACKUP" == true || "$HAS_PREFERENCES_BACKUP" == true ]]; then
    echo "==> 已备份现有用户数据"
else
    echo "==> 未发现现有用户数据，继续安装"
fi

echo "==> 安装到设备: $DEVICE"
xcrun devicectl device install app \
    --device "$DEVICE" \
    --timeout "$INSTALL_TIMEOUT" \
    "$APP_PATH"

if [[ "$HAS_USER_DATA_BACKUP" == true ]]; then
    echo "==> 恢复收藏和单词本"
    xcrun devicectl device copy to \
        --device "$DEVICE" \
        --domain-type appDataContainer \
        --domain-identifier "$BUNDLE_ID" \
        --source "$USER_DATA_BACKUP" \
        --destination "Documents/user-data.json"
fi
if [[ "$HAS_PREFERENCES_BACKUP" == true ]]; then
    xcrun devicectl device copy to \
        --device "$DEVICE" \
        --domain-type appDataContainer \
        --domain-identifier "$BUNDLE_ID" \
        --source "$PREFERENCES_BACKUP" \
        --destination "Library/Preferences/$BUNDLE_ID.plist"
fi

echo "==> 启动 App"
if ! xcrun devicectl device process launch --device "$DEVICE" "$BUNDLE_ID"; then
    echo "警告: 安装成功，但 App 未启动；请解锁 iPhone 后手动打开。" >&2
fi

echo "==> 完成，已安装 $BUNDLE_ID"
"$SCRIPT_DIR/bump_version.sh" --set "$NEXT_MARKETING_VERSION" "$NEXT_BUILD_VERSION"
