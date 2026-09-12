from __future__ import annotations

import asyncio
import logging
from typing import Any
import numpy as np

from app.config import get_settings

logger = logging.getLogger(__name__)

SKILL_ONTOLOGY: list[str] = [
    "Python",
    "Java",
    "JavaScript",
    "TypeScript",
    "C++",
    "Go",
    "Rust",
    "SQL",
    "HTML",
    "CSS",
    "React",
    "DOM manipulation",
    "component lifecycle",
    "state management",
    "Redux",
    "Vue.js",
    "Angular",
    "Node.js",
    "Express",
    "REST APIs",
    "GraphQL",
    "FastAPI",
    "Flask",
    "Django",
    "Spring Boot",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Redis",
    "Docker",
    "Kubernetes",
    "Linux",
    "Git",
    "CI/CD",
    "unit testing",
    "pytest",
    "Jest",
    "machine learning",
    "neural networks",
    "NLP",
    "transformers",
    "embeddings",
    "LangChain",
    "Ollama",
    "prompt engineering",
    "data structures",
    "algorithms",
    "system design",
    "authentication",
    "JWT",
    "OAuth",
    "WebSockets",
    "asynchronous programming",
    "multithreading",
    "AWS",
    "cloud computing",
    "Terraform",
    "Pandas",
    "NumPy",
    "data analysis",
]


class EmbeddingService:
    _instance: EmbeddingService | None = None

    def __init__(self) -> None:
        self._model: Any = None
        self._ontology_matrix: np.ndarray | None = None
        self._ontology_names: list[str] = SKILL_ONTOLOGY
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> EmbeddingService:
        if cls._instance is None:
            cls._instance = EmbeddingService()
        return cls._instance

    @property
    def is_loaded(self) -> bool:
        return self._model is not None and self._ontology_matrix is not None

    def load_model_sync(self) -> None:
        if self._model is not None:
            return
        settings = get_settings()
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading SentenceTransformer singleton: %s", settings.embedding_model)
            self._model = SentenceTransformer(settings.embedding_model)
            vectors = self._model.encode(self._ontology_names, normalize_embeddings=True)
            self._ontology_matrix = np.asarray(vectors, dtype=np.float32)
            logger.info("SentenceTransformer singleton initialized with ontology matrix shape: %s", self._ontology_matrix.shape)
        except Exception as exc:
            logger.warning("Could not load SentenceTransformer model (%s). Fallback mode active.", exc)
            self._model = None
            self._ontology_matrix = None

    async def initialize(self) -> None:
        async with self._lock:
            if not self.is_loaded:
                await asyncio.to_thread(self.load_model_sync)

    def encode(self, texts: list[str]) -> np.ndarray:
        if self._model is None:
            # Fallback uniform embedding if model not loaded
            rng = np.random.default_rng(42)
            vecs = rng.standard_normal((len(texts), 384), dtype=np.float32)
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            return vecs / np.maximum(norms, 1e-12)
        return self._model.encode(texts, normalize_embeddings=True)

    def expand_skills(
        self,
        extracted: list[str],
        min_similarity: float = 0.42,
        max_related: int = 6,
    ) -> list[tuple[str, str, float]]:
        """Return (skill_name, source, confidence) including extracted + semantically related ontology skills."""
        if not extracted:
            return []

        rows: list[tuple[str, str, float]] = []
        seen: set[str] = set()

        for skill in extracted:
            key = skill.strip()
            if not key:
                continue
            lowered = key.lower()
            if lowered not in seen:
                seen.add(lowered)
                rows.append((key, "resume", 1.0))

            if self._ontology_matrix is not None and self._model is not None:
                vec = self.encode([key])[0]
                sims = self._ontology_matrix @ vec
                ranked = np.argsort(-sims)
                added = 0
                for idx in ranked:
                    label = self._ontology_names[int(idx)]
                    score = float(sims[int(idx)])
                    if score < min_similarity:
                        break
                    if label.lower() == lowered or label.lower() in seen:
                        continue
                    seen.add(label.lower())
                    rows.append((label, "semantic", round(score, 4)))
                    added += 1
                    if added >= max_related:
                        break
            else:
                # Direct string/prefix matching fallback
                for ontology_skill in self._ontology_names:
                    if ontology_skill.lower() not in seen and (
                        key.lower() in ontology_skill.lower() or ontology_skill.lower() in key.lower()
                    ):
                        seen.add(ontology_skill.lower())
                        rows.append((ontology_skill, "semantic", 0.75))
                        break

        return rows

    async def expand_skills_async(
        self,
        extracted: list[str],
        min_similarity: float = 0.42,
        max_related: int = 6,
    ) -> list[tuple[str, str, float]]:
        return await asyncio.to_thread(self.expand_skills, extracted, min_similarity, max_related)


# Global singleton instance
embedding_service = EmbeddingService.get_instance()


def get_embedding_model():
    if not embedding_service.is_loaded:
        embedding_service.load_model_sync()
    return embedding_service._model


def expand_skills(
    extracted: list[str],
    min_similarity: float = 0.42,
    max_related: int = 6,
) -> list[tuple[str, str, float]]:
    return embedding_service.expand_skills(extracted, min_similarity, max_related)
