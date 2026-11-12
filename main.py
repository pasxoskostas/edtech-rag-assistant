import ollama
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="EdTech RAG Assistant API")


# --- Pydantic Models ---
class QuizQuestion(BaseModel):
    question: str = Field(description="Η εκφώνηση της ερώτησης στα ελληνικά")
    options: list[str] = Field(
        min_length=4, max_length=4, description="4 πιθανές απαντήσεις στα ελληνικά"
    )
    correct_index: int = Field(
        ge=0, le=3, description="Ο δείκτης (0-3) της σωστής απάντησης"
    )
    explanation: str = Field(
        description="Σύντομη αιτιολόγηση της σωστής απάντησης στα ελληνικά"
    )


class QuizSet(BaseModel):
    topic: str = Field(description="Το θέμα του διαγωνίσματος")
    questions: list[QuizQuestion] = Field(description="Η λίστα των ερωτήσεων")


class TopicRequest(BaseModel):
    topic: str = Field(min_length=3, description="Το θέμα του μαθήματος")
    num_questions: int = Field(default=2, ge=1, le=5)


# --- Endpoints ---
@app.get("/")
def home() -> dict[str, str]:
    return {"message": "Ο server του EdTech Assistant λειτουργεί!"}


@app.post("/generate-quiz", response_model=QuizSet)
def generate_quiz(request: TopicRequest) -> QuizSet:
    prompt = (
        f"Δημιούργησε ένα εκπαιδευτικό κουίζ στα ελληνικά με ακριβώς "
        f"{request.num_questions} ερωτήσεις πολλαπλής επιλογής για το θέμα: '{request.topic}'. "
        f"Κάθε ερώτηση πρέπει να έχει 4 επιλογές και μόνο μία σωστή."
    )

    try:
        # Καλούμε το τοπικό μοντέλο Ollama με αυστηρή δομή εξόδου (Structured Output)
        response = ollama.chat(
            model="qwen2.5:3b",
            messages=[
                {
                    "role": "system",
                    "content": "Είσαι έμπειρος καθηγητής Πληροφορικής. Απαντάς πάντα στα ελληνικά και σε αυστηρή μορφή JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            format=QuizSet.model_json_schema(),
            options={"temperature": 0.3},  # Χαμηλή "δημιουργικότητα" για πιο ακριβείς απαντήσεις
        )

        # Παίρνουμε το JSON κείμενο που επέστρεψε το AI και το επικυρώνουμε με το Pydantic
        raw_json = response.message.content
        return QuizSet.model_validate_json(raw_json)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Σφάλμα επικοινωνίας με το Ollama: {str(e)}",
        )