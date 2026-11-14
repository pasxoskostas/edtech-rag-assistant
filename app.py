import requests
import streamlit as st

# Βασικές ρυθμίσεις σελίδας
st.set_page_config(page_title="EdTech RAG Assistant", page_icon="🎓")

st.title("🎓 EdTech AI Quiz Generator")
st.write("Παραγωγή διαδραστικού κουίζ αποκλειστικά από τις σημειώσεις του μαθήματος.")

# 1. Αρχικοποίηση μνήμης (session_state) ώστε να μην χάνεται το κουίζ στα reruns
if "quiz_data" not in st.session_state:
    st.session_state["quiz_data"] = None

# 2. Πεδία εισόδου χρήστη
topic = st.text_input("Θέμα μαθήματος:", value="Στοίβα: λειτουργίες PUSH και POP")
num_questions = st.slider("Αριθμός ερωτήσεων:", min_value=1, max_value=5, value=2)

if st.button("Δημιουργία Κουίζ"):
    if len(topic.strip()) < 3:
        st.warning("Παρακαλώ γράψε ένα θέμα με τουλάχιστον 3 χαρακτήρες.")
    else:
        with st.spinner("Αναζήτηση στις σημειώσεις και παραγωγή κουίζ..."):
            try:
                response = requests.post(
                    "http://127.0.0.1:8000/generate-quiz",
                    json={"topic": topic.strip(), "num_questions": num_questions},
                    timeout=60,
                )
                if response.status_code == 200:
                    # Αποθηκεύουμε το κουίζ στη μνήμη και καθαρίζουμε παλιές επιλογές
                    st.session_state["quiz_data"] = response.json()
                    for key in list(st.session_state.keys()):
                        if key.startswith("q_"):
                            del st.session_state[key]
                else:
                    st.error(f"Σφάλμα ({response.status_code}): {response.text}")
            except requests.exceptions.ConnectionError:
                st.error("Δεν βρέθηκε ενεργός FastAPI server. Βεβαιώσου ότι τρέχει το main.py!")
            except requests.exceptions.ReadTimeout:
                st.error("Ο server άργησε να απαντήσει (Timeout 60s). Έλεγξε το terminal του FastAPI.")

# 3. Εμφάνιση του διαδραστικού κουίζ (εφόσον υπάρχει στη μνήμη)
quiz = st.session_state["quiz_data"]

if quiz:
    st.divider()
    st.subheader(f"📝 Κουίζ: {quiz['topic']}")

    with st.form("quiz_form"):
        user_answers = []
        for i, q in enumerate(quiz["questions"]):
            choice = st.radio(
                label=f"**{i + 1}. {q['question']}**",
                options=q["options"],
                index=None,  # Καμία προεπιλεγμένη απάντηση στην αρχή
                key=f"q_{i}",
            )
            user_answers.append(choice)
            st.write("")

        submitted = st.form_submit_button("Υποβολή Απαντήσεων")

    # 4. Αυτόματη βαθμολόγηση και αιτιολόγηση
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