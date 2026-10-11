"""D-071: the sign-in (your browser's login), as cookies yt-dlp reads for itself.
D-078: for every site, not only YouTube.

The tool never reads, copies or stores a cookie. It names where they are, a
browser or a cookies.txt file, and yt-dlp reads them in this process for the
call (`cookiesfrombrowser`, `cookiefile`). config.toml keeps that name or path,
never the contents, and nothing a run writes mentions either.

Which one, in order: `fetch --cookies-from-browser` or `--cookies`; then
`sign_in` in config.toml (Settings → Sign-in; D-078, read under its old name
`youtube_cookies` too); then, in portable
mode, a `cookies.txt` in the data folder.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

#: config.toml's key: a browser name, or the path of a cookies.txt file.
CONFIG_KEY = "sign_in"
#: D-078: the key's name before the sign-in served every site; still read.
OLD_CONFIG_KEY = "youtube_cookies"

#: The browsers yt-dlp reads, Firefox first: it is the one that reliably works.
BROWSERS = ("firefox", "chrome", "edge", "brave", "chromium", "opera", "vivaldi", "safari", "whale")

#: Chromium browsers on Windows encrypt their cookies so that only the browser
#: itself can read them (and lock the file while open).
UNREADABLE_ON_WINDOWS = ("chrome", "edge", "brave", "chromium", "opera", "vivaldi")

#: D-071: in portable mode, this file in the data folder is used without asking.
PORTABLE_COOKIES = "cookies.txt"


@dataclass(frozen=True)
class Cookies:
    """Where yt-dlp finds the sign-in: a browser, or a file. Never the cookies."""

    browser: str = ""
    file: Path | None = None

    def params(self) -> dict:
        if self.browser:
            return {"cookiesfrombrowser": (self.browser, None, None, None)}
        return {"cookiefile": str(self.file)}

    def label(self) -> str:
        if self.browser:
            return f"{self.browser.capitalize()}'s login"
        return f"the cookies file {self.file}"


def from_setting(value: str) -> Cookies | None:
    """A browser name, a path, or None for an empty value."""
    value = value.strip()
    if not value:
        return None
    if value.lower() in BROWSERS:
        return Cookies(browser=value.lower())
    return Cookies(file=Path(value.strip("'\"")).expanduser().absolute())


def setting() -> str:
    """What config.toml says, or ""."""
    from ..runs import read_config

    settings = read_config()
    value = settings.get(CONFIG_KEY, settings.get(OLD_CONFIG_KEY))
    return value if isinstance(value, str) else ""


def portable_file() -> Path | None:
    """D-071: `data/cookies.txt` in portable mode, when it is there."""
    from ..runs import portable_dir

    base = portable_dir()
    path = base / PORTABLE_COOKIES if base else None
    return path if path and path.is_file() else None


def configured() -> Cookies | None:
    """Settings, then the portable folder's cookies.txt; None for no sign-in."""
    chosen = from_setting(setting())
    if chosen is not None:
        return chosen
    found = portable_file()
    return Cookies(file=found) if found else None


def chosen(browser: str | None = None, file: str | Path | None = None) -> Cookies | None:
    """The flags win over config.toml (D-071)."""
    if browser:
        return Cookies(browser=browser.lower())
    if file:
        return Cookies(file=Path(file).expanduser().absolute())
    return configured()


# ------------------------------------------------------------------ which browsers are here (D-077)
#
# The folders yt-dlp reads cookies from (yt_dlp/cookies.py: _firefox_browser_dirs,
# _get_chromium_based_browser_settings, _extract_safari_cookies), so a browser
# is offered only where yt-dlp would find it. tests/test_sign_in.py checks these
# against yt-dlp's own on the system the tests run on. Seams for the tests: the
# system, the environment and the home folder.

#: The Chromium-based browsers offered, in this order, and how they are named.
CHROMIUM = ("chrome", "edge", "brave", "opera", "vivaldi", "chromium")
NAMES = {"firefox": "Firefox", "chrome": "Chrome", "edge": "Edge", "brave": "Brave", "opera": "Opera",
         "vivaldi": "Vivaldi", "chromium": "Chromium", "safari": "Safari"}


