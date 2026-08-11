
        let pollInterval = null;
        let currentJobId = null;
        
        // === ACTION TELEMETRY ===
        // Captures every user interaction and sends to /api/log
        // Can be toggled off later for performance
        const TELEMETRY_ENABLED = true;
        let _telemetryBuffer = [];
        let _telemetryFlushTimer = null;
        
        function _getActiveTab() {
            const active = document.querySelector('.tab-content:not([style*="display: none"])');
            return active ? active.id : 'unknown';
        }
        
        function _getElementInfo(el) {
            const tag = el.tagName.toLowerCase();
            const type = el.getAttribute('type') || '';
            const id = el.id || el.getAttribute('data-id') || el.className || tag;
            let elType = 'other';
            if (tag === 'button' || tag === 'a') elType = 'button';
            else if (tag === 'select') elType = 'select';
            else if (tag === 'input') elType = type || 'input';
            else if (tag === 'textarea') elType = 'textarea';
            else if (el.classList.contains('tab-btn')) elType = 'tab';
            else if (tag === 'input' && type === 'range') elType = 'slider';
            else if (tag === 'input' && type === 'checkbox') elType = 'checkbox';
            return { id: id, type: elType, tag: tag };
        }
        
        function _sendTelemetry(eventType, elementId, elementType, value, extra) {
            if (!TELEMETRY_ENABLED) return;
            const payload = {
                event_type: eventType,
                element_id: elementId,
                element_type: elementType,
                value: value !== undefined ? String(value).substring(0, 200) : null,
                page: _getActiveTab(),
                extra: extra || {},
            };
            _telemetryBuffer.push(payload);
            
            // Batch send every 2 seconds or when buffer hits 10
            if (_telemetryFlushTimer) clearTimeout(_telemetryFlushTimer);
            if (_telemetryBuffer.length >= 10) {
                _flushTelemetry();
            } else {
                _telemetryFlushTimer = setTimeout(_flushTelemetry, 2000);
            }
        }
        
        async function _flushTelemetry() {
            if (_telemetryBuffer.length === 0) return;
            const batch = _telemetryBuffer.splice(0);
            for (const payload of batch) {
                try {
                    await fetch('/api/log', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(payload),
                    });
                } catch (e) { /* silent fail */ }
            }
        }
        
        // Global click listener — captures every button press
        document.addEventListener('click', function(e) {
            const el = e.target.closest('button, a, .tab-btn, [onclick]') || e.target;
            const info = _getElementInfo(el);
            _sendTelemetry('click', info.id, info.type, null, {
                text: (el.textContent || '').trim().substring(0, 50),
            });
        }, true);
        
        // Global change listener — captures select, checkbox, input changes
        document.addEventListener('change', function(e) {
            const el = e.target;
            const info = _getElementInfo(el);
            let value = el.value;
            if (el.type === 'checkbox') value = el.checked;
            _sendTelemetry('change', info.id, info.type, value);
        }, true);
        
        // Global input listener — captures text input (debounced via buffer)
        let _inputTimer = null;
        document.addEventListener('input', function(e) {
            const el = e.target;
            if (el.tagName === 'INPUT' && el.type === 'range') {
                // Slider — log on release (change event handles this)
                return;
            }
            const info = _getElementInfo(el);
            if (_inputTimer) clearTimeout(_inputTimer);
            _inputTimer = setTimeout(() => {
                _sendTelemetry('input', info.id, info.type, el.value);
            }, 1000);
        }, true);
        
        // Tab switch listener
        const _originalSwitchTab = window.switchTab;
        if (_originalSwitchTab) {
            window.switchTab = function(tab) {
                _sendTelemetry('switch', tab, 'tab', null);
                return _originalSwitchTab.call(this, tab);
            };
        }
        
        // Page unload — flush remaining telemetry
        window.addEventListener('beforeunload', function() {
            if (_telemetryBuffer.length > 0) {
                for (const payload of _telemetryBuffer) {
                    navigator.sendBeacon('/api/log', JSON.stringify(payload));
                }
            }
        });
        
        // Check backend status on load
        async function init() {
            const cfg = await fetch('/api/config').then(r => r.json());
            if (cfg.gpu_backend_url) {
                document.getElementById('backendUrl').value = cfg.gpu_backend_url;
                checkBackend();
            }
            loadVideos();
            imgInit();
            assetInit();
            setInterval(checkBackend, 30000);
        }
        
        async function checkBackend() {
            const status = await fetch('/api/backend/status').then(r => r.json());
            const badge = document.getElementById('gpuBadge');
            const statusText = document.getElementById('gpuStatus');
            const panel = document.getElementById('generatePanel');
            
            if (status.status === 'online') {
                badge.classList.add('online');
                statusText.textContent = status.gpu || 'GPU Connected';
                panel.classList.remove('disabled');
            } else {
                badge.classList.remove('online');
                statusText.textContent = 'Not connected';
                panel.classList.add('disabled');
            }
        }
        
        async function connectBackend() {
            const url = document.getElementById('backendUrl').value.trim();
            if (!url) {
                showToast('Enter a URL first', 'error');
                return;
            }
            
            const resp = await fetch('/api/config/backend', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url})
            }).then(r => r.json());
            
            if (resp.status === 'ok') {
                showToast('Backend connected!', 'success');
                checkBackend();
            } else {
                showToast('Failed to connect', 'error');
            }
        }
        
        function updateRange(id, valueId) {
            const el = document.getElementById(id);
            const valEl = document.getElementById(valueId);
            if (el && valEl) {
                const v = parseFloat(el.value);
                valEl.textContent = (id === 'guidanceScale' || id === 'flowShift' || id === 'cameraFov' || id === 'fxSharpenAmount') ? v.toFixed(1) : 
                    (id.startsWith('cg') || id === 'guidanceRescale' || id === 'creativityScale' || id === 'cameraSpeed' || id === 'cameraIntensity' || id === 'motionIntensity' || id === 'fxVignetteIntensity' || id === 'fxFilmGrainAmount') ? v.toFixed(2) : v;
            }
        }
        
        function switchSettingsTab(tabName) {
            document.querySelectorAll('.settings-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.settings-panel').forEach(p => p.classList.remove('active'));
            const btn = document.querySelector('.settings-tab[onclick*="' + tabName + '"]');
            if (btn) btn.classList.add('active');
            const panel = document.getElementById('settings-' + tabName);
            if (panel) panel.classList.add('active');
        }
        
        function applyQualityMode() {
            const mode = document.getElementById('qualityMode').value;
            const modeMap = {
                draft: {steps: 10, guidance: 3.0, rescale: 0.0},
                standard: {steps: 30, guidance: 5.0, rescale: 0.0},
                pro: {steps: 50, guidance: 5.0, rescale: 0.7},
                turbo: {steps: 5, guidance: 1.0, rescale: 0.7},
                ultra: {steps: 80, guidance: 6.0, rescale: 0.7},
            };
            const m = modeMap[mode];
            if (m) {
                document.getElementById('steps').value = m.steps;
                document.getElementById('stepsValue').textContent = m.steps;
                document.getElementById('guidanceScale').value = m.guidance;
                document.getElementById('guidanceScaleValue').textContent = m.guidance.toFixed(1);
                document.getElementById('guidanceRescale').value = m.rescale;
                document.getElementById('guidanceRescaleValue').textContent = m.rescale.toFixed(1);
            }
        }
        
        function applyAspectRatio() {
            const ratio = document.getElementById('aspectRatio').value;
            const ratioMap = {
                '16:9': [1280, 720], '9:16': [720, 1280], '1:1': [1024, 1024],
                '4:3': [1024, 768], '21:9': [1280, 544], '2.39:1': [1280, 536], '4:5': [896, 1120],
            };
            const dims = ratioMap[ratio];
            if (dims) {
                document.getElementById('resWidth').value = dims[0];
                document.getElementById('resWidthValue').textContent = dims[0];
                document.getElementById('resHeight').value = dims[1];
                document.getElementById('resHeightValue').textContent = dims[1];
            }
        }
        
        function applyCameraPreset() {
            const preset = document.getElementById('cameraPreset').value;
            document.getElementById('cameraEnabled').checked = preset !== 'static';
        }
        
        function applyPreset(presetName) {
            const presets = {
                cinematic_short: {style:'cinematic',qualityMode:'pro',aspectRatio:'21:9',frames:121,fps:24,cameraEnabled:true,cameraPreset:'dolly_in',cameraSpeed:0.3,colorGradingEnabled:true,cgContrast:0.15,cgSaturation:-0.05,cgTemperature:-0.1,fxVignette:true,fxFilmGrain:true,codec:'h264',crf:'20',encPreset:'slow',encTune:'film'},
                social_media_vertical: {style:'social_media',qualityMode:'standard',aspectRatio:'9:16',frames:49,fps:30,colorGradingEnabled:true,cgSaturation:0.2,fxSharpen:true,codec:'h264',crf:'21',encPreset:'fast'},
                anime_sequence: {style:'anime',qualityMode:'pro',aspectRatio:'16:9',frames:97,fps:24,guidanceScale:7,solver:'euler',upscaleEnabled:true,upscaleModel:'realesrgan_anime',upscaleScale:'2',colorGradingEnabled:true,cgSaturation:0.15,cgContrast:0.1,codec:'h264',crf:'20',encTune:'animation'},
                documentary_clip: {style:'documentary',qualityMode:'pro',aspectRatio:'16:9',frames:121,fps:24,cameraEnabled:true,cameraPreset:'handheld',cameraSpeed:0.2,colorGradingEnabled:true,cgTemperature:0.05,cgSaturation:-0.1,codec:'h264',crf:'19',encPreset:'slow',encTune:'film'},
                fast_preview: {qualityMode:'draft',aspectRatio:'16:9',frames:33,fps:12,upscaleEnabled:false,interpolateEnabled:false,colorGradingEnabled:false,codec:'h264',crf:'28',encPreset:'ultrafast'},
                music_video: {style:'music_video',qualityMode:'pro',aspectRatio:'16:9',frames:121,fps:30,cameraEnabled:true,cameraPreset:'tracking',cameraSpeed:0.7,colorGradingEnabled:true,cgSaturation:0.3,cgContrast:0.2,fxGlow:true,fxBloom:true,codec:'h264',crf:'20'},
                horror_atmosphere: {style:'horror',qualityMode:'pro',aspectRatio:'21:9',frames:97,fps:24,guidanceScale:6,cameraEnabled:true,cameraPreset:'handheld',cameraSpeed:0.15,colorGradingEnabled:true,cgSaturation:-0.4,cgContrast:0.3,cgTemperature:-0.2,fxVignette:true,fxFilmGrain:true,codec:'h264',crf:'22',encPreset:'slow',encTune:'film'},
            };
            const p = presets[presetName];
            if (!p) return;
            for (const [key, val] of Object.entries(p)) {
                const el = document.getElementById(key);
                if (!el) continue;
                if (el.type === 'checkbox') el.checked = val;
                else el.value = val;
                if (el.type === 'range') {
                    const valEl = document.getElementById(key + 'Value');
                    if (valEl) valEl.textContent = val;
                }
            }
            if (p.aspectRatio) applyAspectRatio();
            if (p.qualityMode) applyQualityMode();
            if (p.cameraPreset) applyCameraPreset();
            showToast('Preset applied: ' + presetName.replace(/_/g, ' '), 'success');
        }
        
        function _getVal(id) {
            const el = document.getElementById(id);
            return el ? el.value : null;
        }
        function _getInt(id, def) {
            const el = document.getElementById(id);
            if (!el) return def;
            const v = parseInt(el.value);
            return isNaN(v) ? def : v;
        }
        function _getFloat(id, def) {
            const el = document.getElementById(id);
            if (!el) return def;
            const v = parseFloat(el.value);
            return isNaN(v) ? def : v;
        }
        function _getBool(id, def) {
            const el = document.getElementById(id);
            return el ? el.checked : def;
        }
        
        async function generateVideo() {
            const prompt = document.getElementById('prompt').value.trim();
            if (!prompt) {
                showToast('Enter a description first', 'error');
                return;
            }
            
            const btn = document.getElementById('generateBtn');
            btn.disabled = true;
            btn.textContent = 'Generating...';
            
            const seedVal = document.getElementById('seed').value.trim();
            
            // Build color grading object
            const colorGrading = _getBool('colorGradingEnabled', false) ? {
                contrast: _getFloat('cgContrast', 0),
                saturation: _getFloat('cgSaturation', 0),
                temperature: _getFloat('cgTemperature', 0),
                brightness: _getFloat('cgBrightness', 0),
                hue: _getFloat('cgHue', 0),
                gamma: _getFloat('cgGamma', 0),
            } : null;
            
            // Build effects object
            const effects = {
                vignette_enabled: _getBool('fxVignette', false),
                vignette_intensity: _getFloat('fxVignetteIntensity', 0.3),
                film_grain_enabled: _getBool('fxFilmGrain', false),
                film_grain_amount: _getFloat('fxFilmGrainAmount', 0.15),
                sharpen_enabled: _getBool('fxSharpen', false),
                sharpen_amount: _getFloat('fxSharpenAmount', 0.5),
                glow_enabled: _getBool('fxGlow', false),
                bloom_enabled: _getBool('fxBloom', false),
            };
            
            // Camera direction from preset
            const camPreset = _getVal('cameraPreset') || 'static';
            const camDirection = camPreset.includes('left') ? 'left' : camPreset.includes('right') ? 'right' :
                camPreset.includes('up') ? 'up' : camPreset.includes('down') ? 'down' :
                camPreset.includes('in') ? 'in' : camPreset.includes('out') ? 'out' : null;
            const camMotion = camPreset.replace(/_(left|right|up|down|in|out)$/, '');
            
            const payload = {
                prompt,
                model: _getVal('model') || 'auto',
                style: _getVal('style') || 'cinematic',
                num_frames: _getInt('frames', 97),
                fps: _getInt('fps', 24),
                steps: _getInt('steps', 30),
                seed: seedVal ? parseInt(seedVal) : null,
                enhance: _getBool('enhancePrompt', true),
                // Advanced
                negative_prompt: document.getElementById('negativePrompt')?.value || null,
                width: _getInt('resWidth', null),
                height: _getInt('resHeight', null),
                guidance_scale: _getFloat('guidanceScale', 5.0),
                guidance_rescale: _getFloat('guidanceRescale', 0.0),
                creativity_scale: _getFloat('creativityScale', 0.5),
                // Scheduler
                solver: _getVal('solver') || 'unipc',
                flow_shift: _getFloat('flowShift', 5.0),
                use_karras_sigmas: _getBool('useKarras', false),
                use_dynamic_shifting: _getBool('useDynamicShifting', false),
                decode_timestep: _getFloat('decodeTimestep', 0.05),
                decode_noise_scale: _getFloat('decodeNoiseScale', 0.025),
                // Camera
                camera_enabled: _getBool('cameraEnabled', false),
                camera_motion: camMotion,
                camera_direction: camDirection,
                camera_speed: _getFloat('cameraSpeed', 0.5),
                camera_intensity: _getFloat('cameraIntensity', 0.5),
                camera_fov: _getFloat('cameraFov', 60),
                // Motion
                motion_intensity: _getFloat('motionIntensity', 0.5),
                temporal_smoothing: _getBool('temporalSmoothing', true),
                flicker_elimination: _getBool('flickerElimination', true),
                // Post-processing
                upscale: _getBool('upscaleEnabled', false) ? _getInt('upscaleScale', 2) : 1,
                upscale_model: _getVal('upscaleModel') || 'realesrgan_x2',
                interpolate_fps: _getBool('interpolateEnabled', false) ? _getInt('interpolateFps', 0) : 0,
                interpolate_motion_blur: _getBool('interpolateMotionBlur', false),
                color_grading: colorGrading,
                effects: effects,
                // Output
                codec: _getVal('codec') || 'h264',
                crf: _getInt('crf', 23),
                preset: _getVal('encPreset') || 'medium',
                tune: _getVal('encTune') || 'none',
                bitrate_preset: _getVal('bitratePreset') || 'auto',
                profile: _getVal('encProfile') || 'high',
                pixel_format: _getVal('pixelFormat') || 'yuv420p',
                // Audio
                audio: _getBool('audioEnabled', false),
                native_audio: _getBool('nativeAudio', false),
                tts_text: _getBool('ttsEnabled', false) ? (document.getElementById('ttsText')?.value || null) : null,
                tts_voice: _getVal('ttsVoice') || 'narrator_male',
                ambient_prompt: _getBool('ambientEnabled', false) ? (document.getElementById('ambientPrompt')?.value || null) : null,
                music_prompt: _getBool('musicEnabled', false) ? (document.getElementById('musicPrompt')?.value || null) : null,
            };

            const resp = await fetch('/api/generate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            }).then(r => r.json());
            
            if (resp.error) {
                showToast(resp.error, 'error');
                btn.disabled = false;
                btn.textContent = 'Generate Video';
                return;
            }
            
            currentJobId = resp.job_id;
            document.getElementById('progressBar').classList.add('active');
            document.getElementById('progressText').textContent = 'Processing...';
            
            // Poll for status
            pollInterval = setInterval(pollStatus, 3000);
        }

        function applyBitratePreset() {
            const preset = document.getElementById('bitratePreset').value;
            const presets = {
                'auto': { crf: '23', disableCrf: false },
                'low_720': { crf: null, disableCrf: true },
                'medium_1080': { crf: null, disableCrf: true },
                'high_1080': { crf: null, disableCrf: true },
                'ultra_4k': { crf: null, disableCrf: true },
                'streaming': { crf: null, disableCrf: true },
                'cinema': { crf: null, disableCrf: true },
                'archive': { crf: null, disableCrf: true },
            };
            const p = presets[preset] || presets['auto'];
            const crfSelect = document.getElementById('crf');
            if (p.disableCrf) {
                crfSelect.disabled = true;
                crfSelect.style.opacity = '0.4';
            } else {
                crfSelect.disabled = false;
                crfSelect.style.opacity = '1';
            }
            if (p.crf) crfSelect.value = p.crf;
            showToast(`Bitrate preset: ${preset}`, 'success');
        }

        async function pollStatus() {
            if (!currentJobId) return;
            
            const status = await fetch(`/api/status/${currentJobId}`).then(r => r.json());
            
            if (status.status === 'complete') {
                clearInterval(pollInterval);
                document.getElementById('progressFill').style.width = '100%';
                document.getElementById('progressText').textContent = 'Done!';
                showToast('Video generated successfully!', 'success');
                
                setTimeout(() => {
                    document.getElementById('progressBar').classList.remove('active');
                    document.getElementById('progressFill').style.width = '0%';
                    document.getElementById('progressText').textContent = '';
                    document.getElementById('generateBtn').disabled = false;
                    document.getElementById('generateBtn').textContent = 'Generate Video';
                    loadVideos();
                }, 1500);
                
                currentJobId = null;
            } else if (status.status === 'failed') {
                clearInterval(pollInterval);
                showToast('Generation failed: ' + (status.error || 'Unknown error'), 'error');
                document.getElementById('progressBar').classList.remove('active');
                document.getElementById('progressText').textContent = '';
                document.getElementById('generateBtn').disabled = false;
                document.getElementById('generateBtn').textContent = 'Generate Video';
                currentJobId = null;
            } else {
                document.getElementById('progressText').textContent = 'Generating on GPU...';
            }
        }
        
        async function loadVideos() {
            const data = await fetch('/api/videos').then(r => r.json());
            const grid = document.getElementById('videoGrid');
            
            if (!data.videos || data.videos.length === 0) {
                grid.innerHTML = '<div class="empty-state"><div class="icon">&#127916;</div><p>No videos yet. Create your first one above!</p></div>';
                return;
            }
            
            grid.innerHTML = data.videos.map(v => `
                <div class="video-card">
                    <video controls preload="metadata" src="/api/download/${v.name.replace('soulillusions_', '').replace('.mp4', '')}"></video>
                    <div class="video-info">
                        <div class="name">${v.name}</div>
                        <div class="meta">
                            <span>${v.size_mb}</span>
                            <span>${new Date(v.created * 1000).toLocaleDateString()}</span>
                        </div>
                        <div class="video-actions">
                            <a class="btn btn-secondary btn-sm" href="/api/download/${v.name.replace('soulillusions_', '').replace('.mp4', '')}" download>Download</a>
                        </div>
                    </div>
                </div>
            `).join('');
        }
        
        function showToast(msg, type) {
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.className = `toast ${type} show`;
            setTimeout(() => toast.classList.remove('show'), 3000);
        }
        
        // === Tab System ===
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            const btn = document.querySelector('.tab[onclick*="' + tab + '"]');
            if (btn) btn.classList.add('active');
            const content = document.getElementById('tab-' + tab);
            if (content) content.classList.add('active');
            if (tab === 'production') loadSeriesList();
        }
        
        // === Production Suite ===
        let prodState = { series: null, season: null, episode: null, scene: null };
        let genPollInterval = null;
        
        async function prodFetch(path, opts = {}) {
            const resp = await fetch('/api/production' + path, opts);
            return resp.json();
        }
        
        async function prodPost(path, body) {
            return prodFetch(path, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
        }
        
        async function prodPut(path, body) {
            return prodFetch(path, {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
        }
        
        // Series List View
        async function loadSeriesList() {
            const data = await prodFetch('/series');
            const view = document.getElementById('prodView');
            const series = data.series || [];
            
            view.innerHTML = `
                <div class="prod-card">
                    <h2>&#127916; Production Suite</h2>
                    <p style="color:var(--muted);margin-bottom:20px;">Manage series, seasons, episodes, and scenes for long-form AI video production.</p>
                    
                    <h3>Create New Series</h3>
                    <div class="prod-grid">
                        <div>
                            <label class="prod-label">Series Title</label>
                            <input class="prod-input" id="newSeriesTitle" placeholder="In Time Television" />
                        </div>
                        <div>
                            <label class="prod-label">Genre</label>
                            <select class="prod-select" id="newSeriesGenre">
                                <option value="sci-fi">Sci-Fi</option>
                                <option value="drama">Drama</option>
                                <option value="action">Action</option>
                                <option value="thriller">Thriller</option>
                                <option value="fantasy">Fantasy</option>
                            </select>
                        </div>
                    </div>
                    <label class="prod-label">Concept / Logline</label>
                    <input class="prod-input" id="newSeriesConcept" placeholder="In a future where time is currency, the rich live forever and the poor fight for every second..." />
                    <label class="prod-label">Description</label>
                    <textarea class="prod-textarea" id="newSeriesDesc" placeholder="Detailed series description..."></textarea>
                    <div class="prod-grid" style="margin-top:10px;">
                        <div>
                            <label class="prod-label">Seasons Planned</label>
                            <input class="prod-input" id="newSeriesSeasons" type="number" value="8" />
                        </div>
                        <div>
                            <label class="prod-label">Episodes per Season</label>
                            <input class="prod-input" id="newSeriesEpisodes" type="number" value="16" />
                        </div>
                    </div>
                    <div class="prod-btn-row">
                        <button class="prod-btn" onclick="createSeries()">Create Series</button>
                    </div>
                </div>
                
                <div class="prod-card">
                    <h3>Your Series</h3>
                    ${series.length === 0 ? '<p style="color:var(--muted);">No series yet. Create one above to get started.</p>' : 
                    series.map(s => `
                        <div class="series-card" onclick="openSeries('${s.id}')">
                            <h4>${s.title}</h4>
                            <p>${s.description || 'No description'}</p>
                            <div class="meta">
                                <span>&#128269; ${s.genre}</span>
                                <span>&#128193; ${s.seasons_completed}/${s.seasons_planned} seasons</span>
                                <span>&#127916; ${s.episodes_completed} episodes</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }
        
        async function createSeries() {
            const title = document.getElementById('newSeriesTitle').value.trim();
            if (!title) { showToast('Enter a title', 'error'); return; }
            
            const resp = await prodPost('/series/create', {
                title: title,
                concept: document.getElementById('newSeriesConcept').value.trim(),
                description: document.getElementById('newSeriesDesc').value.trim(),
                genre: document.getElementById('newSeriesGenre').value,
                seasons_planned: parseInt(document.getElementById('newSeriesSeasons').value) || 8,
                episodes_per_season: parseInt(document.getElementById('newSeriesEpisodes').value) || 16,
            });
            
            if (resp.status === 'created') {
                showToast('Series created!', 'success');
                loadSeriesList();
            } else {
                showToast(resp.error || 'Failed to create', 'error');
            }
        }
        
        // Series Detail View
        async function openSeries(id) {
            prodState.series = id;
            const data = await prodFetch('/series/' + id);
            const view = document.getElementById('prodView');
            const seasons = data.seasons || {};
            
            let seasonsHtml = '';
            for (let s = 1; s <= data.seasons_planned; s++) {
                const season = seasons[String(s)];
                const epCount = season ? Object.keys(season.episodes || {}).length : 0;
                const status = season ? season.status : 'not started';
                seasonsHtml += `
                    <div class="episode-card" onclick="openSeason(${s})">
                        <div>
                            <span class="ep-num">Season ${s}</span>
                            <div class="ep-title">${epCount} / ${data.episodes_per_season} episodes</div>
                        </div>
                        <span class="ep-status draft">${status}</span>
                    </div>
                `;
            }
            
            // Characters
            const chars = data.characters || {};
            let charsHtml = Object.keys(chars).length > 0 ?
                Object.values(chars).map(c => `
                    <div class="char-item">
                        <strong>${c.name}</strong> - ${c.appearance || 'No appearance set'}<br>
                        <span style="color:var(--muted);">${c.personality || ''}</span>
                    </div>
                `).join('') : '<p style="color:var(--muted);">No characters defined yet.</p>';
            
            view.innerHTML = `
                <div class="breadcrumb">
                    <a onclick="loadSeriesList()">All Series</a>
                    <span class="sep">/</span>
                    <span>${data.title}</span>
                </div>
                
                <div class="prod-card">
                    <h2>${data.title}</h2>
                    <p style="color:var(--muted);margin-bottom:16px;">${data.description || ''}</p>
                    ${data.concept ? `<div class="info-banner"><strong>Concept:</strong> ${data.concept}</div>` : ''}
                    
                    <div class="prod-grid">
                        <div>
                            <h3>World Bible</h3>
                            <textarea class="prod-textarea" id="worldBible" placeholder="Define the world, rules, setting, history...">${data.world_bible || ''}</textarea>
                            <button class="prod-btn secondary" onclick="saveWorldBible()">Save World Bible</button>
                        </div>
                        <div>
                            <h3>Characters</h3>
                            <div class="char-list" style="margin-bottom:12px;">${charsHtml}</div>
                            <label class="prod-label">Add Character</label>
                            <input class="prod-input" id="charName" placeholder="Character name" />
                            <input class="prod-input" id="charAppearance" placeholder="Appearance description" />
                            <input class="prod-input" id="charPersonality" placeholder="Personality traits" />
                            <button class="prod-btn secondary" onclick="addCharacter()">Add Character</button>
                        </div>
                    </div>
                </div>
                
                <div class="prod-card">
                    <h3>Seasons</h3>
                    ${seasonsHtml}
                </div>
            `;
        }
        
        async function saveWorldBible() {
            const text = document.getElementById('worldBible').value;
            const resp = await prodPut('/series/' + prodState.series, { world_bible: text });
            if (resp.status === 'updated') showToast('World bible saved', 'success');
        }
        
        async function addCharacter() {
            const name = document.getElementById('charName').value.trim();
            if (!name) { showToast('Enter a name', 'error'); return; }
            const resp = await prodPost('/series/' + prodState.series + '/characters', {
                name: name,
                appearance: document.getElementById('charAppearance').value.trim(),
                personality: document.getElementById('charPersonality').value.trim(),
            });
            if (resp.status === 'added') {
                showToast('Character added', 'success');
                openSeries(prodState.series);
            }
        }
        
        // Season View
        async function openSeason(seasonNum) {
            prodState.season = seasonNum;
            const data = await prodFetch('/series/' + prodState.series);
            const view = document.getElementById('prodView');
            const season = (data.seasons || {})[String(seasonNum)] || { episodes: {} };
            const episodes = season.episodes || {};
            
            let epsHtml = '';
            for (let e = 1; e <= data.episodes_per_season; e++) {
                const ep = episodes[String(e)];
                const status = ep ? ep.status : 'not created';
                const title = ep ? ep.title : `Episode ${e}`;
                epsHtml += `
                    <div class="episode-card" onclick="openEpisode(${e})">
                        <div>
                            <span class="ep-num">S${seasonNum}E${e}</span>
                            <div class="ep-title">${title}</div>
                        </div>
                        <span class="ep-status ${status}">${status}</span>
                    </div>
                `;
            }
            
            view.innerHTML = `
                <div class="breadcrumb">
                    <a onclick="loadSeriesList()">All Series</a>
                    <span class="sep">/</span>
                    <a onclick="openSeries('${prodState.series}')">${data.title}</a>
                    <span class="sep">/</span>
                    <span>Season ${seasonNum}</span>
                </div>
                
                <div class="prod-card">
                    <h2>Season ${seasonNum}</h2>
                    <div class="prod-btn-row" style="margin-bottom:20px;">
                        <button class="prod-btn" onclick="showCreateEpisode()">+ Create Episode</button>
                        <button class="prod-btn secondary" onclick="reviewSeason()">Review Season</button>
                    </div>
                    <div id="createEpForm" style="display:none;margin-bottom:20px;">
                        <h3>New Episode</h3>
                        <label class="prod-label">Episode Number</label>
                        <input class="prod-input" id="newEpNum" type="number" value="1" min="1" />
                        <label class="prod-label">Title</label>
                        <input class="prod-input" id="newEpTitle" placeholder="Episode title" />
                        <label class="prod-label">Synopsis</label>
                        <textarea class="prod-textarea" id="newEpSynopsis" placeholder="Brief synopsis..."></textarea>
                        <button class="prod-btn" onclick="createEpisode()">Create</button>
                    </div>
                    ${epsHtml}
                </div>
            `;
        }
        
        function showCreateEpisode() {
            const form = document.getElementById('createEpForm');
            form.style.display = form.style.display === 'none' ? 'block' : 'none';
        }
        
        async function createEpisode() {
            const epNum = parseInt(document.getElementById('newEpNum').value);
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${epNum}`, {
                title: document.getElementById('newEpTitle').value.trim(),
                synopsis: document.getElementById('newEpSynopsis').value.trim(),
            });
            if (resp.status === 'created') {
                showToast('Episode created', 'success');
                openEpisode(epNum);
            } else {
                showToast(resp.error || 'Failed', 'error');
            }
        }
        
        // Episode View (Script + Breakdown + Timeline)
        async function openEpisode(epNum) {
            prodState.episode = epNum;
            const data = await prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${epNum}`);
            if (data.error) { showToast(data.error, 'error'); return; }
            
            const view = document.getElementById('prodView');
            const hasScript = (data.script_raw || '').length > 0;
            const hasEnhanced = (data.script_enhanced || '').length > 0;
            const hasScenes = data.scene_count > 0;
            
            view.innerHTML = `
                <div class="breadcrumb">
                    <a onclick="loadSeriesList()">All Series</a>
                    <span class="sep">/</span>
                    <a onclick="openSeries('${prodState.series}')">Series</a>
                    <span class="sep">/</span>
                    <a onclick="openSeason(${prodState.season})">Season ${prodState.season}</a>
                    <span class="sep">/</span>
                    <span>${data.title}</span>
                </div>
                
                <div class="prod-card">
                    <h2>${data.title}</h2>
                    <p style="color:var(--muted);margin-bottom:16px;">${data.synopsis || ''}</p>
                    <div class="meta" style="display:flex;gap:20px;font-size:13px;color:var(--muted);margin-bottom:20px;">
                        <span>Status: <strong style="color:var(--text)">${data.status}</strong></span>
                        <span>Scenes: <strong style="color:var(--text)">${data.scene_count || 0}</strong></span>
                        <span>Generated: <strong style="color:var(--text)">${data.generated_scenes || 0}</strong></span>
                        <span>Target: <strong style="color:var(--text)">${Math.floor(data.target_duration/60)}min</strong></span>
                    </div>
                    
                    <h3>&#128221; Script</h3>
                    ${!hasScript ? `
                        <div class="info-banner">Upload or paste a script to get started. You can paste a rough draft and the system will enhance it.</div>
                    ` : ''}
                    <label class="prod-label">Script ${hasScript ? `(${data.script_raw.split(/\\s+/).length} words)` : ''}</label>
                    <textarea class="prod-textarea large" id="scriptText" placeholder="Paste your episode script here...">${data.script_raw || ''}</textarea>
                    <div class="prod-btn-row">
                        <button class="prod-btn" onclick="uploadScript()">Save Script</button>
                        ${hasScript ? `
                            <button class="prod-btn secondary" onclick="enhanceScript()">Enhance Script</button>
                            <select class="prod-select" id="enhanceLevel" style="width:auto;margin-bottom:0;">
                                <option value="basic">Basic</option>
                                <option value="detailed" selected>Detailed</option>
                                <option value="cinematic">Cinematic</option>
                                <option value="book-level">Book-Level</option>
                            </select>
                        ` : ''}
                    </div>
                    
                    ${hasEnhanced ? `
                        <div style="margin-top:16px;">
                            <label class="prod-label">Enhanced Script (${data.script_enhanced.split(/\\s+/).length} words)</label>
                            <textarea class="prod-textarea large" id="enhancedScript">${data.script_enhanced}</textarea>
                        </div>
                    ` : ''}
                </div>
                
                ${hasScript ? `
                <div class="prod-card">
                    <h3>&#127917; Scene Breakdown</h3>
                    <p style="color:var(--muted);margin-bottom:16px;">Break the script into individual scenes for generation.</p>
                    <div class="prod-grid">
                        <div>
                            <label class="prod-label">Scene Duration (seconds)</label>
                            <input class="prod-input" id="sceneDuration" type="number" value="5" min="2" max="18" />
                        </div>
                        <div>
                            <label class="prod-label">Model</label>
                            <select class="prod-select" id="breakdownModel">
                                <option value="ltx">LTX-Video (Fast)</option>
                                <option value="wan">Wan 2.1 1.3B (Best Motion)</option>
                                <option value="cogvideox">CogVideoX-2B (Balanced)</option>
                            </select>
                        </div>
                        <div>
                            <label class="prod-label">Style</label>
                            <select class="prod-select" id="breakdownStyle">
                                <option value="cinematic">Cinematic</option>
                                <option value="realistic">Realistic</option>
                                <option value="anime">Anime</option>
                            </select>
                        </div>
                        <div>
                            <label class="prod-label">Frames per scene</label>
                            <input class="prod-input" id="breakdownFrames" type="number" value="97" />
                        </div>
                    </div>
                    <div class="prod-btn-row">
                        <button class="prod-btn" onclick="breakdownEpisode()">Break Down into Scenes</button>
                        ${hasScenes ? '<button class="prod-btn secondary" onclick="loadTimeline()">View Timeline</button>' : ''}
                    </div>
                </div>
                ` : ''}
                
                <div id="timelineSection"></div>
                <div id="sceneEditorSection"></div>
                <div id="genProgressSection"></div>
                <div id="memorySection"></div>
            `;
            
            if (hasScenes) loadTimeline();
            loadMemoryPanel();
        }
        
        async function uploadScript() {
            const text = document.getElementById('scriptText').value.trim();
            if (!text) { showToast('Script is empty', 'error'); return; }
            
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/script/upload`, {
                script_text: text
            });
            if (resp.status === 'uploaded') {
                showToast(`Script saved (${resp.word_count} words)`, 'success');
                openEpisode(prodState.episode);
            }
        }
        
        async function enhanceScript() {
            const level = document.getElementById('enhanceLevel').value;
            showToast('Enhancing script...', 'success');
            
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/script/enhance`, {
                enhancement_level: level
            });
            if (resp.status === 'enhanced') {
                showToast(`Enhanced ${resp.expansion_ratio} expansion`, 'success');
                openEpisode(prodState.episode);
            } else {
                showToast(resp.error || 'Failed', 'error');
            }
        }
        
        async function breakdownEpisode() {
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/breakdown`, {
                scene_duration: parseInt(document.getElementById('sceneDuration').value) || 5,
                model: document.getElementById('breakdownModel').value,
                style: document.getElementById('breakdownStyle').value,
                num_frames: parseInt(document.getElementById('breakdownFrames').value) || 97,
            });
            if (resp.status === 'broken_down') {
                showToast(`${resp.scene_count} scenes created`, 'success');
                loadTimeline();
            } else {
                showToast(resp.error || 'Failed', 'error');
            }
        }
        
        // Timeline View
        async function loadTimeline() {
            const data = await prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes`);
            const section = document.getElementById('timelineSection');
            const scenes = data.scenes || [];
            
            if (scenes.length === 0) { section.innerHTML = ''; return; }
            
            const completed = scenes.filter(s => s.status === 'complete').length;
            const failed = scenes.filter(s => s.status === 'failed').length;
            const generating = scenes.filter(s => s.status === 'generating').length;
            
            section.innerHTML = `
                <div class="prod-card">
                    <h3>&#128197; Timeline (${scenes.length} scenes)</h3>
                    <div class="gen-stats" style="margin-bottom:12px;">
                        <span style="color:var(--success)">&#9989; ${completed} complete</span>
                        <span style="color:var(--warning)">&#9203; ${generating} generating</span>
                        <span style="color:var(--error)">&#10060; ${failed} failed</span>
                        <span style="color:var(--muted)">&#9201; ~${Math.floor(scenes.length * (scenes[0]?.duration || 5) / 60)}min total</span>
                    </div>
                    <div class="timeline">
                        ${scenes.map(s => `
                            <div class="timeline-scene ${s.status}" onclick="openScene(${s.scene_number})" title="Scene ${s.scene_number}: ${s.prompt.substring(0,80)}...">
                                ${s.scene_number}
                            </div>
                        `).join('')}
                    </div>
                    <div class="prod-btn-row">
                        <button class="prod-btn" onclick="generateAll()">Generate All Scenes</button>
                        <button class="prod-btn secondary" onclick="assembleEpisode()">Assemble Episode</button>
                        <button class="prod-btn secondary" onclick="uploadToSoulTube()">Upload to SoulTube</button>
                    </div>
                </div>
            `;
        }
        
        // Scene Editor
        async function openScene(sceneNum) {
            prodState.scene = sceneNum;
            const data = await prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${sceneNum}`);
            if (data.error) { showToast(data.error, 'error'); return; }
            
            // Also load scene memory and assessment
            const [sceneMem, assessment, adjustments] = await Promise.all([
                prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${sceneNum}/memory`).catch(() => null),
                prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${sceneNum}/assessment`).catch(() => null),
                prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${sceneNum}/adjustments`).catch(() => null),
            ]);
            
            const section = document.getElementById('sceneEditorSection');
            const hasVideo = data.status === 'complete' && data.video_path;
            const videoUrl = `/api/production/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${sceneNum}/video`;
            
            // Build memory tags
            let memTagsHtml = '';
            if (sceneMem && !sceneMem.error) {
                if (sceneMem.characters_on_screen && sceneMem.characters_on_screen.length > 0) {
                    memTagsHtml += sceneMem.characters_on_screen.map(c => `<span class="scene-memory-tag char">&#128100; ${c}</span>`).join('');
                }
                if (sceneMem.location && sceneMem.location !== 'unknown') {
                    memTagsHtml += `<span class="scene-memory-tag loc">&#128205; ${sceneMem.location}</span>`;
                }
                if (sceneMem.emotional_tone && sceneMem.emotional_tone !== 'neutral') {
                    memTagsHtml += `<span class="scene-memory-tag tone">&#127917; ${sceneMem.emotional_tone}</span>`;
                }
                if (sceneMem.timeline_id && sceneMem.timeline_id !== 'main') {
                    memTagsHtml += `<span class="scene-memory-tag timeline">&#128260; ${sceneMem.timeline_id}</span>`;
                }
                if (sceneMem.urgency_score !== undefined) {
                    const urg = sceneMem.urgency_score;
                    const urgClass = urg > 0.7 ? 'high' : urg > 0.4 ? 'mid' : 'low';
                    memTagsHtml += `<span class="scene-memory-tag urgency">&#9889; ${(urg*100).toFixed(0)}%</span>`;
                }
            }
            
            // Build assessment HTML
            let assessHtml = '';
            if (assessment && !assessment.error) {
                const score = assessment.overall_score || 0;
                const scoreClass = score > 0.7 ? 'good' : score > 0.4 ? 'mid' : 'low';
                assessHtml = `
                    <div class="learning-card">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                            <strong>&#128269; Quality Assessment</strong>
                            <span class="learning-score ${scoreClass}">${(score*100).toFixed(0)}%</span>
                        </div>
                        ${assessment.issues && assessment.issues.length > 0 ? 
                            `<div style="color:var(--error);margin-bottom:4px;">${assessment.issues.map(i => `&#9888; ${i}`).join('<br>')}</div>` : ''}
                        ${assessment.adjustments && assessment.adjustments.length > 0 ?
                            `<div style="color:var(--warning);">${assessment.adjustments.slice(0,3).map(a => `&#128161; ${a}`).join('<br>')}</div>` : ''}
                    </div>
                `;
            }
            
            // Build adjustments HTML
            let adjHtml = '';
            if (adjustments && adjustments.adjustments && adjustments.adjustments.length > 0) {
                adjHtml = `
                    <div class="memory-item" style="margin-top:10px;">
                        <div class="label">Learnings Applied (${adjustments.count})</div>
                        <div style="margin-top:4px;">${adjustments.adjustments.map(a => `<div style="margin-bottom:2px;">&#128161; ${a}</div>`).join('')}</div>
                    </div>
                `;
            }
            
            section.innerHTML = `
                <div class="prod-card">
                    <h3>Scene ${sceneNum} ${data.retake_count > 0 ? `(Retake #${data.retake_count})` : ''}</h3>
                    ${memTagsHtml ? `<div style="margin-bottom:12px;">${memTagsHtml}</div>` : ''}
                    <div class="scene-editor">
                        <div class="scene-preview">
                            <h4>Preview</h4>
                            ${hasVideo ? `<video src="${videoUrl}" controls></video>` : '<p style="color:var(--muted);padding:20px 0;">No video generated yet.</p>'}
                            <div class="scene-info">
                                <strong>Status:</strong> ${data.status}<br>
                                <strong>Duration:</strong> ${data.duration}s<br>
                                <strong>Model:</strong> ${data.model}<br>
                                <strong>Retakes:</strong> ${data.retake_count || 0}<br>
                                ${data.error ? `<strong style="color:var(--error)">Error:</strong> ${data.error}` : ''}
                            </div>
                            ${assessHtml}
                            <div class="prod-btn-row">
                                <button class="prod-btn" onclick="retakeScene()">Retake Scene</button>
                                ${hasVideo ? '<button class="prod-btn secondary" onclick="closeScene()">Close</button>' : ''}
                            </div>
                        </div>
                        <div>
                            <h4>Edit Prompt</h4>
                            <label class="prod-label">Generation Prompt</label>
                            <textarea class="prod-textarea" id="scenePrompt">${data.prompt}</textarea>
                            <label class="prod-label">Seed (optional)</label>
                            <input class="prod-input" id="sceneSeed" type="number" value="${data.seed || ''}" placeholder="Random" />
                            <div class="prod-grid" style="margin-top:10px;">
                                <div>
                                    <label class="prod-label">Model</label>
                                    <select class="prod-select" id="sceneModel">
                                        <option value="ltx" ${data.model==='ltx'?'selected':''}>LTX-Video</option>
                                        <option value="wan" ${data.model==='wan'?'selected':''}>Wan 2.1</option>
                                        <option value="cogvideox" ${data.model==='cogvideox'?'selected':''}>CogVideoX-2B</option>
                                    </select>
                                </div>
                                <div>
                                    <label class="prod-label">Transition</label>
                                    <select class="prod-select" id="sceneTransition">
                                        <option value="cut" ${data.transition==='cut'?'selected':''}>Cut</option>
                                        <option value="fade" ${data.transition==='fade'?'selected':''}>Fade</option>
                                        <option value="dissolve" ${data.transition==='dissolve'?'selected':''}>Dissolve</option>
                                        <option value="wipe" ${data.transition==='wipe'?'selected':''}>Wipe</option>
                                    </select>
                                </div>
                            </div>
                            <div class="prod-btn-row">
                                <button class="prod-btn secondary" onclick="saveScene(${sceneNum})">Save Changes</button>
                                <button class="prod-btn secondary" onclick="assessScene(${sceneNum})">Assess Quality</button>
                            </div>
                            ${adjHtml}
                        </div>
                    </div>
                </div>
            `;
        }
        
        function closeScene() {
            document.getElementById('sceneEditorSection').innerHTML = '';
            prodState.scene = null;
        }
        
        async function saveScene(sceneNum) {
            const resp = await prodPut(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${sceneNum}`, {
                prompt: document.getElementById('scenePrompt').value,
                seed: parseInt(document.getElementById('sceneSeed').value) || null,
                model: document.getElementById('sceneModel').value,
                transition: document.getElementById('sceneTransition').value,
            });
            if (resp.status === 'updated') showToast('Scene saved', 'success');
        }
        
        async function retakeScene() {
            const prompt = document.getElementById('scenePrompt').value;
            const seed = parseInt(document.getElementById('sceneSeed').value) || null;
            
            showToast('Starting retake...', 'success');
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${prodState.scene}/retake`, {
                prompt_override: prompt,
                seed: seed,
            });
            if (resp.status === 'retake_started') {
                showToast(`Retake #${resp.retake_count} started`, 'success');
                pollGeneration();
            }
        }
        
        async function generateAll() {
            if (!confirm('Generate all pending scenes? This will take a while.')) return;
            
            showToast('Starting batch generation...', 'success');
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/generate`, {});
            if (resp.status === 'started') {
                showToast(`Generating ${resp.total_scenes} scenes...`, 'success');
                pollGeneration();
            } else if (resp.status === 'no_work') {
                showToast('All scenes already generated', 'success');
            } else {
                showToast(resp.error || 'Failed to start', 'error');
            }
        }
        
        function pollGeneration() {
            if (genPollInterval) clearInterval(genPollInterval);
            genPollInterval = setInterval(async () => {
                const data = await prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/generate/status`);
                
                const section = document.getElementById('genProgressSection');
                if (!section) return;
                
                if (data.status === 'idle' || data.status === 'complete') {
                    if (data.status === 'complete') {
                        section.innerHTML = `
                            <div class="gen-progress">
                                <h3>Generation Complete</h3>
                                <div class="gen-stats">
                                    <span style="color:var(--success)">&#9989; ${data.completed} completed</span>
                                    <span style="color:var(--error)">&#10060; ${data.failed} failed</span>
                                </div>
                            </div>
                        `;
                        loadTimeline();
                        clearInterval(genPollInterval);
                        genPollInterval = null;
                    }
                    return;
                }
                
                const pct = data.total_scenes > 0 ? (data.completed / data.total_scenes) * 100 : 0;
                section.innerHTML = `
                    <div class="gen-progress">
                        <h3>Generating... Scene ${data.current_scene} of ${data.total_scenes}</h3>
                        <div class="gen-progress-bar">
                            <div class="gen-progress-fill" style="width:${pct}%"></div>
                        </div>
                        <div class="gen-stats">
                            <span style="color:var(--success)">&#9989; ${data.completed} done</span>
                            <span style="color:var(--error)">&#10060; ${data.failed} failed</span>
                            <span style="color:var(--muted)">${Math.round(pct)}%</span>
                        </div>
                        ${data.errors.length > 0 ? `<div style="margin-top:8px;font-size:12px;color:var(--error);">${data.errors.slice(-3).join('<br>')}</div>` : ''}
                    </div>
                `;
                loadTimeline();
            }, 5000);
        }
        
        async function assembleEpisode() {
            showToast('Assembling episode...', 'success');
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/assemble`, {});
            if (resp.status === 'assembled') {
                showToast(`Assembled ${resp.scenes_assembled} scenes (${resp.file_size_mb})`, 'success');
            } else {
                showToast(resp.error || 'Assembly failed', 'error');
            }
        }
        
        async function uploadToSoulTube() {
            const url = prompt('SoulTube API URL:', 'https://your-soulmate-url.com');
            if (!url) return;
            
            showToast('Uploading to SoulTube...', 'success');
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/upload`, {
                soultube_api_url: url,
            });
            if (resp.status === 'uploaded') {
                showToast(`Uploaded! SoulTube ID: ${resp.soultube_id}`, 'success');
            } else {
                showToast(resp.error || 'Upload failed', 'error');
            }
        }
        
        async function reviewSeason() {
            showToast('Reviewing season...', 'success');
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/review`, {
                review_scope: 'season',
                review_depth: 'thorough'
            });
            if (resp.review_notes) {
                const notes = resp.review_notes;
                const view = document.getElementById('prodView');
                view.innerHTML = `
                    <div class="breadcrumb">
                        <a onclick="loadSeriesList()">All Series</a>
                        <span class="sep">/</span>
                        <a onclick="openSeries('${prodState.series}')">Series</a>
                        <span class="sep">/</span>
                        <a onclick="openSeason(${prodState.season})">Season ${prodState.season}</a>
                        <span class="sep">/</span>
                        <span>Review</span>
                    </div>
                    <div class="prod-card">
                        <h2>&#128269; Season ${prodState.season} Review</h2>
                        <div class="info-banner">${notes.overall_assessment}</div>
                        
                        <h3>Strengths</h3>
                        ${notes.strengths.map(s => `<div style="color:var(--success);margin-bottom:4px;">&#9989; ${s}</div>`).join('') || '<p style="color:var(--muted)">None identified</p>'}
                        
                        <h3 style="margin-top:16px;">Weaknesses</h3>
                        ${notes.weaknesses.map(w => `<div style="color:var(--error);margin-bottom:4px;">&#10060; ${w}</div>`).join('') || '<p style="color:var(--muted)">None identified</p>'}
                        
                        <h3 style="margin-top:16px;">Suggestions for Next Season</h3>
                        ${notes.suggestions.map(s => `<div style="margin-bottom:4px;">&#128161; ${s}</div>`).join('')}
                        
                        ${notes.pacing_notes.length > 0 ? `
                        <h3 style="margin-top:16px;">Pacing Notes</h3>
                        ${notes.pacing_notes.map(p => `<div style="margin-bottom:4px;color:var(--warning);">&#9203; ${p}</div>`).join('')}
                        ` : ''}
                        
                        <div class="prod-btn-row" style="margin-top:20px;">
                            <button class="prod-btn secondary" onclick="openSeason(${prodState.season})">Back to Season</button>
                        </div>
                    </div>
                `;
            }
        }
        
        // === Narrative Memory UI ===
        
        async function loadMemoryPanel() {
            const section = document.getElementById('memorySection');
            if (!section) return;
            
            // Check memory engine status
            const status = await prodFetch('/memory/status').catch(() => ({enabled: false}));
            if (!status.enabled) {
                section.innerHTML = `
                    <div class="memory-panel">
                        <h4>&#129504; Narrative Memory Engine</h4>
                        <span class="memory-badge off">DISABLED</span>
                        <p style="color:var(--muted);font-size:12px;margin-top:8px;">Memory engine not loaded. Ensure narrative_memory.py is present.</p>
                    </div>
                `;
                return;
            }
            
            // Load series memory, narrative stack, and learnings in parallel
            const [seriesMem, stackInfo, learnings] = await Promise.all([
                prodState.series ? prodFetch(`/series/${prodState.series}/memory`).catch(() => null) : null,
                prodState.series && prodState.season && prodState.episode ? 
                    prodFetch(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/narrative-stack`).catch(() => null) : null,
                prodState.series ? prodFetch(`/series/${prodState.series}/learnings`).catch(() => null) : null,
            ]);
            
            // Build narrative stack visualization
            let stackHtml = '';
            if (stackInfo && !stackInfo.error) {
                const stack = stackInfo.stack || [];
                const active = stackInfo.active_timeline || 'main';
                if (stack.length > 0) {
                    stackHtml = '<div class="narrative-stack-viz">';
                    stackHtml += `<div class="stack-layer main ${active === 'main' ? 'active' : ''}">
                        <span>&#128193; Main Timeline</span>
                        <span style="font-size:10px;color:var(--muted);">depth 0</span>
                    </div>`;
                    stack.forEach((layer, i) => {
                        const layerType = layer.timeline_id ? layer.timeline_id.split('_')[0] : 'nested';
                        const isActive = layer.timeline_id === active;
                        stackHtml += `<div class="stack-layer ${layerType} ${isActive ? 'active' : ''}">
                            <span>&#128260; ${layer.timeline_id || 'nested'}</span>
                            <span style="font-size:10px;color:var(--muted);">depth ${layer.depth || i+1} &middot; scene ${layer.scene_number || '?'}</span>
                        </div>`;
                    });
                    stackHtml += '</div>';
                } else {
                    stackHtml = '<p style="color:var(--muted);font-size:12px;">No nested stories active. Main timeline.</p>';
                }
            }
            
            // Build learning summary
            let learnHtml = '';
            if (learnings && !learnings.error && learnings.total_learnings > 0) {
                const score = learnings.avg_score || 0;
                const scoreClass = score > 0.7 ? 'good' : score > 0.4 ? 'mid' : 'low';
                learnHtml = `
                    <div class="memory-grid">
                        <div class="memory-item">
                            <div class="label">Total Learnings</div>
                            <div class="value">${learnings.total_learnings}</div>
                        </div>
                        <div class="memory-item">
                            <div class="label">Avg Quality Score</div>
                            <div class="value"><span class="learning-score ${scoreClass}">${(score*100).toFixed(0)}%</span></div>
                        </div>
                        <div class="memory-item">
                            <div class="label">Score Trend</div>
                            <div class="value">${learnings.score_trend === 'improving' ? '&#128200; Improving' : '&#128193; Stable'}</div>
                        </div>
                        <div class="memory-item">
                            <div class="label">Total Retakes</div>
                            <div class="value">${learnings.total_retakes || 0}</div>
                        </div>
                    </div>
                    ${learnings.common_issues && learnings.common_issues.length > 0 ? `
                        <div style="margin-top:10px;">
                            <div class="label" style="color:var(--muted);font-size:11px;text-transform:uppercase;margin-bottom:4px;">Common Issues</div>
                            ${learnings.common_issues.slice(0,3).map(i => `<div style="font-size:11px;color:var(--error);margin-bottom:2px;">&#9888; ${i.issue} (${i.count}x)</div>`).join('')}
                        </div>
                    ` : ''}
                `;
            } else {
                learnHtml = '<p style="color:var(--muted);font-size:12px;">No learnings yet. Generate scenes to start the learning loop.</p>';
            }
            
            // Build character visual anchors
            let charAnchorsHtml = '';
            if (seriesMem && !seriesMem.error && seriesMem.visual_anchors) {
                const anchors = seriesMem.visual_anchors;
                const charCount = Object.keys(anchors).length;
                if (charCount > 0) {
                    charAnchorsHtml = '<div class="memory-grid">';
                    for (const [charId, anchor] of Object.entries(anchors)) {
                        charAnchorsHtml += `
                            <div class="memory-item">
                                <div class="label">${charId}</div>
                                <div class="value" style="font-size:11px;">${anchor.scene_count || 0} scenes &middot; last: ${anchor.last_seen_scene || 'never'}</div>
                            </div>
                        `;
                    }
                    charAnchorsHtml += '</div>';
                }
            }
            
            section.innerHTML = `
                <div class="memory-panel">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                        <h4>&#129504; Narrative Memory Engine</h4>
                        <span class="memory-badge on">ACTIVE</span>
                    </div>
                    
                    <div class="memory-tabs">
                        <div class="memory-tab active" onclick="switchMemoryTab('stack', this)">Narrative Stack</div>
                        <div class="memory-tab" onclick="switchMemoryTab('learn', this)">Learning</div>
                        <div class="memory-tab" onclick="switchMemoryTab('anchors', this)">Visual Anchors</div>
                    </div>
                    
                    <div id="memTab-stack" class="mem-tab-content">
                        ${stackHtml || '<p style="color:var(--muted);font-size:12px;">No episode selected.</p>'}
                        ${prodState.series && prodState.season && prodState.episode ? `
                            <div class="prod-btn-row" style="margin-top:10px;">
                                <button class="prod-btn secondary" style="font-size:12px;padding:6px 12px;" onclick="scanNestedStories()">Scan Script for Nested Stories</button>
                                <button class="prod-btn secondary" style="font-size:12px;padding:6px 12px;" onclick="pushNestedStory()">Push Timeline</button>
                                <button class="prod-btn secondary" style="font-size:12px;padding:6px 12px;" onclick="popNestedStory()">Pop Timeline</button>
                            </div>
                        ` : ''}
                    </div>
                    
                    <div id="memTab-learn" class="mem-tab-content" style="display:none;">
                        ${learnHtml}
                    </div>
                    
                    <div id="memTab-anchors" class="mem-tab-content" style="display:none;">
                        ${charAnchorsHtml || '<p style="color:var(--muted);font-size:12px;">No visual anchors yet.</p>'}
                    </div>
                </div>
            `;
        }
        
        function switchMemoryTab(tab, el) {
            document.querySelectorAll('.memory-tab').forEach(t => t.classList.remove('active'));
            el.classList.add('active');
            document.querySelectorAll('.mem-tab-content').forEach(c => c.style.display = 'none');
            document.getElementById('memTab-' + tab).style.display = 'block';
        }
        
        async function scanNestedStories() {
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/narrative-stack/scan`, {});
            if (resp.nested_regions) {
                if (resp.count > 0) {
                    showToast(`Found ${resp.count} nested story regions!`, 'success');
                    const details = resp.nested_regions.map(r => 
                        `${r.type}: lines ${r.start_line}-${r.end_line || 'end'}${r.note ? ' (' + r.note + ')' : ''}`
                    ).join('\n');
                    alert(`Nested stories detected:\n\n${details}`);
                } else {
                    showToast('No nested stories found in script', 'success');
                }
                loadMemoryPanel();
            } else {
                showToast(resp.error || 'Scan failed', 'error');
            }
        }
        
        async function pushNestedStory() {
            const type = prompt('Timeline type (flashback/dream/memory/vision/parallel):', 'flashback');
            if (!type) return;
            const sceneNum = prodState.scene || 1;
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/narrative-stack/push`, {
                type: type,
                scene_number: sceneNum,
            });
            if (resp.status === 'pushed') {
                showToast(`Pushed ${type} timeline (depth ${resp.depth})`, 'success');
                loadMemoryPanel();
            } else {
                showToast(resp.error || 'Push failed', 'error');
            }
        }
        
        async function popNestedStory() {
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/narrative-stack/pop`, {});
            if (resp.status === 'popped') {
                showToast(`Popped to ${resp.restored_timeline} (scene ${resp.restored_scene})`, 'success');
                loadMemoryPanel();
            } else {
                showToast(resp.message || 'Pop failed', 'error');
            }
        }
        
        async function assessScene(sceneNum) {
            const resp = await prodPost(`/series/${prodState.series}/season/${prodState.season}/episode/${prodState.episode}/scenes/${sceneNum}/assess`, {});
            if (resp.overall_score !== undefined) {
                showToast(`Quality: ${(resp.overall_score*100).toFixed(0)}%`, 'success');
                openScene(sceneNum);
            } else {
                showToast(resp.error || 'Assessment failed', 'error');
            }
        }
        
        // ==================== IMAGE STUDIO ====================
        let imgState = {
            model: 'flux', modelName: 'FLUX.1',
            aspectRatio: '1:1', quality: 'standard',
            imageMode: 't2i', referenceImages: [],
            stylePreset: 'None', enhanceTags: new Set(),
            imageOptions: null, imageHistory: [],
            currentImageUrl: null, currentJobId: null,
            imgPollInterval: null,
        };

        async function imgInit() {
            try {
                const resp = await fetch('/api/image/options').then(r => r.json());
                if (resp.error) return;
                imgState.imageOptions = resp;
                imgRenderStylePresets();
                imgRenderQuickPrompts();
                imgRenderEnhanceTags();
                imgLoadHistory();
            } catch(e) { console.warn('Image options not loaded:', e); }
            // Auto-grow textarea
            const ta = document.getElementById('imgPrompt');
            if (ta) {
                ta.addEventListener('input', function() {
                    this.style.height = 'auto';
                    this.style.height = Math.min(this.scrollHeight, 200) + 'px';
                });
            }
            // Slider listeners
            const gs = document.getElementById('imgGuidanceSlider');
            if (gs) gs.oninput = (e) => { document.getElementById('imgGuidanceVal').textContent = e.target.value; };
            const ss = document.getElementById('imgStepsSlider');
            if (ss) ss.oninput = (e) => { document.getElementById('imgStepsVal').textContent = e.target.value; };
            const bs = document.getElementById('imgBatchSlider');
            if (bs) bs.oninput = (e) => { document.getElementById('imgBatchVal').textContent = e.target.value; };
            const rs = document.getElementById('imgRefStrengthSlider');
            if (rs) rs.oninput = (e) => { document.getElementById('imgRefStrengthVal').textContent = e.target.value + '%'; };
        }

        function imgRenderStylePresets() {
            const container = document.getElementById('imgStylePresets');
            if (!container || !imgState.imageOptions) return;
            container.innerHTML = '';
            imgState.imageOptions.style_presets.forEach(s => {
                const btn = document.createElement('button');
                btn.className = 'img-style-btn' + (s === imgState.stylePreset ? ' active' : '');
                btn.textContent = s;
                btn.onclick = () => {
                    imgState.stylePreset = s;
                    container.querySelectorAll('.img-style-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                };
                container.appendChild(btn);
            });
        }

        function imgRenderQuickPrompts() {
            const container = document.getElementById('imgQuickPrompts');
            if (!container || !imgState.imageOptions) return;
            container.innerHTML = '';
            imgState.imageOptions.quick_prompts.forEach(q => {
                const btn = document.createElement('button');
                btn.className = 'img-quick-btn';
                btn.textContent = q.label;
                btn.onclick = () => {
                    document.getElementById('imgPrompt').value = q.prompt;
                    document.getElementById('imgToolsPanel').style.display = 'none';
                };
                container.appendChild(btn);
            });
        }

        function imgRenderEnhanceTags() {
            const container = document.getElementById('imgEnhanceTags');
            if (!container || !imgState.imageOptions) return;
            container.innerHTML = '';
            const tags = imgState.imageOptions.enhance_tags;
            Object.entries(tags).forEach(([category, tagList]) => {
                tagList.forEach(tag => {
                    const btn = document.createElement('button');
                    btn.className = 'img-tag-btn';
                    btn.textContent = tag;
                    btn.onclick = () => {
                        if (imgState.enhanceTags.has(tag)) {
                            imgState.enhanceTags.delete(tag);
                            btn.classList.remove('active');
                        } else {
                            imgState.enhanceTags.add(tag);
                            btn.classList.add('active');
                        }
                        imgUpdateEnhancedPrompt();
                    };
                    container.appendChild(btn);
                });
            });
        }

        function imgUpdateEnhancedPrompt() {
            const base = (document.getElementById('imgBasePrompt')?.value || '').trim();
            const tags = Array.from(imgState.enhanceTags).join(', ');
            const enhanced = [base, tags].filter(p => p).join(', ');
            const display = document.getElementById('imgEnhancedDisplay');
            if (display) {
                display.textContent = enhanced || 'Enhanced prompt will appear here...';
                display.style.color = enhanced ? 'var(--text)' : 'var(--muted)';
            }
        }

        function imgCopyEnhanced() {
            const text = document.getElementById('imgEnhancedDisplay')?.textContent || '';
            if (text && text !== 'Enhanced prompt will appear here...') {
                navigator.clipboard.writeText(text);
                showToast('Copied to clipboard', 'success');
            }
        }

        function imgUseEnhanced() {
            const text = document.getElementById('imgEnhancedDisplay')?.textContent || '';
            if (text && text !== 'Enhanced prompt will appear here...') {
                document.getElementById('imgPrompt').value = text;
                document.getElementById('imgToolsPanel').style.display = 'none';
            }
        }

        function imgToggleAdvanced() {
            const panel = document.getElementById('imgAdvPanel');
            const isVisible = panel.style.display !== 'none';
            panel.style.display = isVisible ? 'none' : 'block';
            document.getElementById('imgAdvLabel').textContent = isVisible ? 'Advanced' : 'Less';
        }

        function imgToggleTools() {
            const panel = document.getElementById('imgToolsPanel');
            panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        }

        function imgToggleDropdown(type) {
            // Remove any existing dropdown
            const existing = document.querySelector('.img-dropdown');
            if (existing) { existing.remove(); return; }
            if (!imgState.imageOptions) return;
            const dd = document.createElement('div');
            dd.className = 'img-dropdown';
            if (type === 'model') {
                const models = imgState.imageMode === 't2i' ? imgState.imageOptions.t2i_models : imgState.imageOptions.i2i_models;
                const search = document.createElement('input');
                search.type = 'text'; search.placeholder = 'Search models...'; search.className = 'img-dropdown-search';
                dd.appendChild(search);
                const list = document.createElement('div');
                const renderList = (filter) => {
                    list.innerHTML = '';
                    Object.entries(models).forEach(([id, m]) => {
                        if (filter && !m.label.toLowerCase().includes(filter.toLowerCase()) && !id.toLowerCase().includes(filter.toLowerCase())) return;
                        const item = document.createElement('div');
                        item.className = 'img-dropdown-item' + (id === imgState.model ? ' selected' : '');
                        item.innerHTML = `<div class="model-icon">${m.label.charAt(0)}</div><div class="model-info"><div class="model-name">${m.label}</div><div class="model-desc">${m.desc}</div></div>`;
                        item.onclick = () => {
                            imgState.model = id; imgState.modelName = m.label;
                            document.getElementById('imgModelLabel').textContent = m.label;
                            // Update available ARs
                            const ars = m.aspect_ratios || Object.keys(imgState.imageOptions.aspect_ratios);
                            if (ars.length > 0 && !ars.includes(imgState.aspectRatio)) {
                                imgState.aspectRatio = ars[0];
                                document.getElementById('imgArLabel').textContent = ars[0];
                            }
                            dd.remove();
                        };
                        list.appendChild(item);
                    });
                };
                renderList('');
                search.oninput = (e) => renderList(e.target.value);
                dd.appendChild(list);
            } else if (type === 'ar') {
                const models = imgState.imageMode === 't2i' ? imgState.imageOptions.t2i_models : imgState.imageOptions.i2i_models;
                const modelInfo = models[imgState.model];
                const ars = modelInfo ? (modelInfo.aspect_ratios || Object.keys(imgState.imageOptions.aspect_ratios)) : Object.keys(imgState.imageOptions.aspect_ratios);
                ars.forEach(r => {
                    const item = document.createElement('div');
                    item.className = 'img-dropdown-item' + (r === imgState.aspectRatio ? ' selected' : '');
                    const label = imgState.imageOptions.aspect_ratios[r] || r;
                    item.innerHTML = `<div class="model-icon" style="font-size:0.6em;">${r}</div><div class="model-info"><div class="model-name">${label}</div></div>`;
                    item.onclick = () => {
                        imgState.aspectRatio = r;
                        document.getElementById('imgArLabel').textContent = r;
                        dd.remove();
                    };
                    dd.appendChild(item);
                });
            } else if (type === 'quality') {
                Object.entries(imgState.imageOptions.quality_presets).forEach(([id, label]) => {
                    const item = document.createElement('div');
                    item.className = 'img-dropdown-item' + (id === imgState.quality ? ' selected' : '');
                    item.innerHTML = `<div class="model-icon" style="font-size:0.6em;">&#9733;</div><div class="model-info"><div class="model-name">${label}</div></div>`;
                    item.onclick = () => {
                        imgState.quality = id;
                        document.getElementById('imgQualityLabel').textContent = label;
                        dd.remove();
                    };
                    dd.appendChild(item);
                });
            }
            // Position near button
            const btn = type === 'model' ? document.getElementById('imgModelBtn') : type === 'ar' ? document.getElementById('imgArBtn') : document.getElementById('imgQualityBtn');
            const rect = btn.getBoundingClientRect();
            dd.style.position = 'fixed';
            dd.style.bottom = (window.innerHeight - rect.top + 8) + 'px';
            dd.style.left = rect.left + 'px';
            document.body.appendChild(dd);
            // Close on outside click
            setTimeout(() => {
                document.addEventListener('click', function close(e) {
                    if (!dd.contains(e.target) && e.target !== btn) { dd.remove(); document.removeEventListener('click', close); }
                });
            }, 100);
        }

        function imgUploadClick() {
            const input = document.createElement('input');
            input.type = 'file'; input.accept = 'image/*'; input.multiple = true;
            input.onchange = (e) => {
                const files = Array.from(e.target.files);
                if (files.length === 0) return;
                imgState.referenceImages = [];
                files.forEach(f => {
                    const url = URL.createObjectURL(f);
                    imgState.referenceImages.push(url);
                });
                imgSwitchMode(true);
                imgRenderRefPreview();
            };
            input.click();
        }

        function imgSwitchMode(toI2I) {
            imgState.imageMode = toI2I ? 'i2i' : 't2i';
            const badge = document.getElementById('imgModeBadge');
            badge.textContent = toI2I ? 'I2I' : 'T2I';
            badge.className = 'img-mode-badge ' + (toI2I ? 'i2i' : 't2i');
            const uploadBtn = document.getElementById('imgUploadBtn');
            uploadBtn.classList.toggle('active', toI2I);
            // Switch model to first available in new mode
            if (imgState.imageOptions) {
                const models = toI2I ? imgState.imageOptions.i2i_models : imgState.imageOptions.t2i_models;
                const firstKey = Object.keys(models)[0];
                if (firstKey) {
                    imgState.model = firstKey;
                    imgState.modelName = models[firstKey].label;
                    document.getElementById('imgModelLabel').textContent = models[firstKey].label;
                    // Update AR if needed
                    const ars = models[firstKey].aspect_ratios;
                    if (ars && !ars.includes(imgState.aspectRatio)) {
                        imgState.aspectRatio = ars[0];
                        document.getElementById('imgArLabel').textContent = ars[0];
                    }
                }
            }
            const ta = document.getElementById('imgPrompt');
            ta.placeholder = toI2I ? 'Describe how to transform this image (optional)...' : 'Describe the image you want to create...';
        }

        function imgRenderRefPreview() {
            const container = document.getElementById('imgRefPreview');
            container.innerHTML = '';
            container.style.display = imgState.referenceImages.length > 0 ? 'flex' : 'none';
            imgState.referenceImages.forEach((url, i) => {
                const thumb = document.createElement('div');
                thumb.className = 'img-ref-thumb';
                thumb.innerHTML = `<img src="${url}" /><div class="ref-remove" onclick="imgRemoveRef(${i})">&times;</div>`;
                container.appendChild(thumb);
            });
        }

        function imgRemoveRef(idx) {
            imgState.referenceImages.splice(idx, 1);
            imgRenderRefPreview();
            if (imgState.referenceImages.length === 0) imgSwitchMode(false);
        }

        async function generateImage() {
            const prompt = document.getElementById('imgPrompt').value.trim();
            if (imgState.imageMode === 't2i' && !prompt) { showToast('Enter a prompt first', 'error'); return; }
            if (imgState.imageMode === 'i2i' && imgState.referenceImages.length === 0) { showToast('Upload a reference image', 'error'); return; }

            const btn = document.getElementById('imgGenBtn');
            btn.disabled = true;
            btn.textContent = 'Generating...';
            document.getElementById('imgHero').style.opacity = '0.3';
            document.getElementById('imgProgress').style.display = 'block';
            document.getElementById('imgProgressFill').style.width = '10%';
            document.getElementById('imgProgressText').textContent = 'Submitting...';

            const payload = {
                prompt: prompt,
                model: imgState.model,
                negative_prompt: document.getElementById('imgNegPrompt')?.value || null,
                aspect_ratio: imgState.aspectRatio,
                quality: imgState.quality,
                seed: parseInt(document.getElementById('imgSeed')?.value) || null,
                batch_count: parseInt(document.getElementById('imgBatchSlider')?.value) || 1,
                style_preset: imgState.stylePreset,
                width: parseInt(document.getElementById('imgWidth')?.value) || null,
                height: parseInt(document.getElementById('imgHeight')?.value) || null,
                guidance_scale: parseFloat(document.getElementById('imgGuidanceSlider')?.value) || 7.5,
                steps: parseInt(document.getElementById('imgStepsSlider')?.value) || 25,
                lora_model: document.getElementById('imgLora')?.value || null,
                lora_weight: 1.0,
                reference_strength: parseInt(document.getElementById('imgRefStrengthSlider')?.value) || 50,
                image_mode: imgState.imageMode,
                reference_images: imgState.imageMode === 'i2i' ? imgState.referenceImages : [],
            };

            try {
                const resp = await fetch('/api/image/generate', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                }).then(r => r.json());

                if (resp.error) throw new Error(resp.error);
                const jobId = resp.job_id || resp.id;
                if (jobId) {
                    imgState.currentJobId = jobId;
                    imgPollImage(jobId, prompt);
                } else if (resp.url) {
                    imgShowResult(resp.url, prompt);
                } else {
                    throw new Error('No job ID or URL in response');
                }
            } catch(e) {
                btn.disabled = false;
                btn.textContent = 'Generate';
                document.getElementById('imgHero').style.opacity = '1';
                document.getElementById('imgProgress').style.display = 'none';
                showToast('Error: ' + e.message, 'error');
            }
        }

        async function imgPollImage(jobId, prompt) {
            let attempts = 0;
            const maxAttempts = 120;
            imgState.imgPollInterval = setInterval(async () => {
                attempts++;
                if (attempts > maxAttempts) {
                    clearInterval(imgState.imgPollInterval);
                    imgResetGenBtn();
                    showToast('Image generation timed out', 'error');
                    return;
                }
                try {
                    const status = await fetch(`/api/image/status/${jobId}`).then(r => r.json());
                    const pct = Math.min(95, 10 + attempts * 0.7);
                    document.getElementById('imgProgressFill').style.width = pct + '%';
                    document.getElementById('imgProgressText').textContent = status.status || 'Processing...';
                    if (status.status === 'completed' || status.status === 'succeeded' || status.status === 'success') {
                        clearInterval(imgState.imgPollInterval);
                        const url = status.url || status.image_url || status.output_url;
                        if (url) {
                            imgShowResult(url, prompt);
                        } else {
                            // Try downloading
                            const dlUrl = `/api/image/download/${jobId}`;
                            imgShowResult(dlUrl, prompt);
                        }
                    } else if (status.status === 'failed' || status.status === 'error') {
                        clearInterval(imgState.imgPollInterval);
                        imgResetGenBtn();
                        showToast('Generation failed: ' + (status.error || 'Unknown'), 'error');
                    }
                } catch(e) { /* keep polling */ }
            }, 2000);
        }

        function imgShowResult(url, prompt) {
            document.getElementById('imgProgressFill').style.width = '100%';
            document.getElementById('imgProgressText').textContent = 'Done!';
            setTimeout(() => {
                document.getElementById('imgProgress').style.display = 'none';
            }, 1000);
            imgState.currentImageUrl = url;
            const canvas = document.getElementById('imgCanvas');
            const img = document.getElementById('imgResult');
            img.src = url;
            img.onload = () => {
                canvas.classList.add('active');
            };
            // Add to history
            imgAddToHistory({ url, prompt, model: imgState.model, timestamp: Date.now() });
            imgResetGenBtn();
        }

        function imgResetGenBtn() {
            const btn = document.getElementById('imgGenBtn');
            btn.disabled = false;
            btn.textContent = 'Generate';
            document.getElementById('imgHero').style.opacity = '1';
        }

        function imgAddToHistory(entry) {
            imgState.imageHistory.unshift(entry);
            imgState.imageHistory = imgState.imageHistory.slice(0, 50);
            try { localStorage.setItem('soul_img_history', JSON.stringify(imgState.imageHistory)); } catch(e) {}
            imgRenderHistory();
        }

        function imgRenderHistory() {
            const list = document.getElementById('imgHistoryList');
            if (!list) return;
            list.innerHTML = '';
            if (imgState.imageHistory.length === 0) {
                document.getElementById('imgHistory').classList.remove('active');
                return;
            }
            document.getElementById('imgHistory').classList.add('active');
            imgState.imageHistory.forEach((entry, idx) => {
                const thumb = document.createElement('div');
                thumb.className = 'img-history-thumb' + (idx === 0 ? ' active' : '');
                thumb.innerHTML = `<img src="${entry.url}" alt="${(entry.prompt||'').substring(0,20)}" /><div class="thumb-overlay"><span style="font-size:10px;">&#8595;</span></div>`;
                thumb.onclick = () => {
                    imgState.currentImageUrl = entry.url;
                    document.getElementById('imgResult').src = entry.url;
                    document.getElementById('imgCanvas').classList.add('active');
                    list.querySelectorAll('.img-history-thumb').forEach(t => t.classList.remove('active'));
                    thumb.classList.add('active');
                };
                thumb.querySelector('.thumb-overlay').onclick = (e) => {
                    e.stopPropagation();
                    imgDownloadImage(entry.url);
                };
                list.appendChild(thumb);
            });
        }

        function imgLoadHistory() {
            try {
                const saved = JSON.parse(localStorage.getItem('soul_img_history') || '[]');
                imgState.imageHistory = saved;
                imgRenderHistory();
            } catch(e) {}
        }

        function imgRegenerate() {
            document.getElementById('imgCanvas').classList.remove('active');
            generateImage();
        }

        function imgDownload() {
            if (imgState.currentImageUrl) imgDownloadImage(imgState.currentImageUrl);
        }

        async function imgDownloadImage(url) {
            try {
                const resp = await fetch(url);
                const blob = await resp.blob();
                const blobUrl = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = blobUrl; a.download = `soulillusions_${Date.now()}.png`;
                document.body.appendChild(a); a.click(); document.body.removeChild(a);
                URL.revokeObjectURL(blobUrl);
            } catch(e) { window.open(url, '_blank'); }
        }

        function imgNewPrompt() {
            document.getElementById('imgCanvas').classList.remove('active');
            document.getElementById('imgPrompt').value = '';
            document.getElementById('imgPrompt').focus();
            imgState.referenceImages = [];
            imgRenderRefPreview();
            imgSwitchMode(false);
        }

        function imgSendToVideo() {
            if (!imgState.currentImageUrl) return;
            // Switch to Video Maker tab and pre-fill with image as first frame
            switchTab('maker');
            showToast('Image loaded! Use it as a reference in your video prompt.', 'success');
            // Add a note to the prompt area about the image
            const promptArea = document.getElementById('prompt');
            if (promptArea && !promptArea.value) {
                promptArea.value = '[First frame from Image Studio] ';
                promptArea.focus();
            }
            // Store the image URL for potential use in generation
            window._imgToVideoUrl = imgState.currentImageUrl;
        }

        // ==================== ASSET LIBRARY ====================
        let assetState = {
            categories: null, assets: [], currentCategory: null,
            selectedAsset: null, searchQuery: '',
        };

        async function assetInit() {
            try {
                const resp = await fetch('/api/assets/categories').then(r => r.json());
                if (resp.error) return;
                assetState.categories = resp.categories;
                assetRenderCategories();
                assetLoadStats();
            } catch(e) { console.warn('Asset library init failed:', e); }
            // Script drop zone drag events
            const dz = document.getElementById('scriptDropZone');
            if (dz) {
                dz.addEventListener('dragover', (e) => { e.preventDefault(); dz.classList.add('dragover'); });
                dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
                dz.addEventListener('drop', (e) => {
                    e.preventDefault(); dz.classList.remove('dragover');
                    const file = e.dataTransfer.files[0];
                    if (file) scriptProcessFile(file);
                });
            }
        }

        function assetRenderCategories() {
            const list = document.getElementById('assetCatList');
            if (!list || !assetState.categories) return;
            list.innerHTML = '';
            // "All" option
            const allItem = document.createElement('div');
            allItem.className = 'asset-cat-item' + (!assetState.currentCategory ? ' active' : '');
            allItem.innerHTML = '<span class="cat-icon">&#9634;</span> All Assets<span class="cat-count" id="catCountAll">0</span>';
            allItem.onclick = () => { assetState.currentCategory = null; assetRenderCategories(); assetLoadGrid(); };
            list.appendChild(allItem);
            Object.entries(assetState.categories).forEach(([key, cat]) => {
                const item = document.createElement('div');
                item.className = 'asset-cat-item' + (assetState.currentCategory === key ? ' active' : '');
                item.innerHTML = `<span class="cat-icon">${cat.icon}</span> ${cat.label}<span class="cat-count" id="catCount_${key}">0</span>`;
                item.onclick = () => { assetState.currentCategory = key; assetRenderCategories(); assetLoadGrid(); };
                list.appendChild(item);
            });
        }

        async function assetLoadStats() {
            try {
                const stats = await fetch('/api/assets/stats').then(r => r.json());
                if (stats.error) return;
                const el = document.getElementById('assetStats');
                if (el) el.innerHTML = `${stats.total_assets} assets &middot; ${stats.total_versions} versions &middot; ${stats.locked_assets} locked`;
                // Update category counts
                Object.entries(stats.by_category || {}).forEach(([cat, count]) => {
                    const c = document.getElementById('catCount_' + cat);
                    if (c) c.textContent = count;
                });
                const allCount = document.getElementById('catCountAll');
                if (allCount) allCount.textContent = stats.total_assets;
            } catch(e) {}
        }

        async function assetLoadGrid() {
            assetShowView('grid');
            const params = new URLSearchParams();
            if (assetState.currentCategory) params.set('category', assetState.currentCategory);
            if (assetState.searchQuery) params.set('search', assetState.searchQuery);
            try {
                const resp = await fetch('/api/assets?' + params.toString()).then(r => r.json());
                if (resp.error) { showToast(resp.error, 'error'); return; }
                assetState.assets = resp.assets || [];
                assetRenderGrid();
            } catch(e) { showToast('Failed to load assets', 'error'); }
        }

        function assetRenderGrid() {
            const grid = document.getElementById('assetGrid');
            grid.innerHTML = '';
            if (assetState.assets.length === 0) {
                grid.innerHTML = '<div class="asset-empty"><h3>No assets found</h3><p>Create a new asset or drop a script to get started.</p></div>';
                return;
            }
            assetState.assets.forEach(a => {
                const card = document.createElement('div');
                card.className = 'asset-card' + (a.locked ? ' locked' : '');
                const v = (a.versions || []).find(v => v.version === a.current_version) || (a.versions || [])[0];
                const imgSrc = v && v.image_refs && v.image_refs[0] ? v.image_refs[0] : '';
                card.innerHTML = `
                    ${imgSrc ? `<img src="${imgSrc}" loading="lazy" />` : `<div style="aspect-ratio:1;background:var(--surface2);border-radius:10px;margin-bottom:8px;display:flex;align-items:center;justify-content:center;font-size:2em;opacity:0.3;">${(assetState.categories[a.category]||{}).icon||'?'}</div>`}
                    <div class="asset-name">${a.name}</div>
                    <div class="asset-cat">${a.subtype || a.category}</div>
                    <div class="asset-ver">v${a.current_version} &middot; ${(a.versions||[]).length} versions</div>
                `;
                card.onclick = () => assetShowDetail(a.asset_id);
                grid.appendChild(card);
            });
        }

        async function assetShowDetail(assetId) {
            assetShowView('detail');
            try {
                const resp = await fetch('/api/assets/' + assetId).then(r => r.json());
                if (resp.error) { showToast(resp.error, 'error'); return; }
                const a = resp.asset;
                assetState.selectedAsset = a;
                const v = (a.versions || []).find(v => v.version === a.current_version) || (a.versions || [])[0];
                const imgSrc = v && v.image_refs && v.image_refs[0] ? v.image_refs[0] : '';
                const catInfo = assetState.categories[a.category] || {icon: '?', label: a.category};
                const container = document.getElementById('assetDetailContainer');
                container.innerHTML = `
                    <div class="asset-detail">
                        <div class="asset-detail-header">
                            ${imgSrc ? `<img class="asset-detail-img" src="${imgSrc}" />` : `<div class="asset-detail-img" style="display:flex;align-items:center;justify-content:center;font-size:3em;opacity:0.3;">${catInfo.icon}</div>`}
                            <div class="asset-detail-info">
                                <h2>${catInfo.icon} ${a.name}</h2>
                                <span class="asset-tag">${catInfo.label}</span>
                                ${a.subtype ? `<span class="asset-tag">${a.subtype}</span>` : ''}
                                ${a.locked ? '<span class="asset-tag" style="background:rgba(34,197,94,0.15);color:#22c55e;">Locked</span>' : ''}
                                ${(a.tags||[]).map(t => `<span class="asset-tag">${t}</span>`).join('')}
                                <div class="asset-desc">${a.description || 'No description'}</div>
                                <div class="asset-actions">
                                    <button class="asset-btn primary" onclick="assetSendToImageStudio('${a.asset_id}')">Send to Image Studio</button>
                                    <button class="asset-btn" onclick="assetSendToVideo('${a.asset_id}')">Send to Video</button>
                                    <button class="asset-btn" onclick="assetToggleLock('${a.asset_id}', ${!a.locked})">${a.locked ? 'Unlock' : 'Lock'} (Consistency)</button>
                                    <button class="asset-btn" onclick="assetAddVersionPrompt('${a.asset_id}')">+ New Version</button>
                                    <button class="asset-btn" onclick="assetBindSeriesPrompt('${a.asset_id}')">Bind to Series</button>
                                    <button class="asset-btn danger" onclick="assetDelete('${a.asset_id}')">Delete</button>
                                </div>
                            </div>
                        </div>
                        <div>
                            <h3 style="font-size:0.9em;margin-bottom:12px;">Version Archive (${(a.versions||[]).length})</h3>
                            <div class="asset-version-list" id="versionList"></div>
                        </div>
                    </div>
                `;
                assetRenderVersions(a);
            } catch(e) { showToast('Failed to load asset', 'error'); }
        }

        function assetRenderVersions(a) {
            const list = document.getElementById('versionList');
            if (!list) return;
            list.innerHTML = '';
            (a.versions || []).sort((x,y) => y.version - x.version).forEach(v => {
                const item = document.createElement('div');
                item.className = 'asset-version-item' + (v.version === a.current_version ? ' current' : '');
                const imgSrc = v.image_refs && v.image_refs[0] ? v.image_refs[0] : '';
                const date = new Date(v.timestamp * 1000).toLocaleDateString();
                item.innerHTML = `
                    ${imgSrc ? `<img src="${imgSrc}" />` : '<div style="width:48px;height:48px;border-radius:8px;background:var(--surface2);display:flex;align-items:center;justify-content:center;font-size:1.2em;opacity:0.3;">?</div>'}
                    <div class="ver-info">
                        <div class="ver-num">Version ${v.version}${v.version === a.current_version ? ' (Current)' : ''}</div>
                        <div class="ver-date">${date} ${v.notes ? '&middot; ' + v.notes : ''}</div>
                    </div>
                    <div class="ver-actions">
                        ${v.version !== a.current_version ? `<button onclick="assetRollback('${a.asset_id}', ${v.version})">Restore</button>` : ''}
                        <button onclick="assetCompareVersions('${a.asset_id}', ${v.version})">View</button>
                    </div>
                `;
                list.appendChild(item);
            });
        }

        function assetShowView(view) {
            document.getElementById('assetEmpty').style.display = view === 'empty' ? 'block' : 'none';
            document.getElementById('assetGridContainer').style.display = view === 'grid' ? 'block' : 'none';
            document.getElementById('assetDetailContainer').style.display = view === 'detail' ? 'block' : 'none';
            document.getElementById('assetScriptContainer').style.display = view === 'script' ? 'block' : 'none';
            document.getElementById('assetCreateContainer').style.display = view === 'create' ? 'block' : 'none';
        }

        function assetShowGrid() {
            assetLoadGrid();
        }

        function assetShowCreate() {
            assetShowView('create');
            const sel = document.getElementById('newAssetCategory');
            sel.innerHTML = '<option value="">Select category...</option>';
            if (assetState.categories) {
                Object.entries(assetState.categories).forEach(([key, cat]) => {
                    sel.innerHTML += `<option value="${key}">${cat.icon} ${cat.label}</option>`;
                });
            }
        }

        function newAssetCatChanged() {
            const cat = document.getElementById('newAssetCategory').value;
            const subSel = document.getElementById('newAssetSubtype');
            if (!cat || !assetState.categories || !assetState.categories[cat]) {
                subSel.style.display = 'none';
                return;
            }
            const subtypes = assetState.categories[cat].subtypes;
            subSel.style.display = 'block';
            subSel.innerHTML = '<option value="">Any subtype</option>' + subtypes.map(s => `<option value="${s}">${s}</option>`).join('');
        }

        async function assetCreateSubmit() {
            const name = document.getElementById('newAssetName').value.trim();
            const category = document.getElementById('newAssetCategory').value;
            const subtype = document.getElementById('newAssetSubtype').value;
            const desc = document.getElementById('newAssetDesc').value.trim();
            const tagsStr = document.getElementById('newAssetTags').value.trim();
            if (!name || !category) { showToast('Name and category required', 'error'); return; }
            const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(t => t) : [];
            try {
                const resp = await fetch('/api/assets/create', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ name, category, subtype, description: desc, tags })
                }).then(r => r.json());
                if (resp.error) { showToast(resp.error, 'error'); return; }
                showToast('Asset created', 'success');
                assetLoadStats();
                assetShowDetail(resp.asset.asset_id);
            } catch(e) { showToast('Create failed', 'error'); }
        }

        async function assetToggleLock(assetId, lock) {
            try {
                const resp = await fetch('/api/assets/' + assetId, {
                    method: 'PUT', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ locked: lock })
                }).then(r => r.json());
                if (resp.error) { showToast(resp.error, 'error'); return; }
                showToast(lock ? 'Asset locked for consistency' : 'Asset unlocked', 'success');
                assetShowDetail(assetId);
                assetLoadStats();
            } catch(e) { showToast('Failed', 'error'); }
        }

        async function assetDelete(assetId) {
            if (!confirm('Delete this asset and all versions?')) return;
            try {
                await fetch('/api/assets/' + assetId, { method: 'DELETE' });
                showToast('Asset deleted', 'success');
                assetLoadStats();
                assetLoadGrid();
            } catch(e) { showToast('Delete failed', 'error'); }
        }

        async function assetRollback(assetId, versionNum) {
            try {
                const resp = await fetch(`/api/assets/${assetId}/rollback/${versionNum}`, { method: 'POST' }).then(r => r.json());
                if (resp.status === 'rolled_back') {
                    showToast(`Restored to version ${versionNum}`, 'success');
                    assetShowDetail(assetId);
                } else { showToast('Rollback failed', 'error'); }
            } catch(e) { showToast('Rollback failed', 'error'); }
        }

        function assetCompareVersions(assetId, versionNum) {
            // Simple: just show the version image in a new tab
            const a = assetState.selectedAsset;
            if (!a) return;
            const v = (a.versions || []).find(v => v.version === versionNum);
            if (v && v.image_refs && v.image_refs[0]) window.open(v.image_refs[0], '_blank');
        }

        async function assetAddVersionPrompt(assetId) {
            const url = prompt('Enter image URL for new version:');
            if (!url) return;
            const notes = prompt('Version notes (optional):') || '';
            try {
                const resp = await fetch(`/api/assets/${assetId}/version`, {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ image_refs: [url], notes })
                }).then(r => r.json());
                if (resp.error) { showToast(resp.error, 'error'); return; }
                showToast('Version added', 'success');
                assetShowDetail(assetId);
                assetLoadStats();
            } catch(e) { showToast('Failed to add version', 'error'); }
        }

        async function assetBindSeriesPrompt(assetId) {
            const seriesId = prompt('Enter Series ID to bind this asset to:');
            if (!seriesId) return;
            try {
                const resp = await fetch(`/api/assets/${assetId}/bind`, {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ series_id: seriesId })
                }).then(r => r.json());
                if (resp.status === 'bound') {
                    showToast('Asset bound to series', 'success');
                    assetShowDetail(assetId);
                } else { showToast('Bind failed', 'error'); }
            } catch(e) { showToast('Bind failed', 'error'); }
        }

        function assetSendToImageStudio(assetId) {
            const a = assetState.selectedAsset;
            if (!a) return;
            const v = (a.versions || []).find(v => v.version === a.current_version) || (a.versions || [])[0];
            if (v && v.image_refs && v.image_refs[0]) {
                switchTab('image');
                // Pre-fill the image prompt with the asset's prompt
                const ta = document.getElementById('imgPrompt');
                if (ta && v.prompt) ta.value = v.prompt;
                // If there are reference images, switch to I2I mode
                if (v.image_refs.length > 0) {
                    imgState.referenceImages = [...v.image_refs];
                    imgSwitchMode(true);
                    imgRenderRefPreview();
                }
                showToast(`Loaded "${a.name}" into Image Studio`, 'success');
            } else {
                showToast('No image in this asset', 'error');
            }
        }

        function assetSendToVideo(assetId) {
            const a = assetState.selectedAsset;
            if (!a) return;
            const v = (a.versions || []).find(v => v.version === a.current_version) || (a.versions || [])[0];
            if (v && v.image_refs && v.image_refs[0]) {
                switchTab('maker');
                window._imgToVideoUrl = v.image_refs[0];
                const promptArea = document.getElementById('prompt');
                if (promptArea) {
                    const tag = `@${a.name.toLowerCase().replace(/\s+/g, '_')}`;
                    promptArea.value = `${tag}: ${v.description || a.description || ''}`;
                    promptArea.focus();
                }
                showToast(`Asset "${a.name}" sent to Video Maker as reference`, 'success');
            } else {
                showToast('No image in this asset', 'error');
            }
        }

        function assetSearchHandler() {
            assetState.searchQuery = document.getElementById('assetSearch').value.trim();
            assetLoadGrid();
        }

        function assetShowScriptDrop() {
            assetShowView('script');
        }

        function scriptBrowseClick() {
            document.getElementById('scriptFileInput').click();
        }

        function scriptFileSelected(event) {
            const file = event.target.files[0];
            if (file) scriptProcessFile(file);
        }

        async function scriptProcessFile(file) {
            const text = await file.text();
            const title = file.name.replace(/\.[^.]+$/, '');
            showToast('Parsing script...', 'success');
            try {
                const resp = await fetch('/api/script/parse', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ script_text: text, title })
                }).then(r => r.json());
                if (resp.error) { showToast(resp.error, 'error'); return; }
                scriptRenderResults(resp, title);
            } catch(e) { showToast('Script parse failed', 'error'); }
        }

        function scriptRenderResults(result, title) {
            const container = document.getElementById('scriptResults');
            container.style.display = 'block';
            const m = result.metadata || {};
            const entityIcons = { character: '\\uD83C\\uDFAD', location: '\\uD83C\\uDFD8\\uFE0F', vehicle: '\\uD83D\\uDE97', object: '\\uD83D\\uDCE6', creature: '\\uD83E\\uDD81', building: '\\uD83C\\uDFDB\\uFE0F' };
            let html = `<h3 style="margin-bottom:8px;">\\uD83C\\uDFAC ${result.title || title}</h3>`;
            html += '<div class="script-stats">';
            html += `<div class="script-stat"><div class="stat-num">${m.total_scenes||0}</div><div class="stat-label">Scenes</div></div>`;
            html += `<div class="script-stat"><div class="stat-num">${m.total_characters||0}</div><div class="stat-label">Characters</div></div>`;
            html += `<div class="script-stat"><div class="stat-num">${m.total_locations||0}</div><div class="stat-label">Locations</div></div>`;
            html += `<div class="script-stat"><div class="stat-num">${m.total_vehicles||0}</div><div class="stat-label">Vehicles</div></div>`;
            html += `<div class="script-stat"><div class="stat-num">${m.total_objects||0}</div><div class="stat-label">Props</div></div>`;
            html += `<div class="script-stat"><div class="stat-num">${m.total_creatures||0}</div><div class="stat-label">Creatures</div></div>`;
            html += '</div>';
            html += '<div style="display:flex;gap:8px;margin-bottom:16px;">';
            html += '<button class="asset-btn primary" onclick="scriptCreateAllAssets()">Create All Assets</button>';
            html += '<button class="asset-btn" onclick="scriptSendAllToImageStudio()">Generate All Images</button>';
            html += '</div>';
            html += '<div class="script-results">';
            (result.entities || []).forEach((e, i) => {
                const icon = entityIcons[e.entity_type] || '\\u2753';
                html += `<div class="script-entity">
                    <div class="entity-icon">${icon}</div>
                    <div class="entity-info">
                        <div class="entity-name">${e.name} <span style="font-size:0.7em;color:var(--muted);">(${e.entity_type}${e.subtype ? '/' + e.subtype : ''})</span></div>
                        <div class="entity-prompt">${(e.suggested_prompt || '').substring(0, 120)}...</div>
                    </div>
                    <div class="entity-actions">
                        <button class="asset-btn" style="padding:6px 12px;font-size:0.75em;" onclick="scriptCreateOneAsset(${i})">Create Asset</button>
                        <button class="asset-btn" style="padding:6px 12px;font-size:0.75em;" onclick="scriptSendOneToImageStudio(${i})">Generate</button>
                    </div>
                </div>`;
            });
            html += '</div>';
            container.innerHTML = html;
            container._parsedData = result;
        }

        async function scriptCreateAllAssets() {
            const container = document.getElementById('scriptResults');
            const data = container._parsedData;
            if (!data || !data.entities) return;
            let created = 0;
            for (const e of data.entities) {
                try {
                    const resp = await fetch('/api/assets/create', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            name: e.name, category: e.entity_type === 'creature' ? 'character' : e.entity_type,
                            subtype: e.subtype || '', description: e.description || '',
                            tags: [e.entity_type], prompt: e.suggested_prompt,
                        })
                    }).then(r => r.json());
                    if (!resp.error) created++;
                } catch(e) {}
            }
            showToast(`${created} assets created from script`, 'success');
            assetLoadStats();
            assetLoadGrid();
        }

        function scriptSendAllToImageStudio() {
            const container = document.getElementById('scriptResults');
            const data = container._parsedData;
            if (!data || !data.entities) return;
            switchTab('image');
            // Load first entity prompt
            if (data.entities.length > 0) {
                document.getElementById('imgPrompt').value = data.entities[0].suggested_prompt;
                showToast(`Loaded first of ${data.entities.length} prompts. Generate each in Image Studio.`, 'success');
            }
        }

        function scriptCreateOneAsset(idx) {
            const container = document.getElementById('scriptResults');
            const data = container._parsedData;
            if (!data || !data.entities || !data.entities[idx]) return;
            const e = data.entities[idx];
            fetch('/api/assets/create', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    name: e.name, category: e.entity_type === 'creature' ? 'character' : e.entity_type,
                    subtype: e.subtype || '', description: e.description || '',
                    tags: [e.entity_type], prompt: e.suggested_prompt,
                })
            }).then(r => r.json()).then(resp => {
                if (resp.error) { showToast(resp.error, 'error'); return; }
                showToast(`Asset "${e.name}" created`, 'success');
                assetLoadStats();
            });
        }

        function scriptSendOneToImageStudio(idx) {
            const container = document.getElementById('scriptResults');
            const data = container._parsedData;
            if (!data || !data.entities || !data.entities[idx]) return;
            const e = data.entities[idx];
            switchTab('image');
            document.getElementById('imgPrompt').value = e.suggested_prompt;
            showToast(`Loaded prompt for "${e.name}"`, 'success');
        }

        init();
    