import json
import requests
import streamlit as st

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="EdTech RAG Assistant",
    page_icon="🎓",
    initial_sidebar_state="expanded",
)


def build_quiz_markdown(quiz: dict) -> str:
    option_letters = ["Α", "Β", "Γ", "Δ"]
    lines = [f"# 📝 Διαγώνισμα: {quiz['topic']}\n"]

    if quiz.get("sources"):
        lines.append(f"**Πηγές ύλης:** {', '.join(quiz['sources'])}\n")

    lines.append("---\n\n## Μέρος Α: Ερωτήσεις\n")
    for i, q in enumerate(quiz["questions"], start=1):
        lines.append(f"### {i}. {q['question']}")
        for idx, opt in enumerate(q["options"]):
            letter = option_letters[idx] if idx < len(option_letters) else str(idx + 1)
            lines.append(f"- **{letter}.** {opt}")
        lines.append("")

    lines.append("---\n\n## Μέρος Β: Απαντήσεις & Αιτιολόγηση\n")
    for i, q in enumerate(quiz["questions"], start=1):
        correct_idx = q["correct_index"]
        letter = (
            option_letters[correct_idx]
            if correct_idx < len(option_letters)
            else str(correct_idx + 1)
        )
        correct_text = q["options"][correct_idx]
        lines.append(f"**{i}. Σωστή απάντηση: {letter} ({correct_text})**")
        lines.append(f"> 💡 *{q['explanation']}*\n")

    return "\n".join(lines)


if "quiz_data" not in st.session_state:
    st.session_state["quiz_data"] = None
if "selected_source" not in st.session_state:
    st.session_state["selected_source"] = "Όλα τα αρχεία"

# --- Πλαϊνή Μπάρα: Ανέβασμα Νέας Ύλης ---
with st.sidebar:
    st.header("📚 Υλικό Μαθήματος")
    st.write("Ανέβασε σημειώσεις (PDF ή TXT) για να εμπλουτίσεις τη βάση γνώσης.")

    uploaded_file = st.file_uploader(
        "Επίλεξε αρχείο:",
        type=["pdf", "txt"],
    )

    if uploaded_file is not None:
        if st.button("Αποθήκευση στη Βάση"):
            with st.spinner(f"Επεξεργασία '{uploaded_file.name}'..."):
                try:
                    files = {
                        "file": (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            uploaded_file.type,
                        )
                    }
                    res = requests.post(
                        f"{API_BASE}/upload-document",
                        files=files,
                        timeout=180,
                    )
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state["selected_source"] = data["filename"]
                        st.success(
                            f"Το αρχείο **{data['filename']}** αποθηκεύτηκε!\n\n"
                            f"• Νέα κομμάτια (chunks): **{data['chunks_added']}**\n"
                            f"• Σύνολο στη βάση: **{data['total_chunks_in_db']}**"
                        )
                    else:
                        st.error(f"Σφάλμα ({res.status_code}): {res.text}")
                except requests.exceptions.ConnectionError:
                    st.error("Δεν βρέθηκε ενεργός FastAPI server.")
                except requests.exceptions.ReadTimeout:
                    st.error("Η επεξεργασία άργησε (Timeout 180s).")

# --- Ανάκτηση διαθέσιμων αρχείων από το Backend ---
available_docs = ["Όλα τα αρχεία"]
try:
    docs_res = requests.get(f"{API_BASE}/documents", timeout=5)
    if docs_res.status_code == 200:
        available_docs.extend(docs_res.json().get("documents", []))
except Exception:
    pass

default_index = (
    available_docs.index(st.session_state["selected_source"])
    if st.session_state["selected_source"] in available_docs
    else 0
)

# --- Κύρια Σελίδα: Παραγωγή Κουίζ ---
st.title("🎓 EdTech AI Quiz Generator")
st.write("Παραγωγή διαδραστικού κουίζ αποκλειστικά από τις σημειώσεις του μαθήματος.")

selected_source = st.selectbox(
    "📂 Πηγή ύλης:",
    options=available_docs,
    index=default_index,
)
st.session_state["selected_source"] = selected_source

topic = st.text_input(
    "Εστίαση σε συγκεκριμένο θέμα (προαιρετικό):",
    placeholder="Αφήστε το κενό για ερωτήσεις από ολόκληρο το αρχείο...",
)
num_questions = st.slider("Αριθμός ερωτήσεων:", min_value=1, max_value=20, value=5)

if st.button("Δημιουργία Κουίζ"):
    with st.spinner("Ανάλυση ύλης και παραγωγή κουίζ..."):
        try:
            response = requests.post(
                f"{API_BASE}/generate-quiz",
                json={
                    "topic": topic.strip(),
                    "num_questions": num_questions,
                    "source_filter": selected_source,
                },
                timeout=90,
            )
            if response.status_code == 200:
                st.session_state["quiz_data"] = response.json()
                for key in list(st.session_state.keys()):
                    if key.startswith("q_"):
                        del st.session_state[key]
            else:
                st.error(f"Σφάλμα ({response.status_code}): {response.text}")
        except requests.exceptions.ConnectionError:
            st.error("Δεν βρέθηκε ενεργός FastAPI server. Βεβαιώσου ότι τρέχει το main.py!")
        except requests.exceptions.ReadTimeout:
            st.error("Ο server άργησε να απαντήσει (Timeout 90s). Έλεγξε το terminal του FastAPI.")

quiz = st.session_state["quiz_data"]

if quiz:
    st.divider()
    st.subheader(f"📝 Κουίζ: {quiz['topic']}")
    if quiz.get("sources"):
        st.caption(f"📌 Πηγές: {', '.join(quiz['sources'])}")

    with st.form("quiz_form"):
        user_answers = []
        for i, q in enumerate(quiz["questions"]):
            choice = st.radio(
                label=f"**{i + 1}. {q['question']}**",
                options=q["options"],
                index=None,
                key=f"q_{i}",
            )
            user_answers.append(choice)
            st.write("")

        submitted = st.form_submit_button("Υποβολή Απαντήσεων")

    # --- Κουμπιά Εξαγωγής Αρχείου (εκτός φόρμας) ---
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="📥 Λήψη Διαγωνίσματος & Λύσεων (.md)",
            data=build_quiz_markdown(quiz),
            file_name="edtech_quiz.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            label="📦 Λήψη Δομημένων Δεδομένων (.json)",
            data=json.dumps(quiz, ensure_ascii=False, indent=2),
            file_name="edtech_quiz.json",
            mime="application/json",
            use_container_width=True,
        )

    if submitted:
        score = 0
        st.divider()
        for i, q in enumerate(quiz["questions"]):
            correct_answer = q["options"][q["correct_index"]]
            user_answer = user_answers[i]

            if user_answer == correct_answer:
                score += 1
                st.success(
                    f"**Ερώτηση {i + 1}: Σωστό!** ({correct_answer})\n\n"
                    f"💡 *{q['explanation']}*"
                )
            elif user_answer is None:
                st.warning(
                    f"**Ερώτηση {i + 1}: Δεν απαντήθηκε.** "
                    f"Σωστή απάντηση: **{correct_answer}**\n\n"
                    f"💡 *{q['explanation']}*"
                )
            else:
                st.error(
                    f"**Ερώτηση {i + 1}: Λάθος.** Επέλεξες: *{user_answer}* | "
                    f"Σωστή: **{correct_answer}**\n\n"
                    f"💡 *{q['explanation']}*"
                )

        st.info(f"🎯 **Τελική Βαθμολογία: {score} / {len(quiz['questions'])}**")