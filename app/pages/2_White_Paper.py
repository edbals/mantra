"""
Mantra — Strategy White Paper
Renders the rich HTML whitepaper inside Streamlit via components.html().
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

_LOGO = Path(__file__).parent.parent / "v2" / "logo.png"

st.set_page_config(
    page_title="White Paper — Mantra",
    page_icon=str(_LOGO) if _LOGO.exists() else "📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Hide Streamlit's chrome (top bar, footer, default padding) so the embedded
# whitepaper takes the full viewport.
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

_html_path = Path(__file__).parent / "whitepaper.html"
components.html(_html_path.read_text(), height=1200, scrolling=True)
