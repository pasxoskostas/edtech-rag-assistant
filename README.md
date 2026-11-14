# 🎓 EdTech RAG Assistant

A full-stack **Hybrid Retrieval-Augmented Generation (RAG)** application that generates grounded multiple-choice quizzes directly from course notes, complete with automated grading and explanations.

Designed to eliminate LLM hallucinations in educational settings, the system retrieves relevant context locally using vector search and enforces strict JSON schemas for quiz generation via Google Gemini.

---

## 🏗️ System Architecture

The application follows a decoupled client-server architecture with a hybrid local/cloud AI pipeline:

```text
[Course Notes (notes.txt)]
         │
         ▼  (ingest.py)
[Ollama: nomic-embed-text] ──► [ChromaDB Vector Store (./chroma_db)]
                                          │
                                          ▼  (1. Local Retrieval ~0.6s)
[Streamlit UI (app.py)] ◄───► [FastAPI Backend (main.py)]
                                          │
                                          ▼  (2. Cloud Generation ~2.4s)
                              [Google Gemini API + Pydantic Schema]
```

### Key Engineering Decisions

* **Hybrid RAG Pipeline (~3.0s end-to-end latency):** Embeddings and semantic search run locally via **Ollama (`nomic-embed-text`)** and **ChromaDB** in ~0.6s with zero API cost, while heavy generative inference is offloaded to **Google Gemini Flash** to avoid local CPU bottlenecks.
* **Strict Structured Outputs:** Uses **Pydantic (`QuizSet`, `QuizQuestion`)** passed directly into the Gemini `response_schema`, guaranteeing valid 4-option multiple-choice questions, answer indices, and explanations without fragile regex parsing.
* **High-Availability Model Fallback:** Implements an automatic fallback chain (`gemini-3.5-flash-lite` → `gemini-2.5-flash-lite` → `gemini-3.7-flash`) to gracefully handle transient `503`/`429` API demand spikes.
* **Stateful Interactive UI:** Built with **Streamlit** using `st.session_state` and `st.form` to persist generated quizzes across reruns and provide instant scoring with per-question feedback.

---

## 🛠️ Tech Stack

* **Language & Package Management:** Python 3.12, `uv`
* **Backend API:** FastAPI, Pydantic v2
* **Frontend UI:** Streamlit, Requests
* **Vector Database & Embeddings:** ChromaDB (persistent local storage), Ollama (`nomic-embed-text`)
* **LLM & SDK:** Google GenAI SDK (`google-genai`), `python-dotenv`

---

## 📂 Project Structure

```text
edtech-rag-assistant/
├── app.py              # Streamlit frontend (UI, session state, grading logic)
├── main.py             # FastAPI backend (RAG retrieval, Gemini generation, fallback)
├── ingest.py           # Offline ingestion script (chunking & ChromaDB indexing)
├── notes.txt           # Sample Computer Science (ΑΕΠΠ) course material
├── pyproject.toml      # Project dependencies and metadata
├── uv.lock             # Deterministic dependency lockfile
└── .gitignore          # Excludes .env, chroma_db/, .venv/, and __pycache__/
```

---

## 🚀 Getting Started

### Prerequisites

1. **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)** installed.
2. **[Ollama](https://ollama.com/)** installed locally with the embedding model pulled:
   ```bash
   ollama pull nomic-embed-text
   ```
3. A free API key from **[Google AI Studio](https://aistudio.google.com/)**.

### Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/pasxoskostas/edtech-rag-assistant.git](https://github.com/pasxoskostas/edtech-rag-assistant.git)
   cd edtech-rag-assistant
   ```

2. **Install dependencies:**
   ```bash
   uv sync
   ```

3. **Configure environment variables:**
   Create a `.env` file in the project root and add your Gemini API key:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```

4. **Index the course notes into ChromaDB:**
   ```bash
   uv run python ingest.py
   ```

### Running the Application

Open two terminals in the project directory:

* **Terminal 1 — Start the FastAPI Backend:**
  ```bash
  uv run fastapi dev main.py
  ```
  *(Interactive API docs available at `http://127.0.0.1:8000/docs`)*

* **Terminal 2 — Start the Streamlit Frontend:**
  ```bash
  uv run streamlit run app.py
  ```
  *(Web interface opens automatically at `http://localhost:8501`)*

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Health check confirming the RAG server is active. |
| `POST` | `/generate-quiz` | Accepts `{"topic": str, "num_questions": int}` and returns a validated `QuizSet` JSON object grounded in indexed notes. |

---

## 🗺️ Roadmap

- [x] **Phase 1:** FastAPI REST API & Pydantic data validation models
- [x] **Phase 2:** Local vector indexing with ChromaDB & Ollama embeddings
- [x] **Phase 3:** Hybrid Cloud LLM integration (Gemini API) with structured JSON outputs & model fallback
- [x] **Phase 4:** Full-stack Streamlit web interface with automated grading
- [ ] **Phase 5:** Dynamic PDF & TXT document upload via Streamlit sidebar with overlapping text chunking
- [ ] **Phase 6:** Source citations per question & quiz export
- [x] **Phase 7:** Quiz export (Markdown/JSON) & whole-document sampling