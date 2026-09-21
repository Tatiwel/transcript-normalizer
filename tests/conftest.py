from pathlib import Path

import pytest

from transcript_normalizer import find_annotations, load_pack, read_caption

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "R2Qgz8tFWVI"
CAPTION = FIXTURE / "legenda.txt"
PACK = FIXTURE / "pack.yaml"
GOLD = FIXTURE / "gold.csv"


@pytest.fixture(scope="session")
def pack():
    return load_pack(PACK)


@pytest.fixture(scope="session")
def transcript():
    return read_caption(CAPTION)


@pytest.fixture(scope="session")
def annotations(transcript, pack):
    return find_annotations(transcript, pack)
