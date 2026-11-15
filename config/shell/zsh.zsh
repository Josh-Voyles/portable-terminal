# Interactive Zsh on Linux and macOS. Never load this from .zshenv.
case $- in *i*) ;; *) return ;; esac
[ "${TERM:-dumb}" != dumb ] || return
[ "${_PORTABLE_TERMINAL_ZSH_LOADED:-0}" != 1 ] || return
_PORTABLE_TERMINAL_ZSH_LOADED=1

# macOS non-login shells may not have received Homebrew's PATH.
if [[ $OSTYPE == darwin* ]]; then
    for _pt_prefix in /opt/homebrew /usr/local; do
        if [[ -x $_pt_prefix/bin/brew ]]; then
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

# Keep shell editing consistent even when a nested shell inherits EDITOR=vim.
# This does not change Vim's own modes or keybindings.
bindkey -e

# Save history promptly without importing other tabs' commands into this one.
: "${HISTFILE:=${XDG_STATE_HOME:-$HOME/.local/state}/zsh/history}"
if [[ ! -d ${HISTFILE:h} ]]; then
    (umask 077; mkdir -p -- "${HISTFILE:h}") ||
        print -u2 -- 'portable-terminal: cannot create the history directory.'
fi
HISTSIZE=50000
SAVEHIST=50000
setopt APPEND_HISTORY INC_APPEND_HISTORY EXTENDED_HISTORY HIST_IGNORE_SPACE HIST_IGNORE_DUPS
unsetopt SHARE_HISTORY INC_APPEND_HISTORY_TIME

if (( $+commands[eza] )); then
    alias ls='eza --group-directories-first --icons=auto --color=auto'
    alias ll='eza --long --all --git --header --group-directories-first --icons=auto --color=auto'
    alias la='eza --all --group-directories-first --icons=auto --color=auto'
    alias tree='eza --tree --level=2 --git-ignore --group-directories-first --icons=auto --color=auto'
elif [[ $OSTYPE == darwin* ]]; then
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

if (( $+commands[fzf] )); then
    export FZF_DEFAULT_OPTS="--height=45% --layout=reverse --border=rounded --info=inline --prompt='❯ ' --pointer='▶' --marker='✓' --color=bg+:#313244,bg:#1e1e2e,spinner:#f5e0dc,hl:#f38ba8,fg:#cdd6f4,header:#f38ba8,info:#cba6f7,pointer:#f5e0dc,marker:#b4befe,fg+:#cdd6f4,prompt:#cba6f7,hl+:#f38ba8,selected-bg:#45475a,border:#6c7086,label:#cdd6f4"
    if (( $+commands[fd] )); then
        export FZF_DEFAULT_COMMAND='fd --type f --hidden --exclude .git'
        export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
        export FZF_ALT_C_COMMAND='fd --type d --hidden --exclude .git'
    fi
    if (( $+commands[bat] )); then
        export FZF_CTRL_T_OPTS="--preview 'bat --color=always --style=numbers --line-range=:200 -- {}' --preview-window=right:55%:wrap --bind 'ctrl-/:toggle-preview'"
    fi
    if (( $+commands[eza] )); then
        export FZF_ALT_C_OPTS="--preview 'eza --tree --level=2 --color=always --icons=always --git-ignore -- {}'"
    fi
fi

# Upstream Yazi wrapper: q changes the shell directory; Q leaves it alone.
y() {
    local _pt_tmp _pt_cwd _pt_result
    _pt_tmp=$(mktemp "${TMPDIR:-/tmp}/yazi-cwd.XXXXXX") || return
    if command yazi "$@" --cwd-file="$_pt_tmp"; then
        _pt_result=0
    else
        _pt_result=$?
    fi
    if [[ -f $_pt_tmp ]]; then
        _pt_cwd=$(cat -- "$_pt_tmp")
        if [[ -n $_pt_cwd && $_pt_cwd != "$PWD" ]]; then
            builtin cd -- "$_pt_cwd" || _pt_result=$?
        fi
    fi
    rm -f -- "$_pt_tmp"
    return "$_pt_result"
}

# Initialize completion only if Oh My Zsh / another framework hasn't done it.
# -i ignores insecure completion directories rather than prompting on startup.
if ! (( $+functions[compdef] )); then
    autoload -Uz compinit
    compinit -i
fi
if command -v fzf >/dev/null 2>&1; then
    if _pt_fzf_init=$(fzf --zsh 2>/dev/null); then
        eval "$_pt_fzf_init"
    else
        printf '%s\n' 'portable-terminal: fzf shell integration needs fzf >= 0.48.' >&2
    fi
    unset _pt_fzf_init
fi
if command -v starship >/dev/null 2>&1 && ! (( $+functions[prompt_starship_precmd] )); then
    eval "$(starship init zsh)"
fi

# Highlighting must be loaded after completion, fzf, and other ZLE widgets.
if ! (( $+functions[_zsh_highlight] )); then
    if [[ -r ${XDG_CONFIG_HOME:-$HOME/.config}/portable-terminal/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh ]]; then
        source "${XDG_CONFIG_HOME:-$HOME/.config}/portable-terminal/plugins/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh"
    else
        print -u2 -- 'portable-terminal: syntax highlighting is missing; rerun bash install.sh --config-only.'
    fi
fi
