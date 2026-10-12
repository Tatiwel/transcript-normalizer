"""D-071: YouTube's bot check said plainly, and the sign-in it asks for, as
cookies yt-dlp reads for itself and nothing the tool writes ever holds."""

import io
import re
import sys
from pathlib import Path

import pytest

from transcript_normalizer import cli, runs
from transcript_normalizer.ingest import cookies, fetch
from transcript_normalizer.runs import CAPTION_FILE

from . import fetch_fakes
from .fetch_fakes import BOT_CHECK, URL, VIDEO_ID, FakeYtDlp
from .test_interactive import menu

#: A fake cookie jar: what a browser extension exports, with values no file may repeat.
SECRET = "SECRET-COOKIE-VALUE-7f3a9c"
JAR = (
    "# Netscape HTTP Cookie File\n"
    f".youtube.com\tTRUE\t/\tTRUE\t2147483647\tSAPISID\t{SECRET}-sapisid\n"
    f".youtube.com\tTRUE\t/\tTRUE\t2147483647\t__Secure-3PSID\t{SECRET}-psid\n"
)


@pytest.fixture
def jar(tmp_path):
    path = tmp_path / "exported" / "cookies.txt"
    path.parent.mkdir()
    path.write_text(JAR, encoding="utf-8")
    return path


def fetched(tmp_path, monkeypatch, ytdlp, *extra):
    monkeypatch.chdir(tmp_path)
    fake, _ = fetch_fakes.install(monkeypatch, fetch, ytdlp)
    return cli.main(["fetch", URL, *extra]), fake


# ------------------------------------------------------------------ the check, plainly


@pytest.mark.parametrize("message, plainly", [
    (BOT_CHECK, fetch.BOT_CHECK),
    ("ERROR: [youtube] x: Sign in to confirm you're not a bot", fetch.BOT_CHECK),
    ("ERROR: [youtube] x: Sign in to confirm your age. This video may be inappropriate for some users.", fetch.SIGN_IN),
    ("ERROR: [youtube] x: Login details are needed to download this content.", fetch.SIGN_IN),
    ("ERROR: [youtube] x: Join this channel to get access to members-only content", fetch.SIGN_IN),
    (fetch_fakes.RATE_LIMITED, ""),
    ("ERROR: [youtube] x: Video unavailable", ""),
])
def test_youtube_s_checks_are_recognised(message, plainly):
    assert fetch.sign_in_needed(message) == plainly


def test_the_bot_check_is_said_plainly_and_fetch_stops(tmp_path, monkeypatch, capsys):
    code, fake = fetched(tmp_path, monkeypatch, FakeYtDlp(metadata=["bot"]))
    err = capsys.readouterr().err
    assert code == fetch.EXIT_SIGN_IN
    assert "YouTube asked to confirm you are not a bot. This depends on your connection, not on the video." in err
    assert "--cookies-from-browser firefox" in err and "try again later" in err
    assert "Sign in to confirm" not in err and "yt-dlp/wiki" not in err  # yt-dlp's own words are gone
    assert fake.calls == ["metadata"]  # not retried like a 429
    assert not (tmp_path / "runs" / VIDEO_ID).exists()


def test_a_check_at_the_caption_stops_before_the_audio(tmp_path, monkeypatch, capsys):
    age = "Sign in to confirm your age. This video may be inappropriate for some users."
    code, fake = fetched(tmp_path, monkeypatch, FakeYtDlp(caption=[age]))
    assert code == fetch.EXIT_SIGN_IN
    assert fetch.SIGN_IN in capsys.readouterr().err
    assert fake.calls == ["metadata", "caption"]  # the audio would meet the same check
    assert not (tmp_path / "runs" / VIDEO_ID).exists()  # D-059: the attempt is taken back


# ------------------------------------------------------------------ where the sign-in comes from


def test_no_sign_in_by_default(tmp_path, monkeypatch):
    code, fake = fetched(tmp_path, monkeypatch, FakeYtDlp())
    assert code == 0
    assert not any("cookiefile" in p or "cookiesfrombrowser" in p for p in fake.params)


def test_the_browser_flag_reaches_every_yt_dlp_call(tmp_path, monkeypatch):
    code, fake = fetched(tmp_path, monkeypatch, FakeYtDlp(caption=["fail"]), "--cookies-from-browser", "firefox")
    assert code == 0 and fake.calls == ["metadata", "caption", "audio"]
    assert all(p["cookiesfrombrowser"] == ("firefox", None, None, None) for p in fake.params)


