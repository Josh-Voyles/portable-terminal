#!/usr/bin/env bash
# Compatible with the Bash 3.2 shipped by macOS. Never source a user's dotfiles.
set -euo pipefail
umask 077

ROOT=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
# shellcheck source=lib/common.sh
source "$ROOT/lib/common.sh"
# shellcheck source=lib/packages.sh
source "$ROOT/lib/packages.sh"

usage() {
    cat <<'EOF'
Usage: bash install.sh [options]

Install Josh's Catppuccin Mocha shell setup on Linux or macOS.

  --dry-run          Print the plan; no writes, downloads, or package installs
  --config-only      Install configuration, but not tools or fonts
  --no-tools         Don't install command-line tools
  --no-fonts         Don't install the Nerd Font
  --no-terminals     Don't configure Kitty or install macOS terminal profiles
  --no-yazi          Leave Yazi's theme untouched
  --shell NAME       both (default), bash, zsh, or none
  --reinstall-tools  Replace tools with the pinned Linux builds; reinstall on Mac
  --ptyxis           Also select the Nerd Font in Ptyxis (Linux desktop only)
  --import-terminal Open the Apple Terminal profile for import (macOS only)
  -h, --help         Show this help

Existing files are backed up privately before changes. No sudo, shell switch,
Homebrew bootstrap, terminal-app install, or changes to terminal defaults.
EOF
}

DRY_RUN=0
TOOLS=1
FONTS=1
TERMINALS=1
YAZI=1
SHELLS=both
REINSTALL_TOOLS=0
PTYXIS=0
IMPORT_TERMINAL=0
while [ "$#" -gt 0 ]; do
    case $1 in
        --dry-run) DRY_RUN=1 ;;
        --config-only) TOOLS=0; FONTS=0 ;;
        --no-tools) TOOLS=0 ;;
        --no-fonts) FONTS=0 ;;
        --no-terminals) TERMINALS=0 ;;
        --no-yazi) YAZI=0 ;;
        --shell)
            [ "$#" -ge 2 ] || die '--shell needs a value'
            SHELLS=$2
            shift
            case $SHELLS in both|bash|zsh|none) ;; *) die "Unknown shell: $SHELLS" ;; esac
            ;;
        --reinstall-tools) REINSTALL_TOOLS=1 ;;
        --ptyxis) PTYXIS=1 ;;
        --import-terminal) IMPORT_TERMINAL=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown option: $1 (see --help)" ;;
    esac
    shift
done

OS=$(uname -s)
case $OS in Linux|Darwin) ;; *) die "Unsupported operating system: $OS" ;; esac
case $(uname -m) in
    x86_64|amd64) ARCH=x86_64 ;;
    aarch64|arm64) ARCH=aarch64 ;;
    *) die 'Supported architectures: x86_64 and arm64' ;;
esac

: "${HOME:?HOME must be set}"
CONFIG_HOME=${XDG_CONFIG_HOME:-$HOME/.config}
DATA_HOME=${XDG_DATA_HOME:-$HOME/.local/share}
STATE_HOME=${XDG_STATE_HOME:-$HOME/.local/state}
CACHE_HOME=${XDG_CACHE_HOME:-$HOME/.cache}
ZSH_HOME=${ZDOTDIR:-$HOME}
YAZI_HOME=${YAZI_CONFIG_HOME:-$CONFIG_HOME/yazi}
for directory in "$HOME" "$CONFIG_HOME" "$DATA_HOME" "$STATE_HOME" "$CACHE_HOME" "$ZSH_HOME" "$YAZI_HOME"; do
    validate_path "$directory"
done
DEST="$CONFIG_HOME/portable-terminal"
BIN_HOME="$HOME/.local/bin"
BACKUP_DIR="$STATE_HOME/portable-terminal/backups/$(date -u +%Y%m%dT%H%M%SZ)-$$"
BACKUP_COUNT=0
WORK=''
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [ "$IMPORT_TERMINAL" -eq 1 ]; then
    [ "$OS" = Darwin ] || die '--import-terminal is only available on macOS'
    [ "$TERMINALS" -eq 1 ] || die '--import-terminal cannot be combined with --no-terminals'
fi

# Preflight before changing configuration. A dry run needs no installer tools.
if [ "$DRY_RUN" -eq 0 ]; then
    require_checksum
    if [ "$TOOLS" -eq 1 ] || [ "$FONTS" -eq 1 ]; then
        require_command curl
        require_command tar
    fi
    if [ "$FONTS" -eq 1 ] && [ "$OS" = Linux ]; then require_command xz; fi
    if [ "$TOOLS" -eq 1 ]; then
        if [ "$OS" = Darwin ]; then
            find_brew
            [ -n "$BREW" ] || die 'Install Homebrew from https://brew.sh first, or use --config-only.'
        else
            require_command unzip
            if [ "$ARCH" = aarch64 ] && { [ "$REINSTALL_TOOLS" -eq 1 ] || ! have eza; } && ! getconf GNU_LIBC_VERSION >/dev/null 2>&1; then
                die 'The Linux arm64 eza build requires glibc. Install eza yourself and rerun without --reinstall-tools.'
            fi
        fi
    fi
    WORK=$(mktemp -d "${TMPDIR:-/tmp}/portable-terminal.XXXXXX")
