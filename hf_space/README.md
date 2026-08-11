---
title: SoulIllusions GPU Backend
emoji: 🎬
colorFrom: purple
colorTo: blue
sdk: gradio
sdk_version: "5.0.0"
app_file: app.py
pinned: false
license: mit
---

# SoulIllusions GPU Backend

ZeroGPU (A100 80GB) backend for SoulIllusions AI Video Maker.

## Features
- SDXL image generation
- LTX-Video video generation
- Prompt enhancement with style presets
- Synchronous generation (no polling needed)

## API
- `generate_image` - Generate an image with SDXL
- `generate_video` - Generate a video with LTX-Video
- `status` - Check backend status
