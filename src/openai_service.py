from __future__ import annotations

import json
import os
from dataclasses import dataclass
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

from src.models import CorrelationResult
from src.role_agents import AgentAssignment


load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "db"


@dataclass(frozen=True)
class OpenAIAnswer:
    text: str
    model: str
    response_id: str | None = None


def configured_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-5.4-mini")


def is_openai_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _load_optional_csv(filename: str, date_column: str = "date") -> pd.DataFrame:
    path = DATA_DIR / filename
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if date_column in frame.columns:
        frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce")
    return frame


def _period_frame(frame: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, date_column="date") -> pd.DataFrame:
    if frame.empty or date_column not in frame.columns:
        return frame.iloc[0:0].copy()
    return frame[frame[date_column].between(start, end)].copy()


def _corr(left: pd.Series, right: pd.Series) -> float | None:
    pair = pd.concat(
        [
            pd.to_numeric(left, errors="coerce"),
            pd.to_numeric(right, errors="coerce"),
        ],
        axis=1,
    ).dropna()
    if len(pair) < 3 or pair.iloc[:, 0].nunique() < 2 or pair.iloc[:, 1].nunique() < 2:
        return None
    return float(pair.iloc[:, 0].corr(pair.iloc[:, 1]))


def build_auxiliary_context(start: pd.Timestamp, end: pd.Timestamp) -> dict[str, object]:
    days = max(1, (end - start).days + 1)
    previous_start = start - pd.Timedelta(days=days)
    previous_end = start - pd.Timedelta(days=1)
    weekly_context_start = start - pd.Timedelta(days=55)

    campaign = _load_optional_csv("campaign_product_performance.csv")
    hourly = _load_optional_csv("hourly_web_events.csv")
    segments = _load_optional_csv("customer_segment_data.csv")
    cross_sell = _load_optional_csv("cross_sell_data.csv", "week_start")
    inventory_loss = _load_optional_csv("inventory_loss_estimate.csv", "week_start")
    retention = _load_optional_csv("product_retention_data.csv", "week_start")
    recommendations = _load_optional_csv("recommendation_log.csv")
    pricing = _load_optional_csv("pricing_promotion_data.csv")
    delivery = _load_optional_csv("delivery_experience_data.csv")
    brand_search = _load_optional_csv("brand_search_data.csv")

    context: dict[str, object] = {}

    current_campaign = _period_frame(campaign, start, end)
    previous_campaign = _period_frame(campaign, previous_start, previous_end)
    if not current_campaign.empty:
        channel = current_campaign.groupby("channel", as_index=False).agg(
            ad_spend=("ad_spend", "sum"),
            clicks=("clicks", "sum"),
            conversions=("conversions", "sum"),
            attributed_revenue=("attributed_revenue", "sum"),
        )
        channel["ROAS"] = channel["attributed_revenue"].div(channel["ad_spend"]).mul(100)
        channel["conversion_rate"] = channel["conversions"].div(channel["clicks"].replace(0, pd.NA))
        if not previous_campaign.empty:
            previous = previous_campaign.groupby("channel").agg(
                ad_spend=("ad_spend", "sum"),
                attributed_revenue=("attributed_revenue", "sum"),
            )
            previous["previous_ROAS"] = previous["attributed_revenue"].div(previous["ad_spend"]).mul(100)
            channel = channel.merge(previous[["previous_ROAS"]], on="channel", how="left")
            channel["ROAS_change"] = channel["ROAS"].div(channel["previous_ROAS"]).sub(1)
        context["channel_efficiency"] = _records(
            channel.sort_values("ROAS", ascending=False).head(6),
            ["channel", "ad_spend", "clicks", "conversions", "ROAS", "conversion_rate", "ROAS_change"],
        )
        creative = current_campaign.groupby("creative_type", as_index=False).agg(
            clicks=("clicks", "sum"),
            conversions=("conversions", "sum"),
            ad_spend=("ad_spend", "sum"),
            attributed_revenue=("attributed_revenue", "sum"),
        )
        creative["ROAS"] = creative["attributed_revenue"].div(creative["ad_spend"]).mul(100)
        context["top_creatives"] = _records(
            creative.sort_values("clicks", ascending=False).head(5),
            ["creative_type", "clicks", "conversions", "ROAS"],
        )
        category = current_campaign.groupby("category", as_index=False).agg(
            ad_spend=("ad_spend", "sum"),
            attributed_revenue=("attributed_revenue", "sum"),
        )
        category["ROAS"] = category["attributed_revenue"].div(category["ad_spend"]).mul(100)
        context["category_ad_efficiency"] = _records(
            category.sort_values("ROAS", ascending=False).head(6),
            ["category", "ad_spend", "attributed_revenue", "ROAS"],
        )
        coupon = current_campaign.groupby("coupon_campaign", as_index=False).agg(
            ad_spend=("ad_spend", "sum"),
            attributed_revenue=("attributed_revenue", "sum"),
            conversions=("conversions", "sum"),
        )
        coupon["ROAS"] = coupon["attributed_revenue"].div(coupon["ad_spend"]).mul(100)
        context["coupon_impact"] = _records(
            coupon, ["coupon_campaign", "ad_spend", "attributed_revenue", "conversions", "ROAS"]
        )
        channel_corr_records = []
        for channel_name, group in current_campaign.groupby("channel"):
            if len(group) < 3:
                continue
            spend_roas_corr = _corr(group["ad_spend"], group["ROAS"])
            clicks_repurchase_corr = None
            if "rating_signal" in group.columns:
                clicks_repurchase_corr = _corr(group["clicks"], group["rating_signal"])
            channel_corr_records.append(
                {
                    "channel": channel_name,
                    "ad_spend_roas_correlation": spend_roas_corr,
                    "clicks_rating_signal_correlation": clicks_repurchase_corr,
                    "avg_ROAS": group["ROAS"].mean(),
                    "avg_click_through_rate": group.get("click_through_rate", pd.Series(dtype=float)).mean(),
                }
            )
        if channel_corr_records:
            context["channel_correlation_patterns"] = _records(
                pd.DataFrame(channel_corr_records).sort_values(
                    "ad_spend_roas_correlation", ascending=False
                ),
                [
                    "channel",
                    "ad_spend_roas_correlation",
                    "clicks_rating_signal_correlation",
                    "avg_ROAS",
                    "avg_click_through_rate",
                ],
            )

    current_hourly = _period_frame(hourly, start, end)
    if not current_hourly.empty:
        by_hour = current_hourly.groupby("hour", as_index=False).agg(
            clicks=("clicks", "sum"),
            conversions=("conversions", "sum"),
        )
        by_hour["conversion_rate"] = by_hour["conversions"].div(by_hour["clicks"].replace(0, pd.NA))
        context["hourly_click_conversion"] = _records(
            by_hour.sort_values("clicks", ascending=False).head(8),
            ["hour", "clicks", "conversions", "conversion_rate"],
        )

    current_segments = _period_frame(segments, start, end)
    if not current_segments.empty:
        segment = current_segments.groupby("customer_segment", as_index=False).agg(
            signups=("signups", "sum"),
            returning_customers=("returning_customers", "sum"),
            repeat_purchase_rate=("repeat_purchase_rate", "mean"),
            cart_abandon_rate=("cart_abandon_rate", "mean"),
        )
        context["customer_segments"] = _records(
            segment.sort_values("cart_abandon_rate", ascending=False).head(6),
            ["customer_segment", "signups", "returning_customers", "repeat_purchase_rate", "cart_abandon_rate"],
        )
        segment_corr_records = []
        for segment_name, group in current_segments.groupby("customer_segment"):
            if len(group) < 3 or not {"clicks", "attributed_revenue"}.issubset(group.columns):
                continue
            segment_corr_records.append(
                {
                    "customer_segment": segment_name,
                    "clicks_revenue_correlation": _corr(group["clicks"], group["attributed_revenue"]),
                    "signups_cart_abandon_correlation": _corr(group["signups"], group["cart_abandon_rate"]),
                    "avg_cart_abandon_rate": group["cart_abandon_rate"].mean(),
                    "avg_repeat_purchase_rate": group["repeat_purchase_rate"].mean(),
                }
            )
        if segment_corr_records:
            context["customer_segment_correlation_patterns"] = _records(
                pd.DataFrame(segment_corr_records).sort_values(
                    "clicks_revenue_correlation", ascending=False
                ).head(8),
                [
                    "customer_segment",
                    "clicks_revenue_correlation",
                    "signups_cart_abandon_correlation",
                    "avg_cart_abandon_rate",
                    "avg_repeat_purchase_rate",
                ],
            )

    current_loss = _period_frame(inventory_loss, weekly_context_start, end, "week_start")
    if not current_loss.empty:
        context["inventory_shortage_loss"] = _records(
            current_loss.sort_values("estimated_lost_revenue", ascending=False).head(8),
            ["week_start", "product_name", "category", "shortage_days", "stockout_days", "estimated_lost_revenue", "weekly_inquiry_count"],
        )
        inventory_corr_records = []
        for product_name, group in current_loss.groupby("product_name"):
            if len(group) < 3:
                continue
            inventory_corr_records.append(
                {
                    "product_name": product_name,
                    "category": group["category"].iloc[-1],
                    "stockout_inquiry_correlation": _corr(group["stockout_days"], group["weekly_inquiry_count"]),
                    "stock_sales_loss_correlation": _corr(group["avg_stock"], group["estimated_lost_revenue"]),
                    "total_stockout_days": group["stockout_days"].sum(),
                    "estimated_lost_revenue": group["estimated_lost_revenue"].sum(),
                }
            )
        if inventory_corr_records:
            context["inventory_correlation_patterns"] = _records(
                pd.DataFrame(inventory_corr_records).sort_values(
                    "stockout_inquiry_correlation", ascending=False
                ).head(8),
                [
                    "product_name",
                    "category",
                    "stockout_inquiry_correlation",
                    "stock_sales_loss_correlation",
                    "total_stockout_days",
                    "estimated_lost_revenue",
                ],
            )

    current_cross_sell = _period_frame(cross_sell, weekly_context_start, end, "week_start")
    if not current_cross_sell.empty:
        context["cross_sell_patterns"] = _records(
            current_cross_sell.sort_values("lift_score", ascending=False).head(8),
            ["week_start", "primary_product_name", "secondary_product_name", "primary_category", "secondary_category", "cross_sell_orders", "lift_score"],
        )

    current_retention = _period_frame(retention, weekly_context_start, end, "week_start")
    if not current_retention.empty:
        context["product_retention"] = _records(
            current_retention.sort_values("repeat_purchase_rate", ascending=False).head(8),
            ["week_start", "product_name", "category", "rating", "review_count", "repeat_purchase_rate", "returning_customer_orders"],
        )
        retention_corr_records = []
        for product_name, group in current_retention.groupby("product_name"):
            if len(group) < 3:
                continue
            retention_corr_records.append(
                {
                    "product_name": product_name,
                    "category": group["category"].iloc[-1],
                    "rating_repurchase_correlation": _corr(group["rating"], group["repeat_purchase_rate"]),
                    "turnover_review_correlation": _corr(group["returning_customer_orders"], group["review_count"]),
                    "avg_rating": group["rating"].mean(),
                    "avg_repeat_purchase_rate": group["repeat_purchase_rate"].mean(),
                }
            )
        if retention_corr_records:
            context["retention_correlation_patterns"] = _records(
                pd.DataFrame(retention_corr_records).sort_values(
                    "rating_repurchase_correlation", ascending=True
                ).head(8),
                [
                    "product_name",
                    "category",
                    "rating_repurchase_correlation",
                    "turnover_review_correlation",
                    "avg_rating",
                    "avg_repeat_purchase_rate",
                ],
            )

    current_recs = _period_frame(recommendations, start, end)
    if not current_recs.empty:
        recs = current_recs.groupby("product_name", as_index=False).agg(
            recommended_count=("recommended_count", "sum"),
            click_count=("click_count", "sum"),
            conversion_count=("conversion_count", "sum"),
        )
        recs["recommendation_conversion_rate"] = recs["conversion_count"].div(
            recs["recommended_count"].replace(0, pd.NA)
        )
        context["recommendation_product_rates"] = _records(
            recs.sort_values("recommendation_conversion_rate", ascending=False).head(10),
            ["product_name", "recommended_count", "click_count", "conversion_count", "recommendation_conversion_rate"],
        )
        rec_corr_records = []
        for product_name, group in current_recs.groupby("product_name"):
            if len(group) < 3:
                continue
            rec_ctr = group["click_count"].div(group["recommended_count"].replace(0, pd.NA))
            rec_corr_records.append(
                {
                    "product_name": product_name,
                    "recommendation_ctr_conversion_correlation": _corr(rec_ctr, group["conversion_count"]),
                    "exposure_purchase_correlation": _corr(group["recommended_count"], group["conversion_count"]),
                    "avg_recommendation_ctr": rec_ctr.mean(),
                    "total_conversions": group["conversion_count"].sum(),
                }
            )
        if rec_corr_records:
            context["recommendation_correlation_patterns"] = _records(
                pd.DataFrame(rec_corr_records).sort_values(
                    "recommendation_ctr_conversion_correlation", ascending=True
                ).head(8),
                [
                    "product_name",
                    "recommendation_ctr_conversion_correlation",
                    "exposure_purchase_correlation",
                    "avg_recommendation_ctr",
                    "total_conversions",
                ],
            )

    current_pricing = _period_frame(pricing, start, end)
    if not current_pricing.empty:
        pricing_corr_records = []
        for product_name, group in current_pricing.groupby("product_name"):
            if len(group) < 3:
                continue
            pricing_corr_records.append(
                {
                    "product_name": product_name,
                    "category": group["category"].iloc[-1],
                    "discount_revenue_correlation": _corr(group["discount_rate"], group["daily_revenue"]),
                    "selling_price_revenue_correlation": _corr(group["selling_price"], group["daily_revenue"]),
                    "avg_discount_rate": group["discount_rate"].mean(),
                    "revenue": group["daily_revenue"].sum(),
                    "price_increase_days": int((group["price_change_type"] == "increase").sum()),
                }
            )
        if pricing_corr_records:
            pricing_patterns = pd.DataFrame(pricing_corr_records)
            context["pricing_correlation_patterns"] = _records(
                pricing_patterns.reindex(
                    pricing_patterns["discount_revenue_correlation"].abs().sort_values(ascending=False).index
                ).head(10),
                [
                    "product_name",
                    "category",
                    "discount_revenue_correlation",
                    "selling_price_revenue_correlation",
                    "avg_discount_rate",
                    "revenue",
                    "price_increase_days",
                ],
            )
            context["price_increase_risk"] = _records(
                pricing_patterns[
                    pricing_patterns["price_increase_days"] > 0
                ].sort_values("selling_price_revenue_correlation").head(6),
                [
                    "product_name",
                    "category",
                    "selling_price_revenue_correlation",
                    "price_increase_days",
                    "revenue",
                ],
            )

    current_delivery = _period_frame(delivery, start, end)
    if not current_delivery.empty:
        delivery_corr_records = []
        for product_name, group in current_delivery.groupby("product_name"):
            if len(group) < 3:
                continue
            delivery_corr_records.append(
                {
                    "product_name": product_name,
                    "category": group["category"].iloc[-1],
                    "delay_rating_correlation": _corr(group["delayed_shipments"], group["rating"]),
                    "delivery_issue_rating_correlation": _corr(group["delivery_issue_rate"], group["rating"]),
                    "delayed_shipments": group["delayed_shipments"].sum(),
                    "avg_delivery_days": group["avg_delivery_days"].mean(),
                    "avg_rating": group["rating"].mean(),
                }
            )
        if delivery_corr_records:
            context["delivery_rating_risk"] = _records(
                pd.DataFrame(delivery_corr_records).sort_values(
                    "delay_rating_correlation"
                ).head(8),
                [
                    "product_name",
                    "category",
                    "delay_rating_correlation",
                    "delivery_issue_rating_correlation",
                    "delayed_shipments",
                    "avg_delivery_days",
                    "avg_rating",
                ],
            )

    current_brand_search = _period_frame(brand_search, start, end)
    if not current_brand_search.empty:
        brand_corr_records = []
        for (campaign, channel), group in current_brand_search.groupby(["campaign", "channel"]):
            if len(group) < 3:
                continue
            active_search = group.loc[group["campaign_active"] == 1, "brand_search_volume"].mean()
            inactive_search = group.loc[group["campaign_active"] == 0, "brand_search_volume"].mean()
            brand_corr_records.append(
                {
                    "campaign": campaign,
                    "channel": channel,
                    "campaign_active_search_correlation": _corr(group["campaign_active"], group["brand_search_volume"]),
                    "active_avg_search_volume": active_search,
                    "inactive_avg_search_volume": inactive_search,
                    "search_lift": active_search - inactive_search,
                    "ad_spend_search_correlation": _corr(group["ad_spend"], group["brand_search_volume"]),
                }
            )
        if brand_corr_records:
            context["brand_search_campaign_patterns"] = _records(
                pd.DataFrame(brand_corr_records).sort_values(
                    "campaign_active_search_correlation", ascending=False
                ).head(8),
                [
                    "campaign",
                    "channel",
                    "campaign_active_search_correlation",
                    "active_avg_search_volume",
                    "inactive_avg_search_volume",
                    "search_lift",
                    "ad_spend_search_correlation",
                ],
            )

    return context


