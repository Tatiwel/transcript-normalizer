"""D-069: three-way pack merge, on a synthetic base, upstream and mine.

The pack `med` comes from a file:// packs repository. `pack copy` keeps its
base; the copy is then edited ("mine") and the repository publishes a newer
version ("upstream"). Each term below is one row of D-069's tables.
"""

import hashlib
import io
import json
import urllib.parse

import pytest
import yaml

from transcript_normalizer import contribute, interactive, merge, packfiles, registry
from transcript_normalizer.cli import main
from transcript_normalizer.core.pack import Learned, save_learned

from .test_interactive import menu

CLASSES = ["farmaco", "doenca", "exame"]


def t(term, klass="farmaco", **forms):
    return {"term": term, "class": klass, **{k: list(v) for k, v in forms.items()}}


BASE = [
    t("Alpha", variants=["alfax"]),                                  # nobody changed it
    t("Bravo", variants=["bravox"]),                                 # changed upstream only
    t("Charlie", variants=["charliex"]),                             # changed by me only
    t("Delta", aliases=["deltinha"], variants=["deltax", "deltaz"]),  # both, different fields
    t("Echo"),                                                       # class changed on both sides
    t("Foxtrot", variants=["foxtrotx"]),                             # removed upstream, untouched by me
    t("Golf", variants=["golfx"]),                                   # renamed upstream; I added to it
    t("Hotel", variants=["hotelx", "hotelz"]),                       # upstream removes one I confirmed
    t("India"),                                                      # upstream adds one I rejected
]
UPSTREAM = [
    t("Alpha", variants=["alfax"]),
    t("Bravo", variants=["bravox", "bravoy", "zuluz"]),
    t("Charlie", variants=["charliex"]),
    t("Delta", "doenca", aliases=["deltinha"], variants=["deltax"]),
    t("Echo", "doenca"),
    t("Golfe", variants=["golfx", "Golf"]),
    t("Hotel", variants=["hotelx"]),
    t("India", variants=["indiax"]),
    t("Juliet", "doenca"),                                           # only upstream: added
    t("Paracetamoll"),                                               # upstream's new, near mine
]
MINE = [
    t("Alpha", variants=["alfax"]),
    t("Bravo", variants=["bravox"]),
    t("Charlie", variants=["charliex", "charliey", "zuluz"]),        # zuluz: Bravo's upstream
    t("Delta", aliases=["deltinha"], variants=["deltax", "deltaz", "deltay"]),
    t("Echo", "exame"),
    t("Foxtrot", variants=["foxtrotx"]),
    t("Golf", variants=["golfx", "golfy"]),
    t("Hotel", variants=["hotelx", "hotelz"]),
    t("India"),
    t("Kilo", "exame", variants=["kilox", "Juliet"]),               # only mine; Juliet: upstream's name
    t("Paracetamol"),                                                # my new, near upstream's
]


