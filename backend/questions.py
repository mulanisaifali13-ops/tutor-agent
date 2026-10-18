"""Shared question maker used by the pre-test (Stage 4) and lessons (Stage 5)."""
import random
from typing import List

from pydantic import BaseModel

import config
from backend import llm
from backend.schemas import Question, Span, Topic

Q_SHAPE = ('{"id":"q1","topic_id":"T1","text":"question","options":["A","B","C","D"],"correct_index":0,'
           '"option_explanations":["why option A is right or wrong","...","...","..."],'
           '"kind":"recall|explain|apply|compare|choose_and_justify","hint":"a gentle nudge",'
           '"source_spans":["S1"],"objective_index":0}')


class QuestionList(BaseModel):
    questions: List[Question]


def passages_text(topic: Topic, spans: List[Span]) -> str:
    by_id = {s.id: s for s in spans}
    out, size = [], 0
    for sid in topic.source_spans:
        if sid in by_id:
            line = f"[{sid}] {by_id[sid].text}"
            if out and size + len(line) > config.PASSAGE_CHARS_PER_CALL:
                break
            out.append(line)
            size += len(line)
    return "\n\n".join(out)


def question_problems(q: Question) -> List[str]:
    problems = []
    opts = [o.strip().lower() for o in q.options]
    if len(set(opts)) != 4 or "" in opts:
        problems.append("options must be four different, non-empty answers")
    if any(not e.strip() for e in q.option_explanations):
        problems.append("every option needs an explanation")
    if not q.text.strip():
        problems.append("question text is empty")
    return problems


def finalize(q: Question, topic: Topic, qid: str, rng: random.Random) -> Question:
    """Set ids, keep only valid passage ids, and shuffle options so the answer is not always in the same place."""
    order = list(range(4))
    rng.shuffle(order)
    spans = [s for s in q.source_spans if s in topic.source_spans] or list(topic.source_spans)
    return q.model_copy(update={
        "id": qid, "topic_id": topic.id, "source_spans": spans,
        "options": [q.options[i] for i in order],
        "option_explanations": [q.option_explanations[i] for i in order],
        "correct_index": order.index(q.correct_index),
    })


def ask_questions(task: str, topic: Topic, spans: List[Span], prefix: str, count: int) -> List[Question]:
    """Ask the model for `count` questions on one topic, using only that topic's passages. Retries once."""
    rng = random.Random()
    prompt = (f"{task}\n\nEach question has exactly 4 options and ONE correct answer. Wrong options should reflect common "
              "mistakes. Give a short explanation for EVERY option (why it is right or why it is wrong). "
              "Use ONLY the passages. Question shape:\n" + Q_SHAPE +
              f'\nOutput {{"questions":[...]}} with exactly {count} questions.\n\nPASSAGES:\n{passages_text(topic, spans)}')
    good: List[Question] = []
    for _ in range(2):
        batch = llm.ask_json(prompt, QuestionList, system=llm.TEACHER_SYSTEM, max_tokens=5000).questions
        good = [q for q in batch if not question_problems(q)]
        if len(good) >= count:
            break
        prompt += "\nSome questions were invalid (options must be unique and every option needs an explanation). Try again."
    if not good:
        raise llm.LLMError("The teacher could not prepare questions this time. Please try again.")
    return [finalize(q, topic, f"{prefix}{i + 1}", rng) for i, q in enumerate(good[:count])]
