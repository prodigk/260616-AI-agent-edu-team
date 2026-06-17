from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


AUTO_AGENT = "자동 배정"
PRODUCT_LEAD_AGENT = "제품총괄"
AGENT_DIR = Path(__file__).resolve().parents[1] / "agent"


@dataclass(frozen=True)
class RoleAgent:
    key: str
    label: str
    description: str
    instructions: str
    keywords: tuple[str, ...]
    domains: tuple[str, ...]
    teams: tuple[str, ...]
    dashboard_page: str


@dataclass(frozen=True)
class AgentAssignment:
    agent: RoleAgent
    mode: str
    reason: str


def load_agent_instruction(key: str, fallback: str) -> str:
    path = AGENT_DIR / f"{key}.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return fallback


ROLE_AGENTS = (
    RoleAgent(
        key="marketing",
        label="마케팅 담당",
        description="광고비, 채널, 캠페인, ROAS와 유입·전환 성과",
        instructions=load_agent_instruction(
            "marketing",
            (
                "마케팅 성과 관점에서 채널·캠페인 효율과 예산 우선순위를 설명하세요. "
                "ROAS, 광고비, 클릭, 전환 및 마케팅 이벤트를 먼저 근거로 사용하세요."
            ),
        ),
        keywords=(
            "마케팅",
            "광고",
            "캠페인",
            "roas",
            "채널",
            "소재",
            "타깃",
            "클릭",
            "전환",
            "유입",
            "예산",
        ),
        domains=("마케팅",),
        teams=("마케팅",),
        dashboard_page="종합 현황",
    ),
    RoleAgent(
        key="customer_cs",
        label="고객 CS 담당",
        description="신규·재구매 고객, 리뷰, 평점과 고객 문의",
        instructions=load_agent_instruction(
            "customer_cs",
            (
                "고객 경험과 CS 관점에서 신규·재구매 고객, 리뷰, 평점, 문의와 환불 신호를 "
                "우선 설명하고 고객 영향과 후속 대응을 제안하세요."
            ),
        ),
        keywords=(
            "고객",
            "cs",
            "리뷰",
            "평점",
            "문의",
            "환불",
            "불만",
            "재구매",
            "신규 고객",
            "가입",
            "이탈",
            "장바구니",
        ),
        domains=("고객·CS",),
        teams=("CRM/CS",),
        dashboard_page="종합 현황",
    ),
    RoleAgent(
        key="inventory",
        label="재고관리 담당",
        description="현재 재고, 안전재고, 품절 위험과 발주 우선순위",
        instructions=load_agent_instruction(
            "inventory",
            (
                "재고 운영 관점에서 현재 재고, 안전재고, 품절 위험과 판매 속도를 우선 "
                "설명하세요. 긴급도와 발주 또는 대체 상품 대응을 명확히 제시하세요."
            ),
        ),
        keywords=(
            "재고",
            "품절",
            "안전재고",
            "발주",
            "입고",
            "소진",
            "stock",
            "물류",
            "재고관리",
        ),
        domains=("재고·추천",),
        teams=("MD", "운영"),
        dashboard_page="이벤트",
    ),
    RoleAgent(
        key="sales_product",
        label="매출 상품 담당",
        description="매출, 주문, 판매량과 상품별 판매 성과",
        instructions=load_agent_instruction(
            "sales_product",
            (
                "매출과 상품 운영 관점에서 매출, 주문, 판매량, 급등락 상품을 우선 설명하세요. "
                "전체 실적과 상품별 기여를 구분하고 바로 확인할 운영 포인트를 제시하세요."
            ),
        ),
        keywords=(
            "매출",
            "판매",
            "주문",
            "매출액",
            "판매량",
            "실적",
            "급상승",
            "급감",
            "베스트",
            "인기상품",
            "sales",
            "revenue",
        ),
        domains=("매출·상품",),
        teams=("MD",),
        dashboard_page="종합 현황",
    ),
    RoleAgent(
        key="product_planning",
        label="제품 기획 담당",
        description="상품 구성, 추천 성과, 인기상품과 제품 전략",
        instructions=load_agent_instruction(
            "product_planning",
            (
                "제품 기획 관점에서 상품 구성, 인기상품, 추천 성과, 가격·프로모션·신상품 "
                "기회를 종합하세요. 단기 운영 조치와 검증이 필요한 제품 가설을 구분하세요."
            ),
        ),
        keywords=(
            "제품 기획",
            "상품 기획",
            "기획",
            "신상품",
            "제품",
            "상품 구성",
            "추천",
            "추천상품",
            "카테고리",
            "가격",
            "프로모션",
            "전략",
            "인사이트",
            "기회",
            "상관",
            "관계",
            "원인",
            "액션",
            "조치",
            "할 일",
        ),
        domains=("매출·상품", "재고·추천"),
        teams=("MD", "마케팅"),
        dashboard_page="상관 분석",
    ),
    RoleAgent(
        key="product_lead",
        label=PRODUCT_LEAD_AGENT,
        description="담당별 답변을 종합·평가해 제품/운영 의사결정으로 정리하는 총괄",
        instructions=load_agent_instruction(
            "product_lead",
            (
                "제품총괄 관점에서 여러 담당자의 답변을 비교·종합하세요. "
                "Parallelization에서는 Aggregator로, Orchestrator에서는 Synthesizer로, "
                "Evaluator-optimizer에서는 LLM Call Evaluator로 행동하세요. "
                "중복을 줄이고 상충되는 내용은 판단 기준을 밝혀 정리하며, 최종 권고와 다음 액션을 명확히 제시하세요."
            ),
        ),
        keywords=(
            "제품총괄",
            "총괄",
            "종합",
            "최종",
            "의사결정",
            "우선순위",
            "평가",
            "검수",
            "퀄리티",
            "품질",
            "synthesize",
            "aggregate",
        ),
        domains=("매출·상품", "마케팅", "고객·CS", "재고·추천"),
        teams=("MD", "마케팅", "CRM/CS", "운영"),
        dashboard_page="상관 분석",
    ),
)

ROLE_AGENT_BY_LABEL = {agent.label: agent for agent in ROLE_AGENTS}
ROLE_AGENT_OPTIONS = [AUTO_AGENT, *ROLE_AGENT_BY_LABEL]


def assign_role_agent(question: str, requested: str = AUTO_AGENT) -> AgentAssignment:
    if requested != AUTO_AGENT:
        agent = ROLE_AGENT_BY_LABEL.get(requested)
        if agent is None:
            raise ValueError(f"지원하지 않는 담당 에이전트입니다: {requested}")
        return AgentAssignment(
            agent=agent,
            mode="직접 지정",
            reason=f"사용자가 {agent.label}을 답변 담당으로 지정했습니다.",
        )

    normalized = question.casefold()
    scored: list[tuple[int, int, RoleAgent, list[str]]] = []
    for index, agent in enumerate(ROLE_AGENTS):
        matched = [keyword for keyword in agent.keywords if keyword.casefold() in normalized]
        score = sum(3 if " " in keyword else 2 for keyword in matched)
        scored.append((score, -index, agent, matched))

    score, _, agent, matched = max(scored, key=lambda item: (item[0], item[1]))
    if score == 0:
        agent = ROLE_AGENT_BY_LABEL["매출 상품 담당"]
        reason = "특정 직무 키워드가 없어 전체 KPI를 가장 빠르게 설명할 담당으로 배정했습니다."
    else:
        keywords = ", ".join(matched[:3])
        reason = f"질문의 '{keywords}' 맥락을 감지해 배정했습니다."
    return AgentAssignment(agent=agent, mode="자동 배정", reason=reason)
