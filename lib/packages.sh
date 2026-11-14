# shellcheck shell=bash disable=SC2153
# ARCH is the global platform; arch is one row's architecture in packages.lock.
# Downloads are pinned and checked before extraction. No fetched shell scripts.

find_brew() {
    BREW=''
    if have brew; then BREW=$(command -v brew); return; fi
    local candidate
    for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
        if [ -x "$candidate" ]; then BREW=$candidate; return; fi
    done
}

fetch_asset() {
    local expected=$1 url=$2 cache temporary
    cache="$CACHE_HOME/portable-terminal/$expected-${url##*/}"
    if [ -f "$cache" ]; then
        [ "$(checksum "$cache")" = "$expected" ] || die "Cached download has the wrong SHA256: $cache"
    else
        mkdir -p "$(dirname -- "$cache")"
        temporary="$WORK/download"
        log "Downloading: $url"
        curl --fail --location --silent --show-error --retry 3 --connect-timeout 15 --max-time 300 \
            --proto '=https' --tlsv1.2 --output "$temporary" "$url"
        [ "$(checksum "$temporary")" = "$expected" ] || die "SHA256 verification failed: $url"
        mv "$temporary" "$cache"
    fi
    DOWNLOADED_ASSET=$cache
}

install_linux_tool() {
    local name=$1 expected=$2 url=$3 binaries=$4 binary stage source count
    local needed=$REINSTALL_TOOLS
    for binary in $binaries; do
        if ! have "$binary"; then needed=1; fi
    done
    if [ "$needed" -eq 0 ]; then log "Keeping existing: $name"; return; fi
    if [ "$DRY_RUN" -eq 1 ]; then
        log "Would install $name ($ARCH) in $BIN_HOME; SHA256 $expected"
        return
    fi
    fetch_asset "$expected" "$url"
    stage="$WORK/$name"
    mkdir -p "$stage"
    case $url in
        *.tar.gz) tar -xzf "$DOWNLOADED_ASSET" -C "$stage" ;;
        *.zip) unzip -q "$DOWNLOADED_ASSET" -d "$stage" ;;
        *) die "Unknown archive format: $url" ;;
    esac
    for binary in $binaries; do
        count=$(find "$stage" -type f -name "$binary" | wc -l | tr -d ' ')
        [ "$count" = 1 ] || die "Expected one $binary executable in $url, found $count"
        source=$(find "$stage" -type f -name "$binary")
        put_file "$source" "$BIN_HOME/$binary" 755
    done
}

install_tools() {
    local name arch expected url binaries formula binary action
    if [ "$OS" = Darwin ]; then
        find_brew
        # Check command availability, not just Homebrew's inventory; leave other
        # package managers' working installations alone unless explicitly asked.
        for formula in starship eza fzf bat fd ripgrep yazi; do
            binary=$formula
            if [ "$formula" = ripgrep ]; then binary=rg; fi
            if [ "$REINSTALL_TOOLS" -eq 0 ] && have "$binary"; then
                if [ "$formula" != yazi ] || have ya; then log "Keeping existing: $formula"; continue; fi
            fi
            if [ "$DRY_RUN" -eq 1 ]; then log "Would install with Homebrew: $formula"; continue; fi
            action=install
            if [ "$REINSTALL_TOOLS" -eq 1 ] && "$BREW" list --formula --versions "$formula" >/dev/null 2>&1; then action=reinstall; fi
            HOMEBREW_NO_AUTO_UPDATE=1 HOMEBREW_NO_INSTALL_CLEANUP=1 HOMEBREW_NO_INSTALL_UPGRADE=1 \
                "$BREW" "$action" --formula "$formula"
        done
    else
        while IFS='|' read -r name arch expected url binaries; do
            case $name in ''|'#'*) continue ;; esac
            [ "$arch" = "$ARCH" ] || continue
            install_linux_tool "$name" "$expected" "$url" "$binaries"
        done < "$ROOT/packages.lock"
    fi
}

install_fonts() {
    local expected url font_home stage face
    expected=04d5e8f903693f9dd13e16f867e994834e681eb3c72c0d337a770dcda09010cf
    url=https://github.com/ryanoasis/nerd-fonts/releases/download/v3.5.1/JetBrainsMono.tar.xz
    if [ "$OS" = Darwin ]; then
        font_home="$HOME/Library/Fonts"
    else
        font_home="$DATA_HOME/fonts/PortableTerminal"
    fi
    if [ "$DRY_RUN" -eq 1 ]; then
        log "Would install JetBrainsMono Nerd Font Mono v3.5.1 in $font_home; SHA256 $expected"
        return
    fi
    fetch_asset "$expected" "$url"
    stage="$WORK/fonts"
    mkdir -p "$stage"
    # Extract only four Mono faces, not all 96 patched variants.
    tar -xJf "$DOWNLOADED_ASSET" -C "$stage" \
        JetBrainsMonoNerdFontMono-Regular.ttf JetBrainsMonoNerdFontMono-Bold.ttf \
        JetBrainsMonoNerdFontMono-Italic.ttf JetBrainsMonoNerdFontMono-BoldItalic.ttf OFL.txt
    for face in "$stage"/*.ttf; do put_file "$face" "$font_home/${face##*/}" 644; done
    put_file "$stage/OFL.txt" "$font_home/JetBrainsMonoNerdFontMono-OFL.txt" 644
    if [ "$OS" = Linux ] && have fc-cache; then fc-cache -f "$font_home"; fi
}
