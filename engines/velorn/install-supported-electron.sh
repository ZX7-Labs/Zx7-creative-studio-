#!/usr/bin/env bash
# Provision the official supported Linux x64 Electron runtime for native proof.
set -euo pipefail

test "$(uname -s):$(uname -m)" = Linux:x86_64
version=45.2.3
archive="electron-v$version-linux-x64.zip"
digest=a87fe741f6d121285117e574da6c9a2e65210d410123bbc04713b099add0263b
package="$PWD/node_modules/electron"
test -f "$package/index.js"
test ! -e "$package/dist"
test ! -e "$package/path.txt"

stage=$(mktemp -d "$package/.zx7-electron.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
curl --fail --silent --show-error --location --retry 1 --max-time 120 \
  --proto '=https' --proto-redir '=https' \
  --output "$stage/$archive" "https://github.com/electron/electron/releases/download/v$version/$archive"
printf '%s  %s\n' "$digest" "$stage/$archive" | sha256sum --check --status
unzip -q "$stage/$archive" -d "$stage/dist"
[[ -x "$stage/dist/electron" && ! -L "$stage/dist/electron" ]]
[[ -f "$stage/dist/chrome-sandbox" && ! -L "$stage/dist/chrome-sandbox" ]]
actual=$(cat "$stage/dist/version")
test "${actual#v}" = "$version"
# The pinned npm loader uses the complete contents of path.txt as the name.
printf '%s' electron > "$stage/path.txt"
mv -T -- "$stage/dist" "$package/dist"
mv -T -- "$stage/path.txt" "$package/path.txt"
printf 'Installed checksum-verified Electron %s\n' "$version"
