from __future__ import annotations

import time
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.agents import (
    ActionPlannerAgent,
    CorrelationAnalyzerAgent,
    DataLoaderAgent,
    EventDetectorAgent,
    ExecutiveReportAgent,
    InsightGeneratorAgent,
    TaskAssignmentAgent,
    WeeklyReportAgent,
    calculate_kpis,
)
from src.chat import answer_dashboard_question
from src.openai_service import (
    build_dashboard_context,
    configured_model,
    is_openai_configured,
    stream_openai_text,
)
from src.role_agents import (
    AUTO_AGENT,
    ROLE_AGENT_BY_LABEL,
    assign_role_agent,
)
from src.workflow_patterns import select_workflow_pattern


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "db"

COLORS = {
    "blue": "#0062FF",
    "blue_light": "#50B5FF",
    "green": "#3DD598",
    "yellow": "#FFC542",
    "orange": "#FF974A",
    "red": "#FC5A5A",
    "purple": "#A461D8",
    "ink": "#171725",
    "gray": "#92929D",
    "gray_light": "#B5B5BE",
    "border": "#E2E2EA",
    "surface": "#FAFAFB",
    "white": "#FFFFFF",
}

AGENT_COLORS = {
    AUTO_AGENT: COLORS["gray"],
    "마케팅 담당": COLORS["green"],
    "고객 CS 담당": COLORS["yellow"],
    "재고관리 담당": COLORS["red"],
    "매출 상품 담당": COLORS["blue"],
    "제품 기획 담당": COLORS["purple"],
}

PAGES = (
    {
        "key": "home",
        "label": "Home",
        "subtitle": "커머스 운영 전체 현황",
        "icon": ":material/home:",
    },
    {
        "key": "events",
        "label": "Events",
        "subtitle": "매출·재고·마케팅 이벤트 탐지",
        "icon": ":material/chat_bubble:",
    },
    {
        "key": "analytics",
        "label": "Analytics",
        "subtitle": "지표 간 상관 분석",
        "icon": ":material/analytics:",
    },
    {
        "key": "tasks",
        "label": "Tasks",
        "subtitle": "우선순위 액션 보드",
        "icon": ":material/checklist:",
    },
    {
        "key": "agents",
        "label": "Agents",
        "subtitle": "분석 에이전트 실행 상태",
        "icon": ":material/hub:",
    },
    {
        "key": "reports",
        "label": "Reports",
        "subtitle": "주간·대표 보고서",
        "icon": ":material/article:",
    },
)
PAGE_BY_KEY = {page["key"]: page for page in PAGES}

METRIC_LABELS = {
    "quantity_sold": "판매량",
    "revenue": "매출",
    "current_stock": "현재 재고",
    "ad_spend": "광고비",
    "clicks": "광고 클릭",
    "conversions": "광고 전환",
    "rating": "평점",
    "recommended_count": "추천 노출",
    "click_count": "추천 클릭",
    "conversion_count": "추천 전환",
}


