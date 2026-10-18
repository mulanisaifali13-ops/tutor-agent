"""Frontend helpers shared by all pages. This is the only layer (with app.py and pages/) that imports streamlit."""
import os
import time
from typing import Callable, List, Optional

import streamlit as st

from backend import llm, storage
from backend.documents import DocumentError
from backend.schemas import Question


def load_secrets() -> None:
    """Copy the key from Streamlit secrets into the environment. The key is never shown or logged."""
    if os.environ.get("GROQ_API_KEY"):
        return
    try:
        key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        key = None
    if key:
        os.environ["GROQ_API_KEY"] = str(key)


def setup(title: str = "Your Personal Teacher", icon: str = "🎓") -> None:
    st.set_page_config(page_title=title, page_icon=icon)
    load_secrets()
    st.session_state.setdefault("student_id", None)
    st.session_state.setdefault("course_id", None)
    with st.sidebar:
        st.header("Status")
        if llm.has_key():
            st.success("API key found")
            if "model_name" not in st.session_state:
                try:
                    st.session_state.model_name = llm.available_chat_models()[0]
                except llm.LLMError as e:
                    st.warning(str(e))
            if "model_name" in st.session_state:
                st.caption(f"Model: {st.session_state.model_name}")
        else:
            st.error("No API key yet. Add GROQ_API_KEY in .streamlit/secrets.toml (or the app's Secrets on Streamlit Cloud).")
        st.write(f"**Student:** {st.session_state.student_id or 'not chosen'}")
        st.write(f"**Course:** {st.session_state.course_id or 'not chosen'}")


def link(page: str, label: str, icon: str = "➡️") -> None:
    """A page link that never crashes the page (falls back to a plain hint)."""
    try:
        st.page_link(page, label=label, icon=icon)
    except Exception:
        st.write(f"{icon} Open **{label}** from the sidebar.")


def _stop(message: str, page: str, label: str) -> None:
    st.info(message)
    link(page, label)
    st.stop()


def require(student: bool = True, course: bool = False, profile: bool = False, path: bool = False) -> None:
    """Every page starts here: friendly message plus a link if something is missing."""
    s = st.session_state
    if student and not s.get("student_id"):
        _stop("Please choose or create a student first.", "app.py", "Go to Home")
    if course and (not s.get("course_id") or not storage.load_course(s.course_id)):
        _stop("Please upload a document (or choose a course on Home) first.", "pages/1_Upload_Document.py", "Upload a document")
    if profile and not storage.load_profile(s.student_id):
        _stop("I haven't met you yet. Let's have our first meeting!", "pages/2_First_Meeting.py", "First meeting")
    if path and not storage.load_path(s.student_id):
        _stop("Let's choose your topics and make your plan first.", "pages/3_Choose_and_Pretest.py", "Choose topics")


def run(fn: Callable, *args, spinner: str = "The teacher is thinking, please wait...", **kwargs):
    """Call backend code with a spinner and a friendly error. Returns None on failure."""
    try:
        with st.spinner(spinner):
            return fn(*args, **kwargs)
    except (llm.LLMError, DocumentError) as e:
        st.error(str(e))
    except Exception as e:
        st.error(f"Something unexpected happened ({type(e).__name__}). Please try again.")
    return None


def reset_keys(*prefixes: str) -> None:
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and k.startswith(prefixes):
            del st.session_state[k]


def question_flow(key: str, questions: List[Question]) -> Optional[dict]:
    """Show questions one at a time with hint and immediate feedback.
    Returns None while in progress, then a result dict when every question has been answered."""
    s = st.session_state.setdefault(f"qf_{key}", {"i": 0, "checked": False, "hint": False, "results": {}, "start": time.time()})
    n = len(questions)
    if s["i"] >= n:
        wrong = [q for q in questions if s["results"].get(q.id) != q.correct_index]
        return {"correct": n - len(wrong), "total": n, "wrong_ids": [q.id for q in wrong],
                "chosen_wrong": {q.id: s["results"][q.id] for q in wrong if s["results"].get(q.id) is not None},
                "seconds": int(time.time() - s["start"]), "asked": [q.id for q in questions]}
    q = questions[s["i"]]
    st.progress(s["i"] / n, text=f"Question {s['i'] + 1} of {n}")
    st.markdown(f"**{q.text}**")
    choice = st.radio("Choose one", q.options, index=None, key=f"qrad_{key}_{q.id}", disabled=s["checked"],
                      label_visibility="collapsed")
    if not s["checked"]:
        if q.hint and st.button("Show hint", key=f"hint_{key}_{q.id}"):
            s["hint"] = True
        if s["hint"] and q.hint:
            st.info(q.hint)
        if st.button("Check my answer", key=f"check_{key}_{q.id}", disabled=choice is None, type="primary"):
            s["results"][q.id] = q.options.index(choice)
            s["checked"] = True
            st.rerun()
    else:
        picked = s["results"][q.id]
        if picked == q.correct_index:
            st.success(f"Yes! {q.option_explanations[picked]}")
        else:
            st.warning(f"Not yet. {q.option_explanations[picked]}")
            st.markdown(f"The best answer is **{q.options[q.correct_index]}**. {q.option_explanations[q.correct_index]}")
        if st.button("Next", key=f"next_{key}_{q.id}", type="primary"):
            s["i"] += 1
            s["checked"], s["hint"] = False, False
            st.rerun()
    return None
