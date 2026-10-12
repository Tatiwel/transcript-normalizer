"""D-078: sites other than YouTube. The sign-in for any site, their login
walls said plainly, no captions (straight to transcription), keeping the
audio, and `fetch --list` as a quick check of a link."""

import pytest
import yaml

from transcript_normalizer import cli, interactive, runs
from transcript_normalizer.ingest import cookies, fetch

from . import fetch_fakes
from .fetch_fakes import URL, FakeYtDlp
from .test_interactive import menu

VIMEO = "https://vimeo.com/123456789"
INSTAGRAM = "https://www.instagram.com/reel/C0ffee12345/"
#: What yt-dlp's Instagram extractor raises without a login (raise_login_required).
INSTAGRAM_WALL = (
    "ERROR: [Instagram] C0ffee12345: Requested content is not available, rate-limit reached or login "
    "required. Use --cookies, --cookies-from-browser, --username and --password, --netrc-cmd, or --netrc "
    "(instagram) to provide account credentials. See  https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-"
    "pass-cookies-to-yt-dlp  for how to manually pass cookies"
)
AUDIO_ONLY = [{"format_id": "audio", "ext": "m4a", "acodec": "mp4a.40.2", "vcodec": "none"},
              {"format_id": "720p", "ext": "mp4", "acodec": "none", "vcodec": "avc1"}]


def vimeo(**kwargs):
    """A Vimeo video with no captions and an audio-only format."""
    return FakeYtDlp(url=VIMEO, site="Vimeo", has_caption=False, formats=AUDIO_ONLY,
                     video_id="123456789", **kwargs)


def fetched(tmp_path, monkeypatch, ytdlp, url, *extra):
    monkeypatch.chdir(tmp_path)
    fake, _ = fetch_fakes.install(monkeypatch, fetch, ytdlp)
    return cli.main(["fetch", url, *extra]), fake


# ------------------------------------------------------------------ site names and login walls


@pytest.mark.parametrize("message, url, site", [
    (INSTAGRAM_WALL, "", "Instagram"),
    ("ERROR: [facebook] 1234: This video is only available for registered users. Use --cookies-from-browser "
     "or --cookies for the authentication.", "", "Facebook"),
    ("ERROR: [TikTok] 7200: This user's account is private. Log into an account that has access", "", "TikTok"),
    ("ERROR: [twitter] 1700: You are not authorized to view this protected tweet. Use --cookies", "", "X (Twitter)"),
    ("ERROR: [vimeo] 1: The web client only works when logged-in. Use --cookies", "", "Vimeo"),
    ("ERROR: [instagram:story] x: You need to log in to access this content", "", "Instagram"),
    ("NSFW tweet requires authentication", "https://x.com/someone/status/1", "X (Twitter)"),
    ("This content is only available for registered users who follow this account", INSTAGRAM, "Instagram"),
])
def test_a_login_wall_on_any_site_is_said_with_its_name(message, url, site):
    assert fetch.sign_in_needed(message, url) == f"{site} asked you to sign in for this video."


def test_ordinary_errors_are_not_login_walls():
    for message in ("ERROR: [vimeo] 1: Video unavailable", "ERROR: [TikTok] 2: Unable to extract aweme detail info",
                    fetch_fakes.RATE_LIMITED):
        assert fetch.sign_in_needed(message) == ""


def test_youtube_keeps_its_own_words():
    assert fetch.sign_in_needed("ERROR: [youtube] x: Sign in to confirm your age") == fetch.SIGN_IN
    assert fetch.sign_in_needed(fetch_fakes.BOT_CHECK) == fetch.BOT_CHECK


def test_a_login_wall_without_a_sign_in(tmp_path, monkeypatch, capsys):
    code, fake = fetched(tmp_path, monkeypatch, FakeYtDlp(url=INSTAGRAM, metadata=[INSTAGRAM_WALL]), INSTAGRAM)
    err = capsys.readouterr().err
    assert code == fetch.EXIT_SIGN_IN
    assert "Instagram asked you to sign in for this video." in err
    assert "--username" not in err and "rate-limit" not in err  # yt-dlp's own words are gone


@pytest.mark.parametrize("chosen, said", [
    (["--cookies-from-browser", "firefox"], "The browser you chose (Firefox) may not be signed in to Instagram. "
                                            "Sign in there, or pick another browser in Settings."),
    (None, "The browser you chose (Chrome) may not be signed in to Instagram. "
           "Sign in there, or pick another browser in Settings."),
])
def test_a_login_wall_with_a_sign_in_set(tmp_path, monkeypatch, capsys, chosen, said):
    if chosen is None:
        runs.write_config({cookies.CONFIG_KEY: "chrome"})  # Settings
    code, fake = fetched(tmp_path, monkeypatch, FakeYtDlp(url=INSTAGRAM, metadata=[INSTAGRAM_WALL]), INSTAGRAM,
                         *(chosen or []))
    assert code == fetch.EXIT_SIGN_IN
    assert said in capsys.readouterr().err
    assert all("cookiesfrombrowser" in p for p in fake.params)  # passed for Instagram as for YouTube


