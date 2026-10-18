"""Stage 2: upload a document, find topics, save the course."""
import pandas as pd
import streamlit as st

import ui
from backend import documents, storage, topics
from backend.documents import DocumentError
from backend.schemas import Course, Topic

ui.setup("Upload a document", "📄")
ui.require(student=True)
S = st.session_state

st.title("📄 Upload a document")
up = st.file_uploader("Choose a PDF or text file", type=["pdf", "txt"])
use_sample = st.checkbox("Use sample text (photosynthesis) for testing")

source = ("sample.txt", documents.SAMPLE_TEXT.encode()) if use_sample else ((up.name, up.getvalue()) if up else None)
if source:
    key = f"{source[0]}:{len(source[1])}"
    if S.get("doc_key") != key:
        try:
            pages = documents.read_document(source[1], source[0])
            documents.check_quality(pages)
            S.update(doc_key=key, doc_pages=pages, doc_spans=documents.make_spans(pages), doc_topics=None)
        except DocumentError as e:
            S.pop("doc_key", None)
            st.error(str(e))
            st.stop()

if not S.get("doc_spans"):
    st.info("Upload a file (or tick the sample box) to begin.")
    st.stop()

spans = S.doc_spans
c1, c2, c3 = st.columns(3)
c1.metric("Pages", len(S.doc_pages))
c2.metric("Characters", sum(len(p["text"]) for p in S.doc_pages))
c3.metric("Passages", len(spans))
with st.expander("Preview passage S1"):
    st.write(spans[0].text)
windows, cut = topics.make_windows(spans)
if cut:
    st.warning(f"This document is long, so I'll read only the first {len(windows)} parts to start with.")

if st.button("Find topics", type="primary"):
    bar = st.progress(0.0, text="Starting...")
    found = ui.run(topics.find_topics, spans, lambda f, m: bar.progress(min(f, 1.0), text=m),
                   spinner="Finding the main topics...")
    bar.empty()
    if found:
        S.doc_topics = found
        S.course_title = ui.run(topics.make_course_title, found, spinner="Naming your course...") or "My course"
    elif found is not None:
        st.error("I could not find clear topics in this document. Try a longer or clearer file.")

if not S.get("doc_topics"):
    st.stop()


def _s(v) -> str:
    return "" if v is None or (isinstance(v, float) and v != v) else str(v)


original = {t.id: t for t in S.doc_topics}
df = pd.DataFrame([{"id": t.id, "title": t.title, "summary": t.summary, "difficulty": t.difficulty,
                    "prerequisites": ", ".join(t.prerequisites)} for t in S.doc_topics])
st.subheader("Topics I found")
st.caption("You can rename topics or delete rows you don't want.")
edited = st.data_editor(df, num_rows="dynamic", width="stretch", hide_index=True, disabled=["id"],
                        column_config={"difficulty": st.column_config.SelectboxColumn(
                            options=["beginner", "intermediate", "advanced"], required=True)})
title = st.text_input("Course title", value=S.get("course_title", "My course"))

if st.button("Save course", type="primary"):
    rows = []
    for r in edited.to_dict("records"):
        tid = _s(r.get("id"))
        if tid in original and _s(r.get("title")).strip():
            rows.append(Topic(id=tid, title=_s(r["title"]), summary=_s(r.get("summary")),
                              difficulty=_s(r.get("difficulty")) or "beginner",
                              prerequisites=[p.strip() for p in _s(r.get("prerequisites")).split(",") if p.strip()],
                              source_spans=original[tid].source_spans))
    cleaned = topics.clean_topics(rows, {s.id for s in spans})
    if not cleaned:
        st.error("Please keep at least one topic.")
    else:
        cid = storage.slugify(title)
        storage.save_json(storage.course_dir(cid) / "source_spans.json", spans)
        storage.save_json(storage.course_dir(cid) / "topics.json", Course(course_id=cid, course_title=title, topics=cleaned))
        S.course_id = cid
        st.success(f"Saved your course '{title}' with {len(cleaned)} topics.")
        ui.link("pages/2_First_Meeting.py", "Next: first meeting", "➡️")
