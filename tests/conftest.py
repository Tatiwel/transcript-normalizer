import sys
from pathlib import Path

import pytest

from transcript_normalizer import find_annotations, load_pack, read_caption, runs
from transcript_normalizer.runs import DATA_DIR_ENV, run_dir

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "R2Qgz8tFWVI"
CAPTION = FIXTURE / "legenda.txt"
PACK = FIXTURE / "pack.yaml"
GOLD = FIXTURE / "gold.csv"


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path_factory, monkeypatch):
    """D-061: no test reads the developer's config.toml or TRANSCRIPT_NORMALIZER_HOME,
    and no test opens a real folder dialog (tkinter reads as not installed)."""
    config = tmp_path_factory.mktemp("config") / runs.CONFIG_FILE
    monkeypatch.setattr(runs, "config_file", lambda: config)
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    monkeypatch.setitem(sys.modules, "tkinter", None)
    return config


@pytest.fixture(scope="session")
def pack():
    return load_pack(PACK)


@pytest.fixture(scope="session")
def transcript():
    return read_caption(CAPTION)


@pytest.fixture(scope="session")
def annotations(transcript, pack):
    return find_annotations(transcript, pack)


#: The video the fixture caption came from; its header declares the url.
FIXTURE_VIDEO_ID = "R2Qgz8tFWVI"


def output_dir(caption, out=None):
    """Where a run over `caption` writes, D-018 derivation and all."""
    return run_dir(caption, out, read_caption(caption).header_field("URL"))


def medium_order():
    """The fixture's medium band as `--confirm` asks it: [(term, variant), ...].

    Derived from the loop's own grouping, so a matcher change that reshapes the
    band does not have to be copied into every test that scripts answers.
    """
    from transcript_normalizer import resolve_overlaps
    from transcript_normalizer.cli import confirm_groups, variant_groups
    from transcript_normalizer.core.pack import Learned

    transcript = read_caption(CAPTION)
    found = resolve_overlaps(find_annotations(transcript, load_pack(PACK, learned=Learned())))
    return [
        (term, variant)
        for term, group in confirm_groups(found)
        for variant, _ in variant_groups(group)
    ]


def answers_for(term, answers):
    """`answers` for `term`'s variants, after skipping every variant asked before it."""
    before = [t for t, _ in medium_order()]
    return ["s"] * before.index(term) + list(answers)