def test_the_menu_offers_the_same_ways_out_for_any_site(tmp_path, monkeypatch, capsys):
    _, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", "1", INSTAGRAM, "2", "q"],
                        ytdlp=FakeYtDlp(url=INSTAGRAM, metadata=[INSTAGRAM_WALL]))
    assert "Instagram asked you to sign in for this video." in out
    for way in ("Sign in with your browser's login", "Try again later", "Use a file from this computer"):
        assert way in out


# ------------------------------------------------------------------ the setting's new name


def test_the_old_key_still_works_and_saving_moves_it(tmp_path, monkeypatch, capsys):
    runs.write_config({cookies.OLD_CONFIG_KEY: "firefox", "pack": "financas-ptbr"})
    assert cookies.configured() == cookies.Cookies(browser="firefox")
    interactive.save_sign_in("chrome")
    assert runs.read_config() == {"pack": "financas-ptbr", cookies.CONFIG_KEY: "chrome"}
    interactive.save_sign_in(None)
    assert runs.read_config() == {"pack": "financas-ptbr"}


def test_settings_calls_it_sign_in(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["7", "2", "b", "q"])
    assert "Sign-in (your browser's login)" in out and "YouTube sign-in" not in out


# ------------------------------------------------------------------ no captions


def test_the_full_build_goes_straight_to_transcription(tmp_path, monkeypatch, capsys):
    # Fetch, a link, the Vimeo url; yes to transcribing; no normalizing.
    _, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", "1", VIMEO, "y", "n", "q"], ytdlp=vimeo())
    assert "Vimeo doesn't provide captions for this video." in out
    assert "Transcribe the audio on this computer instead?" in out
    assert "Use the platform's caption" not in out
    assert fake.calls == ["metadata", "metadata", "audio"]


def test_the_lite_build_says_what_would_help_and_returns(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fetch, "is_lite_build", lambda: True)
    _, out, fake = menu(tmp_path, monkeypatch, capsys, ["1", "1", VIMEO, "q"], ytdlp=vimeo())
    assert ("Vimeo doesn't provide captions for this video. "
            "The full build can transcribe its audio on this computer.") in out
    assert "Transcribe the audio" not in out and "fetch did not finish" not in out and "error" not in out
    assert "audio" not in fake.calls


def test_the_lite_build_on_the_command_line(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(fetch, "is_lite_build", lambda: True)
    code, _ = fetched(tmp_path, monkeypatch, vimeo(), VIMEO)
    err = capsys.readouterr().err
    assert code == 1
    assert err.strip() == ("Vimeo doesn't provide captions for this video. "
                           "The full build can transcribe its audio on this computer.")
    assert "could not get a text" not in err


# ------------------------------------------------------------------ keeping the audio


def run_folder(tmp_path):
    return tmp_path / "runs" / "123456789"


def test_the_audio_is_deleted_by_default(tmp_path, monkeypatch, capsys):
    code, _ = fetched(tmp_path, monkeypatch, vimeo(), VIMEO)
    assert code == 0
    assert not list(run_folder(tmp_path).glob("*.m4a"))
    assert "the audio was deleted; --keep-audio, or Settings, keeps it" in capsys.readouterr().out


def test_keep_audio_keeps_it_under_the_video_s_id(tmp_path, monkeypatch, capsys):
    code, _ = fetched(tmp_path, monkeypatch, vimeo(), VIMEO, "--keep-audio")
    assert code == 0
    assert sorted(p.name for p in run_folder(tmp_path).iterdir()) == ["123456789.m4a", "legenda.txt", "meta.yaml"]


def test_settings_keeps_the_audio(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["7", "3", "y", "q"])
    assert "Keep the audio after transcribing" in out and "now: off" in out
    assert runs.read_config() == {fetch.KEEP_AUDIO: "yes"}
    code, _ = fetched(tmp_path, monkeypatch, vimeo(), VIMEO)
    assert (run_folder(tmp_path) / "123456789.m4a").exists()


# ------------------------------------------------------------------ fetch --list


def test_list_checks_a_site_without_captions(tmp_path, monkeypatch, capsys):
    code, fake = fetched(tmp_path, monkeypatch, vimeo(), VIMEO, "--list")
    out = capsys.readouterr().out
    assert code == 0 and fake.calls == ["metadata"]
    lines = [line.strip() for line in out.splitlines()]
    assert lines[0] == "site: Vimeo"
    assert "captions: none (Vimeo doesn't provide captions for this video.)" in lines
    assert "audio: audio only (m4a)" in lines and "login: not asked" in lines
    assert not (tmp_path / "runs").exists()  # nothing downloaded, nothing written


def test_list_says_when_a_site_asks_for_a_login(tmp_path, monkeypatch, capsys):
    code, _ = fetched(tmp_path, monkeypatch, FakeYtDlp(url=INSTAGRAM, metadata=[INSTAGRAM_WALL]), INSTAGRAM, "--list")
    out = capsys.readouterr().out
    assert code == fetch.EXIT_SIGN_IN
    assert "site: Instagram" in out and "login: asked: Instagram asked you to sign in for this video." in out


def test_list_on_youtube_keeps_its_track_lines(tmp_path, monkeypatch, capsys):
    yt = FakeYtDlp(site="Youtube", automatic=("pt-orig", "en"), formats=AUDIO_ONLY)
    code, _ = fetched(tmp_path, monkeypatch, yt, URL, "--list")
    lines = [line.strip() for line in capsys.readouterr().out.splitlines()]
    assert code == 0 and lines[0] == "site: YouTube"
    assert "original: pt-orig" in lines and "login: not asked" in lines


# ------------------------------------------------------------------ D-079: unsupported, duration, one message


UNSUPPORTED_URL = "https://example.org/videos/42"


def unsupported():
    return FakeYtDlp(url=UNSUPPORTED_URL, metadata=[f"ERROR: Unsupported URL: {UNSUPPORTED_URL}"])


def test_an_unsupported_site_on_the_command_line(tmp_path, monkeypatch, capsys):
    code, _ = fetched(tmp_path, monkeypatch, unsupported(), UNSUPPORTED_URL)
    captured = capsys.readouterr()
    assert code == 1
    assert captured.err.strip() == fetch.UNSUPPORTED
    assert "Unsupported URL" not in captured.out + captured.err and "could not read" not in captured.err


def test_an_unsupported_site_in_the_menu(tmp_path, monkeypatch, capsys):
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["1", "1", UNSUPPORTED_URL, "q"], ytdlp=unsupported())
    assert ("This site isn't supported. Download the video another way and use "
            "'A file on this computer'.") in out
    assert "Unsupported URL" not in out and "error:" not in out and "fetch did not finish" not in out


