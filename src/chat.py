from __future__ import annotations

import pandas as pd

from src.models import CorrelationResult
from src.role_agents import AgentAssignment


def answer_dashboard_question(
    question: str,
    kpis: dict[str, float],
    events: pd.DataFrame,
    correlations: CorrelationResult,
    actions: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    assignment: AgentAssignment,
) -> str:
    q = question.strip().lower()
    context = f"{start:%Y-%m-%d}부터 {end:%Y-%m-%d}까지"
    agent_key = assignment.agent.key

    if agent_key == "inventory":
        risks = events[events["event_type"].isin(["품절", "품절 위험"])]
        if risks.empty:
            return f"{context} 품절 또는 품절 위험 이벤트는 없습니다."
        lines = [
            f"{context} 재고 대응이 필요한 상품은 {risks['product_name'].nunique()}개입니다."
        ]
        for row in risks.head(4).itertuples():
            lines.append(f"- {row.product_name}: {row.description}")
        lines.append("MD·운영팀 액션 보드에서 발주 우선순위를 확인하세요.")
        return "\n".join(lines)

    if agent_key == "sales_product":
        surges = events[events["event_type"] == "판매 급상승"]
        answer = (
            f"{context} 매출은 ₩{kpis['revenue']:,.0f}, 판매량은 "
            f"{kpis['quantity_sold']:,.0f}개입니다."
        )
        if not surges.empty:
            top = surges.sort_values("change_rate", ascending=False).iloc[0]
            answer += (
                f"\n가장 큰 판매 급상승은 {top['product_name']}이며 "
                f"3일 기준 대비 {top['change_rate']:.0%} 증가했습니다."
            )
        if not correlations.top_pairs.empty:
            related = correlations.top_pairs[
                correlations.top_pairs[["metric_a", "metric_b"]]
                .isin(["revenue", "quantity_sold"])
                .any(axis=1)
            ]
            if not related.empty:
                pair = related.iloc[0]
                answer += (
                    f"\n근거로 {pair['metric_a']}↔{pair['metric_b']} 상관계수 "
                    f"{pair['coefficient']:.2f}가 관찰됩니다."
                )
        return answer

    if agent_key == "marketing":
        marketing = events[events["domain"] == "마케팅"]
        answer = f"{context} 평균 ROAS는 {kpis['roas']:.1f}%, 광고비는 ₩{kpis['ad_spend']:,.0f}입니다."
        if marketing.empty:
            return answer + "\n전주 대비 20% 이상 하락한 채널은 탐지되지 않았습니다."
        return answer + "\n" + "\n".join(
            f"- {row.product_name}: {row.description}"
            for row in marketing.head(4).itertuples()
        )

    if agent_key == "product_planning" and any(
        word in q for word in ["액션", "할 일", "조치"]
    ):
        high = actions[actions["priority"] == "High"]
        selected = high if not high.empty else actions
        if selected.empty:
            return "현재 생성된 액션이 없습니다."
        lines = [f"우선 실행할 액션 {min(4, len(selected))}개입니다."]
        for row in selected.head(4).itertuples():
            lines.append(
                f"- [{row.team} · {row.priority}] {row.target}: {row.instruction}"
            )
        return "\n".join(lines)

    if agent_key == "product_planning" and any(
        word in q for word in ["상관", "관계", "원인"]
    ):
        if correlations.top_pairs.empty:
            return "선택 기간에는 계산 가능한 상관관계가 없습니다."
        lines = ["절대값 기준으로 함께 움직인 지표입니다."]
        for row in correlations.top_pairs.head(4).itertuples():
            lines.append(
                f"- {row.metric_a} ↔ {row.metric_b}: r={row.coefficient:.2f} ({row.direction})"
            )
        lines.append("상관관계는 인과관계를 의미하지 않습니다.")
        return "\n".join(lines)

    if agent_key == "customer_cs":
        return (
            f"{context} 신규 고객 {kpis['new_customers']:,.0f}명, "
            f"재구매 고객 {kpis['returning_customers']:,.0f}명, "
            f"평균 평점 {kpis['rating']:.2f}점입니다."
        )

    if agent_key == "product_planning":
        product_events = events[
            events["event_type"].isin(
                ["판매 급상승", "판매 급감", "인기상품 진입", "추천상품 성과 우수"]
            )
        ]
        lines = [f"{context} 제품 기획 관점에서 확인할 신호입니다."]
        for row in product_events.head(4).itertuples():
            lines.append(f"- {row.product_name}: {row.event_type} · {row.description}")
        if len(lines) == 1:
            lines.append("- 선택 기간에는 별도의 상품·추천 성과 이벤트가 없습니다.")
        lines.append("운영 신호를 제품 전략으로 확정하기 전 가격·프로모션 영향을 함께 검증하세요.")
        return "\n".join(lines)

    return (
        f"{context} 요약입니다.\n"
        f"- 매출 ₩{kpis['revenue']:,.0f}, 주문 {kpis['orders']:,.0f}건, ROAS {kpis['roas']:.1f}%\n"
        f"- High 이벤트 {int((events['severity'] == 'High').sum())}건\n"
        f"- 실행 액션 {len(actions)}건\n"
        "매출, 품절 위험, 광고 효율, 상관관계, 우선 액션 중 하나를 물어보세요."
    )
