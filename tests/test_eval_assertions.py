"""De eval-assertions moeten fout antwoord afkeuren (#9, externe review bevinding 3).

De oude assertie vergeleek twee verzamelingen en liet drie fouten door: omgedraaide jaren,
een verzonnen getal, en één ontbrekend jaar. Elk daarvan staat hier als test die moet falen.
"""
from tests.eval_assertions import ungrounded_numbers, unpaired_years

TRUTH = {2021: 5000, 2022: 5500, 2023: 6000}
TOOL = [{"rijen": [{"STUDIEJAAR": 2021, "AANTAL": 5000}, {"STUDIEJAAR": 2022, "AANTAL": 5500},
                   {"STUDIEJAAR": 2023, "AANTAL": 6000}]}]


def test_correct_answer_passes_both_checks():
    answer = "In 2021 waren het 5.000, in 2022 5.500 en in 2023 6.000 eerstejaars."
    assert unpaired_years(answer, TRUTH) == []
    assert ungrounded_numbers(answer, TOOL) == set()


def test_reversed_years_are_refused():
    answer = "In 2021 waren het 6.000, in 2022 5.500 en in 2023 5.000 eerstejaars."
    assert unpaired_years(answer, TRUTH)


def test_an_invented_number_is_refused():
    answer = "In 2021 waren het 5.000, in 2022 5.500 en in 2023 6.000; landelijk 91.500."
    assert unpaired_years(answer, TRUTH) == []
    assert ungrounded_numbers(answer, TOOL) == {"91500"}


def test_a_missing_year_is_refused_and_one_error_is_not_tolerated():
    answer = "In 2021 waren het 5.000 en in 2022 5.500 eerstejaars."
    assert unpaired_years(answer, TRUTH) == ["Jaar 2023 niet gekoppeld aan 6,000 in antwoord"]


def test_years_in_the_answer_are_not_numbers_without_a_source():
    assert ungrounded_numbers("Sinds 2019 is dat 5.000 in 2021.", TOOL) == set()


def test_an_invented_number_with_a_space_separator_is_refused():
    """gpt-oss schrijft 91 500 met (smalle) spatie; de eval zag dat niet als getal (audit 11)."""
    for scheiding in (" ", " ", " "):
        answer = f"In 2021 waren het 5{scheiding}000; landelijk 91{scheiding}500."
        assert ungrounded_numbers(answer, TOOL) == {"91500"}
