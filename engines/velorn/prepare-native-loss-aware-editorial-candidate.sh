#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Opt-in, reviewable descendant of the installed Linux cross-process editor.
# Source-only overlay; original Velorn submodule and installed prefixes are untouched.
set -euo pipefail
if [[ "$#" != 3 || ( "$3" != "--inspect" && "$3" != "--install" ) ]]; then
  echo "Usage: $0 PINNED_UPSTREAM_CHECKOUT NEW_DESTINATION --inspect|--install" >&2
  exit 2
fi
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
lock="$root/../../studio_next/editor_runtime/source-lock.json"
parent=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["collab_cross_process_revision"])' "$lock")
expected=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("loss_aware_editorial_revision", ""))' "$lock")
out=$(realpath -m -- "$2")
test ! -e "$2" && test ! -L "$2" || { echo "Destination already exists" >&2; exit 2; }
stage=$(mktemp -d "$(dirname -- "$out")/.zx7-native-loss-aware.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
bash "$root/prepare-native-cross-process-candidate.sh" "$1" "$stage/parent" --install
test "$(git -C "$stage/parent" rev-parse HEAD)" = "$parent"
git clone --quiet --no-local --no-checkout -- "$stage/parent" "$stage/candidate"
git -C "$stage/candidate" checkout --quiet --detach "$parent"
git -C "$stage/candidate" apply --index -- "$root/native-loss-aware-editorial.patch"
cp -- "$root/zx7-loss-aware-split.mjs" "$stage/candidate/src/utils/zx7-loss-aware-split.mjs"
cp -- "$root/zx7-loss-aware-split.test.mjs" "$stage/candidate/src/utils/zx7-loss-aware-split.test.mjs"
git -C "$stage/candidate" add -- src/services/mcpActions.js src/utils/zx7-loss-aware-split.mjs src/utils/zx7-loss-aware-split.test.mjs
tree=$(git -C "$stage/candidate" write-tree)
rev=$(GIT_AUTHOR_NAME='ZX7 Studio' GIT_AUTHOR_EMAIL='zx7-studio@users.noreply.github.com' \
  GIT_AUTHOR_DATE='2026-11-14T00:00:00Z' GIT_COMMITTER_NAME='ZX7 Studio' \
  GIT_COMMITTER_EMAIL='zx7-studio@users.noreply.github.com' GIT_COMMITTER_DATE='2026-11-14T00:00:00Z' \
  git -C "$stage/candidate" -c commit.gpgSign=false commit-tree "$tree" -p "$parent" \
  -m 'Bind loss-aware native editorial razor to the cross-process source fence')
git -C "$stage/candidate" checkout --quiet --detach "$rev"
git -C "$stage/candidate" diff --quiet HEAD --
node --check "$stage/candidate/src/services/mcpActions.js"
node --check "$stage/candidate/src/utils/zx7-loss-aware-split.mjs"
node --test "$stage/candidate/src/utils/zx7-loss-aware-split.test.mjs"
printf 'Reproducible ZX7 loss-aware native editorial source: %s\n' "$rev"
if [[ "$3" == "--inspect" ]]; then exit 0; fi
test -n "$expected" && test "$rev" = "$expected" || {
  echo "Loss-aware native editorial revision not reviewed and pinned; refusing install" >&2
  exit 1
}
mv -T --no-clobber -- "$stage/candidate" "$out"
test ! -e "$stage/candidate"
printf 'Installed source-attested loss-aware native editor: %s\n' "$rev"