def build_dashboard_context(
    kpis: dict[str, float],
    events: pd.DataFrame,
    correlations: CorrelationResult,
    actions: pd.DataFrame,
    cause_candidates: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    role: str,
    assignment: AgentAssignment,
) -> dict[str, object]:
    event_fields = [
        "date",
        "event_type",
        "domain",
        "product_name",
        "severity",
        "description",
    ]
    action_fields = [
        "team",
        "priority",
        "target",
        "due_date",
        "instruction",
        "status",
    ]
    correlation_fields = [
        "metric_a",
        "metric_b",
        "coefficient",
        "direction",
        "sample_size",
    ]
    cause_fields = [
        "event_date",
        "event_type",
        "target",
        "related_metric",
        "correlation",
        "direction",
        "related_metric_change",
        "hypothesis",
        "confidence",
        "recommended_action",
        "caution",
    ]

    prioritized_events = _prioritize(
        events, "domain", set(assignment.agent.domains)
    )
    prioritized_actions = _prioritize(
        actions, "team", set(assignment.agent.teams)
    )
    event_records = _records(prioritized_events.head(20), event_fields)
    action_records = _records(prioritized_actions.head(15), action_fields)
    correlation_records = _records(
        correlations.top_pairs.head(10), correlation_fields
    )
    cause_records = _records(cause_candidates.head(10), cause_fields)

    return {
        "analysis_period": {
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
        },
        "answer_agent": {
            "name": assignment.agent.label,
            "assignment_mode": assignment.mode,
            "assignment_reason": assignment.reason,
            "specialty": assignment.agent.description,
            "focus_domains": list(assignment.agent.domains),
            "focus_teams": list(assignment.agent.teams),
            "suggested_dashboard_page": assignment.agent.dashboard_page,
        },
        "kpis": {key: round(float(value), 4) for key, value in kpis.items()},
        "event_summary": {
            "total": int(len(events)),
            "high": int((events["severity"] == "High").sum()),
            "medium": int((events["severity"] == "Medium").sum()),
            "low": int((events["severity"] == "Low").sum()),
        },
        "top_events": event_records,
        "top_correlations": correlation_records,
        "cause_candidates": cause_records,
        "priority_actions": action_records,
        "auxiliary_analysis": build_auxiliary_context(start, end),
        "data_note": (
            "ROAS values are percentages. Correlation does not establish causation. "
            "Cause candidates are hypotheses, not confirmed root causes. "
            "Only aggregated dashboard context is included."
        ),
    }


