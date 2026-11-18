# Technical Architecture

## Architecture decision
Use a modular monolith with asynchronous jobs and provider adapters. Avoid microservices until workload and team boundaries justify them.

## Components
Internal console; FastAPI; workflow state machine; product/claim service; asset library; campaign/creative service; Agent adapters; Redis job queue; FFmpeg render worker; QC worker; PostgreSQL; S3-compatible object storage.

## Suggested stack
Python 3.11+, FastAPI, Pydantic, PostgreSQL, Redis + RQ, FFmpeg/ffprobe, S3-compatible storage, pytest and GitHub Actions. A lightweight UI is sufficient initially; a Next.js frontend can be considered later.

## Workflow states
DRAFT → PRODUCT_FACT_REVIEW → ASSET_ANALYSIS → MARKETING_BRIEF → CREATIVE_REVIEW → SHOT_MATCHING → OPTIONAL_SCENE_ENHANCEMENT → RENDERING → QUALITY_CHECK → FINAL_VIDEO_REVIEW → READY_TO_PUBLISH → PUBLISHED → PERFORMANCE_LOGGED.

## Rendering
Original footage → normalization/metadata → shot selection → optional enhancement → edit decision list → FFmpeg → subtitles/audio → technical and content QC → approved MP4. AI interprets and recommends; deterministic tools render.

## Guardrails
Enhancement may improve background, lighting, color and framing, but must not change product geometry, material, dimensions, finish, features or included accessories. Store source assets, model/provider, prompt version, render settings, QC and approvals.

## Security
This repository is public. Never commit credentials, customer documents, factory pricing, private footage or TikTok login data. Use local environment files and GitHub Actions secrets. Reserve workspace ownership in the schema, but run a single internal workspace first.