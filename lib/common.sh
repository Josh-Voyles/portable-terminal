# shellcheck shell=bash
# Shared installer functions. Requires Bash 3.2 or newer.

log() { printf '%s\n' "$*"; }
warn() { printf 'Warning: %s\n' "$*" >&2; }
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }
require_command() { have "$1" || die "Required command not found: $1"; }

validate_path() {
    case $1 in /*) ;; *) die "Expected an absolute path: $1" ;; esac
    case $1 in *$'\t'*|*$'\n'*) die 'Paths containing tabs or newlines are not supported.' ;; esac
}

require_checksum() {
    if ! have sha256sum && ! have shasum; then die 'Install sha256sum or shasum first.'; fi
}

checksum() {
    if have sha256sum; then sha256sum "$1"; else shasum -a 256 "$1"; fi | awk '{print $1}'
}

cleanup() {
    # This is only the exact directory created by mktemp, never a user path.
    if [ -n "${WORK:-}" ] && [ -d "$WORK" ]; then rm -rf -- "$WORK"; fi
}

backup_file() {
    local target=$1
    BACKUP_REF=-
    mkdir -p "$BACKUP_DIR/files"
    chmod 700 "$BACKUP_DIR" "$BACKUP_DIR/files"
    if [ -e "$target" ] || [ -L "$target" ]; then
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
        BACKUP_REF="files/$BACKUP_COUNT"
        # Preserve symlinks themselves, not just the files they point to.
        cp -pP "$target" "$BACKUP_DIR/$BACKUP_REF"
    fi
}

put_file() {
    local source=$1 target=$2 mode=${3:-600} temporary digest
    validate_path "$target"
    [ -f "$source" ] || die "Missing bundled file: $source"
    if [ -d "$target" ] || { [ -e "$target" ] && [ ! -f "$target" ]; }; then
        die "Refusing to replace a non-file: $target"
    fi
    if [ -f "$target" ] && cmp -s "$source" "$target"; then return; fi
    if [ "$DRY_RUN" -eq 1 ]; then log "Would install: $target (back up if present)"; return; fi
    mkdir -p "$(dirname -- "$target")"
    temporary=$(mktemp "$(dirname -- "$target")/.portable-terminal.XXXXXX")
    cat "$source" > "$temporary"
    chmod "$mode" "$temporary"
    digest=$(checksum "$temporary")
    backup_file "$target"
    # Record before replacing so an interrupted installation is recoverable too.
    printf '%s\t%s\t%s\n' "$BACKUP_REF" "$target" "$digest" >> "$BACKUP_DIR/manifest.tsv"
    mv -f "$temporary" "$target"
    log "Installed: $target"
}

managed_block() {
    local target=$1 body=$2 generated existing
    # An empty body removes only our block, without creating or deleting rc files.
    if [ -z "$body" ]; then
        [ -f "$target" ] || return 0
        grep -Fqx -e '# >>> portable-terminal >>>' -e '# <<< portable-terminal <<<' "$target" || return 0
    fi
    if [ "$DRY_RUN" -eq 1 ]; then log "Would update/remove the managed block in: $target"; return; fi
    generated="$WORK/managed-block"
    existing=/dev/null
    if [ -f "$target" ]; then existing=$target; fi
    # Reject broken/duplicate markers instead of swallowing unrelated user text.
    if ! awk '
        $0 == "# >>> portable-terminal >>>" {
            if (inside || starts++) bad = 1
            inside = 1; next
        }
        $0 == "# <<< portable-terminal <<<" {
            if (!inside) bad = 1
            inside = 0; next
        }
        !inside { print }
        END { if (inside || bad) exit 1 }
    ' "$existing" > "$generated"; then
        die "Malformed portable-terminal markers in $target; repair them before installing."
    fi
    if [ -n "$body" ]; then
        printf '%s\n%s\n%s\n' '# >>> portable-terminal >>>' "$body" '# <<< portable-terminal <<<' >> "$generated"
    fi
    put_file "$generated" "$target"
}

put_setting() {
    local schema=$1 key=$2 value=$3 previous
    if [ "$DRY_RUN" -eq 1 ]; then log "Would set: $schema $key = $value"; return; fi
    previous=$(gsettings get "$schema" "$key")
    if [ "$previous" = "$value" ]; then return; fi
    [ "$(gsettings writable "$schema" "$key")" = true ] || die "Desktop setting is not writable: $schema $key"
    mkdir -p "$BACKUP_DIR"
    chmod 700 "$BACKUP_DIR"
    printf '%s\t%s\t%s\t%s\n' "$schema" "$key" "$previous" "$value" >> "$BACKUP_DIR/settings.tsv"
    gsettings set "$schema" "$key" "$value"
}