def polish_report_with_openai(report_markdown: str) -> str:
    if not is_openai_configured():
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")
    client = OpenAI(timeout=25.0, max_retries=1)
    response = client.responses.create(
        model=configured_model(),
        instructions=(
            "당신은 한국어 커머스 운영 리포트 에디터입니다. 제공된 Markdown 리포트를 "
            "더 자연스러운 내러티브로 다듬되, 숫자·이벤트·액션을 바꾸거나 새 사실을 "
            "추가하지 마세요. '확인된 데이터'와 'AI 해석/가설'을 구분하고, "
            "상관관계는 인과관계가 아니라는 주의 문구를 유지하세요."
        ),
        input=[
            {
                "role": "user",
                "content": "다음 리포트를 Markdown 형식으로 다듬어 주세요:\n\n"
                + report_markdown,
            }
        ],
    )
    text = response.output_text.strip()
    if not text:
        raise RuntimeError("OpenAI API가 빈 리포트를 반환했습니다.")
    return text


def ask_openai(
    question: str,
    context: dict[str, object],
    assignment: AgentAssignment,
    conversation: list[dict[str, str]] | None = None,
) -> OpenAIAnswer:
    if not is_openai_configured():
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")

    model = configured_model()
    client = OpenAI(timeout=25.0, max_retries=1)
    response = client.responses.create(
        model=model,
        instructions=_instructions(assignment),
        input=_input_items(question, context, conversation),
    )
    text = response.output_text.strip()
    if not text:
        raise RuntimeError("OpenAI API가 빈 응답을 반환했습니다.")
    return OpenAIAnswer(
        text=text,
        model=model,
        response_id=getattr(response, "id", None),
    )


