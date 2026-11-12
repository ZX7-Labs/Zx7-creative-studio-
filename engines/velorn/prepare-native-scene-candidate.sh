#!/usr/bin/env bash
# Reproducible, opt-in scene revision overlay on already vetted title-CAS source.
# Never edits the stable installed editor, media workspace, or original submodule.
set -euo pipefail
if [[ "$#" != 3 || ( "$3" != "--inspect" && "$3" != "--install" ) ]]; then
  echo "Usage: $0 PINNED_UPSTREAM_CHECKOUT DESTINATION --inspect|--install" >&2
  exit 2
fi
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
lock="$root/../../studio_next/editor_runtime/source-lock.json"
parent=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["collab_revision"])' "$lock")
expected=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("collab_scene_revision", ""))' "$lock")
out=$(realpath -m -- "$2")
test ! -e "$2" && test ! -L "$2" || { echo "Destination already exists" >&2; exit 2; }
stage=$(mktemp -d "$(dirname -- "$out")/.zx7-native-scene.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT

bash "$root/prepare-native-revision-candidate.sh" "$1" "$stage/title" --install
test "$(git -C "$stage/title" rev-parse HEAD)" = "$parent"
git clone --quiet --no-local --no-checkout -- "$stage/title" "$stage/scene"
git -C "$stage/scene" checkout --quiet --detach "$parent"
git -C "$stage/scene" apply --index -- "$root/native-scene-revision.patch"
tree=$(git -C "$stage/scene" write-tree)
rev=$(GIT_AUTHOR_NAME='ZX7 Studio' GIT_AUTHOR_EMAIL='zx7-studio@users.noreply.github.com' \
  GIT_AUTHOR_DATE='2026-11-12T00:00:00Z' GIT_COMMITTER_NAME='ZX7 Studio' \
  GIT_COMMITTER_EMAIL='zx7-studio@users.noreply.github.com' GIT_COMMITTER_DATE='2026-11-12T00:00:00Z' \
  git -C "$stage/scene" -c commit.gpgSign=false commit-tree "$tree" -p "$parent" \
  -m 'Guard source-native shape and keyframe edits against GUI races')
git -C "$stage/scene" checkout --quiet --detach "$rev"
git -C "$stage/scene" diff --quiet HEAD --
node --check "$stage/scene/src/services/mcpActions.js"
node --check "$stage/scene/electron/mcpServer.js"
printf 'Reproducible ZX7 scene collaboration revision: %s\n' "$rev"
if [[ "$3" == "--inspect" ]]; then
  exit 0
fi
test -n "$expected" && test "$rev" = "$expected" || {
  echo "Scene collaboration source not reviewed/pinned; refusing install" >&2
  exit 1
}
mv -T --no-clobber -- "$stage/scene" "$out"
test ! -e "$stage/scene"
printf 'Installed exact source-attested scene variant: %s\n' "$rev"
