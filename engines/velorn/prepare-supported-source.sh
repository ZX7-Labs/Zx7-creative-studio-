#!/usr/bin/env bash
# Materialize the reviewed desktop variant without modifying its upstream checkout.
set -euo pipefail

if [[ "$#" != 2 ]]; then
  echo "Usage: prepare-supported-source.sh UPSTREAM_CHECKOUT DESTINATION" >&2
  exit 2
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
lock="$script_dir/../../studio_next/editor_runtime/source-lock.json"
revisions=$(python3 -c '
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    lock = json.load(handle)
print(lock["upstream_revision"], lock["desktop_revision"])
' "$lock")
read -r upstream desktop <<< "$revisions"

source=$(realpath -- "$1")
target=$(realpath -m -- "$2")
test ! -e "$2" && test ! -L "$2" || { echo "Destination already exists" >&2; exit 2; }
test "$(git -C "$source" rev-parse --show-toplevel)" = "$source"
test "$(git -C "$source" rev-parse HEAD)" = "$upstream"
git -C "$source" diff --quiet HEAD --

stage=$(mktemp -d "$(dirname -- "$target")/.zx7-velorn.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT
candidate="$stage/source"
git clone --quiet --no-local --no-checkout -- "$source" "$candidate"
git -C "$candidate" checkout --quiet --detach "$upstream"
git -C "$candidate" apply --unidiff-zero --index -- "$script_dir/electron-file-path.patch"
tree=$(git -C "$candidate" write-tree)
revision=$(GIT_AUTHOR_NAME='ZX7 Studio' GIT_AUTHOR_EMAIL='zx7-studio@users.noreply.github.com' \
  GIT_AUTHOR_DATE='2026-11-10T00:00:00Z' GIT_COMMITTER_NAME='ZX7 Studio' \
  GIT_COMMITTER_EMAIL='zx7-studio@users.noreply.github.com' GIT_COMMITTER_DATE='2026-11-10T00:00:00Z' \
  git -C "$candidate" -c commit.gpgSign=false commit-tree "$tree" -p "$upstream" \
  -m 'Support native image sequence selection on current Electron')
test "$revision" = "$desktop"
git -C "$candidate" checkout --quiet --detach "$revision"
git -C "$candidate" diff --quiet HEAD --
mv -T --no-clobber -- "$candidate" "$target"
test ! -e "$candidate"
printf 'Prepared Velorn desktop source %s\n' "$revision"
