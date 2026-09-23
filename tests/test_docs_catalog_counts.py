"""Docs must quote the same dataset counts as the catalog the app searches."""
import re
from pathlib import Path

import pytest

from tools.catalog import dataset_counts

ROOT = Path(__file__).resolve().parent.parent

# (file, source, pattern with one group for the number)
QUOTED_COUNTS = [
    ("README.md", "CBS", r"\| \*\*CBS\*\* \| (\d+) "),
    ("README.md", "DUO", r"\| \*\*DUO\*\* \| (\d+) "),
    ("docs/index.md", "CBS", r"\| \*\*CBS\*\* \| (\d+) "),
    ("docs/index.md", "DUO", r"\| \*\*DUO\*\* \| (\d+) "),
    ("docs/databronnen.md", "CBS", r"\*\*(\d+) datasets\*\* met statistische"),
    ("docs/databronnen.md", "DUO", r"\*\*(\d+) open datasets\*\* gepubliceerd door DUO"),
]


@pytest.mark.parametrize(("path", "source", "pattern"), QUOTED_COUNTS)
def test_quoted_counts_match_catalog(path, source, pattern):
    match = re.search(pattern, (ROOT / path).read_text(encoding="utf-8"))
    assert match, f"{path} mist de telling voor {source}"
    assert int(match.group(1)) == dataset_counts()[source]
