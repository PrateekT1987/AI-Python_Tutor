# Python Tutor — PyQt6 Desktop App

An interactive Python learning companion with a modern dark-themed desktop interface. Ask questions, get explanations with live streaming responses, run code snippets directly in the chat, and experiment in a built-in scratchpad.

![Python Tutor screenshot](gui_chat.png)

## Features

- **Live streaming answers** — Token-by-token SSE from OpenRouter with a stop button and smart auto-scroll
- **Rich Markdown rendering** — Headings, lists, tables, blockquotes, fenced code blocks with Pygments syntax highlighting + line numbers
- **Runnable code blocks** — Click ▶ Run on any snippet to execute it in an isolated subprocess (clean env, 10 s timeout) and see output inline
- **Scratchpad** — Persistent side window with line-number gutter for free-form code experimentation
- **Session persistence** — History, window geometry, and settings survive restarts
- **Settings dialog** — API key (with show toggle), model, temperature, max tokens; connection test against `/auth/key` with `/models` fallback
- **Modern dark theme** — Fusion palette + QSS, centered readable column (75% / 900 px cap), zoom (Ctrl±/0), keyboard shortcuts
- **Thread-safe lifecycle** — Tracked worker threads, graceful cancel on close, 4 s deadline with terminate fallback

## Quick Start

```bash
# Clone
git clone https://github.com/PrateekT1987/AI-Python_Tutor.git
cd AI-Python_Tutor

# Create virtual env & install deps
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run
python src/main.py
```

On first launch, open **Settings (Ctrl+,)** and enter your OpenRouter API key and model. Settings are saved to `~/.config/python-tutor/config.json` (0600) and persist across restarts.

## Requirements

- Python 3.10+
- PyQt6, requests, python-dotenv, pygments, structlog

## Configuration

All settings are managed through the **Settings** dialog (Ctrl+,):

- **API Key** — Your OpenRouter API key (shown/hidden toggle)
- **Model ID** — e.g., `nvidia/nemotron-3-ultra-550b-a55b:free`
- **Base URL** — OpenRouter endpoint (default: `https://openrouter.ai/api/v1`)
- **Temperature / Max Tokens** — Generation parameters
- **Sandbox Memory / Network** — Reserved for future code execution sandbox

Settings are stored in `~/.config/python-tutor/config.json` (owner-readable only) and take precedence over any environment variables.

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Enter` | Send message |
| `Shift+Enter` | New line in input |
| `Esc` | Stop generating |
| `Ctrl+L` | New session |
| `Ctrl+E` | Export transcript |
| `Ctrl+,` | Settings |
| `Ctrl+Shift+S` | Toggle scratchpad |
| `Ctrl++` / `Ctrl+-` / `Ctrl+0` | Zoom in / out / reset |

## Project Structure

```
src/
├── main.py                 # Entry point, theme bootstrap
├── core/
│   ├── config.py           # Config dataclass, atomic 0600 save
│   ├── settings.py         # Session/history JSON persistence
│   ├── logging_setup.py    # Structured logging (structlog + stdlib)
│   ├── parsers/            # Markdown → blocks → HTML
│   └── workers/            # LLMThread, ConnectionTestThread, ApiError
├── ui/
│   ├── main_window.py      # MainWindow, SettingsDialog
│   ├── theme.py            # Fusion palette + global QSS
│   └── widgets/
│       ├── chat_widgets.py # MessageBubble, InputArea, Scratchpad, CodeEditor
│       └── syntax_highlighter.py
└── prompts.py              # System prompts per difficulty level
tests/
├── test_core.py            # Config, parsers, workers
└── test_widgets.py         # MessageBubble, InputArea, Scratchpad, run/code-execution
```

## Tests

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
# 68 tests covering config precedence, markdown rendering, worker retry logic,
# bubble sizing, code execution, scratchpad line numbers, etc.
```

## License

MIT — see [LICENSE](LICENSE).