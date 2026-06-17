# Session Handoff - 2026-06-16

Read `AGENTS.md`, `README.md`, and `docs/AGENTS.md` before continuing.

## What Was Completed

- Added five role-specific answer agents in `src/role_agents.py`:
  마케팅 담당, 고객 CS 담당, 재고관리 담당, 매출 상품 담당, 제품 기획 담당.
- Added deterministic question routing with automatic assignment and manual
  assignment from the chat UI.
- Applied the assigned role to both OpenAI Responses API answers and
  deterministic fallback answers.
- Prioritized role-relevant events and actions in the aggregated OpenAI
  context.
- Displayed the assigned agent name beside the assistant avatar, with the
  answer below it.
- Removed per-answer `OpenAI · gpt-5.4-mini` captions. Fallback labels remain.
- Kept the desktop sidebar at 250px and always visible. Mobile retains the
  native Streamlit collapse/expand behavior.
- Rebuilt the right chat as a fixed desktop operations console:
  - panel: fixed 16px from browser top, right, and bottom
  - history: flexible height and independently scrollable
  - answer-agent selector: fixed above the input
  - input form: fixed at the panel bottom
  - widths at or below 1100px return to normal document flow

## Important Code Locations

- `dashboard.py`
  - Square/sidebar/chat CSS: near `inject_square_theme`
  - chat answer orchestration: `get_chat_answer`
  - stored chat metadata: `append_chat_exchange`
  - fixed chat layout: `render_chat_panel`
- `src/role_agents.py`
  - role metadata, keywords, deterministic routing, and `dashboard_page`
- `agent/`
  - role-specific answer instructions
  - `assign_role_agent`
- `src/openai_service.py`
  - role-aware aggregated context and OpenAI instructions
- `src/chat.py`
  - role-aware deterministic fallback

## Verified Behavior

- `uv run python -m py_compile main.py dashboard.py src/*.py` passes.
- Automatic routing was verified for all five role agents.
- Manual assignment overrides question keywords.
- OpenAI and no-key fallback paths were both verified.
- At a 1440x720 viewport:
  - panel height: 688px
  - history height: about 215px
  - input bottom: 32px from the viewport bottom
- At a 1440x900 viewport:
  - panel height: 868px
  - history height: about 395px
  - input bottom: 32px from the viewport bottom
- At a 390x844 viewport, the panel returns to document flow and the history
  uses a responsive height with vertical scrolling.

## Runtime Note

Streamlit hot reload did not consistently reflect `dashboard.py` changes in
the long-running server. If the UI looks like an older version, restart it:

```bash
pid=$(lsof -tiTCP:8501 -sTCP:LISTEN | head -1)
if [ -n "$pid" ]; then kill "$pid"; fi
uv run streamlit run main.py --server.address 127.0.0.1 --server.port 8501
```

Do not assume the code was reverted until the running process has been checked.

## Next Planned Feature

The next requested direction is answer-driven dashboard navigation:

1. Use the assigned agent's stored `page_hint` to choose the most relevant
   dashboard page.
2. Add structured evidence targets to an answer, such as event IDs, metric
   names, product IDs, or action IDs.
3. After an answer, navigate to the relevant page and highlight the supporting
   chart, event, table row, or action.
4. Keep the chat context and selected period unchanged during navigation.
5. Provide a clear visual link between each answer claim and its dashboard
   evidence without presenting correlation as causation.

`RoleAgent.dashboard_page` and the `page_hint` field stored by
`append_chat_exchange` already prepare part of this workflow.

## Repository State

The repository files are currently mostly untracked in Git. Do not reset,
restore, or remove existing work. Do not modify the seven CSV fixtures unless
the task is specifically about data.
