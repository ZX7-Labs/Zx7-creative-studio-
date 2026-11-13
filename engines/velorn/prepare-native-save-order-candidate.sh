#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Reproducible, independent child of exact pinned native save-timestamp source.
# Stable/source/editorial older variants and owner workspace are left intact.
set -euo pipefail
if [[ "$#" != 3 || ( "$3" != "--inspect" && "$3" != "--install" ) ]]; then
  echo "Usage: $0 PINNED_UPSTREAM_CHECKOUT DESTINATION --inspect|--install" >&2
  exit 2
fi
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
lock="$root/../../studio_next/editor_runtime/source-lock.json"
parent=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["collab_save_revision"])' "$lock")
expected=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("collab_save_order_revision", ""))' "$lock")
out=$(realpath -m -- "$2")
test ! -e "$2" && test ! -L "$2" || { echo "Destination already exists" >&2; exit 2; }
stage=$(mktemp -d "$(dirname -- "$out")/.zx7-native-save-order.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
bash "$root/prepare-native-save-candidate.sh" "$1" "$stage/save-parent" --install
test "$(git -C "$stage/save-parent" rev-parse HEAD)" = "$parent"
git clone --quiet --no-local --no-checkout -- "$stage/save-parent" "$stage/ordered"
git -C "$stage/ordered" checkout --quiet --detach "$parent"
git -C "$stage/ordered" apply --index -- "$root/native-save-ordering.patch"
tree=$(git -C "$stage/ordered" write-tree)
rev=$(GIT_AUTHOR_NAME='ZX7 Studio' GIT_AUTHOR_EMAIL='zx7-studio@users.noreply.github.com' \
  GIT_AUTHOR_DATE='2026-11-13T00:00:00Z' GIT_COMMITTER_NAME='ZX7 Studio' \
  GIT_COMMITTER_EMAIL='zx7-studio@users.noreply.github.com' GIT_COMMITTER_DATE='2026-11-13T00:00:00Z' \
  git -C "$stage/ordered" -c commit.gpgSign=false commit-tree "$tree" -p "$parent" \
  -m 'Serialize native save writes and preserve unsaved human project edits')
git -C "$stage/ordered" checkout --quiet --detach "$rev"
git -C "$stage/ordered" diff --quiet HEAD --
node --check "$stage/ordered/src/stores/projectStore.js"
node --check "$stage/ordered/src/services/projectDirtyTracker.js"
node --check "$stage/ordered/src/services/nativeSaveSequence.js"
node --test \
  "$stage/ordered/src/services/nativeSaveSequence.test.mjs"
printf 'Reproducible ZX7 native save ordering revision: %s\n' "$rev"
if [[ "$3" == "--inspect" ]]; then exit 0; fi
test -n "$expected" && test "$rev" = "$expected" || {
  echo "Save ordering source not reviewed/pinned; refusing install" >&2
  exit 1
}
mv -T --no-clobber -- "$stage/ordered" "$out"
test ! -e "$stage/ordered"
printf 'Installed exact source-attested native-save-order variant: %s\n' "$rev"
