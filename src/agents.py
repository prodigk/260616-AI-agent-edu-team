from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from src.models import CorrelationResult, DataBundle


EVENT_COLUMNS = [
    "date",
    "event_type",
    "domain",
    "product_id",
    "product_name",
    "severity",
    "metric",
    "value",
    "change_rate",
    "description",
]


class DataLoaderAgent:
    """Loads and validates the seven commerce datasets."""

    files = {
        "sales": "sales_data.csv",
        "products": "product_data.csv",
        "marketing": "marketing_data.csv",
        "customers": "customer_data.csv",
        "inventory": "inventory_data.csv",
        "reviews": "review_cs_data.csv",
        "recommendations": "recommendation_log.csv",
    }

    def run(self, data_dir: str | Path) -> tuple[DataBundle, pd.DataFrame]:
        data_dir = Path(data_dir)
        frames: dict[str, pd.DataFrame] = {}
        quality_rows: list[dict[str, object]] = []

        for name, filename in self.files.items():
            path = data_dir / filename
            if not path.exists():
                raise FileNotFoundError(f"필수 데이터 파일이 없습니다: {path}")
            frame = pd.read_csv(path)
            if "date" in frame.columns:
                frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frames[name] = frame
            quality_rows.append(
                {
                    "dataset": filename,
                    "rows": len(frame),
                    "columns": len(frame.columns),
                    "null_cells": int(frame.isna().sum().sum()),
                    "duplicates": int(frame.duplicated().sum()),
                    "status": "정상"
                    if not frame.isna().any().any() and not frame.duplicated().any()
                    else "확인 필요",
                }
            )

        bundle = DataBundle(
            sales=frames["sales"],
            products=frames["products"],
            marketing=frames["marketing"],
            customers=frames["customers"],
            inventory=frames["inventory"],
            reviews=frames["reviews"],
            recommendations=frames["recommendations"],
            data_dir=data_dir,
        )
        return bundle, pd.DataFrame(quality_rows)


