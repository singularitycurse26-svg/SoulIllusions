"""
SoulIllusions Text-to-Games Engine
===================================
State-of-the-art text-to-game generation inspired by:
- WorldGen (CVPR 2026): Text → navigable 3D worlds
- AutoUE (ACL 2026): Multi-agent game generation in Unreal Engine
- Yume1.5 (CVPR 2026): Text-controlled interactive world generation
- Luddi/OpenGame: Instant HTML5 game generation from text
- Summer Engine: Godot-compatible project generation from text

Implementation:
- Generates complete, playable HTML5 games from text prompts
- Supports: platformers, shooters, puzzles, racing, arcade, strategy, RPG
- AI-controlled game generation with customizable parameters
- Games are single HTML files — instantly playable, shareable, embeddable
- Both user and AI agents can create games
- Game templates + AI code generation for custom mechanics
"""

import json, os, re, time, asyncio, sqlite3
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
GAMES_DB = SCRIPT_DIR / "games.db"
GAMES_DIR = SCRIPT_DIR / "generated_games"
GAMES_DIR.mkdir(exist_ok=True)

# Import LLM interface from agent module
try:
    from soulillusions_agent import LLMInterface, load_config as load_agent_config
except ImportError:
    # Fallback if run standalone
    def load_agent_config():
        return {"mode": "local", "local_model": "qwen2.5:7b", "local_inference_url": "http://localhost:11434"}


