"""Test chart type auto-detection logic."""

import pytest

from tools.plot import _is_time_axis, _infer_chart_type


class TestTimeAxisDetection:
    """Verify time column detection."""

    def test_recognizes_jaar(self):
        assert _is_time_axis("JAAR")
        assert _is_time_axis("jaar")

    def test_recognizes_periode(self):
        assert _is_time_axis("PERIODE")
        assert _is_time_axis("periode")

    def test_recognizes_date_columns(self):
        assert _is_time_axis("DATUM")
        assert _is_time_axis("DATE")

    def test_ignores_non_time_columns(self):
        assert not _is_time_axis("NAAM")
        assert not _is_time_axis("INSTELLING")
        assert not _is_time_axis("AANTAL")


class TestChartTypeInference:
    """Verify chart type selection logic."""

    def test_time_axis_becomes_line(self):
        """Time axis → line (trend visualization)."""
        chart_type = _infer_chart_type(x="JAAR", y="AANTAL", color_by=None)
        assert chart_type == "line"

    def test_time_axis_with_groups_stays_line(self):
        """Time + groups → line (multi-series trend)."""
        chart_type = _infer_chart_type(
            x="JAAR",
            y="AANTAL",
            color_by="SECTOR",
            num_groups=3
        )
        assert chart_type == "line"

    def test_share_with_few_groups_becomes_pie(self):
        """Share/proportion data with ≤5 groups → pie."""
        chart_type = _infer_chart_type(
            x="NIVEAU",
            y="AANDEEL",
            color_by=None,
            is_share=True
        )
        assert chart_type == "pie"

    def test_share_with_many_groups_becomes_bar(self):
        """Share/proportion with >5 groups → bar (pie is unreadable)."""
        chart_type = _infer_chart_type(
            x="INSTELLING",
            y="AANDEEL",
            color_by=None,
            num_groups=12,
            is_share=True
        )
        assert chart_type == "bar"

    def test_multiple_groups_becomes_bar(self):
        """Multiple categories → bar (comparison)."""
        chart_type = _infer_chart_type(
            x="INSTELLING",
            y="AANTAL",
            color_by="JAAR",
            num_groups=5
        )
        assert chart_type == "bar"

    def test_single_series_defaults_to_bar(self):
        """Single series without time → bar."""
        chart_type = _infer_chart_type(
            x="SECTOR",
            y="AANTAL",
            color_by=None
        )
        assert chart_type == "bar"

    def test_demo_case_time_single_group_trend(self):
        """Demo: x=tijd, 1 groep, trend → line."""
        chart_type = _infer_chart_type(
            x="JAAR",
            y="INGESCHREVENEN",
            color_by=None,
            num_groups=1
        )
        assert chart_type == "line"

    def test_demo_case_time_multiple_groups_trend(self):
        """Demo: x=tijd, 12 groepen, trend → line (not bar; too many lines are ok for trend)."""
        chart_type = _infer_chart_type(
            x="PERIODE",
            y="AANTAL",
            color_by="INSTELLING",
            num_groups=12
        )
        assert chart_type == "line"

    def test_demo_case_category_share_few(self):
        """Demo: x=categorie, 4 groepen, aandeel → pie."""
        chart_type = _infer_chart_type(
            x="GESLACHT",
            y="PERCENTAGE",
            color_by=None,
            num_groups=4,
            is_share=True
        )
        assert chart_type == "pie"

    def test_demo_case_category_share_many(self):
        """Demo: x=categorie, 9 groepen, aandeel → bar (max 5 for pie)."""
        chart_type = _infer_chart_type(
            x="SECTOR",
            y="PERCENTAGE",
            color_by=None,
            num_groups=9,
            is_share=True
        )
        assert chart_type == "bar"

    def test_demo_case_continuous_distribution(self):
        """Demo: x=continu, verdeling → histogram (not implemented yet, but bar is safe)."""
        # Note: histogram detection would require knowing x is continuous
        # For now, we test that it doesn't break
        chart_type = _infer_chart_type(
            x="SCHOOLGROOTTE",
            y="COUNT",
            color_by=None
        )
        assert chart_type in ("bar", "histogram")
