# SoulIllusions — 2026-2027 Research Findings & Upgrade Roadmap

## Comprehensive research into the latest AI video generation, narrative consistency,
## audio-video synthesis, post-processing, prompt engineering, and inference acceleration.

---

## 1. OPEN-SOURCE VIDEO GENERATION MODELS (2026)

### 1.1 Wan 2.2 TI2V-5B (Alibaba)
- **Params:** 5B dense (high-compression VAE)
- **Resolution:** 720P (1280×704) at 24fps
- **VRAM:** 24GB (RTX 4090 with offloading), 8GB minimum with ComfyUI native offloading
- **License:** Apache 2.0
- **Key Innovations:**
  - Wan2.2-VAE with 16×16×4 compression ratio (64x total)
  - Unified T2V + I2V in a single model
  - MoE architecture in larger variants (A14B)
  - Supports text-to-video, image-to-video, speech-to-video, character animation
- **Diffusers Integration:** Yes, native `WanTI2VPipeline`
- **Code:** https://github.com/wan-video/Wan2.2
- **Weights:** https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B-Diffusers
- **Inference:**
  ```python
  from diffusers import WanPipeline
  pipe = WanPipeline.from_pretrained("Wan-AI/Wan2.2-TI2V-5B-Diffusers", torch_dtype=torch.bfloat16)
  pipe.enable_model_cpu_offload()
  video = pipe(prompt="...", num_frames=121, num_inference_steps=50).frames[0]
  ```

### 1.2 Helios-Distilled (PKU)
- **Params:** 14B autoregressive diffusion
- **Speed:** 19.5 FPS on H100 (real-time!), ~10 FPS on Ascend NPU
- **VRAM:** ~6GB with group offloading
- **License:** Apache 2.0
- **Key Innovations:**
  - Autoregressive chunked generation (33 frames per chunk)
  - Minute-scale video without anti-drift heuristics (no self-forcing, error-banks, keyframe sampling)
  - No standard acceleration needed (no KV-cache, sparse attention, quantization)
  - Unified History Injection + Representation Control + Guidance Attention
  - Adversarial Hierarchical Distillation: 50→3 sampling steps
  - Multi-Term Memory Patchification + Pyramid Unified Predictor-Corrector
  - Supports T2V, I2V, V2V, Interactive
- **Diffusers Integration:** Yes, `HeliosPipeline` and `HeliosPyramidPipeline`
- **Code:** https://github.com/PKU-YuanGroup/Helios
- **Weights:** https://huggingface.co/BestWishYsh/Helios-Distilled
- **Inference:**
  ```python
  from diffusers import HeliosPyramidPipeline
  pipe = HeliosPyramidPipeline.from_pretrained("BestWishYsh/Helios-Distilled", torch_dtype=torch.bfloat16)
  pipe.enable_group_offload(...)
  output = pipe(prompt="...", num_frames=240, guidance_scale=1.0, is_enable_stage2=True)
  ```

### 1.3 Motif-Video 2B (Motif Technologies)
- **Params:** 2B
- **Resolution:** 720P (1280×736) at 24fps
- **VRAM:** ~15GB with CPU offloading (RTX 4090), ~30GB without
- **License:** Apache 2.0
- **Key Innovations:**
  - Three-stage architecture: 12 dual-stream + 16 single-stream + 8 DDT decoder layers
  - Shared Cross-Attention for stable text-video alignment
  - T5Gemma2 text encoder
  - Rectified flow matching for velocity prediction
  - GGUF quantization: Q4_K_M = 1.1GB (from 3.7GB BF16), no speed penalty
  - SageAttention: ~3.16x speedup
  - Unified T2V + I2V in single checkpoint
- **Diffusers Integration:** Yes, native `MotifVideoPipeline` and `MotifVideoImage2VideoPipeline`
- **Code:** https://huggingface.co/Motif-Technologies/Motif-Video-2B
- **GGUF:** https://huggingface.co/Motif-Technologies/Motif-Video-2B-GGUF
- **Inference:**
  ```python
  from diffusers import MotifVideoPipeline
  pipe = MotifVideoPipeline.from_pretrained("Motif-Technologies/Motif-Video-2B", torch_dtype=torch.bfloat16)
  pipe.enable_model_cpu_offload()
  video = pipe(prompt="...", negative_prompt="...", height=736, width=1280, num_frames=121, num_inference_steps=50).frames[0]
  ```

