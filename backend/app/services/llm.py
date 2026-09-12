from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import AsyncIterator, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from app.config import get_settings
from app.schemas import GeneratedQuestion

logger = logging.getLogger(__name__)
settings = get_settings()

T = TypeVar("T", bound=BaseModel)


class SkillExtraction(BaseModel):
    skills: list[str] = Field(description="Technical skills, tools, and languages found in the resume")


def chat_llm(temperature: float = 0.2, streaming: bool = False) -> ChatOllama:
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=temperature,
        streaming=streaming,
        client_kwargs={"timeout": settings.llm_timeout_seconds},
    )


def _clean_json_text(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


async def _ainvoke_structured(
    parser: PydanticOutputParser[T],
    system: str,
    user: str,
    temperature: float = 0.1,
) -> tuple[T, str]:
    """Invoke Ollama with structured parser. Implements exactly one retry on parse failure."""
    llm = chat_llm(temperature=temperature)
    format_instructions = parser.get_format_instructions()
    messages = [
        SystemMessage(content=f"{system}\n\n{format_instructions}"),
        HumanMessage(content=user),
    ]

    raw_text = ""
    first_error_msg = ""
    # Attempt 1
    try:
        response = await llm.ainvoke(messages)
        raw_text = response.content if isinstance(response.content, str) else str(response.content)
        cleaned = _clean_json_text(raw_text)
        return parser.parse(cleaned), raw_text
    except Exception as first_err:
        first_error_msg = str(first_err)
        logger.warning(
            "Structured LLM parsing failed on first attempt: %s. Initiating exactly one retry.",
            first_err,
        )

    # Attempt 2 (Single automatic retry with error feedback)
    retry_user = (
        f"{user}\n\n"
        f"CRITICAL: Your previous response could not be parsed: {first_error_msg}\n"
        f"Format instructions: {format_instructions}\n"
        "Return ONLY the raw JSON object adhering to this schema. Do not enclose in markdown blocks or include comments."
    )
    retry_messages = [
        SystemMessage(content=f"{system}\n\n{format_instructions}"),
        HumanMessage(content=retry_user),
    ]
    try:
        retry_response = await llm.ainvoke(retry_messages)
        raw_text = retry_response.content if isinstance(retry_response.content, str) else str(retry_response.content)
        cleaned = _clean_json_text(raw_text)
        return parser.parse(cleaned), raw_text
    except Exception as second_err:
        logger.error("Structured LLM parsing failed after retry: %s. Raw text: %s", second_err, raw_text)
        raise RuntimeError(f"Structured output generation failed after 1 retry: {second_err}") from second_err


async def extract_skills_from_text(resume_text: str) -> list[str]:
    parser = PydanticOutputParser(pydantic_object=SkillExtraction)
    system = (
        "You are an expert technical recruiter and resume parser. "
        "Extract all concrete technical skills, languages, frameworks, developer tools, databases, "
        "and architectural patterns mentioned in the candidate resume."
    )
    user = f"Resume Content:\n{resume_text[:12000]}"
    try:
        parsed, _ = await _ainvoke_structured(parser, system, user)
        return [s.strip() for s in parsed.skills if s and s.strip()]
    except Exception as exc:
        logger.warning("Failed to extract skills via LLM: %s. Checking text with regex fallback.", exc)
        # Resilient fallback: extract keywords via regex if LLM is unavailable
        fallback_keywords = [
            "Python", "JavaScript", "TypeScript", "React", "Node.js", "FastAPI",
            "SQL", "PostgreSQL", "Docker", "Git", "REST APIs", "AWS", "Linux",
            "C++", "Java", "Go", "Kubernetes", "GraphQL", "MongoDB", "Redis",
        ]
        found = [k for k in fallback_keywords if re.search(rf"\b{re.escape(k)}\b", resume_text, re.IGNORECASE)]
        return found or ["Software Engineering"]


QUESTION_BANK: dict[str, list[tuple[str, str]]] = {
    "python": [
        (
            "How does Python's Global Interpreter Lock (GIL) affect multithreaded CPU-bound vs I/O-bound applications, and what concurrency models (asyncio, multiprocessing) would you choose for each?",
            "Candidate should discuss GIL constraints on bytecode execution, multithreading for I/O waits, multiprocessing for multi-core CPU parallelism, and asyncio event loops with non-blocking coroutines."
        ),
        (
            "Can you explain how Python manages memory under the hood, specifically reference counting, cyclic garbage collection, and how to detect memory leaks in long-running services?",
            "Candidate should mention PyObject ref counts, generational garbage collector (generations 0, 1, 2) for circular references, weakref, and tools like tracemalloc, objgraph, or memory_profiler."
        ),
        (
            "How do Python generators and the iterator protocol work, and how can they be leveraged to process large datasets without excessive memory usage?",
            "Candidate should describe __iter__ and __next__ protocols, the yield keyword, lazy evaluation, memory efficiency, and generator pipelines using itertools."
        ),
    ],
    "fastapi": [
        (
            "In FastAPI, how does Starlette's asynchronous request lifecycle work with async def vs regular def path operations, and what happens when you block the main thread?",
            "Candidate should distinguish async def (runs directly on the event loop) vs def (dispatched to an anyio threadpool worker), warning against calling blocking synchronous functions inside async def endpoints."
        ),
        (
            "How do you design a robust dependency injection hierarchy in FastAPI for database transactions, authentication, and permission scoping?",
            "Candidate should discuss Depends(), yield dependencies for clean session cleanup/commit/rollback, sub-dependencies, and security scopes."
        ),
    ],
    "javascript": [
        (
            "Explain the JavaScript Event Loop, microtasks (Promise jobs) vs macrotasks (setTimeout, I/O), and how they dictate execution order in asynchronous applications.",
            "Candidate should cover the call stack, Web APIs / libuv, microtask queue priority before rendering and next macrotask turn, and how long-running tasks cause UI jank."
        ),
        (
            "What are closures in JavaScript, how does lexical scoping create them, and what are real-world use cases or potential memory leak scenarios?",
            "Candidate should explain lexical scope chains, functions retaining outer scope references, private variables, event listener cleanup, and memory retention."
        ),
    ],
    "react": [
        (
            "How does React 18's concurrent renderer and Fiber architecture optimize UI updates, and when would you use useTransition or useDeferredValue?",
            "Candidate should explain Fiber reconciliation, interruptible rendering, prioritizing urgent updates (typing/clicks) over non-urgent transitions, and avoiding unnecessary re-renders."
        ),
        (
            "What strategies do you employ in React to avoid redundant component re-renders while maintaining clean state management?",
            "Candidate should discuss React.memo, useCallback, useMemo with proper dependency arrays, component decomposition, context slicing, and colocation of state."
        ),
    ],
    "sql": [
        (
            "How do B-tree indexes improve relational database query performance, what are composite index column ordering rules, and when would an index be ignored by the query planner?",
            "Candidate should explain B-tree search complexity, leftmost prefix rule for composite indexes, index selectivity, full table scans vs index scans, and functions applied to indexed columns preventing index usage."
        ),
        (
            "Compare ACID transaction isolation levels (Read Uncommitted, Read Committed, Repeatable Read, Serializable) and the anomalies they prevent (dirty reads, non-repeatable reads, phantom reads).",
            "Candidate should accurately match each isolation level to the specific anomaly it eliminates and mention MVCC (Multi-Version Concurrency Control) implementation in PostgreSQL."
        ),
    ],
    "docker": [
        (
            "How do multi-stage Docker builds reduce image size and improve container security in production deployments?",
            "Candidate should explain compiling binaries or installing build tools in early stages, copying only runtime artifacts into a minimal base (alpine/distroless), minimizing attack surface and vulnerabilities."
        ),
    ],
    "system_design": [
        (
            "How would you design a distributed caching layer with Redis to prevent cache stampede (thundering herd), cache penetration, and cache breakdown?",
            "Candidate should explain mutex locks/probabilistic early expiration (XFetch) for stampede, Bloom filters for non-existent keys (penetration), and stale-while-revalidate or pre-warming for popular expiring keys."
        ),
        (
            "When designing a system requiring high availability and low latency across multiple regions, how do you balance CAP theorem trade-offs and handle data consistency?",
            "Candidate should discuss CP vs AP systems, eventual consistency, quorum reads/writes, conflict resolution (CRDTs or last-write-wins), and asynchronous database replication lag."
        ),
        (
            "Can you describe how you implement rate limiting in a distributed microservices environment to protect upstream services from cascading failures?",
            "Candidate should cover token bucket or sliding window log algorithms, distributed coordination via Redis Lua scripts, circuit breakers, and 429 Retry-After semantics."
        ),
    ],
}


def _select_fallback_question(skills: list[str], asked: list[str]) -> GeneratedQuestion:
    """Select a rich, non-repeating technical question matched to verified candidate skills."""
    normalized_skills = [s.lower().strip() for s in skills]
    candidate_pools: list[tuple[str, str]] = []

    # Map candidate skills to question pools
    for skill_key, questions in QUESTION_BANK.items():
        if any(skill_key in s or s in skill_key for s in normalized_skills):
            candidate_pools.extend(questions)

    # Always include system design and general architecture questions
    candidate_pools.extend(QUESTION_BANK["system_design"])
    for q_list in QUESTION_BANK.values():
        candidate_pools.extend(q_list)

    # Filter out questions that have already been asked
    asked_set = set(asked)
    available = [q for q in candidate_pools if q[0] not in asked_set]

    if not available:
        # If all predefined questions were asked, synthesize a distinct question
        topic = skills[len(asked) % len(skills)] if skills else "distributed systems"
        q_text = f"In the context of {topic}, how do you evaluate architectural trade-offs between horizontal scalability, operational complexity, and fault tolerance?"
        q_concept = "Candidate should discuss stateless services, load balancing, consensus protocols, telemetry, and automated self-healing."
        return GeneratedQuestion(question=q_text, ideal_answer_concept=q_concept)

    # Pick the next available question
    selected_q, selected_concept = available[0]
    return GeneratedQuestion(question=selected_q, ideal_answer_concept=selected_concept)


async def generate_interview_question(skills: list[str], asked: list[str]) -> GeneratedQuestion:
    """Generate a single interview question forced into GeneratedQuestion schema with 1 retry."""
    if settings.parse_mode == "dummy":
        return _select_fallback_question(skills, asked)

    parser = PydanticOutputParser(pydantic_object=GeneratedQuestion)
    system = (
        "You are a Principal Software Engineer conducting a live technical interview. "
        "Generate exactly ONE focused technical interview question tailored to the candidate's skills. "
        "Also provide an 'ideal_answer_concept' outlining the specific architectural and technical concepts "
        "expected in a top-tier answer."
    )
    skill_blob = ", ".join(skills) if skills else "General Software Engineering, Data Structures, System Design"
    asked_blob = "\n".join(f"- {q}" for q in asked) if asked else "(None yet)"
    user = (
        f"Candidate Verified Skills: {skill_blob}\n"
        f"Previously Asked Questions:\n{asked_blob}\n"
        "Generate a distinct, deep interview question that has not been asked yet."
    )

    try:
        parsed, _ = await _ainvoke_structured(parser, system, user)
        if parsed.question in asked:
            return _select_fallback_question(skills, asked)
        return parsed
    except Exception as exc:
        logger.warning("LLM question generation unavailable or failed: %s. Using tailored question bank.", exc)
        return _select_fallback_question(skills, asked)


def _generate_fallback_feedback(
    question: str,
    ideal_concept: str,
    user_answer: str,
    skills: list[str],
) -> str:
    """Produce constructive, professional interviewer feedback when LLM is offline."""
    answer_len = len(user_answer.strip())
    words = set(re.findall(r"\b[a-zA-Z]{3,}\b", user_answer.lower()))
    concept_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", ideal_concept.lower()))
    overlap = words.intersection(concept_words)

    topic = skills[0] if skills else "system architecture"

    if answer_len < 30:
        return (
            "Thank you for your answer. It provides a brief initial thought, but in a senior technical interview, "
            f"you'll want to expand significantly with concrete technical details regarding {topic}. "
            "Consider explaining the specific trade-offs, concurrency guarantees, and how you would verify this in a production environment."
        )

    feedback_parts = [
        "Good response! You touched on key concepts" + (f" including {', '.join(list(overlap)[:3])}." if overlap else ".")
    ]

    if answer_len > 120:
        feedback_parts.append(
            f"Your approach demonstrates solid practical reasoning for {topic}. "
            "To make it even stronger, consider how this behaves under high concurrent load, "
            "what failure modes could occur, and how you would establish monitoring and automated alerting."
        )
    else:
        feedback_parts.append(
            "You have the right foundational intuition. "
            "In your next answers, try detailing specific mechanisms, edge-case handling, and performance implications under scale."
        )

    return " ".join(feedback_parts)


async def stream_interviewer_reply(
    question: str,
    ideal_concept: str,
    user_answer: str,
    skills: list[str],
) -> AsyncIterator[str]:
    """Stream interviewer feedback and follow-up token by token over WebSocket with graceful fallback."""
    if settings.parse_mode == "dummy":
        fallback_text = _generate_fallback_feedback(question, ideal_concept, user_answer, skills)
        tokens = re.split(r"(\s+)", fallback_text)
        for token in tokens:
            if token:
                yield token
                await asyncio.sleep(0.02)
        return

    llm = chat_llm(temperature=0.4, streaming=True)
    system = (
        "You are a supportive but rigorous Principal Engineer conducting a live mock interview. "
        "Acknowledge the candidate's answer with brief constructive feedback (1-2 sentences), "
        "then either challenge them with a natural follow-up question or probe deeper on edge cases. "
        "Keep the response conversational, concise, and professional. Do not provide a monologue."
    )
    user = json.dumps(
        {
            "skills": skills,
            "interview_question": question,
            "ideal_concepts": ideal_concept,
            "candidate_answer": user_answer,
        }
    )

    try:
        async for chunk in llm.astream(
            [SystemMessage(content=system), HumanMessage(content=user)]
        ):
            content = chunk.content
            if isinstance(content, str) and content:
                yield content
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, str) and part:
                        yield part
                    elif isinstance(part, dict) and part.get("text"):
                        yield str(part["text"])
    except asyncio.CancelledError:
        logger.info("Streaming interviewer reply was cancelled by client disconnection.")
        raise
    except Exception as exc:
        logger.warning("Live Ollama stream unavailable (%s). Streaming fallback feedback.", exc)
        fallback_text = _generate_fallback_feedback(question, ideal_concept, user_answer, skills)
        tokens = re.split(r"(\s+)", fallback_text)
        for token in tokens:
            if token:
                yield token
                await asyncio.sleep(0.02)


