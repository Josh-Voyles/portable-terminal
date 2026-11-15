# Portable terminal

My Catppuccin Mocha setup for Linux and macOS: a two-line Starship prompt with
Git branch/status, JetBrains Mono Nerd Font Mono, colorful file listings,
fuzzy search, and Yazi. Both systems use Zsh, with searchable Tab completion and
live command-line syntax highlighting.

Kitty keeps my existing padding, tabs, split-window shortcuts, and cursor
settings. On a Mac, the installer also supplies matching iTerm2 and Apple
Terminal profiles. If Zsh isn't already your login shell, installation asks
whether to make it the default. Terminal-profile defaults stay untouched.

## Install

Clone the whole repository from Gitea. Replace the example URL with yours:

```sh
git clone https://gitea.example.com/josh/portable-terminal.git
cd portable-terminal
bash install.sh --dry-run
bash install.sh
```

Review the dry run first. The installer uses bundled files, so downloading
`install.sh` by itself or piping it into a shell won't work. No credentials,
machine-specific paths, or existing dotfiles are copied into this repository.

### Requirements

- Linux or macOS on x86_64 or arm64.
- **Zsh must already be installed and available as `zsh` on PATH**, including
  its standard completion functions. macOS normally provides it. On Linux,
  ask your administrator to install it if it's missing. The installer fails
  before making changes when Zsh isn't available; it never installs Zsh.
- Bash 3.2+ runs the installer and restore script. You don't need to use Bash
  as your interactive shell or upgrade the Bash shipped with macOS.