# --- Database ---
def init_db():
    conn = sqlite3.connect(str(GAMES_DB))
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            genre TEXT,
            prompt TEXT NOT NULL,
            html_content TEXT,
            file_path TEXT,
            status TEXT DEFAULT 'generated',
            rating INTEGER DEFAULT 0,
            plays INTEGER DEFAULT 0,
            parameters TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            created_by TEXT DEFAULT 'user',
            metadata TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS game_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            genre TEXT NOT NULL,
            description TEXT,
            html_template TEXT NOT NULL,
            parameters TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS game_tasks (
            id TEXT PRIMARY KEY,
            game_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            type TEXT DEFAULT 'objective',
            completed INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT,
            FOREIGN KEY (game_id) REFERENCES games(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS game_upgrades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            agent TEXT,
            request TEXT,
            response TEXT,
            upgrade_summary TEXT,
            applied INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (game_id) REFERENCES games(id)
        )
    """)
    conn.commit()
    conn.close()


init_db()


# --- Game Templates ---
PLATFORMER_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}}</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #1a1a2e; display: flex; justify-content: center; align-items: center; height: 100vh; font-family: monospace; }
canvas { border: 2px solid #e94560; border-radius: 8px; }
#ui { position: absolute; top: 10px; left: 50%; transform: translateX(-50%); color: #fff; font-size: 18px; z-index: 10; }
#controls { position: absolute; bottom: 10px; left: 50%; transform: translateX(-50%); color: #aaa; font-size: 12px; }
</style>
</head>
<body>
<div id="ui">Score: <span id="score">0</span> | Lives: <span id="lives">3</span> | Level: <span id="level">1</span></div>
<canvas id="game" width="800" height="500"></canvas>
<div id="controls">Arrow Keys / WASD to move | Space to jump</div>
<script>
const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const W = canvas.width, H = canvas.height;

// Game state
let score = 0, lives = 3, level = 1, gameRunning = true;
const gravity = 0.5;
const friction = 0.8;

// Player
const player = { x: 50, y: 300, w: 30, h: 40, vx: 0, vy: 0, speed: 5, jumpPower: 12, onGround: false, color: '#e94560' };

// Platforms
let platforms = [
    { x: 0, y: 480, w: W, h: 20 },
    { x: 200, y: 400, w: 120, h: 15 },
    { x: 400, y: 320, w: 120, h: 15 },
    { x: 600, y: 250, w: 120, h: 15 },
    { x: 100, y: 200, w: 100, h: 15 },
    { x: 350, y: 150, w: 100, h: 15 },
];

// Collectibles
let coins = [
    { x: 250, y: 370, r: 10, collected: false },
    { x: 450, y: 290, r: 10, collected: false },
    { x: 650, y: 220, r: 10, collected: false },
    { x: 150, y: 170, r: 10, collected: false },
    { x: 400, y: 120, r: 10, collected: false },
];

// Enemies
let enemies = [
    { x: 300, y: 460, w: 25, h: 20, vx: 2, color: '#0f3460' },
    { x: 500, y: 460, w: 25, h: 20, vx: -2, color: '#0f3460' },
];

// Goal
let goal = { x: 750, y: 100, w: 30, h: 40, color: '#16213e' };

const keys = {};
document.addEventListener('keydown', e => { keys[e.key.toLowerCase()] = true; keys[e.code] = true; });
document.addEventListener('keyup', e => { keys[e.key.toLowerCase()] = false; keys[e.code] = false; });

function update() {
    if (!gameRunning) return;
    
    // Player movement
    if (keys['arrowleft'] || keys['a']) player.vx -= player.speed * 0.3;
    if (keys['arrowright'] || keys['d']) player.vx += player.speed * 0.3;
    if ((keys[' '] || keys['space'] || keys['arrowup'] || keys['w']) && player.onGround) {
        player.vy = -player.jumpPower;
        player.onGround = false;
    }
    
    // Physics
    player.vx *= friction;
    player.vy += gravity;
    player.x += player.vx;
    player.y += player.vy;
    
    // Platform collision
    player.onGround = false;
    for (let p of platforms) {
        if (player.x < p.x + p.w && player.x + player.w > p.x && player.y < p.y + p.h && player.y + player.h > p.y) {
            if (player.vy > 0 && player.y + player.h - player.vy <= p.y + 5) {
                player.y = p.y - player.h;
                player.vy = 0;
                player.onGround = true;
            }
        }
    }
    
    // Boundaries
    if (player.x < 0) player.x = 0;
    if (player.x + player.w > W) player.x = W - player.w;
    if (player.y > H) { lives--; player.x = 50; player.y = 300; if (lives <= 0) gameOver(); }
    
    // Coins
    for (let c of coins) {
        if (!c.collected) {
            let dx = (player.x + player.w/2) - c.x;
            let dy = (player.y + player.h/2) - c.y;
            if (Math.sqrt(dx*dx + dy*dy) < c.r + 15) {
                c.collected = true;
                score += 10;
            }
        }
    }
    
    // Enemies
    for (let e of enemies) {
        e.x += e.vx;
        if (e.x < 0 || e.x + e.w > W) e.vx *= -1;
        if (player.x < e.x + e.w && player.x + player.w > e.x && player.y < e.y + e.h && player.y + player.h > e.y) {
            lives--;
            player.x = 50; player.y = 300;
            if (lives <= 0) gameOver();
        }
    }
    
    // Goal
    if (player.x < goal.x + goal.w && player.x + player.w > goal.x && player.y < goal.y + goal.h && player.y + player.h > goal.y) {
        level++;
        score += 100;
        nextLevel();
    }
    
    document.getElementById('score').textContent = score;
    document.getElementById('lives').textContent = lives;
    document.getElementById('level').textContent = level;
}

function nextLevel() {
    player.x = 50; player.y = 300;
    coins.forEach(c => c.collected = false);
    // Add more enemies
    if (level % 2 === 0) {
        enemies.push({ x: Math.random() * W, y: 460, w: 25, h: 20, vx: (Math.random() > 0.5 ? 2 : -2) * (1 + level * 0.1), color: '#0f3460' });
    }
}

function gameOver() {
    gameRunning = false;
    ctx.fillStyle = 'rgba(0,0,0,0.7)';
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#e94560';
    ctx.font = '48px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('GAME OVER', W/2, H/2);
    ctx.font = '20px monospace';
    ctx.fillStyle = '#fff';
    ctx.fillText(`Score: ${score} | Level: ${level}`, W/2, H/2 + 40);
    ctx.fillText('Press R to restart', W/2, H/2 + 70);
}

function draw() {
    // Background
    ctx.fillStyle = '#16213e';
    ctx.fillRect(0, 0, W, H);
    
    // Platforms
    ctx.fillStyle = '#e94560';
    for (let p of platforms) ctx.fillRect(p.x, p.y, p.w, p.h);
    
    // Coins
    ctx.fillStyle = '#f5a623';
    for (let c of coins) {
        if (!c.collected) {
            ctx.beginPath();
            ctx.arc(c.x, c.y, c.r, 0, Math.PI * 2);
            ctx.fill();
        }
    }
    
    // Enemies
    for (let e of enemies) {
        ctx.fillStyle = e.color;
        ctx.fillRect(e.x, e.y, e.w, e.h);
    }
    
    // Goal
    ctx.fillStyle = goal.color;
    ctx.fillRect(goal.x, goal.y, goal.w, goal.h);
    ctx.fillStyle = '#e94560';
    ctx.font = '14px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('GOAL', goal.x + goal.w/2, goal.y - 5);
    
    // Player
    ctx.fillStyle = player.color;
    ctx.fillRect(player.x, player.y, player.w, player.h);
    
    if (!gameRunning) {
        document.addEventListener('keydown', e => {
            if (e.key.toLowerCase() === 'r') location.reload();
        }, { once: true });
    }
}

function loop() {
    update();
    draw();
    requestAnimationFrame(loop);
}

loop();
</script>
</body>
</html>'''


SHOOTER_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}}</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0a0a0a; display: flex; justify-content: center; align-items: center; height: 100vh; font-family: monospace; }
canvas { border: 2px solid #00ff41; border-radius: 8px; cursor: crosshair; }
#ui { position: absolute; top: 10px; left: 50%; transform: translateX(-50%); color: #00ff41; font-size: 18px; z-index: 10; }
</style>
</head>
<body>
<div id="ui">Score: <span id="score">0</span> | Wave: <span id="wave">1</span> | Health: <span id="health">100</span></div>
<canvas id="game" width="800" height="500"></canvas>
<script>
const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const W = canvas.width, H = canvas.height;

let score = 0, wave = 1, health = 100, gameRunning = true;
let bullets = [], enemies = [], particles = [];
let spawnTimer = 0, spawnRate = 60;

const player = { x: W/2, y: H - 60, w: 40, h: 40, speed: 5, color: '#00ff41' };
const keys = {};
let mouseX = W/2, mouseY = H/2;

document.addEventListener('keydown', e => keys[e.key.toLowerCase()] = true);
document.addEventListener('keyup', e => keys[e.key.toLowerCase()] = false);
canvas.addEventListener('mousemove', e => {
    const r = canvas.getBoundingClientRect();
    mouseX = e.clientX - r.left;
    mouseY = e.clientY - r.top;
});
canvas.addEventListener('mousedown', () => shoot());

function shoot() {
    let dx = mouseX - (player.x + player.w/2);
    let dy = mouseY - (player.y + player.h/2);
    let len = Math.sqrt(dx*dx + dy*dy);
    bullets.push({ x: player.x + player.w/2, y: player.y + player.h/2, vx: (dx/len)*8, vy: (dy/len)*8, r: 4 });
}

function spawnEnemy() {
    let side = Math.floor(Math.random() * 4);
    let x, y;
    if (side === 0) { x = Math.random() * W; y = -20; }
    else if (side === 1) { x = W + 20; y = Math.random() * H; }
    else if (side === 2) { x = Math.random() * W; y = H + 20; }
    else { x = -20; y = Math.random() * H; }
    let dx = (player.x + player.w/2) - x;
    let dy = (player.y + player.h/2) - y;
    let len = Math.sqrt(dx*dx + dy*dy);
    let speed = 1 + wave * 0.2;
    enemies.push({ x, y, w: 30, h: 30, vx: (dx/len)*speed, vy: (dy/len)*speed, hp: 1 + Math.floor(wave/3), color: '#ff0040' });
}

function update() {
    if (!gameRunning) return;
    
    if (keys['a'] || keys['arrowleft']) player.x -= player.speed;
    if (keys['d'] || keys['arrowright']) player.x += player.speed;
    if (keys['w'] || keys['arrowup']) player.y -= player.speed;
    if (keys['s'] || keys['arrowdown']) player.y += player.speed;
    player.x = Math.max(0, Math.min(W - player.w, player.x));
    player.y = Math.max(0, Math.min(H - player.h, player.y));
    
    bullets.forEach((b, i) => {
        b.x += b.vx; b.y += b.vy;
        if (b.x < 0 || b.x > W || b.y < 0 || b.y > H) bullets.splice(i, 1);
    });
    
    spawnTimer++;
    if (spawnTimer >= spawnRate) { spawnEnemy(); spawnTimer = 0; }
    
    enemies.forEach((e, ei) => {
        e.x += e.vx; e.y += e.vy;
        bullets.forEach((b, bi) => {
            if (b.x > e.x && b.x < e.x + e.w && b.y > e.y && b.y < e.y + e.h) {
                e.hp--;
                bullets.splice(bi, 1);
                for (let i = 0; i < 5; i++) particles.push({ x: b.x, y: b.y, vx: (Math.random()-0.5)*4, vy: (Math.random()-0.5)*4, life: 20, color: '#ff0040' });
                if (e.hp <= 0) { enemies.splice(ei, 1); score += 10 * wave; }
            }
        });
        if (player.x < e.x + e.w && player.x + player.w > e.x && player.y < e.y + e.h && player.y + player.h > e.y) {
            health -= 10;
            enemies.splice(ei, 1);
            if (health <= 0) gameOver();
        }
    });
    
    particles.forEach((p, i) => { p.x += p.vx; p.y += p.vy; p.life--; if (p.life <= 0) particles.splice(i, 1); });
    
    if (enemies.length === 0 && spawnTimer > 30) { wave++; spawnRate = Math.max(20, 60 - wave * 3); }
    
    document.getElementById('score').textContent = score;
    document.getElementById('wave').textContent = wave;
    document.getElementById('health').textContent = Math.max(0, health);
}

function gameOver() {
    gameRunning = false;
    ctx.fillStyle = 'rgba(0,0,0,0.8)';
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#ff0040';
    ctx.font = '48px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('GAME OVER', W/2, H/2);
    ctx.font = '20px monospace';
    ctx.fillStyle = '#00ff41';
    ctx.fillText(`Score: ${score} | Wave: ${wave}`, W/2, H/2 + 40);
    ctx.fillText('Press R to restart', W/2, H/2 + 70);
    document.addEventListener('keydown', e => { if (e.key.toLowerCase() === 'r') location.reload(); }, { once: true });
}

function draw() {
    ctx.fillStyle = '#0a0a0a';
    ctx.fillRect(0, 0, W, H);
    
    // Grid
    ctx.strokeStyle = '#111';
    for (let x = 0; x < W; x += 40) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
    for (let y = 0; y < H; y += 40) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
    
    // Aim line
    ctx.strokeStyle = 'rgba(0,255,65,0.2)';
    ctx.beginPath();
    ctx.moveTo(player.x + player.w/2, player.y + player.h/2);
    ctx.lineTo(mouseX, mouseY);
    ctx.stroke();
    
    ctx.fillStyle = '#00ff41';
    bullets.forEach(b => { ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, Math.PI*2); ctx.fill(); });
    
    enemies.forEach(e => { ctx.fillStyle = e.color; ctx.fillRect(e.x, e.y, e.w, e.h); });
    
    particles.forEach(p => { ctx.fillStyle = p.color; ctx.globalAlpha = p.life/20; ctx.fillRect(p.x, p.y, 3, 3); ctx.globalAlpha = 1; });
    
    ctx.fillStyle = player.color;
    ctx.fillRect(player.x, player.y, player.w, player.h);
}

function loop() { update(); draw(); requestAnimationFrame(loop); }
loop();
</script>
</body>
</html>'''


PUZZLE_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}}</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #1a1a2e; display: flex; justify-content: center; align-items: center; height: 100vh; font-family: monospace; }
#game-container { text-align: center; }
canvas { border: 2px solid #e94560; border-radius: 8px; }
#ui { color: #fff; font-size: 18px; margin-bottom: 10px; }
</style>
</head>
<body>
<div id="game-container">
<div id="ui">Moves: <span id="moves">0</span> | Best: <span id="best">-</span></div>
<canvas id="game" width="400" height="400"></canvas>
</div>
<script>
const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const SIZE = 4;
const CELL = 90;
const GAP = 5;
const W = canvas.width, H = canvas.height;

let grid = [], moves = 0, best = localStorage.getItem('puzzleBest') || '-';
let selected = null;

function init() {
    grid = [];
    let nums = [];
    for (let i = 1; i < SIZE * SIZE; i++) nums.push(i);
    nums.push(0);
    // Shuffle
    for (let i = nums.length - 1; i > 0; i--) {
        let j = Math.floor(Math.random() * (i + 1));
        [nums[i], nums[j]] = [nums[j], nums[i]];
    }
    for (let r = 0; r < SIZE; r++) {
        grid.push([]);
        for (let c = 0; c < SIZE; c++) grid[r].push(nums[r * SIZE + c]);
    }
    moves = 0;
}

canvas.addEventListener('click', e => {
    const r = canvas.getBoundingClientRect();
    const x = e.clientX - r.left;
    const y = e.clientY - r.top;
    const c = Math.floor(x / (CELL + GAP));
    const r2 = Math.floor(y / (CELL + GAP));
    if (r2 < 0 || r2 >= SIZE || c < 0 || c >= SIZE) return;
    
    // Find empty
    let er = -1, ec = -1;
    for (let r = 0; r < SIZE; r++) for (let c = 0; c < SIZE; c++) if (grid[r][c] === 0) { er = r; ec = c; }
    
    // Check adjacent
    if ((Math.abs(r2 - er) === 1 && c === ec) || (Math.abs(c - ec) === 1 && r2 === er)) {
        grid[er][ec] = grid[r2][c];
        grid[r2][c] = 0;
        moves++;
        document.getElementById('moves').textContent = moves;
        checkWin();
    }
});

function checkWin() {
    let n = 1;
    for (let r = 0; r < SIZE; r++) for (let c = 0; c < SIZE; c++) {
        if (r === SIZE - 1 && c === SIZE - 1) { if (grid[r][c] === 0) { win(); return; } else return; }
        if (grid[r][c] !== n++) return;
    }
}

function win() {
    if (best === '-' || moves < parseInt(best)) {
        best = moves;
        localStorage.setItem('puzzleBest', best);
        document.getElementById('best').textContent = best;
    }
    ctx.fillStyle = 'rgba(233,69,96,0.9)';
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#fff';
    ctx.font = '36px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('SOLVED!', W/2, H/2);
    ctx.font = '18px monospace';
    ctx.fillText(`${moves} moves`, W/2, H/2 + 35);
    ctx.fillText('Click to play again', W/2, H/2 + 60);
    canvas.addEventListener('click', () => { init(); }, { once: true });
}

function draw() {
    ctx.fillStyle = '#16213e';
    ctx.fillRect(0, 0, W, H);
    
    for (let r = 0; r < SIZE; r++) {
        for (let c = 0; c < SIZE; c++) {
            const x = c * (CELL + GAP) + GAP;
            const y = r * (CELL + GAP) + GAP;
            if (grid[r][c] === 0) {
                ctx.fillStyle = '#0f3460';
            } else {
                ctx.fillStyle = '#e94560';
            }
            ctx.fillRect(x, y, CELL, CELL);
            if (grid[r][c] !== 0) {
                ctx.fillStyle = '#fff';
                ctx.font = '36px monospace';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(grid[r][c], x + CELL/2, y + CELL/2);
            }
        }
    }
}

function loop() { draw(); requestAnimationFrame(loop); }
init();
loop();
</script>
</body>
</html>'''


RACING_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}}</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #1a1a2e; display: flex; justify-content: center; align-items: center; height: 100vh; font-family: monospace; }
canvas { border: 2px solid #e94560; border-radius: 8px; }
#ui { position: absolute; top: 10px; left: 50%; transform: translateX(-50%); color: #fff; font-size: 18px; z-index: 10; }
</style>
</head>
<body>
<div id="ui">Lap: <span id="lap">1</span>/3 | Time: <span id="time">0.0</span>s | Speed: <span id="speed">0</span></div>
<canvas id="game" width="800" height="500"></canvas>
<script>
const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const W = canvas.width, H = canvas.height;

let car = { x: 100, y: 250, angle: 0, speed: 0, w: 20, h: 40, maxSpeed: 8, accel: 0.2, turnSpeed: 0.05 };
let lap = 1, startTime = Date.now(), gameRunning = true;
let checkpoints = [
    { x: 700, y: 100, passed: false },
    { x: 700, y: 400, passed: false },
    { x: 100, y: 400, passed: false },
    { x: 100, y: 100, passed: false },
];
let allPassed = false;

const keys = {};
document.addEventListener('keydown', e => keys[e.key.toLowerCase()] = true);
document.addEventListener('keyup', e => keys[e.key.toLowerCase()] = false);

// Track boundaries (oval)
function isOnTrack(x, y) {
    let cx = W/2, cy = H/2;
    let dx = (x - cx) / (W/2 - 50);
    let dy = (y - cy) / (H/2 - 50);
    let outer = dx*dx + dy*dy;
    let dx2 = (x - cx) / (W/2 - 150);
    let dy2 = (y - cy) / (H/2 - 150);
    let inner = dx2*dx2 + dy2*dy2;
    return outer <= 1 && inner >= 1;
}

function update() {
    if (!gameRunning) return;
    
    if (keys['w'] || keys['arrowup']) car.speed = Math.min(car.maxSpeed, car.speed + car.accel);
    else if (keys['s'] || keys['arrowdown']) car.speed = Math.max(-car.maxSpeed/2, car.speed - car.accel);
    else car.speed *= 0.95;
    
    if (Math.abs(car.speed) > 0.1) {
        if (keys['a'] || keys['arrowleft']) car.angle -= car.turnSpeed * (car.speed / car.maxSpeed);
        if (keys['d'] || keys['arrowright']) car.angle += car.turnSpeed * (car.speed / car.maxSpeed);
    }
    
    let nx = car.x + Math.cos(car.angle) * car.speed;
    let ny = car.y + Math.sin(car.angle) * car.speed;
    
    if (isOnTrack(nx, ny)) { car.x = nx; car.y = ny; }
    else { car.speed *= 0.5; }
    
    // Checkpoints
    checkpoints.forEach(cp => {
        if (!cp.passed && Math.abs(car.x - cp.x) < 40 && Math.abs(car.y - cp.y) < 40) {
            cp.passed = true;
        }
    });
    
    if (checkpoints.every(cp => cp.passed)) {
        lap++;
        checkpoints.forEach(cp => cp.passed = false);
        if (lap > 3) gameOver();
    }
    
    document.getElementById('lap').textContent = Math.min(lap, 3);
    document.getElementById('time').textContent = ((Date.now() - startTime) / 1000).toFixed(1);
    document.getElementById('speed').textContent = Math.abs(Math.round(car.speed * 20));
}

function gameOver() {
    gameRunning = false;
    let finalTime = ((Date.now() - startTime) / 1000).toFixed(1);
    ctx.fillStyle = 'rgba(0,0,0,0.8)';
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#e94560';
    ctx.font = '48px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('FINISH!', W/2, H/2);
    ctx.fillStyle = '#fff';
    ctx.font = '24px monospace';
    ctx.fillText(`Time: ${finalTime}s`, W/2, H/2 + 40);
    ctx.fillText('Press R to restart', W/2, H/2 + 70);
    document.addEventListener('keydown', e => { if (e.key.toLowerCase() === 'r') location.reload(); }, { once: true });
}

function draw() {
    // Grass
    ctx.fillStyle = '#0f3460';
    ctx.fillRect(0, 0, W, H);
    
    // Track (oval)
    ctx.fillStyle = '#333';
    ctx.beginPath();
    ctx.ellipse(W/2, H/2, W/2 - 50, H/2 - 50, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#0f3460';
    ctx.beginPath();
    ctx.ellipse(W/2, H/2, W/2 - 150, H/2 - 150, 0, 0, Math.PI * 2);
    ctx.fill();
    
    // Checkpoints
    checkpoints.forEach(cp => {
        ctx.fillStyle = cp.passed ? '#00ff41' : '#e94560';
        ctx.beginPath();
        ctx.arc(cp.x, cp.y, 10, 0, Math.PI * 2);
        ctx.fill();
    });
    
    // Car
    ctx.save();
    ctx.translate(car.x, car.y);
    ctx.rotate(car.angle);
    ctx.fillStyle = '#e94560';
    ctx.fillRect(-car.w/2, -car.h/2, car.w, car.h);
    ctx.fillStyle = '#fff';
    ctx.fillRect(-car.w/2, -car.h/2 + 5, car.w, 5);
    ctx.restore();
}

function loop() { update(); draw(); requestAnimationFrame(loop); }
loop();
</script>
</body>
</html>'''


ARCADE_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}}</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #000; display: flex; justify-content: center; align-items: center; height: 100vh; font-family: monospace; }
canvas { border: 2px solid #fff; border-radius: 8px; }
#ui { position: absolute; top: 10px; left: 50%; transform: translateX(-50%); color: #fff; font-size: 18px; z-index: 10; }
</style>
</head>
<body>
<div id="ui">Score: <span id="score">0</span> | Lives: <span id="lives">3</span></div>
<canvas id="game" width="600" height="400"></canvas>
<script>
const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const W = canvas.width, H = canvas.height;

let score = 0, lives = 3, gameRunning = true;
let paddle = { x: W/2 - 40, y: H - 20, w: 80, h: 10, speed: 8 };
let ball = { x: W/2, y: H/2, vx: 4, vy: -4, r: 8 };
let bricks = [];
let particles = [];

const COLS = 10, ROWS = 5;
const BRICK_W = 50, BRICK_H = 20, BRICK_GAP = 4;
const COLORS = ['#ff0040', '#ff4080', '#ff8040', '#40ff80', '#4080ff'];

function initBricks() {
    bricks = [];
    for (let r = 0; r < ROWS; r++) {
        for (let c = 0; c < COLS; c++) {
            bricks.push({ x: c * (BRICK_W + BRICK_GAP) + 20, y: r * (BRICK_H + BRICK_GAP) + 30, w: BRICK_W, h: BRICK_H, color: COLORS[r % COLORS.length], alive: true });
        }
    }
}
initBricks();

const keys = {};
document.addEventListener('keydown', e => keys[e.key.toLowerCase()] = true);
document.addEventListener('keyup', e => keys[e.key.toLowerCase()] = false);
canvas.addEventListener('mousemove', e => {
    const r = canvas.getBoundingClientRect();
    paddle.x = Math.max(0, Math.min(W - paddle.w, e.clientX - r.left - paddle.w/2));
});

function update() {
    if (!gameRunning) return;
    
    if (keys['a'] || keys['arrowleft']) paddle.x = Math.max(0, paddle.x - paddle.speed);
    if (keys['d'] || keys['arrowright']) paddle.x = Math.min(W - paddle.w, paddle.x + paddle.speed);
    
    ball.x += ball.vx;
    ball.y += ball.vy;
    
    if (ball.x < ball.r || ball.x > W - ball.r) ball.vx *= -1;
    if (ball.y < ball.r) ball.vy *= -1;
    
    if (ball.y > H) { lives--; ball.x = W/2; ball.y = H/2; ball.vx = 4; ball.vy = -4; if (lives <= 0) gameOver(); }
    
    if (ball.y + ball.r > paddle.y && ball.x > paddle.x && ball.x < paddle.x + paddle.w && ball.vy > 0) {
        ball.vy *= -1;
        let hit = (ball.x - (paddle.x + paddle.w/2)) / (paddle.w/2);
        ball.vx = hit * 6;
    }
    
    bricks.forEach(b => {
        if (b.alive && ball.x > b.x && ball.x < b.x + b.w && ball.y > b.y && ball.y < b.y + b.h) {
            b.alive = false;
            ball.vy *= -1;
            score += 10;
            for (let i = 0; i < 8; i++) particles.push({ x: b.x + b.w/2, y: b.y + b.h/2, vx: (Math.random()-0.5)*6, vy: (Math.random()-0.5)*6, life: 30, color: b.color });
        }
    });
    
    particles.forEach((p, i) => { p.x += p.vx; p.y += p.vy; p.life--; if (p.life <= 0) particles.splice(i, 1); });
    
    if (bricks.every(b => !b.alive)) { initBricks(); ball.vx *= 1.1; ball.vy *= 1.1; }
    
    document.getElementById('score').textContent = score;
    document.getElementById('lives').textContent = lives;
}

function gameOver() {
    gameRunning = false;
    ctx.fillStyle = 'rgba(0,0,0,0.8)';
    ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#fff';
    ctx.font = '48px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('GAME OVER', W/2, H/2);
    ctx.font = '20px monospace';
    ctx.fillText(`Score: ${score}`, W/2, H/2 + 40);
    ctx.fillText('Press R to restart', W/2, H/2 + 70);
    document.addEventListener('keydown', e => { if (e.key.toLowerCase() === 'r') location.reload(); }, { once: true });
}

function draw() {
    ctx.fillStyle = '#000';
    ctx.fillRect(0, 0, W, H);
    
    bricks.forEach(b => { if (b.alive) { ctx.fillStyle = b.color; ctx.fillRect(b.x, b.y, b.w, b.h); } });
    
    particles.forEach(p => { ctx.fillStyle = p.color; ctx.globalAlpha = p.life/30; ctx.fillRect(p.x, p.y, 4, 4); ctx.globalAlpha = 1; });
    
    ctx.fillStyle = '#fff';
    ctx.fillRect(paddle.x, paddle.y, paddle.w, paddle.h);
    ctx.beginPath();
    ctx.arc(ball.x, ball.y, ball.r, 0, Math.PI * 2);
    ctx.fill();
}

function loop() { update(); draw(); requestAnimationFrame(loop); }
loop();
</script>
</body>
</html>'''


# --- Lock & Key TV Series Game Template ---
LOCK_AND_KEY_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Lock & Key</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #0a0a15; display: flex; justify-content: center; align-items: center; height: 100vh; font-family: 'Georgia', serif; overflow: hidden; }
canvas { border: 2px solid #1a1a2e; border-radius: 4px; }
#ui { position: absolute; top: 10px; left: 50%; transform: translateX(-50%); color: #c4a35a; font-size: 16px; z-index: 10; text-shadow: 0 0 10px rgba(196,163,90,0.5); }
#objective { position: absolute; top: 40px; left: 50%; transform: translateX(-50%); color: #888; font-size: 13px; z-index: 10; }
#dialogue { position: absolute; bottom: 80px; left: 50%; transform: translateX(-50%); width: 500px; background: rgba(15,15,30,0.9); border: 1px solid #c4a35a; border-radius: 8px; padding: 15px; color: #ddd; font-size: 14px; z-index: 10; display: none; }
#dialogue .speaker { color: #c4a35a; font-weight: bold; margin-bottom: 5px; }
#menu { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(10,10,21,0.95); z-index: 20; display: flex; flex-direction: column; justify-content: center; align-items: center; }
#menu h1 { color: #c4a35a; font-size: 48px; margin-bottom: 10px; text-shadow: 0 0 20px rgba(196,163,90,0.3); }
#menu p { color: #888; margin-bottom: 30px; font-size: 14px; }
#menu button { background: #1a1a2e; border: 1px solid #c4a35a; color: #c4a35a; padding: 12px 40px; margin: 5px; cursor: pointer; font-size: 16px; border-radius: 4px; font-family: 'Georgia', serif; transition: all 0.3s; }
#menu button:hover { background: #c4a35a; color: #0a0a15; }
</style>
</head>
<body>
<div id="menu">
  <h1>Lock &amp; Key</h1>
  <p>Based on the TV Series · A SoulIllusions Game</p>
  <button onclick="startGame()">Start Game</button>
  <button onclick="showSettings()">Settings</button>
  <button onclick="showAbout()">About</button>
</div>
<div id="ui">Keys: <span id="keys">0</span> / 3 | Health: <span id="health">100</span></div>
<div id="objective"></div>
<div id="dialogue"><div class="speaker"></div><div class="text"></div></div>
<canvas id="game" width="800" height="500"></canvas>
<script>
const canvas = document.getElementById('game');
const ctx = canvas.getContext('2d');
const W = canvas.width, H = canvas.height;

var game = {
  running: false,
  paused: false,
  player: { x: 100, y: 250, w: 24, h: 36, speed: 3, health: 100, hasKey: false },
  keys: 0,
  totalKeys: 3,
  level: 1,
  doors: [],
  items: [],
  enemies: [],
  walls: [],
  npcs: [],
  currentRoom: 0,
  rooms: [],
  inventory: [],
  dialogueActive: false,
  objective: "Find the 3 keys to unlock the main door"
};

var input = {};
document.addEventListener('keydown', function(e) { input[e.key.toLowerCase()] = true; if (e.key === 'e') interact(); });
document.addEventListener('keyup', function(e) { input[e.key.toLowerCase()] = false; });

// Listen for JARVIS commands
document.addEventListener('jarvis-command', function(e) {
  var cmd = e.detail.action;
  var params = e.detail.params;
  switch(cmd) {
    case 'start': startGame(); break;
    case 'pause': game.paused = true; break;
    case 'resume': game.paused = false; break;
    case 'restart': location.reload(); break;
    case 'menu': showMenu(); break;
    case 'move': movePlayer(params.direction); break;
    case 'jump': game.player.y -= 30; break;
    case 'attack': attack(); break;
    case 'interact': interact(); break;
    case 'inventory': showInventory(); break;
    case 'settings': showSettings(); break;
    case 'character_command': handleCharacterCommand(params.command); break;
  }
});

// Register game-specific JARVIS commands
if (window.jarvisRegisterCommand) {
  jarvisRegisterCommand('use key', function() { if (game.player.hasKey) { useKey(); return "Using key on door."; } return "No key in inventory."; });
  jarvisRegisterCommand('open door', function() { interact(); return "Opening door."; });
  jarvisRegisterCommand('check inventory', function() { showInventory(); return "You have: " + (game.inventory.length ? game.inventory.join(', ') : 'nothing'); });
  jarvisRegisterCommand('where am i', function() { return "You are in room " + (game.currentRoom + 1) + " of the Keyhouse. Objective: " + game.objective; });
}

function startGame() {
  document.getElementById('menu').style.display = 'none';
  game.running = true;
  game.paused = false;
  initLevel();
  if (window.jarvisSetContext) jarvisSetContext({level: game.level, objective: game.objective, keys: game.keys});
  // Initialize in-game tasks
  if (window.jarvisAddTask) {
    jarvisAddTask('Find the Ghost Key', 'Located in the upper-left area of Keyhouse', 'objective');
    jarvisAddTask('Find the Matchstick Key', 'Hidden in the center-right section', 'objective');
    jarvisAddTask('Find the Head Key', 'Near the top-right corner', 'objective');
    jarvisAddTask('Unlock the main door', 'Requires all 3 keys', 'objective');
    jarvisAddTask('Talk to Bode', 'Find Bode for hints about the keys', 'side');
    jarvisAddTask('Talk to Kinsey', 'Kinsey may have useful information', 'side');
    jarvisAddTask('Defeat all shadows', 'Eliminate the shadow enemies', 'challenge');
  }
  loop();
}

function showMenu() {
  document.getElementById('menu').style.display = 'flex';
  game.paused = true;
}

function showSettings() {
  showDialogue('Settings', 'Volume: 100% | Difficulty: Normal | Controls: WASD/Arrows + E to interact | JARVIS: Active');
}

function showAbout() {
  showDialogue('About', 'Lock & Key - Based on the TV series. Explore Keyhouse, find magical keys, unlock doors, and discover the mystery. Use JARVIS (bottom right) for voice/text control.');
}

function initLevel() {
  game.walls = [
    {x:0, y:0, w:W, h:20}, {x:0, y:H-20, w:W, h:20},
    {x:0, y:0, w:20, h:H}, {x:W-20, y:0, w:20, h:H},
    {x:200, y:100, w:20, h:150}, {x:400, y:200, w:20, h:200},
    {x:550, y:50, w:20, h:180}, {x:300, y:350, w:150, h:20},
  ];
  game.doors = [
    {x: 200, y: 80, w: 30, h: 20, locked: true, keyId: 0},
    {x: 550, y: 230, w: 30, h: 20, locked: true, keyId: 1},
    {x: W-50, y: 250, w: 20, h: 60, locked: true, keyId: 2, isExit: true},
  ];
  game.items = [
    {x: 250, y: 150, type: 'key', id: 0, name: 'Ghost Key', collected: false},
    {x: 450, y: 300, type: 'key', id: 1, name: 'Matchstick Key', collected: false},
    {x: 600, y: 100, type: 'key', id: 2, name: 'Head Key', collected: false},
    {x: 100, y: 400, type: 'health', name: 'Health Potion', collected: false},
  ];
  game.enemies = [
    {x: 350, y: 150, w: 20, h: 30, speed: 1, health: 30, dir: 1},
    {x: 500, y: 350, w: 20, h: 30, speed: 1.5, health: 30, dir: -1},
  ];
  game.npcs = [
    {x: 120, y: 300, name: 'Bode', dialogue: 'The keys are hidden in the house. Find them all to unlock the main door.'},
    {x: 650, y: 400, name: 'Kinsey', dialogue: 'Be careful, there are shadows in the house. Use E to interact with objects.'},
  ];
  game.player.x = 100; game.player.y = 250;
  game.keys = 0;
  game.objective = 'Find the 3 keys to unlock the main door';
  document.getElementById('objective').textContent = game.objective;
  updateUI();
}

function movePlayer(dir) {
  if (!game.running || game.paused) return;
  var p = game.player;
  if (dir === 'left') p.x -= p.speed * 3;
  if (dir === 'right') p.x += p.speed * 3;
  if (dir === 'up') p.y -= p.speed * 3;
  if (dir === 'down') p.y += p.speed * 3;
  clampPlayer();
}

function attack() {
  var p = game.player;
  game.enemies.forEach(function(en) {
    var dx = en.x - p.x, dy = en.y - p.y;
    if (Math.sqrt(dx*dx + dy*dy) < 50) {
      en.health -= 15;
      if (en.health <= 0) { en.dead = true; }
    }
  });
}

function interact() {
  if (!game.running) return;
  var p = game.player;
  // Check items
  game.items.forEach(function(item) {
    if (item.collected) return;
    var dx = item.x - p.x, dy = item.y - p.y;
    if (Math.sqrt(dx*dx + dy*dy) < 35) {
      item.collected = true;
      if (item.type === 'key') {
        game.keys++;
        game.inventory.push(item.name);
        showDialogue('Found', 'You found the ' + item.name + '! (' + game.keys + '/' + game.totalKeys + ' keys)');
        if (window.jarvisSpeak) jarvisSpeak('You found the ' + item.name);
        if (window.jarvisGameCompleteTask) jarvisGameCompleteTask('Find the ' + item.name);
        if (window.jarvisSetContext) jarvisSetContext({level: game.level, objective: game.objective, keys: game.keys});
      } else if (item.type === 'health') {
        game.player.health = Math.min(100, game.player.health + 25);
        showDialogue('Found', 'You found a ' + item.name + '! Health restored.');
      }
      updateUI();
    }
  });
  // Check doors
  game.doors.forEach(function(door) {
    var dx = door.x - p.x, dy = door.y - p.y;
    if (Math.sqrt(dx*dx + dy*dy) < 40) {
      if (door.locked) {
        if (game.keys > 0 && door.isExit && game.keys >= game.totalKeys) {
          door.locked = false;
          showDialogue('Door Unlocked', 'You unlocked the main door! You escape Keyhouse!');
          if (window.jarvisSpeak) jarvisSpeak('Congratulations! You escaped Keyhouse!');
          if (window.jarvisGameCompleteTask) jarvisGameCompleteTask('Unlock the main door');
          setTimeout(function() { victory(); }, 2000);
        } else if (!door.isExit) {
          door.locked = false;
          showDialogue('Door Opened', 'The door creaks open...');
        } else {
          showDialogue('Locked', 'This door needs all ' + game.totalKeys + ' keys. You have ' + game.keys + '.');
        }
      }
    }
  });
  // Check NPCs
  game.npcs.forEach(function(npc) {
    var dx = npc.x - p.x, dy = npc.y - p.y;
    if (Math.sqrt(dx*dx + dy*dy) < 40) {
      showDialogue(npc.name, npc.dialogue);
      if (window.jarvisGameCompleteTask) jarvisGameCompleteTask('Talk to ' + npc.name);
    }
  });
}

function handleCharacterCommand(cmd) {
  showDialogue('JARVIS', 'Character command: ' + cmd);
}

function useKey() {
  interact();
}

function showInventory() {
  if (game.inventory.length === 0) {
    showDialogue('Inventory', 'Your inventory is empty.');
  } else {
    showDialogue('Inventory', game.inventory.join(', '));
  }
}

function showDialogue(speaker, text) {
  var d = document.getElementById('dialogue');
  d.querySelector('.speaker').textContent = speaker;
  d.querySelector('.text').textContent = text;
  d.style.display = 'block';
  game.dialogueActive = true;
  setTimeout(function() { d.style.display = 'none'; game.dialogueActive = false; }, 4000);
}

function updateUI() {
  document.getElementById('keys').textContent = game.keys;
  document.getElementById('health').textContent = game.player.health;
}

function clampPlayer() {
  var p = game.player;
  p.x = Math.max(20, Math.min(W - p.w - 20, p.x));
  p.y = Math.max(20, Math.min(H - p.h - 20, p.y));
}

function update() {
  if (!game.running || game.paused || game.dialogueActive) return;
  var p = game.player;
  
  if (input['arrowleft'] || input['a']) p.x -= p.speed;
  if (input['arrowright'] || input['d']) p.x += p.speed;
  if (input['arrowup'] || input['w']) p.y -= p.speed;
  if (input['arrowdown'] || input['s']) p.y += p.speed;
  clampPlayer();
  
  // Enemy AI
  game.enemies.forEach(function(en) {
    if (en.dead) return;
    en.x += en.speed * en.dir;
    if (en.x < 50 || en.x > W - 50) en.dir *= -1;
    var dx = en.x - p.x, dy = en.y - p.y;
    if (Math.sqrt(dx*dx + dy*dy) < 25) {
      p.health -= 0.5;
      updateUI();
      if (p.health <= 0) gameOver();
    }
  });
}

function draw() {
  ctx.fillStyle = '#0a0a15';
  ctx.fillRect(0, 0, W, H);
  
  // Draw walls
  ctx.fillStyle = '#1a1a2e';
  game.walls.forEach(function(w) { ctx.fillRect(w.x, w.y, w.w, w.h); });
  
  // Draw doors
  game.doors.forEach(function(d) {
    ctx.fillStyle = d.locked ? '#4a2a1a' : '#c4a35a';
    ctx.fillRect(d.x, d.y, d.w, d.h);
    if (d.locked) {
      ctx.fillStyle = '#c4a35a';
      ctx.font = '12px Georgia';
      ctx.fillText('\\u{1F512}', d.x + 5, d.y + 15);
    }
  });
  
  // Draw items
  game.items.forEach(function(item) {
    if (item.collected) return;
    ctx.fillStyle = item.type === 'key' ? '#c4a35a' : '#22c55e';
    ctx.beginPath();
    ctx.arc(item.x, item.y, 8, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.font = '9px Georgia';
    ctx.fillText(item.name, item.x - 25, item.y + 20);
  });
  
  // Draw NPCs
  game.npcs.forEach(function(npc) {
    ctx.fillStyle = '#4fc3f7';
    ctx.fillRect(npc.x - 10, npc.y - 15, 20, 30);
    ctx.fillStyle = '#fff';
    ctx.font = '10px Georgia';
    ctx.fillText(npc.name, npc.x - 12, npc.y + 25);
  });
  
  // Draw enemies
  game.enemies.forEach(function(en) {
    if (en.dead) return;
    ctx.fillStyle = '#e94560';
    ctx.fillRect(en.x - en.w/2, en.y - en.h/2, en.w, en.h);
  });
  
  // Draw player
  var p = game.player;
  ctx.fillStyle = '#c4a35a';
  ctx.fillRect(p.x - p.w/2, p.y - p.h/2, p.w, p.h);
  ctx.fillStyle = '#fff';
  ctx.font = '10px Georgia';
  ctx.fillText('You', p.x - 8, p.y + p.h/2 + 12);
}

function gameOver() {
  game.running = false;
  ctx.fillStyle = 'rgba(0,0,0,0.8)';
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#e94560';
  ctx.font = '36px Georgia';
  ctx.textAlign = 'center';
  ctx.fillText('GAME OVER', W/2, H/2);
  ctx.fillStyle = '#888';
  ctx.font = '16px Georgia';
  ctx.fillText('Press R to restart', W/2, H/2 + 40);
  if (window.jarvisSpeak) jarvisSpeak('Game over. Say restart to try again.');
  document.addEventListener('keydown', function(e) { if (e.key.toLowerCase() === 'r') location.reload(); }, { once: true });
}

function victory() {
  game.running = false;
  ctx.fillStyle = 'rgba(0,0,0,0.8)';
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = '#c4a35a';
  ctx.font = '36px Georgia';
  ctx.textAlign = 'center';
  ctx.fillText('YOU ESCAPED!', W/2, H/2);
  ctx.fillStyle = '#888';
  ctx.font = '16px Georgia';
  ctx.fillText('Lock & Key - Complete', W/2, H/2 + 40);
  ctx.fillText('Press R to play again', W/2, H/2 + 70);
  document.addEventListener('keydown', function(e) { if (e.key.toLowerCase() === 'r') location.reload(); }, { once: true });
}

function loop() { if (game.running) { update(); draw(); requestAnimationFrame(loop); } }
draw();
</script>
</body>
</html>'''


# Template registry
TEMPLATES = {
    "platformer": PLATFORMER_TEMPLATE,
    "shooter": SHOOTER_TEMPLATE,
    "puzzle": PUZZLE_TEMPLATE,
    "racing": RACING_TEMPLATE,
    "arcade": ARCADE_TEMPLATE,
    "lock_and_key": LOCK_AND_KEY_TEMPLATE,
}


# --- AI Game Generation ---
GAME_GEN_SYSTEM = """You are a game generation AI for the SoulIllusions platform.
You create complete, playable HTML5 games from text descriptions.
You output a single HTML file with embedded CSS and JavaScript.
The game must be immediately playable in a browser.

Rules:
- Output ONLY the HTML code, no explanations
- Use canvas-based rendering
- Include score, lives, and game over screen
- Make it visually appealing with a color scheme matching the theme
- Include keyboard controls (arrow keys/WASD)
- Keep it under 500 lines of code
- Make it fun and challenging
"""

async def generate_game_with_ai(prompt: str, genre: str = "", parameters: dict = None) -> str:
    """Generate a complete HTML5 game using AI."""
    cfg = load_agent_config()
    llm = LLMInterface(cfg)
    
    # If genre matches a template, use it as a starting point
    base_template = ""
    if genre and genre in TEMPLATES:
        base_template = f"\n\nUse this as a reference structure (but customize it fully for the prompt):\n```html\n{TEMPLATES[genre][:2000]}\n```"
    
    full_prompt = f"""Create a complete, playable HTML5 game based on this description:

"{prompt}"

Genre: {genre or "auto-detect from description"}
Parameters: {json.dumps(parameters or {})}

Requirements:
- Single HTML file with embedded CSS and JS
- Canvas-based rendering
- Score tracking, lives, game over screen
- Keyboard controls
- Visually appealing with matching color scheme
- Fun and challenging gameplay
- Include in-game tasks/objectives that the player must complete
- Call jarvisAddTask('Task Title', 'Description', 'objective') for each task when the game starts
- Call jarvisGameCompleteTask('Task Title') when a task is completed{base_template}

Output the complete HTML code:"""
    
    html = await llm.generate(full_prompt, GAME_GEN_SYSTEM, max_tokens=8000)
    
    # Clean up — extract HTML if wrapped in code block
    if "```html" in html:
        html = html.split("```html")[1].split("```")[0]
    elif "```" in html:
        html = html.split("```")[1].split("```")[0]
    
    # Ensure it starts with <!DOCTYPE
    html = html.strip()
    if not html.startswith("<!DOCTYPE"):
        html = "<!DOCTYPE html>\n" + html
    
    return html


def generate_game_with_ai_upgrade(current_html: str, upgrade_prompt: str) -> str:
    """Modify an existing game's HTML using AI based on an upgrade request.
    This is a synchronous wrapper used by the server for in-game agent upgrades.
    """
    cfg = load_agent_config()
    llm = LLMInterface(cfg)
    
    # Truncate current HTML if too long to fit in context
    max_html = 12000
    html_for_prompt = current_html[:max_html]
    if len(current_html) > max_html:
        html_for_prompt += "\n<!-- ... truncated ... -->\n</body></html>"
    
    full_prompt = f"""You are modifying an existing HTML5 game. Here is the current game:

```html
{html_for_prompt}
```

Modification request: {upgrade_prompt}

Apply the requested changes while keeping the game playable. Return the COMPLETE modified HTML file.
Keep the JARVIS injection if present (the jarvisCellphone div and script). 
Output only the HTML code:"""
    
    try:
        result = asyncio.run(llm.generate(full_prompt, GAME_GEN_SYSTEM, max_tokens=8000))
    except Exception as e:
        print(f"[Games] AI upgrade failed: {e}")
        return current_html
    
    # Clean up
    if "```html" in result:
        result = result.split("```html")[1].split("```")[0]
    elif "```" in result:
        result = result.split("```")[1].split("```")[0]
    
    result = result.strip()
    if not result.startswith("<!DOCTYPE"):
        result = "<!DOCTYPE html>\n" + result
    
    # Ensure JARVIS is injected
    result = inject_jarvis(result)
    
    return result

# --- JARVIS In-Game Control System ---
JARVIS_INJECTION = '''
<!-- JARVIS In-Game Control System -->
<div id="jarvisCellphone" style="position:fixed;bottom:15px;right:15px;width:50px;height:50px;
  background:linear-gradient(135deg,#1a1a2e,#16213e);border:2px solid #0f3460;border-radius:12px;
  cursor:pointer;z-index:99999;display:flex;align-items:center;justify-content:center;
  box-shadow:0 4px 15px rgba(0,0,0,0.5);transition:all 0.3s;" 
  onmouseover="this.style.transform='scale(1.1)'" 
  onmouseout="this.style.transform='scale(1)'"
  onclick="jarvisToggle()">
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#e94560" stroke-width="2">
    <rect x="5" y="2" width="14" height="20" rx="2"/>
    <line x1="12" y1="18" x2="12" y2="18"/>
  </svg>
</div>

<!-- In-game tasks indicator badge -->
<div id="jarvisTaskBadge" style="position:fixed;bottom:60px;right:20px;z-index:99998;
  background:#e94560;color:#fff;border-radius:10px;padding:2px 8px;font-size:10px;
  font-family:sans-serif;display:none;cursor:pointer;" onclick="jarvisToggle();jarvisSwitchTab('tasks');">
  <span id="jarvisTaskCount">0</span> tasks
</div>

<div id="jarvisPhone" style="display:none;position:fixed;bottom:75px;right:15px;width:340px;
  max-height:520px;overflow-y:auto;background:linear-gradient(180deg,#0f0f1e,#1a1a2e);
  border:2px solid #0f3460;border-radius:20px;z-index:99999;
  box-shadow:0 10px 40px rgba(0,0,0,0.7);font-family:'Segoe UI',sans-serif;">
  
  <div style="background:linear-gradient(90deg,#e94560,#0f3460);padding:12px 16px;color:#fff;
    font-size:14px;font-weight:bold;display:flex;justify-content:space-between;align-items:center;
    position:sticky;top:0;z-index:1;">
    <span>JARVIS</span>
    <span onclick="jarvisToggle()" style="cursor:pointer;font-size:18px;">&times;</span>
  </div>
  
  <div style="padding:10px;">
    <!-- Tab buttons: Voice | Text | Agent | Tasks -->
    <div id="jarvisTabs" style="display:flex;gap:3px;margin-bottom:10px;flex-wrap:wrap;">
      <button id="jarvisTabVoice" onclick="jarvisSwitchTab('voice')" 
        style="flex:1;padding:7px 4px;background:#0f3460;border:none;border-radius:8px;color:#fff;cursor:pointer;font-size:11px;">Voice</button>
      <button id="jarvisTabText" onclick="jarvisSwitchTab('text')" 
        style="flex:1;padding:7px 4px;background:#1a1a2e;border:1px solid #333;border-radius:8px;color:#888;cursor:pointer;font-size:11px;">Text</button>
      <button id="jarvisTabAgent" onclick="jarvisSwitchTab('agent')" 
        style="flex:1;padding:7px 4px;background:#1a1a2e;border:1px solid #333;border-radius:8px;color:#888;cursor:pointer;font-size:11px;">Agent</button>
      <button id="jarvisTabTasks" onclick="jarvisSwitchTab('tasks')" 
        style="flex:1;padding:7px 4px;background:#1a1a2e;border:1px solid #333;border-radius:8px;color:#888;cursor:pointer;font-size:11px;">Tasks</button>
    </div>
    
    <!-- Voice Panel -->
    <div id="jarvisVoicePanel">
      <div id="jarvisStatus" style="text-align:center;padding:12px;color:#888;font-size:12px;">
        Tap to speak to JARVIS
      </div>
      <button id="jarvisMicBtn" onclick="jarvisToggleVoice()" 
        style="width:60px;height:60px;border-radius:50%;background:#e94560;border:none;
        margin:0 auto;display:block;cursor:pointer;transition:all 0.3s;"
        title="Tap to speak">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"
          style="vertical-align:middle;">
          <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
          <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
          <line x1="12" y1="19" x2="12" y2="23"/>
        </svg>
      </button>
    </div>
    
    <!-- Text Command Panel -->
    <div id="jarvisTextPanel" style="display:none;">
      <textarea id="jarvisTextInput" placeholder="Type a command to JARVIS..." rows="3"
        style="width:100%;background:#1a1a2e;border:1px solid #333;border-radius:8px;
        color:#fff;padding:10px;font-size:13px;resize:none;font-family:sans-serif;"></textarea>
      <button onclick="jarvisSendText()" 
        style="width:100%;padding:10px;margin-top:8px;background:#e94560;border:none;
        border-radius:8px;color:#fff;cursor:pointer;font-size:13px;font-weight:bold;">Send Command</button>
    </div>
    
    <!-- Agent Chat Panel -->
    <div id="jarvisAgentPanel" style="display:none;">
      <div style="margin-bottom:8px;">
        <select id="jarvisAgentSelect" 
          style="width:100%;padding:8px;background:#1a1a2e;border:1px solid #333;border-radius:8px;color:#fff;font-size:12px;">
          <option value="soulillusions">SoulIllusions Agent</option>
          <option value="prime">Prime Agent</option>
          <option value="both">Both Agents</option>
        </select>
      </div>
      <div id="jarvisAgentLog" style="max-height:200px;overflow-y:auto;background:#0a0a15;
        border-radius:8px;padding:8px;font-size:11px;color:#888;margin-bottom:8px;min-height:80px;">
        <div style="color:#e94560;font-weight:bold;">Agent Chat Online.</div>
        <div style="color:#888;margin-top:4px;">Talk to the AI agents to upgrade your game, request changes, add features, or get help. Agents can communicate with the game maker.</div>
      </div>
      <textarea id="jarvisAgentInput" placeholder="Message the AI agent..." rows="2"
        style="width:100%;background:#1a1a2e;border:1px solid #333;border-radius:8px;
        color:#fff;padding:10px;font-size:13px;resize:none;font-family:sans-serif;"></textarea>
      <button onclick="jarvisSendAgentMessage()" 
        style="width:100%;padding:10px;margin-top:8px;background:#0f3460;border:none;
        border-radius:8px;color:#fff;cursor:pointer;font-size:13px;font-weight:bold;">Send to Agent</button>
      <div style="margin-top:6px;font-size:10px;color:#555;">
        Agents can modify the game, add features, change levels, and communicate with the game maker.
      </div>
    </div>
    
    <!-- Tasks Panel -->
    <div id="jarvisTasksPanel" style="display:none;">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
        <strong style="color:#c4a35a;font-size:13px;">In-Game Tasks</strong>
        <button onclick="jarvisAddTaskPrompt()" 
          style="background:#0f3460;border:none;border-radius:6px;color:#fff;padding:4px 10px;cursor:pointer;font-size:11px;">+ Add</button>
      </div>
      <div id="jarvisTasksList" style="max-height:250px;overflow-y:auto;">
        <div style="color:#888;font-size:11px;text-align:center;padding:10px;">No active tasks. Tasks will appear here during gameplay.</div>
      </div>
    </div>
    
    <!-- Shared Log -->
    <div id="jarvisLog" style="margin-top:10px;max-height:120px;overflow-y:auto;
      background:#0a0a15;border-radius:8px;padding:8px;font-size:11px;color:#888;">
      <div style="color:#e94560;font-weight:bold;">JARVIS Online.</div>
      <div style="color:#888;">Voice/Text: control game. Agent: talk to AI. Tasks: view objectives.</div>
    </div>
    
    <div style="margin-top:8px;font-size:10px;color:#555;text-align:center;">
      JARVIS controls menus, gameplay, agents & tasks
    </div>
  </div>
</div>

<script>
// === JARVIS In-Game Control System v2 ===
var jarvisState = {
  open: false,
  listening: false,
  recognition: null,
  synth: window.speechSynthesis || null,
  gameCommands: {},
  gameContext: null,
  gameId: null,
  tasks: [],
  agentBusy: false,
  serverUrl: window.location.origin || 'http://localhost:7860'
};

// Detect game ID from URL if present
(function() {
  var match = window.location.search.match(/[?&]game_id=(\d+)/);
  if (match) jarvisState.gameId = parseInt(match[1]);
})();

function jarvisToggle() {
  var phone = document.getElementById('jarvisPhone');
  var cell = document.getElementById('jarvisCellphone');
  jarvisState.open = !jarvisState.open;
  phone.style.display = jarvisState.open ? 'block' : 'none';
  cell.style.opacity = jarvisState.open ? '0.5' : '1';
  if (jarvisState.open) {
    jarvisLog("JARVIS ready. How can I help?", 'system');
    jarvisInitVoice();
    jarvisLoadTasks();
  }
}

function jarvisSwitchTab(tab) {
  var panels = {voice:'jarvisVoicePanel',text:'jarvisTextPanel',agent:'jarvisAgentPanel',tasks:'jarvisTasksPanel'};
  var btns = {voice:'jarvisTabVoice',text:'jarvisTabText',agent:'jarvisTabAgent',tasks:'jarvisTabTasks'};
  for (var key in panels) {
    var el = document.getElementById(panels[key]);
    if (el) el.style.display = key === tab ? 'block' : 'none';
    var btn = document.getElementById(btns[key]);
    if (btn) {
      if (key === tab) { btn.style.background = '#0f3460'; btn.style.color = '#fff'; btn.style.border = 'none'; }
      else { btn.style.background = '#1a1a2e'; btn.style.color = '#888'; btn.style.border = '1px solid #333'; }
    }
  }
  if (tab === 'tasks') jarvisRenderTasks();
}

function jarvisInitVoice() {
  if (jarvisState.recognition) return;
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SR) {
    jarvisState.recognition = new SR();
    jarvisState.recognition.continuous = false;
    jarvisState.recognition.interimResults = false;
    jarvisState.recognition.lang = 'en-US';
    jarvisState.recognition.onresult = function(event) {
      var transcript = event.results[0][0].transcript;
      jarvisLog("You: " + transcript, 'user');
      jarvisProcessCommand(transcript);
    };
    jarvisState.recognition.onerror = function(event) {
      jarvisLog("Voice error: " + event.error, 'error');
      jarvisState.listening = false;
      jarvisUpdateMicUI();
    };
    jarvisState.recognition.onend = function() {
      jarvisState.listening = false;
      jarvisUpdateMicUI();
    };
  }
}

function jarvisToggleVoice() {
  if (!jarvisState.recognition) {
    jarvisLog("Voice recognition not supported. Use text tab.", 'error');
    jarvisSwitchTab('text');
    return;
  }
  if (jarvisState.listening) {
    jarvisState.recognition.stop();
  } else {
    try {
      jarvisState.recognition.start();
      jarvisState.listening = true;
      jarvisLog("Listening...", 'system');
    } catch(e) { jarvisLog("Could not start listening: " + e, 'error'); }
  }
  jarvisUpdateMicUI();
}

function jarvisUpdateMicUI() {
  var btn = document.getElementById('jarvisMicBtn');
  var status = document.getElementById('jarvisStatus');
  if (jarvisState.listening) {
    btn.style.background = '#22c55e';
    btn.style.boxShadow = '0 0 20px rgba(34,197,94,0.5)';
    status.textContent = 'Listening...';
    status.style.color = '#22c55e';
  } else {
    btn.style.background = '#e94560';
    btn.style.boxShadow = 'none';
    status.textContent = 'Tap to speak to JARVIS';
    status.style.color = '#888';
  }
}

function jarvisSendText() {
  var input = document.getElementById('jarvisTextInput');
  var cmd = input.value.trim();
  if (!cmd) return;
  jarvisLog("You: " + cmd, 'user');
  jarvisProcessCommand(cmd);
  input.value = '';
}

function jarvisLog(msg, type) {
  var log = document.getElementById('jarvisLog');
  if (!log) return;
  var div = document.createElement('div');
  var colors = {'user':'#4fc3f7','system':'#e94560','error':'#ef4444','action':'#22c55e','jarvis':'#e94560','agent':'#c4a35a','task':'#22c55e'};
  div.style.color = colors[type] || '#888';
  div.style.marginTop = '4px';
  div.textContent = msg;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function jarvisAgentLog(msg, type) {
  var log = document.getElementById('jarvisAgentLog');
  if (!log) return;
  var div = document.createElement('div');
  var colors = {'user':'#4fc3f7','agent':'#c4a35a','error':'#ef4444','system':'#e94560','action':'#22c55e'};
  div.style.color = colors[type] || '#888';
  div.style.marginTop = '4px';
  div.textContent = msg;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function jarvisSpeak(text) {
  if (jarvisState.synth) {
    var utter = new SpeechSynthesisUtterance(text);
    utter.rate = 1.0; utter.pitch = 0.8; utter.volume = 0.7;
    jarvisState.synth.speak(utter);
  }
  jarvisLog("JARVIS: " + text, 'jarvis');
}

// === Agent Communication ===
function jarvisSendAgentMessage() {
  var input = document.getElementById('jarvisAgentInput');
  var msg = input.value.trim();
  if (!msg || jarvisState.agentBusy) return;
  var agentType = document.getElementById('jarvisAgentSelect').value;
  
  jarvisAgentLog("You: " + msg, 'user');
  input.value = '';
  jarvisState.agentBusy = true;
  jarvisAgentLog("Sending to " + (agentType === 'both' ? 'both agents' : agentType + ' agent') + "...", 'system');
  
  // Build context for agents
  var context = {
    game_id: jarvisState.gameId,
    game_context: jarvisState.gameContext,
    tasks: jarvisState.tasks,
    message: msg,
    agent: agentType
  };
  
  fetch(jarvisState.serverUrl + '/api/games/agent-chat', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(context)
  }).then(function(r) { return r.json(); }).then(function(data) {
    jarvisState.agentBusy = false;
    if (data.error) {
      jarvisAgentLog("Error: " + data.error, 'error');
      return;
    }
    if (data.soulillusions_response) {
      jarvisAgentLog("[SoulIllusions Agent]: " + data.soulillusions_response, 'agent');
    }
    if (data.prime_response) {
      jarvisAgentLog("[Prime Agent]: " + data.prime_response, 'agent');
    }
    if (data.response) {
      jarvisAgentLog("[Agent]: " + data.response, 'agent');
    }
    if (data.game_upgraded) {
      jarvisAgentLog("Game has been upgraded! Changes: " + (data.upgrade_summary || 'applied'), 'action');
      jarvisLog("Agent upgraded the game!", 'action');
      if (data.new_html) {
        jarvisApplyGameUpgrade(data.new_html);
      }
    }
    if (data.new_tasks && data.new_tasks.length) {
      data.new_tasks.forEach(function(t) { jarvisAddTask(t.title, t.description, t.type || 'objective'); });
      jarvisAgentLog("New tasks added by agent.", 'action');
    }
    if (data.speak) jarvisSpeak(data.speak);
  }).catch(function(e) {
    jarvisState.agentBusy = false;
    jarvisAgentLog("Connection error: " + e, 'error');
  });
}

function jarvisApplyGameUpgrade(newHtml) {
  // Try to apply upgrade live without full reload
  try {
    var parser = new DOMParser();
    var newDoc = parser.parseFromString(newHtml, 'text/html');
    // Replace canvas/script content
    var newCanvas = newDoc.querySelector('canvas');
    var oldCanvas = document.querySelector('canvas');
    if (newCanvas && oldCanvas) {
      var parent = oldCanvas.parentNode;
      parent.replaceChild(newCanvas, oldCanvas);
    }
    // Replace script tags
    var newScripts = newDoc.querySelectorAll('script');
    newScripts.forEach(function(s) {
      if (s.id && s.id !== 'jarvis-script') {
        var old = document.getElementById(s.id);
        if (old) old.remove();
        var ns = document.createElement('script');
        ns.id = s.id;
        ns.textContent = s.textContent;
        document.body.appendChild(ns);
      }
    });
    jarvisAgentLog("Game upgrade applied live!", 'action');
  } catch(e) {
    jarvisAgentLog("Upgrade needs page reload to take effect.", 'system');
  }
}

// === In-Game Tasks System ===
function jarvisAddTask(title, description, type) {
  type = type || 'objective';
  var task = {
    id: 'task_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5),
    title: title,
    description: description || '',
    type: type,
    completed: false,
    created_at: Date.now()
  };
  jarvisState.tasks.push(task);
  jarvisRenderTasks();
  jarvisUpdateTaskBadge();
  jarvisLog("New task: " + title, 'task');
  // Notify game
  jarvisExecute('task_added', {task: task});
  // Save to server if game ID known
  if (jarvisState.gameId) {
    fetch(jarvisState.serverUrl + '/api/games/' + jarvisState.gameId + '/tasks', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(task)
    }).catch(function(){});
  }
  return task;
}

function jarvisCompleteTask(taskId) {
  jarvisState.tasks.forEach(function(t) {
    if (t.id === taskId) t.completed = true;
  });
  jarvisRenderTasks();
  jarvisUpdateTaskBadge();
  jarvisExecute('task_completed', {taskId: taskId});
  if (jarvisState.gameId) {
    fetch(jarvisState.serverUrl + '/api/games/' + jarvisState.gameId + '/tasks/' + taskId + '/complete', {
      method: 'POST'
    }).catch(function(){});
  }
}

function jarvisRemoveTask(taskId) {
  jarvisState.tasks = jarvisState.tasks.filter(function(t) { return t.id !== taskId; });
  jarvisRenderTasks();
  jarvisUpdateTaskBadge();
}

function jarvisRenderTasks() {
  var el = document.getElementById('jarvisTasksList');
  if (!el) return;
  if (!jarvisState.tasks.length) {
    el.innerHTML = '<div style="color:#888;font-size:11px;text-align:center;padding:10px;">No active tasks. Tasks will appear here during gameplay.</div>';
    return;
  }
  el.innerHTML = jarvisState.tasks.map(function(t) {
    var color = t.completed ? '#22c55e' : (t.type === 'objective' ? '#c4a35a' : '#4fc3f7');
    var checkStyle = t.completed ? 'text-decoration:line-through;opacity:0.6;' : '';
    return '<div style="padding:8px;border-bottom:1px solid rgba(255,255,255,0.05);">' +
      '<div style="display:flex;align-items:start;gap:6px;">' +
      '<span onclick="jarvisCompleteTask(\\'' + t.id + '\\')" style="cursor:pointer;color:' + color + ';font-size:14px;">' + (t.completed ? '\\u2713' : '\\u25CB') + '</span>' +
      '<div style="flex:1;">' +
      '<div style="color:' + color + ';font-size:12px;font-weight:bold;' + checkStyle + '">' + t.title + '</div>' +
      (t.description ? '<div style="color:#888;font-size:10px;margin-top:2px;' + checkStyle + '">' + t.description + '</div>' : '') +
      '<div style="margin-top:3px;font-size:9px;color:#555;">' + t.type + (t.completed ? ' | Done' : '') + '</div>' +
      '</div>' +
      '<span onclick="jarvisRemoveTask(\\'' + t.id + '\\')" style="cursor:pointer;color:#555;font-size:12px;">&times;</span>' +
      '</div></div>';
  }).join('');
}

function jarvisUpdateTaskBadge() {
  var badge = document.getElementById('jarvisTaskBadge');
  var count = document.getElementById('jarvisTaskCount');
  var active = jarvisState.tasks.filter(function(t) { return !t.completed; }).length;
  if (active > 0) {
    badge.style.display = 'block';
    count.textContent = active;
  } else {
    badge.style.display = 'none';
  }
}

function jarvisAddTaskPrompt() {
  var title = prompt('Task title:');
  if (!title) return;
  var desc = prompt('Task description (optional):') || '';
  var type = prompt('Task type (objective, side, challenge, upgrade):', 'objective') || 'objective';
  jarvisAddTask(title, desc, type);
}

function jarvisLoadTasks() {
  if (!jarvisState.gameId) return;
  fetch(jarvisState.serverUrl + '/api/games/' + jarvisState.gameId + '/tasks').then(function(r) {
    return r.json();
  }).then(function(data) {
    if (data.tasks && data.tasks.length) {
      jarvisState.tasks = data.tasks;
      jarvisRenderTasks();
      jarvisUpdateTaskBadge();
    }
  }).catch(function(){});
}

// === Command Processing ===
function jarvisProcessCommand(cmd) {
  cmd = cmd.toLowerCase().trim();
  
  // --- Agent routing commands ---
  if (cmd.match(/ask.*agent|talk.*to.*agent|tell.*agent|agent.*help|upgrade.*game|modify.*game|add.*feature|change.*game|customize.*game/)) {
    jarvisSwitchTab('agent');
    jarvisAgentLog("Switched to agent chat. Tell the agents what you want to change or upgrade.", 'system');
    // Auto-fill the message if there's a specific request
    var agentMsg = cmd.replace(/.*(?:ask agent|talk to agent|tell agent|agent help|upgrade game|modify game|add feature|change game|customize game)/, '').trim();
    if (agentMsg) {
      document.getElementById('jarvisAgentInput').value = agentMsg;
    }
    return;
  }
  
  // --- Task commands ---
  if (cmd.match(/show.*task|task.*list|what.*task|objectives?/)) {
    jarvisSwitchTab('tasks');
    jarvisSpeak("Showing your tasks.");
    return;
  }
  if (cmd.match(/add.*task|new.*task|new.*objective/)) {
    jarvisAddTaskPrompt();
    return;
  }
  if (cmd.match(/complete.*task|done.*task|finish.*task/)) {
    var taskTitle = cmd.replace(/.*(?:complete task|done task|finish task)/, '').trim();
    var found = jarvisState.tasks.find(function(t) { return !t.completed && t.title.toLowerCase().includes(taskTitle); });
    if (found) {
      jarvisCompleteTask(found.id);
      jarvisSpeak("Task completed: " + found.title);
    } else {
      jarvisSpeak("No matching task found.");
    }
    return;
  }
  
  // --- Menu/Settings Commands ---
  if (cmd.match(/start.*game|begin|play|new game/)) {
    jarvisExecute('start');
    jarvisSpeak("Starting the game.");
    return;
  }
  if (cmd.match(/open.*settings|settings|options|configure/)) {
    jarvisExecute('settings');
    jarvisSpeak("Opening settings.");
    return;
  }
  if (cmd.match(/pause|stop.*game/)) {
    jarvisExecute('pause');
    jarvisSpeak("Game paused.");
    return;
  }
  if (cmd.match(/resume|continue|unpause/)) {
    jarvisExecute('resume');
    jarvisSpeak("Resuming game.");
    return;
  }
  if (cmd.match(/restart|reset|new game/)) {
    jarvisExecute('restart');
    jarvisSpeak("Restarting game.");
    return;
  }
  if (cmd.match(/menu|main menu|back/)) {
    jarvisExecute('menu');
    jarvisSpeak("Returning to main menu.");
    return;
  }
  if (cmd.match(/quit|exit|close/)) {
    jarvisExecute('quit');
    jarvisSpeak("Exiting game.");
    return;
  }
  if (cmd.match(/help|what.*can.*you.*do|commands/)) {
    jarvisSpeak("I can control the game with voice or text. Use the Agent tab to talk to AI agents for upgrades. Use Tasks tab to view objectives.");
    return;
  }
  
  // --- Movement Commands ---
  if (cmd.match(/go.*left|move.*left|walk.*left|left/)) {
    jarvisSimKey('ArrowLeft');
    jarvisExecute('move', {direction: 'left'});
    jarvisLog("Moving left", 'action');
    return;
  }
  if (cmd.match(/go.*right|move.*right|walk.*right|right/)) {
    jarvisSimKey('ArrowRight');
    jarvisExecute('move', {direction: 'right'});
    jarvisLog("Moving right", 'action');
    return;
  }
  if (cmd.match(/go.*up|move.*up|forward|up/)) {
    jarvisSimKey('ArrowUp');
    jarvisExecute('move', {direction: 'up'});
    jarvisLog("Moving up", 'action');
    return;
  }
  if (cmd.match(/go.*down|move.*down|back.*down|down/)) {
    jarvisSimKey('ArrowDown');
    jarvisExecute('move', {direction: 'down'});
    jarvisLog("Moving down", 'action');
    return;
  }
  
  // --- Action Commands ---
  if (cmd.match(/jump|hop/)) {
    jarvisSimKey(' ');
    jarvisSimKey('ArrowUp');
    jarvisExecute('jump');
    jarvisLog("Jumping", 'action');
    return;
  }
  if (cmd.match(/attack|fight|hit|shoot|fire/)) {
    jarvisSimKey(' ');
    jarvisSimKey('f');
    jarvisExecute('attack');
    jarvisLog("Attacking", 'action');
    return;
  }
  if (cmd.match(/interact|use|activate|talk|open.*door/)) {
    jarvisSimKey('e');
    jarvisExecute('interact');
    jarvisLog("Interacting", 'action');
    return;
  }
  if (cmd.match(/inventory|items|bag|backpack/)) {
    jarvisSimKey('i');
    jarvisExecute('inventory');
    jarvisSpeak("Opening inventory.");
    return;
  }
  if (cmd.match(/map|where.*am.*i|location/)) {
    jarvisSimKey('m');
    jarvisExecute('map');
    jarvisSpeak("Opening map.");
    return;
  }
  if (cmd.match(/save|save.*game/)) {
    jarvisExecute('save');
    jarvisSpeak("Game saved.");
    return;
  }
  if (cmd.match(/run|sprint|dash/)) {
    jarvisSimKey('Shift');
    jarvisExecute('sprint');
    jarvisLog("Sprinting", 'action');
    return;
  }
  if (cmd.match(/dodge|roll|dodge.*roll/)) {
    jarvisSimKey('Shift');
    jarvisExecute('dodge');
    jarvisLog("Dodging", 'action');
    return;
  }
  if (cmd.match(/crouch|duck|sneak|stealth/)) {
    jarvisSimKey('Control');
    jarvisExecute('crouch');
    jarvisLog("Crouching", 'action');
    return;
  }
  
  // --- Character Commands ---
  if (cmd.match(/look.*around|scan|survey/)) {
    jarvisExecute('look_around');
    jarvisSpeak("Scanning the area.");
    return;
  }
  if (cmd.match(/follow.*path|follow.*road|follow.*trail/)) {
    jarvisExecute('follow_path');
    jarvisSpeak("Following the path.");
    return;
  }
  if (cmd.match(/find.*item|search.*for|look.*for/)) {
    var item = cmd.replace(/.*(?:find|search for|look for)/, '').trim();
    jarvisExecute('find_item', {item: item});
    jarvisSpeak("Searching for " + item);
    return;
  }
  if (cmd.match(/go.*to|navigate.*to|head.*to|travel.*to/)) {
    var dest = cmd.replace(/.*(?:go to|navigate to|head to|travel to)/, '').trim();
    jarvisExecute('goto', {destination: dest});
    jarvisSpeak("Navigating to " + dest);
    return;
  }
  if (cmd.match(/talk.*to|speak.*to|approach/)) {
    var target = cmd.replace(/.*(?:talk to|speak to|approach)/, '').trim();
    jarvisExecute('talk_to', {target: target});
    jarvisSpeak("Approaching " + target);
    return;
  }
  
  // --- Game-specific custom commands ---
  if (jarvisState.gameCommands && jarvisState.gameCommands[cmd]) {
    var result = jarvisState.gameCommands[cmd]();
    if (result) jarvisSpeak(result);
    return;
  }
  
  // --- Free-form character command ---
  jarvisExecute('character_command', {command: cmd});
  jarvisSpeak("Telling character to: " + cmd);
}

function jarvisSimKey(key) {
  var events = ['keydown', 'keyup'];
  events.forEach(function(type) {
    var ev = new KeyboardEvent(type, {
      key: key, code: key, keyCode: key.charCodeAt(0),
      bubbles: true, cancelable: true
    });
    document.dispatchEvent(ev);
    if (window.canvas) window.canvas.dispatchEvent(ev);
  });
}

function jarvisExecute(action, params) {
  params = params || {};
  var ev = new CustomEvent('jarvis-command', {
    detail: {action: action, params: params, timestamp: Date.now()}
  });
  document.dispatchEvent(ev);
  if (typeof window.jarvisGameHook === 'function') {
    try { window.jarvisGameHook(action, params); } catch(e) {}
  }
}

// Games register custom commands via: jarvisRegisterCommand('cast spell', function() { ... })
function jarvisRegisterCommand(phrase, handler) {
  if (!jarvisState.gameCommands) jarvisState.gameCommands = {};
  jarvisState.gameCommands[phrase.toLowerCase()] = handler;
}

// Games set context: jarvisSetContext({level: 3, objective: 'Find the key'})
function jarvisSetContext(ctx) {
  jarvisState.gameContext = ctx;
  if (ctx.tasks) {
    ctx.tasks.forEach(function(t) {
      if (!jarvisState.tasks.find(function(existing) { return existing.title === t.title; })) {
        jarvisAddTask(t.title, t.description || '', t.type || 'objective');
      }
    });
  }
}

// Games add tasks: jarvisAddTask('Find the key', 'Search the house for the golden key')
// Already defined above - this is for game scripts to call

// Games complete tasks: jarvisGameCompleteTask('Find the key')
function jarvisGameCompleteTask(title) {
  var task = jarvisState.tasks.find(function(t) { return !t.completed && t.title.toLowerCase().includes(title.toLowerCase()); });
  if (task) {
    jarvisCompleteTask(task.id);
  }
}

// Expose globally
window.jarvisToggle = jarvisToggle;
window.jarvisSwitchTab = jarvisSwitchTab;
window.jarvisToggleVoice = jarvisToggleVoice;
window.jarvisSendText = jarvisSendText;
window.jarvisSendAgentMessage = jarvisSendAgentMessage;
window.jarvisRegisterCommand = jarvisRegisterCommand;
window.jarvisSetContext = jarvisSetContext;
window.jarvisExecute = jarvisExecute;
window.jarvisSpeak = jarvisSpeak;
window.jarvisState = jarvisState;
window.jarvisAddTask = jarvisAddTask;
window.jarvisCompleteTask = jarvisCompleteTask;
window.jarvisRemoveTask = jarvisRemoveTask;
window.jarvisGameCompleteTask = jarvisGameCompleteTask;
window.jarvisRenderTasks = jarvisRenderTasks;
</script>
'''
DEFAULT_TASKS_SCRIPT = '''
<script>
// === Default In-Game Tasks Auto-Init ===
// This runs after JARVIS is loaded and adds default tasks if no game-specific tasks exist
(function() {
  function jarvisInitDefaultTasks() {
    if (!window.jarvisState || !window.jarvisAddTask) return;
    // Only add defaults if no tasks have been registered yet
    if (jarvisState.tasks.length > 0) return;
    jarvisAddTask('Start the game', 'Press Start or say "start game" to begin', 'objective');
    jarvisAddTask('Learn the controls', 'Use arrow keys/WASD to move, Space to jump/attack, E to interact', 'side');
    jarvisAddTask('Reach the objective', 'Complete the main goal of the game', 'objective');
    jarvisAddTask('Explore the area', 'Look around for hidden items or secrets', 'side');
    jarvisAddTask('Try JARVIS Agent chat', 'Open the Agent tab to talk to AI agents for game upgrades', 'side');
  }
  // Run after a short delay to let game scripts initialize first
  setTimeout(jarvisInitDefaultTasks, 1500);
})();
</script>
'''


def inject_jarvis(html: str) -> str:
    """Inject JARVIS in-game control system into game HTML."""
    if "jarvisCellphone" in html:
        return html  # Already injected
    injection = JARVIS_INJECTION + "\n" + DEFAULT_TASKS_SCRIPT
    # Inject before </body>
    if "</body>" in html:
        return html.replace("</body>", injection + "\n</body>")
    # Fallback: append
    return html + injection


def generate_game_from_template(title: str, genre: str, prompt: str) -> str:
    """Generate a game from a template (instant, no AI needed)."""
    template = TEMPLATES.get(genre, ARCADE_TEMPLATE)
    html = template.replace("{{TITLE}}", title)
    return inject_jarvis(html)


# --- Game Manager ---
class GameManager:
    """Manages game creation, storage, and retrieval."""
    
    def create_game(self, prompt: str, genre: str = "", title: str = "", 
                    parameters: dict = None, use_ai: bool = True, 
                    created_by: str = "user") -> dict:
        """Create a new game."""
        if not title:
            title = prompt[:40].title()
        
        # Generate HTML
        if use_ai:
            try:
                html = asyncio.run(generate_game_with_ai(prompt, genre, parameters))
            except Exception as e:
                print(f"[Games] AI generation failed, using template: {e}")
                html = generate_game_from_template(title, genre or "arcade", prompt)
        else:
            html = generate_game_from_template(title, genre or "arcade", prompt)
        
        # Inject JARVIS in-game control system into all games
        html = inject_jarvis(html)
        
        # Save to file
        safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title.lower())[:50]
        filename = f"{safe_title}_{int(time.time())}.html"
        filepath = GAMES_DIR / filename
        filepath.write_text(html, encoding='utf-8')
        
        # Save to DB
        conn = sqlite3.connect(str(GAMES_DB))
        c = conn.cursor()
        c.execute(
            """INSERT INTO games (title, description, genre, prompt, html_content, file_path, parameters, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, prompt, genre or "custom", prompt, html, str(filepath), json.dumps(parameters or {}), created_by)
        )
        game_id = c.lastrowid
        conn.commit()
        conn.close()
        
        return {
            "id": game_id,
            "title": title,
            "genre": genre or "custom",
            "file_path": str(filepath),
            "html_size": len(html),
            "status": "generated"
        }
    
    def get_game(self, game_id: int) -> Optional[dict]:
        """Get a game by ID."""
        conn = sqlite3.connect(str(GAMES_DB))
        c = conn.cursor()
        c.execute("SELECT id, title, description, genre, prompt, file_path, rating, plays, parameters, created_at, created_by FROM games WHERE id = ?", (game_id,))
        row = c.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": row[0], "title": row[1], "description": row[2], "genre": row[3],
            "prompt": row[4], "file_path": row[5], "rating": row[6], "plays": row[7],
            "parameters": json.loads(row[8]) if row[8] else {}, "created_at": row[9], "created_by": row[10]
        }
    
    def get_game_html(self, game_id: int) -> Optional[str]:
        """Get the HTML content of a game."""
        conn = sqlite3.connect(str(GAMES_DB))
        c = conn.cursor()
        c.execute("SELECT html_content FROM games WHERE id = ?", (game_id,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else None
    
    def list_games(self, limit: int = 50, genre: str = "") -> List[dict]:
        """List all games."""
        conn = sqlite3.connect(str(GAMES_DB))
        c = conn.cursor()
        if genre:
            c.execute("SELECT id, title, genre, rating, plays, created_at FROM games WHERE genre = ? ORDER BY created_at DESC LIMIT ?", (genre, limit))
        else:
            c.execute("SELECT id, title, genre, rating, plays, created_at FROM games ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = c.fetchall()
        conn.close()
        return [{"id": r[0], "title": r[1], "genre": r[2], "rating": r[3], "plays": r[4], "created_at": r[5]} for r in rows]
    
    def rate_game(self, game_id: int, rating: int) -> dict:
        """Rate a game (1-5 stars)."""
        rating = max(1, min(5, rating))
        conn = sqlite3.connect(str(GAMES_DB))
        c = conn.cursor()
        c.execute("UPDATE games SET rating = ? WHERE id = ?", (rating, game_id))
        conn.commit()
        conn.close()
        return {"status": "rated", "game_id": game_id, "rating": rating}
    
    def play_game(self, game_id: int) -> dict:
        """Increment play count and return game HTML."""
        conn = sqlite3.connect(str(GAMES_DB))
        c = conn.cursor()
        c.execute("UPDATE games SET plays = plays + 1 WHERE id = ?", (game_id,))
        c.execute("SELECT html_content FROM games WHERE id = ?", (game_id,))
        row = c.fetchone()
        conn.commit()
        conn.close()
        if row:
            return {"html": row[0]}
        return {"error": "Game not found"}
    
    def delete_game(self, game_id: int) -> dict:
        """Delete a game."""
        conn = sqlite3.connect(str(GAMES_DB))
        c = conn.cursor()
        c.execute("SELECT file_path FROM games WHERE id = ?", (game_id,))
        row = c.fetchone()
        if row and row[0]:
            try:
                Path(row[0]).unlink(missing_ok=True)
            except:
                pass
        c.execute("DELETE FROM games WHERE id = ?", (game_id,))
        conn.commit()
        conn.close()
        return {"status": "deleted", "game_id": game_id}
    
    def get_genres(self) -> List[str]:
        """Get available game genres."""
        return list(TEMPLATES.keys()) + ["custom", "rpg", "strategy", "card", "adventure"]
    
    def update_game(self, game_id: int, html_content: str = None, title: str = None,
                    description: str = None, metadata: dict = None) -> dict:
        """Update a game's content (used by agents for in-game upgrades)."""
        conn = sqlite3.connect(str(GAMES_DB))
        c = conn.cursor()
        c.execute("SELECT id, file_path FROM games WHERE id = ?", (game_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            return {"error": "Game not found"}
        
        updates = []
        params = []
        if html_content is not None:
            updates.append("html_content = ?")
            params.append(html_content)
            # Also update the file
            if row[1]:
                try:
                    Path(row[1]).write_text(html_content, encoding='utf-8')
                except:
                    pass
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))
        
        if updates:
            params.append(game_id)
            c.execute(f"UPDATE games SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
        conn.close()
        return {"status": "updated", "game_id": game_id}
    
    def add_task(self, game_id: int, task_id: str, title: str, description: str = "",
                 task_type: str = "objective") -> dict:
        """Add a task to a game."""
        conn = sqlite3.connect(str(GAMES_DB))
        c = conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO game_tasks (id, game_id, title, description, type) VALUES (?, ?, ?, ?, ?)",
            (task_id, game_id, title, description, task_type)
        )
        conn.commit()
        conn.close()
        return {"status": "added", "task_id": task_id, "game_id": game_id}
    
    def get_tasks(self, game_id: int) -> List[dict]:
        """Get all tasks for a game."""
        conn = sqlite3.connect(str(GAMES_DB))
        c = conn.cursor()
        c.execute("SELECT id, game_id, title, description, type, completed, created_at, completed_at FROM game_tasks WHERE game_id = ? ORDER BY created_at", (game_id,))
        rows = c.fetchall()
        conn.close()
        return [{"id": r[0], "game_id": r[1], "title": r[2], "description": r[3],
                 "type": r[4], "completed": bool(r[5]), "created_at": r[6], "completed_at": r[7]} for r in rows]
    
    def complete_task(self, game_id: int, task_id: str) -> dict:
        """Mark a task as completed."""
        conn = sqlite3.connect(str(GAMES_DB))
        c = conn.cursor()
        c.execute("UPDATE game_tasks SET completed = 1, completed_at = datetime('now') WHERE id = ? AND game_id = ?", (task_id, game_id))
        conn.commit()
        conn.close()
        return {"status": "completed", "task_id": task_id, "game_id": game_id}
    
    def record_upgrade(self, game_id: int, agent: str, request: str, response: str,
                       upgrade_summary: str = "", applied: bool = False) -> dict:
        """Record a game upgrade made by an agent."""
        conn = sqlite3.connect(str(GAMES_DB))
        c = conn.cursor()
        c.execute(
            "INSERT INTO game_upgrades (game_id, agent, request, response, upgrade_summary, applied) VALUES (?, ?, ?, ?, ?, ?)",
            (game_id, agent, request, response, upgrade_summary, 1 if applied else 0)
        )
        upgrade_id = c.lastrowid
        conn.commit()
        conn.close()
        return {"id": upgrade_id, "game_id": game_id, "agent": agent, "status": "recorded"}
    
    def get_upgrades(self, game_id: int) -> List[dict]:
        """Get all upgrades for a game."""
        conn = sqlite3.connect(str(GAMES_DB))
        c = conn.cursor()
        c.execute("SELECT id, game_id, agent, request, upgrade_summary, applied, created_at FROM game_upgrades WHERE game_id = ? ORDER BY created_at DESC", (game_id,))
        rows = c.fetchall()
        conn.close()
        return [{"id": r[0], "game_id": r[1], "agent": r[2], "request": r[3],
                 "upgrade_summary": r[4], "applied": bool(r[5]), "created_at": r[6]} for r in rows]


# Singleton
_game_manager: Optional[GameManager] = None

def get_game_manager() -> GameManager:
    global _game_manager
    if _game_manager is None:
        _game_manager = GameManager()
    return _game_manager


# --- CLI ---
def main():
    import sys
    if len(sys.argv) < 2:
        print("SoulIllusions Text-to-Games Engine")
        print("=" * 45)
        print("Commands:")
        print("  create <prompt> [--genre <g>] [--title <t>] [--no-ai]  — Create a game")
        print("  list [--genre <g>]                                     — List games")
        print("  play <id>                                              — Get game HTML")
        print("  rate <id> <1-5>                                        — Rate a game")
        print("  genres                                                 — List genres")
        print("  delete <id>                                            — Delete a game")
        return
    
    cmd = sys.argv[1]
    mgr = get_game_manager()
    
    if cmd == "create":
        prompt = ""
        genre = ""
        title = ""
        use_ai = True
        for i, arg in enumerate(sys.argv[2:], 2):
            if arg == "--genre" and i + 1 < len(sys.argv): genre = sys.argv[i + 1]
            elif arg == "--title" and i + 1 < len(sys.argv): title = sys.argv[i + 1]
            elif arg == "--no-ai": use_ai = False
            elif not arg.startswith("--"): prompt = arg if not prompt else prompt + " " + arg
        
        if not prompt:
            print("Error: Please provide a game description")
            return
        
        result = mgr.create_game(prompt, genre, title, use_ai=use_ai)
        print(json.dumps(result, indent=2))
        print(f"\nGame saved to: {result.get('file_path', 'unknown')}")
    
    elif cmd == "list":
        genre = ""
        if "--genre" in sys.argv:
            genre = sys.argv[sys.argv.index("--genre") + 1]
        games = mgr.list_games(genre=genre)
        print(json.dumps(games, indent=2))
    
    elif cmd == "play":
        game_id = int(sys.argv[2])
        result = mgr.play_game(game_id)
        if "html" in result:
            # Save to temp file and open
            tmp = GAMES_DIR / f"play_{game_id}.html"
            tmp.write_text(result["html"])
            print(f"Game HTML saved to: {tmp}")
        else:
            print(json.dumps(result, indent=2))
    
    elif cmd == "rate":
        game_id = int(sys.argv[2])
        rating = int(sys.argv[3])
        result = mgr.rate_game(game_id, rating)
        print(json.dumps(result, indent=2))
    
    elif cmd == "genres":
        print(json.dumps(mgr.get_genres(), indent=2))
    
    elif cmd == "delete":
        game_id = int(sys.argv[2])
        result = mgr.delete_game(game_id)
        print(json.dumps(result, indent=2))
    
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
