#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<USAGE
Usage: move_to_trash.sh <paths...>
USAGE
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

existing_paths=()
for path in "$@"; do
  if [[ -e "$path" ]]; then
    existing_paths+=("$path")
  fi
done

if [[ ${#existing_paths[@]} -eq 0 ]]; then
  exit 0
fi

if command -v trash >/dev/null 2>&1; then
  trash "${existing_paths[@]}"
  exit 0
fi

if command -v osascript >/dev/null 2>&1; then
  for path in "${existing_paths[@]}"; do
    if [[ -e "$path" ]]; then
      /usr/bin/osascript -e 'tell application "Finder" to delete POSIX file '"'"$path"'"''
    fi
  done
  exit 0
fi

echo "No trash tool available. Install 'trash' (brew install trash) or move items to Trash manually." >&2
exit 1