class EventDetectorAgent:
    """Detects notable changes across sales, inventory, marketing, and recommendations."""

    def run(
        self, bundle: DataBundle, start: pd.Timestamp, end: pd.Timestamp
    ) -> pd.DataFrame:
        events: list[dict[str, object]] = []
        sales = bundle.sales.sort_values(["product_id", "date"]).copy()
        sales["baseline"] = sales.groupby("product_id")["quantity_sold"].transform(
            lambda s: s.shift(1).rolling(3, min_periods=3).mean()
        )
        scoped_sales = sales[sales["date"].between(start, end)].copy()

        for row in scoped_sales.dropna(subset=["baseline"]).itertuples():
            if row.baseline <= 0:
                continue
            change = row.quantity_sold / row.baseline - 1
            if change >= 0.5:
                events.append(
                    self._event(
                        row.date,
                        "판매 급상승",
                        "매출·상품",
                        row.product_id,
                        row.product_name,
                        "High" if change >= 1 else "Medium",
                        "quantity_sold",
                        row.quantity_sold,
                        change,
                        f"3일 기준 판매량보다 {change:.0%} 증가했습니다.",
                    )
                )
            elif change <= -0.3:
                events.append(
                    self._event(
                        row.date,
                        "판매 급감",
                        "매출·상품",
                        row.product_id,
                        row.product_name,
                        "Medium",
                        "quantity_sold",
                        row.quantity_sold,
                        change,
                        f"3일 기준 판매량보다 {abs(change):.0%} 감소했습니다.",
                    )
                )

        inventory = bundle.inventory[bundle.inventory["date"].between(start, end)]
        if not inventory.empty:
            latest = inventory.loc[inventory.groupby("product_id")["date"].idxmax()]
            product_names = bundle.products.set_index("product_id")["product_name"]
            for row in latest.itertuples():
                if row.current_stock <= row.safe_stock:
                    is_out = row.current_stock == 0
                    events.append(
                        self._event(
                            row.date,
                            "품절" if is_out else "품절 위험",
                            "재고·추천",
                            row.product_id,
                            product_names.get(row.product_id, row.product_id),
                            "High" if is_out or row.current_stock < row.safe_stock * 0.5 else "Medium",
                            "current_stock",
                            row.current_stock,
                            (row.current_stock / row.safe_stock - 1)
                            if row.safe_stock
                            else 0,
                            f"현재 재고 {row.current_stock}개 / 안전재고 {row.safe_stock}개입니다.",
                        )
                    )

        marketing = bundle.marketing.sort_values("date")
        current = marketing[marketing["date"].between(end - pd.Timedelta(days=6), end)]
        previous = marketing[
            marketing["date"].between(end - pd.Timedelta(days=13), end - pd.Timedelta(days=7))
        ]
        if not current.empty and not previous.empty:
            current_roas = current.groupby("channel")["ROAS"].mean()
            previous_roas = previous.groupby("channel")["ROAS"].mean()
            for channel in current_roas.index.intersection(previous_roas.index):
                prev = previous_roas[channel]
                change = current_roas[channel] / prev - 1 if prev else 0
                if change <= -0.2:
                    events.append(
                        self._event(
                            end,
                            "광고 효율 저하",
                            "마케팅",
                            None,
                            channel,
                            "High" if change <= -0.35 else "Medium",
                            "ROAS",
                            current_roas[channel],
                            change,
                            f"{channel} ROAS가 전주보다 {abs(change):.0%} 감소했습니다.",
                        )
                    )

        period_sales = scoped_sales.groupby(
            ["category", "product_id", "product_name"], as_index=False
        )["quantity_sold"].sum()
        if not period_sales.empty:
            top_products = period_sales.sort_values(
                ["category", "quantity_sold"], ascending=[True, False]
            ).groupby("category").head(3)
            for row in top_products.itertuples():
                events.append(
                    self._event(
                        end,
                        "인기상품 진입",
                        "매출·상품",
                        row.product_id,
                        row.product_name,
                        "Low",
                        "quantity_sold",
                        row.quantity_sold,
                        np.nan,
                        f"{row.category} 카테고리 판매량 Top 3 상품입니다.",
                    )
                )

        recs = bundle.recommendations[
            bundle.recommendations["date"].between(start, end)
        ].copy()
        if not recs.empty:
            grouped = recs.groupby(
                ["product_id", "product_name"], as_index=False
            ).agg(
                recommended_count=("recommended_count", "sum"),
                click_count=("click_count", "sum"),
                conversion_count=("conversion_count", "sum"),
            )
            grouped["ctr"] = grouped["click_count"].div(
                grouped["recommended_count"].replace(0, np.nan)
            )
            grouped["cvr"] = grouped["conversion_count"].div(
                grouped["click_count"].replace(0, np.nan)
            )
            avg_ctr, avg_cvr = grouped["ctr"].mean(), grouped["cvr"].mean()
            for row in grouped.itertuples():
                ctr_gain = row.ctr / avg_ctr - 1 if avg_ctr else 0
                cvr_gain = row.cvr / avg_cvr - 1 if avg_cvr else 0
                if max(ctr_gain, cvr_gain) >= 0.3:
                    events.append(
                        self._event(
                            end,
                            "추천상품 성과 우수",
                            "재고·추천",
                            row.product_id,
                            row.product_name,
                            "Low",
                            "recommendation_CTR",
                            row.ctr,
                            max(ctr_gain, cvr_gain),
                            f"추천 CTR {row.ctr:.1%}, CVR {row.cvr:.1%}로 평균을 크게 상회합니다.",
                        )
                    )

        if not events:
            return pd.DataFrame(columns=EVENT_COLUMNS)
        return (
            pd.DataFrame(events, columns=EVENT_COLUMNS)
            .sort_values(["date", "severity"], ascending=[False, True])
            .reset_index(drop=True)
        )

    @staticmethod
    def _event(
        date,
        event_type,
        domain,
        product_id,
        product_name,
        severity,
        metric,
        value,
        change_rate,
        description,
    ) -> dict[str, object]:
        return {
            "date": pd.Timestamp(date),
            "event_type": event_type,
            "domain": domain,
            "product_id": product_id,
            "product_name": product_name,
            "severity": severity,
            "metric": metric,
            "value": value,
            "change_rate": change_rate,
            "description": description,
        }