def instagram_reel():
    """The real case: no duration in the metadata, no captions, 50 s of audio."""
    return FakeYtDlp(url=INSTAGRAM, site="Instagram", has_caption=False, formats=AUDIO_ONLY,
                     video_id="C0ffee12345", duration=None)


class FiftySeconds(fetch_fakes.FakeWhisper):
    def transcribe(self, audio, **options):
        segments, _ = super().transcribe(audio, **options)
        return segments, fetch_fakes.Info(duration=50.04)


def test_list_says_unknown_when_the_site_gives_no_duration(tmp_path, monkeypatch, capsys):
    code, _ = fetched(tmp_path, monkeypatch, instagram_reel(), INSTAGRAM, "--list")
    out = capsys.readouterr().out
    assert code == 0 and "   duration: unknown" in out and "0min00s" not in out


def test_step_2_measures_the_duration_from_the_audio(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    fetch_fakes.install(monkeypatch, fetch, instagram_reel())
    monkeypatch.setattr(fetch, "load_whisper", FiftySeconds)
    assert cli.main(["fetch", INSTAGRAM]) == 0
    out = capsys.readouterr().out
    assert "   duration: unknown" in out
    assert "   duration: 0min50s (measured from the audio)" in out
    meta = yaml.safe_load((tmp_path / "runs" / "C0ffee12345" / "meta.yaml").read_text(encoding="utf-8"))
    assert (meta["duration"], meta["duration_from"]) == (50, "audio")


def test_a_site_s_own_duration_is_kept(tmp_path, monkeypatch, capsys):
    code, _ = fetched(tmp_path, monkeypatch, vimeo(), VIMEO)
    meta = yaml.safe_load((run_folder(tmp_path) / "meta.yaml").read_text(encoding="utf-8"))
    assert code == 0 and meta["duration"] == 125 and "duration_from" not in meta
    assert "measured from the audio" not in capsys.readouterr().out


def test_no_captions_at_all_is_one_sentence_on_the_command_line(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    fetch_fakes.install(monkeypatch, fetch, vimeo())
    # Step 2 fails too, so the failure list is printed and can be read.
    monkeypatch.setattr(fetch, "load_whisper", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no model")))
    assert cli.main(["fetch", VIMEO]) == 1
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert "there is no caption in" not in text
    assert "warning: Vimeo doesn't provide captions for this video." in text
    assert "  - Vimeo doesn't provide captions for this video." in captured.err  # the failure list too


def test_captions_but_not_in_the_language_keeps_the_detail(tmp_path, monkeypatch, capsys):
    code, _ = fetched(tmp_path, monkeypatch, FakeYtDlp(automatic=("en",)), URL, "--caption-only")
    err = capsys.readouterr().err.strip()
    assert code == 1
    assert err == "there is no caption in 'pt' for this video (manual: none; automatic: en)"
