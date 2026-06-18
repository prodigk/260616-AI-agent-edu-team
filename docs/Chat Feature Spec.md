# Chat Feature Spec

이 문서는 AI 커머스 운영 대시보드의 우측 채팅 기능을 별도로 관리하기 위한 제품·개발 스펙입니다. 채팅은 이 대시보드의 핵심 경험이며, 대시보드의 현재 필터, KPI, 이벤트, 상관관계, 원인 후보, 액션을 바탕으로 운영자가 바로 의사결정을 내릴 수 있게 돕습니다.

## 1. 목표

- 사용자가 현재 선택한 분석 기간과 역할 맥락에서 질문할 수 있어야 합니다.
- 답변은 전체 CSV 원본이 아니라 집계된 대시보드 컨텍스트에 grounded되어야 합니다.
- OpenAI Responses API가 가능하면 LLM 답변을 사용하고, 실패하거나 키가 없으면 deterministic fallback 답변으로 전환해야 합니다.
- 채팅 답변은 담당 에이전트, 배정 방식, 배정 근거, workflow pattern, 출처를 명확히 보여야 합니다.
- 한국어 운영자에게 바로 실행 가능한 권고를 제공해야 합니다.

## 2. 주요 코드 위치

- `dashboard.py`
  - `render_chat_panel`: 우측 채팅 패널 전체 UI
  - `queue_chat_question`: 사용자 질문을 `pending_chat`에 등록
  - `render_streaming_chat_answer`: assistant 답변 스트리밍 렌더링
  - `generate_chat_answer`: 화면에 표시하지 않는 내부 담당 답변 생성
  - `append_assistant_messages`: 답변 메시지를 세션 히스토리에 저장
  - `append_chat_log`: 질문/답변을 `chat.txt`에 append 저장
  - `scroll_chat_to_bottom`: 채팅 히스토리 스크롤 갱신
- `src/role_agents.py`
  - 답변 담당 에이전트 메타데이터와 라우팅 정의
  - deterministic 자동 배정 로직
- `agent/`
  - 답변 담당별 Markdown 지침
- `src/openai_service.py`
  - `build_dashboard_context`: OpenAI에 보낼 집계 컨텍스트 생성
  - `stream_openai_text`: OpenAI Responses API 스트리밍
  - `_instructions`: 역할별 공통 시스템 지침
- `src/chat.py`
  - OpenAI 실패 또는 미설정 시 fallback 답변
- `src/workflow_patterns.py`
  - 질문과 담당 선택에 따른 LLM workflow pattern 표시

## 3. UI 계약

- 채팅 패널은 모든 분석 페이지 오른쪽에 표시합니다.
- 데스크톱에서는 `chat_panel_shell`이 viewport fixed입니다.
  - top/right/bottom margin: 16px
  - 메시지 히스토리만 스크롤
  - 담당 선택 UI와 입력 폼은 하단 고정
- 1100px 이하에서는 normal document flow로 돌아갑니다.
- keyed Streamlit 컨테이너 이름은 유지합니다.
  - `chat_panel_shell`
  - `chat_history`
  - `chat_agent_selector`
- assistant 메시지는 avatar 옆에 담당 이름을 보여주고, 답변은 다음 줄에 표시합니다.
- 답변 하단에는 workflow pattern과 선택 이유를 표시합니다.
- OpenAI model명은 각 답변 아래에 반복 표시하지 않습니다. 연결 상태는 패널 header에서만 표시할 수 있습니다.
- fallback 답변일 때는 `규칙 기반` 또는 `규칙 기반 fallback` 출처를 표시합니다.
- 패널 상단은 답변 영역 확보를 우선하며, 현재 기간 맥락은 한 줄 요약으로만 노출합니다.
- 담당 선택 영역은 현재 답변 모드 카드, 빠른 전환 버튼, 상세 담당 선택 순서로 구성합니다.
- 제품총괄은 자주 쓰는 종합 모드이므로 담당 선택 popover 안에 숨기지 않고 빠른 전환 버튼으로 노출합니다.
- 빠른 질문은 채팅 히스토리 공간을 침범하지 않도록 최대 2개만 노출합니다.

## 4. 스트리밍과 스크롤 동작