class CorrelationAnalyzerAgent:
    """Builds a daily metric table and extracts the strongest relationships."""

    metric_columns = [
        "quantity_sold",
        "revenue",
        "current_stock",
        "ad_spend",
        "clicks",
        "conversions",
        "rating",
        "recommended_count",
        "click_count",
        "conversion_count",
    ]

    def run(
        self,
        bundle: DataBundle,
        start: pd.Timestamp,
        end: pd.Timestamp,
        method: str = "pearson",
    ) -> CorrelationResult:
        sales = (
            bundle.sales[bundle.sales["date"].between(start, end)]
            .groupby("date", as_index=False)[["quantity_sold", "revenue"]]
            .sum()
        )
        inventory = (
            bundle.inventory[bundle.inventory["date"].between(start, end)]
            .groupby("date", as_index=False)["current_stock"]
            .sum()
        )
        marketing = (
            bundle.marketing[bundle.marketing["date"].between(start, end)]
            .groupby("date", as_index=False)[["ad_spend", "clicks", "conversions"]]
            .sum()
        )
        reviews = (
            bundle.reviews[bundle.reviews["date"].between(start, end)]
            .groupby("date", as_index=False)["rating"]
            .mean()
        )
        recs = (
            bundle.recommendations[bundle.recommendations["date"].between(start, end)]
            .groupby("date", as_index=False)[
                ["recommended_count", "click_count", "conversion_count"]
            ]
            .sum()
        )
        daily = sales.merge(inventory, on="date", how="outer")
        daily = daily.merge(marketing, on="date", how="outer")
        daily = daily.merge(recs, on="date", how="outer")
        daily = daily.merge(reviews, on="date", how="left").sort_values("date")
        daily["rating"] = daily["rating"].ffill().bfill()
        daily = daily.fillna(0)
        available = [c for c in self.metric_columns if c in daily.columns]
        matrix = daily[available].corr(method=method)
        pairs: list[dict[str, object]] = []
        for i, metric_a in enumerate(available):
            for metric_b in available[i + 1 :]:
                coefficient = matrix.loc[metric_a, metric_b]
                if pd.notna(coefficient):
                    pairs.append(
                        {
                            "metric_a": metric_a,
                            "metric_b": metric_b,
                            "coefficient": coefficient,
                            "strength": abs(coefficient),
                            "direction": "양의 관계" if coefficient >= 0 else "음의 관계",
                            "sample_size": len(daily),
                        }
                    )
        top_pairs = (
            pd.DataFrame(pairs)
            .sort_values("strength", ascending=False)
            .head(12)
            .reset_index(drop=True)
            if pairs
            else pd.DataFrame()
        )
        return CorrelationResult(matrix=matrix, top_pairs=top_pairs, daily_metrics=daily)


class InsightGeneratorAgent:
    """Turns structured analysis into role-specific, evidence-grounded statements."""

    def run(
        self,
        events: pd.DataFrame,
        correlations: CorrelationResult,
        role: str = "전체",
    ) -> list[str]:
        insights: list[str] = []
        high_events = events[events["severity"] == "High"]
        if not high_events.empty:
            top = high_events.iloc[0]
            insights.append(
                f"가장 시급한 신호는 {top['product_name']}의 '{top['event_type']}'입니다. "
                f"{top['description']}"
            )
        inventory_events = events[events["event_type"].isin(["품절", "품절 위험"])]
        if not inventory_events.empty:
            insights.append(
                f"재고 대응이 필요한 상품은 {inventory_events['product_name'].nunique()}개입니다. "
                "판매 속도와 함께 확인한 뒤 발주 우선순위를 정해야 합니다."
            )
        marketing_events = events[events["domain"] == "마케팅"]
        if not marketing_events.empty:
            insights.append(
                "광고 효율 저하 채널이 탐지되었습니다. 예산 확대보다 소재·타깃·랜딩 성과를 먼저 점검하세요."
            )
        if not correlations.top_pairs.empty:
            pair = correlations.top_pairs.iloc[0]
            insights.append(
                f"{pair['metric_a']}와 {pair['metric_b']}가 {pair['direction']} "
                f"(r={pair['coefficient']:.2f})를 보입니다."
            )
        if role != "전체":
            insights.append(f"현재 화면은 {role} 관점의 우선순위로 정리했습니다.")
        insights.append("상관관계는 인과관계를 뜻하지 않으므로 프로모션·요일·계절성을 함께 확인해야 합니다.")
        return insights[:5]


class WeeklyReportAgent:
    """Creates a portable Markdown weekly report."""

    def run(
        self,
        kpis: dict[str, float],
        events: pd.DataFrame,
        correlations: CorrelationResult,
        insights: list[str],
        start: pd.Timestamp,
        end: pd.Timestamp,
    ) -> str:
        lines = [
            f"# AI 커머스 주간 리포트 ({start:%Y-%m-%d} ~ {end:%Y-%m-%d})",
            "",
            "## KPI",
            f"- 매출: ₩{kpis['revenue']:,.0f}",
            f"- 주문: {kpis['orders']:,.0f}건",
            f"- ROAS: {kpis['roas']:.1f}%",
            f"- 신규 고객: {kpis['new_customers']:,.0f}명",
            "",
            "## 핵심 인사이트",
        ]
        lines.extend([f"- {insight}" for insight in insights])
        lines.extend(["", "## 주요 이벤트"])
        for row in events.head(10).itertuples():
            lines.append(
                f"- [{row.severity}] {row.date:%m-%d} {row.event_type} · {row.product_name}: {row.description}"
            )
        lines.extend(["", "## 상관관계 Top 3"])
        for row in correlations.top_pairs.head(3).itertuples():
            lines.append(
                f"- {row.metric_a} ↔ {row.metric_b}: {row.coefficient:.2f} ({row.direction})"
            )
        lines.append("\n> 상관관계는 인과관계를 의미하지 않습니다.")
        return "\n".join(lines)


