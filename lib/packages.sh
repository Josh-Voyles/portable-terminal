# shellcheck shell=bash disable=SC2153
# ARCH is the global platform; arch is one row's architecture in packages.lock.
# Downloads are pinned and checked before extraction. No remote installer scripts.

ZSH_HIGHLIGHT_VERSION=0.8.0
ZSH_HIGHLIGHT_SHA256=5981c19ebaab027e356fe1ee5284f7a021b89d4405cc53dc84b476c3aee9cc32
ZSH_HIGHLIGHT_URL=https://github.com/zsh-users/zsh-syntax-highlighting/archive/refs/tags/0.8.0.tar.gz

FZF_TAB_VERSION=1.3.0
FZF_TAB_SHA256=d75ac08c2c8af5a6a0478787b0f11fabbe24951973b7841ae963431e2070ee9a
FZF_TAB_URL=https://github.com/Aloxaf/fzf-tab/archive/refs/tags/v1.3.0.tar.gz

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
        for formula in starship eza fzf bat fd ripgrep yazi zoxide; do
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

install_highlighting() {
    local stage source target file
    target="$DEST/plugins/zsh-syntax-highlighting"
    if [ "$DRY_RUN" -eq 1 ]; then
        log "Would install zsh-syntax-highlighting $ZSH_HIGHLIGHT_VERSION; SHA256 $ZSH_HIGHLIGHT_SHA256"
        return
    fi
    fetch_asset "$ZSH_HIGHLIGHT_SHA256" "$ZSH_HIGHLIGHT_URL"
    stage="$WORK/highlighting"
    mkdir -p "$stage"
    tar -xzf "$DOWNLOADED_ASSET" -C "$stage"
    source="$stage/zsh-syntax-highlighting-$ZSH_HIGHLIGHT_VERSION"
    # Keep upstream runtime files and its license, not screenshots or test data.
    for file in zsh-syntax-highlighting.zsh .version .revision-hash COPYING.md; do
        put_file "$source/$file" "$target/$file"
    done
    for file in "$source"/highlighters/*/*-highlighter.zsh; do
        put_file "$file" "$target/${file#"$source/"}"
    done
}

install_completion() {
    local stage source target file mode
    target="$DEST/plugins/fzf-tab"
    if [ "$DRY_RUN" -eq 1 ]; then
        log "Would install fzf-tab $FZF_TAB_VERSION; SHA256 $FZF_TAB_SHA256"
        return
    fi
    fetch_asset "$FZF_TAB_SHA256" "$FZF_TAB_URL"
    stage="$WORK/completion"
    mkdir -p "$stage"
    tar -xzf "$DOWNLOADED_ASSET" -C "$stage"
    source="$stage/fzf-tab-$FZF_TAB_VERSION"
    # Install runtime helpers and both MIT licenses, not the optional C module.
    for file in fzf-tab.zsh LICENSE lib/zsh-ls-colors/ls-colors.zsh lib/zsh-ls-colors/LICENSE; do
        put_file "$source/$file" "$target/$file"
    done
    for file in "$source"/lib/*; do
        [ -f "$file" ] || continue
        mode=600
        if [ -x "$file" ]; then mode=700; fi
        put_file "$file" "$target/${file#"$source/"}" "$mode"
    done
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