- 새 질문은 `pending_chat`에 들어가고, 사용자 메시지가 먼저 히스토리에 표시됩니다.
- assistant 답변 영역은 첫 토큰 수신 전 빈 화면으로 두지 않고 skeleton UI를 표시합니다.
- 답변 시작 전에 미리 하단으로 강제 스크롤하지 않습니다.
- 스크롤은 실제 답변 텍스트가 스트리밍될 때 첫 chunk와 이후 일정 chunk마다 갱신합니다.
- 답변 완료 후에는 새 입력/출력 위치를 볼 수 있도록 한 번 더 최신 위치로 이동합니다.
- `chat_history` 외부 영역은 스크롤되지 않아야 합니다.

## 5. 답변 담당 에이전트

현재 채팅 답변 담당은 6개입니다.

1. 마케팅 담당
   - 광고비, 채널, 캠페인, ROAS, 클릭, 전환 중심
   - 마케팅 이벤트와 예산 우선순위를 설명
2. 고객 CS 담당
   - 신규·재구매 고객, 리뷰, 평점, 문의, 환불 중심
   - 고객 영향과 CS 대응을 설명
3. 재고관리 담당
   - 현재 재고, 안전재고, 품절 위험, 발주 우선순위 중심
   - 긴급도와 발주 또는 대체 상품 대응 제시
4. 매출 상품 담당
   - 매출, 주문, 판매량, 급등락 상품 중심
   - 전체 실적과 상품별 기여 구분
5. 제품 기획 담당
   - 상품 구성, 인기상품, 추천 성과, 가격·프로모션·신상품 기회 중심
   - 단기 운영 조치와 검증할 제품 가설 구분
6. 제품총괄
   - 다른 담당자 답변을 종합·평가하는 상위 담당
   - Parallelization에서는 Aggregator
   - Orchestrator에서는 Synthesizer
   - Evaluator-optimizer에서는 LLM Call Evaluator
   - 선택되면 담당별 답변을 참고 자료로 만든 뒤 최종 종합 답변을 생성

개발용 내부 에이전트:

- `AgentCreator`
  - 대시보드 사용자에게 노출되는 답변 담당이 아닙니다.
  - `agent/` 폴더의 역할별 답변 지침을 훈련·개선하는 개발용 지침 관리 에이전트입니다.
  - `chat.txt`와 `inqury.txt`의 질문 패턴을 참고해 담당별 지침을 다듬는 데 사용합니다.
  - 채팅 UI의 담당 선택, 자동 배정, 제품총괄 종합 대상에는 포함하지 않습니다.

## 6. 담당 배정 규칙

- 사용자가 담당을 선택하지 않으면 `자동 배정`을 사용합니다.
- 자동 배정은 `src/role_agents.py`의 keyword scoring으로 결정하며 deterministic하고 빨라야 합니다.
- 담당별 답변 지침은 `agent/*.md`에서 읽어옵니다.
- 사용자가 담당을 하나 이상 직접 선택하면 선택한 담당이 답변합니다.
- `제품총괄`이 포함된 경우:
  - `제품총괄`만 선택하면 나머지 5개 실무 담당 답변을 내부 생성한 뒤 제품총괄 답변만 화면에 표시합니다.
  - `제품총괄 + 일부 담당`을 선택하면 선택한 일부 담당 답변만 내부 생성한 뒤 제품총괄 답변만 화면에 표시합니다.
  - 내부 담당 답변에서 오류가 발생하면 오류는 OpenAI 오류 expander에 남기고 제품총괄 fallback 흐름은 유지합니다.

## 7. OpenAI 컨텍스트 계약

OpenAI에는 전체 CSV 원본을 보내지 않습니다. `build_dashboard_context`가 만든 집계 컨텍스트만 보냅니다.

컨텍스트에는 다음 정보가 포함됩니다.

- 분석 기간
- 답변 담당 정보
- KPI 요약
- 이벤트 요약과 상위 이벤트
- 상관관계 Top N
- 원인 후보 `cause_candidates`
- 우선 액션
- workflow pattern 정보
- 제품총괄 종합 시 `source_agent_answers`

답변 지침:

