"""D-067: pack propose --whole: summary, ask, write, a prefilled issue."""

import hashlib
import io
import json
import urllib.parse

from transcript_normalizer import contribute, registry
from transcript_normalizer.cli import main

from .test_interactive import menu


def setup(tmp_path, monkeypatch, index=None, opened=True):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(registry.INDEX_ENV, index or (tmp_path / "offline" / "index.json").as_uri())
    urls = []
    monkeypatch.setattr(contribute.webbrowser, "open", lambda url: urls.append(url) or opened)
    return urls


def med(tmp_path):
    main(["pack", "create", "--template", "medicina", "--name", "med", "--lang", "pt-BR"])
    for name in ("metformina", "dipirona", "losartana", "insulina", "omeprazol", "sinvastatina"):
        main(["pack", "add-term", "med", name, "--class", "farmaco", "--variant", f"{name}x"])
    return tmp_path / "packs" / "med.yaml"


def propose(monkeypatch, answer, name="med"):
    monkeypatch.setattr("sys.stdin", io.StringIO(answer + "\n"))
    return main(["pack", "propose", "--whole", name])


def query(url):
    return urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)


def test_the_summary_then_a_yes_writes_and_opens_a_new_pack_issue(tmp_path, monkeypatch, capsys):
    urls = setup(tmp_path, monkeypatch)
    path = med(tmp_path)
    capsys.readouterr()
    assert propose(monkeypatch, "y") == 0
    out = capsys.readouterr().out
    assert 'What would be proposed to the packs repository, as "New pack: med":' in out
    assert "  pack      med 0.1.6 (pt-BR)" in out
    assert "  field     medicina: Medicine: diseases, drugs, procedures, anatomy, exams." in out
    assert "  classes   doenca, farmaco, procedimento, anatomia, exame" in out
    assert "  terms     6" in out and "    metformina  (farmaco)  variants: metforminax" in out
    assert "… and 1 more" in out and "sinvastatina" not in out.split("… and 1 more")[0]
    written = tmp_path / "contributions" / "med-0.1.6.yaml"
    assert written.read_bytes() == path.read_bytes()
    (url,) = urls
    fields = query(url)
    assert fields["title"] == ["New pack: med"]
    body = fields["body"][0]
    assert "<details><summary>med-0.1.6.yaml</summary>" in body and path.read_text(encoding="utf-8") in body


def test_declining_writes_and_opens_nothing(tmp_path, monkeypatch, capsys):
    urls = setup(tmp_path, monkeypatch)
    med(tmp_path)
    assert propose(monkeypatch, "n") == 0
    assert "nothing written." in capsys.readouterr().out
    assert not (tmp_path / "contributions").exists() and urls == []


def test_a_pack_the_repository_has_is_an_update(tmp_path, monkeypatch, capsys):
    repo = tmp_path / "repo"
    (repo / "med").mkdir(parents=True)
    pack = repo / "med" / "pack.yaml"
    pack.write_text("language: pt-BR\nterms: []\n", encoding="utf-8")
    entry = {"name": "med", "version": "0.1.0", "language": "pt-BR", "description": "d",
             "path": "med/pack.yaml", "sha256": hashlib.sha256(pack.read_bytes()).hexdigest()}
    (repo / "index.json").write_text(json.dumps({"packs": [entry]}), encoding="utf-8")
    urls = setup(tmp_path, monkeypatch, index=(repo / "index.json").as_uri())
    med(tmp_path)
    assert propose(monkeypatch, "y") == 0
    assert query(urls[0])["title"] == ["Update: med"]


def test_offline_a_bundled_pack_is_an_update_and_too_long_for_a_link(tmp_path, monkeypatch, capsys):
    urls = setup(tmp_path, monkeypatch, opened=False)
    assert propose(monkeypatch, "y", "financas-ptbr") == 0
    out = capsys.readouterr().out
    assert "  field     (not recorded)" in out and "open this link to submit it as an issue:" in out
    fields = query(urls[0])
    assert fields["title"] == ["Update: financas-ptbr"]
    assert "too long for a link: attach `financas-ptbr-" in fields["body"][0]


def test_the_menu_contributes_a_pack(tmp_path, monkeypatch, capsys):
    urls = setup(tmp_path, monkeypatch)
    med(tmp_path)
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["6", "8", "2", "y", "b", "q"])
    assert "Propose this pack? [y/N]" in out and len(urls) == 1
