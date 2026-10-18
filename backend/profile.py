"""Stage 3: first meeting questions and the student profile."""
from typing import List, Tuple

from backend import llm
from backend.schemas import StudentProfile

QUESTIONS = [
    {"key": "name", "text": "What should I call you?"},
    {"key": "short_term_goal", "text": "What would you like to achieve in the next few weeks?"},
    {"key": "long_term_goal", "text": "And what is your bigger goal, further ahead?"},
    {"key": "level", "text": "How would you describe your level with this subject: beginner, some knowledge, or advanced?"},
    {"key": "prior_knowledge", "text": "What do you already know about it?"},
    {"key": "daily_minutes", "text": "How many minutes a day can you study?"},
    {"key": "learning_styles", "text": "How do you like to learn? (for example: examples, stories, practice questions)"},
    {"key": "interests", "text": "What are your interests and hobbies?"},
]


def opening_message(question: str, course_title: str = "") -> str:
    about = f" We will learn about {course_title} together." if course_title else ""
    return f"Hello, and welcome! I'm your teacher.{about} I'd like to know you a little first. {question}"


def teacher_message(question: str, last_answer: str, mode: str, course_title: str = "") -> str:
    """Chat mode: a short friendly reaction plus the next question. Quick mode: just the question."""
    if mode == "quick":
        return question
    try:
        return llm.ask(
            f"The student just told me: \"{last_answer}\". Write ONE short, warm reaction (a few words), then ask exactly: "
            f"\"{question}\". Two sentences at most.", system=llm.TEACHER_SYSTEM, temperature=0.7, max_tokens=150)
    except llm.LLMError:
        return f"Thank you! {question}"


def build_profile(student_id: str, conversation: List[Tuple[str, str]], correction: str = "") -> StudentProfile:
    answers = "\n".join(f"- {k}: {v}" for k, v in conversation)
    prompt = (
        "Turn the student's answers into a profile.\n"
        'Keys: {"student_id":"STUDENT_ID","name":"","short_term_goal":"","long_term_goal":"",'
        '"level":"beginner|intermediate|advanced","prior_knowledge":"","daily_minutes":30,'
        '"learning_styles":["..."],"interests":["..."],"notes":""}\n'
        "Rules: level mapping: beginner = knows little, intermediate = some knowledge, advanced = advanced. "
        "daily_minutes is a whole number from 5 to 240 (use 30 if unclear; 'half an hour' = 30, '1 hour' = 60). "
        "Do not invent facts; use empty text or an empty list if the student did not say.\n\n"
        f"ANSWERS:\n{answers}").replace("STUDENT_ID", student_id)
    if correction:
        prompt += f"\n\nPlease fix this: {correction}"
    profile = llm.ask_json(prompt, StudentProfile, max_tokens=800)
    return profile.model_copy(update={"student_id": student_id})
