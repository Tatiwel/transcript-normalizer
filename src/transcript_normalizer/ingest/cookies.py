"""D-071: the YouTube sign-in, as cookies yt-dlp reads for itself.

The tool never reads, copies or stores a cookie. It names where they are, a
browser or a cookies.txt file, and yt-dlp reads them in this process for the
call (`cookiesfrombrowser`, `cookiefile`). config.toml keeps that name or path,
never the contents, and nothing a run writes mentions either.

Which one, in order: `fetch --cookies-from-browser` or `--cookies`; then
`youtube_cookies` in config.toml (Settings → YouTube sign-in); then, in portable
mode, a `cookies.txt` in the data folder.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

#: config.toml's key: a browser name, or the path of a cookies.txt file.
CONFIG_KEY = "youtube_cookies"

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
            return f"{self.browser.capitalize()}'s YouTube sign-in"
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

    value = read_config().get(CONFIG_KEY)
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


def browser_advice(browser: str) -> str:
    """What to try after `browser` could not be read."""
    if browser == "firefox":
        return "Make sure you are signed in to YouTube in Firefox, or use a cookies.txt file."
    note = ""
    if browser in UNREADABLE_ON_WINDOWS and sys.platform == "win32":
        note = f"On Windows, {browser.capitalize()}'s cookies usually cannot be read. "
    return f"{note}Try Firefox, or a cookies.txt file."
