"""D-018: how a run directory is derived, and why the stem alone is not enough."""

import shutil

import pytest

from transcript_normalizer.cli import main
from transcript_normalizer.runs import (
    ANNOTATIONS_FILE,
    run_dir,
    run_dir_containing,
    video_id_from_url,
)

from .conftest import CAPTION, FIXTURE_VIDEO_ID, PACK

OTHER_ID = "wxgFO_fyfXg"

NO_URL_HEADER = (
    "# Legenda de video, material bruto para ingestao\n"
    "#\n"
    "# Origem da legenda: automatica (pt)\n"
)
BODY = "0:01 uma linha qualquer\n0:04 outra linha qualquer\n"


def caption_with(tmp_path, name, url, parent=None):
    """A caption whose header declares `url` (or nothing when url is empty)."""
    directory = parent or tmp_path
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    header = NO_URL_HEADER + (f"# URL: {url}\n" if url else "")
    path.write_text(header + BODY, encoding="utf-8")
    return path


# --------------------------------------------------------------- derivation


def test_1_a_caption_already_in_a_run_directory_keeps_it(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    inside = caption_with(
        tmp_path, "legenda.txt", f"https://youtu.be/{FIXTURE_VIDEO_ID}",
        parent=tmp_path / "runs" / OTHER_ID,
    )
    # The header says one video and the directory says another: the directory wins.
    assert run_dir(inside, url=f"https://youtu.be/{FIXTURE_VIDEO_ID}") == (
        tmp_path / "runs" / OTHER_ID
    )
    assert run_dir_containing(inside) == tmp_path / "runs" / OTHER_ID


def test_2_the_header_url_names_the_run_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    caption = caption_with(tmp_path, "legenda.txt", f"https://youtu.be/{OTHER_ID}")
    assert run_dir(caption, url=f"https://youtu.be/{OTHER_ID}") == (
        tmp_path / "runs" / OTHER_ID
    )


def test_3_without_either_it_falls_back_to_the_input_stem(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    caption = caption_with(tmp_path, "entrevista.txt", "")
    assert run_dir(caption) == tmp_path / "runs" / "entrevista"
    # An url with nothing id-shaped in it is no better than no url at all.
    assert run_dir(caption, url="https://example.invalid/some/page") == (
        tmp_path / "runs" / "entrevista"
    )


def test_out_still_wins_over_all_three(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    caption = caption_with(
        tmp_path, "legenda.txt", f"https://youtu.be/{OTHER_ID}",
        parent=tmp_path / "runs" / FIXTURE_VIDEO_ID,
    )
    assert run_dir(caption, out=tmp_path / "elsewhere", url=f"https://youtu.be/{OTHER_ID}") == (
        tmp_path / "elsewhere"
    )


def test_a_path_directly_under_runs_is_not_inside_a_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    loose = caption_with(tmp_path, "legenda.txt", "", parent=tmp_path / "runs")
    assert run_dir_containing(loose) is None
    assert run_dir(loose) == tmp_path / "runs" / "legenda"


@pytest.mark.parametrize(
    "url, expected",
    [
        (f"https://youtu.be/{FIXTURE_VIDEO_ID}", FIXTURE_VIDEO_ID),
        (f"https://www.youtube.com/watch?v={OTHER_ID}", OTHER_ID),
        (f"https://www.youtube.com/watch?v={OTHER_ID}&t=42s", OTHER_ID),
        (f"https://youtube.com/shorts/{OTHER_ID}", OTHER_ID),
        (f"https://youtu.be/{OTHER_ID}?t=30", OTHER_ID),
        ("https://example.invalid/video/one", ""),
        ("https://youtu.be/tooshort", ""),
        ("", ""),
    ],
)
def test_video_ids_are_read_out_of_the_usual_url_shapes(url, expected):
    assert video_id_from_url(url) == expected


# --------------------------------------------------------------- the bug


def test_normalizing_a_fetched_caption_writes_back_into_its_own_run(tmp_path, monkeypatch):
    """The reported bug: runs/X/legenda.txt must not normalize into runs/legenda/."""
    monkeypatch.chdir(tmp_path)
    fetched = tmp_path / "runs" / OTHER_ID / "legenda.txt"
    fetched.parent.mkdir(parents=True)
    shutil.copy(CAPTION, fetched)  # its header declares a *different* video

    assert main([str(fetched), "--pack", str(PACK)]) == 0

    assert (tmp_path / "runs" / OTHER_ID / ANNOTATIONS_FILE).exists()
    assert not (tmp_path / "runs" / "legenda").exists()
    assert not (tmp_path / "runs" / FIXTURE_VIDEO_ID).exists()
    assert sorted(p.name for p in (tmp_path / "runs").iterdir()) == [OTHER_ID]


def test_two_videos_do_not_land_in_the_same_run_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    first = caption_with(tmp_path / "a", "legenda.txt", f"https://youtu.be/{OTHER_ID}")
    second = caption_with(
        tmp_path / "b", "legenda.txt", f"https://youtu.be/{FIXTURE_VIDEO_ID}"
    )

    assert main([str(first), "--pack", str(PACK)]) == 0
    assert main([str(second), "--pack", str(PACK)]) == 0

    assert sorted(p.name for p in (tmp_path / "runs").iterdir()) == sorted(
        [OTHER_ID, FIXTURE_VIDEO_ID]
    )
    assert not (tmp_path / "runs" / "legenda").exists()
