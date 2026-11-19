# J.A.R.V.I.S v8.0

> **J**ust **A** **R**ather **V**ery **I**ntelligent **S**ystem — a local, private,
> voice-enabled AI assistant built around [Ollama](https://ollama.com/). Runs
> entirely on your own machine; no cloud API keys required.

J.A.R.V.I.S is a personal assistant that combines an offline LLM (via Ollama) with
system control, persistent notes/todos/habits/reminders, command aliases, a
FastAPI web UI with WebSocket streaming, optional voice I/O, and a terminal mode.

---

## Features

- **Offline AI** — chat with any Ollama model; streaming responses, smart caching,
  model routing (primary / fast / vision / code) and conversation compression.
- **Web UI** — a single-page interface (`jarvis_ui.html`) with WebSocket token
  streaming, served by FastAPI.
- **REST API** — 20+ endpoints for status, system snapshot, notes, todos, habits,
  reminders, aliases, config, model switching, file upload and action logs.
- **System control** — process/performance monitoring, resource alerts, and
  host automation helpers (optional modules).
- **Productivity** — notes (with tags + search), todos, habit tracking, reminders,
  and custom command aliases.
- **Personality** — configurable personality mode, humor and "roast" levels.
- **Voice** — optional speech recognition (input) and TTS playback (output).
- **Terminal mode** — a full-featured CLI client (`jarvis_v7.py`).

---

## Requirements

- **Python 3.10+** (developed and verified on 3.13)
- **[Ollama](https://ollama.com/)** running locally with at least one model pulled
  (e.g. `ollama pull llama3.2:3b`, `ollama pull qwen2.5-coder:7b`)
- Windows, Linux, or macOS

All Python dependencies are listed in [`requirements.txt`](requirements.txt).

---

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start Ollama in another terminal
ollama serve

# 3. Run the setup wizard (installs deps + writes jarvis_config.json)
python launch.py --setup

# 4. Launch the web app  ->  http://localhost:5000
python launch.py
```

The API docs (Swagger UI) are available at <http://localhost:5000/api/docs>.
If port 5000 is busy, the launcher automatically tries 5001, 5002, and so on.

---

## `launch.py` commands

| Command | What it does |
| --- | --- |
| `python launch.py` | Start the web server (default) |
| `python launch.py --setup` | Install dependencies and run the config wizard |
| `python launch.py --check` | Run a system/dependency/file check |
| `python launch.py --cli` | Launch the terminal client (`jarvis_v7.py`) |
| `python launch.py --models 6` | Print model recommendations for 6 GB VRAM |
| `python launch.py --port 8080` | Start the web server on a custom port |

---

## Configuration

Settings live in `jarvis_config.json` (created by `python launch.py --setup`).
Key options:

```json
{
  "user_name": "Moksh",
  "default_city": "Hyderabad",
  "ollama_url": "http://127.0.0.1:11434",
  "primary_model": "llama3.2:3b",
  "fast_model": "llama3.2:3b",
  "vision_model": "llava:7b",
  "code_model": "qwen2.5-coder:7b",
  "personality_mode": "street",
  "humor_level": 8,
  "roast_level": 3
}
```

Run `python launch.py --models <your VRAM in GB>` for model suggestions.

---

## API overview

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/` | Web interface |
| `WS` | `/ws` | WebSocket chat (streaming) |
| `GET` | `/api/status` | Service status |
| `GET` | `/api/snapshot` | System snapshot |
| `GET` | `/api/processes` | Top processes |
| `GET` | `/api/perf_history` | Performance history |
| `GET/POST` | `/api/notes` | List / add notes |
| `DELETE` | `/api/notes/{idx}` | Delete a note |
| `GET/POST` | `/api/todos` | List / add todos |
| `DELETE` | `/api/todos/{idx}` | Delete a todo |
| `GET` | `/api/habits` | Habits |
| `GET` | `/api/reminders` | Reminders |
| `GET` | `/api/aliases` | Command aliases |
| `GET` | `/api/config` | Current configuration |
| `GET` | `/api/ai/stats` | AI usage statistics |
| `GET` | `/api/models` | Available Ollama models |
| `POST` | `/api/models/switch` | Switch active model |
| `GET` | `/api/action_log` | Action log |
| `POST` | `/api/upload` | Upload a file |

---

## Project structure

```
.
├── launch.py            # Launcher / setup / system check
├── jarvis_core.py       # Core engine: config, LLM, cache, notes, todos, etc.
├── jarvis_server.py     # FastAPI web server + WebSocket + REST API
├── jarvis_ui.html       # Single-page web interface
├── jarvis_system.py     # System control / automation helpers (optional)
├── jarvis_v7.py         # Terminal client (optional)
├── jarvis_config.json   # Local configuration
├── requirements.txt     # Python dependencies
└── docs/
    └── SENTINEL_research_report.md   # Research discovery report
```

---

## Research

A separate research discovery report is included in this repository at
[`docs/SENTINEL_research_report.md`](docs/SENTINEL_research_report.md). It covers a
proposed study on *telemetry-sufficiency auditing of provenance-based attack
reconstruction*, including the claims, closest prior work, kill criteria, and
next steps. It is documentation only and is not part of the running application.

---

## Notes

- The assistant needs Ollama running locally. With no Ollama process, the app still
  starts and serves the UI/API, but chat requests will fail until Ollama is up.
- On Windows consoles, the launcher forces UTF-8 output so the Unicode banner and
  status glyphs render correctly.
- Runtime logs (`jarvis.log`, `jarvis_actions.log`) and `__pycache__/` are ignored
  by Git.
