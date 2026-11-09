#!/usr/bin/env bash
# CI-only, pinned Velorn native-module postinstall. A 504 from Electron's
# upstream release download is not a failure of the native editor itself.
# Keep original npm integrity/lockfile checks and never skip native hooks.
set -euo pipefail

log="$(mktemp)"
trap 'rm -f -- "$log"' EXIT

if npm rebuild --no-audit --no-fund >"$log" 2>&1; then
  cat "$log"
  exit 0
else
  original_status=$?
  cat "$log"
fi

# Retry only the observed Electron-release HTTP 504. All other failures,
# including an integrity mismatch, remain hard failures on the first attempt.
if ! grep -Fq 'HTTPError: Response code 504' "$log" ||
   ! grep -Eq 'npm (error|ERR!) path .*/node_modules/electron' "$log"; then
  exit "$original_status"
fi

echo 'ZX7: Electron release download returned HTTP 504; trying one bounded alternate mirror.'
# Official Electron/@electron/get supports ELECTRON_MIRROR. Do not set
# electron_use_remote_checksums or override the lockfile's pinned version.
# The ordinary Electron install hook retains its existing checksum validation.
ELECTRON_MIRROR='https://npmmirror.com/mirrors/electron/' \
  npm rebuild electron --no-audit --no-fund

# Re-run all pinned native postinstalls after a successful Electron recovery;
# otherwise a partial first pass might leave other native modules unbuilt.
# The download is now cached by @electron/get. Any further failure propagates.
npm rebuild --no-audit --no-fund
