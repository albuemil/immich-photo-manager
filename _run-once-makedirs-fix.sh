#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

git add -A
git commit -m "fix: create .mcpb-cache dir on save_config if it doesn't exist

_find_cache_dir now accepts the env var path even when the directory
hasn't been created yet. save_config calls os.makedirs(exist_ok=True)
so credentials persist on first use without manual directory creation.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

git push
bash build-plugin.sh

echo "Done! Reinstall the plugin or restart Cowork."
rm -- "$0"
