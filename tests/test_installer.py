"""Offline installer/restore tests. Every install uses an isolated HOME."""

import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import pty
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import tomllib
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASH = os.environ.get("TEST_BASH") or shutil.which("bash")
ZSH = shutil.which("zsh")
if not ZSH:
    raise RuntimeError("Zsh is required for the tests; install it before running checks.")


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="portable-terminal-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.home = self.base / "home with spaces"
        self.home.mkdir()
        self.tools = self.base / "tools"
        self.tools.mkdir()
        self.tmp = self.base / "tmp"
        self.tmp.mkdir()
        self.log = self.base / "commands.log"
        self.env = {
            "HOME": str(self.home),
            "PATH": str(self.tools) + os.pathsep + os.defpath,
            "TMPDIR": str(self.tmp),
            "TERM": "xterm-256color",
            "LANG": "C",
            "LC_ALL": "C",
            "MOCK_LOG": str(self.log),
        }
        # Account changes are always simulated, regardless of the host's shell.
        self.account = self.base / "login-shell"
        self.account.write_text(ZSH + "\n")
        self.env["MOCK_ACCOUNT"] = str(self.account)
        self.shim("getent", 'printf "test:x:1000:1000:Test:%s:%s\\n" "$HOME" "$(cat "$MOCK_ACCOUNT")"')
        self.shim("dscacheutil", 'printf "shell: %s\\n" "$(cat "$MOCK_ACCOUNT")"')
        self.shim("chsh", 'printf "chsh %s\\n" "$*" >> "$MOCK_LOG"\nprintf "%s\\n" "$2" > "$MOCK_ACCOUNT"')
        self.plugin = self.base / "highlighting.tar.gz"
        with tarfile.open(self.plugin, "w:gz") as bundle:
            for name, content in {
                "zsh-syntax-highlighting.zsh": "_zsh_highlight() { :; }\ntypeset -g TEST_HIGHLIGHT_COUNT=$(( ${TEST_HIGHLIGHT_COUNT:-0} + 1 ))\n",
                ".version": "0.8.0\n",
                ".revision-hash": "fixture\n",
                "COPYING.md": "fixture license\n",
                "highlighters/main/main-highlighter.zsh": "# fixture\n",
            }.items():
                payload = content.encode()
                entry = tarfile.TarInfo("zsh-syntax-highlighting-0.8.0/" + name)
                entry.size = len(payload)
                bundle.addfile(entry, io.BytesIO(payload))
        self.env["MOCK_PLUGIN"] = str(self.plugin)
        self.completion_plugin = self.base / "completion.tar.gz"
        with tarfile.open(self.completion_plugin, "w:gz") as bundle:
            for name, content in {
                "fzf-tab.zsh": textwrap.dedent("""\
                    fzf-tab-complete() { :; }
                    typeset -g TEST_FZF_TAB_COUNT=$(( ${TEST_FZF_TAB_COUNT:-0} + 1 ))
                    typeset -g TEST_FZF_TAB_AFTER_COMPINIT=$+functions[compdef]
                    typeset -g TEST_FZF_TAB_BEFORE_HIGHLIGHT=$+functions[_zsh_highlight]
                    typeset -g TEST_FZF_TAB_PREVIOUS_WIDGET=$(bindkey '^I')
                    zle -N fzf-tab-complete
                    bindkey '^I' fzf-tab-complete
                    """),
                "LICENSE": "fixture MIT license\n",
                "lib/-ftb-fzf": "#!/hint/zsh\n# fixture helper\n",
                "lib/-ftb-preview.tpl": "# fixture preview\n",
                "lib/zsh-ls-colors/ls-colors.zsh": "# fixture\n",
                "lib/zsh-ls-colors/LICENSE": "fixture bundled MIT license\n",
            }.items():
                payload = content.encode()
                entry = tarfile.TarInfo("fzf-tab-1.3.0/" + name)
                entry.size = len(payload)
                entry.mode = 0o755 if name == "lib/-ftb-fzf" else 0o644
                bundle.addfile(entry, io.BytesIO(payload))
        self.env["MOCK_COMPLETION_PLUGIN"] = str(self.completion_plugin)
        self.repo = self.copy_repo()
        # Tests never touch the host's font caches or fetch anything from GitHub.
        self.shim("fc-cache", 'printf "fc-cache\\n" >> "$MOCK_LOG"')
        self.curl_shim('printf "unexpected curl\\n" >&2; exit 98')
        self.shim("uname", 'case "$1" in -s) echo "${MOCK_OS:-Linux}" ;; -m) echo "${MOCK_ARCH:-x86_64}" ;; esac')

    def shim(self, name, body):
        path = self.tools / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def curl_shim(self, body):
        self.shim("curl", '''for arg do
    case "$arg" in
        *zsh-syntax-highlighting*)
            while [ "$1" != --output ]; do shift; done
            cp "$MOCK_PLUGIN" "$2"
            exit 0 ;;
        *fzf-tab*)
            while [ "$1" != --output ]; do shift; done
            cp "$MOCK_COMPLETION_PLUGIN" "$2"
            exit 0 ;;
    esac
done
''' + body)

    def run_script(self, script, *args, root=None, expected=0):
        root = root or self.repo
        result = subprocess.run(
            [BASH, str(root / script), *map(str, args)],
            env=self.env,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def install(self, *args, **kwargs):
        return self.run_script("install.sh", "--config-only", *args, **kwargs)

    def backups(self):
        return sorted((self.home / ".local/state/portable-terminal/backups").glob("*"))

    def snapshot(self):
        return {
            str(p.relative_to(self.home)): ("link", os.readlink(p)) if p.is_symlink() else p.read_bytes()
            for p in self.home.rglob("*")
            if p.is_file() or p.is_symlink()
        }

    def copy_repo(self):
        target = Path(tempfile.mkdtemp(prefix="checkout with spaces-", dir=self.base))
        shutil.copytree(ROOT, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        packages = target / "lib/packages.sh"
        packages.write_text(re.sub(
            r"(?m)^ZSH_HIGHLIGHT_SHA256=.*$",
            "ZSH_HIGHLIGHT_SHA256=" + hashlib.sha256(self.plugin.read_bytes()).hexdigest(),
            packages.read_text(),
        ))
        packages.write_text(re.sub(
            r"(?m)^FZF_TAB_SHA256=.*$",
            "FZF_TAB_SHA256=" + hashlib.sha256(self.completion_plugin.read_bytes()).hexdigest(),
            packages.read_text(),
        ))
        return target

    def fixture_download(self, repo, *, zip_archive=False, checksum=None, tool="starship"):
        archive = self.base / ("asset.zip" if zip_archive else "asset.tar.gz")
        payload = b"#!/bin/sh\nprintf 'fixture tool\\n'\n"
        if zip_archive:
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("release/yazi", payload)
                bundle.writestr("release/ya", payload)
            tool, binaries = "yazi", "yazi ya"
        else:
            with tarfile.open(archive, "w:gz") as bundle:
                entry = tarfile.TarInfo("release/" + tool)
                entry.size = len(payload)
                entry.mode = 0o755
                bundle.addfile(entry, io.BytesIO(payload))
            binaries = tool
        digest = checksum or hashlib.sha256(archive.read_bytes()).hexdigest()
        (repo / "packages.lock").write_text(
            f"{tool}|x86_64|{digest}|https://example.invalid/{archive.name}|{binaries}\n"
        )
        self.env["MOCK_DOWNLOAD"] = str(archive)
        self.curl_shim('printf "download\\n" >> "$MOCK_LOG"\nwhile [ "$1" != --output ]; do shift; done\ncp "$MOCK_DOWNLOAD" "$2"')
        return archive

    def test_help_and_invalid_options_dont_write(self):
        self.run_script("install.sh", "--help")
        self.assertEqual(self.snapshot(), {})
        self.run_script("install.sh", "--not-an-option", expected=1)
        self.run_script("install.sh", "--make-default-shell", "--keep-default-shell", expected=1)
        self.run_script("install.sh", "--shell", "fish", expected=1)
        self.assertEqual(self.snapshot(), {})

    def test_missing_zsh_fails_before_any_writes_even_in_dry_run(self):
        (self.tools / "dirname").symlink_to(shutil.which("dirname"))
        self.env["PATH"] = str(self.tools)  # No Zsh; Bash itself is invoked by absolute path.
        for args in [(), ("--dry-run",)]:
            result = self.install(*args, expected=1)
            self.assertIn("Zsh must already be installed", result.stderr)
            self.assertEqual(self.snapshot(), {})
            self.assertEqual(list(self.tmp.iterdir()), [])
            self.assertFalse(self.log.exists())

    def test_noninteractive_install_requires_a_shell_choice(self):
        self.account.write_text(BASH + "\n")
        self.env["SHELL"] = ZSH  # Must not be mistaken for the account record.
        result = self.install(expected=1)
        self.assertIn("--keep-default-shell", result.stderr)
        self.assertEqual(self.snapshot(), {})
        self.assertFalse(self.log.exists())

    def test_keep_default_shell_does_not_require_account_lookup(self):
        self.shim("getent", "exit 1")
        self.install("--keep-default-shell")
        self.assertTrue((self.home / ".zshrc").exists())
        self.assertFalse(self.log.exists())

    def test_missing_chsh_is_reported_before_writes(self):
        self.account.write_text(BASH + "\n")
        (self.tools / "chsh").unlink()
        for name in ["dirname", "zsh", "id", "awk", "date", "cat"]:
            (self.tools / name).symlink_to(shutil.which(name))
        self.env["PATH"] = str(self.tools)
        result = self.install("--make-default-shell", expected=1)
        self.assertIn("Required command not found: chsh", result.stderr)
        self.assertEqual(self.snapshot(), {})
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_mac_account_lookup_preserves_shell_path_with_spaces(self):
        self.env["MOCK_OS"] = "Darwin"
        other = self.base / "another zsh installation" / "zsh"
        other.parent.mkdir()
        other.symlink_to(ZSH)
        self.account.write_text(str(other) + "\n")
        self.install("--make-default-shell")
        self.assertFalse(self.log.exists())

    def test_default_shell_change_is_last_and_restore_is_file_only(self):
        self.account.write_text(BASH + "\n")
        self.shim("chsh", '''test -f "$HOME/.zshrc" || exit 90
printf "chsh\\n" >> "$MOCK_LOG"
printf "%s\\n" "$2" > "$MOCK_ACCOUNT"''')
        self.install("--make-default-shell")
        backup = self.backups()[0]
        self.assertTrue(os.path.samefile(self.account.read_text().strip(), ZSH))
        self.assertEqual((backup / "previous-shell").read_text().strip(), BASH)
        restored = self.run_script("restore.sh", backup)
        self.assertIn("To switch back manually: chsh", restored.stdout)
        self.assertTrue(os.path.samefile(self.account.read_text().strip(), ZSH))
        self.assertEqual(self.log.read_text().count("chsh"), 1)

    def test_shell_only_backup_can_be_used_without_a_file_manifest(self):
        self.install()
        self.account.write_text(BASH + "\n")
        self.install("--make-default-shell")
        backup = next(p for p in self.backups() if (p / "previous-shell").exists())
        self.assertFalse((backup / "manifest.tsv").exists())
        result = self.run_script("restore.sh", backup)
        self.assertIn("Login shell was not restored", result.stdout)

    def test_already_default_zsh_is_not_changed_even_at_another_path(self):
        other = self.base / "another zsh installation" / "zsh"
        other.parent.mkdir()
        other.symlink_to(ZSH)
        self.account.write_text(str(other) + "\n")
        self.env["SHELL"] = BASH
        self.install("--make-default-shell")
        self.assertFalse(self.log.exists())
        self.assertFalse((self.backups()[0] / "previous-shell").exists())

    def test_shell_change_dry_run_never_prompts_or_changes_account(self):
        self.account.write_text(BASH + "\n")
        for args in [(), ("--make-default-shell",)]:
            self.install("--dry-run", *args)
            self.assertEqual(self.account.read_text().strip(), BASH)
            self.assertEqual(self.snapshot(), {})
            self.assertFalse(self.log.exists())

    def test_failed_or_unverified_shell_change_reports_failure_and_keeps_config(self):
        self.account.write_text(BASH + "\n")
        for status in [1, 0]:
            with self.subTest(status=status):
                self.shim("chsh", f"exit {status}")  # Success without an account update isn't success.
                result = self.install("--make-default-shell", expected=1)
                self.assertIn("Installed configuration was kept", result.stderr)
                self.assertIn("Private backups:", result.stdout)
                self.assertTrue((self.home / ".zshrc").exists())
                self.assertEqual(self.account.read_text().strip(), BASH)

    def test_interactive_shell_prompt_defaults_to_no_and_accepts_yes(self):
        self.account.write_text(BASH + "\n")
        for answer in ["", "yes"]:
            master, slave = pty.openpty()
            try:
                process = subprocess.Popen(
                    [BASH, str(self.repo / "install.sh"), "--config-only"],
                    stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    env=self.env, text=True,
                )
                os.write(master, (answer + "\n").encode())
                stdout, stderr = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 0, stdout + stderr)
                self.assertIn("[y/N]", stdout)
            finally:
                os.close(master)
                os.close(slave)
            self.assertTrue(os.path.samefile(self.account.read_text().strip(), ZSH if answer else BASH))
            self.assertEqual(self.log.exists(), bool(answer))

    def test_dry_run_is_offline_and_writes_nothing(self):
        result = self.run_script("install.sh", "--dry-run", "--reinstall-tools")
        self.assertIn("Would install starship", result.stdout)
        self.assertIn("Would install zoxide", result.stdout)
        self.assertIn("Would install fzf-tab 1.3.0", result.stdout)
        self.assertIn("Nothing was changed or downloaded", result.stdout)
        self.assertEqual(self.snapshot(), {})
        self.assertFalse(self.log.exists())
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_config_only_installs_all_shared_files(self):
        self.install()
        for name in [".zshrc", ".config/portable-terminal/shell/zsh.zsh", ".config/yazi/theme.toml", ".local/bin/terminal-doctor",
                     ".config/portable-terminal/plugins/zsh-syntax-highlighting/highlighters/main/main-highlighter.zsh",
                     ".config/portable-terminal/plugins/fzf-tab/fzf-tab.zsh",
                     ".config/portable-terminal/plugins/fzf-tab/LICENSE",
                     ".config/portable-terminal/plugins/fzf-tab/lib/-ftb-preview.tpl",
                     ".config/portable-terminal/plugins/fzf-tab/lib/zsh-ls-colors/ls-colors.zsh",
                     ".config/portable-terminal/plugins/fzf-tab/lib/zsh-ls-colors/LICENSE"]:
            self.assertTrue((self.home / name).is_file(), name)
        for name in [".bashrc", ".bash_profile", ".bash_login", ".profile"]:
            self.assertFalse((self.home / name).exists(), name)
        self.assertFalse((self.home / ".config/starship.toml").exists())
        self.assertEqual((self.home / ".config/portable-terminal/starship.toml").read_bytes(), (ROOT / "config/starship.toml").read_bytes())
        self.assertTrue(os.access(self.home / ".local/bin/terminal-doctor", os.X_OK))
        helper = self.home / ".config/portable-terminal/plugins/fzf-tab/lib/-ftb-fzf"
        self.assertEqual(stat.S_IMODE(helper.stat().st_mode), 0o700)

    def test_install_is_idempotent(self):
        self.install()
        before = self.snapshot()
        before_backups = self.backups()
        self.install()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.backups(), before_backups)
        self.assertEqual((self.home / ".zshrc").read_text().count("# >>> portable-terminal >>>"), 1)

    def test_legacy_bash_hooks_are_removed_without_deleting_dotfiles_and_can_be_restored(self):
        content = "# keep this\n# >>> portable-terminal >>>\nexit 99\n# <<< portable-terminal <<<\n# keep that\n"
        for name in [".bashrc", ".bash_profile", ".bash_login", ".profile"]:
            (self.home / name).write_text(content)
        self.install()
        backup = self.backups()[0]
        for name in [".bashrc", ".bash_profile", ".bash_login", ".profile"]:
            self.assertEqual((self.home / name).read_text(), "# keep this\n# keep that\n")
        self.install()
        self.assertEqual(len(self.backups()), 1)
        self.run_script("restore.sh", backup)
        for name in [".bashrc", ".bash_profile", ".bash_login", ".profile"]:
            self.assertEqual((self.home / name).read_text(), content)

    def test_legacy_bash_symlink_and_malformed_markers_remain_protected(self):
        original = self.home / "original bashrc"
        original.write_text("# >>> portable-terminal >>>\nold hook\n# <<< portable-terminal <<<\n")
        startup = self.home / ".bashrc"
        startup.symlink_to(original)
        self.install()
        self.assertEqual(startup.read_text(), "")
        self.assertIn("old hook", original.read_text())
        self.run_script("restore.sh", self.backups()[0])
        self.assertTrue(startup.is_symlink())
        original.write_text("# >>> portable-terminal >>>\nunclosed\n")
        self.install(expected=1)
        self.assertEqual(original.read_text(), "# >>> portable-terminal >>>\nunclosed\n")

    def test_preserves_user_content_without_sourcing_or_printing_it(self):
        content = "# pretend credential: test-only-not-a-real-secret\nexit 99\n"
        for name in [".bashrc", ".zshrc"]:
            (self.home / name).write_text(content)
        result = self.install()
        self.assertNotIn("test-only-not-a-real-secret", result.stdout + result.stderr)
        for name in [".bashrc", ".zshrc"]:
            self.assertTrue((self.home / name).read_text().startswith(content))
        self.assertEqual(stat.S_IMODE(self.backups()[0].stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.backups()[0] / "files").stat().st_mode), 0o700)

    def test_does_not_mask_existing_bash_login_file(self):
        (self.home / ".bash_login").write_text("export KEEP_ME=yes\n")
        self.install()
        self.assertFalse((self.home / ".bash_profile").exists())
        self.assertIn("KEEP_ME", (self.home / ".bash_login").read_text())
        self.assertNotIn("portable-terminal", (self.home / ".bash_login").read_text())

    def test_unmanaged_profile_is_untouched(self):
        (self.home / ".profile").write_text("export KEEP_ME=yes\n")
        self.install()
        self.assertFalse((self.home / ".bash_profile").exists())
        self.assertEqual((self.home / ".profile").read_text(), "export KEEP_ME=yes\n")

    def test_custom_xdg_zdotdir_and_yazi_paths(self):
        self.env.update(
            XDG_CONFIG_HOME=str(self.home / "settings"),
            XDG_STATE_HOME=str(self.home / "state"),
            ZDOTDIR=str(self.home / "zsh"),
            YAZI_CONFIG_HOME=str(self.home / "yazi"),
        )
        self.install()
        self.assertTrue((self.home / "settings/portable-terminal/starship.toml").exists())
        self.assertTrue((self.home / "zsh/.zshrc").exists())
        self.assertTrue((self.home / "yazi/theme.toml").exists())
        self.assertFalse((self.home / ".zshrc").exists())

    def test_rejects_relative_xdg_paths_before_writes(self):
        self.env["XDG_CONFIG_HOME"] = "relative/path"
        self.install(expected=1)
        self.assertEqual(self.snapshot(), {})

    def test_rejects_unclosed_managed_marker(self):
        content = "# >>> portable-terminal >>>\nimportant user content\n"
        (self.home / ".zshrc").write_text(content)
        self.install(expected=1)
        self.assertEqual((self.home / ".zshrc").read_text(), content)

    def test_rejects_duplicate_managed_markers(self):
        content = "# >>> portable-terminal >>>\n# <<< portable-terminal <<<\n" * 2
        (self.home / ".zshrc").write_text(content)
        self.install(expected=1)
        self.assertEqual((self.home / ".zshrc").read_text(), content)

    def test_updates_old_managed_block_without_duplicates(self):
        (self.home / ".zshrc").write_text("keep this\n# >>> portable-terminal >>>\nold hook\n# <<< portable-terminal <<<\nkeep that\n")
        self.install()
        content = (self.home / ".zshrc").read_text()
        self.assertIn("keep this\nkeep that\n", content)
        self.assertNotIn("old hook", content)
        self.assertEqual(content.count("# >>> portable-terminal >>>"), 1)

    def test_symlink_is_backed_up_without_changing_its_target(self):
        original = self.home / "original rc"
        original.write_text("# original\n")
        startup = self.home / ".zshrc"
        startup.symlink_to(original)
        self.install()
        self.assertFalse(startup.is_symlink())
        self.assertEqual(original.read_text(), "# original\n")
        self.run_script("restore.sh", self.backups()[0])
        self.assertTrue(startup.is_symlink())
        self.assertEqual(os.readlink(startup), str(original))

    def test_opt_out_flags_leave_unselected_components_alone(self):
        self.install("--no-terminals", "--no-yazi")
        for name in [".bashrc", ".bash_profile", ".config/kitty", ".config/yazi"]:
            self.assertFalse((self.home / name).exists(), name)
        self.assertTrue((self.home / ".zshrc").exists())

    def test_restores_originals_and_removes_new_files(self):
        original = "# keep my config\n"
        (self.home / ".zshrc").write_text(original)
        self.install()
        self.run_script("restore.sh", self.backups()[0])
        self.assertEqual((self.home / ".zshrc").read_text(), original)
        self.assertFalse((self.home / ".config/portable-terminal/shell/zsh.zsh").exists())
        self.assertFalse((self.home / ".config/portable-terminal/plugins/fzf-tab/fzf-tab.zsh").exists())
        self.assertFalse((self.home / ".local/bin/terminal-doctor").exists())

    def test_restore_preserves_later_edits_unless_forced(self):
        startup = self.home / ".zshrc"
        startup.write_text("# original\n")
        self.install()
        startup.write_text("# edited after installation\n")
        backup = self.backups()[0]
        self.run_script("restore.sh", backup, expected=2)
        self.assertEqual(startup.read_text(), "# edited after installation\n")
        self.run_script("restore.sh", "--force", backup)
        self.assertEqual(startup.read_text(), "# original\n")

    def test_restore_dry_run_doesnt_write_or_refresh_fonts(self):
        self.install()
        before = self.snapshot()
        self.run_script("restore.sh", "--dry-run", self.backups()[0])
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.log.exists())

    def test_mac_profiles_have_the_same_font_and_colors(self):
        self.env["MOCK_OS"] = "Darwin"
        self.env["MOCK_ARCH"] = "arm64"
        preview = self.run_script("install.sh", "--dry-run", "--no-tools")
        self.assertIn(f"in {self.home}/Library/Fonts; SHA256", preview.stdout)
        self.install()
        dynamic = self.home / "Library/Application Support/iTerm2/DynamicProfiles/portable-terminal.json"
        profile = json.loads(dynamic.read_text())["Profiles"][0]
        self.assertEqual(profile["Normal Font"], "JetBrainsMonoNFM-Regular 12")
        self.assertAlmostEqual(profile["Background Color"]["Blue Component"], 46 / 255)
        terminal = plistlib.loads((self.home / ".config/portable-terminal/profiles/Portable-Mocha.terminal").read_bytes())
        archive = plistlib.loads(terminal["Font"])
        font = archive["$objects"][1]
        self.assertEqual(archive["$objects"][font["NSName"].data], "JetBrainsMonoNFM-Regular")
        self.assertEqual(font["NSSize"], 12)
        self.assertFalse(self.log.exists())

    def test_terminal_import_is_explicit(self):
        self.env["MOCK_OS"] = "Darwin"
        self.shim("open", 'printf "%s\\n" "$*" >> "$MOCK_LOG"')
        self.install("--import-terminal")
        self.assertIn("-a Terminal", self.log.read_text())
        self.assertIn("Portable-Mocha.terminal", self.log.read_text())

    def test_rejects_terminal_import_on_linux_or_when_disabled(self):
        self.install("--import-terminal", expected=1)
        self.assertEqual(self.snapshot(), {})
        self.env["MOCK_OS"] = "Darwin"
        self.install("--import-terminal", "--no-terminals", expected=1)
        self.assertEqual(self.snapshot(), {})

    def test_mac_tools_use_brew_not_linux_downloads(self):
        self.env["MOCK_OS"] = "Darwin"
        self.shim("brew", 'if [ "$1" = list ]; then exit 1; fi\nprintf "%s\\n" "$*" >> "$MOCK_LOG"')
        self.run_script("install.sh", "--no-fonts", "--reinstall-tools")
        calls = self.log.read_text()
        for formula in ["starship", "eza", "fzf", "bat", "fd", "ripgrep", "yazi", "zoxide"]:
            self.assertIn("install --formula " + formula, calls)

    def test_ptyxis_font_changes_have_restore_records(self):
        state = self.base / "settings.json"
        state.write_text(json.dumps({"use-system-font": "true", "font-name": "'Monospace 10'"}))
        self.env["MOCK_SETTINGS"] = str(state)
        shim = self.tools / "gsettings"
        shim.write_text(f"#!{sys.executable}\n" + textwrap.dedent('''\
            import json, os, pathlib, sys
            path = pathlib.Path(os.environ['MOCK_SETTINGS'])
            state = json.loads(path.read_text())
            args = sys.argv[1:]
            if args[0] == 'list-schemas': print('org.gnome.Ptyxis')
            elif args[0] == 'get': print(state[args[2]])
            elif args[0] == 'writable': print('true')
            elif args[0] == 'set':
                state[args[2]] = args[3]
                path.write_text(json.dumps(state))
        '''))
        shim.chmod(0o755)
        self.install("--ptyxis")
        self.assertEqual(json.loads(state.read_text())["font-name"], "'JetBrainsMono Nerd Font Mono 12'")
        self.run_script("restore.sh", self.backups()[0])
        self.assertEqual(json.loads(state.read_text()), {"use-system-font": "true", "font-name": "'Monospace 10'"})

    def test_download_is_verified_then_installed_and_cached(self):
        repo = self.copy_repo()
        self.fixture_download(repo)
        self.run_script("install.sh", "--no-fonts", "--reinstall-tools", root=repo)
        binary = self.home / ".local/bin/starship"
        self.assertTrue(binary.is_file())
        self.assertEqual(stat.S_IMODE(binary.stat().st_mode), 0o755)
        self.run_script("install.sh", "--no-fonts", "--reinstall-tools", root=repo)
        self.assertEqual(self.log.read_text().count("download"), 1)

    def test_zip_download_installs_yazi_and_companion(self):
        repo = self.copy_repo()
        self.fixture_download(repo, zip_archive=True)
        self.run_script("install.sh", "--no-fonts", "--reinstall-tools", root=repo)
        self.assertTrue((self.home / ".local/bin/yazi").is_file())
        self.assertTrue((self.home / ".local/bin/ya").is_file())

    def test_zoxide_download_is_installed_and_existing_command_is_kept(self):
        self.fixture_download(self.repo, tool="zoxide")
        self.shim("zoxide", 'exit 0')
        result = self.run_script("install.sh", "--no-fonts")
        self.assertIn("Keeping existing: zoxide", result.stdout)
        binary = self.home / ".local/bin/zoxide"
        self.assertFalse(binary.exists())
        self.run_script("install.sh", "--no-fonts", "--reinstall-tools")
        self.assertTrue(binary.is_file())
        self.assertEqual(stat.S_IMODE(binary.stat().st_mode), 0o755)
        self.assertEqual(self.log.read_text().count("download"), 1)

    def test_bad_download_checksum_is_rejected_before_dotfile_changes(self):
        repo = self.copy_repo()
        self.fixture_download(repo, checksum="0" * 64)
        result = self.run_script("install.sh", "--no-fonts", "--reinstall-tools", root=repo, expected=1)
        self.assertIn("SHA256 verification failed", result.stderr)
        self.assertFalse((self.home / ".zshrc").exists())
        self.assertFalse((self.home / ".local/bin/starship").exists())

    def test_invalid_cached_checksum_is_rejected(self):
        repo = self.copy_repo()
        archive = self.fixture_download(repo)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        cache = self.home / ".cache/portable-terminal" / f"{digest}-{archive.name}"
        cache.parent.mkdir(parents=True)
        cache.write_text("tampered cache")
        result = self.run_script("install.sh", "--no-fonts", "--reinstall-tools", root=repo, expected=1)
        self.assertIn("wrong SHA256", result.stderr)
        self.assertFalse((self.home / ".zshrc").exists())
        self.assertFalse(self.log.exists())

    def test_highlighting_checksum_is_checked_and_cached_downloads_are_offline(self):
        packages = self.repo / "lib/packages.sh"
        good = packages.read_text()
        packages.write_text(re.sub(r"(?m)^ZSH_HIGHLIGHT_SHA256=.*$", "ZSH_HIGHLIGHT_SHA256=" + "0" * 64, good))
        result = self.install(expected=1)
        self.assertIn("SHA256 verification failed", result.stderr)
        self.assertFalse((self.home / ".zshrc").exists())
        packages.write_text(good)
        self.install()
        self.shim("curl", "exit 98")  # A repeat config-only install must use the verified cache.
        self.install()
        cached = next((self.home / ".cache/portable-terminal").glob("*0.8.0.tar.gz"))
        cached.write_text("tampered")
        result = self.install(expected=1)
        self.assertIn("wrong SHA256", result.stderr)

    def test_fzf_tab_checksum_is_checked_and_cached_downloads_are_offline(self):
        packages = self.repo / "lib/packages.sh"
        good = packages.read_text()
        packages.write_text(re.sub(r"(?m)^FZF_TAB_SHA256=.*$", "FZF_TAB_SHA256=" + "0" * 64, good))
        result = self.install(expected=1)
        self.assertIn("SHA256 verification failed", result.stderr)
        self.assertFalse((self.home / ".zshrc").exists())
        self.assertFalse((self.home / ".config/portable-terminal/plugins/fzf-tab/fzf-tab.zsh").exists())
        packages.write_text(good)
        self.install()
        self.shim("curl", "exit 98")
        self.install()
        cached = next((self.home / ".cache/portable-terminal").glob("*v1.3.0.tar.gz"))
        cached.write_text("tampered")
        result = self.install(expected=1)
        self.assertIn("wrong SHA256", result.stderr)

    def test_noninteractive_shell_config_does_nothing(self):
        self.install()
        result = subprocess.run(
            [ZSH, "-df", "-c", '. "$HOME/.config/portable-terminal/shell/zsh.zsh"; printf "%s" "${STARSHIP_CONFIG-unset}"'],
            env=self.env, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout, "unset")

    def test_dumb_terminal_does_not_load_configuration(self):
        self.install()
        self.env["TERM"] = "dumb"
        result = subprocess.run(
            [ZSH, "-d", "-ic", 'printf "%s" "${STARSHIP_CONFIG-unset}"'],
            env=self.env, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout, "unset")
        self.assertFalse((self.home / ".local/state/zsh").exists())

    def test_interactive_zsh_sets_prompt_and_aliases_once(self):
        self.install()
        self.env["STARSHIP_SHELL"] = "zsh"
        self.env["EDITOR"] = "vim"  # A nested shell must still use emacs editing.
        self.shim("starship", '''[ "$*" = "init zsh" ] || exit 90
cat <<'EOF'
prompt_starship_precmd() { :; }
export STARSHIP_SHELL=zsh
typeset -g TEST_STARSHIP_COUNT=$(( ${TEST_STARSHIP_COUNT:-0} + 1 ))
EOF''')
        self.shim("fzf", '''[ "$*" = "--zsh" ] || exit 90
cat <<'EOF'
export TEST_FZF_READY=yes
typeset -g TEST_FZF_COUNT=$(( ${TEST_FZF_COUNT:-0} + 1 ))
test-fzf-completion() { :; }
zle -N test-fzf-completion
bindkey '^I' test-fzf-completion
EOF''')
        self.shim("eza", 'exit 0')
        result = subprocess.run(
            [ZSH, "-d", "-i", "-c",
             '. "$HOME/.zshrc"; alias ll; bindkey -lL main; '
             'printf "PROMPT=%s FZF=%s EDITOR=%s COUNTS=%s/%s/%s/%s\\n" "$STARSHIP_SHELL" "$TEST_FZF_READY" "$EDITOR" '
             '"$TEST_STARSHIP_COUNT" "$TEST_FZF_COUNT" "$TEST_FZF_TAB_COUNT" "$TEST_HIGHLIGHT_COUNT"; '
             'bindkey "^I"; print TAB_ORDER=$TEST_FZF_TAB_AFTER_COMPINIT/$TEST_FZF_TAB_BEFORE_HIGHLIGHT; '
             'print -r -- "TAB_PREVIOUS=$TEST_FZF_TAB_PREVIOUS_WIDGET"; '
             'zstyle -L ":completion:*" menu; zstyle -L ":fzf-tab:*" use-fzf-default-opts; '
             'zstyle -L ":fzf-tab:*" fzf-pad; '
             '(( $+functions[compdef] )) && print COMPLETION=yes; '
             'print HISTORY=$HISTSIZE/$SAVEHIST/$options[incappendhistory]/$options[sharehistory]'],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("eza --long --all --git", result.stdout)
        self.assertIn("PROMPT=zsh FZF=yes EDITOR=vim", result.stdout)
        self.assertIn("COUNTS=1/1/1/1", result.stdout)
        self.assertIn("bindkey -A emacs main", result.stdout)
        self.assertIn('"^I" fzf-tab-complete', result.stdout)
        self.assertIn("TAB_ORDER=1/0", result.stdout)
        self.assertIn('TAB_PREVIOUS="^I" test-fzf-completion', result.stdout)
        self.assertIn("zstyle ':completion:*' menu no", result.stdout)
        self.assertIn("zstyle ':fzf-tab:*' use-fzf-default-opts yes", result.stdout)
        self.assertIn("zstyle ':fzf-tab:*' fzf-pad 4", result.stdout)
        self.assertIn("COMPLETION=yes", result.stdout)
        self.assertIn("HISTORY=50000/50000/on/off", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_without_fzf_keeps_native_tab_completion_and_does_not_require_aws(self):
        self.install()
        for name in ["mkdir", "mv", "rm"]:
            (self.tools / name).symlink_to(shutil.which(name))
        self.env["PATH"] = str(self.tools)
        result = subprocess.run(
            [ZSH, "-d", "-ic",
             'bindkey "^I"; print READY=$+functions[compdef]/$+functions[fzf-tab-complete]/$+functions[complete]'],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"^I" expand-or-complete', result.stdout)
        self.assertIn("READY=1/0/0", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_zoxide_initializes_once_after_completion_without_replacing_cd(self):
        self.install()
        self.shim("fzf", '[ "$*" = "--zsh" ] || exit 90')
        self.env["_ZO_DATA_DIR"] = str(self.home / "custom directory history")
        self.shim("zoxide", '''[ "$*" = "init zsh" ] || exit 90
cat <<'EOF'
typeset -g TEST_ZOXIDE_COUNT=$(( ${TEST_ZOXIDE_COUNT:-0} + 1 ))
typeset -g TEST_ZOXIDE_AFTER_COMPINIT=$+functions[compdef]
typeset -g TEST_ZOXIDE_BEFORE_HIGHLIGHT=$+functions[_zsh_highlight]
__zoxide_z() { :; }
z() { __zoxide_z "$@"; }
zi() { :; }
EOF''')
        result = subprocess.run(
            [ZSH, "-d", "-ic",
             '. "$HOME/.zshrc"; print LOADS=$TEST_ZOXIDE_COUNT; '
             'print ORDER=$TEST_ZOXIDE_AFTER_COMPINIT/$TEST_ZOXIDE_BEFORE_HIGHLIGHT; '
             'print COMMANDS=$+functions[z]/$+functions[zi]/$+functions[cd]/$+aliases[cd]; '
             'print -r -- "DATA=$_ZO_DATA_DIR"'],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("LOADS=1", result.stdout)
        self.assertIn("ORDER=1/0", result.stdout)
        self.assertIn("COMMANDS=1/1/0/0", result.stdout)
        self.assertIn("DATA=" + self.env["_ZO_DATA_DIR"], result.stdout)
        self.assertEqual(result.stderr, "")

    def test_existing_zoxide_integration_is_not_initialized_again(self):
        (self.home / ".zshrc").write_text("__zoxide_z() { :; }\nz() { print existing; }\n")
        self.install()
        self.shim("fzf", '[ "$*" = "--zsh" ] || exit 90')
        self.shim("zoxide", 'printf "unexpected zoxide init\\n" >&2; exit 90')
        result = subprocess.run(
            [ZSH, "-d", "-ic", 'z'],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "existing")
        self.assertEqual(result.stderr, "")

    def test_missing_fzf_tab_plugin_warns_without_breaking_shell_startup(self):
        self.install()
        (self.home / ".config/portable-terminal/plugins/fzf-tab/fzf-tab.zsh").unlink()
        self.shim("fzf", '[ "$*" = "--zsh" ] || exit 90')
        result = subprocess.run(
            [ZSH, "-d", "-ic", 'bindkey "^I"; print READY=$+functions[compdef]/$+functions[_zsh_highlight]'],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"^I" expand-or-complete', result.stdout)
        self.assertIn("READY=1/1", result.stdout)
        self.assertIn("searchable Tab completion is missing", result.stderr)

    def test_existing_fzf_tab_plugin_is_not_loaded_twice(self):
        (self.home / ".zshrc").write_text("fzf-tab-complete() { :; }\n")
        self.install()
        self.shim("fzf", '[ "$*" = "--zsh" ] || exit 90')
        result = subprocess.run(
            [ZSH, "-d", "-ic", 'print LOADS=${TEST_FZF_TAB_COUNT:-0}'],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("LOADS=0", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_aws_completer_is_registered_and_handles_paths_with_spaces_and_quotes(self):
        aws_tools = self.base / "AWS tools with 'quotes'"
        aws_tools.mkdir()
        completer = aws_tools / "aws_completer"
        completer.write_text("""#!/bin/sh
case "$COMP_LINE" in
    'aws s3 ') printf '%s\\n' cp ls sync ;;
    'aws s3 cp --') printf '%s\\n' --recursive --dryrun ;;
    *) exit 90 ;;
esac
""")
        completer.chmod(0o755)
        self.env["PATH"] = str(aws_tools) + os.pathsep + self.env["PATH"]
        self.shim("fzf", '[ "$*" = "--zsh" ] || exit 90')
        self.install()
        result = subprocess.run(
            [ZSH, "-d", "-ic", '''
                [[ ${_comps[aws]} == '_bash_complete -C '* ]] || exit 91
                compadd() { print -rl -- "$@"; }
                words=(aws s3 '') CURRENT=3 PREFIX='' QIPREFIX='' IPREFIX=''
                eval "${_comps[aws]}"
                words=(aws s3 cp --) CURRENT=4 PREFIX=--
                eval "${_comps[aws]}"
            '''],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for candidate in ["cp", "ls", "sync", "--recursive", "--dryrun"]:
            self.assertIn(candidate, result.stdout.splitlines())
        self.assertEqual(result.stderr, "")
        self.assertFalse((self.home / ".aws").exists())
        self.assertFalse((self.home / ".local/bin/aws").exists())
        self.assertFalse((self.home / ".local/bin/aws_completer").exists())

    def test_zsh_history_survives_sessions_without_importing_bash_history(self):
        self.install()
        (self.home / ".bash_history").write_text("old-bash-history-token\n")
        result = subprocess.run(
            [ZSH, "-d", "-i"], input="print -r -- saved-zsh-history-token\n print private-history-token\nexit\n",
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        history = self.home / ".local/state/zsh/history"
        self.assertIn("saved-zsh-history-token", history.read_text())
        self.assertNotIn("private-history-token", history.read_text())
        self.assertEqual(stat.S_IMODE(history.parent.stat().st_mode), 0o700)
        result = subprocess.run(
            [ZSH, "-d", "-i"], input="fc -l 1\nexit\n",
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertIn("saved-zsh-history-token", result.stdout)
        self.assertNotIn("old-bash-history-token", result.stdout)

    def test_existing_history_file_location_is_preserved(self):
        custom = self.home / "existing history"
        (self.home / ".zshrc").write_text('HISTFILE="$HOME/existing history"\n')
        self.install()
        result = subprocess.run(
            [ZSH, "-d", "-ic", 'print -r -- "$HISTFILE"'], env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.stdout.strip(), str(custom))

    def test_yazi_wrapper_preserves_arguments_exit_status_and_directory_change(self):
        self.install()
        target = self.home / "directory with 'quotes' and spaces"
        target.mkdir()
        self.env["MOCK_CWD"] = str(target)
        self.shim("yazi", '''printf "%s\\n" "$@" >> "$MOCK_LOG"
for arg do
    case "$arg" in --cwd-file=*) printf "%s" "$MOCK_CWD" > "${arg#--cwd-file=}" ;; esac
done
exit 7''')
        result = subprocess.run(
            [ZSH, "-d", "-ic", 'y "argument with spaces"; result=$?; print -r -- "PWD=$PWD"; print RESULT=$result'],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PWD=" + str(target), result.stdout)
        self.assertIn("RESULT=7", result.stdout)
        self.assertIn("argument with spaces", self.log.read_text())
        self.assertEqual(list(self.tmp.glob("yazi-cwd.*")), [])
        self.env["MOCK_CWD"] = ""  # Yazi's Q behavior.
        result = subprocess.run(
            [ZSH, "-d", "-ic", 'before=$PWD; y; [[ $PWD == "$before" ]]'],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class RepositoryTests(unittest.TestCase):
    def test_configuration_files_parse(self):
        for name in ["config/starship.toml", "config/yazi/theme.toml"]:
            tomllib.loads((ROOT / name).read_text())
        json.loads((ROOT / "profiles/portable-terminal.json").read_text())
        plistlib.loads((ROOT / "profiles/Portable-Mocha.terminal").read_bytes())

    def test_linux_lock_has_both_architectures_and_valid_sha256s(self):
        rows = [line.split("|") for line in (ROOT / "packages.lock").read_text().splitlines() if line and not line.startswith("#")]
        self.assertEqual(len(rows), 16)
        for row in rows:
            self.assertEqual(len(row), 5)
            name, arch, digest, url, binaries = row
            self.assertIn(arch, {"x86_64", "aarch64"})
            self.assertRegex(digest, r"^[a-f0-9]{64}$")
            self.assertTrue(url.startswith("https://github.com/"))
            self.assertTrue(binaries)
        self.assertEqual(len({(row[0], row[1]) for row in rows}), len(rows))
        self.assertEqual({row[1] for row in rows if row[0] == "zoxide"}, {"x86_64", "aarch64"})

    def test_generated_profiles_are_reproducible(self):
        paths = [ROOT / "profiles/portable-terminal.json", ROOT / "profiles/Portable-Mocha.terminal"]
        before = [p.read_bytes() for p in paths]
        subprocess.run([sys.executable, str(ROOT / "scripts/generate-profiles.py"), "--check"], check=True)
        self.assertEqual([p.read_bytes() for p in paths], before)

    def test_shell_scripts_parse(self):
        for script in ["install.sh", "restore.sh", "lib/common.sh", "lib/packages.sh", "scripts/check.sh", "bin/terminal-doctor"]:
            subprocess.run([BASH, "-n", str(ROOT / script)], check=True)
        subprocess.run([ZSH, "-n", str(ROOT / "config/shell/zsh.zsh")], check=True)


if __name__ == "__main__":
    unittest.main()
