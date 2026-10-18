"""Stage 4: choose topics, take an ungraded pre-test, get a personal learning path."""
import streamlit as st

import ui
from backend import pretest, storage
from backend.schemas import PreTest, PreTestAnswer

ui.setup("Choose and pre-test", "🧭")
ui.require(student=True, course=True, profile=True)
S = st.session_state
sid, cid = S.student_id, S.course_id
course, spans = storage.load_course(cid)
profile = storage.load_profile(sid)
topics = course.topics
by_id = {t.id: t for t in topics}

if S.get("pt_for") != (sid, cid):
    for k in ("pretest", "placements", "pt_answers"):
        S.pop(k, None)
    S.pt_for = (sid, cid)

FRIENDLY = {"skip_with_check": "Quick check", "short_path": "Short lesson", "full_lesson": "Full lesson",
            "misconception_lesson": "Careful lesson", "bridge_first": "Basics first"}

st.title("🧭 Choose what to learn")

# ---------- Step 3: result ----------
if S.get("placements"):
    st.subheader("Your plan")
    adjusted = {}
    for tid, p in S.placements.items():
        if p.state == "skip_with_check" and st.checkbox(
                f"You already seem to know '{by_id[tid].title}'. Tick to take the full lesson anyway.", key=f"add_{tid}"):
            p = p.model_copy(update={"state": "full_lesson", "reason": "You asked for the full lesson."})
        adjusted[tid] = p
    path = pretest.build_path(profile, course, adjusted)
    total = sum(i.minutes for i in path.items)
    st.success(f"Your plan: {len(path.items)} lessons, about {total} minutes in total.")
    st.dataframe([{"Order": i.order, "Topic": by_id[i.topic_id].title, "Type": FRIENDLY[i.state],
                   "Minutes": i.minutes, "Why": i.reason} for i in path.items], hide_index=True, width="stretch")
    if st.button("Save my plan", type="primary"):
        storage.save_json(storage.student_dir(sid) / "path.json", path)
        storage.save_json(storage.student_dir(sid) / "pretest_result.json", {
            "scores": {t: {"correct": p.correct, "total": p.total} for t, p in S.placements.items()},
            "placements": S.placements, "answers": S.pt_answers})
        st.success("Your plan is saved.")
        ui.link("pages/4_Learn.py", "Start learning", "📚")
    if st.button("Start over"):
        for k in ("pretest", "placements", "pt_answers"):
            S.pop(k, None)
        st.rerun()
    st.stop()

# ---------- Step 2: pre-test ----------
if S.get("pretest"):
    pt: PreTest = S.pretest
    st.info("This short quiz is not marked. It only helps me choose where to start.")
    with st.form("pretest_form"):
        for n, q in enumerate(pt.questions, 1):
            st.markdown(f"**{n}. {q.text}**")
            st.radio("Answer", q.options + ["I don't know yet"], index=None, key=f"pt_{q.id}", label_visibility="collapsed")
            st.radio("How sure are you?", ["sure", "unsure", "guessing"], index=1, horizontal=True, key=f"ptc_{q.id}")
            st.divider()
        submitted = st.form_submit_button("Submit", type="primary")
    if submitted:
        answers = []
        for q in pt.questions:
            val = S.get(f"pt_{q.id}")
            answers.append(PreTestAnswer(question_id=q.id, chosen_index=q.options.index(val) if val in q.options else None,
                                         confidence=S.get(f"ptc_{q.id}", "unsure")))
        S.pt_answers = answers
        S.placements = pretest.score_pretest(pt, answers, topics)
        st.rerun()
    if st.button("Back to topics"):
        S.pretest = None
        st.rerun()
    st.stop()

# ---------- Step 1: choose ----------
st.write("What would you like to learn first? The choice is always yours.")
for t in topics:
    with st.container(border=True):
        st.markdown(f"**{t.title}** · _{t.difficulty}_")
        st.write(t.summary)


def _suggest() -> None:
    S.choose_ids = pretest.suggest_topics(profile, topics)


st.button("Not sure, suggest for me", on_click=_suggest)
picked = st.multiselect("Your topics", [t.id for t in topics], key="choose_ids", format_func=lambda i: by_id[i].title)
chosen = [t.id for t in topics if t.id in picked]
for note in pretest.advise_order(chosen, topics):
    st.info(note)
if st.button("Start the short quiz", type="primary", disabled=not chosen):
    pt = ui.run(pretest.generate_pretest, course, spans, chosen, spinner="Preparing your quiz...")
    if pt:
        S.pretest = pt
        storage.save_json(storage.student_dir(sid) / "pretest.json", pt)
        st.rerun()
