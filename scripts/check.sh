#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$ROOT"
command -v zsh >/dev/null 2>&1 || { printf '%s\n' 'Zsh is required for these checks.' >&2; exit 1; }
zsh -n config/shell/zsh.zsh

if command -v shellcheck >/dev/null 2>&1; then
    shellcheck -x install.sh restore.sh scripts/check.sh lib/common.sh lib/packages.sh \
        bin/terminal-doctor
else
    printf '%s\n' 'ShellCheck not installed; skipping lint.'
fi
python3 -m unittest discover -s tests -v
