#!/usr/bin/env bash
# Show stable /dev/v4l/by-id paths and supported formats for attached cameras.
set -uo pipefail

shopt -s nullglob
links=(/dev/v4l/by-id/*)

if [[ ${#links[@]} -eq 0 ]]; then
  echo "No /dev/v4l/by-id entries found. Are the cameras connected by USB?" >&2
  exit 1
fi

echo "Stable device paths (/dev/v4l/by-id):"
for link in "${links[@]}"; do
  printf '  %s -> %s\n' "${link}" "$(readlink -f "${link}")"
done

if ! command -v v4l2-ctl >/dev/null 2>&1; then
  echo
  echo "Install v4l-utils for format details: sudo apt install v4l-utils" >&2
  exit 0
fi

echo
for link in "${links[@]}"; do
  device="$(readlink -f "${link}")"
  echo "== ${link} =="
  v4l2-ctl --list-formats-ext -d "${device}" 2>/dev/null | sed 's/^/  /'
done
