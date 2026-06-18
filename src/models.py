from __future__ import annotations

from dataclasses import dataclass, field
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
    hourly_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    customer_segments: pd.DataFrame = field(default_factory=pd.DataFrame)
    campaign_products: pd.DataFrame = field(default_factory=pd.DataFrame)
    cross_sell: pd.DataFrame = field(default_factory=pd.DataFrame)
    inventory_loss: pd.DataFrame = field(default_factory=pd.DataFrame)
    product_retention: pd.DataFrame = field(default_factory=pd.DataFrame)
    pricing_promotions: pd.DataFrame = field(default_factory=pd.DataFrame)
    delivery_experience: pd.DataFrame = field(default_factory=pd.DataFrame)
    brand_search: pd.DataFrame = field(default_factory=pd.DataFrame)

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


@dataclass(frozen=True)
class CauseAnalysisResult:
    candidates: pd.DataFrame
