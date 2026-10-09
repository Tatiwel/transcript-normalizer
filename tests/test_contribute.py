"""D-056: pack propose shows what the learned layer adds, asks, writes, opens an issue."""

import io
import urllib.parse

import yaml

from transcript_normalizer import contribute
from transcript_normalizer.cli import main
from transcript_normalizer.core.pack import Learned, save_learned
from transcript_normalizer.runs import BUNDLED_PACKS

from .fetch_fakes import LINK
from .test_interactive import menu

BUNDLED = BUNDLED_PACKS / "financas-ptbr.yaml"


def teach(tmp_path):
    """A learned layer with one of each decision, and one entry the pack already has."""
    layer = (
        Learned()
        .confirm("CEMIG", "esse mig", decided="2026-10-01")
        .confirm("CEMIG", "SEMIG", decided="2026-10-01")  # a curated variant already
        .alias("Klabin", "Klabinha", decided="2026-10-02")
        .reject("saber se", "Sabesp", decided="2026-10-03")
    )
    save_learned(layer, tmp_path / "packs" / "financas-ptbr.learned.yaml")


def propose(tmp_path, monkeypatch, answer, opened=True):
    monkeypatch.chdir(tmp_path)
    urls = []
    monkeypatch.setattr(contribute.webbrowser, "open", lambda url: urls.append(url) or opened)
    monkeypatch.setattr("sys.stdin", io.StringIO(answer + "\n"))
    return main(["pack", "propose"]), urls


def test_items_leave_out_what_the_pack_has(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    teach(tmp_path)
    assert [(i.term, i.form, i.decision) for i in contribute.items(BUNDLED)] == [
        ("CEMIG", "esse mig", "variant"),
        ("Klabin", "Klabinha", "alias"),
        ("Sabesp", "saber se", "rejected"),
    ]


def test_propose_shows_asks_writes_and_opens_an_issue(tmp_path, monkeypatch, capsys):
    teach(tmp_path)
    code, urls = propose(tmp_path, monkeypatch, "y")
    out = capsys.readouterr().out
    assert code == 0
    assert "  + variant   esse mig -> CEMIG" in out
    assert "  + alias     Klabinha -> Klabin" in out
    assert "  - rejected  saber se  (not Sabesp)" in out
    written = list((tmp_path / "contributions").glob("financas-ptbr-*.yaml"))
    assert len(written) == 1
    data = yaml.safe_load(written[0].read_text(encoding="utf-8"))
    assert data["pack"] == "financas-ptbr" and data["pack_version"] == "0.3.7"
    assert data["entries"][0] == {"term": "CEMIG", "form": "esse mig", "decision": "variant", "decided": "2026-10-01"}
    (url,) = urls
    assert url.startswith("https://github.com/Tatiwel/transcript-normalizer-packs/issues/new?")
    body = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["body"][0]
    assert "form: esse mig" in body
    assert "a prefilled issue is open in your browser" in out


def test_propose_never_sends_the_transcript(tmp_path, monkeypatch, capsys):
    teach(tmp_path)
    (tmp_path / "runs" / "x").mkdir(parents=True)
    (tmp_path / "runs" / "x" / "legenda.txt").write_text("0:01 uma frase secreta\n", encoding="utf-8")
    _, urls = propose(tmp_path, monkeypatch, "y")
    assert "secreta" not in urllib.parse.unquote_plus(urls[0])


def test_declining_writes_nothing(tmp_path, monkeypatch, capsys):
    teach(tmp_path)
    code, urls = propose(tmp_path, monkeypatch, "n")
    assert code == 0 and urls == []
    assert not (tmp_path / "contributions").exists()
    assert "nothing written." in capsys.readouterr().out


def test_without_a_browser_the_url_is_printed(tmp_path, monkeypatch, capsys):
    teach(tmp_path)
    _, urls = propose(tmp_path, monkeypatch, "y", opened=False)
    assert f"open this link to submit it as an issue:\n{urls[0]}" in capsys.readouterr().out


def test_nothing_to_contribute(tmp_path, monkeypatch, capsys):
    code, urls = propose(tmp_path, monkeypatch, "y")
    assert code == 0 and urls == []
    assert "nothing to contribute" in capsys.readouterr().out


def test_an_unknown_pack_is_an_error(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["pack", "propose", "--pack", "biomed-ptbr"]) == 1
    assert "no pack called biomed-ptbr" in capsys.readouterr().err


def test_a_long_contribution_asks_for_the_file_instead(tmp_path):
    found = [contribute.Item("CEMIG", f"forma {i}", "variant", "2026-10-01") for i in range(400)]
    text = contribute.contribution_yaml("financas-ptbr", "0.3.4", found, "2026-10-06")
    url = contribute.issue_url("financas-ptbr", tmp_path / "financas-ptbr-2026-10-06.yaml", text, 400)
    assert len(url) <= contribute.MAX_URL
    assert "attach" in urllib.parse.unquote_plus(url)


def test_the_menu_offers_to_contribute_after_a_review(tmp_path, monkeypatch, capsys):
    urls = []
    monkeypatch.setattr(contribute.webbrowser, "open", lambda url: urls.append(url) or True)
    lines = [*LINK, "", "1", "", "a", "-", "y", "y", "", "q"]
    _, out, _ = menu(tmp_path, monkeypatch, capsys, lines)
    assert "Contribute what you taught the tool? [y/N]" in out
    assert "  + variant   Klabine -> Klabin" in out
    assert len(urls) == 1 and list((tmp_path / "contributions").glob("*.yaml"))
