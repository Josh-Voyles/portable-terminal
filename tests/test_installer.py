"""Offline installer/restore tests. Every install uses an isolated HOME."""

import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
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
        # Tests never touch the host's font caches or fetch anything from GitHub.
        self.shim("fc-cache", 'printf "fc-cache\\n" >> "$MOCK_LOG"')
        self.shim("curl", 'printf "unexpected curl\\n" >&2; exit 98')
        self.shim("uname", 'case "$1" in -s) echo "${MOCK_OS:-Linux}" ;; -m) echo "${MOCK_ARCH:-x86_64}" ;; esac')

    def shim(self, name, body):
        path = self.tools / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def run_script(self, script, *args, root=ROOT, expected=0):
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
        target = self.base / "checkout with spaces"
        shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        return target

    def fixture_download(self, repo, *, zip_archive=False, checksum=None):
        archive = self.base / ("asset.zip" if zip_archive else "asset.tar.gz")
        payload = b"#!/bin/sh\nprintf 'fixture tool\\n'\n"
        if zip_archive:
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("release/yazi", payload)
                bundle.writestr("release/ya", payload)
            tool, binaries = "yazi", "yazi ya"
        else:
            with tarfile.open(archive, "w:gz") as bundle:
                entry = tarfile.TarInfo("release/starship")
                entry.size = len(payload)
                entry.mode = 0o755
                bundle.addfile(entry, io.BytesIO(payload))
            tool, binaries = "starship", "starship"
        digest = checksum or hashlib.sha256(archive.read_bytes()).hexdigest()
        (repo / "packages.lock").write_text(
            f"{tool}|x86_64|{digest}|https://example.invalid/{archive.name}|{binaries}\n"
        )
        self.env["MOCK_DOWNLOAD"] = str(archive)
        self.shim("curl", 'printf "download\\n" >> "$MOCK_LOG"\nwhile [ "$1" != --output ]; do shift; done\ncp "$MOCK_DOWNLOAD" "$2"')
        return archive

    def test_help_and_invalid_options_dont_write(self):
        self.run_script("install.sh", "--help")
        self.assertEqual(self.snapshot(), {})
        self.run_script("install.sh", "--not-an-option", expected=1)
        self.run_script("install.sh", "--shell", expected=1)
        self.run_script("install.sh", "--shell", "fish", expected=1)
        self.assertEqual(self.snapshot(), {})

    def test_dry_run_is_offline_and_writes_nothing(self):
        result = self.run_script("install.sh", "--dry-run", "--reinstall-tools")
        self.assertIn("Would install starship", result.stdout)
        self.assertIn("Nothing was changed or downloaded", result.stdout)
        self.assertEqual(self.snapshot(), {})
        self.assertFalse(self.log.exists())
        self.assertEqual(list(self.tmp.iterdir()), [])

    def test_config_only_installs_all_shared_files(self):
        self.install()
        for name in [".bashrc", ".bash_profile", ".zshrc", ".config/yazi/theme.toml", ".local/bin/terminal-doctor"]:
            self.assertTrue((self.home / name).is_file(), name)
        self.assertFalse((self.home / ".config/starship.toml").exists())
        self.assertEqual((self.home / ".config/portable-terminal/starship.toml").read_bytes(), (ROOT / "config/starship.toml").read_bytes())
        self.assertTrue(os.access(self.home / ".local/bin/terminal-doctor", os.X_OK))

    def test_install_is_idempotent(self):
        self.install()
        before = self.snapshot()
        before_backups = self.backups()
        self.install()
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.backups(), before_backups)
        self.assertEqual((self.home / ".bashrc").read_text().count("# >>> portable-terminal >>>"), 1)

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
        self.assertIn("portable-terminal", (self.home / ".bash_login").read_text())

    def test_profile_is_guarded_for_non_bash_shells(self):
        (self.home / ".profile").write_text("export KEEP_ME=yes\n")
        self.install()
        self.assertFalse((self.home / ".bash_profile").exists())
        self.assertIn('"${BASH_VERSION-}"', (self.home / ".profile").read_text())

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
        (self.home / ".bashrc").write_text(content)
        self.install(expected=1)
        self.assertEqual((self.home / ".bashrc").read_text(), content)

    def test_rejects_duplicate_managed_markers(self):
        content = "# >>> portable-terminal >>>\n# <<< portable-terminal <<<\n" * 2
        (self.home / ".bashrc").write_text(content)
        self.install(expected=1)
        self.assertEqual((self.home / ".bashrc").read_text(), content)

    def test_updates_old_managed_block_without_duplicates(self):
        (self.home / ".bashrc").write_text("keep this\n# >>> portable-terminal >>>\nold hook\n# <<< portable-terminal <<<\nkeep that\n")
        self.install()
        content = (self.home / ".bashrc").read_text()
        self.assertIn("keep this\nkeep that\n", content)
        self.assertNotIn("old hook", content)
        self.assertEqual(content.count("# >>> portable-terminal >>>"), 1)

    def test_symlink_is_backed_up_without_changing_its_target(self):
        original = self.home / "original rc"
        original.write_text("# original\n")
        startup = self.home / ".bashrc"
        startup.symlink_to(original)
        self.install()
        self.assertFalse(startup.is_symlink())
        self.assertEqual(original.read_text(), "# original\n")
        self.run_script("restore.sh", self.backups()[0])
        self.assertTrue(startup.is_symlink())
        self.assertEqual(os.readlink(startup), str(original))

    def test_opt_out_flags_leave_unselected_components_alone(self):
        self.install("--shell", "none", "--no-terminals", "--no-yazi")
        for name in [".bashrc", ".bash_profile", ".zshrc", ".config/kitty", ".config/yazi"]:
            self.assertFalse((self.home / name).exists(), name)

    def test_restores_originals_and_removes_new_files(self):
        original = "# keep my config\n"
        (self.home / ".bashrc").write_text(original)
        self.install()
        self.run_script("restore.sh", self.backups()[0])
        self.assertEqual((self.home / ".bashrc").read_text(), original)
        self.assertFalse((self.home / ".zshrc").exists())
        self.assertFalse((self.home / ".local/bin/terminal-doctor").exists())

    def test_restore_preserves_later_edits_unless_forced(self):
        startup = self.home / ".bashrc"
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
        for formula in ["starship", "eza", "fzf", "bat", "fd", "ripgrep", "yazi"]:
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

    def test_bad_download_checksum_is_rejected_before_dotfile_changes(self):
        repo = self.copy_repo()
        self.fixture_download(repo, checksum="0" * 64)
        result = self.run_script("install.sh", "--no-fonts", "--reinstall-tools", root=repo, expected=1)
        self.assertIn("SHA256 verification failed", result.stderr)
        self.assertFalse((self.home / ".bashrc").exists())
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
        self.assertFalse((self.home / ".bashrc").exists())
        self.assertFalse(self.log.exists())

    def test_noninteractive_shell_config_does_nothing(self):
        self.install()
        result = subprocess.run(
            [BASH, "--noprofile", "--norc", "-c", '. "$HOME/.config/portable-terminal/shell/bash.sh"; printf "%s" "${STARSHIP_CONFIG-unset}"'],
            env=self.env, capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout, "unset")

    def test_interactive_bash_sets_prompt_and_aliases_once(self):
        self.install()
        self.env["STARSHIP_SHELL"] = "bash"  # inherited from a parent shell
        self.shim("starship", 'printf "export STARSHIP_SHELL=bash\\n"')
        self.shim("fzf", 'printf "export TEST_FZF_READY=yes\\n"')
        self.shim("eza", 'exit 0')
        result = subprocess.run(
            [BASH, "--noprofile", "--rcfile", str(self.home / ".bashrc"), "-ic",
             '. "$HOME/.bashrc"; alias ll; printf "PROMPT=%s FZF=%s EDITOR=%s\\n" "$STARSHIP_SHELL" "$TEST_FZF_READY" "$EDITOR"'],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("eza --long --all --git", result.stdout)
        self.assertIn("PROMPT=bash FZF=yes EDITOR=vim", result.stdout)

    @unittest.skipUnless(shutil.which("zsh"), "Zsh is not installed")
    def test_interactive_zsh_sets_prompt_and_aliases_once(self):
        self.install()
        self.env["STARSHIP_SHELL"] = "zsh"
        self.shim("starship", 'printf "export STARSHIP_SHELL=zsh\\n"')
        self.shim("fzf", 'printf "export TEST_FZF_READY=yes\\n"')
        self.shim("eza", 'exit 0')
        result = subprocess.run(
            [shutil.which("zsh"), "-d", "-i", "-c",
             '. "$HOME/.zshrc"; alias ll; printf "PROMPT=%s FZF=%s EDITOR=%s\\n" "$STARSHIP_SHELL" "$TEST_FZF_READY" "$EDITOR"'],
            env=self.env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("eza --long --all --git", result.stdout)
        self.assertIn("PROMPT=zsh FZF=yes EDITOR=vim", result.stdout)


class RepositoryTests(unittest.TestCase):
    def test_configuration_files_parse(self):
        for name in ["config/starship.toml", "config/yazi/theme.toml"]:
            tomllib.loads((ROOT / name).read_text())
        json.loads((ROOT / "profiles/portable-terminal.json").read_text())
        plistlib.loads((ROOT / "profiles/Portable-Mocha.terminal").read_bytes())

    def test_linux_lock_has_both_architectures_and_valid_sha256s(self):
        rows = [line.split("|") for line in (ROOT / "packages.lock").read_text().splitlines() if line and not line.startswith("#")]
        self.assertEqual(len(rows), 14)
        for row in rows:
            self.assertEqual(len(row), 5)
            name, arch, digest, url, binaries = row
            self.assertIn(arch, {"x86_64", "aarch64"})
            self.assertRegex(digest, r"^[a-f0-9]{64}$")
            self.assertTrue(url.startswith("https://github.com/"))
            self.assertTrue(binaries)
        self.assertEqual(len({(row[0], row[1]) for row in rows}), len(rows))

    def test_generated_profiles_are_reproducible(self):
        paths = [ROOT / "profiles/portable-terminal.json", ROOT / "profiles/Portable-Mocha.terminal"]
        before = [p.read_bytes() for p in paths]
        subprocess.run([sys.executable, str(ROOT / "scripts/generate-profiles.py"), "--check"], check=True)
        self.assertEqual([p.read_bytes() for p in paths], before)

    def test_shell_scripts_parse(self):
        for script in ["install.sh", "restore.sh", "lib/common.sh", "lib/packages.sh", "config/shell/common.sh", "config/shell/bash.sh", "bin/terminal-doctor"]:
            subprocess.run([BASH, "-n", str(ROOT / script)], check=True)


if __name__ == "__main__":
    unittest.main()
