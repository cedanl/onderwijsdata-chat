"""Test that DUO sentinels are masked consistently across all code paths."""

import pandas as pd
import pytest

from tools.duo import _mask_sentinels, _apply_aggregation


class TestSentinelMasking:
    """Verify sentinels are masked at load time, not during aggregation."""

    def test_mask_sentinels_replaces_minus_one(self):
        """_mask_sentinels should replace -1 with pd.NA in numeric columns."""
        df = pd.DataFrame({
            "AANTAL": [100, 200, -1, 300],
            "NAAM": ["A", "B", "C", "D"],
        })
        masked = _mask_sentinels(df)

        assert pd.isna(masked.loc[2, "AANTAL"])
        assert masked.loc[0, "AANTAL"] == 100
        assert masked.loc[1, "AANTAL"] == 200
        assert masked.loc[3, "AANTAL"] == 300
        assert list(masked["NAAM"]) == ["A", "B", "C", "D"]

    def test_mask_sentinels_preserves_other_columns(self):
        """_mask_sentinels should not modify non-numeric columns."""
        df = pd.DataFrame({
            "AANTAL": [100, -1, 300],
            "NAAM": ["A", "B", "C"],
            "JAAR": [2021, 2021, 2021],
        })
        masked = _mask_sentinels(df)

        assert list(masked["NAAM"]) == ["A", "B", "C"]
        assert list(masked["JAAR"]) == [2021, 2021, 2021]

    def test_aggregation_with_group_by_excludes_sentinels(self):
        """After masking, aggregation should exclude sentinels in group_by."""
        df = pd.DataFrame({
            "GROEP": ["A", "A", "A"],
            "AANTAL": [100.0, 200.0, pd.NA],
        })

        result, _ = _apply_aggregation(
            df,
            group_by=["GROEP"],
            aggregate={"AANTAL": "sum"}
        )

        assert float(result.loc[0, "AANTAL"]) == 300.0

    def test_multiple_groups_all_exclude_sentinels(self):
        """Sentinels should be excluded in multi-group aggregations."""
        df = pd.DataFrame({
            "GROEP_A": ["X", "X", "X", "Y", "Y"],
            "GROEP_B": ["1", "1", "1", "2", "2"],
            "AANTAL": [100.0, 200.0, pd.NA, 150.0, pd.NA],
        })

        result, _ = _apply_aggregation(
            df,
            group_by=["GROEP_A", "GROEP_B"],
            aggregate={"AANTAL": "sum"}
        )

        x_1 = float(result[(result["GROEP_A"] == "X") & (result["GROEP_B"] == "1")]["AANTAL"].values[0])
        y_2 = float(result[(result["GROEP_A"] == "Y") & (result["GROEP_B"] == "2")]["AANTAL"].values[0])

        assert x_1 == 300.0
        assert y_2 == 150.0

    def test_masked_sentinels_are_na_not_zero(self):
        """Masked sentinels should be pd.NA, not 0 (which would be different behavior)."""
        df = pd.DataFrame({
            "AANTAL": [100, 200, -1],
        })
        masked = _mask_sentinels(df)

        assert pd.isna(masked.loc[2, "AANTAL"])
        assert not masked.loc[2, "AANTAL"] == 0

    def test_multiple_sentinels(self):
        """_mask_sentinels should handle multiple occurrences."""
        df = pd.DataFrame({
            "AANTAL": [-1, 100, -1, 200, -1],
        })
        masked = _mask_sentinels(df)

        assert pd.isna(masked.loc[0, "AANTAL"])
        assert pd.isna(masked.loc[2, "AANTAL"])
        assert pd.isna(masked.loc[4, "AANTAL"])
        assert masked.loc[1, "AANTAL"] == 100
        assert masked.loc[3, "AANTAL"] == 200
