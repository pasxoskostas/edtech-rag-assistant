import io
import os
import random
import time

import chromadb
import ollama
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel, Field
from pypdf import PdfReader

load_dotenv()

app = FastAPI(title="EdTech RAG Assistant API")

chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="edtech_notes")
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

FALLBACK_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-3.7-flash",
]


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    clean_text = " ".join(text.split())
    if not clean_text:
        return []

    chunks = []
    step = chunk_size - overlap
    for start in range(0, len(clean_text), step):
        chunk = clean_text[start : start + chunk_size]
        chunks.append(chunk)
        if start + chunk_size >= len(clean_text):
            break
    return chunks


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
    topic: str = Field(description="Ο τίτλος ή το γενικό θέμα του διαγωνίσματος")
    questions: list[QuizQuestion] = Field(description="Η λίστα των ερωτήσεων")
    sources: list[str] = Field(
        default_factory=list,
        description="Τα αρχεία από τα οποία αντλήθηκαν οι πληροφορίες",
    )


class TopicRequest(BaseModel):
    topic: str = Field(
        default="",
        description="Προαιρετικό θέμα. Αν είναι κενό, επιλέγεται ύλη από όλο το αρχείο.",
    )
    num_questions: int = Field(default=5, ge=1, le=20)
    source_filter: str | None = Field(
        default=None, description="Προαιρετικό φιλτράρισμα βάσει ονόματος αρχείου"
    )


class ExplainRequest(BaseModel):
    question: str = Field(description="Η εκφώνηση της ερώτησης")
    user_answer: str = Field(description="Η απάντηση που επέλεξε ο μαθητής")
    correct_answer: str = Field(description="Η σωστή απάντηση")
    source_filter: str | None = Field(
        default=None, description="Η πηγή ύλης από την οποία προήλθε το κουίζ"
    )


class ExplainResponse(BaseModel):
    explanation: str = Field(
        description="Αναλυτική παιδαγωγική επεξήγηση στα ελληνικά βάσει του κειμένου"
    )
    sources: list[str] = Field(
        default_factory=list,
        description="Τα αρχεία που χρησιμοποιήθηκαν για την επεξήγηση",
    )


# --- Endpoints ---
@app.get("/")
def home() -> dict[str, str]:
    return {"message": "Ο RAG server του EdTech Assistant λειτουργεί!"}


@app.get("/documents")
def list_documents() -> dict[str, list[str]]:
    data = collection.get(include=["metadatas"])
    metadatas = data.get("metadatas") or []
    sources = {
        meta["source"]
        for meta in metadatas
        if isinstance(meta, dict) and "source" in meta
    }
    return {"documents": sorted(sources)}


@app.post("/upload-document")
def upload_document(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Δεν δόθηκε όνομα αρχείου.")

    filename_lower = file.filename.lower()
    if not (filename_lower.endswith(".pdf") or filename_lower.endswith(".txt")):
        raise HTTPException(
            status_code=400,
            detail="Υποστηρίζονται μόνο αρχεία .pdf και .txt.",
        )

    try:
        t0 = time.perf_counter()
        raw_bytes = file.file.read()
        print(
            f"[INGEST 1/3] Ανάγνωση '{file.filename}' ({len(raw_bytes) / 1024:.1f} KB)...",
            flush=True,
        )

        if filename_lower.endswith(".txt"):
            extracted_text = raw_bytes.decode("utf-8")
        else:
            reader = PdfReader(io.BytesIO(raw_bytes))
            pages_text = [page.extract_text() or "" for page in reader.pages]
            extracted_text = "\n".join(pages_text)
            print(
                f"[INGEST 1/3] Εξήχθη κείμενο από {len(reader.pages)} σελίδες.",
                flush=True,
            )

        chunks = chunk_text(extracted_text, chunk_size=800, overlap=150)
        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="Δεν βρέθηκε αναγνώσιμο κείμενο στο αρχείο (μήπως είναι σκαναρισμένη εικόνα;).",
            )

        print(
            f"[INGEST 2/3] Δημιουργήθηκαν {len(chunks)} chunks. Εκκίνηση embeddings...",
            flush=True,
        )

        embeddings = []
        batch_size = 10
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            batch_response = ollama.embed(model="nomic-embed-text", input=batch)
            embeddings.extend(batch_response.embeddings)
            done = min(i + batch_size, len(chunks))
            print(
                f"   -> Embeddings: {done}/{len(chunks)} chunks ({time.perf_counter() - t0:.2f}s)",
                flush=True,
            )

        ids = [f"{file.filename}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {"source": file.filename, "chunk_index": i} for i in range(len(chunks))
        ]

        collection.upsert(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        elapsed = time.perf_counter() - t0
        print(
            f"[INGEST 3/3] Ολοκληρώθηκε το '{file.filename}' ({len(chunks)} chunks) σε {elapsed:.2f}s",
            flush=True,
        )

        return {
            "filename": file.filename,
            "chunks_added": len(chunks),
            "total_chunks_in_db": collection.count(),
        }

    except HTTPException:
        raise
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Το αρχείο .txt πρέπει να είναι αποθηκευμένο σε κωδικοποίηση UTF-8.",
        )
    except Exception as e:
        print(f"[INGEST ERROR] {e}", flush=True)
        raise HTTPException(
            status_code=500,
            detail=f"Σφάλμα κατά την επεξεργασία του αρχείου: {str(e)}",
        )


