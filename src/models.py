from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class DataBundle:
    sales: pd.DataFrame
    products: pd.DataFrame
    marketing: pd.DataFrame
    customers: pd.DataFrame
    inventory: pd.DataFrame
    reviews: pd.DataFrame
    recommendations: pd.DataFrame
    data_dir: Path

    @property
    def min_date(self) -> pd.Timestamp:
        dated = [
            frame["date"].min()
            for frame in (
                self.sales,
                self.marketing,
                self.customers,
                self.inventory,
                self.reviews,
                self.recommendations,
            )
        ]
        return min(dated)

    @property
    def max_date(self) -> pd.Timestamp:
        dated = [
            frame["date"].max()
            for frame in (
                self.sales,
                self.marketing,
                self.customers,
                self.inventory,
                self.recommendations,
            )
        ]
        return max(dated)


@dataclass(frozen=True)
class CorrelationResult:
    matrix: pd.DataFrame
    top_pairs: pd.DataFrame
    daily_metrics: pd.DataFrame