def test_the_file_flag_reaches_every_yt_dlp_call(tmp_path, monkeypatch, jar):
    code, fake = fetched(tmp_path, monkeypatch, FakeYtDlp(), "--cookies", str(jar))
    assert code == 0
    assert all(p["cookiefile"] == str(jar) for p in fake.params) and len(fake.params) == 2


def test_settings_is_the_default_and_a_flag_wins(tmp_path, monkeypatch, jar):
    runs.write_config({cookies.CONFIG_KEY: "firefox"})
    _, fake = fetched(tmp_path, monkeypatch, FakeYtDlp())
    assert all(p["cookiesfrombrowser"][0] == "firefox" for p in fake.params)
    _, fake = fetched(tmp_path, monkeypatch, FakeYtDlp(), "--cookies", str(jar))
    assert all(p.get("cookiefile") == str(jar) and "cookiesfrombrowser" not in p for p in fake.params)
    runs.write_config({cookies.CONFIG_KEY: str(jar)})
    assert cookies.configured() == cookies.Cookies(file=jar)


def test_a_missing_cookies_file_is_named(tmp_path, monkeypatch, capsys):
    code, fake = fetched(tmp_path, monkeypatch, FakeYtDlp(), "--cookies", str(tmp_path / "gone.txt"))
    assert code == 1
    assert f"There is no cookies file at {tmp_path / 'gone.txt'}." in capsys.readouterr().err
    assert fake.calls == []


@pytest.mark.parametrize("platform, windows_note", [("win32", True), ("linux", False)])
def test_an_unreadable_browser_is_named_with_what_to_try(tmp_path, monkeypatch, capsys, platform, windows_note):
    monkeypatch.setattr(cookies, "system", lambda: "windows" if platform == "win32" else "linux")
    code, _ = fetched(tmp_path, monkeypatch, FakeYtDlp(unreadable_browser=True), "--cookies-from-browser", "chrome")
    err = capsys.readouterr().err
    assert code == 1
    assert "Could not read the login from Chrome (Failed to decrypt with DPAPI)." in err
    assert "Try Firefox, or a cookies.txt file." in err
    assert ("On Windows, Chrome's cookies usually cannot be read." in err) == windows_note


def test_portable_mode_uses_the_cookies_txt_in_data(tmp_path, monkeypatch, jar):
    app = tmp_path / "app"
    (app / runs.PORTABLE_DATA).mkdir(parents=True)
    (app / runs.PORTABLE_FILE).write_text("portable\n", encoding="utf-8")
    monkeypatch.setattr(runs, "program_dir", lambda: app)
    placed = app / runs.PORTABLE_DATA / cookies.PORTABLE_COOKIES
    placed.write_text(JAR, encoding="utf-8")
    _, fake = fetched(tmp_path, monkeypatch, FakeYtDlp())
    assert all(p["cookiefile"] == str(placed) for p in fake.params)
    # Settings still wins over the file in data/.
    runs.write_config({cookies.CONFIG_KEY: "firefox"})
    assert cookies.configured() == cookies.Cookies(browser="firefox")


# ------------------------------------------------------------------ privacy


def test_no_cookie_value_is_in_any_file_a_run_writes(tmp_path, monkeypatch, jar, isolated_settings):
    """Fetch through both steps with the sign-in in Settings, then normalize:
    yt-dlp read the jar, and no file written holds anything from it."""
    runs.write_config({cookies.CONFIG_KEY: str(jar)})
    code, fake = fetched(tmp_path, monkeypatch, FakeYtDlp(caption=["fail"]))
    assert code == 0 and fake.calls == ["metadata", "caption", "audio"]
    assert fake.cookies and all(SECRET in read for read in fake.cookies)  # the jar was really used
    caption = tmp_path / "runs" / VIDEO_ID / CAPTION_FILE
    assert cli.main(["normalize", str(caption), "--force"]) == 0
    written = [p for p in tmp_path.rglob("*") if p.is_file() and p != jar]
    assert any(p.name == "meta.yaml" for p in written) and any(p.name == "report.txt" for p in written)
    for path in [*written, isolated_settings]:
        assert SECRET.encode() not in path.read_bytes(), path
    # config.toml names the file, and holds nothing of what is in it.
    assert runs.read_config() == {cookies.CONFIG_KEY: str(jar)}


# ------------------------------------------------------------------ the menu


