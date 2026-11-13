#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Build an independent, sandboxed ZX7 Studio from this source checkout.
set -euo pipefail

# Preserve the established install path as the default. The source-attested
# scene editor is a separately pinned experimental writer variant; no silent
# switch to a new native runtime or mutation of an installed prefix.
profile=stable
install_prefix=""
for argument in "$@"; do
  if [[ "$argument" == "--scene-collaboration" && "$profile" == stable ]]; then
    profile=scene
  elif [[ "$argument" == "--editorial-collaboration" && "$profile" == stable ]]; then
    profile=editorial
  elif [[ "$argument" == -* || -n "$install_prefix" ]]; then
    echo "Usage: bash scripts/install-zx7-linux.sh [--scene-collaboration|--editorial-collaboration] [INSTALL_PREFIX]" >&2
    exit 2
  else
    install_prefix=$argument
  fi
done
if [[ "$(uname -s):$(uname -m)" != Linux:x86_64 || "$EUID" == 0 ]]; then
  echo "Run this installer as an ordinary user on Ubuntu 24.04 x86-64." >&2
  exit 2
fi
if ! ( . /etc/os-release && [[ "$ID:$VERSION_ID" == ubuntu:24.04 ]] ); then
  echo "This installer supports Ubuntu 24.04 x86-64." >&2
  exit 2
fi

checkout=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
requested=${install_prefix:-"${HOME}/.local/opt/zx7-studio"}
if [[ -e "$requested" || -L "$requested" ]]; then
  echo "Install destination already exists: $requested" >&2
  exit 2
fi
target=$(realpath -m -- "$requested")
parent=$(dirname -- "$target")

echo "Installing Ubuntu dependencies with apt. The editor runs as your user."
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
  ca-certificates curl git python3 python3-venv xz-utils unzip \
  ffmpeg xvfb xauth x11-xkb-utils xkb-data \
  libnss3 libatk-bridge2.0-0 libasound2t64 libgtk-3-0 \
  libgbm1 libxss1 libxdamage1 libxcomposite1 libxrandr2 libx11-xcb1

upstream="$checkout/third_party/velorn"
if [[ ! -f "$upstream/package.json" ]]; then
  git -C "$checkout" submodule update --init --recursive -- third_party/velorn
fi

mkdir -p -- "$parent"
# Keep the Python environment at its original path. Publish only a link once
# all install steps pass, so pip entry points keep their original shebangs.
candidate=$(mktemp -d "$parent/.zx7-studio-install.XXXXXXXX")
cleanup() {
  if [[ -L "$target" ]] && [[ "$(readlink -- "$target")" == "$candidate" ]]; then
    return
  fi
  rm -rf -- "$candidate"
}
trap cleanup EXIT

node_version=24.22.2
node_archive="node-v$node_version-linux-x64.tar.xz"
node_digest=48cc0e21e048790e54c0cf5749c2725005313d652651c40b7a21feb9697aaf75
curl --fail --silent --show-error --location --retry 1 --connect-timeout 20 --max-time 120 \
  --proto '=https' --proto-redir '=https' \
  --output "$candidate/$node_archive" "https://nodejs.org/dist/v$node_version/$node_archive"
printf '%s  %s\n' "$node_digest" "$candidate/$node_archive" | sha256sum --check --status
mkdir -- "$candidate/node" "$candidate/bin"
tar --extract --xz --file "$candidate/$node_archive" --directory "$candidate/node" --strip-components=1
rm -- "$candidate/$node_archive"
export PATH="$candidate/node/bin:$PATH"
test "$(node --version)" = "v$node_version"

python3 -m venv "$candidate/venv"
"$candidate/venv/bin/python" -m pip --isolated install --disable-pip-version-check "$checkout[editor,production]"
mkdir -p "$candidate/venv/share/zx7-studio"
editor="$candidate/venv/share/zx7-studio/velorn"
if [[ "$profile" == editorial ]]; then
  # Upgrade only the explicitly opted-in editorial profile. Its reviewed
  # parent variants stay trusted; stable/default installations are untouched.
  bash "$checkout/engines/velorn/prepare-native-save-order-candidate.sh" \
    "$upstream" "$editor" --install
elif [[ "$profile" == scene ]]; then
  bash "$checkout/engines/velorn/prepare-native-scene-candidate.sh" \
    "$upstream" "$editor" --install
else
  bash "$checkout/engines/velorn/prepare-supported-source.sh" "$upstream" "$editor"
fi
(
  cd "$editor"
  bash "$checkout/engines/velorn/install-ci-dependencies.sh" supported-electron
  npm run build
  test -s dist/index.html
)
helper="$editor/node_modules/electron/dist/chrome-sandbox"
[[ -f "$helper" && ! -L "$helper" ]]
sudo chown root:root -- "$helper"
sudo chmod 4755 -- "$helper"
test "$(stat -c '%u:%a' "$helper")" = 0:4755

cat > "$candidate/bin/zx7-studio" <<'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail
installed=$(dirname -- "$(realpath -- "${BASH_SOURCE[0]}")")/..
export PATH="$installed/node/bin:$PATH"
exec "$installed/venv/bin/zx7-studio" "$@"
LAUNCHER
chmod 755 "$candidate/bin/zx7-studio"
"$candidate/bin/zx7-studio" --help >/dev/null
ln -sT -- "$candidate" "$target"
printf 'Installed Studio command: %s\n' "$target/bin/zx7-studio"
printf 'Native editor profile: %s\n' "$profile"