- `curl`, `tar`, and either `sha256sum` or `shasum`, including for `--config-only`.
- Linux also needs `unzip` for Yazi and `xz` for the font archive.
- macOS tool installation needs an existing [Homebrew](https://brew.sh/).
  Homebrew isn't installed automatically. Intel and Apple Silicon prefixes
  are both supported.
- `git`, `file`, and `vim` should be available. On a fresh Mac, install Apple's
  Command Line Tools (`xcode-select --install`) if Git isn't available.

The installer doesn't use sudo. Linux downloads official release binaries
into `~/.local/bin`, checks their pinned SHA256 hashes, and leaves existing
commands alone. macOS installs missing tools through Homebrew. Fonts go into
your account's font directory. You don't need Python to install or restore.

Searchable Tab menus come from [fzf-tab](https://github.com/Aloxaf/fzf-tab), and
syntax highlighting comes from
[zsh-syntax-highlighting](https://github.com/zsh-users/zsh-syntax-highlighting).
Both plugins are loaded directly. Installation downloads their pinned,
checksum-verified archives to your user cache, even with `--config-only`;
later runs reuse the verified cache. Nothing is downloaded when a shell starts.
Oh My Zsh, a plugin manager, bash-completion, and ble.sh aren't needed.

### Your default shell

If your account already uses Zsh, the installer leaves it alone. Otherwise it
asks **“Make Zsh your default login shell? [y/N]”**. Pressing Enter keeps the
current default. For unattended installs, choose one of:

```sh
bash install.sh --make-default-shell
bash install.sh --keep-default-shell
```

Without a terminal or an explicit choice, installation stops before changes
if the default isn't Zsh. `--dry-run` never prompts or changes your account.

Changing the default uses the system's `chsh`. It needs `getent` on Linux or
`dscacheutil` on macOS to read your account's current shell. `chsh` may ask for
your account password, and host policy can reject the change (for example,
if the Zsh pathname isn't approved in `/etc/shells`). The installer never
uses sudo, edits that file, or handles your password. A failed shell change
returns an error but keeps the installed configuration and prints its backup
directory. Use `--keep-default-shell` if you only want the configuration.

After installation, start Zsh with `zsh -l`, or log out and back in after
changing the default. Existing terminal profiles that explicitly launch Bash
will still do so; select the login shell or Zsh in those profiles yourself.

Linux arm64 uses a glibc-based eza build because that release doesn't offer
an arm64 musl build. Other Linux downloads use musl builds. Older Linux
systems may still need newer libraries for a particular tool; install that
tool through your package manager and rerun if a bundled binary won't start.

### Useful options

```sh
bash install.sh --config-only           # Keep tools/fonts; still install shell plugins
bash install.sh --keep-default-shell    # Don't change the account's login shell
bash install.sh --no-terminals          # Keep all terminal profiles untouched
bash install.sh --no-yazi               # Keep your existing Yazi theme
bash install.sh --ptyxis                # Also set Ptyxis's font on Linux
bash install.sh --import-terminal       # Mac: open the profile for import
bash install.sh --reinstall-tools       # Explicitly replace/reinstall the tools
```

`--reinstall-tools` installs the versions in `packages.lock` on Linux, even
if that means downgrading a newer tool. On macOS, it reinstalls installed
Homebrew formulae and installs missing ones. Normal runs don't update
existing tools. Use `bash install.sh --help` for all options.

Use recent tool versions: this configuration is tested with the Linux pins
and targets current Homebrew formulae. If an older existing tool rejects an
option, update it or use `--reinstall-tools` rather than keeping that version.

In a fresh Zsh session, run
`~/.local/bin/terminal-doctor`. This prints tool paths, an icon sample, and
the current Git branch if you're in a repository.

## Choose a terminal profile

### Kitty (Linux and Mac)

The installer adds a small managed `include` block to `~/.config/kitty/kitty.conf`.
Existing settings stay in place; the included appearance settings take
precedence. Press **Ctrl+Shift+F5** to reload, then open a new tab.

Kitty itself isn't installed automatically. On macOS, you can install it with
`brew install --cask kitty`; on Linux, use your usual package manager.

### iTerm2 (Mac)

Choose **Profiles → Portable Terminal - Mocha**. The dynamic profile includes
the font and colors; it loads from
`~/Library/Application Support/iTerm2/DynamicProfiles/portable-terminal.json`.
If iTerm2 was open during installation, it should pick up the file without
a restart. You can select the profile as your default in iTerm2's settings.

### Apple Terminal (Mac)

In **Settings → Profiles**, use the menu below the profile list to import:

```text
~/.config/portable-terminal/profiles/Portable-Mocha.terminal
```

Or pass `--import-terminal` during installation to open the file for import.
The profile already includes the correct 12-point font. Choose it for a new
window and make it the default if you want. Import once; importing repeatedly
can create duplicate profiles in Terminal's own preferences.

Apple Terminal has fewer graphics/color capabilities than Kitty or iTerm2.
The shell, Git prompt, and file icons still work, but don't expect identical
true-color rendering or the same Yazi image previews.

### Ptyxis and other terminals

Select **JetBrainsMono Nerd Font Mono**, size **12**, in each terminal's
preferences. Installing a font doesn't select it in every application.
`--ptyxis` handles that font selection for Ptyxis and records the previous
settings for restore; it doesn't change GNOME's system-wide font.

Icons are font glyphs. Image previews use separate terminal graphics
protocols, so fixing one doesn't fix the other. Over SSH, the Nerd Font belongs
on the **local computer displaying the terminal**, not just the remote host.
The installer never forces a global `TERM` value.

## Everyday commands

| Command or key | What it does |
| --- | --- |
| `ls`, `la`, `ll` | eza listings with icons; `ll` includes Git file status |
| `tree` | Two directory levels, respecting `.gitignore` |
| `bat file` | Syntax highlighting in matching colors; plain `cat` stays unchanged |
| `tldr tar` | Short, practical command examples (provided by tealdeer) |
| **Tab** | Search available subcommands, flags, files, or directories with fzf-tab |
| **Ctrl+R** | Search shell history |
| **Ctrl+T** | Search files, with a bat preview; **Ctrl+/** toggles it |
| **Alt+C** | Find a directory and change into it |
| `y` | Open Yazi; quit with `q` to change the shell's directory too |
| `yazi` | Open Yazi without changing the shell's directory afterward |
| `terminal-doctor` | Check commands, show sample icons, explain the branch display |

The prompt hides the branch outside Git repositories. Within one, `!` means
modified, `+` staged, `?` untracked, and `↑` / `↓` ahead / behind. It shows
language versions when relevant and command duration after two seconds.
Your editor preference stays `vim`.

Run `tldr --update` once after installation to download the community-maintained
pages, then try `tldr tar` or `tldr git commit`. Cached pages work offline;
rerun `tldr --update` when you want fresh examples. The installer doesn't fetch
pages or change an existing tldr client's configuration. An existing `tldr`
command is kept unless you pass `--reinstall-tools`.

Shell command editing uses Emacs-style shortcuts, including Ctrl+A and Ctrl+E.
This doesn't change Vim's own keybindings. Inline gray-text suggestions aren't
enabled.

### Searchable Tab completion

Tab still completes files and directories. `fzf-tab` replaces the plain
selection list with a searchable menu, using the completion definitions Zsh
already has:

```text
cd <Tab>          → directories
cat <Tab>         → files
git <Tab>         → Git subcommands
aws s3 <Tab>      → AWS subcommands (when aws_completer is available)
aws s3 cp --<Tab>  → AWS flags
```

Type to filter, use the arrow keys to select, and press **Enter** to insert
the selection without running the command. **Esc** cancels the menu. A single
match may complete directly without opening a menu.

AWS completion is enabled automatically when the AWS CLI's `aws_completer`
is on `PATH`. The installer doesn't install AWS, configure an account, or
change credentials. If `aws` works but `command -v aws_completer` doesn't,
add the directory containing your AWS installation's completer to `PATH`
before starting a new Zsh session.

Other commands also need their own completion definitions; `fzf-tab` doesn't
generate them. Existing Ctrl+R, Ctrl+T, and Alt+C shortcuts stay available.
With `--config-only` or `--no-tools`, install `fzf` separately if needed;
without it, ordinary Zsh Tab completion stays in place.

### Shell history

Zsh saves up to roughly 50,000 history entries. An existing `HISTFILE` location
is retained; otherwise history goes to
`${XDG_STATE_HOME:-~/.local/state}/zsh/history`. Commands are appended promptly,
but active tabs keep independent histories; new sessions read the combined
saved history. Commands beginning with a space aren't saved. Don't rely on
that to keep secrets out of logs or other programs.

Existing Bash history and private Bash startup settings are left untouched.
Old Bash commands won't automatically appear in Zsh history search. Move any
needed personal exports or tool setup into the appropriate Zsh startup file
yourself; don't source an entire `.bashrc` from Zsh.

### Terminal shortcuts and Yazi

In Kitty, **Ctrl+Shift+E / O** creates side-by-side / stacked splits;
**Ctrl+Shift+H / J / K / L** changes focus. **Ctrl+Shift+T** opens a tab in
the current directory. On macOS, the native profiles make Option act as Meta
so **Option+C** can reach the shell's Alt+C shortcut.

Yazi's basic browsing and icons don't require video/PDF preview tools. If you
want those on a Mac, start with:

```sh
brew install ffmpeg sevenzip jq poppler resvg imagemagick
```

See [Yazi's dependency list](https://yazi-rs.github.io/docs/installation/) for
Linux packages and format-specific requirements. This installer deliberately
doesn't add third-party Linux repositories or install large preview packages.

## What changes

- Appends/replaces one marked block in `.zshrc`. Keep it after any custom
  completion/widget setup so syntax highlighting loads last.
- Removes only this project's old marked blocks from `.bashrc`,
  `.bash_profile`, `.bash_login`, and `.profile`, with backups. Unrelated
  content and the files themselves are retained.
- Copies the Zsh configuration, completion/highlighting plugins, and prompt to
  `~/.config/portable-terminal/`.
  The shell sets `STARSHIP_CONFIG` to that copy; an existing
  `~/.config/starship.toml` is left alone.
- Replaces Yazi's `theme.toml` after backing it up, but leaves `yazi.toml`,
  keymaps, and plugins untouched. Bundled file icons are retained.
- Adds the Kitty include and, on macOS, the separate native profiles.
- Installs missing tools and four font faces unless disabled.

Configuration runs are repeatable: unchanged files aren't rewritten, managed
blocks aren't duplicated, and reruns don't keep creating new backups.
Startup configuration only runs in interactive shells with a usable terminal;
it doesn't alter noninteractive scripts. Reopen a tab to load changed modules.
If another shell framework already initialized Starship, its integration is
reused with this prompt configuration.

`XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME`, `XDG_CACHE_HOME`,
`ZDOTDIR`, and `YAZI_CONFIG_HOME` are respected. Keep those variables set
consistently when installing and launching your shell. Relative paths and
paths containing tabs or newlines are rejected. Fish isn't configured.
Bash interactive configuration is no longer supported.

## Backups and restore

Each run that changes files prints its private backup directory, normally:

```text
~/.local/state/portable-terminal/backups/<UTC-time>-<process-id>/
```

The directory is mode `700`. Backups may contain secrets from existing
startup files; keep them off Gitea and out of shared folders. The installer
never sources those files or prints their contents.

Use the exact directory printed by the installer:

```sh
bash restore.sh --dry-run /path/to/backup-directory
bash restore.sh /path/to/backup-directory
```

Restore removes new files and puts back replaced files, including original
symlinks. It compares hashes first and skips files you've edited since the
installation (exit status `2`). Inspect those files before considering
`--force`, which explicitly discards later edits. Restore newer backup sets
before older ones if you've made several rounds of changes.

Homebrew package installs can't be rolled back by this file-based restore.
The account's login shell isn't rolled back either. When a shell change was
attempted, its previous value is recorded in the backup's `previous-shell`
file; the installer and restore script print the `chsh -s ...` command for
switching back manually. Shell history isn't part of configuration restore.
An Apple Terminal profile you've already imported also remains in Terminal's
preferences; remove it there if no longer wanted. Backups and download caches
are retained, and empty directories may remain.

## Update, test, and host

After editing this repository, rerun the installer. Installed configuration
is copied rather than symlinked, so moving the checkout doesn't break it.
Linux versions and hashes live in `packages.lock`; fonts and the shell plugin
archives are pinned in `lib/packages.sh`. Verify new hashes against upstream
metadata or a trusted package recipe before changing them. Homebrew follows
its own formula versions.

Developers need Zsh and Python **3.11+** for the offline tests and profile generator.
ShellCheck is optional but recommended:

```sh
bash scripts/check.sh
python3 scripts/generate-profiles.py          # After changing profile colors/fonts
python3 scripts/generate-profiles.py --check  # Check without modifying profiles
```

Tests use temporary home directories and fake download/package-manager
commands. They cover repeat installs, restore, checksum rejection, required
Zsh detection, consent/default-shell handling, old Bash-hook removal, Zsh
startup, completion widget order/fallback, AWS completion, history, the Yazi
wrapper, macOS profile data, and preservation of unrelated settings. Unit tests
mock account changes; they never call the host's real `chsh`. Zsh tests are
required, not silently skipped.

The Gitea workflow uses a disposable Linux job container and provisions Zsh
there. It also runs a real plugin/configuration install and automatically
changes that container's account shell, never the runner host's shell.
The runner must support job containers. No password-handling test setup is
added; real authentication and native macOS behavior still need manual checks.

### Mac smoke test

The tests simulate macOS installation, not native terminal behavior. On a Mac:

- Check `command -v zsh`, then review `bash install.sh --dry-run`.
- Install and confirm an already-default Zsh doesn't trigger a shell change.
- Open a fresh Zsh login session. Check the Git prompt, searchable Tab menus
  for files/directories and Git, live syntax highlighting, Ctrl+R, Ctrl+T,
  and Option+C. If AWS is installed, check `aws s3 <Tab>` and `aws s3 cp --<Tab>`.
- Check a command remains in history after closing and reopening the session.
- Run Vim normally; check `y` changes directory after Yazi's `q`, while `Q`
  leaves it alone.
- Check fonts, icons, and colors in each terminal profile you use. In Kitty,
  also check splits, tabs, and focus shortcuts.

To publish, create an empty Gitea repository, then run from this directory:

```sh
git init -b main
git add .
git commit -m "Add portable terminal setup"
git remote add origin https://gitea.example.com/josh/portable-terminal.git
git push -u origin main
```

Use your configured Git/SSH credentials rather than embedding a token in
this repository or its clone URL.
