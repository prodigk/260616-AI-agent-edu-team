from __future__ import annotations

from dataclasses import dataclass

from src.role_agents import AUTO_AGENT


@dataclass(frozen=True)
class WorkflowPattern:
    workflow_type: str
    reason: str
    implementation_note: str


SEQUENTIAL_KEYWORDS = (
    "먼저",
    "다음",
    "단계",
    "순서",
    "초안",
    "검토",
    "보정",
    "정제",
    "분류 후",
    "요약 후",
)
ORCHESTRATOR_KEYWORDS = (
    "조사해",
    "찾아서",
    "여러 출처",
    "경쟁사",
    "복합",
    "계획 세워",
    "분해해서",
    "원인 찾아",
)
EVALUATOR_KEYWORDS = ("평가", "검수", "개선", "리뷰", "점수", "품질")


def select_workflow_pattern(question: str, target_agents: list[str]) -> WorkflowPattern:
    """Classify the answer path using Anthropic-style workflow patterns.

    The dashboard currently implements deterministic UI/code paths, so this
    function explains the actual path used rather than claiming unsupported
    multi-call workflows.
    """
    normalized = question.casefold()
    explicit_agents = [agent for agent in target_agents if agent != AUTO_AGENT]

    if len(explicit_agents) > 1:
        return WorkflowPattern(
            workflow_type="Parallelization",
            reason="여러 담당 에이전트를 독립 관점으로 실행해 답변을 나눠 생성했습니다.",
            implementation_note="선택된 담당별 답변을 순차 렌더링하지만, 논리적으로는 독립 작업을 병합하는 병렬화 패턴입니다.",
        )

    if target_agents == [AUTO_AGENT]:
        return WorkflowPattern(
            workflow_type="Routing",
            reason="질문 맥락을 먼저 분류해 가장 관련 있는 담당 에이전트로 라우팅했습니다.",
            implementation_note="키워드 기반 결정 로직으로 담당을 고른 뒤 대시보드 컨텍스트를 붙여 답변합니다.",
        )

    if any(keyword in normalized for keyword in SEQUENTIAL_KEYWORDS):
        return WorkflowPattern(
            workflow_type="별도 패턴: Workflow intent detected",
            reason="질문에는 순차 처리 의도가 있지만 현재 채팅은 실제 다중 단계 LLM 체인을 실행하지 않습니다.",
            implementation_note="Prompt chaining으로 고도화하려면 단계별 LLM 호출과 중간 검증 기준을 별도 구현해야 합니다.",
        )

    if any(keyword in normalized for keyword in ORCHESTRATOR_KEYWORDS):
        return WorkflowPattern(
            workflow_type="별도 패턴: Orchestration intent detected",
            reason="질문에는 동적 작업 분해 의도가 있지만 현재 앱은 사전 정의된 대시보드 컨텍스트만 사용합니다.",
            implementation_note="Orchestrator-workers로 고도화하려면 worker 생성 한도, 도구 목록, 합성 규칙을 코드로 정의해야 합니다.",
        )

    if any(keyword in normalized for keyword in EVALUATOR_KEYWORDS):
        return WorkflowPattern(
            workflow_type="별도 패턴: Evaluator-optimizer",
            reason="평가나 개선 루프가 필요한 표현이 있지만 현재 앱은 평가-개선 반복을 실행하지 않습니다.",
            implementation_note="사용자가 지정한 5개 패턴 밖의 Anthropic 추가 패턴입니다.",
        )

    return WorkflowPattern(
        workflow_type="Augmented LLM",
        reason="선택된 담당 프롬프트에 집계된 대시보드 KPI·이벤트·액션 컨텍스트를 붙여 단일 답변을 생성했습니다.",
        implementation_note="전체 CSV 원본이 아니라 집계 컨텍스트만 LLM 입력으로 전달합니다.",
    )
