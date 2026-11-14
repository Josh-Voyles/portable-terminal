# macOS's default shell. Don't replace the user's .zshrc or framework setup.
case $- in *i*) ;; *) return ;; esac
[ "${TERM:-dumb}" != dumb ] || return
[ "${_PORTABLE_TERMINAL_ZSH_LOADED:-0}" != 1 ] || return
_PORTABLE_TERMINAL_ZSH_LOADED=1

# shellcheck source=config/shell/common.sh
. "${XDG_CONFIG_HOME:-$HOME/.config}/portable-terminal/shell/common.sh"

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