def test_the_menu_offers_the_ways_out_and_retries_signed_in(tmp_path, monkeypatch, capsys):
    # Fetch, a link, the url; YouTube's check; "Use your browser's sign-in",
    # Firefox; read again; the caption; no normalizing; quit.
    browsers(monkeypatch, tmp_path, "linux", "firefox")
    _, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", "1", URL, "1", "1", "", "n", "q"],
                        ytdlp=FakeYtDlp(metadata=["bot", "ok"]))
    assert fetch.BOT_CHECK in out and "Sign in to confirm" not in out
    for way in ("Sign in with your browser's login", "Try again later",
                "Use a file from this computer", "<- Back"):
        assert way in out
    assert re.search(r"Firefox +works best", out)
    assert runs.read_config() == {cookies.CONFIG_KEY: "firefox"}
    assert "cookiesfrombrowser" not in fake.params[0]
    assert all(p["cookiesfrombrowser"][0] == "firefox" for p in fake.params[1:])
    assert (tmp_path / "runs" / VIDEO_ID / CAPTION_FILE).exists()


def test_try_again_later_goes_back_to_the_menu(tmp_path, monkeypatch, capsys):
    _, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", "1", URL, "2", "q"], ytdlp=FakeYtDlp(metadata=["bot"]))
    assert fake.calls == ["metadata"] and runs.read_config() == {}
    assert "What would you like to do?" in out.split(fetch.BOT_CHECK)[1]


def test_a_check_at_the_caption_offers_the_same_ways_out(tmp_path, monkeypatch, capsys):
    # The check comes at the caption download this time; sign in, and it is fetched again.
    browsers(monkeypatch, tmp_path, "linux", "firefox")
    _, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", "1", URL, "", "1", "1", "n", "q"],
                        ytdlp=FakeYtDlp(caption=["Sign in to confirm you're not a bot", "ok"]))
    assert fetch.BOT_CHECK in out and "Use a file from this computer" in out
    assert fake.calls == ["metadata", "metadata", "caption", "metadata", "caption"]  # the menu reads it first
    assert (tmp_path / "runs" / VIDEO_ID / CAPTION_FILE).exists()


def test_settings_takes_a_cookies_txt_and_keeps_only_its_path(tmp_path, monkeypatch, capsys, jar, isolated_settings):
    # Settings, YouTube sign-in, "A cookies.txt file…" (no dialog here: typed).
    # No browser on this (test) computer: the file, None, and the help row.
    file_, none = "1", "2"
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["7", "2", file_, str(jar), "q"])
    assert "no file dialog here; type the path instead" in out
    assert f"Saved. Sign-in: the cookies file {jar}" in out
    assert runs.read_config() == {cookies.CONFIG_KEY: str(jar)}
    assert SECRET not in isolated_settings.read_text(encoding="utf-8")
    # And "None" removes it.
    menu(tmp_path, monkeypatch, capsys, ["7", "2", none, "q"])
    assert runs.read_config() == {}


# ------------------------------------------------------------------ which browsers are offered (D-077)


def browsers(monkeypatch, tmp_path, where, *names, snap=False):
    """A computer running `where` with these browsers' profile folders, where
    yt-dlp looks for them. `snap`: Firefox from the snap store (Linux)."""
    home = tmp_path / "home"
    env = {"APPDATA": str(home / "AppData" / "Roaming"), "LOCALAPPDATA": str(home / "AppData" / "Local")} \
        if where == "windows" else {}
    monkeypatch.setattr(cookies, "system", lambda: where)
    monkeypatch.setattr(cookies, "home", lambda: home)
    monkeypatch.setattr(cookies, "environ", lambda: env)
    for name in names:
        folder = cookies.firefox_dirs(where)[-1 if snap else 0] if name == "firefox" else cookies.chromium_dir(name, where)
        folder.mkdir(parents=True)


def sign_in_list(monkeypatch, capsys, answers):
    """The list as Settings and fetch show it, answered with `answers`."""
    from transcript_normalizer import interactive

    monkeypatch.setattr("sys.stdin", io.StringIO("".join(f"{a}\n" for a in answers)))
    picked = interactive.choose_sign_in()
    return picked, capsys.readouterr().out


def rows(out):
    """The rows of the first list printed: (label, description)."""
    first = out.split("Sign-in (your browser's login)")[1].split("enter alone")[0].split("\n> ")[0]
    return [(m.group(1).strip(), (m.group(2) or "").strip()) for m in re.finditer(r"^ +\w\. (.+?)(?: {3}(.*))?$", first, re.M)]


