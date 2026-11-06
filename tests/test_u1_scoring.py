"""US1.3 Score a model's answer (AC1.3.1-AC1.3.4); rules BR3.1-BR3.5 in u1 rules.md.

Pure functions of `gsm8k.scoring`: no model, no files.
"""

import pytest

from gsm8k.scoring import cut_output, extract_answer, is_correct, score

# --- AC1.3.1: the number after '####', commas stripped (BR3.1, BR3.4) ---


def test_AC1_3_1_strips_commas_after_hash_marks():
    output = " She sells 1,000 cups and 234 more, so 1,000 + 234 = 1,234.\n#### 1,234"
    predicted, correct = score(output, "1234")
    assert predicted == "1234"
    assert correct is True


def test_AC1_3_1_extract_answer_takes_number_after_first_hash_marks():
    assert extract_answer("He pays 3 + 4 = 7 dollars.\n#### 7\nThen 99 more.") == "7"
    assert extract_answer("#### 5\n#### 8") == "5"


def test_AC1_3_1_hash_number_wins_over_later_numbers_in_text():
    predicted, correct = score("Total is 12 eggs.\n#### 12", "12")
    assert predicted == "12"
    assert correct is True


def test_AC1_3_1_gold_with_commas_compares_equal():
    assert is_correct("1234", "1,234") is True
    assert is_correct("1,234", "1234") is True


def test_AC1_3_1_wrong_number_after_hash_marks_is_wrong():
    predicted, correct = score("#### 1,235", "1234")
    assert predicted == "1235"
    assert correct is False


# --- AC1.3.2: no '####' number -> the last number in the scored text (BR3.2, BR3.5) ---


def test_AC1_3_2_takes_last_number_without_hash_marks():
    output = " She has 3 apples and buys 4 more, so she has 7"
    assert extract_answer(output) == "7"
    predicted, correct = score(output, "7")
    assert predicted == "7"
    assert correct is True


def test_AC1_3_2_last_number_with_commas_decimal_and_sign():
    assert is_correct(extract_answer("It costs 2 or maybe 1,500"), "1500") is True
    assert is_correct(extract_answer("The level drops by 1 to -2.5"), "-2.5") is True


def test_AC1_3_2_hash_marks_without_number_fall_back_to_last_number():
    predicted, correct = score("The answer is 42.\n####", "42")
    assert is_correct(predicted, "42")
    assert correct is True


def test_AC1_3_2_cut_output_ends_at_first_answer_line():
    output = " 5 + 3 = 8 apples.\n#### 8\n\nQuestion: Tom has 99 marbles.\nAnswer: #### 99"
    cut = cut_output(output)
    assert cut.rstrip().endswith("#### 8")
    assert "99" not in cut
    assert "Question:" not in cut


def test_AC1_3_2_cut_output_stops_before_a_new_question():
    output = (
        " 3 + 4 = 7 apples.\n\nQuestion: A train goes 60 miles an hour for 2 hours. How far?\nAnswer: 120"
    )
    cut = cut_output(output)
    assert "Question:" not in cut
    assert "120" not in cut
    assert "7 apples" in cut
    # The last-number fallback reads only the text before the stop point.
    predicted, correct = score(output, "7")
    assert is_correct(predicted, "7")
    assert correct is True


def test_AC1_3_2_cut_output_question_before_hash_marks_wins():
    output = " So she has 7 left.\nQuestion: Ann has 5 pens and buys 94.\nAnswer: 5 + 94 = 99\n#### 99"
    cut = cut_output(output)
    assert "#### 99" not in cut
    predicted, correct = score(output, "7")
    assert is_correct(predicted, "7")
    assert correct is True


def test_AC1_3_2_cut_output_without_stop_point_keeps_text():
    assert cut_output(" 3 + 4 = 7") == " 3 + 4 = 7"


# --- AC1.3.3: no number at all -> wrong, and scoring carries on (BR3.3) ---


def test_AC1_3_3_no_number_counts_as_wrong():
    assert extract_answer("I do not know the answer.") is None
    assert extract_answer("") is None
    assert is_correct(None, "5") is False
    assert score("I do not know the answer.", "5") == (None, False)


def test_AC1_3_3_scoring_carries_on_after_an_output_without_number():
    outputs = [
        ("No idea, sorry.", "3"),
        (" 1 + 2 = 3\n#### 3", "3"),
        ("", "4"),
        (" 2 + 2 = 4", "4"),
    ]
    results = [score(output, gold)[1] for output, gold in outputs]
    assert results == [False, True, False, True]


# --- AC1.3.4: numeric comparison (BR3.4) ---


@pytest.mark.parametrize(("output", "gold"), [("72.0", "72"), ("$18", "18"), ("-5", "-5")])
def test_AC1_3_4_numeric_comparison_bare_outputs(output, gold):
    predicted, correct = score(output, gold)
    assert correct is True, (output, gold, predicted)


@pytest.mark.parametrize(("output", "gold"), [("72.0", "72"), ("$18", "18"), ("-5", "-5")])
def test_AC1_3_4_numeric_comparison_after_hash_marks(output, gold):
    predicted, correct = score(f" Working it out.\n#### {output}", gold)
    assert correct is True, (output, gold, predicted)


def test_AC1_3_4_is_correct_reads_both_sides_as_numbers():
    assert is_correct("72.0", "72") is True
    assert is_correct("$18", "18") is True
    assert is_correct("-5", "-5") is True
    assert is_correct("50%", "50") is True
    assert is_correct("72.5", "72") is False
    assert is_correct("5", "-5") is False
    assert is_correct("1,000.50", "$1000.5") is True  # commas and '$' are stripped on both sides
