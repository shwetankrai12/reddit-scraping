import logging
from typing import List, Union
import numpy as np

logger = logging.getLogger(__name__)


class ProblemEmbedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}...")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 384))
        model = self._get_model()
        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return np.array(embeddings)
