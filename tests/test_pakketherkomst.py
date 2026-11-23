"""De korte vorm van de buildcommit (#1123): één plek voor /version en het manifest van een antwoord of rapport."""

from core.pakketherkomst import korte_commit


def test_korte_commit_is_de_eerste_acht_tekens_van_de_volledige_commit():
    assert korte_commit("7d3488aa0da386a087f6363b3f2ffa40049f604b") == "7d3488aa"
    assert korte_commit("021632f") == "021632f"


def test_zonder_commit_is_er_geen_korte_commit():
    assert korte_commit(None) is None
    assert korte_commit("") is None
