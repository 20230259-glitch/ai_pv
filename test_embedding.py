from ai.embedding import (
    create_embedding,
    calculate_similarity,
    similarity_percent
)


text1 = """
Tôi có kinh nghiệm phát triển REST API bằng Python
và FastAPI.
"""

text2 = """
Ứng viên đã từng xây dựng backend API
sử dụng Python và FastAPI.
"""

text3 = """
Tôi có kinh nghiệm thiết kế giao diện website
bằng HTML và CSS.
"""


vector = create_embedding(text1)

print("Vector shape:", vector.shape)

score1 = calculate_similarity(text1, text2)
score2 = calculate_similarity(text1, text3)

print("Similarity text1 - text2:", score1)
print("Similarity text1 - text3:", score2)

print(
    "Similarity % text1 - text2:",
    similarity_percent(text1, text2)
)

print(
    "Similarity % text1 - text3:",
    similarity_percent(text1, text3)
)