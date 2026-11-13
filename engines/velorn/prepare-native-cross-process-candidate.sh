#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
# Ubuntu-only opt-in project source; never alter pinned upstream/stable editor.
set -euo pipefail
if [[ "$#" != 3 || ( "$3" != "--inspect" && "$3" != "--install" ) ]]; then
  echo "Usage: $0 PINNED_UPSTREAM_CHECKOUT DESTINATION --inspect|--install" >&2
  exit 2
fi
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
lock="$root/../../studio_next/editor_runtime/source-lock.json"
parent=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["collab_save_order_revision"])' "$lock")
expected=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("collab_cross_process_revision",""))' "$lock")
out=$(realpath -m -- "$2")
test ! -e "$2" && test ! -L "$2" || { echo "Destination already exists" >&2; exit 2; }
stage=$(mktemp -d "$(dirname -- "$out")/.zx7-native-cross-process.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
bash "$root/prepare-native-save-order-candidate.sh" "$1" "$stage/parent" --install
test "$(git -C "$stage/parent" rev-parse HEAD)" = "$parent"
git clone --quiet --no-local --no-checkout -- "$stage/parent" "$stage/candidate"
git -C "$stage/candidate" checkout --quiet --detach "$parent"
git -C "$stage/candidate" apply --index -- "$root/native-cross-process-save.patch"
cp -- "$root/nativeProjectCAS.cjs" "$stage/candidate/electron/nativeProjectCAS.cjs"
cp -- "$root/nativeProjectCAS.test.cjs" "$stage/candidate/electron/nativeProjectCAS.test.cjs"
git -C "$stage/candidate" add -- electron/nativeProjectCAS.cjs electron/nativeProjectCAS.test.cjs
tree=$(git -C "$stage/candidate" write-tree)
rev=$(GIT_AUTHOR_NAME='ZX7 Studio' GIT_AUTHOR_EMAIL='zx7-studio@users.noreply.github.com' \
  GIT_AUTHOR_DATE='2026-11-14T00:00:00Z' GIT_COMMITTER_NAME='ZX7 Studio' \
  GIT_COMMITTER_EMAIL='zx7-studio@users.noreply.github.com' GIT_COMMITTER_DATE='2026-11-14T00:00:00Z' \
  git -C "$stage/candidate" -c commit.gpgSign=false commit-tree "$tree" -p "$parent" \
  -m 'Isolate source-native cross-process project save CAS on Linux')
git -C "$stage/candidate" checkout --quiet --detach "$rev"
git -C "$stage/candidate" diff --quiet HEAD --
node --check "$stage/candidate/electron/main.js"
node --check "$stage/candidate/src/services/fileSystem.js"
node --check "$stage/candidate/electron/nativeProjectCAS.cjs"
node --test "$stage/candidate/electron/nativeProjectCAS.test.cjs"
printf 'Reproducible ZX7 source-native cross-process CAS revision: %s\n' "$rev"
if [[ "$3" == "--inspect" ]]; then exit 0; fi
test -n "$expected" && test "$rev" = "$expected" || {
  echo "Source identity not reviewed/pinned; refusing install" >&2
  exit 1
}
mv -T --no-clobber -- "$stage/candidate" "$out"
test ! -e "$stage/candidate"
printf 'Installed exact source-native cross-process project writer: %s\n' "$rev"
