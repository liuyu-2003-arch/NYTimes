#!/bin/bash
# 一键打包 .ipa（用于 AltStore / SideStore 安装）
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEAM_ID="${TEAM_ID:-PW9G92A5Q4}"
MARKETING_VERSION_OVERRIDE="${MARKETING_VERSION_OVERRIDE:-}"
CURRENT_PROJECT_VERSION_OVERRIDE="${CURRENT_PROJECT_VERSION_OVERRIDE:-}"
ARCHIVE_PATH="/tmp/NYTimesReader.xcarchive"
IPA_DIR="/tmp/NYTimesReader_ipa"
EXPORT_OPTIONS="/tmp/ExportOptions.plist"
OUTPUT_IPA="$HOME/Desktop/双语头条.ipa"

cat > "$EXPORT_OPTIONS" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>development</string>
    <key>signingStyle</key>
    <string>automatic</string>
    <key>teamID</key>
    <string>$TEAM_ID</string>
    <key>stripSwiftSymbols</key>
    <true/>
    <key>compileBitcode</key>
    <false/>
</dict>
</plist>
PLIST

echo "==> 清理旧文件"
rm -rf "$ARCHIVE_PATH" "$IPA_DIR"

echo "==> 归档构建"
cd "$PROJECT_DIR"
BUILD_SETTINGS=(
    "DEVELOPMENT_TEAM=$TEAM_ID"
    "CODE_SIGN_STYLE=Automatic"
)
if [[ -n "$MARKETING_VERSION_OVERRIDE" ]]; then
    BUILD_SETTINGS+=("MARKETING_VERSION=$MARKETING_VERSION_OVERRIDE")
fi
if [[ -n "$CURRENT_PROJECT_VERSION_OVERRIDE" ]]; then
    BUILD_SETTINGS+=("CURRENT_PROJECT_VERSION=$CURRENT_PROJECT_VERSION_OVERRIDE")
fi

xcodebuild -project ../NYTimesReader.xcodeproj \
    -scheme NYTimesReader \
    -configuration Release \
    -allowProvisioningUpdates \
    -destination 'generic/platform=iOS' \
    "${BUILD_SETTINGS[@]}" \
    -archivePath "$ARCHIVE_PATH" \
    archive -quiet

echo "==> 导出 .ipa"
xcodebuild -exportArchive \
    -archivePath "$ARCHIVE_PATH" \
    -exportPath "$IPA_DIR" \
    -exportOptionsPlist "$EXPORT_OPTIONS" \
    -allowProvisioningUpdates -quiet

cp "$IPA_DIR/NYTimesReader.ipa" "$OUTPUT_IPA"
echo "==> 完成: $OUTPUT_IPA"
ls -lh "$OUTPUT_IPA"
