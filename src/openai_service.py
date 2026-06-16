from __future__ import annotations

import json
import os
from dataclasses import dataclass
from collections.abc import Iterator

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

from src.models import CorrelationResult
from src.role_agents import AgentAssignment


load_dotenv()


@dataclass(frozen=True)
class OpenAIAnswer:
    text: str
    model: str
    response_id: str | None = None


def configured_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-5.4-mini")


def is_openai_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def build_dashboard_context(
    kpis: dict[str, float],
    events: pd.DataFrame,
    correlations: CorrelationResult,
    actions: pd.DataFrame,
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

    return {
        "analysis_period": {
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
        },
        "selected_role": role,
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
        "priority_actions": action_records,
        "data_note": (
            "ROAS values are percentages. Correlation does not establish causation. "
            "Only aggregated dashboard context is included."
        ),
    }


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
        "액션을 구체적으로 인용하세요. 상관관계를 인과관계로 단정하지 마세요. "
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
