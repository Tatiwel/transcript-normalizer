"""D-007: matching runs over the joined text, not caption line by caption line."""

from transcript_normalizer.core.pack import fold


def line_at(transcript, timestamp):
    return next(l for l in transcript.lines if l.timestamp == timestamp)


def test_ser_mig_is_one_annotation_across_two_caption_lines(transcript, annotations):
    before = line_at(transcript, "24:48")
    after = line_at(transcript, "24:51")
    assert before.text.endswith("que tem que ser")
    assert after.text.startswith("MIG,")

    # Low-band marks straddle the break too; only the applied one is the correction.
    crossing = [
        a
        for a in annotations
        if a.applied
        and [l.timestamp for l in transcript.spans(a.start, a.end)] == ["24:48", "24:51"]
    ]
    assert len(crossing) == 1, [(a.original, a.term) for a in crossing]

    a = crossing[0]
    assert a.term == "CEMIG"
    assert fold(a.original) == "ser mig"
    assert transcript.text[a.start : a.end] == a.original
    # The break itself is inside the annotation: it starts on one line, ends on the next.
    assert a.start < before.end < a.end
