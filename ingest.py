import chromadb
import ollama

# 1. Διαβάζουμε το αρχείο σημειώσεων (πάντα με utf-8 για τα ελληνικά)
with open("notes.txt", "r", encoding="utf-8") as f:
    text = f.read()

# 2. Χωρίζουμε το κείμενο σε παραγράφους (chunks)
chunks = [chunk.strip() for chunk in text.split("\n\n") if chunk.strip()]
print(f"Βρέθηκαν {len(chunks)} αποσπάσματα κειμένου.")

# 3. Συνδεόμαστε στην τοπική βάση ChromaDB (θα δημιουργηθεί φάκελος chroma_db)
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="edtech_notes")

# 4. Μετατρέπουμε κάθε απόσπασμα σε διάνυσμα (embedding) και το αποθηκεύουμε
for i, chunk in enumerate(chunks):
    response = ollama.embed(model="nomic-embed-text", input=chunk)
    embedding = response.embeddings[0]

    collection.upsert(
        ids=[f"chunk_{i}"],
        documents=[chunk],
        embeddings=[embedding],
    )
    print(f"Αποθηκεύτηκε το απόσπασμα {i + 1}/{len(chunks)}")

print("\nΗ βάση ενημερώθηκε επιτυχώς!")

# 5. Γρήγορη δοκιμή σημασιολογικής αναζήτησης (Retrieval)
test_query = "Τι συμβαίνει όταν προσθέτουμε στοιχείο σε γεμάτη στοίβα;"
query_embedding = ollama.embed(model="nomic-embed-text", input=test_query).embeddings[0]

results = collection.query(query_embeddings=[query_embedding], n_results=1)
print("\n--- Δοκιμή Αναζήτησης ---")
print(f"Ερώτηση: {test_query}")
print(f"Πιο σχετικό απόσπασμα που βρέθηκε:\n{results['documents'][0][0]}")