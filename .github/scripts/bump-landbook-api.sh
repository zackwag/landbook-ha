#!/usr/bin/env bash
# Opens a PR bumping the exact landbook-api pin in manifest.json when PyPI
# has a newer release. Home Assistant never upgrades a requirement the
# installed version already satisfies, so this pin is the only way a
# landbook-api release reaches users.
#
# DRY_RUN=1 rewrites the manifest and stops before any git/gh calls.
set -euo pipefail

manifest=custom_components/landbook/manifest.json
pin_prefix="landbook-api=="

current=$(jq -r --arg p "$pin_prefix" \
  '.requirements[] | select(startswith($p)) | ltrimstr($p)' "$manifest")
if [ -z "$current" ]; then
  echo "::error::No exact ${pin_prefix}X.Y.Z requirement in $manifest" >&2
  exit 1
fi

latest=${LANDBOOK_API_VERSION:-$(curl -fsSL https://pypi.org/pypi/landbook-api/json | jq -r .info.version)}
echo "pinned: $current, latest on PyPI: $latest"
if [ "$current" = "$latest" ]; then
  exit 0
fi

tmp=$(mktemp)
jq --arg p "$pin_prefix" --arg v "$latest" \
  '.requirements |= map(if startswith($p) then $p + $v else . end)' \
  "$manifest" >"$tmp"
mv "$tmp" "$manifest"

if [ "${DRY_RUN:-0}" = 1 ]; then
  git --no-pager diff -- "$manifest"
  exit 0
fi

branch="deps/landbook-api-$latest"
if git ls-remote --exit-code --heads origin "$branch" >/dev/null; then
  echo "$branch already exists; nothing to do"
  exit 0
fi

title="fix(deps): bump landbook-api to $latest"
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git switch -c "$branch"
git commit -am "$title"
git push origin "$branch"

gh pr create --head "$branch" --title "$title" --body "$(cat <<EOF
Bumps the \`landbook-api\` pin from \`$current\` to \`$latest\`.

Release notes: [v$latest](https://github.com/zackwag/landbook-api/releases/tag/v$latest)

Before merging, check the release notes for anything this integration should adopt or that changes behavior, and push those changes to this branch. Retitle to \`feat(deps):\` if it adds user-facing functionality.
EOF
)"

# Older bump PRs are superseded by this one.
gh pr list --state open --json number,headRefName \
  --jq ".[] | select(.headRefName | startswith(\"deps/landbook-api-\")) | select(.headRefName != \"$branch\") | .number" |
  while read -r number; do
    gh pr close "$number" --delete-branch --comment "Superseded by the bump to $latest."
  done
