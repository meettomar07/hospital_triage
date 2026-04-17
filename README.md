---
title: Hospital Triage System
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
---

# Hospital Triage System

A hospital triage dashboard and simulation backend built with FastAPI and Streamlit, with an OpenEnv-compatible reinforcement learning environment for benchmarking agent behavior.

## Live Demo

- **Frontend (Streamlit):** https://hospitaltriageenv-dgx4gpqnn4y7lw2vqvvhpf.streamlit.app
- **Backend (Vercel):** https://hospital-triage-eta.vercel.app

Click `Load Demo Patients` or submit a patient through the intake form.

## Quick Demo (Local)

1. Start the backend:

```bash
pip install -e .
uvicorn backend.server.app:app --host 127.0.0.1 --port 8000
```

2. Start the frontend in another terminal:

```bash
pip install -r frontend/requirements.txt
streamlit run frontend/app.py --server.port 8501 --server.address 127.0.0.1
```

3. Open the dashboard:

```text
http://127.0.0.1:8501
```

4. Click `Load Demo Patients` or submit a patient through the intake form.

## Overview

This project simulates hospital front-desk triage in a practical, explainable way. Staff can enter patient details, view a live queue, monitor urgent cases, and understand why the system assigned a priority level or doctor team.

The same repository also includes an OpenEnv-compatible reinforcement learning environment, so the triage workflow can be used both as a user-facing application and as an evaluation benchmark for AI agents.

## Highlights

- **Explainable decisions**: every patient includes a short decision summary, detailed reasoning steps, and doctor assignment rationale.
- **Real-time queue workflow**: the dashboard shows live queue sections, emergency alerts, wait times, and system-level status.
- **Dual-mode design**: the project supports both a practical dashboard app and an OpenEnv RL benchmark in one backend.

## Features

- Patient intake form with name, age, symptoms, and severity
- Common symptom suggestions plus free-text symptom input
- Automatic form reset after successful submission
- Live queue grouped by high, medium, and low priority
- Priority color coding for fast triage visibility
- Emergency alert panel with active and recent events
- System overview showing doctors available, active emergencies, and average wait time
- Decision explanations with collapsed reasoning details
- Doctor assignment explanation for each patient
- One-click demo queue loading for hackathon walkthroughs
- OpenEnv-compatible routes for RL benchmarking and validation

## Architecture

### Simple Flow

```text
User -> Streamlit UI -> FastAPI API -> Triage Logic -> Response
```

### What Happens

1. A user submits patient details in the Streamlit dashboard.
2. The FastAPI backend receives the intake request.
3. The triage service calculates priority, selects a doctor or team, estimates wait time, and generates reasoning.
4. The frontend refreshes the queue, alerts, and system overview.
5. The same backend can also serve OpenEnv benchmark routes for RL evaluation.

## Project Structure

```text
hospital_triage_env/
+-- backend/
|   +-- server/
|   |   +-- app.py
|   |   +-- triage_service.py
|   |   +-- hospital_environment.py
|   +-- client.py
|   +-- inference.py
|   +-- models.py
|   +-- __init__.py
+-- frontend/
|   +-- app.py
|   +-- api_client.py
|   +-- requirements.txt
+-- tests/
|   +-- test_environment.py
+-- app.py
+-- requirements.txt
+-- vercel.json
+-- LICENSE
+-- openenv.yaml
+-- pyproject.toml
+-- Dockerfile
+-- README.md
```

## How to Run

### App Mode (Local)

Start the backend:

```bash
pip install -e .
uvicorn backend.server.app:app --host 127.0.0.1 --port 8000
```

Start the frontend:

```bash
pip install -r frontend/requirements.txt
streamlit run frontend/app.py --server.port 8501 --server.address 127.0.0.1
```

Open:

```text
http://127.0.0.1:8501
```

Default backend URL:

```text
http://127.0.0.1:8000
```

Optional override:

```bash
TRIAGE_API_BASE_URL=http://127.0.0.1:8000
```

If the dashboard sidebar shows `Backend unavailable`, confirm the backend URL is exactly `http://127.0.0.1:8000`.

### App Mode (Deployed)

The backend is deployed on Vercel and the frontend on Streamlit Community Cloud.

To connect the Streamlit frontend to the Vercel backend, set the following secret in Streamlit Cloud (Settings → Secrets):

```toml
TRIAGE_API_BASE_URL = "https://hospital-triage-eta.vercel.app"
```

### OpenEnv Benchmark Mode

Run the backend on the OpenEnv port:

```bash
pip install -e .
uvicorn backend.server.app:app --host 0.0.0.0 --port 7860
```

Run benchmark inference:

```bash
python -m backend.inference
```

Default benchmark backend URL:

```text
ENV_BASE_URL=http://127.0.0.1:7860
```

## API Endpoints

### Dashboard App Endpoints

- `GET /health` - backend health check
- `POST /intake` - create a patient intake record
- `GET /queue` - fetch current queue rows
- `GET /alerts` - fetch active and recent emergency events
- `GET /triage-logic/{patient_id}` - fetch detailed decision reasoning
- `GET /system-insights` - fetch compact system-level metrics
- `POST /demo/seed` - load a sample demo queue

### Demo Seed

`POST /demo/seed` loads a realistic starter queue so the dashboard can be demonstrated immediately without manual data entry.

### OpenEnv Endpoints

- `GET /tasks`
- `POST /reset`
- `POST /step`
- `GET /state`
- `GET|POST /grader`
- `GET|POST /baseline`

## Demo Instructions

For a quick walkthrough:

1. Start the backend and frontend.
2. Open the dashboard at `http://127.0.0.1:8501`.
3. Click `Load Demo Patients`.
4. Review the grouped queue, system overview, emergency alerts, and decision summaries.
5. Open `View details` on a patient card to inspect the reasoning steps.

For a manual workflow:

1. Enter a new patient through the intake form.
2. Submit symptoms and severity.
3. Watch the queue update immediately.
4. Inspect the assigned doctor, wait time, and decision explanation.

## Validation

Run tests with:

```bash
python -m unittest discover -s tests
```

## Notes

- The dashboard assumes the backend is running at `http://127.0.0.1:8000` unless changed.
- The OpenEnv workflow traditionally uses port `7860`.
- Benchmark scores are normalized to remain strictly inside `(0,1)`.
- The frontend includes fallback readers for `/state`, but the cleanest app flow uses the app-specific endpoints listed above.
