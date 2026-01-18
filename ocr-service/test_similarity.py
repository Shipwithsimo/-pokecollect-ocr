"""
Test rapido per verificare il fuzzy matching
"""
from rapidfuzz import fuzz

def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0

    a_clean = a.lower().strip()
    b_clean = b.lower().strip()

    ratio = fuzz.ratio(a_clean, b_clean) / 100.0
    token_sort = fuzz.token_sort_ratio(a_clean, b_clean) / 100.0
    partial = fuzz.partial_ratio(a_clean, b_clean) / 100.0

    return (ratio * 0.5) + (token_sort * 0.3) + (partial * 0.2)

# Test cases
test_cases = [
    ("Pikachu", "Pikachu"),           # Perfect match
    ("Pikachu", "Pikachuu"),          # Typo
    ("Charizard EX", "Charizard-EX"), # Variante
    ("Fire Energy", "Energy - Fire"), # Ordine diverso
    ("Mewtwo", "Mew"),                # Simile ma diverso
    ("Bulbasaur", "Venusaur"),        # Nome correlato
]

print("🧪 Test Fuzzy Matching\n")
print("-" * 60)
for a, b in test_cases:
    score = similarity(a, b)
    print(f"{a:20} vs {b:20} → {score:.2%}")
print("-" * 60)
