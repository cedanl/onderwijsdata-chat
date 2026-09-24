import pandas as pd


def sample_values(series: pd.Series, limit: int) -> list[str]:
    """Up to `limit` distinct non-null values of a column, as text for the model."""
    values = series.dropna()
    try:
        distinct = values.unique()
    except TypeError:
        # JSON-API's (zoals RIO met zijn _links) leveren geneste dicts/lijsten, en die zijn niet hashbaar.
        distinct = values.astype(str).unique()
    return [str(v) for v in distinct[:limit]]