fi

log "Platform: $OS / $ARCH; shells: $SHELLS"
if [ "$TOOLS" -eq 1 ]; then install_tools; fi
if [ "$FONTS" -eq 1 ]; then install_fonts; fi

# Private, managed copies: the checkout can be moved or deleted after installing.
put_file "$ROOT/config/starship.toml" "$DEST/starship.toml"
for name in common.sh bash.sh zsh.sh; do
    put_file "$ROOT/config/shell/$name" "$DEST/shell/$name"
done
put_file "$ROOT/bin/terminal-doctor" "$BIN_HOME/terminal-doctor" 755

if [ "$SHELLS" = both ] || [ "$SHELLS" = bash ]; then
    # Expand these variables when the user's shell starts, not during install.
    # shellcheck disable=SC2016
    bash_hook='if [ -n "${BASH_VERSION-}" ] && [ -r "${XDG_CONFIG_HOME:-$HOME/.config}/portable-terminal/shell/bash.sh" ]; then
    . "${XDG_CONFIG_HOME:-$HOME/.config}/portable-terminal/shell/bash.sh"
fi'
    managed_block "$HOME/.bashrc" "$bash_hook"
    # Don't create .bash_profile if doing so would mask .bash_login or .profile.
    login_file="$HOME/.bash_profile"
    for name in .bash_profile .bash_login .profile; do
        if [ -f "$HOME/$name" ]; then login_file="$HOME/$name"; break; fi
    done
    managed_block "$login_file" "$bash_hook"
fi
if [ "$SHELLS" = both ] || [ "$SHELLS" = zsh ]; then
    # shellcheck disable=SC2016
    managed_block "$ZSH_HOME/.zshrc" 'if [ -n "${ZSH_VERSION-}" ] && [ -r "${XDG_CONFIG_HOME:-$HOME/.config}/portable-terminal/shell/zsh.sh" ]; then
    . "${XDG_CONFIG_HOME:-$HOME/.config}/portable-terminal/shell/zsh.sh"
fi'
fi

if [ "$YAZI" -eq 1 ]; then
    put_file "$ROOT/config/yazi/theme.toml" "$YAZI_HOME/theme.toml"
fi

if [ "$TERMINALS" -eq 1 ]; then
    put_file "$ROOT/config/kitty/mocha.conf" "$CONFIG_HOME/kitty/portable-terminal/mocha.conf"
    put_file "$ROOT/config/kitty/kitty.conf" "$CONFIG_HOME/kitty/portable-terminal/kitty.conf"
    managed_block "$CONFIG_HOME/kitty/kitty.conf" 'include portable-terminal/kitty.conf'
    if [ "$OS" = Darwin ]; then
        put_file "$ROOT/profiles/portable-terminal.json" "$HOME/Library/Application Support/iTerm2/DynamicProfiles/portable-terminal.json"
        put_file "$ROOT/profiles/Portable-Mocha.terminal" "$DEST/profiles/Portable-Mocha.terminal"
        if [ "$IMPORT_TERMINAL" -eq 1 ]; then
            if [ "$DRY_RUN" -eq 1 ]; then
                log 'Would open the Apple Terminal profile for import.'
            else
                open -a Terminal "$DEST/profiles/Portable-Mocha.terminal"
            fi
        fi
    fi
fi
if [ "$PTYXIS" -eq 1 ]; then
    if [ "$OS" != Linux ] || ! have gsettings; then
        warn 'Ptyxis font configuration skipped: Linux and gsettings are required.'
    elif gsettings list-schemas | grep -qx org.gnome.Ptyxis; then
        put_setting org.gnome.Ptyxis use-system-font false
        put_setting org.gnome.Ptyxis font-name "'JetBrainsMono Nerd Font Mono 12'"
    else
        warn 'Ptyxis is not installed; no desktop settings changed.'
    fi
fi

if [ "$DRY_RUN" -eq 1 ]; then
    log 'Dry run complete. Nothing was changed or downloaded.'
else
    log 'Done. Open a new terminal tab to load the shell setup.'
    if [ -f "$BACKUP_DIR/manifest.tsv" ] || [ -f "$BACKUP_DIR/settings.tsv" ]; then
        log "Private backups: $BACKUP_DIR"
        log "Restore with: bash restore.sh '$BACKUP_DIR'"
    else
        log 'All managed files were already up to date.'
    fi
    log 'Run terminal-doctor in each terminal to check tools and icon rendering.'
fi
if [ "$TERMINALS" -eq 1 ]; then
    log 'Kitty: Ctrl+Shift+F5 reloads appearance; open a new tab for shell changes.'
    if [ "$OS" = Darwin ]; then
        log 'iTerm2: choose Profiles > Portable Terminal - Mocha (set as default if wanted).'
        log "Apple Terminal: import $DEST/profiles/Portable-Mocha.terminal in Settings > Profiles."
    fi
fi
log 'Other terminals: select JetBrainsMono Nerd Font Mono, size 12, in their preferences.'
