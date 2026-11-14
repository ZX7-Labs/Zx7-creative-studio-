#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Independent opt-in source child: real loss-aware native extract/ripple.
# Never mutate pinned upstream, prior verified editor variants or owner media.
set -euo pipefail
if [[ "$#" != 3 || ( "$3" != "--inspect" && "$3" != "--install" ) ]]; then
  echo "Usage: $0 PINNED_UPSTREAM_CHECKOUT NEW_DESTINATION --inspect|--install" >&2
  exit 2
fi
root=$(cd -- "$(dirname -- "$0")" && pwd -P)
lock="$root/../../studio_next/editor_runtime/source-lock.json"
parent=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["loss_aware_editorial_revision"])' "$lock")
expected=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("loss_aware_extract_revision",""))' "$lock")
out=$(realpath -m -- "$2")
test ! -e "$2" && test ! -L "$2" || { echo "Destination already exists" >&2; exit 2; }
stage=$(mktemp -d "$(dirname -- "$out")/.zx7-native-range.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
bash "$root/prepare-native-loss-aware-editorial-candidate.sh" "$1" "$stage/parent" --install
test "$(git -C "$stage/parent" rev-parse HEAD)" = "$parent"
git clone --quiet --no-local --no-checkout -- "$stage/parent" "$stage/candidate"
git -C "$stage/candidate" checkout --quiet --detach "$parent"
git -C "$stage/candidate" apply --index -- "$root/native-loss-aware-extract.patch"
python3 - "$stage/candidate/src/services/mcpActions.js" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
source = p.read_text(encoding="utf-8")
old = ',"split_clip"])'
new = ',"split_clip","extract_range"])'
if source.count(old) != 1 or source.count('These eleven native editorial operations') != 1:
    raise SystemExit("Unreviewed native writer-fence source; cannot add range")
source = source.replace(old, new, 1).replace(
    'These eleven native editorial operations',
    'These twelve native editorial operations', 1)
p.write_text(source, encoding="utf-8")
PY
cp -- "$root/zx7-loss-aware-extract.mjs" "$stage/candidate/src/utils/zx7-loss-aware-extract.mjs"
cp -- "$root/zx7-loss-aware-extract.test.mjs" "$stage/candidate/src/utils/zx7-loss-aware-extract.test.mjs"
python3 - "$stage/candidate/electron/mcpServer.js" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1])
source=p.read_text(encoding="utf-8")
old=('Remove a timeline time range across unlocked tracks: splits clips at the range edges, '
     'deletes everything inside, and (by default) ripples later clips left to close the gap. '
     'The core cut-down/remove-section operation. Markers are not shifted. Defaults to previewOnly.')
new=('Source-preserving atomic range extract across chosen native tracks. One undo checkpoint, '
     'frame-snapped video/audio media windows and verified revision-fenced writer. '
     'Ripple is optional; unsupported effect/transition/marker and linked sound semantics '
     'refuse before mutation. Defaults to previewOnly. Not equivalent to the legacy GUI range editor.')
if source.count(old) != 1:
    raise SystemExit("Native extract_range MCP source descriptor was not reviewed")
p.write_text(source.replace(old,new),encoding="utf-8")
PY
git -C "$stage/candidate" add -- electron/mcpServer.js src/services/mcpActions.js \
  src/utils/zx7-loss-aware-extract.mjs src/utils/zx7-loss-aware-extract.test.mjs
tree=$(git -C "$stage/candidate" write-tree)
rev=$(GIT_AUTHOR_NAME='ZX7 Studio' GIT_AUTHOR_EMAIL='zx7-studio@users.noreply.github.com' \
  GIT_AUTHOR_DATE='2026-11-14T00:00:00Z' GIT_COMMITTER_NAME='ZX7 Studio' \
  GIT_COMMITTER_EMAIL='zx7-studio@users.noreply.github.com' GIT_COMMITTER_DATE='2026-11-14T00:00:00Z' \
  git -C "$stage/candidate" -c commit.gpgSign=false commit-tree "$tree" -p "$parent" \
  -m 'Source-native atomic loss-aware extract and ripple editorial editing')
git -C "$stage/candidate" checkout --quiet --detach "$rev"
git -C "$stage/candidate" diff --quiet HEAD --
node --check "$stage/candidate/src/services/mcpActions.js"
node --check "$stage/candidate/src/utils/zx7-loss-aware-extract.mjs"
node --test "$stage/candidate/src/utils/zx7-loss-aware-split.test.mjs" \
  "$stage/candidate/src/utils/zx7-loss-aware-extract.test.mjs"
printf 'Reproducible ZX7 atomic loss-aware range source: %s\n' "$rev"
if [[ "$3" == "--inspect" ]]; then exit 0; fi
test -n "$expected" && test "$rev" = "$expected" || {
  echo "Loss-aware extract source revision is not pinned; refusing installation" >&2
  exit 1
}
mv -T --no-clobber -- "$stage/candidate" "$out"
test ! -e "$stage/candidate"
printf 'Installed source-attested atomic loss-aware native editor: %s\n' "$rev"
