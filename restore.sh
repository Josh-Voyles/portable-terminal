#!/usr/bin/env bash
# Restore one installation's recorded changes, without discarding later edits.
set -euo pipefail
umask 077
ROOT=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
# shellcheck source=lib/common.sh
source "$ROOT/lib/common.sh"

DRY_RUN=0
FORCE=0
DIRECTORY=''
while [ "$#" -gt 0 ]; do
    case $1 in
        --dry-run) DRY_RUN=1 ;;
        --force) FORCE=1 ;;
        -h|--help)
            log 'Usage: bash restore.sh [--dry-run] [--force] BACKUP_DIRECTORY'
            log 'Later edits are skipped unless --force is explicitly supplied.'
            exit 0
            ;;
        --*) die "Unknown option: $1" ;;
        *) [ -z "$DIRECTORY" ] || die 'Supply only one backup directory.'; DIRECTORY=$1 ;;
    esac
    shift
done
[ -n "$DIRECTORY" ] || die 'Supply the private backup directory printed by install.sh.'
[ -d "$DIRECTORY" ] || die "Backup directory not found: $DIRECTORY"
DIRECTORY=$(CDPATH='' cd -- "$DIRECTORY" && pwd -P)
if [ ! -f "$DIRECTORY/manifest.tsv" ] && [ ! -f "$DIRECTORY/settings.tsv" ]; then
    die 'No portable-terminal manifest found in that directory.'
fi
require_checksum
skipped=0

if [ -f "$DIRECTORY/manifest.tsv" ]; then
    while IFS=$'\t' read -r original target expected extra; do
        [ -z "${extra:-}" ] || die 'Invalid backup manifest.'
        validate_path "$target"
        case $original in
            -) ;;
            files/*)
                case ${original#files/} in ''|*[!0-9]*) die 'Invalid backup reference.' ;; esac
                [ -e "$DIRECTORY/$original" ] || [ -L "$DIRECTORY/$original" ] || die "Missing backup: $original"
                ;;
            *) die 'Invalid backup reference.' ;;
        esac
        [ "${#expected}" -eq 64 ] || die 'Invalid manifest checksum.'
        case $expected in *[!0-9a-f]*) die 'Invalid manifest checksum.' ;; esac
        if [ -d "$target" ] || { [ -e "$target" ] && [ ! -f "$target" ]; }; then
            warn "Skipping non-file: $target"
            skipped=$((skipped + 1))
            continue
        fi
        if [ "$FORCE" -eq 0 ]; then
            if [ -L "$target" ] || [ ! -f "$target" ] || [ "$(checksum "$target")" != "$expected" ]; then
                warn "Skipping changed file: $target (use --force only if you want to discard those changes)"
                skipped=$((skipped + 1))
                continue
            fi
        fi
        if [ "$DRY_RUN" -eq 1 ]; then log "Would restore: $target"; continue; fi
        if [ "$original" = - ]; then
            rm -f -- "$target"
        else
            mkdir -p "$(dirname -- "$target")"
            temporary=$(mktemp "$(dirname -- "$target")/.portable-restore.XXXXXX")
            rm -f -- "$temporary"
            cp -pP "$DIRECTORY/$original" "$temporary"
            mv -f "$temporary" "$target"
        fi
        log "Restored: $target"
    done < "$DIRECTORY/manifest.tsv"
fi

if [ -f "$DIRECTORY/settings.tsv" ]; then
    require_command gsettings
    while IFS=$'\t' read -r schema key previous installed extra; do
        [ -z "${extra:-}" ] || die 'Invalid desktop settings manifest.'
        if [ "$FORCE" -eq 0 ] && [ "$(gsettings get "$schema" "$key")" != "$installed" ]; then
            warn "Skipping changed desktop setting: $schema $key"
            skipped=$((skipped + 1))
            continue
        fi
        if [ "$DRY_RUN" -eq 1 ]; then
            log "Would restore: $schema $key"
        else
            gsettings set "$schema" "$key" "$previous"
            log "Restored: $schema $key"
        fi
    done < "$DIRECTORY/settings.tsv"
fi

if [ "$DRY_RUN" -eq 0 ] && have fc-cache; then fc-cache -f; fi
log 'Restore finished. Backups and download caches were retained.'
log 'Homebrew packages and profiles already imported into Apple Terminal are not removed.'
if [ "$skipped" -gt 0 ]; then
    warn "$skipped changed or non-file target(s) were left alone."
    exit 2
fi
