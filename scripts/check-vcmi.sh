#!/usr/bin/env bash
set -euo pipefail
printf 'VCMI package: '
dpkg-query -W -f='${Version}\n' vcmi
printf '\nAI modules:\n'
dpkg-query -L vcmi | while IFS= read -r path; do
  case "$path" in */AI/*.so) printf '%s\n' "$path" ;; esac
done
vcmi_data="${XDG_DATA_HOME:-$HOME/.local/share}/vcmi"
printf '\nGame data: %s\n' "$vcmi_data"
for dir in Data Maps Mp3 Saves; do
  if [[ -d "$vcmi_data/$dir" ]]; then
    printf 'OK %s\n' "$dir"
  else
    printf 'MISSING %s\n' "$dir"
  fi
done
printf '\nSaves:\n'
if [[ -d "$vcmi_data/Saves" ]]; then
  find "$vcmi_data/Saves" -maxdepth 1 -type f -printf '%f\n'
fi