def system() -> str:
    """`windows`, `macos` or `linux`, from sys.platform; never asked."""
    if sys.platform in ("win32", "cygwin"):
        return "windows"
    return "macos" if sys.platform == "darwin" else "linux"


def environ():
    import os

    return os.environ


def home() -> Path:
    return Path.home()


def _config_home() -> Path:
    return Path(environ().get("XDG_CONFIG_HOME") or home() / ".config")


def firefox_dirs(where: str) -> list[Path]:
    env = environ()
    if where == "windows":
        roaming, local = Path(env.get("APPDATA", "")), Path(env.get("LOCALAPPDATA", ""))
        return [roaming / "Mozilla" / "Firefox" / "Profiles",
                local / "Packages" / "Mozilla.Firefox_n80bbvh6b1yt2" / "LocalCache" / "Roaming" / "Mozilla"
                / "Firefox" / "Profiles"]
    if where == "macos":
        return [home() / "Library" / "Application Support" / "Firefox" / "Profiles"]
    return [
        _config_home() / "mozilla" / "firefox",
        home() / ".mozilla" / "firefox",
        home() / ".var" / "app" / "org.mozilla.firefox" / "config" / "mozilla" / "firefox",  # flatpak
        home() / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",  # flatpak
        home() / "snap" / "firefox" / "common" / ".mozilla" / "firefox",  # snap
    ]


def chromium_dir(browser: str, where: str) -> Path:
    env = environ()
    if where == "windows":
        local, roaming = Path(env.get("LOCALAPPDATA", "")), Path(env.get("APPDATA", ""))
        return {
            "brave": local / "BraveSoftware" / "Brave-Browser" / "User Data",
            "chrome": local / "Google" / "Chrome" / "User Data",
            "chromium": local / "Chromium" / "User Data",
            "edge": local / "Microsoft" / "Edge" / "User Data",
            "opera": roaming / "Opera Software" / "Opera Stable",
            "vivaldi": local / "Vivaldi" / "User Data",
        }[browser]
    if where == "macos":
        support = home() / "Library" / "Application Support"
        return support / {
            "brave": "BraveSoftware/Brave-Browser", "chrome": "Google/Chrome", "chromium": "Chromium",
            "edge": "Microsoft Edge", "opera": "com.operasoftware.Opera", "vivaldi": "Vivaldi",
        }[browser]
    return _config_home() / {
        "brave": "BraveSoftware/Brave-Browser", "chrome": "google-chrome", "chromium": "chromium",
        "edge": "microsoft-edge", "opera": "opera", "vivaldi": "vivaldi",
    }[browser]


def installed_browsers() -> list[str]:
    """D-077: the browsers whose profile folder is on this computer, in the
    order offered: Firefox, the Chromium-based ones, Safari (macOS only)."""
    where = system()
    found = ["firefox"] if any(d.is_dir() for d in firefox_dirs(where)) else []
    found += [b for b in CHROMIUM if chromium_dir(b, where).is_dir()]
    if where == "macos":
        found.append("safari")  # part of macOS; yt-dlp reads it from ~/Library
    return found


def chromium_warning() -> str:
    """D-077: only on Windows do Chromium-based browsers keep their login unreadable."""
    return "on Windows usually cannot be read" if system() == "windows" else ""


#: D-077: the "How does this work?" row of the sign-in list.
HOW_IT_WORKS = (
    "YouTube sometimes asks to confirm you're a person. It depends on your internet connection, "
    "not on the video.\n"
    "Signing in solves it: the program borrows your browser's YouTube login, the same way your "
    "browser proves who you are.\n"
    "Firefox works on every computer. On Windows, Chrome, Edge and other Chromium-based browsers "
    "lock their login so that only they can use it (this protects you from viruses that steal "
    "logins), so the program usually can't borrow it there. On Linux and macOS they usually work.\n"
    "Your login never leaves this computer and is never saved in the files the program writes."
)


def browser_advice(browser: str) -> str:
    """What to try after `browser` could not be read."""
    if browser == "firefox":
        return "Make sure you are signed in to YouTube in Firefox, or use a cookies.txt file."
    note = ""
    if browser in UNREADABLE_ON_WINDOWS and system() == "windows":
        note = f"On Windows, {browser.capitalize()}'s cookies usually cannot be read. "
    return f"{note}Try Firefox, or a cookies.txt file."
