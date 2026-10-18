"""Home page: choose or create a student, choose a course, say hello."""
import streamlit as st

import ui
from backend import llm, storage

ui.setup("Your Personal Teacher", "🎓")
S = st.session_state

st.title("🎓 Your Personal Teacher")
st.write("Upload a document and I'll teach it to you step by step, at your pace.")

if not llm.has_key():
    st.error("I need an API key to think. Add `GROQ_API_KEY = \"...\"` to `.streamlit/secrets.toml` "
             "(or to the app's Secrets on Streamlit Cloud), then refresh this page.")

st.subheader("Who is learning today?")
students = storage.list_students()
if students:
    idx = students.index(S.student_id) if S.student_id in students else None
    pick = st.selectbox("Choose a student", students, index=idx, placeholder="Pick a name")
    if pick and pick != S.student_id:
        S.student_id = pick
        st.rerun()
with st.form("new_student", clear_on_submit=True):
    name = st.text_input("Or create a new student")
    if st.form_submit_button("Create student"):
        if not name.strip():
            st.warning("Please type a name first.")
        else:
            S.student_id = storage.slugify(name)
            storage.student_dir(S.student_id)
            st.rerun()

courses = storage.list_courses()
if courses:
    cidx = courses.index(S.course_id) if S.course_id in courses else None
    cpick = st.selectbox("Course", courses, index=cidx, placeholder="Pick a course")
    if cpick and cpick != S.course_id:
        S.course_id = cpick
        st.rerun()

if S.student_id:
    st.subheader("Your journey")
    prof, path = storage.load_profile(S.student_id), storage.load_path(S.student_id)
    st.write(f"{'✅' if S.course_id else '⬜'} 1. Upload a document")
    st.write(f"{'✅' if prof else '⬜'} 2. First meeting")
    st.write(f"{'✅' if path else '⬜'} 3. Choose topics and pre-test")
    st.write("⬜ 4. Learn   ⬜ 5. Today's target")
    ui.link("pages/1_Upload_Document.py", "Upload a document", "📄")
    ui.link("pages/2_First_Meeting.py", "First meeting", "💬")
    ui.link("pages/3_Choose_and_Pretest.py", "Choose topics and pre-test", "🧭")
    ui.link("pages/4_Learn.py", "Learn", "📚")
    ui.link("pages/5_Today.py", "Today", "📅")

    if st.button("Say hello 👋"):
        who = prof.name if prof else S.student_id
        reply = ui.run(llm.ask, f"Greet a student called {who} in one warm sentence and invite them to start.",
                       system=llm.TEACHER_SYSTEM, max_tokens=80)
        if reply:
            with st.chat_message("assistant"):
                st.write(reply)
