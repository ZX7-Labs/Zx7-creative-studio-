#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Reproducible native GUI + model MCP source editing parity. New opt-in child;
# no mutation of old installed sources, media, models or private projects.
set -euo pipefail
if [[ "$#" != 3 || ( "$3" != "--inspect" && "$3" != "--install" ) ]]; then
  echo "Usage: $0 PINNED_UPSTREAM_CHECKOUT NEW_DESTINATION --inspect|--install" >&2
  exit 2
fi
root=$(cd -- "$(dirname -- "$0")" && pwd -P)
lock="$root/../../studio_next/editor_runtime/source-lock.json"
parent=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["loss_aware_extract_revision"])' "$lock")
expected=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("native_gui_range_revision",""))' "$lock")
out=$(realpath -m -- "$2")
test ! -e "$2" && test ! -L "$2" || { echo "Destination already exists" >&2; exit 2; }
stage=$(mktemp -d "$(dirname -- "$out")/.zx7-native-gui-range.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
bash "$root/prepare-native-loss-aware-extract-candidate.sh" "$1" "$stage/parent" --install
test "$(git -C "$stage/parent" rev-parse HEAD)" = "$parent"
git clone --quiet --no-local --no-checkout -- "$stage/parent" "$stage/candidate"
git -C "$stage/candidate" checkout --quiet --detach "$parent"
cp -- "$root/zx7-native-range-review.mjs" "$stage/candidate/src/utils/zx7-native-range-review.mjs"
cp -- "$root/zx7-native-range-review.test.mjs" "$stage/candidate/src/utils/zx7-native-range-review.test.mjs"
python3 "$root/native-gui-range-transform.py" "$stage/candidate"
git -C "$stage/candidate" add -- src/utils/zx7-native-range-review.mjs \
  src/utils/zx7-native-range-review.test.mjs \
  src/stores/timelineStore.js src/components/Timeline.jsx
tree=$(git -C "$stage/candidate" write-tree)
rev=$(GIT_AUTHOR_NAME='ZX7 Studio' GIT_AUTHOR_EMAIL='zx7-studio@users.noreply.github.com' \
  GIT_AUTHOR_DATE='2026-11-14T00:00:00Z' GIT_COMMITTER_NAME='ZX7 Studio' \
  GIT_COMMITTER_EMAIL='zx7-studio@users.noreply.github.com' GIT_COMMITTER_DATE='2026-11-14T00:00:00Z' \
  git -C "$stage/candidate" -c commit.gpgSign=false commit-tree "$tree" -p "$parent" \
  -m 'Source-native human GUI and model MCP editing parity from same A/V planner')
git -C "$stage/candidate" checkout --quiet --detach "$rev"
git -C "$stage/candidate" diff --quiet HEAD --
node --check "$stage/candidate/src/stores/timelineStore.js"
node --test "$stage/candidate/src/utils/zx7-loss-aware-split.test.mjs" \
  "$stage/candidate/src/utils/zx7-loss-aware-extract.test.mjs" \
  "$stage/candidate/src/utils/zx7-native-range-review.test.mjs"
printf 'Reproducible reviewed native GUI range source: %s\n' "$rev"
if [[ "$3" == "--inspect" ]]; then exit 0; fi
test -n "$expected" && test "$rev" = "$expected" || {
  echo "GUI range source revision is not exactly pinned; installation refused" >&2
  exit 1
}
mv -T --no-clobber -- "$stage/candidate" "$out"
printf 'Installed source-attested native GUI + MCP range editor: %s\n' "$rev"
