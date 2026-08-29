from app.models import SourceStance
from app.services.source_synthesis import best_passage, classify_passage_stance


CLAIM = "The Great Wall of China is visible from the Moon with the naked eye."


def test_question_heading_does_not_beat_explicit_answer() -> None:
    text = (
        "Is it Really Possible to See the Great Wall of China from Space with a Naked Eye? "
        "This question has been repeated for decades. "
        "Obviously, it would be even less likely to see the Great Wall from the Moon, because the visual acuity required would be far beyond normal human vision."
    )
    passage, relevance = best_passage(CLAIM, text)
    assert passage is not None
    assert "less likely" in passage.lower() or "visual acuity" in passage.lower()
    assert not passage.strip().endswith("?")
    # Raw lexical overlap remains modest because the answer paraphrases
    # "visible with the naked eye" as a visual-acuity limitation.
    assert relevance >= 0.4


def test_debunked_claim_is_recognized_as_contradiction() -> None:
    passage = (
        "The claim that the Great Wall of China is the only man-made object visible from the Moon "
        "or outer space has been debunked many times."
    )
    stance, confidence = classify_passage_stance(CLAIM, passage, 0.9)
    assert stance == SourceStance.CONTRADICTS
    assert confidence >= 0.8


def test_myth_of_negative_claim_does_not_flip_in_wrong_direction() -> None:
    claim = "The Great Wall of China is not visible from low Earth orbit."
    passage = "The myth that the Great Wall of China is not visible from low Earth orbit is incorrect."
    stance, _ = classify_passage_stance(claim, passage, 0.9)
    assert stance == SourceStance.CONTRADICTS


def test_short_question_only_remains_unclear() -> None:
    passage = "Is the Great Wall of China visible from the Moon with the naked eye?"
    stance, confidence = classify_passage_stance(CLAIM, passage, 1.0)
    assert stance == SourceStance.UNCLEAR
    assert confidence == 0.0
