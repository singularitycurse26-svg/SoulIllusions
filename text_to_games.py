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


# Template registry
TEMPLATES = {
    "platformer": PLATFORMER_TEMPLATE,
    "shooter": SHOOTER_TEMPLATE,
    "puzzle": PUZZLE_TEMPLATE,
    "racing": RACING_TEMPLATE,
    "arcade": ARCADE_TEMPLATE,
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
- Fun and challenging gameplay{base_template}

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


def generate_game_from_template(title: str, genre: str, prompt: str) -> str:
    """Generate a game from a template (instant, no AI needed)."""
    template = TEMPLATES.get(genre, ARCADE_TEMPLATE)
    return template.replace("{{TITLE}}", title)


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
