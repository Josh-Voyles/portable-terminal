# Upstream sources

These are the maintainers' own documentation and release repositories. They
define the actual configuration formats and release assets used here, rather
than relying on a third-party setup script.

- [Starship](https://starship.rs/guide/) documents Zsh initialization and
  Nerd Font requirements. Linux downloads come from
  [starship/starship](https://github.com/starship/starship/releases).
- [Yazi installation](https://yazi-rs.github.io/docs/installation/) distinguishes
  file detection, fonts, and optional preview helpers. Official binaries come
  from [sxyazi/yazi](https://github.com/sxyazi/yazi/releases).
- [zoxide 0.10.0 documentation](https://github.com/ajeetdsouza/zoxide/tree/v0.10.0)
  defines Zsh initialization after `compinit`, the default `z`/`zi` commands,
  and local database preferences. Linux musl binaries for both architectures
  come from its [official releases](https://github.com/ajeetdsouza/zoxide/releases/tag/v0.10.0);
  SHA256 pins were checked against GitHub's release-asset metadata. Interactive
  selection uses the existing fzf (upstream requires fzf 0.51.0+).
- [iTerm2 Dynamic Profiles](https://iterm2.com/documentation-dynamic-profiles.html)
  documents the per-user directory and `Profiles`/`Name`/`Guid` fields used by
  the generated profile.
- [Apple's Terminal profile documentation](https://support.apple.com/guide/terminal/import-and-export-terminal-profiles-trml4299c696/mac)
  describes profile imports. The keyed color archives follow the structure in
  [catppuccin/Terminal.app](https://github.com/catppuccin/Terminal.app).
- [Homebrew](https://docs.brew.sh/Manpage) documents formula installation and
  the environment switches used to avoid incidental updates and cleanup.
- [Zsh's completion system](https://zsh.sourceforge.io/Doc/Release/Completion-System.html)
  supplies completion candidates for commands, flags, files, and directories.
- [fzf-tab 1.3.0](https://github.com/Aloxaf/fzf-tab/tree/v1.3.0) displays those
  candidates in searchable menus. Its archive is downloaded and SHA256-checked
  on both platforms. The checksum was cross-checked against
  [Homebrew's formula](https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/f/fzf-tab.rb).
  Unmodified runtime helpers and the MIT licenses for fzf-tab and its bundled
  zsh-ls-colors library are installed; the optional compiled module isn't.
  It is loaded after fzf's shell integration and before syntax highlighting.
- [AWS CLI command completion](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-completion.html)
  documents the `bashcompinit` / `complete -C` integration used when an existing
  AWS installation supplies `aws_completer` on `PATH`. AWS itself isn't installed.
- [zsh-syntax-highlighting 0.8.0](https://github.com/zsh-users/zsh-syntax-highlighting/tree/0.8.0)
  supplies live command-line highlighting. Its archive is downloaded and
  SHA256-checked on both platforms. The checksum was cross-checked against
  Homebrew's upstream formula; its BSD-3-Clause `COPYING.md` is installed
  alongside the unmodified runtime files. It is loaded after fzf/Starship.
- The palette and theme settings are adapted from
  [catppuccin/kitty](https://github.com/catppuccin/kitty) and
  [catppuccin/yazi](https://github.com/catppuccin/yazi). Their MIT license is
  included in `LICENSES/Catppuccin-MIT.txt`.
- [Nerd Fonts](https://github.com/ryanoasis/nerd-fonts/releases/tag/v3.5.1)
  supplies the patched JetBrains Mono faces. The font archive's `OFL.txt` is
  installed alongside the fonts as `JetBrainsMonoNerdFontMono-OFL.txt`.

Other binary release sources are
[eza](https://github.com/eza-community/eza/releases),
[fzf](https://github.com/junegunn/fzf/releases),
[bat](https://github.com/sharkdp/bat/releases),
[fd](https://github.com/sharkdp/fd/releases), and
[ripgrep](https://github.com/BurntSushi/ripgrep/releases).

Linux SHA256 pins were checked against GitHub's release-asset metadata. This
detects a changed download; it isn't a substitute for an independent publisher
signature. Binary archives aren't committed to this repository. macOS package
versions and their checksums are managed by Homebrew instead of `packages.lock`.

Confidence is high for the documented formats and pinned x86_64 Linux assets,
which have been exercised locally. Native macOS profile import/rendering and
Linux arm64 execution haven't been tested on corresponding hardware. One web
search located the official Terminal.app theme repository; other references
were fetched directly from maintainers. No third-party guides were used.
