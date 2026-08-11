# SoulIllusions Platform

> AI-powered creative suite: Video generation, image studio, AI agent, text-to-games, and automated phone verification.
> 100% Free — Open Source — No API Keys Needed

## Features

### 1. Video Maker
AI video generation using free Kaggle GPU backends (T4 x2, 90 hrs/week with 3 accounts).

### 2. Image Studio
Text-to-image and image-to-image generation with multiple models.

### 3. Asset Library
Organized library of generated assets with categories and search.

### 4. Production Suite
Series/Episode/Scene management with narrative memory engine.

### 5. SoulIllusions Prime
Integration with Prime Agent for autonomous task execution.

### 6. Terminal
Remote terminal access to GPU backend with GPU account switching.

### 7. SoulIllusions Agent (NEW)
Always-on persistent AI agent — hybrid of Magnitude + Prime Agent:
- **Free & Local**: Uses Ollama/llama.cpp — no API keys, no token costs
- **Always-On**: Continuous ReAct loop that never stops working
- **File-Centric Memory**: InfiAgent architecture — state externalized to file system
- **Full System Access**: Shell, files, code, browser, day trading
- **Sub-Agents**: Coder, Trader, Researcher, Browser

### 8. Text-to-Games (NEW)
Generate complete, playable HTML5 games from text prompts:
- **Instant Templates**: Platformer, Shooter, Puzzle, Racing, Arcade
- **AI Generation**: Custom games generated from text descriptions
- **Playable Immediately**: Single HTML files, no dependencies
- **Game Library**: Browse, rate, and replay generated games

### 9. Phone Verification System (NEW)
Automated SMS verification using free phone numbers:
- **Multi-Provider**: asms.ai, ReceiveFreeSMS, ReceiveSMS.me
- **Number Pool**: Up to 10 numbers for verifications
- **OTP Extraction**: Automatic code detection from SMS messages
- **Kaggle Integration**: One-click verification for all Kaggle accounts
- **AI Agent Accessible**: Agents can use verification system autonomously

### 10. Book Writer System (NEW)
Complete book writing, storage, and audiobook platform:
- **Book Library**: Create, store, and manage finished works
- **Chapter Management**: Write chapters with word count targets and length tracking
- **AI-Assisted Writing**: SoulIllusions Agent and Prime Agent can write chapters, continue stories, and fix spelling
- **Audiobook Generation**: Text-to-speech for individual chapters or full books
- **Book Analysis Engine**: Extracts characters, plot structure, visual scenes, and game adaptation data
- **Video/Game Integration**: Feeds detailed book data to text-to-video and text-to-game pipelines
- **Export**: TXT, HTML, JSON formats
- **Character & World Building**: Track characters, locations, items, and world elements

### 11. AI Movie & TV Analyzer Engine (NEW)
AI-powered engine that sits on top of the video maker platform:
- **Multi-Source Analysis**: Fetch and analyze movies/TV from YouTube, Facebook, or text descriptions
- **Deep Analysis**: Extracts plot structure, characters, world design, visual style, themes, tone, key scenes, plot twists
- **Movie Combination**: Dissect multiple movies and combine elements into new stories with unique plot twists
- **Game Adaptation**: Extracts world design for game transfer — suggested genre, player character, missions, locations, items
- **Video Adaptation**: Generates visual prompts for characters, scenes, and mood boards
- **Pipeline Integration**: Feeds analysis data to text-to-video and text-to-game for better quality
- **SQLite Storage**: All analyzed movies and combinations stored in movies.db
- **API Endpoints**: Full REST API at /api/movies/*

### 12. JARVIS In-Game Control System (NEW)
Voice and text control system embedded in all games:
- **Cellphone UI**: Small phone icon in bottom right corner — click to open JARVIS interface
- **Voice Control**: Speech recognition for hands-free game control
- **Text Control**: Text tab for typing commands to JARVIS
- **Menu Navigation**: Start game, open settings, pause, resume, restart, quit
- **Movement Control**: Go left/right/up/down, jump, sprint, dodge, crouch
- **Action Control**: Attack, interact, open inventory, open map, save game
- **Character Commands**: Tell character to do things — "go to", "find item", "talk to", "look around"
- **Game-Specific Commands**: Games can register custom JARVIS commands
- **Auto-Injected**: JARVIS is automatically injected into all generated games
- **Developer API**: Games listen for `jarvis-command` events and can register via `jarvisRegisterCommand()`

### 13. Lock & Key Game (NEW)
First game with full JARVIS integration, based on the TV series:
- **Adventure RPG**: Explore Keyhouse, find 3 magical keys, unlock the main door to escape
- **NPCs**: Talk to Bode and Kinsey for clues
- **Enemies**: Shadow enemies that damage the player
- **Items**: Ghost Key, Matchstick Key, Head Key, Health Potion
- **Full JARVIS Support**: Voice/text control for all game functions

## Quick Start

```bash
# Install dependencies
pip install fastapi uvicorn pillow requests

# For local AI agent (free inference)
# Install Ollama: https://ollama.com
ollama pull qwen2.5:7b

# Start the platform
python server.py

# Open http://localhost:7860
```

## How It Works

1. **GPU Backend** runs on Kaggle (free T4 GPU) using open-source models
2. **Local App** runs on your computer and connects to the GPU backend
3. **No API keys, no paid services, no limits**

## Quick Start (GPU Backend)

### Step 1: Start the GPU Backend
1. Run `py kaggle_auto.py` for automatic Kaggle notebook push and tunnel setup
2. Or manually: Upload `SoulIllusions_Kaggle_Backend.ipynb` to Kaggle → Settings → Accelerator → GPU T4 x2 → Internet ON → Run all
3. Copy the Cloudflare tunnel URL (looks like `https://xxxx.trycloudflare.com`)

### Step 2: Launch the App
- Run `python server.py`
- Open http://localhost:7860

### Step 3: Connect & Generate
1. Paste the Cloudflare tunnel URL into the app
2. Click "Connect"
3. Type your video description
4. Click "Generate Video"

## Models Used (2025/2026 State-of-the-Art)

| Model | Resolution | FPS | Duration | Speed (T4) | Best For |
|---|---|---|---|---|---|
| **LTX-Video** (Lightricks) | 768x512 | 24 | ~5s | ~30-60s | Fast generation, good quality |
| **Wan 2.1 1.3B** (Alibaba) | 832x480 | 16 | ~5s | ~15-30min | Best motion quality, Apache 2.0 |
| **CogVideoX-2B** (Tsinghua) | 720x480 | 8 | 6s | ~5-8min | Balanced quality, Apache 2.0 |

## Files

- `server.py` — FastAPI backend with all API endpoints
- `served_page.html` — Frontend UI (all 9 tabs)
- `soulillusions_agent.py` — Always-on AI agent (Magnitude + Prime hybrid)
- `text_to_games.py` — Text-to-games engine
- `sms_verify.py` — Phone verification system
- `kaggle_auto.py` — Kaggle GPU automation
- `kaggle_accounts.json` — Kaggle account configuration
- `SoulIllusions_Kaggle_Backend.ipynb` — Kaggle notebook (GPU backend)
- `generated_games/` — Generated HTML5 games

## Requirements

- Python 3.8+ with `fastapi`, `uvicorn`, `pydantic`
- Kaggle account (for free T4 GPU access)
- [Ollama](https://ollama.com) (for free local AI agent inference)
- Internet connection

## License

MIT
