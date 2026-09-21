"""D-004: the transcript is never modified; annotations only point at it."""

from transcript_normalizer import find_annotations, read_caption

from .conftest import CAPTION


def test_text_is_byte_identical_after_normalization(pack):
    before = CAPTION.read_bytes()
    transcript = read_caption(CAPTION)
    text_before = transcript.text

    find_annotations(transcript, pack)

    assert transcript.text == text_before
    assert CAPTION.read_bytes() == before


def test_every_annotation_slice_is_its_original(transcript, annotations):
    assert annotations
    for a in annotations:
        assert transcript.text[a.start : a.end] == a.original


def test_annotations_carry_the_pack_version(pack, annotations):
    assert pack.version
    assert {a.pack_version for a in annotations} == {pack.version}
