from __future__ import annotations

import json
from typing import AsyncIterator

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

from app.config import get_settings
from app.schemas import GeneratedQuestion

settings = get_settings()


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


def _invoke_structured(parser: PydanticOutputParser, system: str, user: str, retry_hint: str | None = None):
    llm = chat_llm(temperature=0.1)
    format_instructions = parser.get_format_instructions()
    messages = [
        SystemMessage(content=system + "\n\n" + format_instructions),
        HumanMessage(content=user if not retry_hint else f"{user}\n\nPrevious output failed validation: {retry_hint}\nReturn ONLY valid JSON."),
    ]
    result = llm.invoke(messages)
    text = result.content if isinstance(result.content, str) else str(result.content)
    return parser.parse(text), text


def extract_skills_from_text(resume_text: str) -> list[str]:
    parser = PydanticOutputParser(pydantic_object=SkillExtraction)
    system = (
        "You extract technical skills from resumes. "
        "Return only skills that are clearly technical (languages, frameworks, tools, platforms)."
    )
    user = f"Resume text:\n{resume_text[:12000]}"
    try:
        parsed, _ = _invoke_structured(parser, system, user)
        return [s.strip() for s in parsed.skills if s.strip()]
    except Exception as first_err:
        try:
            parsed, _ = _invoke_structured(parser, system, user, retry_hint=str(first_err))
            return [s.strip() for s in parsed.skills if s.strip()]
        except Exception:
            return []


def generate_interview_question(skills: list[str], asked: list[str]) -> GeneratedQuestion:
    parser = PydanticOutputParser(pydantic_object=GeneratedQuestion)
    system = (
        "You are an interviewer for a software role. "
        "Generate ONE tailored interview question grounded in the candidate's skills. "
        "ideal_answer_concept must describe the concepts a strong answer should cover, not a full script."
    )
    skill_blob = ", ".join(skills) or "general software engineering"
    asked_blob = "\n".join(f"- {q}" for q in asked) or "(none yet)"
    user = (
        f"Candidate skills: {skill_blob}\n"
        f"Already asked:\n{asked_blob}\n"
        "Produce a new question that does not repeat the list."
    )
    try:
        parsed, _ = _invoke_structured(parser, system, user)
        return parsed
    except Exception as first_err:
        try:
            parsed, _ = _invoke_structured(parser, system, user, retry_hint=str(first_err))
            return parsed
        except Exception as second_err:
            raise RuntimeError(f"Question generation failed after retry: {second_err}") from second_err


async def stream_interviewer_reply(
    question: str,
    ideal_concept: str,
    user_answer: str,
    skills: list[str],
) -> AsyncIterator[str]:
    llm = chat_llm(temperature=0.4, streaming=True)
    system = (
        "You are a live mock interviewer. Respond in a spoken, concise style. "
        "Give brief feedback on the candidate's answer, then ask one short follow-up "
        "or move on. Do not reveal a full model answer."
    )
    user = json.dumps(
        {
            "skills": skills,
            "current_question": question,
            "ideal_answer_concept": ideal_concept,
            "candidate_answer": user_answer,
        }
    )
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


def score_answer(question: str, ideal_concept: str, user_answer: str) -> float:
    prompt = (
        "Score the candidate answer from 0 to 10. Reply with a single number only.\n"
        f"Question: {question}\n"
        f"Ideal concepts: {ideal_concept}\n"
        f"Answer: {user_answer}"
    )
    try:
        result = chat_llm(temperature=0).invoke([HumanMessage(content=prompt)])
        text = result.content if isinstance(result.content, str) else str(result.content)
        digits = "".join(ch if ch.isdigit() or ch == "." else " " for ch in text).split()
        if not digits:
            return 0.0
        score = float(digits[0])
        return max(0.0, min(10.0, score))
    except Exception:
        return 0.0
