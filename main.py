from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="EdTech RAG Assistant API")


# --- Pydantic Models ---
class QuizQuestion(BaseModel):
    question: str = Field(description="Η εκφώνηση της ερώτησης")
    options: list[str] = Field(min_length=4, max_length=4)
    correct_index: int = Field(ge=0, le=3)
    explanation: str


class QuizSet(BaseModel):
    topic: str
    questions: list[QuizQuestion]


# Νέο μοντέλο για τα δεδομένα που στέλνει ο χρήστης (Request)
class TopicRequest(BaseModel):
    topic: str = Field(min_length=3, description="Το θέμα του μαθήματος")
    num_questions: int = Field(default=2, ge=1, le=5)


# --- Endpoints ---
@app.get("/")
def home() -> dict[str, str]:
    return {"message": "Ο server του EdTech Assistant λειτουργεί!"}


@app.get("/sample-quiz", response_model=QuizSet)
def get_sample_quiz() -> QuizSet:
    return QuizSet(
        topic="Αλγόριθμοι",
        questions=[
            QuizQuestion(
                question="Ποια δομή δεδομένων ακολουθεί την αρχή LIFO;",
                options=["Ουρά", "Στοίβα", "Δέντρο", "Γράφος"],
                correct_index=1,
                explanation="Last-In, First-Out (Τελευταίο μέσα, πρώτο έξω).",
            )
        ],
    )


# Νέο POST endpoint: δέχεται TopicRequest και επιστρέφει QuizSet
@app.post("/generate-quiz", response_model=QuizSet)
def generate_quiz(request: TopicRequest) -> QuizSet:
    # Προσωρινές ερωτήσεις (στην 3η εβδομάδα εδώ θα μπει το Ollama/AI)
    questions = [
        QuizQuestion(
            question=f"Ερώτηση {i + 1} για το θέμα: {request.topic}",
            options=["Επιλογή Α", "Επιλογή Β", "Επιλογή Γ", "Επιλογή Δ"],
            correct_index=0,
            explanation="Προσωρινή αιτιολόγηση.",
        )
        for i in range(request.num_questions)
    ]
    return QuizSet(topic=request.topic, questions=questions)