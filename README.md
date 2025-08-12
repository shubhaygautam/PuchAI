# JEE Exam Prep MCP Server

This project implements a Model Context Protocol (MCP) server for Puch AI that powers a WhatsApp chatbot helping students prepare for the Joint Entrance Examination (JEE).

The server exposes tools for quizzes, explanations, notes, formulas, progress tracking, reminders and official exam information. All factual data is stored in an SQLite database so answers remain consistent. An optional generative AI endpoint (e.g. Gemini) can be provided to rephrase explanations and to interpret natural language reminder times.

## Features
- ✅ Validate a user's phone number from the bearer token
- 📚 Generate quizzes from a question bank and check answers with explanations
- 📝 Show study notes and important formulas
- 📈 Track study progress and daily streaks
- ⏰ Set reminders using natural language like "tomorrow at 7am"
- 📅 Show official exam dates and pattern

## Getting Started
1. **Install dependencies**
   ```bash
   uv venv
   uv sync
   source .venv/bin/activate
   ```
2. **Configure environment**
   ```bash
   cp .env.example .env
   ```
   Fill in:
   - `AUTH_TOKEN` – bearer token required by Puch AI
   - `MY_NUMBER` – your WhatsApp number
   - Optional `GEN_AI_URL` and `GEN_AI_KEY` for generative AI
3. **Run the server**
   ```bash
   cd mcp-bearer-token
   python mcp_starter.py
   ```
   The server starts on `http://0.0.0.0:8086`.

Expose the port using a service like ngrok if you need public HTTPS access for Puch AI.

## Database
An SQLite database `jee_bot.db` is created automatically with sample questions, notes and formulas so the bot works immediately. All user progress and reminders are stored in this database.

## MCP Tools
- `validate`
- `exam_info`
- `generate_quiz`
- `check_answer`
- `show_notes`
- `show_formulas`
- `progress`
- `set_reminder`
- `list_reminders`

These tools are ready to be connected to Puch AI via the `/mcp connect` command on WhatsApp.

---
Happy studying! 🎓
