"""README must quote the same dataset counts as the catalog the app searches."""
import re
from pathlib import Path

from tools.catalog import dataset_counts

README = Path(__file__).resolve().parent.parent / "README.md"


def test_readme_counts_match_catalog():
    text = README.read_text(encoding="utf-8")
    counts = dataset_counts()
    for source in ("CBS", "DUO"):
        match = re.search(rf"\| \*\*{source}\*\* \| (\d+) ", text)
        assert match, f"README mist de telling voor {source}"
        assert int(match.group(1)) == counts[source], source
