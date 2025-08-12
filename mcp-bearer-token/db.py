import sqlite3
import json
from pathlib import Path
from datetime import date

DB_PATH = Path(__file__).with_name("jee_bot.db")


def get_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS exam_info (
            name TEXT PRIMARY KEY,
            mains_date TEXT,
            advanced_date TEXT,
            pattern TEXT
        );
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            topic TEXT,
            question TEXT,
            options TEXT,
            answer INTEGER,
            explanation TEXT
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            topic TEXT,
            note TEXT
        );
        CREATE TABLE IF NOT EXISTS formulas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            topic TEXT,
            formula TEXT,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS progress (
            phone TEXT,
            subject TEXT,
            streak INTEGER,
            last_date TEXT,
            correct INTEGER,
            attempted INTEGER,
            PRIMARY KEY(phone, subject)
        );
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT,
            message TEXT,
            remind_at TEXT
        );
        """
    )

    # sample data
    cur.execute("SELECT COUNT(*) FROM exam_info")
    if cur.fetchone()[0] == 0:
        pattern = json.dumps({
            "duration": "3 hours",
            "questions": "75 (25 per subject)",
            "marking": "+4 for correct, -1 for incorrect"
        })
        cur.execute(
            "INSERT INTO exam_info VALUES (?,?,?,?)",
            ("JEE", "2025-01-24", "2025-05-25", pattern),
        )

    cur.execute("SELECT COUNT(*) FROM questions")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO questions (subject, topic, question, options, answer, explanation) VALUES (?,?,?,?,?,?)",
            [
                (
                    "Physics",
                    "Units",
                    "What is the SI unit of force?",
                    json.dumps(["Newton", "Joule", "Watt", "Pascal"]),
                    0,
                    "Force is measured in Newtons (N) in the SI system."
                ),
                (
                    "Chemistry",
                    "Atomic Structure",
                    "What is the charge of a proton?",
                    json.dumps(["+1", "0", "-1", "+2"]),
                    0,
                    "A proton carries a +1 elementary charge."
                ),
                (
                    "Mathematics",
                    "Calculus",
                    "Derivative of x^2 is?",
                    json.dumps(["x", "2x", "x^2", "2"]),
                    1,
                    "Using power rule d/dx(x^n) = n*x^(n-1), so derivative is 2x."
                ),
            ],
        )

    cur.execute("SELECT COUNT(*) FROM notes")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO notes (subject, topic, note) VALUES (?,?,?)",
            [
                ("Physics", "Kinematics", "Velocity is rate of change of displacement."),
                ("Chemistry", "Periodic Table", "Elements are arranged in order of increasing atomic number."),
            ],
        )

    cur.execute("SELECT COUNT(*) FROM formulas")
    if cur.fetchone()[0] == 0:
        cur.executemany(
            "INSERT INTO formulas (subject, topic, formula, description) VALUES (?,?,?,?)",
            [
                ("Physics", "Dynamics", "F = m a", "Force equals mass times acceleration."),
                ("Mathematics", "Geometry", "A = π r^2", "Area of a circle."),
            ],
        )

    conn.commit()
    conn.close()


def get_exam_info():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT mains_date, advanced_date, pattern FROM exam_info WHERE name='JEE'")
    row = cur.fetchone()
    conn.close()
    if not row:
        return {}
    mains, adv, pattern = row
    return {
        "mains_date": mains,
        "advanced_date": adv,
        "pattern": json.loads(pattern),
    }


def get_questions(subject: str, limit: int = 5):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, question, options FROM questions WHERE subject=? ORDER BY RANDOM() LIMIT ?",
        (subject, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "text": r[1],
            "options": json.loads(r[2]),
        }
        for r in rows
    ]


def get_question(qid: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, subject, question, options, answer, explanation FROM questions WHERE id=?",
        (qid,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "subject": row[1],
        "text": row[2],
        "options": json.loads(row[3]),
        "answer": row[4],
        "explanation": row[5],
    }


def get_notes(subject: str, topic: str | None = None):
    conn = get_conn()
    cur = conn.cursor()
    if topic:
        cur.execute("SELECT note FROM notes WHERE subject=? AND topic=?", (subject, topic))
    else:
        cur.execute("SELECT topic, note FROM notes WHERE subject=?", (subject,))
    rows = cur.fetchall()
    conn.close()
    if topic:
        return [r[0] for r in rows]
    return [{"topic": r[0], "note": r[1]} for r in rows]


def get_formulas(subject: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT topic, formula, description FROM formulas WHERE subject=?",
        (subject,)
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"topic": r[0], "formula": r[1], "description": r[2]} for r in rows
    ]


def record_progress(phone: str, subject: str, correct: bool):
    today = date.today().isoformat()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT streak, last_date, correct, attempted FROM progress WHERE phone=? AND subject=?",
        (phone, subject),
    )
    row = cur.fetchone()
    if row:
        streak, last_date, corr, att = row
        att += 1
        if correct:
            corr += 1
        if last_date == today:
            pass
        elif last_date == (date.fromisoformat(today) - date.resolution).isoformat():
            streak += 1
        else:
            streak = 1
        cur.execute(
            "UPDATE progress SET streak=?, last_date=?, correct=?, attempted=? WHERE phone=? AND subject=?",
            (streak, today, corr, att, phone, subject),
        )
    else:
        cur.execute(
            "INSERT INTO progress VALUES (?,?,?,?,?,?)",
            (phone, subject, 1, today, 1 if correct else 0, 1),
        )
    conn.commit()
    conn.close()


def get_progress_summary(phone: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT subject, streak, correct, attempted FROM progress WHERE phone=?",
        (phone,),
    )
    rows = cur.fetchall()
    conn.close()
    summary = []
    for subject, streak, correct, attempted in rows:
        summary.append(
            {
                "subject": subject,
                "streak": streak,
                "correct": correct,
                "attempted": attempted,
            }
        )
    return summary


def add_reminder(phone: str, message: str, remind_at: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reminders (phone, message, remind_at) VALUES (?,?,?)",
        (phone, message, remind_at),
    )
    conn.commit()
    conn.close()


def get_reminders(phone: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, message, remind_at FROM reminders WHERE phone=? ORDER BY remind_at",
        (phone,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {"id": r[0], "message": r[1], "remind_at": r[2]} for r in rows
    ]
