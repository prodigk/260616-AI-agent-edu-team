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
    cause_candidates: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    assignment: AgentAssignment,
    source_answers: list[dict[str, str]] | None = None,
) -> str:
    q = question.strip().lower()
    context = f"{start:%Y-%m-%d}부터 {end:%Y-%m-%d}까지"
    agent_key = assignment.agent.key

    if agent_key == "product_lead" and source_answers:
        lines = [
            f"{context} 제품총괄 종합 답변입니다.",
            "담당별 답변을 비교해 중복은 줄이고 실행 우선순위 중심으로 정리했습니다.",
            "",
            "## 핵심 판단",
        ]
        for answer in source_answers[:5]:
            summary = answer.get("content", "").strip().splitlines()
            first_line = summary[0] if summary else "요약 가능한 답변이 없습니다."
            lines.append(f"- {answer.get('agent', '담당')}: {first_line[:180]}")
        lines.extend(
            [
                "",
                "## 제품총괄 권고",
                "- 원인 후보와 상관관계는 확정 원인이 아니라 검토 가설로 두고, High 이벤트부터 검증하세요.",
                "- 매출·재고 영향이 큰 항목은 MD/운영이 먼저 처리하고, 마케팅·CS는 고객 영향과 유입 품질을 병행 점검하세요.",
                "- 다음 액션은 담당팀, 마감일, 검증 지표를 함께 지정해 Tasks 페이지에서 추적하세요.",
            ]
        )
        return "\n".join(lines)

    if any(word in q for word in ["원인", "왜", "상관", "관계", "급상승", "급감", "roas 하락"]):
        if cause_candidates.empty:
            return (
                f"{context} 계산 가능한 원인 후보가 충분하지 않습니다.\n"
                "상관관계는 인과관계를 의미하지 않으므로 이벤트 전후 지표와 운영 맥락을 함께 확인하세요."
            )
        scoped = _prioritize_causes(cause_candidates, assignment).head(3)
        lines = [f"{context} 원인 후보 분석입니다."]
        for row in scoped.itertuples():
            lines.extend(
                [
                    f"\n- 확인된 사실: {row.target}의 {row.event_type} 이벤트와 "
                    f"{row.related_metric} 지표가 r={row.correlation:.2f} ({row.direction})로 함께 움직였습니다.",
                    f"  가능한 가설: {row.hypothesis}",
                    f"  추가 확인 필요 데이터: 프로모션, 요일성, 가격/노출 변경, 재고 운영 기록을 함께 확인하세요.",
                    f"  추천 액션: {row.recommended_action}",
                ]
            )
        lines.append("주의: 원인 후보는 확정 원인이 아니라 검토할 가설입니다.")
        return "\n".join(lines)

    if any(word in q for word in ["액션", "할 일", "조치", "권고", "추천"]):
        selected = _prioritize_actions(actions, assignment)
        high = selected[selected["priority"] == "High"] if not selected.empty else selected
        selected = high if not high.empty else selected
        if selected.empty:
            return "현재 생성된 역할별 권고 액션이 없습니다."
        lines = [
            f"{assignment.agent.label} 관점의 우선 권고입니다.",
            f"- 담당 관점 요약: {assignment.agent.description}",
            "- 우선 확인 지표: KPI, 이벤트 심각도, 원인 후보, 마감일",
        ]
        for row in selected.head(3).itertuples():
            reason = getattr(row, "recommendation_reason", "이벤트 기반 권고입니다.")
            lines.append(
                f"- 추천 액션: [{row.team} · {row.priority}] {row.target}: {row.instruction} "
                f"(권고 사유: {reason})"
            )
        lines.extend(
            [
                "- 예상 리스크: 원인 후보를 확정 원인으로 단정하면 잘못된 예산·재고 판단으로 이어질 수 있습니다.",
                "- 후속 질문 제안: 이 액션의 근거 이벤트와 관련 지표를 물어보세요.",
            ]
        )
        return "\n".join(lines)

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


def _prioritize_causes(
    cause_candidates: pd.DataFrame, assignment: AgentAssignment
) -> pd.DataFrame:
    if cause_candidates.empty or "domain" not in cause_candidates.columns:
        return cause_candidates
    preferred = cause_candidates[
        cause_candidates["domain"].isin(assignment.agent.domains)
    ]
    if preferred.empty:
        return cause_candidates
    remaining = cause_candidates[~cause_candidates.index.isin(preferred.index)]
    return pd.concat([preferred, remaining])


def _prioritize_actions(actions: pd.DataFrame, assignment: AgentAssignment) -> pd.DataFrame:
    if actions.empty or "team" not in actions.columns:
        return actions
    preferred = actions[actions["team"].isin(assignment.agent.teams)]
    if preferred.empty:
        return actions
    remaining = actions[~actions.index.isin(preferred.index)]
    return pd.concat([preferred, remaining])