def stream_openai_text(
    question: str,
    context: dict[str, object],
    assignment: AgentAssignment,
    conversation: list[dict[str, str]] | None = None,
) -> Iterator[str]:
    if not is_openai_configured():
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")

    client = OpenAI(timeout=25.0, max_retries=1)
    stream = client.responses.create(
        model=configured_model(),
        instructions=_instructions(assignment),
        input=_input_items(question, context, conversation),
        stream=True,
    )
    for event in stream:
        delta = _event_text_delta(event)
        if delta:
            yield delta


def _input_items(
    question: str,
    context: dict[str, object],
    conversation: list[dict[str, str]] | None = None,
) -> list[dict[str, object]]:
    recent_conversation = (conversation or [])[-6:]
    input_items: list[dict[str, object]] = [
        {
            "role": "user",
            "content": (
                "현재 대시보드 컨텍스트:\n"
                + json.dumps(context, ensure_ascii=False, indent=2)
            ),
        }
    ]
    for message in recent_conversation:
        if message.get("role") in {"user", "assistant"} and message.get("content"):
            input_items.append(
                {"role": message["role"], "content": message["content"]}
            )
    input_items.append({"role": "user", "content": question})
    return input_items


def _instructions(assignment: AgentAssignment) -> str:
    return (
        f"당신은 AI 커머스 운영 조직의 '{assignment.agent.label}'입니다. "
        f"{assignment.agent.instructions} 제공된 대시보드 컨텍스트만 "
        "근거로 답하세요. 먼저 결론을 말하고, 근거가 있으면 KPI·이벤트·상관계수·"
        "원인 후보·액션을 구체적으로 인용하세요. 원인 분석 질문에는 가능하면 "
        "'확인된 사실', '가능한 가설', '추가 확인 필요 데이터', '추천 액션'으로 "
        "나눠 답하세요. 상관관계를 인과관계로 단정하지 마세요. "
        "컨텍스트에 source_agent_answers가 있으면 제품총괄처럼 담당별 답변을 평가하고 "
        "중복·충돌·누락을 정리한 최종 종합 답변을 작성하세요. "
        "담당팀과 다음 행동이 명확한 경우 짧은 실행 제안으로 마무리하세요. "
        "컨텍스트에 없는 수치나 사실을 만들지 말고, 확인할 수 없으면 그렇게 말하세요. "
        "답변은 읽기 쉬운 3~8문장 또는 짧은 불릿으로 작성하세요."
    )


