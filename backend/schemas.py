"""All Pydantic models. Names follow the spec; a few optional fields were added."""
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

Level = Literal["beginner", "intermediate", "advanced"]


class Span(BaseModel):
    id: str
    page: int
    text: str


class Topic(BaseModel):
    id: str
    title: str
    summary: str
    prerequisites: List[str] = []
    source_spans: List[str]
    difficulty: Level


class Course(BaseModel):
    course_id: str
    course_title: str
    topics: List[Topic]


class StudentProfile(BaseModel):
    student_id: str
    name: str = "Student"
    short_term_goal: str
    long_term_goal: str
    level: Level
    prior_knowledge: str
    daily_minutes: int = Field(ge=5, le=240)
    learning_styles: List[str]
    interests: List[str]
    notes: str = ""


class Question(BaseModel):
    id: str
    topic_id: str
    text: str
    options: List[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    option_explanations: List[str] = Field(min_length=4, max_length=4)
    kind: Literal["recall", "explain", "apply", "compare", "choose_and_justify"]
    hint: str = ""
    source_spans: List[str] = []
    objective_index: Optional[int] = None      # added: which lesson objective a quiz question covers


class PreTest(BaseModel):
    course_id: str
    chosen_topic_ids: List[str]
    questions: List[Question]
    prerequisite_question_ids: List[str] = []


class PreTestAnswer(BaseModel):
    question_id: str
    chosen_index: Optional[int] = None
    confidence: Literal["sure", "unsure", "guessing"] = "unsure"


PlacementState = Literal["skip_with_check", "short_path", "full_lesson", "bridge_first", "misconception_lesson"]


class TopicPlacement(BaseModel):                 # added: result of scoring one topic
    topic_id: str
    state: PlacementState
    reason: str
    bridge_topic_ids: List[str] = []
    correct: int = 0
    total: int = 0


class PathItem(BaseModel):
    order: int
    topic_id: str
    state: PlacementState
    reason: str
    minutes: int


class LearningPath(BaseModel):
    student_id: str
    course_id: str
    items: List[PathItem]


class Lesson(BaseModel):
    topic_id: str
    variant: Literal["full", "short", "misconception", "bridge"]
    hook: str
    objectives: List[str]
    warmup: List[Question]
    explanation: List[str]
    worked_example: str
    extra_worked_example: str
    practice: List[Question]
    quiz: List[Question]
    quiz_variants: List[Question]
    summary: str
    transfer_question: Question
    source_spans: List[str]


class ReviewResult(BaseModel):
    topic_id: str
    structural_ok: bool
    structural_problems: List[str] = []
    scores: Dict[str, int] = {}
    issues: List[str] = []
    decision: Literal["pass", "revise", "person_review"]
    attempt: int = 0


class DailyTarget(BaseModel):
    day_index: int
    topic_id: str
    minutes: int
    description: str
    status: Literal["pending", "completed", "not_completed"] = "pending"


class Attempt(BaseModel):
    topic_id: str
    attempt_no: int
    passed: bool
    wrong_question_ids: List[str] = []
    chosen_wrong_options: Dict[str, int] = {}
    seconds_taken: int = 0
    asked_question_ids: List[str] = []           # added: so retries never repeat questions


class SupportAction(BaseModel):                  # added: what to do after a "not yet"
    kind: Literal["hint_retry", "switch_route", "bridge_and_alert", "to_person"]
    message: str
    cause: str = ""
    use_extra_example: bool = False
    bridge_topic_id: Optional[str] = None
    alert: bool = False


class TeacherAlert(BaseModel):
    student_id: str
    topic_id: str
    reason: str
    likely_cause: str
    tried: List[str]
    created_day: int
    resolved: bool = False
