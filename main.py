import os
import time

import chromadb
import ollama
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel, Field

load_dotenv()

app = FastAPI(title="EdTech RAG Assistant API")

chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="edtech_notes")
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Λίστα προτεραιότητας μοντέλων (Model Fallback για υψηλή διαθεσιμότητα)
FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-3.7-flash",
]


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


@app.get("/")
def home() -> dict[str, str]:
    return {"message": "Ο RAG server του EdTech Assistant λειτουργεί!"}


@app.post("/generate-quiz", response_model=QuizSet)
def generate_quiz(request: TopicRequest) -> QuizSet:
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(
            status_code=500, detail="Λείπει το GEMINI_API_KEY από το αρχείο .env."
        )

    try:
        t0 = time.perf_counter()

        # 1. Τοπικό Embedding
        query_embedding = ollama.embed(
            model="nomic-embed-text", input=request.topic
        ).embeddings[0]
        print(f"[1/3] Embedding έτοιμο σε {time.perf_counter() - t0:.2f}s", flush=True)

        # 2. Αναζήτηση στη ChromaDB
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=2,
        )
        print(f"[2/3] ChromaDB αναζήτηση σε {time.perf_counter() - t0:.2f}s", flush=True)

        retrieved_docs = results["documents"][0] if results["documents"] else []
        if not retrieved_docs:
            raise HTTPException(
                status_code=404, detail="Δεν βρέθηκαν σχετικές σημειώσεις στη βάση."
            )

        context = "\n\n".join(retrieved_docs)

        # 3. Παραγωγή κουίζ με αυτόματο Fallback
        prompt = (
            f"Διάβασε προσεκτικά το παρακάτω εκπαιδευτικό κείμενο:\n"
            f"--- ΑΡΧΗ ΚΕΙΜΕΝΟΥ ---\n{context}\n--- ΤΕΛΟΣ ΚΕΙΜΕΝΟΥ ---\n\n"
            f"Βασιζόμενος ΑΠΟΚΛΕΙΣΤΙΚΑ και ΜΟΝΟ στις πληροφορίες του παραπάνω κειμένου, "
            f"δημιούργησε {request.num_questions} ερωτήσεις πολλαπλής επιλογής στα ελληνικά "
            f"για το θέμα '{request.topic}'."
        )

        last_error = None
        for model_name in FALLBACK_MODELS:
            try:
                print(f"[3/3] Αποστολή στο {model_name}...", flush=True)
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction="Είσαι αυστηρός καθηγητής Πληροφορικής. Φτιάχνεις ερωτήσεις αποκλειστικά από το κείμενο που σου δίνεται, στα ελληνικά.",
                        response_mime_type="application/json",
                        response_schema=QuizSet,
                        temperature=0.2,
                    ),
                )
                print(
                    f"[OK] Απάντησε το {model_name} σε {time.perf_counter() - t0:.2f}s",
                    flush=True,
                )
                return QuizSet.model_validate_json(response.text)

            except APIError as e:
                last_error = e
                print(
                    f"[WARN] Το {model_name} απέτυχε (HTTP {e.code}), δοκιμή επόμενου...",
                    flush=True,
                )
                continue

        raise HTTPException(
            status_code=503,
            detail=f"Όλα τα μοντέλα είναι προσωρινά μη διαθέσιμα: {last_error}",
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] {e}", flush=True)
        raise HTTPException(
            status_code=500,
            detail=f"Σφάλμα κατά την παραγωγή του κουίζ: {str(e)}",
        )