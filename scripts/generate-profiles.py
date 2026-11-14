#!/usr/bin/env python3
"""Generate committed macOS profiles. Dev-only: requires Python 3.11+."""

import argparse
import json
from pathlib import Path
import plistlib
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PALETTE = tomllib.loads((ROOT / "config/starship.toml").read_text())["palettes"][
    "catppuccin_mocha"
]
FONT = "JetBrainsMonoNFM-Regular"
NAME = "Portable Terminal - Mocha"


def components(hex_color):
    return tuple(int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5))


def archived(objects):
    return plistlib.dumps(
        {
            "$archiver": "NSKeyedArchiver",
            "$version": 100000,
            "$top": {"root": plistlib.UID(1)},
            "$objects": objects,
        },
        fmt=plistlib.FMT_BINARY,
    )


def terminal_color(hex_color):
    # Same keyed NSColor archive structure as catppuccin/Terminal.app.
    rgb = " ".join(f"{value:.10f}" for value in components(hex_color))
    return archived(
        [
            "$null",
            {"NSRGB": rgb.encode() + b"\0", "NSColorSpace": 1, "$class": plistlib.UID(2)},
            {"$classes": ["NSColor", "NSObject"], "$classname": "NSColor"},
        ]
    )


def iterm_color(hex_color):
    red, green, blue = components(hex_color)
    return {
        "Red Component": red,
        "Green Component": green,
        "Blue Component": blue,
        "Alpha Component": 1.0,
        "Color Space": "sRGB",
    }


def generate(check=False):
    # Follow the existing Kitty palette exactly, including the bright colors.
    ansi = [
        "surface1", "red", "green", "yellow", "blue", "pink", "teal", "subtext1",
        "surface2", "red", "green", "yellow", "blue", "pink", "teal", "subtext0",
    ]
    profile = {
        "Name": NAME,
        "Guid": "f8e5ca1e-39aa-4d2b-bab0-b8bba78a4d10",
        "Normal Font": f"{FONT} 12",
        "Non Ascii Font": f"{FONT} 12",
        "Use Non-ASCII Font": False,
        "Use Ligatures": True,
        "Custom Command": "No",
        "Command": "",
        "Initial Text": "",
        "Terminal Type": "xterm-256color",
        "Scrollback Lines": 10000,
        "Unlimited Scrollback": False,
        "Silence Bell": True,
        "Blinking Cursor": False,
        "Cursor Type": 1,
        "Option Key Sends": 2,
    }
    for index, key in enumerate(ansi):
        profile[f"Ansi {index} Color"] = iterm_color(PALETTE[key])
    for label, key in {
        "Background Color": "base",
        "Foreground Color": "text",
        "Bold Color": "text",
        "Cursor Color": "rosewater",
        "Cursor Text Color": "base",
        "Selection Color": "rosewater",
        "Selected Text Color": "base",
    }.items():
        profile[label] = iterm_color(PALETTE[key])

    terminal = {
        "name": NAME,
        "type": "Window Settings",
        "ProfileCurrentVersion": 2.04,
        "DisableANSIColor": False,
        "Bell": False,
        "CursorBlink": False,
        "ScrollbackLines": 10000,
        "useOptionAsMetaKey": True,
        "Font": archived(
            [
                "$null",
                {"NSName": plistlib.UID(2), "NSSize": 12.0, "NSfFlags": 16, "$class": plistlib.UID(3)},
                FONT,
                {"$classes": ["NSFont", "NSObject"], "$classname": "NSFont"},
            ]
        ),
    }
    color_names = ["Black", "Red", "Green", "Yellow", "Blue", "Magenta", "Cyan", "White"]
    for index, key in enumerate(ansi):
        label = "ANSI" + ("Bright" if index >= 8 else "") + color_names[index % 8] + "Color"
        terminal[label] = terminal_color(PALETTE[key])
    for label, key in {
        "BackgroundColor": "base",
        "TextColor": "text",
        "BoldTextColor": "text",
        "CursorColor": "rosewater",
        "SelectionColor": "rosewater",
    }.items():
        terminal[label] = terminal_color(PALETTE[key])

    directory = ROOT / "profiles"
    outputs = {
        directory / "portable-terminal.json": (json.dumps({"Profiles": [profile]}, indent=2) + "\n").encode(),
        directory / "Portable-Mocha.terminal": plistlib.dumps(terminal),
    }
    if check:
        for path, content in outputs.items():
            if not path.exists() or path.read_bytes() != content:
                raise SystemExit(f"Outdated generated profile: {path.name}. Run scripts/generate-profiles.py.")
    else:
        directory.mkdir(exist_ok=True)
        for path, content in outputs.items():
            path.write_bytes(content)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check committed profiles without writing files")
    generate(parser.parse_args().check)