async def score_answer(question: str, ideal_concept: str, user_answer: str) -> float:
    """Evaluate and score candidate answer between 0.0 and 10.0."""
    prompt = (
        "You are an interview evaluator. Score the candidate's answer from 0.0 to 10.0 based on technical accuracy, "
        "depth, and alignment with the ideal concepts. Output ONLY a single decimal number between 0.0 and 10.0.\n\n"
        f"Question: {question}\n"
        f"Expected Concepts: {ideal_concept}\n"
        f"Candidate Answer: {user_answer}"
    )
    try:
        llm = chat_llm(temperature=0.0)
        result = await llm.ainvoke([HumanMessage(content=prompt)])
        text = result.content if isinstance(result.content, str) else str(result.content)
        matches = re.findall(r"\b\d+(?:\.\d+)?\b", text)
        if matches:
            score = float(matches[0])
            return max(0.0, min(10.0, score))
    except Exception as exc:
        logger.debug("Failed to calculate score via LLM: %s. Using heuristic evaluation.", exc)

    # Heuristic scoring fallback based on length and concept coverage
    clean_answer = user_answer.strip()
    if len(clean_answer) < 20:
        return 4.0
    if len(clean_answer) < 60:
        return 6.0

    words = set(re.findall(r"\b[a-zA-Z]{3,}\b", clean_answer.lower()))
    concept_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", ideal_concept.lower()))
    overlap_count = len(words.intersection(concept_words))

    score = 6.5 + min(2.5, overlap_count * 0.5)
    if len(clean_answer) > 180:
        score = min(9.5, score + 0.5)

    return round(score, 1)
