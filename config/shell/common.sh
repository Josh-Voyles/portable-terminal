# shellcheck shell=bash
# Shared by interactive Bash and Zsh. No hostnames, credentials, or fixed users.
case $- in *i*) ;; *) return ;; esac
[ "${TERM:-dumb}" != dumb ] || return

# macOS login shells normally get this from /etc/zprofile. Also support shells
# launched directly by an editor or a non-login terminal profile.
if [ "$(uname -s)" = Darwin ]; then
    for _pt_prefix in /opt/homebrew /usr/local; do
        if [ -x "$_pt_prefix/bin/brew" ]; then
            case :$PATH: in
                *:"$_pt_prefix/bin":*) ;;
                *) PATH="$_pt_prefix/bin:$_pt_prefix/sbin:$PATH" ;;
            esac
            break
        fi
    done
    unset _pt_prefix
fi
case :$PATH: in *:"$HOME/.local/bin":*) ;; *) PATH="$HOME/.local/bin:$PATH" ;; esac
export PATH

export STARSHIP_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/portable-terminal/starship.toml"
export EDITOR=vim
export VISUAL="$EDITOR"
export BAT_THEME='Catppuccin Mocha'

if command -v eza >/dev/null 2>&1; then
    alias ls='eza --group-directories-first --icons=auto --color=auto'
    alias ll='eza --long --all --git --header --group-directories-first --icons=auto --color=auto'
    alias la='eza --all --group-directories-first --icons=auto --color=auto'
    alias tree='eza --tree --level=2 --git-ignore --group-directories-first --icons=auto --color=auto'
elif [ "$(uname -s)" = Darwin ]; then
    # BSD ls does not understand GNU --color or --group-directories-first.
    alias ls='ls -G'
    alias ll='ls -alhG'
    alias la='ls -AG'
else
    alias ls='ls --color=auto'
    alias ll='ls -alh --color=auto'
    alias la='ls -A --color=auto'
fi
alias grep='grep --color=auto'
alias ..='cd ..'

if command -v fzf >/dev/null 2>&1; then
    export FZF_DEFAULT_OPTS="--height=45% --layout=reverse --border=rounded --info=inline --prompt='❯ ' --pointer='▶' --marker='✓' --color=bg+:#313244,bg:#1e1e2e,spinner:#f5e0dc,hl:#f38ba8,fg:#cdd6f4,header:#f38ba8,info:#cba6f7,pointer:#f5e0dc,marker:#b4befe,fg+:#cdd6f4,prompt:#cba6f7,hl+:#f38ba8,selected-bg:#45475a,border:#6c7086,label:#cdd6f4"
    if command -v fd >/dev/null 2>&1; then
        export FZF_DEFAULT_COMMAND='fd --type f --hidden --exclude .git'
        export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
        export FZF_ALT_C_COMMAND='fd --type d --hidden --exclude .git'
    fi
    if command -v bat >/dev/null 2>&1; then
        export FZF_CTRL_T_OPTS="--preview 'bat --color=always --style=numbers --line-range=:200 -- {}' --preview-window=right:55%:wrap --bind 'ctrl-/:toggle-preview'"
    fi
    if command -v eza >/dev/null 2>&1; then
        export FZF_ALT_C_OPTS="--preview 'eza --tree --level=2 --color=always --icons=always --git-ignore -- {}'"
    fi
fi

# Quit Yazi with q to cd to its last directory; Q leaves the shell cwd alone.
# Plain `yazi` is untouched. This is the upstream shell-wrapper pattern.
y() {
    local _pt_tmp _pt_cwd _pt_result
    _pt_tmp=$(mktemp "${TMPDIR:-/tmp}/yazi-cwd.XXXXXX") || return
    command yazi "$@" --cwd-file="$_pt_tmp"
    _pt_result=$?
    if [ -f "$_pt_tmp" ]; then
        _pt_cwd=$(cat -- "$_pt_tmp")
        if [ -n "$_pt_cwd" ] && [ "$_pt_cwd" != "$PWD" ]; then
            builtin cd -- "$_pt_cwd" || _pt_result=$?
        fi
    fi
    rm -f -- "$_pt_tmp"
    return "$_pt_result"
}