def _event_text_delta(event: object) -> str:
    delta = getattr(event, "delta", None)
    if isinstance(delta, str):
        return delta
    event_type = getattr(event, "type", "")
    if event_type == "response.output_text.delta" and delta:
        return str(delta)
    if isinstance(event, dict):
        if isinstance(event.get("delta"), str):
            return event["delta"]
        if event.get("type") == "response.output_text.delta" and event.get("delta"):
            return str(event["delta"])
    return ""


def _records(frame: pd.DataFrame, fields: list[str]) -> list[dict[str, object]]:
    if frame.empty:
        return []
    selected = frame[[field for field in fields if field in frame.columns]].copy()
    for column in selected.columns:
        if pd.api.types.is_datetime64_any_dtype(selected[column]):
            selected[column] = selected[column].dt.strftime("%Y-%m-%d")
    selected = selected.replace({np_value: None for np_value in [float("inf"), float("-inf")]})
    return json.loads(selected.to_json(orient="records", date_format="iso"))


def _prioritize(
    frame: pd.DataFrame, column: str, preferred_values: set[str]
) -> pd.DataFrame:
    if frame.empty or column not in frame.columns:
        return frame
    preferred = frame[frame[column].isin(preferred_values)]
    remaining = frame[~frame.index.isin(preferred.index)]
    return pd.concat([preferred, remaining])