def pack_text(terms, version):
    data = {"language": "pt-BR", "version": version, "classes": CLASSES, "terms": terms}
    return "# med: a synthetic pack for D-069.\n" + yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def publish(repo, version, text):
    (repo / "med").mkdir(parents=True, exist_ok=True)
    path = repo / "med" / "pack.yaml"
    path.write_text(text, encoding="utf-8")
    entry = {"name": "med", "version": version, "language": "pt-BR", "description": "medicine",
             "path": "med/pack.yaml", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (repo / "index.json").write_text(json.dumps({"packs": [entry]}), encoding="utf-8")
    return (repo / "index.json").as_uri()


@pytest.fixture
def triple(tmp_path, monkeypatch, capsys):
    """Base 0.1.0 installed and copied; mine edited; upstream 0.2.0 published."""
    monkeypatch.chdir(tmp_path)
    repo = tmp_path / "repo"
    monkeypatch.setenv(registry.INDEX_ENV, publish(repo, "0.1.0", pack_text(BASE, "0.1.0")))
    assert main(["pack", "install", "med"]) == 0
    assert main(["pack", "copy", "med"]) == 0
    mine = tmp_path / "packs" / "med.yaml"
    data = yaml.safe_load(mine.read_text(encoding="utf-8"))
    assert data["based_on"] == "med@0.1.0" and data["local_edits"] == 0
    mine.write_text(merge.with_provenance(pack_text(MINE, "0.1.4"), "med", "0.1.0", 4), encoding="utf-8")
    save_learned(Learned().confirm("Hotel", "hotelz").reject("indiax", "India"),
                 tmp_path / "packs" / "med.learned.yaml")
    publish(repo, "0.2.0", pack_text(UPSTREAM, "0.2.0"))
    capsys.readouterr()
    return mine


def run_merge(monkeypatch, *flags, answers=""):
    monkeypatch.setattr("sys.stdin", io.StringIO(answers))
    return main(["pack", "merge", "med", *flags])


def terms(path):
    return {x["term"]: x for x in yaml.safe_load(path.read_text(encoding="utf-8"))["terms"]}


# ------------------------------------------------------------------ the table, with --yes-theirs and --yes-mine


def test_every_row_taking_theirs(triple, monkeypatch, capsys):
    assert run_merge(monkeypatch, "--yes-theirs") == 0
    out = capsys.readouterr().out
    got = terms(triple)
    assert got["Alpha"] == t("Alpha", variants=["alfax"])                       # unchanged
    assert got["Bravo"]["variants"] == ["bravox", "bravoy", "zuluz"]            # upstream's
    assert got["Charlie"]["variants"] == ["charliex", "charliey"]               # mine; zuluz went to Bravo
    assert got["Delta"] == t("Delta", "doenca", aliases=["deltinha"], variants=["deltax", "deltay"])
    assert "Delta: upstream removed the variant 'deltaz'" in out                 # a notice
    assert got["Echo"]["class"] == "doenca"                                      # class conflict: theirs
    assert "Foxtrot" not in got and "Foxtrot: removed upstream" in out
    assert "Golf" not in got and set(got["Golfe"]["variants"]) == {"golfx", "Golf", "golfy"}
    assert "hotelz" not in got["Hotel"]["variants"]                              # learned: theirs
    assert got["India"]["variants"] == ["indiax"]
    assert got["Juliet"] == t("Juliet", "doenca")                               # only upstream
    assert got["Kilo"]["variants"] == ["kilox"]                                 # its 'Juliet' dropped
    assert "Paracetamoll" in got and "Paracetamol" not in got                    # duplicate: theirs
    data = yaml.safe_load(triple.read_text(encoding="utf-8"))
    assert data["based_on"] == "med@0.2.0" and data["version"] == "0.2.1" and data["local_edits"] > 0
    assert (triple.parent / ".bases" / "med@0.2.0.yaml").exists()
    assert not (triple.parent / "med.merge-pending.yaml").exists()


def test_every_row_keeping_mine(triple, monkeypatch, capsys):
    assert run_merge(monkeypatch, "--yes-mine") == 0
    out = capsys.readouterr().out
    got = terms(triple)
    assert got["Echo"]["class"] == "exame"
    assert "Golf" in got and "golfy" in got["Golf"]["variants"] and "Golfe" not in got
    assert "Paracetamol" in got and "Paracetamoll" not in got
    assert "zuluz" in got["Charlie"]["variants"] and "zuluz" not in got["Bravo"]["variants"]
    assert "hotelz" in got["Hotel"]["variants"] and "indiax" not in got["India"].get("variants", [])
    # Mine cannot win over upstream's canonical name: decided later.
    assert "Juliet" in got["Kilo"]["variants"]
    pending = yaml.safe_load((triple.parent / "med.merge-pending.yaml").read_text(encoding="utf-8"))
    assert [c["kind"] for c in pending["conflicts"]] == ["form"]
    assert "conflicts pending        1" in out


def test_the_summary_and_learned_layer_report(triple, monkeypatch, capsys):
    assert run_merge(monkeypatch, "--yes-theirs") == 0
    out = capsys.readouterr().out
    assert "Merging med: yours 0.1.4 with the repository 0.2.0, three-way, from 0.1.0" in out
    for line in ("added from upstream      2  Juliet, Paracetamoll", "removed                  1  Foxtrot",
                 "conflicts resolved       7", "conflicts pending        0"):
        assert line in out
    assert "contradiction: you rejected 'indiax' for India; the pack has it" in out
    assert (triple.parent / "med.learned.yaml").read_text(encoding="utf-8").count("hotelz") == 1  # untouched


# ------------------------------------------------------------------ asked one at a time


def test_conflicts_are_asked_one_at_a_time(triple, monkeypatch, capsys):
    # Every conflict answered with its last option, "Decide later".
    assert run_merge(monkeypatch, answers="l\n" * 7) == 0
    out = capsys.readouterr().out
    assert out.count("Which one?") == 7
    assert "Conflict 1: Echo: the class differs on both sides" in out
    assert "  base      Echo  (farmaco)" in out and "  mine      Echo  (exame)" in out
    assert "  theirs    Echo  (doenca)" in out
    assert "   k. Keep both" in out  # only for the duplicate, whose forms do not collide
    assert out.count("   l. Decide later") == 7
    pending = yaml.safe_load((triple.parent / "med.merge-pending.yaml").read_text(encoding="utf-8"))
    assert len(pending["conflicts"]) == 7
    assert terms(triple)["Echo"]["class"] == "exame"  # later leaves mine


def test_context_from_the_users_runs(triple, tmp_path, monkeypatch, capsys):
    run = tmp_path / "runs" / "abcdefghijk"
    run.mkdir(parents=True)
    (run / "legenda.txt").write_text("# header\n0:01 tomei Echo ontem\n0:05 e Echo de novo\n", encoding="utf-8")
    run_merge(monkeypatch, "--yes-theirs")
    out = capsys.readouterr().out
    assert "  in your runs:\n    abcdefghijk  0:01 tomei Echo ontem\n    abcdefghijk  0:05 e Echo de novo" in out


# ------------------------------------------------------------------ safety


def test_a_backup_is_written_first(triple, monkeypatch, capsys):
    before = triple.read_bytes()
    assert run_merge(monkeypatch, "--yes-theirs") == 0
    (backup,) = triple.parent.glob("med.yaml.bak-*")
    assert backup.read_bytes() == before
    assert f"backup: {backup}" in capsys.readouterr().out


def test_dry_run_writes_nothing(triple, monkeypatch, capsys):
    before = sorted(p.name for p in triple.parent.rglob("*"))
    text = triple.read_bytes()
    assert run_merge(monkeypatch, "--dry-run") == 0
    out = capsys.readouterr().out
    assert "Would be merged:" in out and "(would be asked)" in out and "--dry-run: nothing written." in out
    assert triple.read_bytes() == text and sorted(p.name for p in triple.parent.rglob("*")) == before


def test_nothing_to_merge_when_upstream_is_not_newer(triple, tmp_path, monkeypatch, capsys):
    publish(tmp_path / "repo", "0.1.0", pack_text(BASE, "0.1.0"))
    assert run_merge(monkeypatch) == 0
    assert "nothing to merge" in capsys.readouterr().out


# ------------------------------------------------------------------ two-way


def test_two_way_without_a_base(triple, monkeypatch, capsys):
    data = yaml.safe_load(triple.read_text(encoding="utf-8"))
    del data["based_on"], data["local_edits"]
    data["terms"].append(t("Mike", aliases=["mikey"]))
    triple.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    upstream = [*UPSTREAM, t("Mike", variants=["mikey"])]
    publish(triple.parents[1] / "repo", "0.2.0", pack_text(upstream, "0.2.0"))
    assert run_merge(monkeypatch, "--yes-theirs") == 0
    out = capsys.readouterr().out
    assert "two-way (no base)" in out
    got = terms(triple)
    assert "Foxtrot" in got and "Golf" in got and "Golfe" in got  # union: nothing is a removal
    assert got["Echo"]["class"] == "doenca"  # a class difference is a conflict
    assert "'mikey' is an alias in yours, a variant in theirs" in out
    assert got["Mike"] == t("Mike", variants=["mikey"])
    assert yaml.safe_load(triple.read_text(encoding="utf-8"))["based_on"] == "med@0.2.0"  # gains a base


def test_the_base_snapshot_missing_is_two_way(triple, monkeypatch, capsys):
    (triple.parent / ".bases" / "med@0.1.0.yaml").unlink()
    assert run_merge(monkeypatch, "--yes-theirs", "--dry-run") == 0
    assert "merging two-way" in capsys.readouterr().out


# ------------------------------------------------------------------ detection


def test_installed_packs_shows_merge_available(triple, capsys):
    assert main(["pack", "list", "--installed"]) == 0
    out = capsys.readouterr().out
    line = next(x for x in out.splitlines() if x.startswith("med "))
    assert line.rstrip().endswith("↑ merge available (0.2.0)")
    assert "`transcript-normalizer pack merge <name>` merges it" in out


def test_pack_update_offers_the_merge_and_never_merges_unasked(triple, capsys):
    before = triple.read_bytes()
    assert main(["pack", "update"]) == 0
    out = capsys.readouterr().out
    assert "med 0.2.0 is available; your copy is based on 0.1.0 with 4 local edits." in out
    assert "`transcript-normalizer pack merge med` merges it" in out
    assert triple.read_bytes() == before


NOTICE = ("med 0.2.0 is available; your copy is based on 0.1.0 with 4 local edits. "
          "Packs → Merge an update merges it.")


def test_the_menu_says_so_once_and_never_asks(triple, tmp_path, monkeypatch, capsys):
    """D-069, amended: a one-line notice when the menu is drawn; no question at startup."""
    monkeypatch.setattr(interactive, "MERGE_CHECK_IN_BACKGROUND", False)
    before = triple.read_bytes()
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["5", "q"])
    assert out.count(NOTICE) == 1  # drawn twice, said once
    assert "Merge? [y/N]" not in out
    assert triple.read_bytes() == before


