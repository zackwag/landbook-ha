#!/usr/bin/env bash
set -euo pipefail

# Usage: ./prep_release.sh "commit message"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"commit message\""
  exit 1
fi

MESSAGE="$1"

# --- Read current version from manifest.json ---
CURRENT=$(grep '"version"' custom_components/landbook/manifest.json | grep -o '[0-9][0-9.]*')
MAJOR=$(echo "$CURRENT" | cut -d. -f1)
MINOR=$(echo "$CURRENT" | cut -d. -f2)
PATCH=$(echo "$CURRENT" | cut -d. -f3)

echo "Current version: $CURRENT"
echo ""
echo "Bump type:"
echo "  1) patch  → $MAJOR.$MINOR.$((PATCH + 1))"
echo "  2) minor  → $MAJOR.$((MINOR + 1)).0"
echo "  3) major  → $((MAJOR + 1)).0.0"
echo ""
read -rp "Choose [1]: " bump_choice
bump_choice="${bump_choice:-1}"

case "$bump_choice" in
  1) NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))" ;;
  2) NEW_VERSION="$MAJOR.$((MINOR + 1)).0" ;;
  3) NEW_VERSION="$((MAJOR + 1)).0.0" ;;
  *)
    echo "Invalid choice."
    exit 1
    ;;
esac

TAG="v${NEW_VERSION}"

echo ""
echo "Preparing release:"
echo "  Message : $MESSAGE"
echo "  Version : $CURRENT → $NEW_VERSION ($TAG)"
echo ""
read -rp "Proceed? [Y/n] " confirm
confirm="${confirm:-Y}"
[[ "$confirm" =~ ^[Yy]$ ]] || exit 0

# --- Update version in manifest.json ---
sed -i '' "s/\"version\": \"${CURRENT}\"/\"version\": \"${NEW_VERSION}\"/" \
  custom_components/landbook/manifest.json

# --- Update version in .bumpversion.cfg ---
sed -i '' "s/^current_version = .*/current_version = ${NEW_VERSION}/" \
  .bumpversion.cfg

echo "Updated manifest.json and .bumpversion.cfg to $NEW_VERSION"

# --- Commit, tag, push ---
git add custom_components/landbook/manifest.json .bumpversion.cfg

# Include any other changes the user may have staged
git add -u

git commit -m "$MESSAGE"
git tag "$TAG"

echo ""
echo "Pushing to origin/main..."
git push origin main
git push origin "$TAG"

echo ""
echo "Done. Release $TAG is live."
