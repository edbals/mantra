"""
MyMantra Dashboard v2 — Bloomberg-style React prototype embedded in Streamlit.

Currently uses mock data from app/v2/src/data.js. Real data wiring is the
next step — a Python adapter will read scores_*.csv and inject window.IDX_DATA
before serving.
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Dashboard v2 — MyMantra",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Strip Streamlit chrome so the embedded app fills the viewport
st.markdown(
    """
    <style>
      header[data-testid="stHeader"] { display: none; }
      .block-container { padding: 0 !important; max-width: 100% !important; }
      footer { display: none; }
      [data-testid="stSidebarCollapsedControl"] { display: block; }
    </style>
    """,
    unsafe_allow_html=True,
)

V2_DIR = Path(__file__).parent.parent / "v2"


def build_inlined_html() -> str:
    """Read index.html and inline every local CSS/JS file referenced by it."""
    html = (V2_DIR / "index.html").read_text()

    css = (V2_DIR / "src" / "styles.css").read_text()
    html = html.replace(
        '<link rel="stylesheet" href="src/styles.css"/>',
        f"<style>{css}</style>",
    )

    data_js = (V2_DIR / "src" / "data.js").read_text()
    html = html.replace(
        '<script src="src/data.js"></script>',
        f"<script>{data_js}</script>",
    )

    for jsx in ("icons", "ui", "charts", "views", "app"):
        content = (V2_DIR / "src" / f"{jsx}.jsx").read_text()
        html = html.replace(
            f'<script type="text/babel" data-presets="react" src="src/{jsx}.jsx"></script>',
            f'<script type="text/babel" data-presets="react">{content}</script>',
        )

    return html


components.html(build_inlined_html(), height=1100, scrolling=True)
