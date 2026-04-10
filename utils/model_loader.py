from sentence_transformers import SentenceTransformer
from config.settings import settings

_shared_model = None

def get_shared_sentence_transformer():
    global _shared_model
    if _shared_model is None:
        _shared_model = SentenceTransformer(settings.embedding_model)
    return _shared_model