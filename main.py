import chromadb
import ollama
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="EdTech RAG Assistant API")

# Σύνδεση με την τοπική βάση ChromaDB που δημιουργήθηκε από το ingest.py
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="edtech_notes")


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
        description="Σύντομη αιτιολόγηση της σωστής απάντησης βάσει του κειμένου"
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
    return {"message": "Ο RAG server του EdTech Assistant λειτουργεί!"}


@app.post("/generate-quiz", response_model=QuizSet)
def generate_quiz(request: TopicRequest) -> QuizSet:
    try:
        # 1. RETRIEVAL: Μετατρέπουμε το θέμα αναζήτησης σε διάνυσμα και ψάχνουμε στη βάση
        query_embedding = ollama.embed(
            model="nomic-embed-text", input=request.topic
        ).embeddings[0]

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=1,  # Φέρνουμε τα 2 πιο σχετικά αποσπάσματα από τις σημειώσεις
        )

        retrieved_docs = results["documents"][0] if results["documents"] else []
        if not retrieved_docs:
            raise HTTPException(
                status_code=404, detail="Δεν βρέθηκαν σχετικές σημειώσεις στη βάση."
            )

        context = "\n\n".join(retrieved_docs)

        # 2. AUGMENTED GENERATION: Δίνουμε στο LLM ΑΠΟΚΛΕΙΣΤΙΚΑ το κείμενο που βρέθηκε
        prompt = (
            f"Διάβασε προσεκτικά το παρακάτω εκπαιδευτικό κείμενο:\n"
            f"--- ΑΡΧΗ ΚΕΙΜΕΝΟΥ ---\n{context}\n--- ΤΕΛΟΣ ΚΕΙΜΕΝΟΥ ---\n\n"
            f"Βασιζόμενος ΑΠΟΚΛΕΙΣΤΙΚΑ και ΜΟΝΟ στις πληροφορίες του παραπάνω κειμένου, "
            f"δημιούργησε {request.num_questions} ερωτήσεις πολλαπλής επιλογής στα ελληνικά "
            f"για το θέμα '{request.topic}'. Μην χρησιμοποιήσεις εξωτερικές γνώσεις."
        )

        response = ollama.chat(
            model="qwen2.5:3b",
            messages=[
                {
                    "role": "system",
                    "content": "Είσαι αυστηρός καθηγητής Πληροφορικής. Φτιάχνεις ερωτήσεις αποκλειστικά από το κείμενο που σου δίνεται, στα ελληνικά και σε μορφή JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            format=QuizSet.model_json_schema(),
            options={"temperature": 0.2},
            keep_alive="10m"
        )

        return QuizSet.model_validate_json(response.message.content)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Σφάλμα κατά την παραγωγή του κουίζ: {str(e)}",
        )