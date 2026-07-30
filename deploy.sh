#!/usr/bin/env bash
# Commit any local changes and push to GitHub (triggers Pages redeploy).
# Usage: ./deploy.sh ["commit message"]
set -euo pipefail
cd "$(dirname "$0")"

MSG="${1:-Update map}"

if [[ -z "$(git status --porcelain)" ]]; then
  echo "No changes to deploy."
  exit 0
fi

git add -A
git commit -m "$MSG"
git push origin main
echo "Pushed. GitHub Pages will redeploy in ~1 minute."
