"""Stage 4: topic choice helpers, pre-test, scoring and the learning path."""
from collections import defaultdict
from typing import Dict, List, Optional

import config
from backend import questions as qgen
from backend.schemas import (Course, LearningPath, PathItem, PreTest, PreTestAnswer, Span, StudentProfile,
                             Topic, TopicPlacement)

RANK = {"beginner": 0, "intermediate": 1, "advanced": 2}


def suggest_topics(profile: StudentProfile, topics: List[Topic], n: int = 3) -> List[str]:
    """Rule-based: topics that fit the student's level first, always including needed earlier topics."""
    by_id = {t.id: t for t in topics}
    ordered = sorted(topics, key=lambda t: (abs(RANK[t.difficulty] - RANK[profile.level]), topics.index(t)))
    chosen: List[str] = []
    for t in ordered:
        for need in t.prerequisites + [t.id]:
            if need not in chosen and need in by_id:
                chosen.append(need)
        if len(chosen) >= n:
            break
    return [t.id for t in topics if t.id in chosen]


def advise_order(chosen_ids: List[str], topics: List[Topic]) -> List[str]:
    """Friendly warnings when a chosen topic needs an earlier topic that is not chosen."""
    by_id = {t.id: t for t in topics}
    notes = []
    for tid in chosen_ids:
        t = by_id[tid]
        for p in t.prerequisites:
            if p not in chosen_ids and p in by_id:
                notes.append(f"'{t.title}' builds on '{by_id[p].title}'. Shall we start there? I'll check your basics in the quiz.")
    return notes


def generate_pretest(course: Course, spans: List[Span], chosen_ids: List[str]) -> PreTest:
    by_id = {t.id: t for t in course.topics}
    questions, prereq_q = [], []
    extra = [p for tid in chosen_ids for p in by_id[tid].prerequisites if p not in chosen_ids and p in by_id]
    for tid in chosen_ids:
        t = by_id[tid]
        questions += qgen.ask_questions(
            "Write 2 short pre-test multiple-choice questions on this topic that make the student think "
            f"(explain, apply, or compare, not just recall). Topic: {t.title} - {t.summary}",
            t, spans, f"P{t.id}-", 2)
    for pid in dict.fromkeys(extra):
        t = by_id[pid]
        qs = qgen.ask_questions(
            f"Write 1 basic multiple-choice question checking the student knows the basics of: {t.title} - {t.summary}",
            t, spans, f"P{t.id}-", 1)
        questions += qs
        prereq_q += [q.id for q in qs]
    return PreTest(course_id=course.course_id, chosen_topic_ids=chosen_ids, questions=questions,
                   prerequisite_question_ids=prereq_q)


def score_pretest(pretest: PreTest, answers: List[PreTestAnswer],
                  topics: Optional[List[Topic]] = None) -> Dict[str, TopicPlacement]:
    """Rule: when unsure, teach. Skip only when the evidence is strong."""
    ans = {a.question_id: a for a in answers}
    prereq_ids = set(pretest.prerequisite_question_ids)
    by_topic: Dict[str, list] = defaultdict(list)
    for q in pretest.questions:
        by_topic[q.topic_id].append(q)
    topic_map = {t.id: t for t in (topics or [])}

    def correct(q) -> bool:
        a = ans.get(q.id)
        return a is not None and a.chosen_index == q.correct_index

    def conf(q) -> str:
        a = ans.get(q.id)
        return a.confidence if a else "unsure"

    def answered(q) -> bool:
        a = ans.get(q.id)
        return a is not None and a.chosen_index is not None

    placements: Dict[str, TopicPlacement] = {}
    for tid in pretest.chosen_topic_ids:
        qs = [q for q in by_topic[tid] if q.id not in prereq_ids]
        n_ok = sum(correct(q) for q in qs)
        if any(answered(q) and not correct(q) and conf(q) == "sure" for q in qs):
            state, why = "misconception_lesson", "You were sure about an answer that was not quite right, so we'll look at it closely."
        elif qs and n_ok == len(qs) and all(conf(q) == "sure" for q in qs):
            state, why = "skip_with_check", "You answered with confidence, so we'll just do a quick check."
        elif n_ok >= 1:
            state, why = "short_path", "You know part of this already, so we'll go to the missing part."
        else:
            state, why = "full_lesson", "This is new to you, so we'll start from the beginning, step by step."
        bridges = []
        for p in (topic_map[tid].prerequisites if tid in topic_map else []):
            pq = [q for q in by_topic.get(p, []) if q.id in prereq_ids]
            if pq and not all(correct(q) for q in pq):
                bridges.append(p)
        if bridges:
            state, why = "bridge_first", "We'll refresh some basics first, then come back to this topic."
        placements[tid] = TopicPlacement(topic_id=tid, state=state, reason=why, bridge_topic_ids=bridges,
                                         correct=n_ok, total=len(qs))
    return placements


def build_path(profile: StudentProfile, course: Course, placements: Dict[str, TopicPlacement]) -> LearningPath:
    """Keep course order; insert bridge topics before the topics that need them."""
    scale = max(0.5, min(1.5, profile.daily_minutes / 30))
    titles = {t.id: t.title for t in course.topics}
    items, added = [], set()

    def minutes(state: str) -> int:
        return max(3, round(config.PATH_MINUTES[state] * scale))

    for t in course.topics:
        p = placements.get(t.id)
        if not p:
            continue
        for b in p.bridge_topic_ids:
            if b not in added and b not in placements:
                items.append(PathItem(order=0, topic_id=b, state="bridge_first", minutes=minutes("bridge_first"),
                                      reason=f"Basics needed before '{titles[t.id]}'."))
                added.add(b)
        if t.id in added:
            continue
        state = "full_lesson" if p.state == "bridge_first" else p.state
        items.append(PathItem(order=0, topic_id=t.id, state=state, minutes=minutes(state), reason=p.reason))
        added.add(t.id)
    for i, it in enumerate(items, 1):
        it.order = i
    return LearningPath(student_id=profile.student_id, course_id=course.course_id, items=items)
