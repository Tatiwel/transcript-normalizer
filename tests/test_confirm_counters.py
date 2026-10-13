"""D-085: applied medium-band corrections and ask-band suggestions are counted apart."""

import yaml

from transcript_normalizer.cli import main
from transcript_normalizer.runs import NORMALIZED_FILE, REPORT_FILE

TERMS = [
    {"term": "BR Partners", "class": "companhia"},
    {"term": "fluxo de caixa", "class": "conceito"},
]


def normalized(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pack = tmp_path / "p.yaml"
    pack.write_text(yaml.safe_dump({"language": "pt-BR", "version": "test", "terms": TERMS}), "utf-8")
    caption = tmp_path / "legenda.txt"
    # `fluxo de caixo`: fuzzy, medium, applied. `Berry Portene`: phonetic, ask, not applied.
    caption.write_text("0:01 o fluxo de caixo melhorou\n0:05 a Berry Portene subiu\n", "utf-8")
    out_dir = tmp_path / "run"
    assert main([str(caption), "--pack", str(pack), "--summary", "--force", "--out", str(out_dir)]) == 0
    return capsys.readouterr().out, out_dir


def test_the_summary_counts_them_apart(tmp_path, monkeypatch, capsys):
    out, run = normalized(tmp_path, monkeypatch, capsys)
    assert "applied, please confirm 1" in out
    assert "suggested, not applied 1" in out
    text = (run / NORMALIZED_FILE).read_text(encoding="utf-8")
    assert "fluxo de caixa" in text and "Berry Portene" in text and "BR Partners" not in text


def test_the_report_has_a_section_for_each(tmp_path, monkeypatch, capsys):
    _, run = normalized(tmp_path, monkeypatch, capsys)
    report = (run / REPORT_FILE).read_text(encoding="utf-8")
    confirm = report.split("applied, please confirm:")[1].split("\n\n")[0]
    suggested = report.split("suggested, not applied:")[1]
    assert "fluxo de caixo" in confirm and "Berry Portene" not in confirm
    assert "Berry Portene" in suggested and "fluxo de caixo" not in suggested


def test_no_suggestion_no_line(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    pack = tmp_path / "p.yaml"
    pack.write_text(yaml.safe_dump({"language": "pt-BR", "version": "test", "terms": TERMS}), "utf-8")
    caption = tmp_path / "legenda.txt"
    caption.write_text("0:01 o fluxo de caixo melhorou\n", "utf-8")
    assert main([str(caption), "--pack", str(pack), "--summary", "--force", "--out", str(tmp_path / "r")]) == 0
    out = capsys.readouterr().out
    assert "applied, please confirm 1" in out and "suggested, not applied" not in out
