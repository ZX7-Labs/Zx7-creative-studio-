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
# An exact one-line native renderer CAS extension; refuse unexpected source.
python3 - "$stage/candidate/src/services/mcpActions.js" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
source = p.read_text(encoding="utf-8")
old = 'const zx7FencedEditorialActions = new Set(["move_clips","trim_clips","delete_clips","add_asset_to_timeline","add_assets_to_timeline","set_clip_audio","set_clip_speed","update_track","add_transition","set_clip_style"])'
new = old[:-2] + ',"split_clip"])'
if source.count(old) != 1 or 'These ten native editorial operations' not in source:
    raise SystemExit("Unreviewed native CAS source; refusing loss-aware install")
source = source.replace(old, new)
source = source.replace('These ten native editorial operations', 'These eleven native editorial operations', 1)
p.write_text(source, encoding="utf-8")
PY
cp -- "$root/zx7-loss-aware-split.mjs" "$stage/candidate/src/utils/zx7-loss-aware-split.mjs"
cp -- "$root/zx7-loss-aware-split.test.mjs" "$stage/candidate/src/utils/zx7-loss-aware-split.test.mjs"
# The native MCP discovery contract must describe the actual child, not
# upstream's destructive GUI razor behavior. Refuse any unknown descriptor.
python3 - "$stage/candidate/electron/mcpServer.js" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
source = p.read_text(encoding="utf-8")
old = 'Effects and keyframes stay on the left piece, matching the in-app razor. Defaults to previewOnly.'
new = ('The loss-aware native MCP razor retains supported animated video/audio source '
       'state on both sides, refuses unsupported effects and transitions before mutation, '
       'and does not change the separate GUI razor. Defaults to previewOnly.')
if source.count(old) != 1:
    raise SystemExit("Unreviewed native split_clip descriptor; refusing child build")
p.write_text(source.replace(old, new), encoding="utf-8")
PY
git -C "$stage/candidate" add -- electron/mcpServer.js src/services/mcpActions.js src/utils/zx7-loss-aware-split.mjs src/utils/zx7-loss-aware-split.test.mjs
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