def test_packs_offers_the_merge(triple, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(interactive, "MERGE_CHECK_IN_BACKGROUND", False)
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["6", "1", *(["l"] * 7), "b", "q"])
    assert "Merge an update" in out and "med 0.2.0" in out
    assert "Merging med" in out and yaml.safe_load(triple.read_text(encoding="utf-8"))["based_on"] == "med@0.2.0"


def test_the_first_screen_never_waits_for_the_index(triple, tmp_path, monkeypatch, capsys):
    """Offline (the index never answers), the menu is drawn at once, without the notice."""
    import time

    monkeypatch.setattr(packfiles, "index_within", lambda seconds, url=None: time.sleep(seconds))
    started = time.monotonic()
    _, out, _ = menu(tmp_path, monkeypatch, capsys, ["q"])
    assert time.monotonic() - started < 1
    assert "What would you like to do?" in out and NOTICE not in out


def test_the_index_is_cached_for_a_day(triple, monkeypatch):
    url = registry.index_url()
    assert packfiles.index_cache().parent == triple.parent  # packs/ under the data directory
    assert packfiles.index_cached_within(3)["med"].version == "0.2.0"
    assert packfiles.index_cache().exists()
    monkeypatch.setattr(packfiles, "index_within", lambda seconds, url=None: None)  # offline now
    assert packfiles.index_cached_within(3)["med"].version == "0.2.0"  # from the cache
    later = __import__("time").time() + packfiles.INDEX_CACHE_SECONDS + 1
    assert packfiles.cached_index(url, now=later) is None  # a day old: read again
    assert packfiles.cached_index("file:///elsewhere/index.json") is None  # another index


