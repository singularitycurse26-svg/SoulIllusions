# SoulIllusions Agent

> Always-on persistent AI agent — a hybrid of [Magnitude](https://github.com/magnitudedev/magnitude) + Prime Agent architecture.
> Free to run, no API keys required, full system access, never stops working.

## Features

- **Always-On**: Continuous ReAct loop that never stops — creates, completes, and improves projects autonomously
- **Free & Local**: Uses local inference (Ollama/llama.cpp) — no API keys, no token costs, no rate limits
- **Cloud Fallback**: Optionally use Anthropic/OpenAI API keys for higher quality reasoning
- **File-Centric Memory**: Based on [InfiAgent](https://arxiv.org/abs/2601.03204) architecture — state is externalized to the file system, context stays bounded regardless of task duration
- **10-Step Refresh**: Every 10 actions, context is rebuilt from file system state (no context compression, no information loss)
- **Full System Access**: Shell commands, file operations, Python execution, browser automation, day trading
- **Sub-Agents**: Specialized agents for coding, trading, research, and browser automation
- **Persistent**: Memory survives across sessions via workspace files and SQLite database

## Architecture

```
┌─────────────────────────────────────────────┐
│           SoulIllusions Agent               │
├─────────────┬──────────────┬───────────────┤
│  LLM        │  Tools       │  State Mgr    │
│  Interface  │  (System     │  (File-       │
│  (Local/    │   Access)    │   Centric)    │
│   Cloud)    │              │               │
├─────────────┴──────────────┴───────────────┤
│         Continuous ReAct Loop               │
│  Reason → Act → Observe → Repeat            │
├─────────────────────────────────────────────┤
│  Sub-Agents: Coder | Trader | Researcher   │
│              Browser                        │
├─────────────────────────────────────────────┤
│  Workspace (File System = Authoritative)    │
│  /projects  /memory  /skills  /logs        │
└─────────────────────────────────────────────┘
```

## Quick Start

```bash
# Install Ollama (for free local inference)
# https://ollama.com
ollama pull qwen2.5:7b

# Run the agent
python soulillusions_agent.py start

# Check status
python soulillusions_agent.py status

# Set a goal
python soulillusions_agent.py goal "Build a REST API for a todo app"

# Send a prompt
python soulillusions_agent.py prompt "What projects are currently active?"
```

## Configuration

Edit `agent_config.json`:

```json
{
  "mode": "local",
  "local_model": "qwen2.5:7b",
  "local_inference_url": "http://localhost:11434",
  "always_on": true,
  "max_actions_before_refresh": 10,
  "api_keys": {
    "anthropic": "",
    "openai": ""
  }
}
```

Switch to cloud mode by setting `"mode": "cloud"` and adding an API key.

## Tools

| Tool | Description |
|------|-------------|
| `run_command` | Execute shell commands |
| `read_file` | Read file contents |
| `write_file` | Write files |
| `edit_file` | Edit files by text replacement |
| `list_files` | List directory contents |
| `execute_python` | Run Python code |
| `create_project` | Create a new project |
| `complete_project` | Mark project as done |
| `improve_project` | Increment improvement counter |
| `save_memory` | Save persistent memory |
| `load_memory` | Load memory items |
| `search_web` | Web search |
| `browser_action` | Browser automation |
| `trade_action` | Day trading actions |

## Research Foundation

This agent is built on research from:

- **InfiAgent** (ACL 2026) — File-centric state externalization for infinite-horizon agents
- **Magnitude** — Local AI agent with Rust inference engine on llama.cpp
- **MemTier** — Tiered memory architecture for long-running agents
- **CogniFold** — Proactive cognitive memory folding for always-on agents

## License

MIT
