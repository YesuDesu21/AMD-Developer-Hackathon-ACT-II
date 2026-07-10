from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from src.router.policy import Policy

st.set_page_config(page_title="TokenGate", page_icon="🔒", layout="centered")
st.title("🔒 TokenGate")
st.caption("Hybrid Token-Efficient Routing Agent")


@st.cache_resource
def get_router() -> Policy:
    return Policy()


router = get_router()

if "history" not in st.session_state:
    st.session_state.history = []


def render_metadata(outcome: dict) -> None:
    st.caption(
        f"**Model:** {outcome.get('model', 'unknown')} · "
        f"**Model name:** {outcome.get('model_name', 'unknown')} · "
        f"**Confidence:** {outcome.get('confidence', 0.0):.2f} · "
        f"**Tokens:** {outcome.get('tokens_used', 0)}"
    )
    if outcome.get("error"):
        st.error(outcome["error"])


def render_user_turn(prompt: str) -> None:
    _, right = st.columns([1, 3])
    with right:
        with st.container(border=True):
            st.markdown(prompt)


def render_assistant_turn(outcome: dict) -> None:
    left, _ = st.columns([3, 1])
    with left:
        with st.container(border=True):
            st.markdown(outcome.get("answer", ""))
            render_metadata(outcome)


# Replay prior turns on every rerun
for turn in st.session_state.history:
    render_user_turn(turn["prompt"])
    render_assistant_turn(turn)

# Handle a new message
prompt = st.chat_input("Ask something...")
if prompt:
    render_user_turn(prompt)

    with st.spinner("Routing..."):
        outcome = router.route(prompt)
    render_assistant_turn(outcome)

    st.session_state.history.append({
        "prompt": prompt,
        "answer": outcome.get("answer", ""),
        "model": outcome.get("model", "unknown"),
        "model_name": outcome.get("model_name", "unknown"),
        "confidence": outcome.get("confidence", 0.0),
        "tokens_used": outcome.get("tokens_used", 0),
        "error": outcome.get("error"),
    })