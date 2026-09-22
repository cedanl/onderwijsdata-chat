"""Validate README claims against actual code configuration."""

import re
from functools import cache
from pathlib import Path

import pytest
from onderwijsdata import catalog as cbs_catalog
from riodata import catalog as rio_catalog

from core import config

README_PATH = Path(__file__).parent.parent / "README.md"


def read_readme() -> str:
    """Read README content."""
    return README_PATH.read_text(encoding="utf-8")


@cache
def catalogus_aantal(leverancier: str) -> int:
    """Aantal datasets per leverancier, uit dezelfde bron als search_catalog leest."""
    if leverancier == "CBS":
        return len(cbs_catalog())
    return sum(
        1 for entry in rio_catalog(source="all")
        if str(entry.get("leverancier", "")).upper() == leverancier
    )


class TestReadmeConsistency:
    """Validate README against code config."""

    def test_max_tool_iterations_matches_config(self):
        """README should show correct MAX_TOOL_ITERATIONS default."""
        readme = read_readme()
        # Find the table row for MAX_TOOL_ITERATIONS
        match = re.search(r"\|\s*`MAX_TOOL_ITERATIONS`\s*\|\s*`(\d+)`", readme)
        assert match, "MAX_TOOL_ITERATIONS not found in README table"
        readme_value = int(match.group(1))
        assert readme_value == config.MAX_TOOL_ITERATIONS, (
            f"README says {readme_value} but config.MAX_TOOL_ITERATIONS is {config.MAX_TOOL_ITERATIONS}"
        )

    def test_cbs_row_limit_matches_config(self):
        """README should show correct CBS_ROW_LIMIT default."""
        readme = read_readme()
        match = re.search(r"\|\s*`CBS_ROW_LIMIT`\s*\|\s*`(\d+)`", readme)
        assert match, "CBS_ROW_LIMIT not found in README table"
        readme_value = int(match.group(1))
        assert readme_value == config.CBS_ROW_LIMIT, (
            f"README says {readme_value} but config.CBS_ROW_LIMIT is {config.CBS_ROW_LIMIT}"
        )

    def test_max_tokens_matches_config(self):
        """README should show correct MAX_TOKENS default."""
        readme = read_readme()
        match = re.search(r"\|\s*`MAX_TOKENS`\s*\|\s*`(\d+)`", readme)
        assert match, "MAX_TOKENS not found in README table"
        readme_value = int(match.group(1))
        assert readme_value == config.MAX_TOKENS, (
            f"README says {readme_value} but config.MAX_TOKENS is {config.MAX_TOKENS}"
        )

    def test_rio_page_size_matches_config(self):
        """README should show correct RIO_PAGE_SIZE default."""
        readme = read_readme()
        match = re.search(r"\|\s*`RIO_PAGE_SIZE`\s*\|\s*`(\d+)`", readme)
        assert match, "RIO_PAGE_SIZE not found in README table"
        readme_value = int(match.group(1))
        assert readme_value == config.RIO_PAGE_SIZE, (
            f"README says {readme_value} but config.RIO_PAGE_SIZE is {config.RIO_PAGE_SIZE}"
        )

    def test_duo_row_limit_matches_config(self):
        """README should show correct DUO_ROW_LIMIT default."""
        readme = read_readme()
        match = re.search(r"\|\s*`DUO_ROW_LIMIT`\s*\|\s*`(\d+)`", readme)
        assert match, "DUO_ROW_LIMIT not found in README table"
        readme_value = int(match.group(1))
        assert readme_value == config.DUO_ROW_LIMIT, (
            f"README says {readme_value} but config.DUO_ROW_LIMIT is {config.DUO_ROW_LIMIT}"
        )

    def test_max_history_matches_config(self):
        """README should show correct MAX_HISTORY default."""
        readme = read_readme()
        match = re.search(r"\|\s*`MAX_HISTORY`\s*\|\s*`(\d+)`", readme)
        assert match, "MAX_HISTORY not found in README table"
        readme_value = int(match.group(1))
        assert readme_value == config.MAX_HISTORY, (
            f"README says {readme_value} but config.MAX_HISTORY is {config.MAX_HISTORY}"
        )

    def test_databronnen_section_includes_major_sources(self):
        """README databronnen table should mention all major sources."""
        readme = read_readme()
        sources = ["CBS", "RIO", "DUO", "ROA", "UWV"]
        for source in sources:
            assert source in readme, f"Source '{source}' not mentioned in README databronnen section"

    @pytest.mark.parametrize(
        ("leverancier", "patroon"),
        [
            ("CBS", r"\*\*CBS\*\*\s*\|\s*(\d+) datasets"),
            ("DUO", r"\*\*DUO\*\*\s*\|\s*(\d+) open datasets"),
            ("RIO", r"\*\*RIO\*\*\s*\|.*?\((\d+) resources\)"),
        ],
    )
    def test_dataset_aantallen_komen_overeen_met_de_catalogus(self, leverancier, patroon):
        """Vergelijk met de catalogus zelf, niet met historische getallen.

        De vorige opzet controleerde of de strings "68 datasets" en "57 open datasets"
        nog in de README stonden. Groeit CBS naar 270, dan blijft de README 266 zeggen
        en slaagde die test gewoon — precies de drift die #35 moest repareren.
        """
        match = re.search(patroon, read_readme())
        assert match, f"geen aantal voor {leverancier} gevonden in de bronnentabel"

        assert int(match.group(1)) == catalogus_aantal(leverancier), (
            f"README zegt {match.group(1)} voor {leverancier}, "
            f"catalogus heeft er {catalogus_aantal(leverancier)}"
        )

    def test_readme_noemt_geen_bron_die_de_catalogus_wegfiltert(self):
        """Zie #55: Inspectie en SBB zitten in de ruwe catalogus maar worden gefilterd.

        Ze noemen zou een belofte zijn die de app niet waarmaakt — de gebruiker kan die
        datasets niet vinden via search_catalog.
        """
        readme = read_readme()
        for verborgen in ("Inspectie van het Onderwijs", "SBB"):
            assert verborgen not in readme, (
                f"'{verborgen}' staat in de README maar wordt door "
                f"SUPPORTED_LEVERANCIERS uit de zoekresultaten gefilterd"
            )

    def test_env_example_includes_all_config_vars(self):
        """Alle configuratievariabelen uit config.py moeten in .env.example staan.

        Voorkomt dat .env.example en config.py uit de pas lopen.
        Vergelijk met test_readme_consistency tests voor README.
        """
        env_path = Path(__file__).parent.parent / ".env.example"
        env_content = env_path.read_text(encoding="utf-8")

        # Public config variables (getenv calls in config.py)
        required_vars = [
            "MODEL", "MAX_TOKENS", "MAX_TOOL_ITERATIONS",
            "CBS_ROW_LIMIT", "RIO_PAGE_SIZE", "DUO_ROW_LIMIT", "MAX_HISTORY",
            "WILLMA_API_KEY", "WILLMA_BASE_URL", "AVAILABLE_MODELS", "USER_MODELS"
        ]

        for var in required_vars:
            assert var in env_content, (
                f"'{var}' ontbreekt in .env.example maar staat in config.py"
            )
