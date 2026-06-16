# AI 커머스 운영 대시보드

`docs/Agent Task Definitions.md`에 정의된 8개 에이전트를 Python 모듈로 구현하고,
7개 CSV 데이터를 Streamlit 대시보드에서 분석하는 팀 프로젝트입니다.

## 실행

```bash
uv sync
uv run streamlit run main.py
```

기본 주소는 `http://localhost:8501`입니다.

VS Code에서는 `Terminal > Run Task`에서 의존성 설치, Streamlit 실행, 문법
검사를 바로 실행할 수 있습니다. Codex 작업 규칙과 현재 구현 맥락은
루트의 `AGENTS.md`를 기준으로 유지합니다.

## OpenAI 연결

프로젝트 루트의 `.env`에 API 키를 넣으면 우측 챗이 OpenAI Responses API를
사용합니다.

```env
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.4-mini
```

처음 설정할 때는 `.env.example`을 참고하세요. 실제 `.env`는 Git에서
제외됩니다.

`OPENAI_MODEL`은 선택 사항입니다. API 연결이 실패하거나 키가 없으면 기존
규칙 기반 분석 답변으로 자동 전환됩니다.

## 주요 기능

- 매출·상품 / 마케팅 / 고객·CS / 재고·추천 데이터 그룹
- KPI와 기간 비교
- 판매 급등락, 품절 위험, 광고 효율, 인기상품, 추천 성과 이벤트 탐지
- Pearson/Spearman 상관관계 히트맵과 상세 분석
- 역할별 액션 보드와 상태 관리
- 주간 및 대표 보고서 Markdown 다운로드
- 현재 필터와 분석 결과를 이해하는 우측 운영 분석 챗 UI
- 질문 맥락에 따른 직무 에이전트 자동 배정 및 CEO 직접 지정

## 직무 답변 에이전트

기존 8개 에이전트가 데이터 로딩부터 리포트 생성까지 분석 파이프라인을
담당하고, 우측 채팅에서는 다음 5개 직무 에이전트가 분석 결과를 역할별로
설명합니다.

- 마케팅 담당
- 고객 CS 담당
- 재고관리 담당
- 매출 상품 담당
- 제품 기획 담당

`자동 배정`을 선택하면 질문 키워드와 업무 맥락에 맞는 담당이 즉시
선택됩니다. CEO 등 사용자가 특정 관점의 답변을 원하면 담당을 직접 지정할
수 있으며, 답변에는 담당 에이전트와 배정 근거가 함께 표시됩니다.

## 에이전트

1. Data Loader Agent
2. Event Detector Agent
3. Correlation Analyzer Agent
4. Insight Generator Agent
5. Weekly Report Agent
6. Action Planner Agent
7. Task Assignment Agent
8. Executive Report Agent

UI는 `square-dashboard-html`의 Circle Overview 화면, 색상 토큰, 카드 및
내비게이션 패턴을 Streamlit 컴포넌트에 맞춰 재구성했습니다.