class ActionPlannerAgent:
    """Converts notable events into executable, prioritized work."""

    mappings = {
        "판매 급상승": ("MD", "수요 증가 상품의 재고 소진일을 확인하고 추가 발주안을 준비하세요."),
        "판매 급감": ("MD", "가격·노출·리뷰·프로모션 변화를 점검하고 원인을 기록하세요."),
        "품절 위험": ("MD", "안전재고와 최근 판매 속도를 기준으로 추가 발주를 검토하세요."),
        "품절": ("운영", "상품 노출 상태를 조정하고 긴급 발주 또는 대체 상품 연결을 진행하세요."),
        "광고 효율 저하": ("마케팅", "저효율 캠페인의 소재·타깃·예산 배분을 재검토하세요."),
        "인기상품 진입": ("마케팅", "인기상품의 추천·광고 노출을 확대하고 재고 여력을 확인하세요."),
        "추천상품 성과 우수": ("CRM/CS", "성과가 높은 추천 슬롯과 고객 세그먼트를 확대 테스트하세요."),
    }

    def run(self, events: pd.DataFrame, today: pd.Timestamp) -> pd.DataFrame:
        actions: list[dict[str, object]] = []
        for idx, row in events.iterrows():
            team, instruction = self.mappings.get(
                row["event_type"], ("운영", "관련 지표를 검토하고 후속 조치를 정의하세요.")
            )
            priority = row["severity"] if row["severity"] in {"High", "Medium"} else "Low"
            due_days = {"High": 1, "Medium": 3, "Low": 7}[priority]
            actions.append(
                {
                    "action_id": f"ACT-{idx + 1:03d}",
                    "event_type": row["event_type"],
                    "target": row["product_name"],
                    "team": team,
                    "priority": priority,
                    "due_date": pd.Timestamp(today) + timedelta(days=due_days),
                    "instruction": instruction,
                    "status": "대기",
                }
            )
        return pd.DataFrame(actions).head(30)


class TaskAssignmentAgent:
    """Filters action work by role and highlights overdue tasks."""

    def run(
        self, actions: pd.DataFrame, role: str, today: pd.Timestamp
    ) -> pd.DataFrame:
        assigned = actions.copy()
        if role not in {"전체", "대표"}:
            assigned = assigned[assigned["team"] == role]
        if not assigned.empty:
            assigned["overdue"] = (
                (assigned["due_date"] < pd.Timestamp(today))
                & (assigned["status"] != "완료")
            )
        return assigned.reset_index(drop=True)


class ExecutiveReportAgent:
    """Creates a concise executive decision summary."""

    def run(
        self,
        kpis: dict[str, float],
        events: pd.DataFrame,
        actions: pd.DataFrame,
        insights: list[str],
    ) -> str:
        approvals = actions[
            (actions["priority"] == "High") & actions["team"].isin(["MD", "마케팅", "운영"])
        ].head(5)
        lines = [
            "# Executive Brief",
            f"매출 ₩{kpis['revenue']:,.0f} · 주문 {kpis['orders']:,.0f}건 · ROAS {kpis['roas']:.1f}%",
            "",
            "## 핵심 판단",
            *[f"- {item}" for item in insights[:3]],
            "",
            "## 승인·결정 필요",
        ]
        if approvals.empty:
            lines.append("- 현재 즉시 승인이 필요한 High 액션은 없습니다.")
        else:
            lines.extend(
                [
                    f"- [{row.team}] {row.target}: {row.instruction}"
                    for row in approvals.itertuples()
                ]
            )
        return "\n".join(lines)


@dataclass(frozen=True)
class AgentOutputs:
    bundle: DataBundle
    quality: pd.DataFrame
    events: pd.DataFrame
    correlations: CorrelationResult
    insights: list[str]
    actions: pd.DataFrame


def calculate_kpis(
    bundle: DataBundle, start: pd.Timestamp, end: pd.Timestamp
) -> dict[str, float]:
    sales = bundle.sales[bundle.sales["date"].between(start, end)]
    marketing = bundle.marketing[bundle.marketing["date"].between(start, end)]
    customers = bundle.customers[bundle.customers["date"].between(start, end)]
    reviews = bundle.reviews[bundle.reviews["date"].between(start, end)]
    return {
        "revenue": float(sales["revenue"].sum()),
        "orders": float(sales["orders"].sum()),
        "quantity_sold": float(sales["quantity_sold"].sum()),
        "roas": float(marketing["ROAS"].mean()) if not marketing.empty else 0,
        "ad_spend": float(marketing["ad_spend"].sum()),
        "new_customers": float(customers["new_customers"].sum()),
        "returning_customers": float(customers["returning_customers"].sum()),
        "rating": float(reviews["rating"].mean()) if not reviews.empty else 0,
    }
