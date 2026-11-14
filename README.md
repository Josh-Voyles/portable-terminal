# Portable terminal

My Catppuccin Mocha setup for Linux and macOS: a two-line Starship prompt with
Git branch/status, JetBrains Mono Nerd Font Mono, colorful file listings,
fuzzy search, and Yazi. Bash and Zsh get the same prompt and shortcuts.

Kitty keeps my existing padding, tabs, split-window shortcuts, and cursor
settings. On a Mac, the installer also supplies matching iTerm2 and Apple
Terminal profiles. It doesn't switch your shell or change which terminal
profile is the default.

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

- Linux or macOS on x86_64 or arm64; Bash 3.2 or newer runs the installer.
- `curl`, `tar`, and either `sha256sum` or `shasum`.
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

Linux arm64 uses a glibc-based eza build because that release doesn't offer
an arm64 musl build. Other Linux downloads use musl builds. Older Linux
systems may still need newer libraries for a particular tool; install that
tool through your package manager and rerun if a bundled binary won't start.

### Useful options

```sh
bash install.sh --config-only           # Already have tools and fonts
bash install.sh --shell zsh             # Only add Zsh startup hooks
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

Open a new tab after installing. For an immediate check, run
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

- Appends/replaces a marked block in `.bashrc` and the first existing Bash
  login file (`.bash_profile`, `.bash_login`, or `.profile`). This avoids
  masking an existing login configuration. Zsh gets a block in `.zshrc`.
- Copies shell modules and the prompt to `~/.config/portable-terminal/`.
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
An Apple Terminal profile you've already imported also remains in Terminal's
preferences; remove it there if no longer wanted. Backups and download caches
are retained, and empty directories may remain.

## Update, test, and host

After editing this repository, rerun the installer. Installed configuration
is copied rather than symlinked, so moving the checkout doesn't break it.
Linux versions and hashes live in `packages.lock`; fonts are pinned in
`lib/packages.sh`. Verify new hashes against the upstream release metadata
before changing them. Homebrew follows its own formula versions.

Developers need Python **3.11+** for the offline tests and profile generator.
ShellCheck is optional but recommended:

```sh
bash scripts/check.sh
python3 scripts/generate-profiles.py          # After changing profile colors/fonts
python3 scripts/generate-profiles.py --check  # Check without modifying profiles
```

Tests use temporary home directories and fake download/package-manager
commands. They cover repeat installs, restore, checksum rejection, Bash/Zsh
startup, macOS profile data, and preservation of unrelated settings. The
macOS installer branch is simulated in those tests; native GUI/profile
behavior still needs a smoke test on a Mac. Bash 3.2 can also be tested on
Linux using the official `bash:3.2` container image.

The 33 offline tests have passed under Bash 3.2 with Zsh 5.9 available, as
well as under the host's newer Bash (where the Zsh test is skipped if absent).
The Linux x86_64 binaries, prompt, font extraction, Kitty configuration, and
Yazi startup have also been checked with real downloads/configuration.

The included Gitea Actions workflow expects an `ubuntu-latest` runner with
Python 3.11+ and Bash. Zsh and ShellCheck tests run when those commands are
available. You can add a macOS runner for native checks.

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
