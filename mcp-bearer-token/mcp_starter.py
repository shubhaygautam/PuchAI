import asyncio
import os
import json
from typing import Annotated, List, Dict
from datetime import datetime

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp.server.auth.provider import AccessToken
from pydantic import BaseModel, Field
import httpx
import dateparser

from db import (
    init_db,
    get_exam_info,
    get_questions,
    get_question,
    get_notes,
    get_formulas,
    record_progress,
    get_progress_summary,
    add_reminder,
    get_reminders,
)

load_dotenv()
TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")
GEN_URL = os.environ.get("GEN_AI_URL")
GEN_KEY = os.environ.get("GEN_AI_KEY")

assert TOKEN and MY_NUMBER, "AUTH_TOKEN and MY_NUMBER must be set"

class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str) -> AccessToken | None:
        if token == self.token:
            return AccessToken(token=token, client_id="puch-client", scopes=["*"], expires_at=None)
        return None

mcp = FastMCP(
    "JEE Exam Bot",
    auth=SimpleBearerAuthProvider(TOKEN),
)

class Question(BaseModel):
    id: int
    text: str
    options: List[str]

class AnswerResult(BaseModel):
    correct: bool
    correct_answer: int
    explanation: str

async def call_gen_ai(prompt: str) -> str | None:
    if not GEN_URL:
        return None
    headers = {"Content-Type": "application/json"}
    if GEN_KEY:
        headers["Authorization"] = f"Bearer {GEN_KEY}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(GEN_URL, headers=headers, json={"prompt": prompt})
            if resp.status_code == 200:
                data = resp.json()
                return data.get("text") or data.get("output")
    except Exception:
        return None
    return None

async def rephrase(text: str) -> str:
    prompt = f"Rephrase in simple words: {text}"
    result = await call_gen_ai(prompt)
    return result or text

async def parse_time(text: str) -> str:
    now = datetime.now().isoformat()
    prompt = f"Convert '{text}' to ISO 8601 datetime. Current time is {now}."
    result = await call_gen_ai(prompt)
    if result:
        return result.strip()
    dt = dateparser.parse(text)
    return dt.isoformat() if dt else now

@mcp.tool
async def validate() -> str:
    return MY_NUMBER

@mcp.tool(description="Get official JEE exam dates and pattern")
async def exam_info() -> Dict:
    return get_exam_info()

@mcp.tool(description="Generate quiz questions for a subject")
async def generate_quiz(
    subject: Annotated[str, Field(description="Subject for quiz")],
    count: Annotated[int, Field(description="Number of questions")] = 5,
) -> List[Question]:
    rows = get_questions(subject, count)
    return [Question(**r) for r in rows]

@mcp.tool(description="Check answer for a question")
async def check_answer(
    question_id: Annotated[int, Field(description="Question id")],
    selected: Annotated[int, Field(description="Selected option index")],
    phone: Annotated[str, Field(description="User phone number")],
) -> AnswerResult:
    q = get_question(question_id)
    if not q:
        return AnswerResult(correct=False, correct_answer=-1, explanation="Question not found")
    correct = selected == q["answer"]
    record_progress(phone, q["subject"], correct)
    explanation = await rephrase(q["explanation"])
    return AnswerResult(correct=correct, correct_answer=q["answer"], explanation=explanation)

@mcp.tool(description="Show study notes")
async def show_notes(
    subject: Annotated[str, Field(description="Subject")],
    topic: Annotated[str | None, Field(description="Topic", default=None)] = None,
) -> List[Dict]:
    return get_notes(subject, topic)

@mcp.tool(description="Show important formulas")
async def show_formulas(
    subject: Annotated[str, Field(description="Subject")],
) -> List[Dict]:
    return get_formulas(subject)

@mcp.tool(description="Get study progress and streaks")
async def progress(
    phone: Annotated[str, Field(description="User phone number")],
) -> List[Dict]:
    return get_progress_summary(phone)

@mcp.tool(description="Set a study reminder")
async def set_reminder(
    phone: Annotated[str, Field(description="User phone number")],
    message: Annotated[str, Field(description="Reminder message")],
    time_text: Annotated[str, Field(description="When to remind")],
) -> Dict:
    remind_at = await parse_time(time_text)
    add_reminder(phone, message, remind_at)
    return {"remind_at": remind_at, "message": message}

@mcp.tool(description="List reminders")
async def list_reminders(
    phone: Annotated[str, Field(description="User phone number")],
) -> List[Dict]:
    return get_reminders(phone)

async def main():
    init_db()
    print("🚀 Starting JEE MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    asyncio.run(main())
