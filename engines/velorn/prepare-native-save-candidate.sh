#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Additional reproducible single-timestamp native save source overlay.
# Preserve all prior original/desktop/scene/editorial variants unchanged.
set -euo pipefail
if [[ "$#" != 3 || ( "$3" != "--inspect" && "$3" != "--install" ) ]]; then
  echo "Usage: $0 PINNED_UPSTREAM_CHECKOUT DESTINATION --inspect|--install" >&2
  exit 2
fi
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
lock="$root/../../studio_next/editor_runtime/source-lock.json"
parent=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["collab_editorial_revision"])' "$lock")
expected=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("collab_save_revision", ""))' "$lock")
out=$(realpath -m -- "$2")
test ! -e "$2" && test ! -L "$2" || { echo "Destination already exists" >&2; exit 2; }
stage=$(mktemp -d "$(dirname -- "$out")/.zx7-native-save.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT

bash "$root/prepare-native-editorial-candidate.sh" "$1" "$stage/editorial-parent" --install
test "$(git -C "$stage/editorial-parent" rev-parse HEAD)" = "$parent"
git clone --quiet --no-local --no-checkout -- "$stage/editorial-parent" "$stage/save"
git -C "$stage/save" checkout --quiet --detach "$parent"
git -C "$stage/save" apply --index -- "$root/native-save-timestamp.patch"
tree=$(git -C "$stage/save" write-tree)
rev=$(GIT_AUTHOR_NAME='ZX7 Studio' GIT_AUTHOR_EMAIL='zx7-studio@users.noreply.github.com' \
  GIT_AUTHOR_DATE='2026-11-13T00:00:00Z' GIT_COMMITTER_NAME='ZX7 Studio' \
  GIT_COMMITTER_EMAIL='zx7-studio@users.noreply.github.com' GIT_COMMITTER_DATE='2026-11-13T00:00:00Z' \
  git -C "$stage/save" -c commit.gpgSign=false commit-tree "$tree" -p "$parent" \
  -m 'Reconcile exact native source-save revision and MCP acknowledgment')
git -C "$stage/save" checkout --quiet --detach "$rev"
git -C "$stage/save" diff --quiet HEAD --
node --check "$stage/save/src/services/fileSystem.js"
node --check "$stage/save/src/stores/projectStore.js"
printf 'Reproducible ZX7 native save revision: %s\n' "$rev"
if [[ "$3" == "--inspect" ]]; then exit 0; fi
test -n "$expected" && test "$rev" = "$expected" || {
  echo "Native save source not reviewed/pinned; refusing install" >&2
  exit 1
}
mv -T --no-clobber -- "$stage/save" "$out"
test ! -e "$stage/save"
printf 'Installed exact source-attested native-save variant: %s\n' "$rev"
