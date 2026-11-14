# Upstream sources

These are the maintainers' own documentation and release repositories. They
define the actual configuration formats and release assets used here, rather
than relying on a third-party setup script.

- [Starship](https://starship.rs/guide/) documents Bash/Zsh initialization and
  Nerd Font requirements. Linux downloads come from
  [starship/starship](https://github.com/starship/starship/releases).
- [Yazi installation](https://yazi-rs.github.io/docs/installation/) distinguishes
  file detection, fonts, and optional preview helpers. Official binaries come
  from [sxyazi/yazi](https://github.com/sxyazi/yazi/releases).
- [iTerm2 Dynamic Profiles](https://iterm2.com/documentation-dynamic-profiles.html)
  documents the per-user directory and `Profiles`/`Name`/`Guid` fields used by
  the generated profile.
- [Apple's Terminal profile documentation](https://support.apple.com/guide/terminal/import-and-export-terminal-profiles-trml4299c696/mac)
  describes profile imports. The keyed color archives follow the structure in
  [catppuccin/Terminal.app](https://github.com/catppuccin/Terminal.app).
- [Homebrew](https://docs.brew.sh/Manpage) documents formula installation and
  the environment switches used to avoid incidental updates and cleanup.
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
