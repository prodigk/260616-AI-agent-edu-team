from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from src.models import CauseAnalysisResult, CorrelationResult, DataBundle


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

CAUSE_COLUMNS = [
    "event_date",
    "event_type",
    "domain",
    "target",
    "event_metric",
    "related_metric",
    "correlation",
    "direction",
    "event_metric_change",
    "related_metric_change",
    "hypothesis",
    "confidence",
    "recommended_action",
    "caution",
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


class CauseAnalyzerAgent:
    """Creates evidence-grounded cause hypotheses from events and correlations."""

    caution = "상관관계와 이벤트 전후 변화는 원인 확정이 아니라 검토할 가설입니다."
    metric_aliases = {
        "recommendation_CTR": ("recommended_count", "click_count", "conversion_count"),
        "ROAS": ("ad_spend", "clicks", "conversions"),
    }

    def run(
        self,
        events: pd.DataFrame,
        correlations: CorrelationResult,
    ) -> CauseAnalysisResult:
        if events.empty or correlations.top_pairs.empty or correlations.daily_metrics.empty:
            return CauseAnalysisResult(pd.DataFrame(columns=CAUSE_COLUMNS))

        candidates: list[dict[str, object]] = []
        daily = correlations.daily_metrics.copy()
        for event in events.head(24).itertuples():
            related_pairs = self._related_pairs(event.metric, correlations.top_pairs)
            if related_pairs.empty:
                related_pairs = correlations.top_pairs.head(2)
            for pair in related_pairs.head(3).itertuples():
                related_metric = (
                    pair.metric_b
                    if pair.metric_a in self._metric_candidates(event.metric)
                    else pair.metric_a
                )
                event_change = self._window_change(daily, event.date, event.metric)
                related_change = self._window_change(daily, event.date, related_metric)
                confidence = self._confidence(abs(float(pair.coefficient)), event.severity)
                candidates.append(
                    {
                        "event_date": pd.Timestamp(event.date),
                        "event_type": event.event_type,
                        "domain": event.domain,
                        "target": event.product_name,
                        "event_metric": event.metric,
                        "related_metric": related_metric,
                        "correlation": float(pair.coefficient),
                        "direction": pair.direction,
                        "event_metric_change": event_change,
                        "related_metric_change": related_change,
                        "hypothesis": self._hypothesis(
                            event.event_type, related_metric, pair.direction
                        ),
                        "confidence": confidence,
                        "recommended_action": self._recommended_action(
                            event.event_type, related_metric
                        ),
                        "caution": self.caution,
                    }
                )

        if not candidates:
            return CauseAnalysisResult(pd.DataFrame(columns=CAUSE_COLUMNS))
        frame = pd.DataFrame(candidates, columns=CAUSE_COLUMNS)
        frame["strength"] = frame["correlation"].abs()
        frame["confidence_rank"] = frame["confidence"].map(
            {"High": 0, "Medium": 1, "Low": 2}
        )
        frame = (
            frame.sort_values(["confidence_rank", "strength"], ascending=[True, False])
            .drop(columns=["strength", "confidence_rank"])
            .head(30)
            .reset_index(drop=True)
        )
        return CauseAnalysisResult(frame)

    def _related_pairs(self, metric: str, top_pairs: pd.DataFrame) -> pd.DataFrame:
        candidates = self._metric_candidates(metric)
        return top_pairs[
            top_pairs["metric_a"].isin(candidates)
            | top_pairs["metric_b"].isin(candidates)
        ].copy()

    def _metric_candidates(self, metric: str) -> tuple[str, ...]:
        return self.metric_aliases.get(metric, (metric,))

    def _window_change(self, daily: pd.DataFrame, event_date, metric: str) -> float | None:
        metrics = self._metric_candidates(metric)
        metric_name = next((item for item in metrics if item in daily.columns), None)
        if metric_name is None:
            return None
        event_date = pd.Timestamp(event_date)
        before = daily[
            daily["date"].between(
                event_date - pd.Timedelta(days=3), event_date - pd.Timedelta(days=1)
            )
        ][metric_name]
        after = daily[
            daily["date"].between(event_date, event_date + pd.Timedelta(days=3))
        ][metric_name]
        before_avg = before.mean()
        after_avg = after.mean()
        if pd.isna(before_avg) or pd.isna(after_avg) or before_avg == 0:
            return None
        return float(after_avg / before_avg - 1)

    @staticmethod
    def _confidence(strength: float, severity: str) -> str:
        if strength >= 0.7 and severity == "High":
            return "High"
        if strength >= 0.45:
            return "Medium"
        return "Low"

    @staticmethod
    def _hypothesis(event_type: str, related_metric: str, direction: str) -> str:
        metric_label = {
            "ad_spend": "광고비 변화",
            "clicks": "광고 클릭 변화",
            "conversions": "광고 전환 변화",
            "current_stock": "재고 수준 변화",
            "rating": "평점 변화",
            "recommended_count": "추천 노출 변화",
            "click_count": "추천 클릭 변화",
            "conversion_count": "추천 전환 변화",
            "revenue": "매출 변화",
            "quantity_sold": "판매량 변화",
        }.get(related_metric, related_metric)
        return (
            f"{event_type}은 {metric_label}와 {direction}로 함께 움직인 신호가 있어 "
            "운영 가설로 검토할 수 있습니다."
        )

    @staticmethod
    def _recommended_action(event_type: str, related_metric: str) -> str:
        if event_type in {"품절", "품절 위험"}:
            return "판매 속도와 추천/광고 노출을 함께 확인하고 발주 또는 대체 상품 노출을 검토하세요."
        if event_type == "광고 효율 저하":
            return "클릭·전환·소재·타깃 변화를 분리해 보고 예산 조정 전 원인을 확인하세요."
        if event_type in {"판매 급상승", "인기상품 진입"}:
            return "재고 여력, 추천 노출, 광고 유입을 함께 확인해 기회 손실을 줄이세요."
        if event_type == "판매 급감":
            return "가격·노출·리뷰·재고 변화를 비교해 하락 원인 후보를 좁히세요."
        return f"{related_metric} 변화를 이벤트 전후로 재확인하고 담당팀 액션으로 연결하세요."


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
        cause_candidates: pd.DataFrame | None = None,
    ) -> str:
        lines = [
            f"# AI 커머스 주간 리포트 ({start:%Y-%m-%d} ~ {end:%Y-%m-%d})",
            "",
            "## KPI",
            f"- 매출: ₩{kpis['revenue']:,.0f}",
            f"- 주문: {kpis['orders']:,.0f}건",
            f"- ROAS: {kpis['roas']:.1f}%",
            f"- 신규 고객: {kpis['new_customers']:,.0f}명",
            f"- 평균 평점: {kpis['rating']:.2f}점",
            "",
            "## 확인된 데이터",
            f"- 선택 기간 이벤트는 총 {len(events)}건이며, High 이벤트는 {int((events['severity'] == 'High').sum())}건입니다.",
            f"- 실행 액션은 총 {len(ActionPlannerAgent().run(events, end, cause_candidates))}건 생성되었습니다.",
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
        lines.extend(["", "## AI 해석/가설: 원인 후보"])
        if cause_candidates is not None and not cause_candidates.empty:
            for row in cause_candidates.head(5).itertuples():
                lines.append(
                    f"- [{row.confidence}] {row.target} · {row.event_type}: "
                    f"{row.related_metric} r={row.correlation:.2f}, 전후 변화 {_format_change(row.related_metric_change)}. "
                    f"{row.hypothesis}"
                )
        else:
            lines.append("- 선택 기간에는 충분한 원인 후보를 계산할 수 없습니다.")
        lines.extend(
            [
                "",
                "## 이번 주 실행 우선순위",
                "- High 이벤트는 24시간 내 담당팀이 원인 후보와 재고·광고·추천 지표를 함께 확인합니다.",
                "- Medium 이벤트는 3일 내 운영 가설을 검증하고 액션 상태를 업데이트합니다.",
                "",
                "## 역할별 확인 포인트",
                "- 마케팅: ROAS, 클릭, 전환, 캠페인 변화",
                "- MD/운영: 판매 급변, 안전재고, 품절 위험",
                "- CRM/CS: 평점, 문의, 환불, 고객 영향",
                "",
                "> 상관관계와 원인 후보는 인과관계 확정이 아니라 검토할 가설입니다.",
            ]
        )
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

    def run(
        self,
        events: pd.DataFrame,
        today: pd.Timestamp,
        cause_candidates: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        actions: list[dict[str, object]] = []
        for idx, row in events.iterrows():
            team, instruction = self.mappings.get(
                row["event_type"], ("운영", "관련 지표를 검토하고 후속 조치를 정의하세요.")
            )
            cause = self._matching_cause(row, cause_candidates)
            if cause is not None:
                instruction = (
                    f"{instruction} 근거 가설: {cause['related_metric']} 변화와 함께 확인하세요."
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
                    "recommendation_reason": self._recommendation_reason(row, cause),
                    "status": "대기",
                }
            )
        return pd.DataFrame(actions).head(30)

    @staticmethod
    def _matching_cause(row: pd.Series, cause_candidates: pd.DataFrame | None):
        if cause_candidates is None or cause_candidates.empty:
            return None
        matched = cause_candidates[
            (cause_candidates["event_type"] == row["event_type"])
            & (cause_candidates["target"] == row["product_name"])
        ]
        if matched.empty:
            return None
        return matched.iloc[0]

    @staticmethod
    def _recommendation_reason(row: pd.Series, cause) -> str:
        if cause is None:
            return f"{row['severity']} 등급 {row['event_type']} 이벤트 기반 권고입니다."
        return (
            f"{row['severity']} 등급 {row['event_type']} 이벤트와 "
            f"{cause['related_metric']} 상관 신호를 함께 반영했습니다."
        )


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
        cause_candidates: pd.DataFrame | None = None,
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
            "## 근거 요약",
            f"- High 이벤트 {int((events['severity'] == 'High').sum())}건, 전체 액션 {len(actions)}건입니다.",
        ]
        if cause_candidates is not None and not cause_candidates.empty:
            top = cause_candidates.iloc[0]
            lines.append(
                f"- 주요 원인 후보: {top['target']}의 {top['event_type']}은 "
                f"{top['related_metric']}와 r={top['correlation']:.2f} 관계를 보입니다."
            )
        lines.extend(
            [
                "- 위 원인 후보는 확정 원인이 아니라 검토 가설입니다.",
                "",
                "## 승인·결정 필요",
            ]
        )
        if approvals.empty:
            lines.append("- 현재 즉시 승인이 필요한 High 액션은 없습니다.")
        else:
            lines.extend(
                [
                    f"- [{row.team}] {row.target}: {row.instruction}"
                    for row in approvals.itertuples()
                ]
            )
        lines.extend(
            [
                "",
                "## 역할별 후속 확인",
                "- 마케팅: 광고 효율 하락과 클릭·전환 변화를 확인",
                "- MD/운영: 품절 위험과 판매 속도 기반 발주 판단",
                "- CRM/CS: 리뷰·문의·환불 신호의 고객 영향 확인",
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
    cause_candidates: pd.DataFrame


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


def _format_change(value) -> str:
    if value is None or pd.isna(value):
        return "계산 불가"
    return f"{float(value):+.1%}"