@app.post("/generate-quiz", response_model=QuizSet)
def generate_quiz(request: TopicRequest) -> QuizSet:
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(
            status_code=500, detail="Λείπει το GEMINI_API_KEY από το αρχείο .env."
        )

    try:
        t0 = time.perf_counter()
        clean_topic = request.topic.strip()

        where_clause = (
            {"source": request.source_filter}
            if request.source_filter and request.source_filter != "Όλα τα αρχεία"
            else None
        )

        if clean_topic:
            query_embedding = ollama.embed(
                model="nomic-embed-text", input=clean_topic
            ).embeddings[0]
            print(f"[1/3] Embedding έτοιμο σε {time.perf_counter() - t0:.2f}s", flush=True)

            dynamic_k = min(max(4, request.num_questions), max(1, collection.count()))
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=dynamic_k,
                where=where_clause,
            )
            retrieved_docs = results["documents"][0] if results["documents"] else []
            retrieved_metas = results["metadatas"][0] if results["metadatas"] else []
        else:
            print("[1/3] Λειτουργία ολόκληρου εγγράφου (Whole-Document Mode)", flush=True)
            all_data = collection.get(
                where=where_clause, include=["documents", "metadatas"]
            )
            all_docs = all_data.get("documents") or []
            all_metas = all_data.get("metadatas") or []

            paired = list(zip(all_docs, all_metas))
            paired.sort(
                key=lambda x: x[1].get("chunk_index", 0)
                if isinstance(x[1], dict)
                else 0
            )

            sample_size = min(len(paired), max(8, request.num_questions * 2), 20)
            if len(paired) > sample_size:
                indices = sorted(random.sample(range(len(paired)), sample_size))
                sampled = [paired[i] for i in indices]
            else:
                sampled = paired

            retrieved_docs = [item[0] for item in sampled]
            retrieved_metas = [item[1] for item in sampled]

        if not retrieved_docs:
            raise HTTPException(
                status_code=404, detail="Δεν βρέθηκαν σχετικές σημειώσεις στη βάση."
            )

        used_sources = sorted(
            {
                meta["source"]
                if isinstance(meta, dict) and "source" in meta
                else "notes.txt (αρχικές σημειώσεις)"
                for meta in retrieved_metas
            }
        )
        context = "\n\n".join(retrieved_docs)
        print(
            f"[2/3] Ανακτήθηκαν {len(retrieved_docs)} chunks σε {time.perf_counter() - t0:.2f}s | Πηγές: {used_sources}",
            flush=True,
        )

        topic_instruction = (
            f"για το θέμα '{clean_topic}'"
            if clean_topic
            else "που να καλύπτουν ισομερώς όλο το εύρος των πληροφοριών του παραπάνω κειμένου (και όρισε έναν αντιπροσωπευτικό τίτλο στο πεδίο topic)"
        )

        prompt = (
            f"Διάβασε προσεκτικά το παρακάτω εκπαιδευτικό κείμενο:\n"
            f"--- ΑΡΧΗ ΚΕΙΜΕΝΟΥ ---\n{context}\n--- ΤΕΛΟΣ ΚΕΙΜΕΝΟΥ ---\n\n"
            f"Βασιζόμενος ΑΠΟΚΛΕΙΣΤΙΚΑ και ΜΟΝΟ στις πληροφορίες του παραπάνω κειμένου, "
            f"δημιούργησε {request.num_questions} διαφορετικές ερωτήσεις πολλαπλής επιλογής στα ελληνικά "
            f"{topic_instruction}, χωρίς επαναλήψεις."
        )

        last_error = None
        for model_name in FALLBACK_MODELS:
            try:
                print(f"[3/3] Αποστολή στο {model_name}...", flush=True)
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction="Είσαι αυστηρός καθηγητής. Φτιάχνεις ερωτήσεις αποκλειστικά από το κείμενο που σου δίνεται, στα ελληνικά.",
                        response_mime_type="application/json",
                        response_schema=QuizSet,
                        temperature=0.3 if not clean_topic else 0.2,
                    ),
                )
                print(
                    f"[OK] Απάντησε το {model_name} σε {time.perf_counter() - t0:.2f}s",
                    flush=True,
                )
                quiz = QuizSet.model_validate_json(response.text)
                quiz.sources = used_sources
                return quiz

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


