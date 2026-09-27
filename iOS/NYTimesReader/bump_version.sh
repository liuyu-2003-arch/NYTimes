#!/bin/bash
# Calculate and persist the next app version.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION_FILE="$SCRIPT_DIR/NYTimesReader/version.xcconfig"

read_version() {
    MARKETING_VERSION="$(awk -F= '/^MARKETING_VERSION[[:space:]]*=/ { gsub(/[[:space:]]/, "", $2); print $2; exit }' "$VERSION_FILE")"
    CURRENT_PROJECT_VERSION="$(awk -F= '/^CURRENT_PROJECT_VERSION[[:space:]]*=/ { gsub(/[[:space:]]/, "", $2); print $2; exit }' "$VERSION_FILE")"

    if [[ ! "$MARKETING_VERSION" =~ ^[0-9]+(\.[0-9]+){1,2}$ ]]; then
        echo "错误: MARKETING_VERSION 格式无效: $MARKETING_VERSION" >&2
        exit 1
    fi
    if [[ ! "$CURRENT_PROJECT_VERSION" =~ ^[0-9]+$ ]]; then
        echo "错误: CURRENT_PROJECT_VERSION 格式无效: $CURRENT_PROJECT_VERSION" >&2
        exit 1
    fi
}

write_version() {
    local new_marketing_version="$1"
    local new_build_version="$2"
    local temp_file
    temp_file="$(mktemp "$VERSION_FILE.XXXXXX")"

    awk -v marketing="$new_marketing_version" -v build="$new_build_version" '
        /^MARKETING_VERSION[[:space:]]*=/ { print "MARKETING_VERSION = " marketing; found_marketing = 1; next }
        /^CURRENT_PROJECT_VERSION[[:space:]]*=/ { print "CURRENT_PROJECT_VERSION = " build; found_build = 1; next }
        { print }
        END { if (!found_marketing || !found_build) exit 1 }
    ' "$VERSION_FILE" > "$temp_file"

    mv "$temp_file" "$VERSION_FILE"
}

read_version

if [[ "${1:-}" == "--set" ]]; then
    if [[ $# -ne 3 ]]; then
        echo "用法: $0 --set <marketing-version> <build-version>" >&2
        exit 2
    fi
    NEXT_MARKETING_VERSION="$2"
    NEXT_BUILD_VERSION="$3"
    if [[ ! "$NEXT_MARKETING_VERSION" =~ ^[0-9]+(\.[0-9]+){1,2}$ || ! "$NEXT_BUILD_VERSION" =~ ^[0-9]+$ ]]; then
        echo "错误: 版本号格式无效" >&2
        exit 2
    fi
    write_version "$NEXT_MARKETING_VERSION" "$NEXT_BUILD_VERSION"
    echo "==> 版本已更新: $NEXT_MARKETING_VERSION ($NEXT_BUILD_VERSION)"
    exit 0
fi

BUMP_MODE="${1:-patch}"
IFS=. read -r major minor patch <<< "$MARKETING_VERSION"
minor="${minor:-0}"
patch="${patch:-0}"

case "$BUMP_MODE" in
    major)
        major=$((major + 1))
        minor=0
        patch=0
        ;;
    minor)
        minor=$((minor + 1))
        patch=0
        ;;
    patch)
        patch=$((patch + 1))
        ;;
    *)
        echo "用法: $0 [patch|minor|major] 或 $0 --set <version> <build>" >&2
        exit 2
        ;;
esac

NEXT_MARKETING_VERSION="$major.$minor.$patch"
NEXT_BUILD_VERSION=$((CURRENT_PROJECT_VERSION + 1))

if [[ "${2:-}" == "--dry-run" ]]; then
    echo "$NEXT_MARKETING_VERSION $NEXT_BUILD_VERSION"
    exit 0
fi

write_version "$NEXT_MARKETING_VERSION" "$NEXT_BUILD_VERSION"
echo "==> 版本已更新: $NEXT_MARKETING_VERSION ($NEXT_BUILD_VERSION)"
