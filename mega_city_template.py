"""
Mega City Open World Game Template for SoulIllusions Text-to-Games Engine.
A 60-mile open-world city with Lock & Key house, schools, casinos, time currency,
Incentives Inc. crypto, central computer brain, underground city, blackouts,
robots, hover vehicles, property system, courthouse, and NPC life simulation.
"""

MEGA_CITY_TEMPLATE = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}}</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { background:#0a0a15; overflow:hidden; font-family:'Segoe UI',sans-serif; color:#fff; }
canvas { display:block; }
#ui { position:fixed; top:0; left:0; width:100%; pointer-events:none; z-index:100; }
#topBar { display:flex; justify-content:space-between; padding:8px 16px; background:rgba(10,10,21,0.85); border-bottom:1px solid #0f3460; }
#timeDisplay { font-size:22px; font-weight:bold; color:#00ffcc; text-shadow:0 0 10px rgba(0,255,204,0.5); }
#cryptoDisplay { font-size:16px; color:#ffcc00; }
#locationDisplay { font-size:12px; color:#888; }
#minimap { position:fixed; top:50px; right:10px; width:180px; height:180px; border:2px solid #0f3460; border-radius:8px; background:rgba(10,10,21,0.9); z-index:100; }
#dialogueBox { position:fixed; bottom:80px; left:50%; transform:translateX(-50%); width:500px; max-width:90%; background:rgba(15,52,96,0.95); border:2px solid #e94560; border-radius:12px; padding:16px; display:none; z-index:200; pointer-events:auto; }
#dialogueTitle { font-size:16px; font-weight:bold; color:#e94560; margin-bottom:8px; }
#dialogueText { font-size:13px; color:#ccc; line-height:1.5; white-space:pre-line; }
#dialogueClose { margin-top:10px; padding:6px 16px; background:#e94560; border:none; border-radius:6px; color:#fff; cursor:pointer; font-size:12px; }
#interactionPrompt { position:fixed; bottom:120px; left:50%; transform:translateX(-50%); background:rgba(0,0,0,0.8); padding:6px 16px; border-radius:20px; font-size:12px; color:#00ffcc; display:none; z-index:100; }
#blackoutOverlay { position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); pointer-events:none; z-index:50; display:none; }
#blackoutText { position:fixed; top:40%; left:50%; transform:translate(-50%,-50%); font-size:28px; font-weight:bold; color:#ff0000; text-shadow:0 0 20px rgba(255,0,0,0.8); z-index:51; display:none; }
#menuScreen { position:fixed; top:0; left:0; width:100%; height:100%; background:linear-gradient(135deg,#0a0a15,#0f3460); display:flex; flex-direction:column; align-items:center; justify-content:center; z-index:300; }
#menuTitle { font-size:48px; font-weight:bold; color:#e94560; text-shadow:0 0 30px rgba(233,69,96,0.5); margin-bottom:10px; }
#menuSub { font-size:16px; color:#888; margin-bottom:30px; }
.menuBtn { padding:12px 40px; margin:5px; background:#0f3460; border:2px solid #e94560; border-radius:10px; color:#fff; cursor:pointer; font-size:16px; transition:all 0.3s; }
.menuBtn:hover { background:#e94560; transform:scale(1.05); }
#hudPanel { position:fixed; bottom:10px; left:10px; background:rgba(10,10,21,0.85); border:1px solid #0f3460; border-radius:8px; padding:8px; font-size:11px; color:#888; z-index:100; }
#vehicleHud { position:fixed; bottom:10px; left:50%; transform:translateX(-50%); background:rgba(10,10,21,0.85); border:1px solid #0f3460; border-radius:8px; padding:6px 16px; font-size:12px; color:#00ffcc; z-index:100; display:none; }
#arrestScreen { position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); display:none; flex-direction:column; align-items:center; justify-content:center; z-index:250; }
#arrestText { font-size:24px; color:#ff0000; margin-bottom:20px; }
#arrestBtn { padding:10px 30px; background:#e94560; border:none; border-radius:8px; color:#fff; cursor:pointer; font-size:14px; }
#overlayUI { position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(10,10,21,0.95); display:none; flex-direction:column; z-index:280; overflow-y:auto; }
.overlay-header { padding:16px; background:#0f3460; font-size:20px; font-weight:bold; color:#fff; display:flex; justify-content:space-between; position:sticky; top:0; }
.overlay-content { padding:20px; max-width:800px; margin:0 auto; }
.class-card { background:#1a1a2e; border:1px solid #333; border-radius:10px; padding:16px; margin-bottom:12px; cursor:pointer; transition:all 0.3s; }
.class-card:hover { border-color:#e94560; background:#16213e; }
.class-title { font-size:16px; font-weight:bold; color:#e94560; }
.class-desc { font-size:12px; color:#888; margin-top:4px; white-space:pre-line; }
.class-reward { font-size:11px; color:#00ffcc; margin-top:6px; }
.close-btn { padding:6px 14px; background:#e94560; border:none; border-radius:6px; color:#fff; cursor:pointer; font-size:14px; }
.btn { padding:8px 20px; background:#0f3460; border:1px solid #333; border-radius:8px; color:#fff; cursor:pointer; font-size:13px; margin:4px; transition:all 0.2s; }
.btn:hover { background:#e94560; }
</style>
</head>
<body>
<canvas id="game"></canvas>
<div id="ui">
  <div id="topBar">
    <div><div id="timeDisplay">24:00:00</div><div id="locationDisplay">Mega City - Downtown</div></div>
    <div style="text-align:right;"><div id="cryptoDisplay">Incentives Inc.: 0.00</div><div style="font-size:11px;color:#888;" id="dayDisplay">Day 1</div></div>
  </div>
</div>
<canvas id="minimap" width="180" height="180"></canvas>
<div id="hudPanel"><div>WASD/Arrows: Move | E: Interact | Space: Action</div><div>V: Vehicle | B: Buy Property | H: Hack</div></div>
<div id="vehicleHud">Vehicle: None (Press V to summon)</div>
<div id="interactionPrompt">Press E to interact</div>
<div id="dialogueBox"><div id="dialogueTitle">Title</div><div id="dialogueText">Text</div><button id="dialogueClose" onclick="closeDialogue()">Close</button></div>
<div id="blackoutOverlay"></div><div id="blackoutText">BLACKOUT</div>
<div id="arrestScreen"><div id="arrestText">CAUGHT BY ENFORCEMENT ROBOT!</div><div style="color:#888;margin-bottom:20px;font-size:14px;" id="arrestDetail">You lost time and must restart the day.</div><button id="arrestBtn" onclick="restartDay()">Restart Day</button></div>
<div id="overlayUI"><div class="overlay-header"><span id="overlayTitle">Title</span><button class="close-btn" onclick="closeOverlay()">X</button></div><div class="overlay-content" id="overlayContent"></div></div>
<div id="menuScreen"><div id="menuTitle">MEGA CITY</div><div id="menuSub">A 60-Mile Open World | Time is Life | Incentives Inc.</div><button class="menuBtn" onclick="startGame()">Enter the City</button><button class="menuBtn" onclick="showAbout()">About</button></div>
<script>
var canvas=document.getElementById('game'),ctx=canvas.getContext('2d');
var miniCanvas=document.getElementById('minimap'),miniCtx=miniCanvas.getContext('2d');
var W=window.innerWidth,H=window.innerHeight;canvas.width=W;canvas.height=H;
var CITY_SIZE=8000;
var game={running:false,paused:false,player:{x:3200,y:3200,speed:3,health:100,angle:0,onVehicle:null},camera:{x:3200,y:3200},time:86400,crypto:0,day:1,hour:8,minute:0,blackout:false,blackoutTimer:0,nextBlackout:14400,robots:[],npcs:[],vehicles:[],properties:[],ownedProperties:[],currentLocation:'Downtown',schoolEnrolled:{high:false,college:false},collegeMajor:null,grades:{high:{},college:{}},businesses:[],cryptoOwned:null,hackingLevel:1,notoriety:0,keys:0,inventory:[]};
var DISTRICTS=[
{name:'Keyhouse',x:200,y:200,w:600,h:600,color:'#1a2a1a'},{name:'Downtown',x:2800,y:2800,w:2400,h:2400,color:'#1a1a2e'},
{name:'High School',x:1000,y:3200,w:800,h:600,color:'#2a1a1a'},{name:'College',x:1000,y:4200,w:1000,h:800,color:'#1a1a2a'},
{name:'Casino District',x:5200,y:2000,w:800,h:600,color:'#2a2a1a'},{name:'Central Brain',x:3800,y:3800,w:400,h:400,color:'#0a1a2a'},
{name:'Underground',x:3800,y:4200,w:800,h:600,color:'#0a0a1a'},{name:'Courthouse',x:3400,y:2400,w:400,h:300,color:'#1a2a2a'},
{name:'Residential',x:2000,y:1200,w:1600,h:1200,color:'#1a2a1a'},{name:'Industrial',x:5200,y:4000,w:1200,h:1000,color:'#2a2a2a'},
{name:'Entertainment',x:4800,y:3200,w:800,h:500,color:'#2a1a2a'},{name:'Hover Park',x:2400,y:4800,w:800,h:400,color:'#0a2a1a'}
];
var BUILDINGS=[
{id:'keyhouse',x:350,y:350,w:200,h:180,type:'keyhouse',name:'Keyhouse Manor'},{id:'keycave',x:420,y:580,w:120,h:100,type:'cave',name:'The Cave'},
{id:'bank',x:3400,y:3100,w:120,h:100,type:'bank',name:'Central Bank'},{id:'store1',x:3600,y:3200,w:100,h:80,type:'store',name:'Tech Store'},
{id:'store2',x:3300,y:3300,w:100,h:80,type:'store',name:'General Store'},{id:'highschool',x:1200,y:3300,w:300,h:200,type:'school',name:'Mega City High'},
{id:'college',x:1200,y:4300,w:350,h:250,type:'college',name:'Mega City University'},{id:'casino',x:5400,y:2150,w:200,h:180,type:'casino',name:'Lucky Star Casino'},
{id:'brain',x:3900,y:3900,w:200,h:200,type:'brain',name:'Central Computer Brain'},{id:'underground',x:4000,y:4300,w:150,h:120,type:'underground',name:'Underground City Entrance'},
{id:'courthouse',x:3500,y:2480,w:200,h:160,type:'courthouse',name:'Mega City Courthouse'},{id:'hoverpark',x:2600,y:4900,w:200,h:150,type:'hoverpark',name:'Hover Vehicle Station'},
{id:'bar',x:4900,y:3300,w:100,h:80,type:'bar',name:'Neon Bar'},{id:'club',x:5100,y:3350,w:120,h:100,type:'club',name:'Pulse Club'}
];
var STREETS=[];
for(var sx=0;sx<CITY_SIZE;sx+=200)STREETS.push({x:sx,y:0,w:30,h:CITY_SIZE,h:false});
for(var sy=0;sy<CITY_SIZE;sy+=200)STREETS.push({x:0,y:sy,w:CITY_SIZE,h:30,h:true});
var VEHICLE_TYPES=[{name:'Hover Bike',speed:8,cost:500,color:'#00ffcc',size:30},{name:'Hover Board',speed:6,cost:200,color:'#ff6600',size:25},{name:'Hover Car',speed:10,cost:2000,color:'#4488ff',size:45}];
var NPC_NAMES=['Alex','Sam','Jordan','Taylor','Morgan','Riley','Casey','Jamie','Drew','Quinn','Sage','River','Sky','Phoenix','Kai','Nova','Zane','Iris','Luna','Orion'];
var NPC_TASKS=['going to school','heading to work','shopping','walking home','going to casino','heading to college','looking around','talking to friends','going to the bar','heading underground'];
var PROPERTIES=[
{id:'p1',name:'Downtown Loft',price:5000,income:50,type:'housing'},{id:'p2',name:'Casino Penthouse',price:15000,income:150,type:'housing'},
{id:'p3',name:'Residential House',price:3000,income:30,type:'housing'},{id:'p4',name:'Industrial Warehouse',price:8000,income:100,type:'commercial'},
{id:'p5',name:'Entertainment Club',price:12000,income:200,type:'commercial'},{id:'p6',name:'Keyhouse Grounds',price:25000,income:300,type:'special'},
{id:'p7',name:'Tech Store',price:6000,income:80,type:'commercial'},{id:'p8',name:'Hover Park Garage',price:4000,income:60,type:'commercial'}
];
var keys={};
document.addEventListener('keydown',function(e){keys[e.key.toLowerCase()]=true;if(e.key==='e'||e.key==='E')tryInteract();if(e.key==='v'||e.key==='V')toggleVehicle();if(e.key==='b'||e.key==='B')openOverlay('property');if(e.key==='h'||e.key==='H')tryHack();if(e.key==='Escape')togglePause();});
document.addEventListener('keyup',function(e){keys[e.key.toLowerCase()]=false;});
function initNPCs(){game.npcs=[];for(var i=0;i<80;i++){var d=DISTRICTS[Math.floor(Math.random()*DISTRICTS.length)];var nx=d.x+Math.random()*d.w,ny=d.y+Math.random()*d.h;game.npcs.push({id:i,x:nx,y:ny,targetX:nx,targetY:ny,speed:0.5+Math.random(),name:NPC_NAMES[i%NPC_NAMES.length]+(i>=NPC_NAMES.length?i:''),task:NPC_TASKS[Math.floor(Math.random()*NPC_TASKS.length)],color:'#'+Math.floor(Math.random()*16777215).toString(16).substring(0,6),isStudent:Math.random()<0.3,isWorker:Math.random()<0.3,isRobot:Math.random()<0.1,dialogue:["Just "+NPC_TASKS[Math.floor(Math.random()*NPC_TASKS.length)]+".","Watch out for blackouts.","The Central Brain controls everything.","Time is money. Literally.","Incentives Inc. is going up!","Don't get caught during a blackout.","Earn time by going to school.","The underground city has real tech."]})}}
function initRobots(){game.robots=[];for(var i=0;i<15;i++){var a=(i/15)*Math.PI*2;game.robots.push({id:i,x:4000+Math.cos(a)*300,y:4000+Math.sin(a)*300,patrolX:4000+Math.cos(a)*300,patrolY:4000+Math.sin(a)*300,speed:2.5,chasing:false,alertRadius:200,catchRadius:30})}}
function initVehicles(){game.vehicles=[{id:'v0',type:VEHICLE_TYPES[1],x:3200,y:3250,owned:true,parked:true}]}
function loop(){if(!game.running)return;if(!game.paused){update();render()}requestAnimationFrame(loop)}
function update(){var p=game.player,speed=p.onVehicle?p.onVehicle.type.speed:p.speed,dx=0,dy=0;
if(keys['w']||keys['arrowup'])dy-=1;if(keys['s']||keys['arrowdown'])dy+=1;if(keys['a']||keys['arrowleft'])dx-=1;if(keys['d']||keys['arrowright'])dx+=1;
if(dx||dy){var l=Math.sqrt(dx*dx+dy*dy);dx=dx/l*speed;dy=dy/l*speed;p.x+=dx;p.y+=dy;p.angle=Math.atan2(dy,dx);p.x=Math.max(0,Math.min(CITY_SIZE,p.x));p.y=Math.max(0,Math.min(CITY_SIZE,p.y))}
game.camera.x=p.x-W/2;game.camera.y=p.y-H/2;game.minute+=0.1;if(game.minute>=60){game.minute=0;game.hour++}if(game.hour>=24){game.hour=0;game.day++;game.time+=3600;dailyIncome()}
game.time-=0.5;if(game.time<=0){gameOver();return}updateLocation();updateNPCs();updateRobots();updateBlackout();checkNearby();updateUI()}
function dailyIncome(){game.ownedProperties.forEach(function(p){game.crypto+=p.income})}
function updateLocation(){for(var i=0;i<DISTRICTS.length;i++){var d=DISTRICTS[i];if(game.player.x>=d.x&&game.player.x<=d.x+d.w&&game.player.y>=d.y&&game.player.y<=d.y+d.h){game.currentLocation=d.name;return}}game.currentLocation='Mega City Streets'}
function updateNPCs(){game.npcs.forEach(function(n){var dx=n.targetX-n.x,dy=n.targetY-n.y,d=Math.sqrt(dx*dx+dy*dy);if(d<10){var a=Math.random()*Math.PI*2,r=100+Math.random()*300;n.targetX=Math.max(0,Math.min(CITY_SIZE,n.x+Math.cos(a)*r));n.targetY=Math.max(0,Math.min(CITY_SIZE,n.y+Math.sin(a)*r));if(Math.random()<0.3)n.task=NPC_TASKS[Math.floor(Math.random()*NPC_TASKS.length)]}else{n.x+=dx/d*n.speed;n.y+=dy/d*n.speed}})}
function updateRobots(){game.robots.forEach(function(r){if(game.blackout){var dx=game.player.x-r.x,dy=game.player.y-r.y,d=Math.sqrt(dx*dx+dy*dy);if(d<r.catchRadius){arrestPlayer();return}if(d<r.alertRadius||r.chasing){r.chasing=true;r.x+=dx/d*r.speed;r.y+=dy/d*r.speed}else{var px=r.patrolX-r.x,py=r.patrolY-r.y,pd=Math.sqrt(px*px+py*py);if(pd>10){r.x+=px/pd*r.speed*0.5;r.y+=py/pd*r.speed*0.5}}}else{r.chasing=false;var px=r.patrolX-r.x,py=r.patrolY-r.y,pd=Math.sqrt(px*px+py*py);if(pd>10){r.x+=px/pd*r.speed*0.3;r.y+=py/pd*r.speed*0.3}}})}
function updateBlackout(){if(!game.blackout){game.nextBlackout-=1;if(game.nextBlackout<=0&&game.hour>=20)triggerBlackout()}else{game.blackoutTimer-=1;if(game.blackoutTimer<=0)endBlackout()}}
function triggerBlackout(){game.blackout=true;game.blackoutTimer=1800;document.getElementById('blackoutOverlay').style.display='block';document.getElementById('blackoutText').style.display='block';game.robots.forEach(function(r){r.chasing=false});if(window.jarvisSpeak)jarvisSpeak('Warning! City blackout! Robots hunting! Find shelter!');if(window.jarvisAddTask)jarvisAddTask('Survive the blackout','Avoid robots until power restores','challenge')}
function endBlackout(){game.blackout=false;game.nextBlackout=21600+Math.random()*10800;document.getElementById('blackoutOverlay').style.display='none';document.getElementById('blackoutText').style.display='none';game.robots.forEach(function(r){r.chasing=false});if(window.jarvisGameCompleteTask)jarvisGameCompleteTask('Survive the blackout');if(window.jarvisSpeak)jarvisSpeak('Power restored.')}
function arrestPlayer(){game.paused=true;game.time-=3600;game.notoriety+=10;document.getElementById('arrestScreen').style.display='flex';document.getElementById('arrestDetail').textContent='You lost 1 hour. Notoriety: '+game.notoriety;if(window.jarvisSpeak)jarvisSpeak('You were caught! Lost time!')}
function restartDay(){document.getElementById('arrestScreen').style.display='none';game.paused=false;game.player.x=3200;game.player.y=3200;game.hour=8;game.minute=0;game.blackout=false;document.getElementById('blackoutOverlay').style.display='none';document.getElementById('blackoutText').style.display='none';game.robots.forEach(function(r){r.chasing=false;r.x=r.patrolX;r.y=r.patrolY})}
function gameOver(){game.running=false;showDialogue('GAME OVER','You ran out of time. Day: '+game.day+' | Crypto: '+game.crypto.toFixed(2)+' INC')}
function render(){ctx.fillStyle='#0a0a15';ctx.fillRect(0,0,W,H);var c=game.camera;
DISTRICTS.forEach(function(d){var sx=d.x-c.x,sy=d.y-c.y;if(sx+d.w<0||sy+d.h<0||sx>W||sy>H)return;ctx.fillStyle=d.color;ctx.fillRect(sx,sy,d.w,d.h);ctx.strokeStyle='rgba(15,52,96,0.5)';ctx.lineWidth=2;ctx.strokeRect(sx,sy,d.w,d.h);if(sx>-200&&sy>-50&&sx<W&&sy<H){ctx.fillStyle='rgba(233,69,96,0.4)';ctx.font='14px Segoe UI';ctx.fillText(d.name,sx+10,sy+20)}});
ctx.fillStyle='rgba(40,40,60,0.6)';STREETS.forEach(function(s){var sx=s.x-c.x,sy=s.y-c.y;if(s.h){if(sy+s.h<0||sy>H)return;ctx.fillRect(sx,sy,s.w,s.h)}else{if(sx+s.w<0||sx>W)return;ctx.fillRect(sx,sy,s.w,s.h)}});
var bcolors={keyhouse:'#3a2a1a',cave:'#1a1a0a',bank:'#1a2a3a',store:'#2a2a3a',school:'#3a2a2a',college:'#2a2a3a',casino:'#3a3a1a',brain:'#0a3a3a',underground:'#1a0a1a',courthouse:'#2a3a3a',hoverpark:'#0a3a2a',bar:'#3a1a2a',club:'#3a2a3a'};
BUILDINGS.forEach(function(b){var sx=b.x-c.x,sy=b.y-c.y;if(sx+b.w<0||sy+b.h<0||sx>W||sy>H)return;ctx.fillStyle=bcolors[b.type]||'#2a2a2a';ctx.fillRect(sx,sy,b.w,b.h);ctx.strokeStyle=game.blackout?'#330000':'#e94560';ctx.lineWidth=1.5;ctx.strokeRect(sx,sy,b.w,b.h);if(sx>-200&&sy>-30&&sx<W&&sy<H){ctx.fillStyle=game.blackout?'rgba(100,50,50,0.6)':'rgba(255,255,255,0.7)';ctx.font='10px Segoe UI';ctx.fillText(b.name,sx+4,sy-4)}var dist=Math.sqrt(Math.pow(b.x-game.player.x,2)+Math.pow(b.y-game.player.y,2));if(dist<80){ctx.fillStyle='#00ffcc';ctx.font='bold 12px Segoe UI';ctx.fillText('[E]',sx+b.w/2-8,sy-8)}});
game.npcs.forEach(function(n){var sx=n.x-c.x,sy=n.y-c.y;if(sx<-20||sy<-20||sx>W+20||sy>H+20)return;if(n.isRobot){ctx.fillStyle='#666';ctx.fillRect(sx-5,sy-5,10,10)}else{ctx.fillStyle=n.color;ctx.beginPath();ctx.arc(sx,sy,6,0,Math.PI*2);ctx.fill()}var d=Math.sqrt(Math.pow(n.x-game.player.x,2)+Math.pow(n.y-game.player.y,2));if(d<60){ctx.fillStyle='rgba(255,255,255,0.6)';ctx.font='9px Segoe UI';ctx.fillText(n.name,sx-12,sy-10)}});
game.robots.forEach(function(r){var sx=r.x-c.x,sy=r.y-c.y;if(sx<-30||sy<-30||sx>W+30||sy>H+30)return;ctx.fillStyle=r.chasing?'#ff0000':'#aa3333';ctx.fillRect(sx-8,sy-8,16,16);ctx.fillStyle=r.chasing?'#ffff00':'#ff6666';ctx.fillRect(sx-3,sy-3,6,6);if(game.blackout){ctx.strokeStyle=r.chasing?'rgba(255,0,0,0.2)':'rgba(255,100,100,0.1)';ctx.beginPath();ctx.arc(sx,sy,r.alertRadius,0,Math.PI*2);ctx.stroke()}});
game.vehicles.forEach(function(v){if(v===game.player.onVehicle)return;var sx=v.x-c.x,sy=v.y-c.y;if(sx<-30||sy<-30||sx>W+30||sy>H+30)return;ctx.fillStyle=v.type.color;ctx.fillRect(sx-v.type.size/2,sy-v.type.size/2,v.type.size,v.type.size/2)});
var psx=game.player.x-c.x,psy=game.player.y-c.y;if(game.player.onVehicle){var v=game.player.onVehicle;ctx.fillStyle=v.type.color;ctx.fillRect(psx-v.type.size/2,psy-v.type.size/3,v.type.size,v.type.size*0.66)}
ctx.fillStyle='#e94560';ctx.beginPath();ctx.arc(psx,psy,8,0,Math.PI*2);ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.stroke();ctx.strokeStyle='#00ffcc';ctx.beginPath();ctx.moveTo(psx,psy);ctx.lineTo(psx+Math.cos(game.player.angle)*15,psy+Math.sin(game.player.angle)*15);ctx.stroke();renderMinimap()}
function renderMinimap(){miniCtx.fillStyle='#0a0a15';miniCtx.fillRect(0,0,180,180);var s=180/CITY_SIZE;DISTRICTS.forEach(function(d){miniCtx.fillStyle=d.color;miniCtx.fillRect(d.x*s,d.y*s,d.w*s,d.h*s)});miniCtx.fillStyle='#e94560';BUILDINGS.forEach(function(b){miniCtx.fillRect(b.x*s-1,b.y*s-1,3,3)});miniCtx.fillStyle='rgba(100,200,100,0.5)';game.npcs.forEach(function(n){miniCtx.fillRect(n.x*s,n.y*s,1,1)});miniCtx.fillStyle='#ff3333';game.robots.forEach(function(r){miniCtx.fillRect(r.x*s-1,r.y*s-1,2,2)});miniCtx.fillStyle='#00ffcc';miniCtx.fillRect(game.player.x*s-2,game.player.y*s-2,4,4)}
function updateUI(){var h=Math.floor(game.time/3600),m=Math.floor((game.time%3600)/60),s=Math.floor(game.time%60);document.getElementById('timeDisplay').textContent=String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');document.getElementById('cryptoDisplay').textContent='Incentives Inc.: '+game.crypto.toFixed(2);document.getElementById('locationDisplay').textContent='Mega City - '+game.currentLocation;document.getElementById('dayDisplay').textContent='Day '+game.day+' | '+String(Math.floor(game.hour)).padStart(2,'0')+':'+String(Math.floor(game.minute)).padStart(2,'0');var vh=document.getElementById('vehicleHud');if(game.player.onVehicle){vh.style.display='block';vh.textContent='Vehicle: '+game.player.onVehicle.type.name+' (V to dismount)'}else vh.style.display='none'}
var nearbyBuilding=null;
function checkNearby(){nearbyBuilding=null;var closest=null,cd=80;BUILDINGS.forEach(function(b){var d=Math.sqrt(Math.pow(b.x-game.player.x,2)+Math.pow(b.y-game.player.y,2));if(d<cd){closest=b;cd=d}});nearbyBuilding=closest;var pr=document.getElementById('interactionPrompt');if(closest){pr.style.display='block';pr.textContent='Press E to enter '+closest.name}else{var nn=null;game.npcs.forEach(function(n){var d=Math.sqrt(Math.pow(n.x-game.player.x,2)+Math.pow(n.y-game.player.y,2));if(d<40)nn=n});if(nn){pr.style.display='block';pr.textContent='Press E to talk to '+nn.name}else pr.style.display='none'}}
function tryInteract(){if(!game.running||game.paused)return;if(nearbyBuilding){enterBuilding(nearbyBuilding);return}game.npcs.forEach(function(n){var d=Math.sqrt(Math.pow(n.x-game.player.x,2)+Math.pow(n.y-game.player.y,2));if(d<40){var msg=n.dialogue[Math.floor(Math.random()*n.dialogue.length)];showDialogue(n.name,msg+(n.isStudent?' (Student)':n.isWorker?' (Worker)':n.isRobot?' (Robot)':''));game.time+=30;if(window.jarvisSpeak)jarvisSpeak(n.name+' says: '+msg);return}})}
function enterBuilding(b){var handlers={keyhouse:enterKeyhouse,cave:enterCave,school:function(){openOverlay('school','high')},college:function(){openOverlay('school','college')},casino:function(){openOverlay('casino')},brain:function(){openOverlay('brain')},underground:enterUnderground,courthouse:function(){openOverlay('courthouse')},hoverpark:function(){openOverlay('hoverpark')},store:function(){openStore(b)},bank:openBar_enter,bar:enterBar,club:enterClub};if(handlers[b.type])handlers[b.type]();else showDialogue(b.name,'This building is closed or under construction.')}
function openBar_enter(){openBank()}
function showDialogue(title,text){var box=document.getElementById('dialogueBox');document.getElementById('dialogueTitle').textContent=title;document.getElementById('dialogueText').textContent=text;box.style.display='block'}
function closeDialogue(){document.getElementById('dialogueBox').style.display='none'}
function togglePause(){game.paused=!game.paused;if(game.paused)showDialogue('Paused','Game paused. Press ESC to resume.');else closeDialogue()}
function showAbout(){showDialogue('Mega City','A 60-mile open world city. Time is your life - earn it by working, learning, and completing missions. Incentives Inc. is the crypto currency. Survive blackouts, explore Keyhouse, attend school, gamble at the casino, hack the Central Brain, buy property, create businesses, and ride hover vehicles. Use JARVIS for voice/text control and agent chat.')}

// --- Keyhouse ---
function enterKeyhouse(){
showDialogue('Keyhouse Manor','The grand Keyhouse Manor stands as it did in the Lock & Key series.\nThe wooden doors, the grandfather clock, the mysterious hallways.\nSomewhere inside are magical keys hidden by the Locke family.\nThe grounds stretch out behind the manor with ancient trees.');
game.time+=120;
if(window.jarvisAddTask){jarvisAddTask('Explore Keyhouse','Search the manor for hidden keys','objective');jarvisAddTask('Visit the Cave','The cave beneath Keyhouse holds secrets','side');jarvisAddTask('Walk the grounds','Explore the Keyhouse estate grounds','side')}
if(Math.random()<0.3){game.keys++;game.inventory.push('Mysterious Key');showDialogue('Found!','You discovered a mysterious key hidden in Keyhouse!');if(window.jarvisGameCompleteTask)jarvisGameCompleteTask('Explore Keyhouse');if(window.jarvisSpeak)jarvisSpeak('You found a mysterious key!')}
}
function enterCave(){
showDialogue('The Cave','A dark cave beneath Keyhouse. The walls glow with strange symbols.\nThis is where the Locke family kept their most dangerous secrets.\nYou feel a strange energy emanating from deep within.');
game.time+=60;
if(Math.random()<0.2){game.crypto+=10;showDialogue('Crypto Found!','You found 10 INC crypto in the cave!')}
}

// --- Overlay System ---
function openOverlay(type,sub){
var t=document.getElementById('overlayTitle'),c=document.getElementById('overlayContent');
if(type==='school'){t.textContent=sub==='college'?'Mega City University':'Mega City High School (Bully-Style)';c.innerHTML=renderSchool(sub)}
else if(type==='casino'){t.textContent='Lucky Star Casino';c.innerHTML=renderCasino()}
else if(type==='brain'){t.textContent='CITY BRAIN - CENTRAL COMPUTER';c.innerHTML=renderBrain()}
else if(type==='courthouse'){t.textContent='Mega City Courthouse';c.innerHTML=renderCourthouse()}
else if(type==='hoverpark'){t.textContent='Hover Vehicle Station';c.innerHTML=renderHoverPark()}
else if(type==='property'){t.textContent='Mega City Real Estate';c.innerHTML=renderProperty()}
document.getElementById('overlayUI').style.display='flex';game.paused=true;
}
function closeOverlay(){document.getElementById('overlayUI').style.display='none';game.paused=false}

// --- School ---
function renderSchool(level){
if(level==='high'){
return '<p style="color:#888;margin-bottom:16px;">Welcome to Mega City High! Attend classes to earn time, cause mischief, or hang out.</p>'+
(game.schoolEnrolled.high?renderClasses('high'):'<div class="class-card" onclick="enrollSchool(\'high\')"><div class="class-title">Enroll at Mega City High</div><div class="class-desc">Sign up as a student. Earn time by attending classes.</div><div class="class-reward">+3600s per class | Learn skills</div></div>')+
'<div class="class-card" onclick="causeMischief()"><div class="class-title">Cause Mischief</div><div class="class-desc">Prank students, skip class, cause trouble (Bully-style)</div><div class="class-reward">+50 INC | +5 notoriety | Risk getting caught</div></div>'+
'<div class="class-card" onclick="talkToStudents()"><div class="class-title">Talk to Students</div><div class="class-desc">Socialize with other students</div><div class="class-reward">+60s life time</div></div>';
}
return '<p style="color:#888;margin-bottom:16px;">Mega City University - Professional education. CS, Business, Engineering, Medicine, Law, Arts, Economics, Political Science.</p>'+
(game.schoolEnrolled.college?renderClasses('college'):'<div class="class-card" onclick="enrollSchool(\'college\')"><div class="class-title">Apply to Mega City University</div><div class="class-desc">Submit acceptance letter and pick your major. All electives a college offers.</div><div class="class-reward">+7200s per class | Professional skills</div></div>')+
'<div class="class-card" onclick="talkToProfessors()"><div class="class-title">Talk to Professors</div><div class="class-desc">Interact with professors for advice and bonus time</div><div class="class-reward">+120s | Professor interactions</div></div>'+
'<div class="class-card" onclick="pickElectives()"><div class="class-title">Pick Electives</div><div class="class-desc">Choose from all electives a college has to offer</div><div class="class-reward">Various rewards</div></div>';
}
function renderClasses(level){
var cls=level==='high'?[
{n:'Math Class',d:'Algebra and geometry',t:3600,s:'math'},{n:'English Class',d:'Reading and writing',t:3600,s:'english'},
{n:'Science Class',d:'Biology and chemistry',t:3600,s:'science'},{n:'History Class',d:'World and city history',t:3600,s:'history'},
{n:'Gym Class',d:'Physical education',t:3600,s:'gym'},{n:'Art Class',d:'Creative expression',t:3600,s:'art'}
]:[
{n:'Computer Science',d:'Programming, AI, cybersecurity, algorithms',t:7200,s:'cs'},{n:'Business Administration',d:'Management, finance, entrepreneurship',t:7200,s:'business'},
{n:'Engineering',d:'Mechanical, electrical, software',t:7200,s:'engineering'},{n:'Medicine',d:'Medical science and healthcare',t:7200,s:'medicine'},
{n:'Law',d:'Legal studies and justice',t:7200,s:'law'},{n:'Arts & Design',d:'Digital arts, architecture, design',t:7200,s:'arts'},
{n:'Economics',d:'Market analysis and crypto economics',t:7200,s:'economics'},{n:'Political Science',d:'Governance and city management',t:7200,s:'politics'}
];
return '<p style="color:#e94560;margin-bottom:8px;">Enrolled! Pick a class:</p>'+cls.map(function(c){
return '<div class="class-card" onclick="attendClass(\''+c.s+'\',\''+c.n+'\','+c.t+')"><div class="class-title">'+c.n+'</div><div class="class-desc">'+c.d+'</div><div class="class-reward">+'+c.t+'s | Skill: '+c.s+'</div></div>';
}).join('');
}
function enrollSchool(level){
if(level==='high'){game.schoolEnrolled.high=true;showDialogue('Enrolled!','You are now a student at Mega City High!');if(window.jarvisAddTask){jarvisAddTask('Attend high school classes','Go to class to earn life time','objective');jarvisAddTask('Cause mischief at school','Prank students (Bully-style)','side')}}
else{game.schoolEnrolled.college=true;var m=prompt('Pick major: Computer Science, Business, Engineering, Medicine, Law, Arts, Economics, Political Science:');if(m)game.collegeMajor=m;showDialogue('Accepted!','Welcome to MCU! Major: '+(game.collegeMajor||'Undeclared'));if(window.jarvisAddTask){jarvisAddTask('Attend college classes','Go to class to earn time and skills','objective');jarvisAddTask('Talk to professors','Interact with professors for bonuses','side')}}
closeOverlay();openOverlay('school',level);
}
function attendClass(skill,name,tr){game.time+=tr;game.grades.high[skill]=(game.grades.high[skill]||0)+1;closeOverlay();showDialogue('Class Complete!','You attended '+name+'. +'+tr+'s life time! Skill '+skill+' increased.');if(window.jarvisSpeak)jarvisSpeak('Class attended. Time earned.');if(window.jarvisGameCompleteTask)jarvisGameCompleteTask('Attend')}
function causeMischief(){if(Math.random()<0.3){game.time-=600;game.notoriety+=5;closeOverlay();showDialogue('Caught!','You got caught! -600s, +5 notoriety.')}else{game.crypto+=50;game.notoriety+=5;closeOverlay();showDialogue('Mischief!','You pulled off a prank! +50 INC. Notoriety +5.');if(window.jarvisGameCompleteTask)jarvisGameCompleteTask('Cause mischief')}}
function talkToStudents(){game.time+=60;closeOverlay();var n=NPC_NAMES[Math.floor(Math.random()*NPC_NAMES.length)];var t=['wants to skip class','is studying for exams','heard about a blackout','is trading crypto','wants to cause trouble','knows about the underground city'];showDialogue(n,n+' '+t[Math.floor(Math.random()*t.length)]+'.')}
function talkToProfessors(){game.time+=120;closeOverlay();var p=['Dr. Chen (CS)','Prof. Williams (Business)','Dr. Patel (Engineering)','Prof. Garcia (Law)'];var a=['Study hard to earn more time.','The Central Brain controls everything.','Crypto is the future. Invest in INC.','During blackouts, stay safe.','Go to the Courthouse to start a business.','The underground city has the best tech.'];var prof=p[Math.floor(Math.random()*p.length)];showDialogue(prof,prof+' says: '+a[Math.floor(Math.random()*a.length)]);if(window.jarvisGameCompleteTask)jarvisGameCompleteTask('Talk to professors')}
function pickElectives(){var e=['Music','Photography','Drama','Cooking','Robotics','Crypto Trading','Hacking 101','Urban Planning'];var h='<p style="color:#888;margin-bottom:12px;">Pick an elective:</p>';e.forEach(function(x){h+='<div class="class-card" onclick="takeElective(\''+x+'\')"><div class="class-title">'+x+'</div><div class="class-reward">+1800s | Skill bonus</div></div>'});document.getElementById('overlayContent').innerHTML=h}

function takeElective(n){game.time+=1800;closeOverlay();showDialogue('Elective Complete!','You took '+n+'. +1800s!');if(n==='Hacking 101')game.hackingLevel++;if(n==='Crypto Trading')game.crypto+=20}

// --- Casino ---
function renderCasino(){
return '<p style="color:#888;margin-bottom:16px;">Welcome to Lucky Star Casino! Gamble your INC crypto.</p>'+
'<div class="class-card" onclick="casinoGame(\'slots\')"><div class="class-title">Slot Machine</div><div class="class-desc">Bet 10 INC. Match 3 symbols!</div><div class="class-reward">Win up to 500 INC</div></div>'+
'<div class="class-card" onclick="casinoGame(\'dice\')"><div class="class-title">Dice Roll</div><div class="class-desc">Bet 25 INC. Roll high to double.</div><div class="class-reward">Win 50 INC</div></div>'+
'<div class="class-card" onclick="casinoGame(\'blackjack\')"><div class="class-title">Blackjack</div><div class="class-desc">Bet 50 INC. Beat dealer to 21.</div><div class="class-reward">Win 100 INC</div></div>'+
'<div class="class-card" onclick="casinoGame(\'roulette\')"><div class="class-title">Roulette</div><div class="class-desc">Bet 100 INC. Red or black.</div><div class="class-reward">Win 200 INC</div></div>'+
'<p style="color:#ffcc00;margin-top:12px;">Your INC: '+game.crypto.toFixed(2)+'</p>';
}
function casinoGame(type){var bet={slots:10,dice:25,blackjack:50,roulette:100}[type];if(game.crypto<bet){showDialogue('Not enough','You need '+bet+' INC.');return}game.crypto-=bet;if(Math.random()<0.4){var pay={slots:500,dice:50,blackjack:100,roulette:200}[type];game.crypto+=pay;closeOverlay();showDialogue('WIN!','You won '+pay+' INC! Total: '+game.crypto.toFixed(2));if(window.jarvisSpeak)jarvisSpeak('You won at the casino!')}else{closeOverlay();showDialogue('Loss','You lost '+bet+' INC. Total: '+game.crypto.toFixed(2))}}

// --- Central Brain ---
function renderBrain(){
return '<p style="color:#00ffcc;margin-bottom:16px;">The Central Computer Brain manages all of Mega City: lights, traffic, robots, computers, and the time on every citizen\'s forearm.</p>'+
'<p style="color:#888;margin-bottom:12px;">Underground, massive servers store all city data. The underground city houses people and robots who maintain it.</p>'+
'<div style="margin:20px 0;color:#888;font-size:12px;text-align:left;">Day: '+game.day+' | Time: '+Math.floor(game.hour)+':'+String(Math.floor(game.minute)).padStart(2,'0')+'<br>Robots: '+game.robots.length+' | NPCs: '+game.npcs.length+'<br>Blackout: '+(game.blackout?'ACTIVE':'Standby')+'<br>Your notoriety: '+game.notoriety+'</div>'+
'<button class="btn" onclick="hackBrain()">Hack City Brain</button><button class="btn" onclick="enterUnderground()">Enter Underground City</button><button class="btn" onclick="closeOverlay()">Exit</button>';
}
function hackBrain(){if(game.hackingLevel<3){showDialogue('Hack Failed','Hacking level too low (need 3). Take Hacking 101 at school.');return}if(Math.random()<0.5){game.crypto+=500;game.time+=3600;game.notoriety+=20;closeOverlay();showDialogue('HACK SUCCESSFUL!','+500 INC, +3600s. Notoriety +20.');if(window.jarvisSpeak)jarvisSpeak('City Brain hacked!')}else{game.time-=1800;game.notoriety+=30;closeOverlay();showDialogue('HACK FAILED!','Detected! -1800s. Notoriety +30. Robots alert!');game.robots.forEach(function(r){r.alertRadius+=50})}}

// --- Underground ---
function enterUnderground(){closeOverlay();showDialogue('Underground City','You descend into the massive underground city beneath the Central Brain.\nThousands of servers hum around you. People and robots live here,\nmaintaining the computer that runs all of Mega City.');game.time+=300;game.crypto+=25;if(window.jarvisAddTask)jarvisAddTask('Explore underground city','Find tech below the surface','side');if(Math.random()<0.4){game.hackingLevel++;showDialogue('Tech Found!','You found advanced tech! Hacking level increased!')}}

// --- Courthouse ---
function renderCourthouse(){
return '<p style="color:#888;margin-bottom:16px;">Mega City Courthouse - Face real laws, or create a business entity.</p>'+
(game.notoriety>0?'<div class="class-card" onclick="faceTrial()"><div class="class-title">Face Trial</div><div class="class-desc">Your notoriety is '+game.notoriety+'. Face justice.</div><div class="class-reward">Clear notoriety | Risk losing time</div></div>':'')+
'<div class="class-card" onclick="createBusiness()"><div class="class-title">Business Entity Creation Department</div><div class="class-desc">File to create a business. Fill out applications and pay the fee.</div><div class="class-reward">Own a business | Passive INC income</div></div>'+
'<div class="class-card" onclick="createCrypto()"><div class="class-title">Create Your Own Crypto Currency</div><div class="class-desc">File paperwork to launch your own crypto in Mega City.</div><div class="class-reward">Own crypto | Trade on exchange</div></div>'+
'<div class="class-card" onclick="transferTitle()"><div class="class-title">Property Title Transfer</div><div class="class-desc">Put property titles in your name officially.</div><div class="class-reward">Official ownership</div></div>';
}
function faceTrial(){if(Math.random()<0.6){game.time-=game.notoriety*120;showDialogue('GUILTY','Lost '+(game.notoriety*120)+'s.');game.notoriety=0}else{showDialogue('NOT GUILTY','Acquitted! Notoriety cleared.');game.notoriety=0}closeOverlay()}
function createBusiness(){var n=prompt('Business name:');if(!n)return;var fee=500;if(game.crypto<fee){showDialogue('Insufficient Funds','Need '+fee+' INC.');return}game.crypto-=fee;var t=prompt('Type (store, tech, restaurant, crypto, entertainment, property):');game.businesses.push({name:n,type:t||'store',income:20+Math.random()*80,day:game.day});closeOverlay();showDialogue('Business Created!',n+' registered! Passive INC income daily.');if(window.jarvisAddTask)jarvisAddTask('Manage '+n,'Passive income business','side');if(window.jarvisSpeak)jarvisSpeak('Business entity created!')}
function createCrypto(){var n=prompt('Name your crypto currency:');if(!n)return;var fee=1000;if(game.crypto<fee){showDialogue('Insufficient Funds','Need '+fee+' INC.');return}game.crypto-=fee;game.cryptoOwned={name:n,value:1.0,supply:10000,owned:10000};closeOverlay();showDialogue('Crypto Launched!',n+' now trading on Mega City exchange! You own 10,000 '+n+'.');if(window.jarvisSpeak)jarvisSpeak('Your crypto currency launched!')}
function transferTitle(){if(game.ownedProperties.length===0){showDialogue('No Properties','Buy some first.');return}var l=game.ownedProperties.map(function(p,i){return i+': '+p.name}).join('\n');var idx=prompt('Which property?\n'+l);if(idx!==null&&game.ownedProperties[parseInt(idx)]){game.ownedProperties[parseInt(idx)].titled=true;showDialogue('Title Transferred',game.ownedProperties[parseInt(idx)].name+' is now in your name!')}}

// --- Hover Vehicles ---
function renderHoverPark(){var h='<p style="color:#888;margin-bottom:16px;">Hover Vehicle Station - Buy or summon vehicles.</p>';VEHICLE_TYPES.forEach(function(v,i){h+='<div class="class-card" onclick="buyVehicle('+i+')"><div class="class-title">'+v.name+' - '+v.cost+' INC</div><div class="class-desc">Speed: '+v.speed+' | Color: '+v.color+'</div><div class="class-reward">Faster travel</div></div>'});h+='<div class="class-card" onclick="summonVehicle()"><div class="class-title">Summon Owned Vehicle</div><div class="class-desc">Call your nearest owned vehicle</div></div>';return h}
function buyVehicle(i){var v=VEHICLE_TYPES[i];if(game.crypto<v.cost){showDialogue('Not enough INC','Need '+v.cost+' INC.');return}game.crypto-=v.cost;game.vehicles.push({id:'v'+game.vehicles.length,type:v,x:game.player.x,y:game.player.y+30,owned:true,parked:true});closeOverlay();showDialogue('Purchased!','You bought a '+v.name+'! Press V to mount.');if(window.jarvisSpeak)jarvisSpeak('Vehicle purchased!')}
function summonVehicle(){var c=null,cd=99999;game.vehicles.forEach(function(v){if(!v.owned)return;var d=Math.sqrt(Math.pow(v.x-game.player.x,2)+Math.pow(v.y-game.player.y,2));if(d<cd){c=v;cd=d}});if(c){c.x=game.player.x+30;c.y=game.player.y+30;closeOverlay();showDialogue('Vehicle Summoned','Your '+c.type.name+' has been summoned!')}else showDialogue('No Vehicle','You do not own any vehicles.')}
function toggleVehicle(){if(game.player.onVehicle){game.player.onVehicle.x=game.player.x;game.player.onVehicle.y=game.player.y+20;game.player.onVehicle.parked=true;game.player.onVehicle=null;if(window.jarvisSpeak)jarvisSpeak('Dismounted.')}else{var c=null,cd=50;game.vehicles.forEach(function(v){if(!v.owned)return;var d=Math.sqrt(Math.pow(v.x-game.player.x,2)+Math.pow(v.y-game.player.y,2));if(d<cd){c=v;cd=d}});if(c){game.player.onVehicle=c;c.parked=false;if(window.jarvisSpeak)jarvisSpeak('Mounted '+c.type.name)}else showDialogue('No Vehicle Nearby','Visit the Hover Park or summon one.')}}

// --- Property ---
function renderProperty(){var h='<p style="color:#888;margin-bottom:16px;">Mega City Real Estate - Buy property, own buildings, upgrade them.</p><p style="color:#ffcc00;margin-bottom:12px;">Your INC: '+game.crypto.toFixed(2)+'</p>';PROPERTIES.forEach(function(p){var owned=game.ownedProperties.find(function(o){return o.id===p.id});if(owned){h+='<div class="class-card" style="border-color:#22c55e;"><div class="class-title" style="color:#22c55e;">'+p.name+' (OWNED)</div><div class="class-desc">Income: '+p.income+' INC/day | Type: '+p.type+(owned.titled?' | Titled':'')+'</div><button class="btn" onclick="upgradeProperty(\''+p.id+'\')">Upgrade ('+Math.floor(p.price*0.3)+' INC)</button></div>'}else{h+='<div class="class-card" onclick="buyProperty(\''+p.id+'\')"><div class="class-title">'+p.name+'</div><div class="class-desc">Price: '+p.price+' INC | Income: '+p.income+' INC/day | Type: '+p.type+'</div><div class="class-reward">Buy for passive income</div></div>'}});return h}
function buyProperty(id){var p=PROPERTIES.find(function(pr){return pr.id===id});if(!p)return;if(game.crypto<p.price){showDialogue('Not enough INC','Need '+p.price+' INC.');return}game.crypto-=p.price;game.ownedProperties.push({id:p.id,name:p.name,price:p.price,income:p.income,type:p.type,titled:false,upgrades:0});closeOverlay();showDialogue('Purchased!','You now own '+p.name+'! '+p.income+' INC/day.');if(window.jarvisSpeak)jarvisSpeak('Property purchased!');if(window.jarvisAddTask)jarvisAddTask('Collect income from '+p.name,'Passive: '+p.income+' INC/day','side')}
function upgradeProperty(id){var p=game.ownedProperties.find(function(pr){return pr.id===id});if(!p)return;var cost=Math.floor(p.price*0.3);if(game.crypto<cost){showDialogue('Not enough INC','Upgrade costs '+cost+' INC.');return}game.crypto-=cost;p.income+=Math.floor(p.income*0.5);p.upgrades++;closeOverlay();showDialogue('Upgraded!',p.name+' now generates '+p.income+' INC/day!');openOverlay('property')}

// --- Store ---
function openStore(b){showDialogue(b.name,'Welcome to '+b.name+'!\n\n1. Health Pack: 50 INC\n2. Time Capsule (+3600s): 200 INC\n3. Hacking Tool: 100 INC\n4. Speed Boost: 30 INC');var c=prompt('Buy: 1=Health, 2=Time, 3=HackTool, 4=Speed');var items={'1':{n:'Health Pack',c:50,f:function(){game.player.health=100}},'2':{n:'Time Capsule',c:200,f:function(){game.time+=3600}},'3':{n:'Hacking Tool',c:100,f:function(){game.hackingLevel++}},'4':{n:'Speed Boost',c:30,f:function(){game.player.speed+=0.5}}};if(c&&items[c]){var it=items[c];if(game.crypto>=it.c){game.crypto-=it.c;it.f();game.inventory.push(it.n);showDialogue('Purchased!','You bought a '+it.n+'!')}else showDialogue('Not enough INC','Need '+it.c+' INC.')}}

// --- Bank ---
function openBank(){showDialogue('Central Bank','Exchange time for INC or INC for time.\n1. 3600s time -> 100 INC\n2. 100 INC -> 3600s time');var c=prompt('1=Time->INC, 2=INC->Time');if(c==='1'){if(game.time>7200){game.time-=3600;game.crypto+=100;showDialogue('Trade Complete','-3600s, +100 INC')}else showDialogue('Not enough time','Need >2 hours.')}else if(c==='2'){if(game.crypto>=100){game.crypto-=100;game.time+=3600;showDialogue('Trade Complete','-100 INC, +3600s')}else showDialogue('Not enough INC','Need 100 INC.')}}

// --- Bar/Club ---
function enterBar(){game.time+=120;game.crypto-=10;if(game.crypto<0)game.crypto=0;showDialogue('Neon Bar','You had a drink. +120s, -10 INC. Refreshed!')}
function enterClub(){game.time+=180;game.crypto-=25;if(game.crypto<0)game.crypto=0;showDialogue('Pulse Club','You danced at Pulse Club! +180s, -25 INC. Electric!')}

// --- Hacking ---
function tryHack(){if(!game.running||game.paused)return;var hackable=null;BUILDINGS.forEach(function(b){var d=Math.sqrt(Math.pow(b.x-game.player.x,2)+Math.pow(b.y-game.player.y,2));if(d<60&&['bank','store','brain','casino'].includes(b.type))hackable=b});if(!hackable){showDialogue('No Target','No hackable building nearby. Stand near a bank, store, casino, or the Central Brain.');return}if(game.hackingLevel<1){showDialogue('No Skill','Take Hacking 101 at school first.');return}var success=Math.random()<(0.3+game.hackingLevel*0.1);if(success){var reward=50+game.hackingLevel*25;game.crypto+=reward;game.notoriety+=5;showDialogue('HACK SUCCESS','You hacked '+hackable.name+'! +'+reward+' INC. Notoriety +5.');if(window.jarvisSpeak)jarvisSpeak('Hack successful!')}else{game.time-=300;game.notoriety+=10;showDialogue('HACK FAILED','You failed to hack '+hackable.name+'. -300s. Notoriety +10.')}}

// --- JARVIS Commands ---
function registerJarvisCommands(){
if(!window.jarvisRegisterCommand)return;
jarvisRegisterCommand('go to school',function(){openOverlay('school','high');return'Opening Mega City High School'});
jarvisRegisterCommand('go to college',function(){openOverlay('school','college');return'Opening Mega City University'});
jarvisRegisterCommand('go to casino',function(){openOverlay('casino');return'Opening Lucky Star Casino'});
jarvisRegisterCommand('go to courthouse',function(){openOverlay('courthouse');return'Opening Mega City Courthouse'});
jarvisRegisterCommand('buy property',function(){openOverlay('property');return'Opening Real Estate'});
jarvisRegisterCommand('get vehicle',function(){openOverlay('hoverpark');return'Opening Hover Vehicle Station'});
jarvisRegisterCommand('check time',function(){var h=Math.floor(game.time/3600),m=Math.floor((game.time%3600)/60);return'You have '+h+' hours and '+m+' minutes of life remaining'});
jarvisRegisterCommand('check crypto',function(){return'You have '+game.crypto.toFixed(2)+' Incentives Inc. crypto'});
jarvisRegisterCommand('check notoriety',function(){return'Your notoriety is '+game.notoriety});
jarvisRegisterCommand('go to keyhouse',function(){game.player.x=350;game.player.y=350;return'Teleported to Keyhouse Manor'});
jarvisRegisterCommand('go to brain',function(){game.player.x=3900;game.player.y=3900;return'Teleported to Central Computer Brain'});
jarvisRegisterCommand('go underground',function(){enterUnderground();return'Entering underground city'});
jarvisRegisterCommand('hack',function(){tryHack();return'Attempting hack'});
jarvisRegisterCommand('summon vehicle',function(){summonVehicle();return'Summoning vehicle'});
jarvisRegisterCommand('mount vehicle',function(){toggleVehicle();return'Toggling vehicle'});
jarvisRegisterCommand('check inventory',function(){return'You have: '+(game.inventory.length?game.inventory.join(', '):'nothing')+' | Keys: '+game.keys});
jarvisRegisterCommand('where am i',function(){return'You are in '+game.currentLocation+' on Day '+game.day});
jarvisRegisterCommand('cause mischief',function(){causeMischief();return'Causing mischief at school'});
jarvisRegisterCommand('enroll school',function(){enrollSchool('high');return'Enrolling at Mega City High'});
jarvisRegisterCommand('enroll college',function(){enrollSchool('college');return'Applying to Mega City University'});
jarvisRegisterCommand('create business',function(){openOverlay('courthouse');return'Opening courthouse for business creation'});
jarvisRegisterCommand('create crypto',function(){createCrypto();return'Creating your own crypto currency'});
}

// --- Game Start ---
function startGame(){
document.getElementById('menuScreen').style.display='none';
game.running=true;game.paused=false;
initNPCs();initRobots();initVehicles();
if(window.jarvisSetContext)jarvisSetContext({location:game.currentLocation,day:game.day,time:game.time});
if(window.jarvisAddTask){
jarvisAddTask('Explore Mega City','Walk around and discover districts','objective');
jarvisAddTask('Visit Keyhouse','Explore the Lock & Key manor','objective');
jarvisAddTask('Enroll in school','Go to high school or college to earn time','objective');
jarvisAddTask('Earn Incentives Inc.','Work, gamble, or trade for INC crypto','objective');
jarvisAddTask('Buy property','Own buildings for passive income','side');
jarvisAddTask('Try hover vehicles','Visit the Hover Park for fast travel','side');
jarvisAddTask('Survive a blackout','Avoid robots during blackouts','challenge');
jarvisAddTask('Hack the Central Brain','Break into the city computer (need hacking 3)','challenge');
jarvisAddTask('Create a business','File at the courthouse','side');
jarvisAddTask('Talk to NPCs','Meet the people of Mega City','side');
}
registerJarvisCommands();
loop();
}

// Expose globals
window.startGame=startGame;
window.showAbout=showAbout;
window.closeDialogue=closeDialogue;
window.closeOverlay=closeOverlay;
window.restartDay=restartDay;
window.enrollSchool=enrollSchool;
window.attendClass=attendClass;
window.causeMischief=causeMischief;
window.talkToStudents=talkToStudents;
window.talkToProfessors=talkToProfessors;
window.pickElectives=pickElectives;
window.takeElective=takeElective;
window.casinoGame=casinoGame;
window.hackBrain=hackBrain;
window.enterUnderground=enterUnderground;
window.faceTrial=faceTrial;
window.createBusiness=createBusiness;
window.createCrypto=createCrypto;
window.transferTitle=transferTitle;
window.buyVehicle=buyVehicle;
window.summonVehicle=summonVehicle;
window.toggleVehicle=toggleVehicle;
window.buyProperty=buyProperty;
window.upgradeProperty=upgradeProperty;
window.openOverlay=openOverlay;
window.tryHack=tryHack;
</script>
</body>
</html>
'''