### 1.4 HoloCine (CVPR 2026 Highlight)
- **Params:** 14B and 5B variants
- **Resolution:** Multi-shot, minute-scale
- **License:** Open-source (weights on HuggingFace)
- **Key Innovations:**
  - Built on Wan2.2 DiT architecture
  - Window Cross-Attention: localizes text prompts to specific shots for directorial control
  - Sparse Inter-Shot Self-Attention: dense within shots, sparse between them → near-linear scaling
  - Holistic generation: all shots processed simultaneously for global consistency
  - Emergent abilities: persistent character/scene memory, cinematic technique understanding
  - Hierarchical prompt format: global_caption + shot_captions[] + shot_cut_frames[]
  - Variants: full/sparse attention, 14B/5B, long versions for >1 minute
- **Code:** https://github.com/yihao-meng/HoloCine
- **Weights:** https://huggingface.co/hlwang06/HoloCine
- **Inference:**
  ```python
  run_inference(
      pipe=pipe,
      global_caption="A scene in a neon-lit city...",
      shot_captions=["Close-up of character A...", "Wide shot of the city..."],
      num_frames=241,
      shot_cut_frames=[120],
      output_path="output.mp4"
  )
  ```

### 1.5 LTX-2.3 (Lightricks)
- **Params:** 22B
- **Resolution:** Native 4K
- **License:** Open weights
- **Key Innovations:**
  - First open-source model with native 4K + audio + open weights together
  - ID-LoRA support for identity-preserving audio-video generation
  - ComfyUI native integration
- **Note:** Successor to LTX-Video (currently used in SoulIllusions)

### 1.6 Bernini (ByteDance)
- **Params:** 14B (Bernini-R) + MLLM planner
- **License:** Apache 2.0
- **Key Innovations:**
  - MLLM-based semantic planner (Qwen2.5-VL) + DiT-based renderer
  - Latent Semantic Planning for Video Diffusion
  - Better instruction following for complex editing requests
  - Bernini-R 1.3B variant for simpler tasks
- **Code:** https://github.com/bytedance/Bernini
- **Weights:** https://huggingface.co/ByteDance/Bernini-Diffusers

---

## 2. AUDIO-VIDEO JOINT GENERATION (2026)

### 2.1 MOVA (OpenMOSS)
- **Resolution:** 360p and 720p
- **License:** Apache 2.0
- **Key Innovations:**
  - Native bimodal generation: video + audio in single inference pass
  - Asymmetric Dual-Tower Architecture with bidirectional cross-attention
  - SOTA lip-sync and environment-aware sound effects
  - Fully open-source: weights, inference code, training pipelines, LoRA fine-tuning
  - SGLang integration for high-throughput inference
- **Code:** https://github.com/OpenMOSS/MOVA
- **Weights:** https://huggingface.co/OpenMOSS-Team/MOVA-720p

### 2.2 HappyHorse-1.0
- **Params:** 15B unified Transformer (40-layer "sandwich" architecture)
- **Speed:** ~38 seconds for 1080p on H100, ~2 seconds for 5s 256p
- **License:** Apache 2.0 + Commercial Usage
- **Key Innovations:**
  - Native joint audio-video synthesis (dialogue + ambient + Foley)
  - DMD-2 distillation → only 8 denoising steps (CFG-free)
  - 7-language lip-sync: English, Mandarin, Cantonese, Japanese, Korean, German, French
  - Persistent character identity across multi-shot storytelling
  - Multiple aspect ratios: 16:9, 9:16, 1:1
  - #1 Open-Source on Artificial Analysis Video Arena (April 2026)
- **Code:** https://github.com/CalvintheBear/HappyHorse-1.0

