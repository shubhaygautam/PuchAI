import asyncio
from typing import Annotated, List, Dict, Optional
import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
from mcp import ErrorData, McpError
from mcp.server.auth.provider import AccessToken
from mcp.types import TextContent, ImageContent, INVALID_PARAMS, INTERNAL_ERROR
from pydantic import BaseModel, Field, AnyUrl
import httpx
from datetime import datetime, timedelta
import json

# --- Load environment variables ---
load_dotenv()

TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")

assert TOKEN is not None, "Please set AUTH_TOKEN in your .env file"
assert MY_NUMBER is not None, "Please set MY_NUMBER in your .env file"

# --- Auth Provider ---
class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str) -> AccessToken | None:
        if token == self.token:
            return AccessToken(
                token=token,
                client_id="puch-client",
                scopes=["*"],
                expires_at=None,
            )
        return None

# --- Models for Exam Bot ---
class ExamInfo(BaseModel):
    name: str
    description: str
    syllabus: Dict[str, List[str]]  # {subject: [topics]}
    important_dates: Dict[str, str]
    pattern: Dict[str, str]
    resources: Dict[str, List[str]]  # {subject: [resources]}

class Question(BaseModel):
    text: str
    options: List[str]
    correct_answer: int
    explanation: str
    difficulty: str

class StudyPlan(BaseModel):
    exam: str
    start_date: str
    end_date: str
    daily_schedule: Dict[str, Dict]
    revision_days: List[str]

# --- Exam Database ---
EXAM_DATABASE = {
    "JEE": {
        "name": "Joint Entrance Examination (JEE)",
        "description": "Engineering entrance exam for IITs, NITs, and other colleges",
        "syllabus": {
            "Physics": ["Mechanics", "Electrodynamics", "Thermodynamics", "Optics", "Modern Physics"],
            "Chemistry": ["Physical Chemistry", "Organic Chemistry", "Inorganic Chemistry"],
            "Mathematics": ["Algebra", "Calculus", "Coordinate Geometry", "Trigonometry"]
        },
        "important_dates": {
            "registration": "2023-12-15",
            "mains": "2024-01-24",
            "advanced": "2024-05-26"
        },
        "pattern": {
            "duration": "3 hours",
            "questions": "75 (25 per subject)",
            "marking": "+4 for correct, -1 for incorrect"
        },
        "resources": {
            "Physics": ["HC Verma", "Irodov", "NCERT"],
            "Chemistry": ["OP Tandon", "MS Chouhan", "NCERT"],
            "Mathematics": ["RD Sharma", "Arihant", "NCERT"]
        }
    },
    "NEET": {
        "name": "National Eligibility cum Entrance Test (NEET)",
        "description": "Medical entrance exam for MBBS/BDS courses",
        "syllabus": {
            "Physics": ["Mechanics", "Optics", "Thermodynamics"],
            "Chemistry": ["Organic", "Inorganic", "Physical"],
            "Biology": ["Botany", "Zoology"]
        },
        "important_dates": {
            "registration": "2024-03-01",
            "exam": "2024-05-05"
        },
        "pattern": {
            "duration": "3 hours 20 minutes",
            "questions": "180 (45 per subject)",
            "marking": "+4 for correct, -1 for incorrect"
        },
        "resources": {
            "Physics": ["NCERT", "DC Pandey"],
            "Chemistry": ["NCERT", "Morrison Boyd"],
            "Biology": ["NCERT", "Trueman"]
        }
    }
}

QUESTION_BANK = {
    "JEE": {
        "Physics": [
            {
                "text": "What is the SI unit of force?",
                "options": ["Newton", "Joule", "Watt", "Pascal"],
                "correct_answer": 0,
                "explanation": "Force is measured in Newtons (N) in the SI system.",
                "difficulty": "easy"
            }
        ],
        "Mathematics": [
            {
                "text": "What is the derivative of x²?",
                "options": ["x", "2x", "x³/3", "1"],
                "correct_answer": 1,
                "explanation": "The derivative of xⁿ is n*xⁿ⁻¹",
                "difficulty": "easy"
            }
        ]
    }
}

# --- MCP Server Setup ---
mcp = FastMCP(
    "Competitive Exam Prep Bot",
    auth=SimpleBearerAuthProvider(TOKEN),
)

# --- Required Validation Tool ---
@mcp.tool
async def validate() -> str:
    return MY_NUMBER

# --- Exam Selection Tool ---
@mcp.tool(description="Get list of supported competitive exams")
async def get_exams() -> List[str]:
    return list(EXAM_DATABASE.keys())

# --- Exam Information Tool ---
@mcp.tool(description="Get detailed information about a specific exam")
async def get_exam_info(
    exam_name: Annotated[str, Field(description="Name of the exam (e.g., JEE, NEET)")]
) -> ExamInfo:
    exam = EXAM_DATABASE.get(exam_name.upper())
    if not exam:
        raise McpError(ErrorData(code=INVALID_PARAMS, message="Exam not found"))
    return exam

# --- Quiz Generator Tool ---
@mcp.tool(description="Generate quiz questions for a specific exam topic")
async def generate_quiz(
    exam_name: Annotated[str, Field(description="Name of the exam")],
    subject: Annotated[str, Field(description="Subject/topic for the quiz")],
    difficulty: Annotated[str, Field(description="Difficulty level (easy, medium, hard)")] = "medium",
    count: Annotated[int, Field(description="Number of questions")] = 5
) -> List[Question]:
    exam = EXAM_DATABASE.get(exam_name.upper())
    if not exam:
        raise McpError(ErrorData(code=INVALID_PARAMS, message="Exam not found"))
    
    if subject not in exam["syllabus"]:
        raise McpError(ErrorData(code=INVALID_PARAMS, message="Subject not found in exam syllabus"))
    
    questions = QUESTION_BANK.get(exam_name.upper(), {}).get(subject, [])
    filtered = [q for q in questions if q["difficulty"] == difficulty]
    
    if not filtered:
        return [{
            "text": "Sample question - this would be from real database",
            "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
            "correct_answer": 0,
            "explanation": "This is a sample explanation",
            "difficulty": difficulty
        } for _ in range(min(count, 5))]
    
    return filtered[:count]