- 제공된 컨텍스트만 근거로 답변합니다.
- KPI, 이벤트, 상관계수, 원인 후보, 액션을 구체적으로 인용합니다.
- 원인 분석 질문은 가능하면 `확인된 사실`, `가능한 가설`, `추가 확인 필요 데이터`, `추천 액션`으로 나눕니다.
- 상관관계를 인과관계로 단정하지 않습니다.
- 컨텍스트에 없는 수치나 사실은 만들지 않습니다.

## 8. Fallback 계약

- `.env`에 `OPENAI_API_KEY`가 없거나 API 호출이 실패하면 `src/chat.py`의 fallback을 사용합니다.
- fallback도 역할별 관점, 원인 후보, 권고 액션을 반영해야 합니다.
- fallback은 다음 질문 유형을 최소 지원합니다.
  - 매출/판매/주문 요약
  - 품절/재고 위험
  - 마케팅/ROAS
  - 고객 CS/평점/문의/환불
  - 상관관계/원인/왜/급상승/급감
  - 액션/할 일/조치/권고/추천
  - 제품총괄 종합 답변
- fallback 출처 라벨은 UI에 유지합니다.

## 9. Workflow Pattern 표시

`src/workflow_patterns.py`는 실제 구현 흐름을 사용자에게 설명하는 UI 메타데이터입니다.

현재 표시 가능한 패턴:

- Routing
- Augmented LLM
- Parallelization
- Parallelization · Aggregator
- Orchestrator · Synthesizer
- Evaluator-optimizer · LLM Call Evaluator
- 별도 패턴: Workflow intent detected
- 별도 패턴: Orchestration intent detected
- 별도 패턴: Evaluator-optimizer

제품총괄이 포함되면 질문 의도에 따라 Aggregator, Synthesizer, Evaluator 역할을 우선 표시합니다.

## 10. 채팅 로그

- 새 assistant 답변은 `append_assistant_messages`에서 세션 히스토리에 저장됩니다.
- 질문과 답변은 `chat.txt`에 append 저장합니다.
- 기존 `chat.txt` 내용은 덮어쓰지 않습니다.
- 저장 오류가 있으면 `최근 대화 저장 오류` expander에 표시합니다.
- 저장 내용에는 질문, 답변, 담당자, 배정 방식, 배정 근거, workflow, 출처가 포함됩니다.

## 11. 상태 관리

- `st.session_state.chat_messages`
  - 현재 세션의 user/assistant 메시지 히스토리
- `st.session_state.pending_chat`
  - 새 질문을 queue하고, user 메시지를 먼저 렌더링하기 위한 임시 상태
- `st.session_state.chat_requested_agents`
  - 사용자가 선택한 답변 담당
- `st.session_state.chat_scroll_to_bottom`
  - 새 입력/출력 후 스크롤 갱신 플래그
- `st.session_state.openai_last_error`
  - 최근 OpenAI 오류
- `st.session_state.chat_log_error`
  - 최근 chat log 저장 오류

## 12. 품질 기준

- 답변은 짧고 실행 가능해야 합니다.
- 숫자와 근거는 현재 대시보드 기간과 컨텍스트에 맞아야 합니다.
- 원인 후보는 항상 가설로 표현합니다.
- 담당 선택과 자동 배정은 빠르고 deterministic해야 합니다.
- 제품총괄은 담당 답변의 중복을 줄이고 최종 의사결정 관점으로 정리해야 합니다.
- 채팅 UI는 답변 대기 중 빈 영역을 노출하지 않아야 합니다.
- 스크롤은 답변 텍스트 스트리밍에 맞춰 자연스럽게 따라가야 합니다.
- 현재 답변 담당 모드는 사용자가 popover를 열지 않아도 확인 가능해야 합니다.

## 13. 변경 시 체크리스트

채팅 기능을 수정하면 최소 다음을 확인합니다.

```bash
uv run python -m py_compile main.py dashboard.py src/*.py
```

수동 확인:

- 자동 배정 질문
- 단일 담당 직접 지정
- 복수 담당 직접 지정
- 제품총괄 단독 지정
- 제품총괄 + 일부 담당 지정
- OpenAI 성공 경로
- OpenAI 실패 또는 API 키 없음 fallback 경로
- 원인 분석 질문
- 액션/권고 질문
- 스켈레톤 표시와 스트리밍 스크롤
- `chat.txt` append 저장
