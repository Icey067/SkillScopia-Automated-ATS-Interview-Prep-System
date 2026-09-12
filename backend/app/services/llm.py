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


async def generate_interview_question(skills: list[str], asked: list[str]) -> GeneratedQuestion:
    """Generate a single interview question forced into GeneratedQuestion schema with 1 retry."""
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
        return parsed
    except Exception as exc:
        logger.error("Failed to generate question via LLM: %s. Using default question.", exc)
        # Fallback question if Ollama service is unavailable
        skill_sample = skills[0] if skills else "software architecture"
        return GeneratedQuestion(
            question=f"Can you explain how you design and scale systems using {skill_sample}, including common performance bottlenecks and trade-offs?",
            ideal_answer_concept="Candidate should discuss concurrency, state management, caching, database indexing, and fault tolerance.",
        )


async def stream_interviewer_reply(
    question: str,
    ideal_concept: str,
    user_answer: str,
    skills: list[str],
) -> AsyncIterator[str]:
    """Stream interviewer feedback and follow-up token by token over WebSocket."""
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
        return 7.0
    except Exception as exc:
        logger.warning("Failed to calculate score via LLM: %s. Defaulting to 7.0", exc)
        return 7.0