def inject_square_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:wght@400;500&family=Poppins:wght@400;500;600;700&family=Noto+Sans+KR:wght@400;500;600;700&display=swap');

        :root {
            --sq-blue: #0062FF;
            --sq-blue-light: #50B5FF;
            --sq-green: #3DD598;
            --sq-yellow: #FFC542;
            --sq-orange: #FF974A;
            --sq-red: #FC5A5A;
            --sq-purple: #A461D8;
            --sq-ink: #171725;
            --sq-gray: #92929D;
            --sq-border: #E2E2EA;
            --sq-surface: #FAFAFB;
        }
        html, body, [class*="css"] {
            font-family: "Noto Sans KR", "Poppins", sans-serif;
            color: var(--sq-ink);
        }
        .stApp { background: var(--sq-surface); }
        .block-container {
            max-width: 1900px;
            padding: 1.7rem 2rem 3rem;
        }
        [data-testid="stSidebar"] {
            background: #F7F7F8;
            border-right: 1px solid var(--sq-border);
            box-shadow:none;
        }
        [data-testid="stSidebar"] > div:first-child { padding:1.45rem .9rem 1rem; }
        .sq-brand {
            display:flex;align-items:center;justify-content:space-between;
            padding:2px 8px 20px;color:#2F2F31;
            font-family:Poppins,sans-serif;font-size:22px;font-weight:600;
            letter-spacing:-.03em;
        }
        .sq-brand-switch {
            color:#8E8E93;font-size:17px;font-weight:600;letter-spacing:-.08em;
        }
        [data-testid="stSidebar"] {
            text-align:left;
        }
        [data-testid="stSidebar"] .stButton {
            margin-bottom:2px;
        }
        [data-testid="stSidebar"] .stButton > button {
            justify-content:flex-start !important;gap:11px !important;
            text-align:left !important;
            width:100% !important;min-height:42px !important;padding:8px 11px !important;
            border:0 !important;border-radius:14px !important;background:transparent !important;
            color:#303033 !important;font-size:16px !important;font-weight:500 !important;
            box-shadow:none !important;
        }
        [data-testid="stSidebar"] .stButton > button p,
        [data-testid="stSidebar"] .stButton > button div {
            text-align:left !important;
            justify-content:flex-start !important;
        }
        [data-testid="stSidebar"] .stButton > button:hover {
            background:#EFEFF1 !important;color:#171719 !important;
        }
        [data-testid="stSidebar"] .stButton > button [data-testid="stIconMaterial"] {
            font-size:23px !important;color:#303033 !important;
        }
        .sq-eyebrow {
            color:var(--sq-gray); font-size:11px; font-weight:700;
            letter-spacing:.12em; text-transform:uppercase; margin-bottom:5px;
        }
        h1.sq-page-title {
            font-family:Poppins,"Noto Sans KR",sans-serif;
            font-size:27px !important; font-weight:700 !important; line-height:1.35;
            color:var(--sq-ink) !important;
            margin:0;
        }
        .sq-subtitle { color:#696974;font-size:13px;margin:5px 0 0; }
        .sq-section-title {
            font-family:Poppins,"Noto Sans KR",sans-serif;
            font-size:17px; font-weight:700; margin:4px 0 13px;color:var(--sq-ink);
        }
        .sq-card {
            background:#fff;border:1px solid rgba(226,226,234,.75);
            border-radius:20px;padding:20px 22px;min-height:128px;
            box-shadow:0 8px 28px rgba(68,68,79,.035);
        }
        .sq-card-label {font-size:13px;font-weight:700;color:#44444F;margin-bottom:13px;}
        .sq-card-value {
            font-family:Poppins,sans-serif;font-size:25px;font-weight:700;
            color:var(--sq-ink);letter-spacing:-.02em;white-space:nowrap;
        }
        .sq-card-meta {font-size:12px;color:var(--sq-gray);margin-top:7px;}
        .sq-delta-up {color:var(--sq-green);font-weight:700;}
        .sq-delta-down {color:var(--sq-red);font-weight:700;}
        .sq-risk-value {color:var(--sq-red);}
        .sq-blue-value {color:var(--sq-blue);}
        .sq-chat-header {
            display:flex;align-items:center;justify-content:space-between;
            padding-bottom:14px;border-bottom:1px solid #F1F1F5;margin-bottom:12px;
        }
        .sq-chat-title {font-size:17px;font-weight:700;}
        .sq-status {
            display:inline-flex;align-items:center;gap:6px;padding:5px 9px;
            border-radius:99px;background:rgba(61,213,152,.11);
            color:#15966a;font-size:11px;font-weight:700;
        }
        .sq-status:before {content:"";width:7px;height:7px;border-radius:50%;background:#3DD598;}
        .sq-context {
            border-radius:10px;background:rgba(0,98,255,.055);color:#0062FF;
            padding:8px 10px;font-size:11px;font-weight:600;margin-bottom:10px;
        }
        .st-key-chat_panel_shell {
            position:fixed;top:1rem;right:2rem;bottom:1rem;
            width:min(420px, calc((100vw - 250px) * .29));
            height:auto !important;min-height:0;max-height:none;
            z-index:20;
        }
        .st-key-chat_panel_shell [data-testid="stVerticalBlock"] {
            min-height:0;
        }
        .st-key-chat_panel_shell > [data-testid="stLayoutWrapper"]:has(
            > .st-key-chat_history
        ) {
            flex:1 1 0 !important;height:0 !important;min-height:180px;
            overflow:hidden;
        }
        .st-key-chat_history {
            flex:1 1 auto;height:100% !important;min-height:0;
            overflow-x:hidden !important;overflow-y:auto !important;
            overscroll-behavior:contain;scrollbar-width:thin;
            scrollbar-color:#D6D6DE transparent;
            padding:4px 8px 10px;border-radius:14px;
            background:#FAFAFB;border:1px solid #F1F1F5;
        }
        .st-key-chat_history::-webkit-scrollbar {
            width:6px;
        }
        .st-key-chat_history::-webkit-scrollbar-thumb {
            background:#D6D6DE;border-radius:99px;
        }
        .st-key-chat_history::-webkit-scrollbar-track {
            background:transparent;
        }
        .sq-chat-controls {
            padding-top:10px;margin-top:2px;border-top:1px solid #F1F1F5;
        }
        .st-key-chat_agent_selector {
            flex:0 0 auto;
        }
        .st-key-chat_input_form {
            flex:0 0 auto;
        }
        .sq-agent {
            display:flex;align-items:center;gap:9px;padding:9px 0;
            border-bottom:1px solid #F1F1F5;font-size:12px;
        }
        .sq-agent:last-child {border:0;}
        .sq-agent-dot {width:9px;height:9px;border-radius:50%;background:#3DD598;box-shadow:0 0 0 4px rgba(61,213,152,.12);}
        .sq-agent-name {font-weight:700;flex:1;}
        .sq-agent-state {color:#15966a;font-size:11px;}
        [data-testid="stMetric"] {
            background:#fff;border:1px solid rgba(226,226,234,.75);
            padding:17px 19px;border-radius:18px;
            box-shadow:0 8px 28px rgba(68,68,79,.035);
        }
        [data-testid="stMetricLabel"] {font-weight:700;color:#44444F;}
        [data-testid="stMetricValue"] {font-family:Poppins,sans-serif;font-weight:700;}
        [data-testid="stMetricDelta"] svg {display:none;}
        [data-testid="stPlotlyChart"] {
            background:#fff;border:1px solid rgba(226,226,234,.75);
            border-radius:20px;padding:10px 12px;
            box-shadow:0 8px 28px rgba(68,68,79,.035);
        }
        [data-testid="stDataFrame"] {
            border:1px solid rgba(226,226,234,.9);border-radius:16px;overflow:hidden;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap:7px;background:#fff;border-radius:14px;padding:5px;
            border:1px solid var(--sq-border);
        }
        .stTabs [data-baseweb="tab"] {
            border-radius:10px;padding:8px 15px;font-weight:700;
        }
        .stTabs [aria-selected="true"] {background:rgba(0,98,255,.08);color:var(--sq-blue);}
        .stButton > button, .stDownloadButton > button,
        [data-testid="stBaseButton-secondary"] {
            border-radius:10px;border:1px solid var(--sq-border);
            font-weight:700;min-height:40px;background:#fff !important;
            color:var(--sq-ink) !important;
        }
        .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
            background:var(--sq-blue) !important;border-color:var(--sq-blue) !important;color:white !important;
        }
        div[data-testid="stForm"] {
            border:0;padding:0;background:transparent;
        }
        div[data-testid="stChatMessage"] {
            border-radius:14px;padding:8px 10px;margin:6px 0;
            background:#FAFAFB;border:1px solid #F1F1F5;
        }
        .sq-chat-agent-header {
            display:flex;align-items:center;gap:7px;min-height:26px;
            margin:0 0 7px;color:var(--sq-ink);
        }
        .sq-chat-agent-name {
            font-size:13px;font-weight:700;line-height:1.3;
        }
        .sq-chat-agent-mode {
            display:inline-flex;align-items:center;padding:3px 7px;
            border-radius:99px;background:rgba(0,98,255,.07);
            color:var(--sq-blue);font-size:10px;font-weight:700;
        }
        .sq-workflow-meta {
            margin-top:9px;padding:8px 10px;border-radius:11px;
            background:#F7F7F8;border:1px solid #EAEAEE;
            color:#696974;font-size:11px;line-height:1.45;
        }
        .sq-workflow-meta strong {
            color:#44444F;font-weight:700;
        }
        .sq-target-label {
            font-size:11px;font-weight:700;color:#696974;margin:0 0 6px;
        }
        .sq-target-chip-row {
            display:flex;flex-wrap:wrap;gap:5px;margin:4px 0 8px;
        }
        .sq-target-chip {
            --agent-color:var(--sq-blue);
            display:inline-flex;align-items:center;gap:5px;padding:3px 7px;
            border-radius:99px;background:#fff;color:#44444F;
            font-size:10px;font-weight:700;line-height:1.2;
            border:1px solid rgba(226,226,234,.95);
        }
        .sq-target-chip:before {
            content:"";width:6px;height:6px;border-radius:50%;
            background:var(--agent-color);
        }
        .sq-agent-picker-note {
            margin-top:4px;padding:8px 10px;border-radius:11px;
            background:#FAFAFB;border:1px solid #F1F1F5;color:#696974;
            font-size:11px;line-height:1.45;
        }
        .sq-agent-picker-summary {
            margin-bottom:4px;color:#696974;font-size:11px;font-weight:600;
        }
        .st-key-chat_agent_selector [data-testid="stPills"] {
            margin-bottom:0;gap:5px;
        }
        .st-key-chat_agent_selector [data-testid="stPills"] button {
            border-radius:99px !important;font-size:10px !important;
            line-height:1.2 !important;font-weight:700 !important;
            min-height:28px !important;padding:4px 8px !important;
            color:#44444F !important;
            border-color:rgba(226,226,234,.95) !important;
            background:#fff !important;
        }
        .st-key-chat_agent_selector [data-testid="stPills"] button:before {
            content:"";display:inline-block;width:6px;height:6px;
            border-radius:50%;margin-right:5px;background:var(--sq-gray);
        }
        .st-key-chat_agent_selector [data-testid="stPills"] button:nth-of-type(1):before {
            background:var(--sq-green);
        }
        .st-key-chat_agent_selector [data-testid="stPills"] button:nth-of-type(2):before {
            background:var(--sq-yellow);
        }
        .st-key-chat_agent_selector [data-testid="stPills"] button:nth-of-type(3):before {
            background:var(--sq-red);
        }
        .st-key-chat_agent_selector [data-testid="stPills"] button:nth-of-type(4):before {
            background:var(--sq-blue);
        }
        .st-key-chat_agent_selector [data-testid="stPills"] button:nth-of-type(5):before {
            background:var(--sq-purple);
        }
        .st-key-chat_agent_selector [data-testid="stPopover"] button {
            min-height:32px !important;padding:5px 10px !important;
            border-radius:12px !important;font-size:11px !important;
            font-weight:700 !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background:#fff;border-color:rgba(226,226,234,.85) !important;
            border-radius:20px !important;
            box-shadow:0 8px 28px rgba(68,68,79,.045);
        }
        .sq-note {
            padding:11px 13px;border-radius:12px;background:#FFF8E6;
            color:#8A6411;font-size:12px;border:1px solid rgba(255,197,66,.42);
        }
        hr {border-color:#F1F1F5;}
        #MainMenu, footer, header[data-testid="stHeader"] {visibility:hidden;}
        @media (min-width: 769px) {
            [data-testid="stSidebar"] {
                display:block !important;
                min-width:250px !important;
                width:250px !important;
                transform:none !important;
            }
            [data-testid="stSidebarCollapseButton"],
            [data-testid="stExpandSidebarButton"] {
                display:none !important;
            }
        }
        @media (max-width: 1100px) {
            .block-container {padding:1rem;}
            .sq-card {min-height:112px;}
            .st-key-chat_panel_shell {
                position:static;width:auto;height:auto !important;
                min-height:0;max-height:none;
            }
            .st-key-chat_panel_shell > [data-testid="stLayoutWrapper"]:has(
                > .st-key-chat_history
            ) {
                flex:0 0 auto !important;height:auto !important;
                min-height:0;overflow:visible;
            }
            .st-key-chat_history {
                height:clamp(360px, 60vh, 560px) !important;min-height:320px;
            }
        }
        @media (max-width: 768px) {
            [data-testid="stSidebar"] {
                width:280px !important;max-width:86vw !important;
                box-shadow:18px 0 45px rgba(23,23,37,.14);
            }
            [data-testid="stSidebarCollapseButton"] button,
            [data-testid="stExpandSidebarButton"] button,
            button[data-testid="stExpandSidebarButton"] {
                width:40px !important;height:40px !important;min-height:40px !important;
                border:1px solid rgba(0,98,255,.18) !important;
                border-radius:12px !important;background:#fff !important;
                color:var(--sq-blue) !important;
                box-shadow:0 10px 28px rgba(0,98,255,.14) !important;
            }
            header[data-testid="stHeader"] {
                visibility:visible;background:transparent !important;
                pointer-events:none;
            }
            header[data-testid="stHeader"] [data-testid="stToolbar"],
            [data-testid="stExpandSidebarButton"] {
                pointer-events:auto !important;
            }
            [data-testid="stExpandSidebarButton"] {
                position:fixed !important;top:12px !important;left:12px !important;
                z-index:1000;
            }
            .block-container {
                padding:3.8rem 1rem 1rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_data():
    return DataLoaderAgent().run(DATA_DIR)


@st.cache_data(show_spinner=False)
def run_analysis(start_date, end_date, method, role):
    bundle, quality = load_data()
    start, end = pd.Timestamp(start_date), pd.Timestamp(end_date)
    events = EventDetectorAgent().run(bundle, start, end)
    correlations = CorrelationAnalyzerAgent().run(bundle, start, end, method)
    insights = InsightGeneratorAgent().run(events, correlations, role)
    actions = ActionPlannerAgent().run(events, end)
    return quality, events, correlations, insights, actions


def format_krw(value: float) -> str:
    if abs(value) >= 100_000_000:
        return f"₩{value / 100_000_000:.1f}억"
    if abs(value) >= 10_000_000:
        return f"₩{value / 10_000_000:.1f}천만"
    if abs(value) >= 10_000:
        return f"₩{value / 10_000:.0f}만"
    return f"₩{value:,.0f}"


def compare_period_kpis(bundle, start, end):
    days = (end - start).days + 1
    previous_end = start - pd.Timedelta(days=1)
    previous_start = previous_end - pd.Timedelta(days=days - 1)
    current = calculate_kpis(bundle, start, end)
    previous = calculate_kpis(bundle, previous_start, previous_end)

    def delta(key):
        prev = previous[key]
        return (current[key] / prev - 1) if prev else 0

    return current, {key: delta(key) for key in current}


def card(label, value, meta, accent_class=""):
    st.markdown(
        f"""
        <div class="sq-card">
            <div class="sq-card-label">{label}</div>
            <div class="sq-card-value {accent_class}">{value}</div>
            <div class="sq-card-meta">{meta}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def base_layout(fig, height=330):
    fig.update_layout(
        height=height,
        margin=dict(l=12, r=12, t=50, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Noto Sans KR, sans-serif", color=COLORS["gray"], size=12),
        title_font=dict(color=COLORS["ink"], size=16),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        hoverlabel=dict(bgcolor=COLORS["ink"], font_color="white"),
    )
    fig.update_xaxes(gridcolor="#F1F1F5", zeroline=False)
    fig.update_yaxes(gridcolor="#F1F1F5", zeroline=False)
    return fig


def render_sidebar_nav(current_page):
    active_css = "\n".join(
        (
            f'.st-key-nav_{page["key"]} button {{'
            'background:#ECECEF !important;color:#171719 !important;'
            'font-weight:600 !important;'
            '}'
        )
        for page in PAGES
        if page["key"] == current_page
    )
    st.markdown(f"<style>{active_css}</style>", unsafe_allow_html=True)
    for page in PAGES:
        if st.button(
            page["label"],
            icon=page["icon"],
            key=f'nav_{page["key"]}',
            width="stretch",
        ):
            st.session_state["current_page"] = page["key"]
            st.rerun()


def render_header(start, end, role, page_meta):
    st.markdown('<div class="sq-eyebrow">AI COMMERCE OPERATIONS</div>', unsafe_allow_html=True)
    st.markdown(
        f'<h1 class="sq-page-title">{escape(page_meta["label"])}</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        (
            f'<p class="sq-subtitle">{escape(page_meta["subtitle"])} · '
            f'{start:%Y.%m.%d}–{end:%Y.%m.%d} · {role} 관점 · '
            '8개 분석 에이전트 가동</p>'
        ),
        unsafe_allow_html=True,
    )
    st.write("")


def render_kpis(bundle, kpis, deltas, events):
    inventory_risk = int(events["event_type"].isin(["품절", "품절 위험"]).sum())
    cols = st.columns(4)
    values = [
        ("매출", format_krw(kpis["revenue"]), deltas["revenue"], "blue"),
        ("주문", f"{kpis['orders']:,.0f}건", deltas["orders"], "green"),
        ("평균 ROAS", f"{kpis['roas']:.1f}%", deltas["roas"], "yellow"),
        ("품절 위험", f"{inventory_risk}건", None, "red"),
    ]
    color_map = {
        "blue": "sq-blue-value",
        "green": "",
        "yellow": "",
        "red": "sq-risk-value",
    }
    for col, (label, value, change, color) in zip(cols, values):
        with col:
            if change is None:
                meta = "즉시 확인이 필요한 재고 이벤트"
            else:
                direction = "증가" if change >= 0 else "감소"
                cls = "sq-delta-up" if change >= 0 else "sq-delta-down"
                meta = f'<span class="{cls}">{change:+.1%}</span> 이전 동일 기간 대비 {direction}'
            card(label, value, meta, color_map[color])


def sales_product_tab(bundle, start, end, events):
    sales = bundle.sales[bundle.sales["date"].between(start, end)].copy()
    daily = sales.groupby("date", as_index=False)[["revenue", "orders"]].sum()
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=daily["date"],
            y=daily["revenue"],
            name="매출",
            line=dict(color=COLORS["blue"], width=3, shape="spline"),
            fill="tozeroy",
            fillcolor="rgba(0,98,255,.08)",
        )
    )
    fig.update_layout(title="매출 추이")
    st.plotly_chart(base_layout(fig, 350), width="stretch", key="sales_trend")

    left, right = st.columns([1.35, 1])
    with left:
        product_perf = sales.groupby(
            ["product_id", "product_name", "category"], as_index=False
        ).agg(판매량=("quantity_sold", "sum"), 매출=("revenue", "sum"), 주문=("orders", "sum"))
        product_perf = product_perf.sort_values("매출", ascending=False)
        st.markdown('<div class="sq-section-title">상품 성과</div>', unsafe_allow_html=True)
        st.dataframe(
            product_perf,
            width="stretch",
            hide_index=True,
            column_config={
                "매출": st.column_config.NumberColumn(format="₩%d"),
                "판매량": st.column_config.NumberColumn(format="%d개"),
            },
        )
    with right:
        st.markdown('<div class="sq-section-title">판매 이벤트</div>', unsafe_allow_html=True)
        sales_events = events[events["domain"] == "매출·상품"][
            ["date", "event_type", "product_name", "severity", "description"]
        ].head(12)
        st.dataframe(
            sales_events,
            width="stretch",
            hide_index=True,
            column_config={
                "date": st.column_config.DateColumn("날짜", format="MM-DD"),
                "event_type": "이벤트",
                "product_name": "상품",
                "severity": "등급",
                "description": "근거",
            },
        )


def marketing_tab(bundle, start, end, events):
    marketing = bundle.marketing[bundle.marketing["date"].between(start, end)].copy()
    channel = marketing.groupby("channel", as_index=False).agg(
        광고비=("ad_spend", "sum"),
        클릭=("clicks", "sum"),
        전환=("conversions", "sum"),
        ROAS=("ROAS", "mean"),
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("광고비", format_krw(channel["광고비"].sum()))
    c2.metric("광고 클릭", f"{channel['클릭'].sum():,.0f}")
    c3.metric("광고 전환", f"{channel['전환'].sum():,.0f}")

    left, right = st.columns([1.35, 1])
    with left:
        daily = marketing.groupby(["date", "channel"], as_index=False)["ROAS"].mean()
        fig = px.line(
            daily,
            x="date",
            y="ROAS",
            color="channel",
            title="채널별 ROAS",
            color_discrete_sequence=[
                COLORS["blue"],
                COLORS["green"],
                COLORS["orange"],
                COLORS["purple"],
            ],
        )
        fig.update_traces(line_width=3)
        st.plotly_chart(base_layout(fig, 350), width="stretch", key="marketing_roas")
    with right:
        fig = px.bar(
            channel.sort_values("광고비"),
            x="광고비",
            y="channel",
            orientation="h",
            title="채널별 광고비",
            color="ROAS",
            color_continuous_scale=["#EAF1FF", COLORS["blue"]],
        )
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(base_layout(fig, 350), width="stretch", key="marketing_spend")

    warnings = events[events["domain"] == "마케팅"]
    if warnings.empty:
        st.success("전주 대비 20% 이상 ROAS가 하락한 채널이 없습니다.")
    else:
        st.dataframe(warnings, width="stretch", hide_index=True)


def customer_cs_tab(bundle, start, end):
    customer = bundle.customers[bundle.customers["date"].between(start, end)].copy()
    reviews = bundle.reviews[bundle.reviews["date"].between(start, end)].copy()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("신규 고객", f"{customer['new_customers'].sum():,.0f}명")
    c2.metric("재구매 고객", f"{customer['returning_customers'].sum():,.0f}명")
    c3.metric("평균 평점", f"{reviews['rating'].mean():.2f}" if not reviews.empty else "-")
    c4.metric("환불", f"{reviews['refund_count'].sum():,.0f}건" if not reviews.empty else "0건")

    left, right = st.columns([1.35, 1])
    with left:
        melted = customer.melt(
            id_vars="date",
            value_vars=["new_customers", "returning_customers"],
            var_name="고객 유형",
            value_name="고객 수",
        )
        melted["고객 유형"] = melted["고객 유형"].map(
            {"new_customers": "신규", "returning_customers": "재구매"}
        )
        fig = px.area(
            melted,
            x="date",
            y="고객 수",
            color="고객 유형",
            title="고객 구성 추이",
            color_discrete_map={"신규": COLORS["blue"], "재구매": COLORS["green"]},
        )
        st.plotly_chart(base_layout(fig, 340), width="stretch", key="customer_trend")
    with right:
        if reviews.empty:
            st.info("선택 기간에 리뷰/CS 데이터가 없습니다.")
        else:
            by_product = reviews.groupby("product_name", as_index=False).agg(
                평점=("rating", "mean"),
                문의=("inquiry_count", "sum"),
                환불=("refund_count", "sum"),
            )
            fig = px.scatter(
                by_product,
                x="문의",
                y="평점",
                size="환불",
                hover_name="product_name",
                title="상품별 CS 신호",
                color="환불",
                color_continuous_scale=["#FFF4D4", COLORS["red"]],
            )
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(base_layout(fig, 340), width="stretch", key="cs_scatter")


def inventory_recommendation_tab(bundle, start, end, events):
    inventory = bundle.inventory[bundle.inventory["date"].between(start, end)]
    latest = inventory.loc[inventory.groupby("product_id")["date"].idxmax()].merge(
        bundle.products[["product_id", "product_name", "category"]],
        on="product_id",
        how="left",
    )
    latest["재고 비율"] = latest["current_stock"].div(latest["safe_stock"].replace(0, np.nan))
    latest["상태"] = np.select(
        [latest["current_stock"].eq(0), latest["current_stock"].lt(latest["safe_stock"])],
        ["품절", "위험"],
        default="정상",
    )
    recs = bundle.recommendations[bundle.recommendations["date"].between(start, end)]
    grouped = recs.groupby(["product_id", "product_name"], as_index=False).agg(
        노출=("recommended_count", "sum"),
        클릭=("click_count", "sum"),
        전환=("conversion_count", "sum"),
    )
    grouped["CTR"] = grouped["클릭"].div(grouped["노출"].replace(0, np.nan))
    grouped["CVR"] = grouped["전환"].div(grouped["클릭"].replace(0, np.nan))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("품절 위험 상품", f"{latest['상태'].isin(['품절','위험']).sum()}개")
    c2.metric("전체 재고", f"{latest['current_stock'].sum():,.0f}개")
    c3.metric("추천 CTR", f"{grouped['클릭'].sum()/grouped['노출'].sum():.1%}")
    c4.metric("추천 CVR", f"{grouped['전환'].sum()/grouped['클릭'].sum():.1%}")

    left, right = st.columns([1.3, 1])
    with left:
        plot = latest.sort_values("재고 비율")
        colors = plot["상태"].map({"품절": COLORS["red"], "위험": COLORS["orange"], "정상": COLORS["green"]})
        fig = go.Figure(
            go.Bar(
                x=plot["재고 비율"],
                y=plot["product_name"],
                orientation="h",
                marker_color=colors,
                text=[f"{x:.0%}" for x in plot["재고 비율"].fillna(0)],
                textposition="outside",
            )
        )
        fig.update_layout(title="안전재고 대비 현재 재고")
        st.plotly_chart(base_layout(fig, 390), width="stretch", key="inventory_ratio")
    with right:
        fig = px.scatter(
            grouped,
            x="CTR",
            y="CVR",
            size="노출",
            hover_name="product_name",
            title="AI 추천 성과",
            color="전환",
            color_continuous_scale=["#EAF1FF", COLORS["blue"]],
        )
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(base_layout(fig, 390), width="stretch", key="recommendation_scatter")

    st.markdown('<div class="sq-section-title">재고 상세</div>', unsafe_allow_html=True)
    st.dataframe(
        latest[
            ["product_name", "category", "current_stock", "safe_stock", "재고 비율", "상태"]
        ].sort_values("재고 비율"),
        width="stretch",
        hide_index=True,
        column_config={
            "product_name": "상품",
            "category": "카테고리",
            "current_stock": st.column_config.NumberColumn("현재 재고", format="%d개"),
            "safe_stock": st.column_config.NumberColumn("안전재고", format="%d개"),
            "재고 비율": st.column_config.ProgressColumn(
                "안전재고 대비", min_value=0, max_value=max(2.0, latest["재고 비율"].max())
            ),
            "상태": "상태",
        },
    )


def overview_page(bundle, start, end, kpis, deltas, events, correlations, insights):
    render_kpis(bundle, kpis, deltas, events)
    st.write("")
    tabs = st.tabs(["매출·상품", "마케팅", "고객·CS", "재고·추천"])
    with tabs[0]:
        sales_product_tab(bundle, start, end, events)
    with tabs[1]:
        marketing_tab(bundle, start, end, events)
    with tabs[2]:
        customer_cs_tab(bundle, start, end)
    with tabs[3]:
        inventory_recommendation_tab(bundle, start, end, events)

    st.write("")
    left, right = st.columns([1.15, 1])
    with left:
        st.markdown('<div class="sq-section-title">AI 핵심 인사이트</div>', unsafe_allow_html=True)
        for insight in insights:
            st.info(insight)
    with right:
        st.markdown('<div class="sq-section-title">강한 상관관계</div>', unsafe_allow_html=True)
        top = correlations.top_pairs.head(5).copy()
        if top.empty:
            st.info("선택 기간에 계산 가능한 관계가 없습니다.")
        else:
            top["지표 A"] = top["metric_a"].map(METRIC_LABELS)
            top["지표 B"] = top["metric_b"].map(METRIC_LABELS)
            top["상관계수"] = top["coefficient"].round(2)
            st.dataframe(
                top[["지표 A", "지표 B", "상관계수", "direction"]],
                width="stretch",
                hide_index=True,
                column_config={
                    "direction": "방향",
                    "상관계수": st.column_config.NumberColumn(format="%.2f"),
                },
            )
        st.markdown(
            '<div class="sq-note">상관관계는 인과관계를 뜻하지 않습니다. 프로모션·요일·계절성을 함께 확인하세요.</div>',
            unsafe_allow_html=True,
        )


def events_page(events):
    st.markdown('<div class="sq-section-title">탐지된 운영 이벤트</div>', unsafe_allow_html=True)
    f1, f2 = st.columns(2)
    domains = ["전체"] + sorted(events["domain"].dropna().unique().tolist())
    domain = f1.selectbox("분야", domains)
    severity = f2.multiselect("심각도", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    filtered = events[events["severity"].isin(severity)]
    if domain != "전체":
        filtered = filtered[filtered["domain"] == domain]
    c1, c2, c3 = st.columns(3)
    c1.metric("High", int((filtered["severity"] == "High").sum()))
    c2.metric("Medium", int((filtered["severity"] == "Medium").sum()))
    c3.metric("Low", int((filtered["severity"] == "Low").sum()))
    st.dataframe(
        filtered[
            ["date", "domain", "event_type", "product_name", "severity", "description"]
        ],
        width="stretch",
        hide_index=True,
        column_config={"date": st.column_config.DateColumn("날짜", format="YYYY-MM-DD")},
    )


def correlations_page(correlations, method):
    left, right = st.columns([1.25, 1])
    labels = [METRIC_LABELS.get(x, x) for x in correlations.matrix.columns]
    with left:
        fig = px.imshow(
            correlations.matrix,
            x=labels,
            y=labels,
            zmin=-1,
            zmax=1,
            color_continuous_scale=[
                [0, COLORS["red"]],
                [0.5, "#F8F8FA"],
                [1, COLORS["blue"]],
            ],
            text_auto=".2f",
            title=f"{method.title()} 상관관계 히트맵",
        )
        st.plotly_chart(base_layout(fig, 540), width="stretch", key="correlation_heatmap")
    with right:
        st.markdown('<div class="sq-section-title">상관관계 Top 12</div>', unsafe_allow_html=True)
        top = correlations.top_pairs.copy()
        if not top.empty:
            top["지표 A"] = top["metric_a"].map(METRIC_LABELS)
            top["지표 B"] = top["metric_b"].map(METRIC_LABELS)
            top["상관계수"] = top["coefficient"].round(3)
            st.dataframe(
                top[["지표 A", "지표 B", "상관계수", "direction", "sample_size"]],
                width="stretch",
                hide_index=True,
                column_config={"sample_size": "표본 수", "direction": "방향"},
            )
        st.markdown(
            '<div class="sq-note">절대값이 클수록 함께 움직이는 경향이 강합니다. 원인 판단에는 이벤트 전후 데이터와 운영 맥락이 필요합니다.</div>',
            unsafe_allow_html=True,
        )

    metrics = list(correlations.matrix.columns)
    a, b = st.columns(2)
    metric_a = a.selectbox("상세 지표 A", metrics, format_func=lambda x: METRIC_LABELS.get(x, x))
    metric_b = b.selectbox(
        "상세 지표 B",
        [x for x in metrics if x != metric_a],
        format_func=lambda x: METRIC_LABELS.get(x, x),
    )
    fig = px.scatter(
        correlations.daily_metrics,
        x=metric_a,
        y=metric_b,
        trendline=None,
        hover_data=["date"],
        color_discrete_sequence=[COLORS["blue"]],
        title=f"{METRIC_LABELS.get(metric_a, metric_a)} ↔ {METRIC_LABELS.get(metric_b, metric_b)}",
    )
    fig.update_traces(marker=dict(size=10, opacity=.75, line=dict(width=1, color="white")))
    st.plotly_chart(base_layout(fig, 390), width="stretch", key="correlation_detail")


def actions_page(actions, role, end):
    assigned = TaskAssignmentAgent().run(actions, role, end)
    st.markdown('<div class="sq-section-title">역할별 액션 보드</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    c1.metric("High", int((assigned["priority"] == "High").sum()) if not assigned.empty else 0)
    c2.metric("진행 전", int((assigned["status"] == "대기").sum()) if not assigned.empty else 0)
    c3.metric("마감 초과", int(assigned["overdue"].sum()) if not assigned.empty else 0)
    if assigned.empty:
        st.info("현재 역할에 배정된 액션이 없습니다.")
        return
    edited = st.data_editor(
        assigned[
            ["action_id", "team", "priority", "target", "due_date", "instruction", "status"]
        ],
        width="stretch",
        hide_index=True,
        disabled=["action_id", "team", "priority", "target", "due_date", "instruction"],
        column_config={
            "action_id": "ID",
            "team": "담당팀",
            "priority": "우선순위",
            "target": "대상",
            "due_date": st.column_config.DateColumn("마감일"),
            "instruction": "세부 지침",
            "status": st.column_config.SelectboxColumn(
                "상태", options=["대기", "진행중", "완료"], required=True
            ),
        },
        key="action_editor",
    )
    if st.button("상태 저장", type="primary", width="stretch"):
        st.session_state["saved_action_status"] = dict(
            zip(edited["action_id"], edited["status"])
        )
        st.success("현재 세션에 액션 상태를 저장했습니다.")


def agents_page(quality, events, correlations, insights, actions):
    st.markdown('<div class="sq-section-title">에이전트 실행 상태</div>', unsafe_allow_html=True)
    agents = [
        ("Data Loader Agent", f"7개 데이터셋 · {quality['rows'].sum():,}행"),
        ("Event Detector Agent", f"{len(events)}개 이벤트 탐지"),
        ("Correlation Analyzer Agent", f"{len(correlations.top_pairs)}개 상위 관계"),
        ("Insight Generator Agent", f"{len(insights)}개 인사이트"),
        ("Weekly Report Agent", "리포트 생성 준비"),
        ("Action Planner Agent", f"{len(actions)}개 액션"),
        ("Task Assignment Agent", "역할별 보드 연결"),
        ("Executive Report Agent", "대표 요약 생성 준비"),
    ]
    cols = st.columns(2)
    for idx, (name, state) in enumerate(agents):
        with cols[idx % 2]:
            st.markdown(
                f"""
                <div class="sq-card" style="min-height:auto;margin-bottom:12px">
                  <div class="sq-agent" style="border:0;padding:0">
                    <span class="sq-agent-dot"></span>
                    <span class="sq-agent-name">{name}</span>
                    <span class="sq-agent-state">정상</span>
                  </div>
                  <div class="sq-card-meta" style="margin-left:18px">{state}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown('<div class="sq-section-title">데이터 품질</div>', unsafe_allow_html=True)
    st.dataframe(quality, width="stretch", hide_index=True)


def reports_page(kpis, events, correlations, insights, actions, start, end):
    weekly = WeeklyReportAgent().run(
        kpis, events, correlations, insights, start, end
    )
    executive = ExecutiveReportAgent().run(kpis, events, actions, insights)
    tab1, tab2 = st.tabs(["주간 리포트", "대표 보고서"])
    with tab1:
        st.markdown(weekly)
        st.download_button(
            "주간 리포트 다운로드",
            weekly,
            file_name=f"weekly_report_{end:%Y%m%d}.md",
            mime="text/markdown",
            type="primary",
        )
    with tab2:
        st.markdown(executive)
        st.download_button(
            "대표 보고서 다운로드",
            executive,
            file_name=f"executive_report_{end:%Y%m%d}.md",
            mime="text/markdown",
            type="primary",
        )


def get_answer_targets(requested_agents):
    requested_agents = requested_agents or []
    requested_agents = [
        agent for agent in requested_agents if agent in ROLE_AGENT_BY_LABEL
    ]
    return requested_agents or [AUTO_AGENT]


def render_target_chips(labels):
    if not labels:
        labels = [AUTO_AGENT]
    chips = "".join(
        (
            '<span class="sq-target-chip" '
            f'style="--agent-color:{AGENT_COLORS.get(label, COLORS["gray"])}">'
            f"{escape(label)}</span>"
        )
        for label in labels
    )
    st.markdown(
        f'<div class="sq-target-chip-row">{chips}</div>',
        unsafe_allow_html=True,
    )


def queue_chat_question(question, target_agents):
    target_agents = target_agents or [AUTO_AGENT]
    workflow = select_workflow_pattern(question, target_agents)
    st.session_state.chat_messages.append(
        {
            "role": "user",
            "content": question,
            "target_agents": target_agents,
        }
    )
    st.session_state.pending_chat = {
        "question": question,
        "target_agents": target_agents,
        "workflow": workflow,
    }
    st.session_state.chat_scroll_to_bottom = True


def append_assistant_messages(answers, workflow):
    messages = []
    for response, source, _error, assignment in answers:
        messages.append(
            {
                "role": "assistant",
                "content": response,
                "source": source,
                "agent": assignment.agent.label,
                "assignment_mode": assignment.mode,
                "assignment_reason": assignment.reason,
                "page_hint": assignment.agent.dashboard_page,
                "workflow_type": workflow.workflow_type,
                "workflow_reason": workflow.reason,
            }
        )
    st.session_state.chat_messages.extend(messages)


def render_chat_message(message):
    avatar = (
        ":material/auto_awesome:"
        if message["role"] == "assistant"
        else ":material/person:"
    )
    with st.chat_message(message["role"], avatar=avatar):
        if message.get("target_agents"):
            st.markdown(
                '<div class="sq-target-label">질문 대상</div>',
                unsafe_allow_html=True,
            )
            render_target_chips(message["target_agents"])
        if message.get("agent"):
            render_assistant_header(
                message["agent"], message.get("assignment_mode")
            )
        st.markdown(message["content"])
        if message.get("assignment_reason"):
            st.caption(f"배정 근거: {message['assignment_reason']}")
        if message.get("workflow_type"):
            render_workflow_meta(
                message["workflow_type"], message.get("workflow_reason", "")
            )
        if message.get("source") and not message["source"].startswith("OpenAI ·"):
            st.caption(message["source"])


def render_assistant_header(agent_name, assignment_mode=None):
    mode_badge = (
        f'<span class="sq-chat-agent-mode">{assignment_mode}</span>'
        if assignment_mode
        else ""
    )
    st.markdown(
        (
            '<div class="sq-chat-agent-header">'
            f'<span class="sq-chat-agent-name">{escape(agent_name)}</span>'
            f"{mode_badge}</div>"
        ),
        unsafe_allow_html=True,
    )


def render_workflow_meta(workflow_type, reason):
    st.markdown(
        (
            '<div class="sq-workflow-meta">'
            f'<strong>답변 방식:</strong> {escape(workflow_type)}<br>'
            f'<strong>선택 이유:</strong> {escape(reason)}'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def stream_text_chunks(text, chunk_size=6, delay=0.012):
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]
        time.sleep(delay)


def render_streaming_chat_answer(
    question,
    kpis,
    events,
    correlations,
    actions,
    start,
    end,
    role,
    requested_agent,
    workflow,
):
    assignment = assign_role_agent(question, requested_agent)
    source = None
    error = None
    collected = ""
    with st.chat_message("assistant", avatar=":material/auto_awesome:"):
        render_assistant_header(assignment.agent.label, assignment.mode)
        placeholder = st.empty()
        try:
            if is_openai_configured():
                context = build_dashboard_context(
                    kpis, events, correlations, actions, start, end, role, assignment
                )
                context["answer_workflow"] = {
                    "type": workflow.workflow_type,
                    "reason": workflow.reason,
                    "implementation_note": workflow.implementation_note,
                }
                chunks = stream_openai_text(
                    question,
                    context,
                    assignment,
                    conversation=st.session_state.get("chat_messages", []),
                )
            else:
                source = "규칙 기반"
                fallback = answer_dashboard_question(
                    question,
                    kpis,
                    events,
                    correlations,
                    actions,
                    start,
                    end,
                    assignment,
                )
                chunks = stream_text_chunks(fallback)

            for chunk_index, chunk in enumerate(chunks):
                collected += chunk
                placeholder.markdown(collected + "▌")
                if chunk_index % 4 == 0:
                    scroll_chat_to_bottom()
            if not collected.strip():
                raise RuntimeError("답변 텍스트가 비어 있습니다.")
        except Exception as exc:
            source = "규칙 기반 fallback"
            error = str(exc)
            fallback = answer_dashboard_question(
                question,
                kpis,
                events,
                correlations,
                actions,
                start,
                end,
                assignment,
            )
            collected = ""
            for chunk_index, chunk in enumerate(stream_text_chunks(fallback)):
                collected += chunk
                placeholder.markdown(collected + "▌")
                if chunk_index % 4 == 0:
                    scroll_chat_to_bottom()

        placeholder.markdown(collected)
        if assignment.reason:
            st.caption(f"배정 근거: {assignment.reason}")
        render_workflow_meta(workflow.workflow_type, workflow.reason)
        if source:
            st.caption(source)
    return collected, source, error, assignment


def scroll_chat_to_bottom():
    st.iframe(
        """
        <script>
        const doc = window.parent.document;
        const history = doc.querySelector('.st-key-chat_history');
        if (history) {
          requestAnimationFrame(() => { history.scrollTop = history.scrollHeight; });
        }
        </script>
        """,
        height=1,
    )


def render_chat_panel(kpis, events, correlations, actions, start, end, role):
    openai_ready = is_openai_configured()
    status_label = (
        f"OpenAI · {configured_model()}" if openai_ready else "규칙 기반"
    )
    with st.container(border=True, key="chat_panel_shell"):
        st.markdown(
            f"""
            <div class="sq-chat-header">
              <div>
                <div class="sq-eyebrow">DASHBOARD COPILOT</div>
                <div class="sq-chat-title">운영 분석 AI</div>
              </div>
              <span class="sq-status">{status_label}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="sq-context">현재 분석 맥락 · {start:%m.%d}–{end:%m.%d} · 이벤트 {len(events)}건 · 액션 {len(actions)}건</div>',
            unsafe_allow_html=True,
        )

        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [
                {
                    "role": "assistant",
                    "content": (
                        "질문 맥락에 맞는 직무 담당을 자동 배정해 현재 대시보드 데이터로 "
                        "답변합니다. 필요하면 아래 담당 칩을 하나 이상 선택해 직접 질문하세요."
                    ),
                    "agent": "AI 운영 코디네이터",
                }
            ]

        with st.container(
            key="chat_history",
            height="stretch",
            border=False,
            autoscroll=True,
        ):
            st.caption("빠른 질문")
            suggestions = [
                "품절 위험 상품 알려줘",
                "이번 기간 매출 변화는?",
                "우선 액션을 추천해줘",
            ]
            for idx, suggestion in enumerate(suggestions):
                if st.button(suggestion, key=f"suggest_{idx}", width="stretch"):
                    requested_agents = st.session_state.get(
                        "chat_requested_agents", []
                    )
                    queue_chat_question(suggestion, get_answer_targets(requested_agents))
                    st.rerun()

            for message in st.session_state.chat_messages:
                render_chat_message(message)

            pending_chat = st.session_state.pop("pending_chat", None)
            if pending_chat:
                scroll_chat_to_bottom()
                workflow = pending_chat.get("workflow") or select_workflow_pattern(
                    pending_chat["question"], pending_chat.get("target_agents", [])
                )
                streamed_answers = []
                for requested_agent in get_answer_targets(
                    pending_chat.get("target_agents", [])
                ):
                    streamed_answers.append(
                        render_streaming_chat_answer(
                            pending_chat["question"],
                            kpis,
                            events,
                            correlations,
                            actions,
                            start,
                            end,
                            role,
                            requested_agent,
                            workflow,
                        )
                    )
                append_assistant_messages(streamed_answers, workflow)
                errors = [
                    error for *_rest, error, _assignment in streamed_answers if error
                ]
                if errors:
                    st.session_state["openai_last_error"] = "\n\n".join(errors)
                else:
                    st.session_state.pop("openai_last_error", None)
                st.session_state.chat_scroll_to_bottom = True
                scroll_chat_to_bottom()
                st.rerun()

            if st.session_state.get("openai_last_error"):
                with st.expander("최근 OpenAI 연결 오류"):
                    st.caption(st.session_state["openai_last_error"])
            if st.session_state.pop("chat_scroll_to_bottom", False):
                scroll_chat_to_bottom()

        st.markdown('<div class="sq-chat-controls"></div>', unsafe_allow_html=True)
        with st.container(key="chat_agent_selector"):
            selected_before = st.session_state.get("chat_requested_agents", [])
            picker_label = (
                f"답변 담당 · {len(selected_before)}명 선택"
                if selected_before
                else "답변 담당 · 자동 배정"
            )
            with st.popover(
                picker_label,
                icon=":material/tune:",
                width="stretch",
                key="chat_agent_picker_popover",
            ):
                st.markdown(
                    '<div class="sq-agent-picker-summary">질문할 담당을 선택하세요. 복수 선택도 가능합니다.</div>',
                    unsafe_allow_html=True,
                )
                requested_agents = st.pills(
                    "답변 담당 선택",
                    list(ROLE_AGENT_BY_LABEL),
                    selection_mode="multi",
                    key="chat_requested_agents",
                    help=(
                        "선택하지 않으면 질문 맥락에 맞는 담당을 자동 배정합니다. "
                        "하나 이상 선택하면 선택된 담당들이 각각 답변합니다."
                    ),
                    label_visibility="collapsed",
                    width="stretch",
                )

        with st.form("chat_form", clear_on_submit=True, border=False):
            prompt = st.text_area(
                "질문",
                placeholder="예: 판매 급증의 원인과 필요한 액션은?",
                label_visibility="collapsed",
                height=88,
            )
            submitted = st.form_submit_button(
                "질문 보내기", type="primary", width="stretch"
            )
        if submitted and prompt.strip():
            queue_chat_question(prompt, get_answer_targets(requested_agents))
            st.rerun()


def run_dashboard() -> None:
    st.set_page_config(
        page_title="AI 커머스 운영 대시보드",
        page_icon=None,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_square_theme()
    bundle, quality = load_data()
    if st.session_state.get("current_page") not in PAGE_BY_KEY:
        st.session_state["current_page"] = "home"

    with st.sidebar:
        st.markdown(
            '<div class="sq-brand"><span>agent</span><span class="sq-brand-switch">⌃⌄</span></div>',
            unsafe_allow_html=True,
        )
        render_sidebar_nav(st.session_state["current_page"])
        st.write("")
        st.markdown('<div class="sq-eyebrow">FILTERS</div>', unsafe_allow_html=True)
        date_range = st.date_input(
            "분석 기간",
            value=(bundle.max_date.date() - pd.Timedelta(days=13), bundle.max_date.date()),
            min_value=bundle.min_date.date(),
            max_value=bundle.max_date.date(),
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
        else:
            start_date = end_date = date_range
        role = st.selectbox("역할", ["전체", "대표", "마케팅", "MD", "CRM/CS", "운영"])
        method = st.selectbox("상관 방식", ["pearson", "spearman"])
        st.caption(f"데이터: {bundle.min_date:%Y.%m.%d}–{bundle.max_date:%Y.%m.%d}")

    start, end = pd.Timestamp(start_date), pd.Timestamp(end_date)
    quality, events, correlations, insights, actions = run_analysis(
        start_date, end_date, method, role
    )
    kpis, deltas = compare_period_kpis(bundle, start, end)
    page = st.session_state["current_page"]
    page_meta = PAGE_BY_KEY[page]
    render_header(start, end, role, page_meta)

    main_col, chat_col = st.columns([2.55, 1], gap="large")
    with main_col:
        if page == "home":
            overview_page(
                bundle, start, end, kpis, deltas, events, correlations, insights
            )
        elif page == "events":
            events_page(events)
        elif page == "analytics":
            correlations_page(correlations, method)
        elif page == "tasks":
            actions_page(actions, role, end)
        elif page == "agents":
            agents_page(quality, events, correlations, insights, actions)
        else:
            reports_page(kpis, events, correlations, insights, actions, start, end)

    with chat_col:
        render_chat_panel(kpis, events, correlations, actions, start, end, role)
