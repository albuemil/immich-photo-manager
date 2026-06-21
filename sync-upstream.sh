#!/usr/bin/env bash
set -e

echo "Fetching upstream (drolosoft/immich-photo-manager)..."
git fetch upstream

echo "Merging upstream/main..."
git merge upstream/main

echo "Pushing to origin (albuemil/immich-photo-manager)..."
git push origin main

echo "Done — repo is up to date with upstream."