def test_edits_count_since_the_base(triple, capsys):
    assert main(["pack", "add-term", "med", "November", "--class", "farmaco"]) == 0
    assert yaml.safe_load(triple.read_text(encoding="utf-8"))["local_edits"] == 5


# ------------------------------------------------------------------ contribution against the base


def test_propose_sends_only_the_diff_against_the_base(triple, monkeypatch, capsys):
    urls = []
    monkeypatch.setattr(contribute.webbrowser, "open", lambda url: urls.append(url) or True)
    monkeypatch.setattr("getpass.getuser", lambda: "ana")
    monkeypatch.setattr("sys.stdin", io.StringIO("y\n"))
    assert main(["pack", "propose", "--whole", "med"]) == 0
    out = capsys.readouterr().out
    assert 'as "med: 6 additions from ana"' in out
    assert "  + term     Kilo  (exame)  variants: kilox, Juliet" in out
    assert "  + variant  charliey -> Charlie" in out and "  ~ class    Echo: farmaco -> exame" in out
    (url,) = urls
    fields = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert fields["title"] == ["med: 6 additions from ana"]
    body = fields["body"][0]
    assert "based_on: med@0.1.0" in body and "Alpha" not in body  # only what changed
    assert (triple.parents[1] / "contributions" / "med-0.1.4-diff.yaml").exists()
