#!/usr/bin/env bash
# Produce a separate deterministic source-attested collaboration candidate.
# Stable installed editor remains unchanged until this variant is accepted.
set -euo pipefail
if [[ "$#" != 3 || ( "$3" != "--inspect" && "$3" != "--install" ) ]]; then
  echo "Usage: $0 PINNED_UPSTREAM_CHECKOUT DESTINATION --inspect|--install" >&2
  exit 2
fi
base_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
lock="$base_dir/../../studio_next/editor_runtime/source-lock.json"
desktop=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["desktop_revision"])' "$lock")
expected=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("collab_revision", ""))' "$lock")
output=$(realpath -m -- "$2")
test ! -e "$2" && test ! -L "$2" || { echo "Destination already exists" >&2; exit 2; }
stage=$(mktemp -d "$(dirname -- "$output")/.zx7-native-revision.XXXXXX")
trap 'rm -rf -- "$stage"' EXIT

bash "$base_dir/prepare-supported-source.sh" "$1" "$stage/desktop"
test "$(git -C "$stage/desktop" rev-parse HEAD)" = "$desktop"
git clone --quiet --no-local --no-checkout -- "$stage/desktop" "$stage/candidate"
git -C "$stage/candidate" checkout --quiet --detach "$desktop"
git -C "$stage/candidate" apply --unidiff-zero --index -- "$base_dir/native-live-revision.patch"
tree=$(git -C "$stage/candidate" write-tree)
revision=$(GIT_AUTHOR_NAME='ZX7 Studio' GIT_AUTHOR_EMAIL='zx7-studio@users.noreply.github.com' \
  GIT_AUTHOR_DATE='2026-11-12T00:00:00Z' GIT_COMMITTER_NAME='ZX7 Studio' \
  GIT_COMMITTER_EMAIL='zx7-studio@users.noreply.github.com' GIT_COMMITTER_DATE='2026-11-12T00:00:00Z' \
  git -C "$stage/candidate" -c commit.gpgSign=false commit-tree "$tree" -p "$desktop" \
  -m 'Source-guard synchronous ZX7 native revisions')
git -C "$stage/candidate" checkout --quiet --detach "$revision"
git -C "$stage/candidate" diff --quiet HEAD --
for f in electron/mcpServer.js src/services/mcpSnapshot.js src/services/mcpActions.js; do
  node --check "$stage/candidate/$f"
done
printf 'Reproducible ZX7 collaboration candidate: %s\n' "$revision"
if [[ "$3" == "--inspect" ]]; then
  exit 0
fi
# Installation and trusted Python admission require the exact approved SHA.
test -n "$expected" && test "$revision" = "$expected" || {
  echo "Candidate has not passed exact source-pin review; refusing install" >&2
  exit 1
}
mv -T --no-clobber -- "$stage/candidate" "$output"
test ! -e "$stage/candidate"
printf 'Installed pinned collaboration variant: %s\n' "$revision"