def test_windows_one_chromium_row_with_the_warning(tmp_path, monkeypatch, capsys):
    browsers(monkeypatch, tmp_path, "windows", "firefox", "chrome", "edge")
    picked, out = sign_in_list(monkeypatch, capsys, ["2", "2"])  # Chromium-based, then Edge
    assert rows(out) == [
        ("Firefox", "works best"),
        ("Chromium-based browser", "Chrome, Edge · on Windows usually cannot be read"),
        ("A cookies.txt file…", "exported from your browser; see Help"),
        ("None", "fetch without signing in"),
        ("How does this work?", ""),
        ("<- Back", ""),
    ]
    assert "Which Chromium-based browser?" in out and picked == "edge"


def test_linux_with_snap_firefox_and_chrome_has_no_warning_and_no_sub_list(tmp_path, monkeypatch, capsys):
    browsers(monkeypatch, tmp_path, "linux", "firefox", "chrome", snap=True)
    assert cookies.installed_browsers() == ["firefox", "chrome"]  # snap Firefox found
    picked, out = sign_in_list(monkeypatch, capsys, ["2"])
    assert rows(out)[:2] == [("Firefox", "works best"), ("Chromium-based browser", "Chrome")]
    assert "usually cannot be read" not in out
    assert picked == "chrome" and "Which Chromium-based browser?" not in out  # only one: straight to it


@pytest.mark.parametrize("snap", [False, True])
def test_firefox_is_found_in_the_folders_yt_dlp_reads(tmp_path, monkeypatch, snap):
    browsers(monkeypatch, tmp_path, "linux", "firefox", snap=snap)
    assert cookies.installed_browsers() == ["firefox"]


def test_macos_offers_safari_and_no_warning(tmp_path, monkeypatch, capsys):
    browsers(monkeypatch, tmp_path, "macos", "chrome", "brave")
    assert cookies.installed_browsers() == ["chrome", "brave", "safari"]
    _, out = sign_in_list(monkeypatch, capsys, ["b"])
    assert [r[0] for r in rows(out)][:2] == ["Chromium-based browser", "Safari"]
    assert "usually cannot be read" not in out


def test_the_sub_list_only_with_two_or_more(tmp_path, monkeypatch, capsys):
    browsers(monkeypatch, tmp_path, "linux", "brave", "vivaldi", "chromium")
    picked, out = sign_in_list(monkeypatch, capsys, ["1", "3"])
    assert rows(out)[0] == ("Chromium-based browser", "Brave, Vivaldi, Chromium")
    assert "Which Chromium-based browser?" in out and picked == "chromium"


def test_no_browser_found_leaves_the_file_none_and_help(tmp_path, monkeypatch, capsys):
    browsers(monkeypatch, tmp_path, "windows")
    _, out = sign_in_list(monkeypatch, capsys, ["b"])
    assert [r[0] for r in rows(out)] == ["A cookies.txt file…", "None", "How does this work?", "<- Back"]
    assert "none was found on this computer" in out


def test_how_does_this_work_explains_then_lists_again(tmp_path, monkeypatch, capsys):
    browsers(monkeypatch, tmp_path, "linux", "firefox")
    picked, out = sign_in_list(monkeypatch, capsys, ["4", "1"])  # How does this work?, then Firefox
    for paragraph in cookies.HOW_IT_WORKS.split("\n"):
        assert f"  {paragraph}" in out
    assert "Some sites sometimes ask to confirm you're a person" in out
    assert out.count("How does this work?") == 2 and picked == "firefox"


def test_the_folders_are_the_ones_yt_dlp_reads(monkeypatch):
    """On the system the tests run on, with its real home and environment."""
    import os

    from yt_dlp import cookies as ytdlp_cookies

    real = "windows" if sys.platform in ("win32", "cygwin") else "macos" if sys.platform == "darwin" else "linux"
    monkeypatch.setattr(cookies, "system", lambda: real)
    monkeypatch.setattr(cookies, "home", Path.home)
    monkeypatch.setattr(cookies, "environ", lambda: os.environ)
    assert [str(d) for d in cookies.firefox_dirs(real)] == [
        os.path.normpath(d) for d in ytdlp_cookies._firefox_browser_dirs()
    ]
    for browser in cookies.CHROMIUM:
        theirs = ytdlp_cookies._get_chromium_based_browser_settings(browser)["browser_dir"]
        assert str(cookies.chromium_dir(browser, real)) == os.path.normpath(theirs)
