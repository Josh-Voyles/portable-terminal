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

Install Josh's Catppuccin Mocha Zsh setup on Linux or macOS.
Zsh must already be on PATH. This installer never installs or upgrades it.

  --dry-run          Print the plan; no writes, downloads, or package installs
  --config-only      Install configuration and highlighting, not tools or fonts
  --no-tools         Don't install command-line tools
  --no-fonts         Don't install the Nerd Font
  --no-terminals     Don't configure Kitty or install macOS terminal profiles
  --no-yazi          Leave Yazi's theme untouched
  --make-default-shell  Change your login shell to Zsh without the consent prompt
  --keep-default-shell  Leave your account's login shell unchanged
  --reinstall-tools  Replace tools with the pinned Linux builds; reinstall on Mac
  --ptyxis           Also select the Nerd Font in Ptyxis (Linux desktop only)
  --import-terminal Open the Apple Terminal profile for import (macOS only)
  -h, --help         Show this help

Existing files are backed up privately before changes. If Zsh isn't your login
shell, an interactive install asks whether to change it (default: no).
No sudo, Homebrew bootstrap, terminal-app install, or terminal-profile default
changes. chsh may request your account password or be blocked by host policy.
EOF
}

# Read the account record, not the possibly stale/inherited $SHELL variable.
login_shell() {
    case $OS in
        Linux)
            have getent || return 1
            getent passwd "$(id -u)" | awk -F: 'NR == 1 { print $7 }'
            ;;
        Darwin)
            have dscacheutil || return 1
            dscacheutil -q user -a uid "$(id -u)" |
                awk '$1 == "shell:" { sub(/^[[:space:]]*shell:[[:space:]]*/, ""); print }'
            ;;
    esac
}

is_zsh() {
    case ${1##*/} in
        zsh) [ -x "$1" ] ;;
        *) [ -n "$1" ] && [ "$1" -ef "$ZSH" ] ;;
    esac
}

DRY_RUN=0
TOOLS=1
FONTS=1
TERMINALS=1
YAZI=1
SHELL_CHANGE=ask
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
        --make-default-shell|--keep-default-shell)
            [ "$SHELL_CHANGE" = ask ] || die 'Choose only one default-shell option.'
            case $1 in
                --make-default-shell) SHELL_CHANGE=yes ;;
                --keep-default-shell) SHELL_CHANGE=no ;;
            esac
            ;;
        --reinstall-tools) REINSTALL_TOOLS=1 ;;
        --ptyxis) PTYXIS=1 ;;
        --import-terminal) IMPORT_TERMINAL=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "Unknown option: $1 (see --help)" ;;
    esac
    shift
done

# Check before even creating temporary/cache/backup files, including in dry runs.
ZSH=$(type -P zsh) || die 'Zsh must already be installed and on PATH. Ask your administrator to provide it, then rerun.'
case $ZSH in
    /*) ;;
    *) ZSH="$(CDPATH='' cd -- "$(dirname -- "$ZSH")" && pwd -P)/$(basename -- "$ZSH")" ;;
esac
validate_path "$ZSH"

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

CURRENT_SHELL=$(login_shell) || CURRENT_SHELL=''
MAKE_DEFAULT=0
if is_zsh "$CURRENT_SHELL"; then
    log "Zsh is already your login shell: $CURRENT_SHELL"
elif [ "$SHELL_CHANGE" != no ]; then
    if [ "$SHELL_CHANGE" = ask ] && [ "$DRY_RUN" -eq 1 ]; then
        log 'Would ask whether to make Zsh your login shell (default: no).'
    else
        [ -n "$CURRENT_SHELL" ] || die 'Cannot read your account login shell. Use --keep-default-shell to install configuration without changing it.'
        validate_path "$CURRENT_SHELL"
        if [ "$SHELL_CHANGE" = ask ]; then
            [ -t 0 ] || die 'No interactive terminal. Choose --make-default-shell or --keep-default-shell.'
            printf 'Make Zsh your default login shell? [y/N] '
            answer=''
            IFS= read -r answer || answer=''
            case $answer in y|Y|yes|YES) SHELL_CHANGE=yes ;; *) SHELL_CHANGE=no ;; esac
        fi
        if [ "$SHELL_CHANGE" = yes ]; then
            MAKE_DEFAULT=1
            if [ "$DRY_RUN" -eq 0 ]; then require_command chsh; fi
        fi
    fi
fi

# Preflight before changing configuration. Highlighting is included even in
# --config-only; its verified archive is reused from the cache on later runs.
if [ "$DRY_RUN" -eq 0 ]; then
    require_checksum
    require_command curl
    require_command tar
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

log "Platform: $OS / $ARCH; shell: $ZSH"
install_highlighting
if [ "$TOOLS" -eq 1 ]; then install_tools; fi
if [ "$FONTS" -eq 1 ]; then install_fonts; fi

# Private, managed copies: the checkout can be moved or deleted after installing.
put_file "$ROOT/config/starship.toml" "$DEST/starship.toml"
put_file "$ROOT/config/shell/zsh.zsh" "$DEST/shell/zsh.zsh"
put_file "$ROOT/bin/terminal-doctor" "$BIN_HOME/terminal-doctor" 755

# Remove old project hooks only. Never source, delete, or translate Bash dotfiles.
for name in .bashrc .bash_profile .bash_login .profile; do
    managed_block "$HOME/$name" ''
done
# Expand these variables when Zsh starts, not during installation.
# shellcheck disable=SC2016
managed_block "$ZSH_HOME/.zshrc" 'if [ -n "${ZSH_VERSION-}" ] && [ -r "${XDG_CONFIG_HOME:-$HOME/.config}/portable-terminal/shell/zsh.zsh" ]; then
    . "${XDG_CONFIG_HOME:-$HOME/.config}/portable-terminal/shell/zsh.zsh"
fi'

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

# Change the account only after successful configuration. Native chsh owns
# authentication and host policy; we never invoke sudo or edit /etc/shells.
if [ "$MAKE_DEFAULT" -eq 1 ]; then
    if [ "$DRY_RUN" -eq 1 ]; then
        log "Would run: chsh -s $ZSH"
    else
        mkdir -p "$BACKUP_DIR"
        chmod 700 "$BACKUP_DIR"
        printf '%s\n' "$CURRENT_SHELL" > "$BACKUP_DIR/previous-shell"
        printf 'Previous login shell: %s\nTo switch back manually: chsh -s %q\n' "$CURRENT_SHELL" "$CURRENT_SHELL"
        if ! chsh -s "$ZSH" || ! is_zsh "$(login_shell)"; then
            warn 'Could not verify a successful login-shell change. Installed configuration was kept.'
            log "Private backups: $BACKUP_DIR"
            log "Restore files with: bash restore.sh '$BACKUP_DIR'"
            die 'Check chsh permissions and /etc/shells, or run Zsh directly. No sudo was attempted.'
        fi
        log 'Login shell changed to Zsh. Log out and back in for new login sessions.'
    fi
fi

if [ "$DRY_RUN" -eq 1 ]; then
    log 'Dry run complete. Nothing was changed or downloaded.'
else
    log 'Done. Start a fresh Zsh session to load the setup (run: zsh -l).'
    if [ -f "$BACKUP_DIR/manifest.tsv" ] || [ -f "$BACKUP_DIR/settings.tsv" ] || [ -f "$BACKUP_DIR/previous-shell" ]; then
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
