# shellcheck shell=bash
# Bash 3.2+; interactive only. A login shell may reach this through two files.
case $- in *i*) ;; *) return ;; esac
[ "${TERM:-dumb}" != dumb ] || return
[ "${_PORTABLE_TERMINAL_BASH_LOADED:-0}" != 1 ] || return
_PORTABLE_TERMINAL_BASH_LOADED=1

# Fedora's /etc/bashrc has its own load guard; don't replace distro defaults.
if [ -r /etc/bashrc ]; then . /etc/bashrc; fi
shopt -s histappend checkwinsize
# shellcheck source=config/shell/common.sh
. "${XDG_CONFIG_HOME:-$HOME/.config}/portable-terminal/shell/common.sh"

if command -v fzf >/dev/null 2>&1; then
    if _pt_fzf_init=$(fzf --bash 2>/dev/null); then
        eval "$_pt_fzf_init"
    else
        printf '%s\n' 'portable-terminal: fzf shell integration needs fzf >= 0.48.' >&2
    fi
    unset _pt_fzf_init
fi
# STARSHIP_SHELL is exported and can be inherited by a fresh nested shell.
# Check for this shell's function, not just that environment variable.
if command -v starship >/dev/null 2>&1 && ! declare -F starship_precmd >/dev/null; then
    eval "$(starship init bash)"
fi
