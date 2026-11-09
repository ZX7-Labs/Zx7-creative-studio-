#!/usr/bin/env bash
# Run inside the pinned Velorn checkout on the Linux x64 integration runner.
set -euo pipefail

test "$(uname -s):$(uname -m)" = Linux:x86_64
npm ci --ignore-scripts --no-audit --no-fund
assets=$(mktemp -d)
trap 'rm -rf -- "$assets"' EXIT

fetch() {
  local id=$1 name=$2 sha=$3
  local repository=https://api.github.com/repos/eugeneware/ffmpeg-static
  local download=https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1
  local output="$assets/$name"
  if curl --fail --silent --show-error --location --retry 1 --max-time 55 \
      --proto '=https' --proto-redir '=https' --header 'Accept: application/octet-stream' \
      --output "$output" "$repository/releases/assets/$id?download=1" &&
      printf '%s  %s\n' "$sha" "$output" | sha256sum --check --status; then
    return
  fi
  curl --fail --silent --show-error --location --retry 1 --max-time 55 \
    --proto '=https' --proto-redir '=https' --output "$output" "$download/$name"
  printf '%s  %s\n' "$sha" "$output" | sha256sum --check --status
}

# IDs and digests are for the upstream b6.1.1 Linux x64 release used by
# both locked 5.3.0 npm packages. Retain the original binary notices.
fetch 316528626 ffmpeg-linux-x64.gz bfe8a8fc511530457b528c48d77b5737527b504a3797a9bc4866aeca69c2dffa
fetch 316529539 ffprobe-linux-x64.gz 25d9b6ccb05e3d9de9e04e31e2506d8dd7f9f0418981965ac6df12e8d3afd067
fetch 316529924 linux-x64.LICENSE 8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903
fetch 316529927 linux-x64.README 72f4b1b06d419d22ace6e7cc75f06826f90737345aa0b1736158929f4aacc537

install_binary() {
  local package=$1 binary=$2
  local target
  target=$(node -p 'require(process.argv[1])' "$package")
  case "$target" in
    "$PWD/node_modules/$package/"*) ;;
    *) echo "Unexpected $package binary path" >&2; return 1 ;;
  esac
  gzip -dc "$assets/$binary-linux-x64.gz" > "$target"
  chmod 755 "$target"
  cp "$assets/linux-x64.LICENSE" "$target.LICENSE"
  cp "$assets/linux-x64.README" "$target.README"
}

install_binary ffmpeg-static ffmpeg
install_binary @derhuerst/ffprobe-static ffprobe
# Run every ordinary native install hook, including Electron. The two media
# packages detect their checksum-verified executables at the expected paths.
# A known Electron upstream 504 gets one checksum-preserving alternate route.
bash ../../engines/velorn/rebuild-ci-native-modules.sh
