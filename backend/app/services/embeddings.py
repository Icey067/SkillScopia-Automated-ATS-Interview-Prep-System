from __future__ import annotations

from functools import lru_cache

import numpy as np

from app.config import get_settings

# Relationship space: canonical tech concepts. Related ideas sit close in embedding space
# even when the resume never used those exact words (e.g. "React" ↔ "DOM manipulation").
SKILL_ONTOLOGY = [
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


@lru_cache
def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    return SentenceTransformer(settings.embedding_model)


@lru_cache
def ontology_matrix() -> tuple[list[str], np.ndarray]:
    model = get_embedding_model()
    vectors = model.encode(SKILL_ONTOLOGY, normalize_embeddings=True)
    return SKILL_ONTOLOGY, np.asarray(vectors)


def expand_skills(extracted: list[str], min_similarity: float = 0.42, max_related: int = 6) -> list[tuple[str, str, float]]:
    """Return (skill_name, source, confidence) including original + semantically related concepts."""
    if not extracted:
        return []

    model = get_embedding_model()
    names, matrix = ontology_matrix()
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

        vec = model.encode([key], normalize_embeddings=True)[0]
        sims = matrix @ vec
        ranked = np.argsort(-sims)
        added = 0
        for idx in ranked:
            label = names[int(idx)]
            score = float(sims[int(idx)])
            if score < min_similarity:
                break
            if label.lower() == lowered:
                continue
            if label.lower() in seen:
                continue
            seen.add(label.lower())
            rows.append((label, "semantic", round(score, 4)))
            added += 1
            if added >= max_related:
                break
    return rows
