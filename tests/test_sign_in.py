"""D-071: YouTube's bot check said plainly, and the sign-in it asks for, as
cookies yt-dlp reads for itself and nothing the tool writes ever holds."""

import sys

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
    monkeypatch.setattr(sys, "platform", platform)
    code, _ = fetched(tmp_path, monkeypatch, FakeYtDlp(unreadable_browser=True), "--cookies-from-browser", "chrome")
    err = capsys.readouterr().err
    assert code == 1
    assert "Could not read the YouTube sign-in from Chrome (Failed to decrypt with DPAPI)." in err
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
    assert isolated_settings.read_text(encoding="utf-8") == f'{cookies.CONFIG_KEY} = "{jar}"\n'


# ------------------------------------------------------------------ the menu


def test_the_menu_offers_the_ways_out_and_retries_signed_in(tmp_path, monkeypatch, capsys):
    # Fetch, a link, the url; YouTube's check; "Use your browser's sign-in",
    # Firefox; read again; the caption; no normalizing; quit.
    _, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", "1", URL, "1", "1", "", "n", "q"],
                        ytdlp=FakeYtDlp(metadata=["bot", "ok"]))
    assert fetch.BOT_CHECK in out and "Sign in to confirm" not in out
    for way in ("Use your browser's YouTube sign-in (cookies)", "Try again later",
                "Use a file from this computer", "<- Back"):
        assert way in out
    assert "Chrome and Edge on Windows usually cannot be read" in out
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
    _, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", "1", URL, "", "1", "1", "n", "q"],
                        ytdlp=FakeYtDlp(caption=["Sign in to confirm you're not a bot", "ok"]))
    assert fetch.BOT_CHECK in out and "Use a file from this computer" in out
    assert fake.calls == ["metadata", "metadata", "caption", "metadata", "caption"]  # the menu reads it first
    assert (tmp_path / "runs" / VIDEO_ID / CAPTION_FILE).exists()


def test_settings_takes_a_cookies_txt_and_keeps_only_its_path(tmp_path, monkeypatch, capsys, jar, isolated_settings):
    # Settings, YouTube sign-in, "A cookies.txt file…" (no dialog here: typed).
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["7", "2", "5", str(jar), "q"])
    assert "no file dialog here; type the path instead" in out
    assert f"Saved. YouTube sign-in: the cookies file {jar}" in out
    assert runs.read_config() == {cookies.CONFIG_KEY: str(jar)}
    assert SECRET not in isolated_settings.read_text(encoding="utf-8")
    # And "None" removes it.
    menu(tmp_path, monkeypatch, capsys, ["7", "2", "6", "q"])
    assert runs.read_config() == {}
