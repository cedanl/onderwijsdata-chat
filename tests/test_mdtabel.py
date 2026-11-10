"""De cellen van een markdowntabel met hun kolomkop, labelcellen en de tekst ervoor (#1002)."""

from agent.mdtabel import cellen, tabelcellen

_TEKST = (
    "Het diplomaresultaat was:\n\n"
    "| Studiejaar | Instelling | Alle roc's |\n|---|---:|---:|\n"
    "| 2022/23 | **71,2%** | 70,4% |\n"
    "  | 2023/24 | 71,3% | 71,9% |  \n\n"
    "Daarna niets."
)


def test_elke_cel_staat_op_haar_plek_in_de_tekst():
    gevonden = tabelcellen(_TEKST)

    assert [c.tekst for c in gevonden] == ["2022/23", "71,2%", "70,4%", "2023/24", "71,3%", "71,9%"]
    assert all(_TEKST[c.begin : c.einde].strip(" *") == c.tekst for c in gevonden)


def test_een_cel_kent_haar_kop_labels_en_de_tekst_ervoor():
    cel = tabelcellen(_TEKST)[2]

    assert (cel.kop, cel.labels, cel.rij) == ("Alle roc's", ("2022/23",), ("2022/23", "71,2%", "70,4%"))
    assert cel.context == "Alle roc's 2022/23"
    assert cel.ervoor == "Het diplomaresultaat was:\n\nStudiejaar | Instelling | Alle roc's"


def test_een_rij_met_meer_cellen_dan_de_kop_heeft_een_lege_kop():
    [*_, laatste] = tabelcellen("| A |\n|---|\n| x | 1.234 |")
    assert (laatste.tekst, laatste.kop) == ("1.234", "")


def test_cellen_blijven_zoals_ze_waren():
    assert cellen("  | a | **b** |  ") == ("a", "b")
    assert cellen("a | b") == ("a", "b")
    assert cellen("| a | | c |") == ("a", "", "c")


def test_een_tabel_in_een_codeblok_heeft_geen_cellen():
    assert tabelcellen("```\n| A |\n|---|\n| 1.234 |\n```") == []