# --- Study Plan Generator ---
@mcp.tool(description="Create personalized study plan for an exam")
async def generate_study_plan(
    exam_name: Annotated[str, Field(description="Name of the exam")],
    start_date: Annotated[str, Field(description="Start date (YYYY-MM-DD)")],
    end_date: Annotated[str, Field(description="Exam date (YYYY-MM-DD)")],
    hours_per_day: Annotated[int, Field(description="Available study hours per day")] = 2,
    weak_areas: Annotated[List[str], Field(description="List of weak topics")] = None,
    strong_areas: Annotated[List[str], Field(description="List of strong topics")] = None
) -> StudyPlan:
    exam = EXAM_DATABASE.get(exam_name.upper())
    if not exam:
        raise McpError(ErrorData(code=INVALID_PARAMS, message="Exam not found"))
    
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    days = (end - start).days
    
    if days <= 0:
        raise McpError(ErrorData(code=INVALID_PARAMS, message="End date must be after start date"))
    
    # Calculate topic weights
    topic_weights = {}
    for subject, topics in exam["syllabus"].items():
        for topic in topics:
            if weak_areas and topic in weak_areas:
                topic_weights[f"{subject}: {topic}"] = 3
            elif strong_areas and topic in strong_areas:
                topic_weights[f"{subject}: {topic}"] = 1
            else:
                topic_weights[f"{subject}: {topic}"] = 2
    
    # Create daily schedule
    daily_schedule = {}
    current_date = start
    topics = list(topic_weights.keys())
    weights = list(topic_weights.values())
    
    for i in range(days):
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Select topic based on weight
        topic = topics[i % len(topics)]
        
        daily_schedule[date_str] = {
            "topic": topic,
            "hours": hours_per_day,
            "activities": [
                f"Study {topic} for {hours_per_day*0.6} hours",
                f"Practice questions for {hours_per_day*0.4} hours"
            ],
            "resources": exam["resources"].get(topic.split(":")[0], ["General resources"])
        }
        
        current_date += timedelta(days=1)
    
    # Add revision days (last 7 days)
    revision_days = []
    for i in range(1, min(8, days)):
        revision_date = (end - timedelta(days=i)).strftime("%Y-%m-%d")
        revision_days.append(revision_date)
        daily_schedule[revision_date] = {
            "topic": "Revision",
            "hours": hours_per_day,
            "activities": [
                "Review all notes",
                "Solve previous year papers",
                "Take mock test"
            ]
        }
    
    return {
        "exam": exam_name,
        "start_date": start_date,
        "end_date": end_date,
        "daily_schedule": daily_schedule,
        "revision_days": revision_days
    }

# --- College Predictor ---
@mcp.tool(description="Predict colleges based on expected marks/rank")
async def predict_colleges(
    exam_name: Annotated[str, Field(description="Name of the exam")],
    expected_rank: Annotated[int, Field(description="Expected rank")] = None,
    expected_marks: Annotated[float, Field(description="Expected marks")] = None,
    category: Annotated[str, Field(description="Category (General, OBC, SC, ST)")] = "General",
    preferred_location: Annotated[str, Field(description="Preferred region")] = None
) -> List[Dict]:
    # Sample data - in real implementation this would connect to a database
    colleges = {
        "JEE": [
            {
                "name": "IIT Bombay",
                "cutoff_rank": 100,
                "cutoff_marks": 280,
                "fees": "₹2.5L/year",
                "location": "Mumbai"
            },
            {
                "name": "IIT Delhi",
                "cutoff_rank": 200,
                "cutoff_marks": 270,
                "fees": "₹2.3L/year",
                "location": "Delhi"
            },
            {
                "name": "NIT Trichy",
                "cutoff_rank": 1000,
                "cutoff_marks": 220,
                "fees": "₹1.5L/year",
                "location": "Tamil Nadu"
            }
        ],
        "NEET": [
            {
                "name": "AIIMS Delhi",
                "cutoff_rank": 100,
                "cutoff_marks": 680,
                "fees": "₹10K/year",
                "location": "Delhi"
            }
        ]
    }
    
    exam_colleges = colleges.get(exam_name.upper(), [])
    results = []
    
    for college in exam_colleges:
        if expected_rank and college["cutoff_rank"] < expected_rank:
            continue
        if expected_marks and college["cutoff_marks"] > expected_marks:
            continue
        if preferred_location and preferred_location.lower() not in college["location"].lower():
            continue
        
        results.append(college)
    
    return results[:10]  # Return top 10 matches

# --- Daily Question Reminder ---
@mcp.tool(description="Get daily practice question on a topic")
async def daily_question(
    exam_name: Annotated[str, Field(description="Name of the exam")],
    topic: Annotated[str, Field(description="Topic for the question")]
) -> Question:
    questions = await generate_quiz(exam_name, topic, "medium", 1)
    return questions[0] if questions else {
        "text": "No questions available for this topic yet",
        "options": [],
        "correct_answer": -1,
        "explanation": "",
        "difficulty": ""
    }

# --- Run MCP Server ---
async def main():
    print("🚀 Starting Competitive Exam Bot MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    asyncio.run(main())