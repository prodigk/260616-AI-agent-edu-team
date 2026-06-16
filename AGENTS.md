# AI Commerce Operations Dashboard

This file is the primary handoff context for Codex sessions working in this
repository. Read it together with `README.md` before making changes.

## Product Goal

Build a Streamlit MVP that helps commerce operators understand sales,
marketing, customer/CS, inventory, and recommendation data in one place. The
right-side chat must answer questions using the currently selected dashboard
period and analysis outputs.

The primary users are team members implementing the assignment and evaluators
reviewing the result. User-facing copy is Korean.

## Source Documents

- `docs/Agent Task Definitions.md`: canonical definitions for the eight agents.
- `docs/AI Commerce Operations Dashboard: Build Guide.md`: product and data
  requirements.
- `square-dashboard-html/`: visual reference UI kit. Reuse its design language;
  do not introduce a separate frontend runtime unless explicitly requested.
- `AI_커머스_운영_대시보드_기획서.docx`: detailed planning artifact.
- `AI_커머스_운영_대시보드_발표자료.pptx`: six-slide presentation artifact.

## Current Architecture

- `main.py`: Streamlit entry point.
- `dashboard.py`: page layout, filters, charts, actions, reports, and chat UI.
- `src/models.py`: shared data result models.
- `src/agents.py`: eight agent modules and KPI calculation.
- `src/openai_service.py`: OpenAI Responses API integration and dashboard
  context serialization.
- `src/chat.py`: deterministic fallback answers when OpenAI is unavailable.
- `src/role_agents.py`: five answer-specialist definitions and deterministic
  question routing.
- `db/`: seven required CSV datasets.
- `.streamlit/config.toml`: app theme.

The eight agents are implemented as Python modules, not separate services:

1. Data Loader Agent
2. Event Detector Agent
3. Correlation Analyzer Agent
4. Insight Generator Agent
5. Weekly Report Agent
6. Action Planner Agent
7. Task Assignment Agent
8. Executive Report Agent

Shared outputs should continue to use the concepts `events`, `correlations`,
`insights`, `actions`, and `reports`.

The analysis pipeline is separate from the chat answer layer. Chat questions
are automatically routed to one of five role agents, or the user can assign
one directly:

1. 마케팅 담당
2. 고객 CS 담당
3. 재고관리 담당
4. 매출 상품 담당
5. 제품 기획 담당

Routing must remain deterministic and fast. The selected role agent controls
answer perspective and context priority for both OpenAI and fallback answers.

## Data Domains

Keep data and UI grouped into these four domains:

- 매출·상품: `sales_data.csv`, `product_data.csv`
- 마케팅: `marketing_data.csv`
- 고객·CS: `customer_data.csv`, `review_cs_data.csv`
- 재고·추천: `inventory_data.csv`, `recommendation_log.csv`

Preserve source column names and use structured pandas operations for joins and
aggregation. Product joins use `product_id`; time-series analysis uses `date`.
Do not present correlation as causation.

## OpenAI Chat Contract

- Secrets live only in `.env`; never commit or print the API key.
- Supported variables are documented in `.env.example`.
- Default model: `gpt-5.4-mini`, overridable with `OPENAI_MODEL`.
- Use the Responses API through the official `openai` Python package.
- Send only the aggregated context built by
  `src.openai_service.build_dashboard_context`; do not send entire raw CSVs.
- Answers must be grounded in supplied KPI, event, correlation, and action data.
- Include the selected answer agent, assignment mode, and assignment reason in
  the chat UI.
- Keep the deterministic fallback in `src/chat.py` working.
- The UI must indicate whether an answer came from OpenAI or the fallback.

## UI Direction

- Streamlit components are the default implementation surface.
- Preserve the Square-inspired navigation, cards, spacing, and navy/teal base.
- Use saturated key colors for high-priority values and alerts.
- Keep the chat panel on the right side of analysis pages.
- On desktop, keep the 250px sidebar visible. On mobile, preserve the
  Streamlit off-canvas collapse/expand behavior.
- On desktop, the chat panel is fixed to the browser viewport with 16px top
  and bottom margins. Only `chat_history` scrolls; the answer-agent selector
  and input form remain at the bottom.
- At widths of 1100px or less, return the chat panel to normal document flow
  and use a responsive scroll area based on viewport height.
- Prefer readable Korean labels and short operational copy.
- New pages must work at the normal desktop viewport without horizontal
  overflow.

## Chat UI Contract

- `render_chat_panel` uses keyed Streamlit containers:
  `chat_panel_shell`, `chat_history`, and `chat_agent_selector`.
- Assistant messages show the assigned role-agent name next to the avatar,
  followed by the answer on the next line.
- Show assignment mode and reason, but do not show the OpenAI model name below
  each answer. The panel header may still show connection status.
- Chat answers must show the selected LLM workflow pattern below the answer.
  `src/workflow_patterns.py` maps questions to Anthropic-style patterns:
  Augmented LLM, Prompt chaining intent, Routing, Parallelization,
  Orchestrator intent, or a separate pattern such as Evaluator-optimizer.
- New chat questions are queued into `pending_chat` so the user message appears
  first, then the assistant answer streams inside `chat_history`.
- Keep chat history auto-scrolled to the newest input/output with
  `scroll_chat_to_bottom`.
- Keep fallback source labels visible when OpenAI fails.
- `append_assistant_messages` stores `page_hint` for the planned answer-driven
  dashboard navigation feature.

## Development Workflow

Use `uv` as the package and command runner:

```bash
uv sync
uv run streamlit run main.py
```

The default local URL is `http://127.0.0.1:8501`.

Before considering a code change complete, run:

```bash
uv run python -m py_compile main.py dashboard.py src/*.py
```

For UI changes, also open the running app and verify the affected page,
filters, chart rendering, and chat panel. For OpenAI changes, verify both a
successful API response and fallback behavior without exposing secrets.

## Change Guidelines

- Work with the current Streamlit/Python architecture and existing agent
  boundaries.
- Keep changes scoped; avoid unrelated refactors or generated-file churn.
- Do not modify the seven CSV fixtures unless the task is specifically about
  data.
- Update `README.md`, this file, or `.env.example` when setup or architecture
  changes.
- Keep `.env`, `.venv`, caches, and macOS metadata out of Git.
- The repository may contain uncommitted user work. Never revert it unless
  explicitly asked.

## Current State

The MVP currently provides six sidebar pages: Home, Events, Analytics, Tasks,
Agents, Reports. The seven CSVs load successfully, all eight
analysis stages run in-process, and the right-side chat can automatically
route questions to five role agents or accept a direct assignment. API
failures automatically fall back to role-aware rule-based answers.

The desktop sidebar is always visible, while mobile retains collapse controls.
The sidebar uses a platform-style icon + label navigation pattern, and the
main page header title follows the selected page name.
The desktop chat panel is viewport-fixed; its message history alone scrolls,
and the agent selector and input remain fixed at the bottom. See
`SESSION_HANDOFF.md` for the latest session details and next planned work.
