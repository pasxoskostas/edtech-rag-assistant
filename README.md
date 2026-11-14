# 🎓 EdTech RAG Assistant

A full-stack **Hybrid Retrieval-Augmented Generation (RAG)** application that transforms PDF and TXT course materials into grounded multiple-choice exams (up to 20 questions), complete with automated grading, an interactive **AI Tutor** for mistake remediation, and Markdown/JSON export.

Designed to eliminate LLM hallucinations in educational settings, the system retrieves relevant context locally using vector search and enforces strict Pydantic JSON schemas via Google Gemini.

---

## 🏗️ System Architecture

The application follows a decoupled client-server architecture combining local vector search with structured cloud LLM generation:

```text
[PDF / TXT Course Material]
         │
         ▼  (POST /upload-document — Overlapping Chunking)
[Ollama: nomic-embed-text] ──► [ChromaDB Vector Store (./chroma_db)]
                                          │
                                          ▼  (1. Local Retrieval / Whole-Doc Sampling)
[Streamlit UI (app.py)] ◄───► [FastAPI Backend (main.py)]
         │                                │
         ├──► [POST /generate-quiz] ──────┼──► [Google Gemini API + Pydantic Schema]
         └──► [POST /explain-mistake] ────┘
```

### Key Engineering Decisions

* **Hybrid Local/Cloud RAG Pipeline:** Embeddings and semantic search run locally via **Ollama (`nomic-embed-text`)** and **ChromaDB** with zero embedding API cost, while structured JSON generation is offloaded to **Google Gemini Flash** to avoid local CPU bottlenecks.
* **Dual-Mode Retrieval:** Supports targeted semantic vector search with dynamic `n_results` scaling when a specific topic is provided, as well as stratified whole-document chunk sampling when generating comprehensive exams across an entire PDF.
* **Strict Structured Outputs & Model Fallback:** Enforces Pydantic schemas (`QuizSet`, `ExplainResponse`) directly in Gemini's `response_schema` with an automatic fallback chain (`gemini-3.5-flash-lite` → `gemini-2.5-flash-lite` → `gemini-3.7-flash`) to handle transient API demand spikes.
* **Multi-Step AI Tutor Remediation:** Performs targeted re-retrieval using the question, the student's selected answer, and the correct answer to generate grounded, step-by-step pedagogical explanations.
* **Full Vector Store CRUD:** Supports dynamic PDF/TXT ingestion with overlapping chunks (`800` chars, `150` overlap), mini-batch embeddings, metadata source filtering, source citations per quiz, and per-document deletion.

---

## 🛠️ Tech Stack

* **Language & Package Management:** Python 3.12, `uv`
* **Backend API:** FastAPI, Pydantic v2, `python-multipart`
* **Frontend UI:** Streamlit (`st.session_state`, `st.form`, `st.download_button`)
* **Document Processing & Vector DB:** `pypdf`, ChromaDB (persistent local storage), Ollama (`nomic-embed-text`)
* **LLM & SDK:** Google GenAI SDK (`google-genai`), `python-dotenv`

---

## 📂 Project Structure

```text
edtech-rag-assistant/
├── app.py              # Streamlit UI (upload/delete docs, quiz form, AI Tutor, export)
├── main.py             # FastAPI backend (RAG retrieval, Gemini generation, fallback)
├── ingest.py           # Offline CLI ingestion script for initial notes
├── notes.txt           # Sample Computer Science (ΑΕΠΠ) course material
├── pyproject.toml      # Project dependencies and metadata
├── uv.lock             # Deterministic dependency lockfile
├── README.md           # Project architecture and setup documentation
└── .gitignore          # Excludes .env, chroma_db/, .venv/, and __pycache__/
```

---

## 🚀 Getting Started

### Prerequisites

1. **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)** installed.
2. **[Ollama](https://ollama.com/)** running locally with the embedding model pulled:
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

4. *(Optional)* **Index the sample course notes into ChromaDB:**
   ```bash
   uv run python ingest.py
   ```
   *(You can also upload any `.pdf` or `.txt` document directly from the Streamlit sidebar.)*

### Running the Application

Open two terminals in the project directory:

* **Terminal 1 — Start the FastAPI Backend:**
  ```bash
  uv run fastapi dev main.py
  ```
  *(Interactive Swagger API docs available at `http://127.0.0.1:8000/docs`)*

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
| `GET` | `/documents` | Lists all unique