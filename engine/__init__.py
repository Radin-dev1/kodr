"""Kodr engine: vision -> concept -> code + 3D.

Layers (each independently verifiable, all degrade gracefully):
  code   : HF Inference router (Qwen2.5-Coder) with a local template fallback
  vision : local CV on image / sampled video frames (ffmpeg or OpenCV)
  3d     : local procedural voxel->OBJ/GLB/STL export, cloud TripoSR best-effort
"""
from . import codegen, llm, theme, three_d, vision  # noqa: F401

__all__ = ["codegen", "llm", "theme", "three_d", "vision"]