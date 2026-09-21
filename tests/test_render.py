"""D-016: normalized.txt is a view over the stand-off layer, not a new source."""

import shutil

from transcript_normalizer import read_caption, resolve_overlaps
from transcript_normalizer.cli import main
from transcript_normalizer.core.render import TIMESTAMP_GAP, render_lines, render_normalized
from transcript_normalizer.core.standoff import applied
from transcript_normalizer.runs import NORMALIZED_FILE, TO_CONFIRM_FILE, review_dir, run_dir

from .conftest import CAPTION, PACK


def resolved(annotations):
    return applied(resolve_overlaps(annotations))


def test_one_line_per_caption_line_with_the_same_timestamps(transcript, annotations):
    lines = render_lines(transcript, resolved(annotations))
    assert len(lines) == len(transcript.lines)
    assert [stamp for stamp, _ in lines] == [l.timestamp for l in transcript.lines]


def test_normalized_file_matches_the_caption_line_for_line(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)
    assert main([str(caption), "--pack", str(PACK)]) == 0

    transcript = read_caption(caption)
    rendered = (run_dir(caption) / NORMALIZED_FILE).read_text(encoding="utf-8")
    lines = rendered.splitlines()

    assert len(lines) == len(transcript.lines)
    assert [l.split(TIMESTAMP_GAP)[0] for l in lines] == [
        l.timestamp for l in transcript.lines
    ]
    # The original is kept beside the view and is byte-identical (D-004).
    assert (run_dir(caption) / "legenda.txt").read_bytes() == CAPTION.read_bytes()


def test_every_applied_replacement_lands_on_its_line(transcript, annotations):
    rendered = render_lines(transcript, resolved(annotations))
    index = {line.index: i for i, line in enumerate(transcript.lines)}

    for a in resolved(annotations):
        line_index, _stamp = transcript.locate(a.start)
        _, body = rendered[index[line_index]]
        assert a.replacement in body, (a.original, a.replacement, body)


def test_a_cross_line_annotation_is_written_where_it_starts(transcript, annotations):
    rendered = dict(render_lines(transcript, resolved(annotations)))
    # `ser MIG` spans 24:48/24:51; the correction goes on the first line only.
    assert rendered["24:48"].endswith("que tem que CEMIG")
    assert rendered["24:51"].startswith(", não é?")


def test_nothing_is_substituted_on_the_manter_lines(transcript, annotations):
    rendered = dict(render_lines(transcript, resolved(annotations)))
    by_stamp = {l.timestamp: l.text for l in transcript.lines}
    for stamp in ("7:30", "10:27"):
        assert rendered[stamp] == by_stamp[stamp]


def test_to_confirm_is_the_text_the_prompt_shows(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    caption = tmp_path / "legenda.txt"
    shutil.copy(CAPTION, caption)
    main([str(caption), "--pack", str(PACK)])

    text = (review_dir(run_dir(caption)) / TO_CONFIRM_FILE).read_text(encoding="utf-8")
    assert "confirm as variants of CEMIG? [y]es / [n]o / [s]kip:" in text
    assert "variants: dos 10, mês caiu, nesse ramo, e caiu" in text
    # One block per term in the medium band, in the order the loop would ask.
    assert text.count("[y]es / [n]o / [s]kip:") == 4


def test_render_is_a_pure_view(transcript, annotations):
    before = transcript.text
    render_normalized(transcript, resolved(annotations))
    assert transcript.text == before