@app.post("/explain-mistake", response_model=ExplainResponse)
def explain_mistake(request: ExplainRequest) -> ExplainResponse:
    if not os.getenv("GEMINI_API_KEY"):
        raise HTTPException(
            status_code=500, detail="Λείπει το GEMINI_API_KEY από το αρχείο .env."
        )

    try:
        t0 = time.perf_counter()
        search_query = f"{request.question} {request.user_answer} {request.correct_answer}"

        query_embedding = ollama.embed(
            model="nomic-embed-text", input=search_query
        ).embeddings[0]

        where_clause = (
            {"source": request.source_filter}
            if request.source_filter and request.source_filter != "Όλα τα αρχεία"
            else None
        )
        n_docs = min(3, max(1, collection.count()))

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_docs,
            where=where_clause,
        )

        retrieved_docs = results["documents"][0] if results["documents"] else []
        retrieved_metas = results["metadatas"][0] if results["metadatas"] else []

        if not retrieved_docs:
            raise HTTPException(
                status_code=404, detail="Δεν βρέθηκαν σχετικά αποσπάσματα στη βάση."
            )

        used_sources = sorted(
            {
                meta["source"]
                if isinstance(meta, dict) and "source" in meta
                else "notes.txt (αρχικές σημειώσεις)"
                for meta in retrieved_metas
            }
        )
        context = "\n\n".join(retrieved_docs)

        prompt = (
            f"Διάβασε τα παρακάτω αποσπάσματα από τις σημειώσεις του μαθήματος:\n"
            f"--- ΑΡΧΗ ΣΗΜΕΙΩΣΕΩΝ ---\n{context}\n--- ΤΕΛΟΣ ΣΗΜΕΙΩΣΕΩΝ ---\n\n"
            f"Ένας μαθητής απάντησε στην παρακάτω ερώτηση:\n"
            f"• Ερώτηση: {request.question}\n"
            f"• Επιλογή μαθητή: {request.user_answer}\n"
            f"• Σωστή απάντηση: {request.correct_answer}\n\n"
            f"Ως υποστηρικτικός καθηγητής, εξήγησε αναλυτικά και κατανοητά στα ελληνικά:\n"
            f"1. Γιατί η επιλογή του μαθητή είναι λανθασμένη (ή ελλιπής) με βάση τις σημειώσεις.\n"
            f"2. Γιατί ισχύει η σωστή απάντηση, παραθέτοντας το σχετικό σημείο της ύλης."
        )

        last_error = None
        for model_name in FALLBACK_MODELS:
            try:
                print(f"[TUTOR] Αποστολή στο {model_name}...", flush=True)
                response = gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction="Είσαι υποστηρικτικός, σαφής καθηγητής. Εξηγείς λάθη μαθητών αποκλειστικά βάσει των σημειώσεων που σου δίνονται, στα ελληνικά.",
                        response_mime_type="application/json",
                        response_schema=ExplainResponse,
                        temperature=0.3,
                    ),
                )
                print(
                    f"[TUTOR OK] Απάντησε το {model_name} σε {time.perf_counter() - t0:.2f}s",
                    flush=True,
                )
                result = ExplainResponse.model_validate_json(response.text)
                result.sources = used_sources
                return result

            except APIError as e:
                last_error = e
                continue

        raise HTTPException(
            status_code=503,
            detail=f"Όλα τα μοντέλα είναι προσωρινά μη διαθέσιμα: {last_error}",
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[TUTOR ERROR] {e}", flush=True)
        raise HTTPException(
            status_code=500,
            detail=f"Σφάλμα κατά την ανάλυση του AI Tutor: {str(e)}",
        )