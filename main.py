from pydantic import BaseModel, Field


class QuizQuestion(BaseModel):
    question: str = Field(description="Η εκφώνηση της ερώτησης")
    options: list[str] = Field(
        min_length=4, max_length=4, description="4 πιθανές απαντήσεις"
    )
    correct_index: int = Field(
        ge=0, le=3, description="Ο δείκτης (0-3) της σωστής απάντησης"
    )
    explanation: str = Field(
        description="Σύντομη αιτιολόγηση της σωστής απάντησης"
    )


# Νέο μοντέλο που περιέχει λίστα από QuizQuestion
class QuizSet(BaseModel):
    topic: str = Field(description="Το θέμα του διαγωνίσματος")
    questions: list[QuizQuestion] = Field(
        min_length=1, description="Λίστα ερωτήσεων"
    )


def main() -> None:
    raw_quiz_set = {
        "topic": "Αλγόριθμοι & Πολυπλοκότητα",
        "questions": [
            {
                "question": "Ποια είναι η χρονική πολυπλοκότητα της δυαδικής αναζήτησης;",
                "options": ["O(n)", "O(log n)", "O(n^2)", "O(1)"],
                "correct_index": 1,
                "explanation": "Σε κάθε βήμα το εύρος αναζήτησης υποδιπλασιάζεται.",
            },
            {
                "question": "Ποια δομή δεδομένων ακολουθεί την αρχή LIFO;",
                "options": ["Ουρά (Queue)", "Στοίβα (Stack)", "Δέντρο", "Γράφος"],
                "correct_index": 1,
                "explanation": "Last-In, First-Out (Τελευταίο μέσα, πρώτο έξω).",
            },
        ],
    }

    quiz = QuizSet(**raw_quiz_set)
    print(f"Θέμα: {quiz.topic} ({len(quiz.questions)} ερωτήσεις)")
    for i, q in enumerate(quiz.questions, start=1):
        print(f"{i}. {q.question} -> {q.options[q.correct_index]}")


if __name__ == "__main__":
    main()