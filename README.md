# BRD Agent

An AI agent system that transforms business ideas and source documents into structured Business Requirements Documents (BRDs), actively detecting gaps and asking targeted clarification questions.

## Project Structure

- `backend/`: Python 3.11+ backend core foundation & AI Core Loop
  - `app/models/`: Pydantic v2 data models (`Project`, `Requirement`, `Question`, `Answer`, `Assumption`, `ValidationResult`, `SourceDocument`, `BRDDocumentVersion`)
  - `app/llm/`: Isolated Gemini client, prompt templates, and Pydantic response schemas
  - `app/core/`: Deterministic state machine, pure Python completeness rules, question engine, answer merger, and `BRDOrchestrator`
  - `app/templates/`: Standardized BRD document skeleton template (`build_brd_skeleton`)
  - `scripts/run_cli_demo.py`: Interactive CLI loop testing extraction and clarification
  - `tests/`: 32 unit and integration tests covering models, rules, questions, state machine, and orchestrator
  - `run_lifecycle_demo.py`: Executable walkthrough script

## One-Click Local Developer Setup

Clone the repository and launch both backend (FastAPI on `0.0.0.0:8000`) and frontend (React/Vite on `0.0.0.0:5173`) simultaneously:

### Windows Batch / Double-Click
Double-click `start-dev.bat` or run:
```cmd
start-dev.bat
```

### Windows PowerShell
```powershell
.\start-dev.ps1
```

### Cross-Platform / NPM
```bash
npm install
npm run dev:all
```

The script will automatically:
- Check for `.env` in `backend/` and `frontend/` and copy from `.env.example` if missing
- Verify and install Python & Node.js dependencies
- Bind both servers to `0.0.0.0` for seamless local and LAN network access (e.g. mobile devices)
- Color-code backend (blue) and frontend (green) logs in a unified terminal

---

## Architecture & Manual Setup

Refer to [backend/README.md](file:///c:/hackaton/Brd-Agent/backend/README.md) for architecture details, testing instructions, and CLI demos:

```bash
cd backend
python -m pip install -r requirements.txt
python -m pytest tests/ -v
python run_lifecycle_demo.py
python scripts/run_cli_demo.py
```

