from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


# Model embedding đa ngôn ngữ
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

_model = None


def get_model():
    global _model

    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)

    return _model


def create_embedding(text):
    """
    Chuyển một đoạn text thành vector embedding.
    """
    if not text or not text.strip():
        return None

    model = get_model()

    vector = model.encode(
        text,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    return vector


def calculate_similarity(text1, text2):
    """
    Tính độ tương đồng giữa hai đoạn text.
    Kết quả từ 0 đến 1.
    """

    if not text1 or not text2:
        return 0.0

    vector1 = create_embedding(text1)
    vector2 = create_embedding(text2)

    score = cosine_similarity(
        [vector1],
        [vector2]
    )[0][0]

    return float(score)


def similarity_percent(text1, text2):
    """
    Trả về similarity dưới dạng phần trăm.
    """

    score = calculate_similarity(text1, text2)

    score = max(0.0, min(1.0, score))

    return round(score * 100, 2)