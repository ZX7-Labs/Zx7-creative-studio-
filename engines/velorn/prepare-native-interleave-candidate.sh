#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# CI-only fault-injection descendant: production/stable editor sources untouched.
set -euo pipefail
if [[ "$#" != 3 || ( "$3" != "--inspect" && "$3" != "--install" ) ]]; then
  echo "Usage: $0 PINNED_UPSTREAM_CHECKOUT DESTINATION --inspect|--install" >&2
  exit 2
fi
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
lock="$root/../../studio_next/editor_runtime/source-lock.json"
parent=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["collab_save_order_revision"])' "$lock")
expected=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("collab_save_interleave_revision", ""))' "$lock")
out=$(realpath -m -- "$2")
test ! -e "$2" && test ! -L "$2" || { echo "Destination already exists" >&2; exit 2; }
stage=$(mktemp -d "$(dirname -- "$out")/.zx7-native-save-interleave.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
bash "$root/prepare-native-save-order-candidate.sh" "$1" "$stage/save-parent" --install
test "$(git -C "$stage/save-parent" rev-parse HEAD)" = "$parent"
git clone --quiet --no-local --no-checkout -- "$stage/save-parent" "$stage/interleave"
git -C "$stage/interleave" checkout --quiet --detach "$parent"
git -C "$stage/interleave" apply --index -- "$root/native-save-interleaving.patch"
tree=$(git -C "$stage/interleave" write-tree)
rev=$(GIT_AUTHOR_NAME='ZX7 Studio' GIT_AUTHOR_EMAIL='zx7-studio@users.noreply.github.com' \
  GIT_AUTHOR_DATE='2026-11-13T00:00:00Z' GIT_COMMITTER_NAME='ZX7 Studio' \
  GIT_COMMITTER_EMAIL='zx7-studio@users.noreply.github.com' GIT_COMMITTER_DATE='2026-11-13T00:00:00Z' \
  git -C "$stage/interleave" -c commit.gpgSign=false commit-tree "$tree" -p "$parent" \
  -m 'Isolate native save interleaving and interrupted-write physical test boundary')
git -C "$stage/interleave" checkout --quiet --detach "$rev"
git -C "$stage/interleave" diff --quiet HEAD --
node --check "$stage/interleave/electron/main.js"
node --check "$stage/interleave/electron/nativeSaveBarrier.cjs"
node --test "$stage/interleave/electron/nativeSaveBarrier.test.mjs"
printf 'Reproducible ZX7 isolated native-save-interleave source: %s\n' "$rev"
if [[ "$3" == "--inspect" ]]; then exit 0; fi
test -n "$expected" && test "$rev" = "$expected" || {
  echo "CI-only source identity not reviewed/pinned; refusing install" >&2
  exit 1
}
mv -T --no-clobber -- "$stage/interleave" "$out"
test ! -e "$stage/interleave"
printf 'Installed exact CI-only native-save-interleave source: %s\n' "$rev"