### 2.3 ID-LoRA (ECCV 2026)
- **Base Models:** LTX-2 (19B) and LTX-2.3 (22B)
- **License:** Open-source
- **Key Innovations:**
  - Identity-preserving audio-video generation in a single model
  - Voice identity transfer from short reference audio
  - Visual identity control via first-frame conditioning
  - Unified audio-video diffusion (not cascaded)
  - Zero-shot inference — just load LoRA weights
  - Two-Stage HQ inference mode for higher fidelity
  - ComfyUI native integration (PR #13111)
- **Code:** https://github.com/ID-LoRA/ID-LoRA

### 2.4 MultiTalk / LongCat-Video-Avatar-1.5 (MeiGen-AI)
- **License:** Apache 2.0
- **Key Innovations:**
  - Audio-driven multi-person conversational video generation
  - Whisper-Large for accurate lip synchronization (v1.5)
  - 8-step distillation acceleration
  - Supports singing, cartoon, interaction control
  - 480p & 720p at arbitrary aspect ratios
  - Long video up to 15 seconds
- **Code:** https://github.com/MeiGen-AI/MultiTalk
- **LongCat:** https://github.com/meituan-longcat/LongCat-Video

---

## 3. NARRATIVE CONSISTENCY FRAMEWORKS

### 3.1 ViMax (HKUDS, 11K stars)
- **License:** MIT
- **Key Innovations:**
  - Multi-agent architecture: Director, Screenwriter, Shot Planner, Character Styling, Video Generator, VLM Quality Control
  - Hierarchical narrative decomposition with retrieval-augmented generation
  - Graph-based visual consistency: tracks cross-shot character/environment dependencies
  - Transition video generation for spatial coherence across camera angles
  - VLM-guided agents continuously monitor and refine narrative + visual fidelity
  - Best-of-k selection for quality control
  - Workflows: Idea2Video, Script2Video, Novel2Video, AutoCameo
  - Web UI with project management, agent loop conversations, storyboard previews
  - Parallelized generation for multi-shot acceleration
- **Code:** https://github.com/HKUDS/ViMax

### 3.2 InfinityStory (Adobe Research / KAUST)
- **VBench Rankings:** #1 Background Consistency (88.94), #1 Subject Consistency (82.11), #1 Overall (2.80)
- **Key Innovations:**
  - Hierarchical multi-agent: Chapters → Locations → Scenes → Shots
  - Location Library: canonical background images generated first, injected into every shot
  - Background fusion: I2I composes canonical background + character references
  - Perceptual loss function penalizes visual drift from canonical background
  - CMTS (Cinematic Multi-Subject Transition Synthesis): 10,000 transition videos
  - FLF2V (First-Last-Frame-to-Video) model for smooth multi-subject transitions
  - Alternating shot structure: odd=I2V narrative, even=FLF2V transition
  - Cross-shot memory accumulates identity and layout info
  - Scales to hour-long narratives

### 3.3 VideoMemory
- **Key Innovations:**
  - Entity-centric Dynamic Memory Bank
  - Stores explicit visual + semantic descriptors for characters, props, backgrounds
  - Retrieval-update mechanism: retrieve entity states before generation, update after
  - Multi-agent system decomposes narrative into shots
  - 54-case multi-shot consistency benchmark
  - Enables consistent portrayal across distant shots

### 3.4 CineOrchestra (Snap Research)
- **License:** MIT
- **Key Innovations:**
  - Unified entity-centric conditioning: subjects, events, camera, shot transitions in ONE forward pass
  - Shared primitive: (start_time, end_time, prompt, [reference_image])
  - Interval-sampled temporal RoPE: consistent attention across events 0.1s to 10s
  - 2D entity-temporal cross-attention RoPE: routes conditions to spatiotemporal targets
  - Generalizes from 10s training clips to 40s inference (4x extrapolation)
  - CineBenchSyn benchmark with evaluation pipeline
- **Code:** https://github.com/snap-research/CineOrchestra

### 3.5 HoloCine (CVPR 2026 Highlight) — also listed in models
- Persistent character/scene memory as emergent ability
- Holistic multi-shot generation ensures global consistency
- Window Cross-Attention for per-shot directorial control

---

## 4. VIDEO POST-PROCESSING & ENHANCEMENT

### 4.1 Super Resolution
- **Real-ESRGAN** — 2x/4x upscaling, ONNX models, BSD-3-Clause
  - Models: realesr-general (live-action), realesr-anime (fast), realesrgan-x4plus (best quality)
  - Smart tiling for any image size with Hann-windowed blending
- **FlashVSR** — Streaming video super-resolution for arbitrary length videos
  - Processes in chunks to avoid memory issues

### 4.2 Frame Interpolation
- **RIFE 4.25/4.26** — Multiply FPS 2x/4x/8x
  - Smart scene detection: avoids blurry ghosting across cuts
  - Ensemble mode: horizontal-flip averaging for higher fidelity
  - ~51ms/frame on Apple M5
- **GIMM-VFI** — Next-gen frame interpolation model
  - Higher quality than RIFE for some cases

### 4.3 Combined Tools
- **videnoa** — Node-based pipeline: Real-ESRGAN + RIFE with TensorRT acceleration
- **Sqwale** — CLI tool: RIFE 4.25 + ONNX upscaling, streaming pipelines, cross-platform
- **venhance** — Apple Silicon native: interpolation + SR in one pass
- **VSRFI-ComfyUI** — ComfyUI node: FlashVSR + GIMM-VFI/RIFE/FILM, stream processing

### 4.4 Implementation for SoulIllusions
```python
# Post-processing pipeline
def enhance_video(input_path, scale=2, target_fps=None):
    # 1. Super-resolution with Real-ESRGAN
    if scale > 1:
        video = upscale_video(input_path, model="realesr-general", scale=scale)
    # 2. Frame interpolation with RIFE
    if target_fps:
        video = interpolate_frames(video, model="rife-v4.7", target_fps=target_fps)
    return video
```

---

## 5. PROMPT ENHANCEMENT

### 5.1 Six-Dimension Framework
Structured prompt engineering for video generation:
1. **Absolute subject** — exactly one protagonist
2. **Core action** — exactly one primary action
3. **Frame boundaries** — rules for background & secondary characters
4. **Camera movement** — explicit type, direction, framing
5. **Lighting & color** — directional light, contrast, tone
6. **Timeline** — second-by-second state evolution

### 5.2 Video Prompt Enhancer LLM
- Fine-tuned Qwen2.5-14B-Instruct with LoRA
- Two-stage training: next-token prediction + online RL with PPO
- VisionReward scoring for feedback loop
- Simple prompts → professional-grade prompts
- **Code:** https://github.com/dariakryvosheieva/video-prompt-enhancer

### 5.3 Veo 3 Prompt Optimizer
- Gemini 2.5 Pro with structured output
- Canonical JSON with style, technical, audio fields
- Multi-platform payloads (FAL.ai, Replicate)
- **Code:** https://github.com/sanky369/veo3-prompt-optimizer

### 5.4 Seedance Superprompt
- WRITE/LINT/FIX modes for prompt engineering
- 25-rule audit system with 1-10 scoring
- 3-segment timeline structure
- Named cameras, color+material+light triplets
- **Code:** https://github.com/scotti1i/seedance-2.0-superprompt

### 5.5 Implementation for SoulIllusions
```python
def enhance_prompt_simple(prompt, style="cinematic"):
    """Six-dimension structured prompt enhancement."""
    dimensions = {
        "subject": extract_subject(prompt),
        "action": extract_action(prompt),
        "frame": f"background: {infer_setting(prompt)}, secondary: none",
        "camera": infer_camera(style),
        "lighting": infer_lighting(style),
        "timeline": f"0-5s: {prompt}"
    }
    return format_structured_prompt(dimensions)
```

---

## 6. INFERENCE ACCELERATION & DISTILLATION

### 6.1 BLADE (ICLR 2026)
- Block-sparse attention + step distillation
- 50 → 8 inference steps
- Supports CogVideoX-5B and Wan-1.3B (plug-and-play)
- Data-free framework (TDM distillation)
- **Code:** https://github.com/ziplab/BLADE
- **Weights:** https://huggingface.co/GYP666/BLADE

### 6.2 DSA (Dynamic Step Allocation)
- Confidence-guided adaptive computation
- Lightweight confidence head trained jointly with generator
- Simple frames: fewer steps, complex frames: more steps
- 22.63 FPS on H100 with sub-second latency
- Distilled from Wan-1.3B and Wan-14B

### 6.3 DisCa (Tencent Hunyuan)
- Distillation-compatible learnable feature caching
- Lightweight predictor (<4% of DiT size) replaces full model passes
- Restricted MeanFlow for stable distillation
- Works on HunyuanVideo-1.0 (T2V) and HunyuanVideo-1.5 (I2V)
- **Code:** https://github.com/Tencent-Hunyuan/DisCa

### 6.4 Adaptive Video Distillation (CVPR 2026)
- Fixes oversaturation and temporal collapse in few-step generation
- DMD-based with adaptive sampling
- Can learn from new data during distillation training
- **Code:** https://github.com/yuyangyou/Adaptive-Video-Distillation

### 6.5 Dynamic-in-Few-Step
- 24% FLOP reduction on top of 4-step distillation
- 30x speedup over 50-step teacher (Wan-14B)
- Step-specific Mixture-of-Models (MoM)
- Progressive Training Strategy + Output Rollout Mechanism

---

## 7. 2027 PIPELINE PREDICTIONS

### Duration
- 60-second coherent generation becoming standard (late 2026 - mid 2027)
- Helios already at minute-scale, Seedance 2.5 at 30s with multi-round extensions
- Long-Context Video Transformers targeting 10-20 minute coherent segments

### Speed
- Real-time generation for short clips (Helios at 19.5 FPS already)
- Sub-2-second generation threshold for interactivity
- Consistency models: 1-4 denoising steps instead of 20-100

### Quality
- Physics becoming believable for commercial work (fluid dynamics, cloth, collisions)
- Audio-native generation becoming standard (FLUX 3, Seedance 2.5, Veo 3.1, MOVA)
- Character consistency extending past 60 seconds

### Economics
- Per-clip cost approaching zero for normal-volume users
- Tool consolidation: ~12 viable tools → ~3 dominant models
- Vertical-specific platforms emerging

### Upcoming Models to Watch
- **Wan 3.0** (Alibaba) — Targeted mid-2026: 60B params, native 4K, 30s continuous
- **FLUX 3 Dev** — Open-weight variant of FLUX 3
- **Sora replacement** — OpenAI's next video model (Sora API sunset Sept 2026)

---

## 8. UPGRADE IMPLEMENTATION PRIORITY

### Phase 1: GPU Backend Models (Highest Impact)
1. Replace LTX-Video → LTX-2.3 (native 4K, audio)
2. Replace Wan 2.1 1.3B → Wan 2.2 TI2V-5B (720P@24fps, 4090-compatible)
3. Replace CogVideoX-2B → Motif-Video 2B (720P, GGUF quantized, modern architecture)
4. Add Helios-Distilled (real-time, minute-scale, 6GB VRAM)
5. Add HoloCine (multi-shot narrative generation)

### Phase 2: Audio-Video Generation
1. Add MOVA for native audio+video generation
2. Add ID-LoRA for character voice + visual identity
3. Add MultiTalk for multi-person dialogue scenes

### Phase 3: Post-Processing Pipeline
1. Real-ESRGAN super-resolution (2x/4x upscaling)
2. RIFE frame interpolation (FPS multiplication)
3. Combined enhancement pipeline

### Phase 4: Prompt Enhancement
1. Six-dimension structured prompt framework
2. Style-specific prompt templates
3. Negative prompt optimization

### Phase 5: Inference Acceleration
1. BLADE step distillation (50→8 steps for Wan/CogVideoX)
2. Dynamic step allocation for adaptive compute
3. GGUF quantization support for all models

### Phase 6: Production Suite Upgrades
1. ViMax-style multi-agent pipeline integration
2. InfinityStory background consistency (location injection)
3. CineOrchestra entity-centric conditioning concepts
4. VLM-based quality assessment

### Phase 7: Server UI Updates
1. New model selectors with capability descriptions
2. Audio generation options
3. Post-processing controls (upscale, interpolate)
4. Prompt enhancement preview
5. Acceleration settings

### Phase 8: Chatbot Companion (Later)
1. Persistent memory of production decisions
2. Proactive scene improvement suggestions
3. Script review and feedback
4. Emotion-aware interactions
