"""Validate README claims against actual code configuration."""

import re
from pathlib import Path

import pytest

from core import config


README_PATH = Path(__file__).parent.parent / "README.md"


def read_readme() -> str:
    """Read README content."""
    return README_PATH.read_text(encoding="utf-8")


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

    def test_no_hardcoded_dataset_counts(self):
        """README should not have outdated hardcoded dataset counts.

        This test documents that dataset counts (266 CBS, 56 DUO) are now in README
        but should ideally come from dynamic catalog queries in the future.
        """
        readme = read_readme()
        # These specific numbers appear in the README now (after the fix)
        # This test ensures they stay current or get replaced with dynamic queries
        if "68 datasets" in readme or "57 open datasets" in readme:
            pytest.fail("Found old dataset counts in README — should be 266 CBS, 56 DUO")
