---
title: Hospital Triage System
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
---

# Hospital Triage System

## Overview

Hospital Triage System is a FastAPI backend with a Streamlit staff dashboard for patient intake, live queue visibility, emergency alerts, and triage decision review. It also keeps the original OpenEnv reinforcement-learning environment for benchmark and agent-evaluation workflows.

The project has two clear modes:

- **Staff dashboard app**: use this for demos and user-facing hospital triage workflows.
- **OpenEnv benchmark**: use this for reinforcement-learning tasks, scoring, and validation.

For the app workflow, medical staff submit patient details through the Streamlit dashboard. The FastAPI backend calculates a priority score, assigns a likely doctor/team, estimates wait time, raises emergency alerts, exposes triage reasoning, and returns compact system-level insights.

For the benchmark workflow, an AI agent interacts with `/reset` and `/step` to solve hospital triage tasks. Scores are normalized inside the open interval `(0,1)` for OpenEnv compatibility.

## Project Structure

```text
hospital_triage_env/
+-- backend/
|   +-- server/
|   |   +-- app.py                  # FastAPI routes for app + OpenEnv
|   |   +-- triage_service.py       # App-facing intake, queue, alerts, doctor matching
|   |   +-- hospital_environment.py # OpenEnv simulation engine
|   +-- client.py                   # HTTP client for OpenEnv workflows
|   +-- inference.py                # Benchmark inference runner
|   +-- models.py                   # Shared Pydantic/OpenEnv models
|   +-- __init__.py
+-- frontend/
|   +-- app.py                  # Streamlit staff dashboard
|   +-- api_client.py           # REST client and response normalization
|   +-- requirements.txt        # Frontend dependencies
+-- tests/
|   +-- test_environment.py
+-- scripts/
|   +-- validate-submission.sh
+-- openenv.yaml                # OpenEnv manifest
+-- pyproject.toml              # Backend dependencies
+-- Dockerfile
+-- README.md
```

## Staff Dashboard

The Streamlit dashboard is the primary user interface for medical staff.

It includes:

- patient intake form with name, age, common symptom suggestions, free-text symptoms, and severity level
- automatic form clearing after successful submission
- compact system overview with doctors available, active emergencies, and average wait time
- grouped live queue sections for High Priority, Medium Priority, and Low Priority
- one-click demo patient loading for hackathon walkthroughs
- priority color coding using red, yellow, and green Streamlit status blocks
- doctor assignment explanation, such as why Emergency Team, Cardiology, Trauma, or General was selected
- short decision summary shown first, with detailed reasoning collapsed under `View details`
- emergency escalation alerts with active and recent events
- triage logic section with scoring rules and patient-specific reasoning
- collapsed backend settings sidebar for local development

### Run the Dashboard Locally

Start the backend on port `8000`:

```bash
pip install -e .
uvicorn backend.server.app:app --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal:

```bash
pip install -r frontend/requirements.txt
streamlit run frontend/app.py --server.port 8501 --server.address 127.0.0.1
```

The frontend defaults to:

```text
http://127.0.0.1:8000
```

You can override it in the Streamlit sidebar or with:

```bash
TRIAGE_API_BASE_URL=http://127.0.0.1:8000
```

Open the dashboard at:

```text
http://127.0.0.1:8501
```

## App API

These routes are used by the Streamlit dashboard:

- `GET /health`: backend health check
- `POST /intake`: create a patient intake record
- `GET /queue`: return live queue rows
- `GET /alerts`: return emergency escalation alerts
- `GET /triage-logic/{patient_id}`: return the priority-score explanation for a patient
- `GET /system-insights`: return compact operational metrics for the dashboard
- `POST /demo/seed`: load a realistic sample queue for demos

Example intake request:

```json
{
  "patient_name": "Anika Sharma",
  "age": 42,
  "symptoms": "Chest pain and shortness of breath",
  "severity": 5
}
```

Example queue response:

```json
{
  "patients": [
    {
      "patient_id": "pt-1234abcd",
      "patient_name": "Anika Sharma",
      "age": 42,
      "symptoms": "Chest pain and shortness of breath",
      "severity": 5,
      "priority_score": 100.0,
      "assigned_doctor": "Emergency Team",
      "assignment_reason": "Assigned to Emergency Team because severity is emergency-level.",
      "estimated_wait_time": "Immediate",
      "status": "Escalated",
      "decision_summary": "High-priority triage due to severity, emergency status, and/or critical symptom signals.",
      "emergency_status": true
    }
  ]
}
```

Example system insights response:

```json
{
  "total_doctors": 4,
  "doctors_available": 4,
  "active_emergencies": 0,
  "average_wait_minutes": 0.0
}
```

## OpenEnv Benchmark

The original RL environment is still available and remains compatible with OpenEnv-style evaluation.

Core OpenEnv routes:

- `GET /tasks`
- `POST /reset`
- `POST /step`
- `GET /state`
- `GET|POST /grader`
- `GET|POST /baseline`

Available tasks:

- `task_1_basic_triage`: specialist matching and prioritization
- `task_2_queue_optimization`: wait-time and resource optimization
- `task_3_emergency_handling`: emergency escalation and urgent-case handling

Run the OpenEnv backend on the traditional validation port:

```bash
pip install -e .
uvicorn backend.server.app:app --host 0.0.0.0 --port 7860
```

Run benchmark inference:

```bash
python -m backend.inference
```

By default, `backend/inference.py` expects:

```text
ENV_BASE_URL=http://127.0.0.1:7860
```

Optional inference environment variables:

```bash
API_BASE_URL=https://your-openai-compatible-endpoint.example/v1
ENV_BASE_URL=http://127.0.0.1:7860
MODEL_NAME=gpt-4.1-mini
HF_TOKEN=your_hf_token
API_KEY=your_api_key
```

## Backend Design

The backend intentionally separates the app workflow from the benchmark workflow:

- `backend/server/triage_service.py` powers the Streamlit app. It handles patient intake, priority scoring, doctor/team matching, queue rows, alerts, and triage explanations.
- `frontend/app.py` renders the Streamlit dashboard, grouped queue cards, system overview, intake form, alerts, and triage logic.
- `frontend/api_client.py` handles REST calls and normalizes backend JSON for the UI.
- `backend/server/hospital_environment.py` powers OpenEnv simulation. It handles seeded tasks, patient dynamics, rewards, and strict score normalization.
- `backend/server/app.py` exposes both sets of routes from one FastAPI application.

This keeps the user-facing app simple while preserving the existing RL benchmark behavior.

## Docker Deployment

The included Dockerfile serves the FastAPI backend:

```bash
docker build -t hospital-triage-system .
docker run -p 7860:7860 hospital-triage-system
```

For a full app deployment, run the Streamlit frontend separately or add a process manager/docker-compose setup that starts both FastAPI and Streamlit.

## Validation

Run tests with:

```bash
python -m unittest discover -s tests
```

For OpenEnv submission checks:

```bash
bash scripts/validate-submission.sh https://<your-space>.hf.space
```

## Notes

- The dashboard assumes the backend is running at `http://127.0.0.1:8000` unless changed.
- The OpenEnv workflow traditionally uses port `7860`.
- All benchmark scores are defensively normalized to remain strictly inside `(0,1)`.
- The frontend has fallback readers for `/state`, but the app workflow is cleanest when `/intake`, `/queue`, `/alerts`, `/triage-logic/{patient_id}`, and `/system-insights` are available.
