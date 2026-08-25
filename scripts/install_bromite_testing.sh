#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/bromite/bromite/releases/latest"
APK_DIR="/tmp/bromite-install"
mkdir -p "$APK_DIR"

LATEST_TAG=$(python3 - <<'PY'
import json, urllib.request
url='https://api.github.com/repos/bromite/bromite/releases/latest'
with urllib.request.urlopen(url, timeout=30) as r:
    data=json.load(r)
print(data['tag_name'])
PY
)

APK_NAME="arm64_ChromePublic.apk"
APK_URL="https://github.com/bromite/bromite/releases/download/${LATEST_TAG}/${APK_NAME}"
APK_PATH="$APK_DIR/${APK_NAME}"

curl -L --fail -o "$APK_PATH" "$APK_URL"
adb install -r "$APK_PATH"

echo "Installed Bromite from ${APK_URL}"
