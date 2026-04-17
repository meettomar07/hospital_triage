"""API client utilities for the Hospital Triage Streamlit frontend.

The frontend expects an app-oriented FastAPI backend running at:
    http://127.0.0.1:8000

Expected primary endpoints:
    GET  /health
    POST /intake
    GET  /queue
    GET  /alerts
    GET  /triage-logic/{patient_id}
    GET  /system-insights
    POST /demo/seed

For easier local development with the existing OpenEnv-style backend, this
client also includes best-effort fallback readers for /state when /queue or
/alerts are not available. The UI will display a clear error if /intake is not
implemented by the backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
REQUEST_TIMEOUT_SECONDS = 8


@dataclass
class ApiResult:
    """Uniform result object so UI code does not need raw requests handling."""

    ok: bool
    data: Any = None
    error: str | None = None
    status_code: int | None = None


class TriageApiClient:
    """Small REST client for the FastAPI triage backend."""

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def health(self) -> ApiResult:
        return self._request("GET", "/health")

    def submit_intake(self, patient_name: str, age: int, symptoms: str, severity: int) -> ApiResult:
        payload = {
            "patient_name": patient_name.strip(),
            "age": age,
            "symptoms": symptoms.strip(),
            "severity": severity,
        }
        return self._request("POST", "/intake", json=payload)

    def get_queue(self) -> ApiResult:
        """Return normalized queue rows for display.

        Preferred backend response shape:
            {"patients": [{...}]}
        Also accepts:
            [{...}]
            {"queue": [{...}]}
        Fallback:
            reads /state from the OpenEnv backend and maps visible patients.
        """

        result = self._request("GET", "/queue")
        if result.ok:
            return ApiResult(ok=True, data=normalize_queue_payload(result.data))

        state_result = self._request("GET", "/state")
        if state_result.ok:
            return ApiResult(ok=True, data=queue_from_state_payload(state_result.data))

        return result

    def get_alerts(self) -> ApiResult:
        """Return normalized alert dictionaries for high-severity cases."""

        result = self._request("GET", "/alerts")
        if result.ok:
            return ApiResult(ok=True, data=normalize_alert_payload(result.data))

        state_result = self._request("GET", "/state")
        if state_result.ok:
            return ApiResult(ok=True, data=alerts_from_state_payload(state_result.data))

        return result

    def get_triage_logic(self, patient_id: str) -> ApiResult:
        if not patient_id:
            return ApiResult(ok=False, error="Select a patient before requesting triage logic.")
        result = self._request("GET", f"/triage-logic/{patient_id}")
        if result.ok:
            return ApiResult(ok=True, data=normalize_logic_payload(result.data))
        return result

    def get_system_insights(self) -> ApiResult:
        """Fetch compact operational metrics for the dashboard header."""

        return self._request("GET", "/system-insights")

    def seed_demo_patients(self) -> ApiResult:
        """Backend integration: POST /demo/seed loads sample patients for demos."""

        return self._request("POST", "/demo/seed")

    def _request(self, method: str, path: str, **kwargs: Any) -> ApiResult:
        url = f"{self.base_url}{path}"
        try:
            response = self.session.request(method, url, timeout=REQUEST_TIMEOUT_SECONDS, **kwargs)
            if response.status_code >= 400:
                return ApiResult(
                    ok=False,
                    error=_format_http_error(response),
                    status_code=response.status_code,
                )
            try:
                data = response.json()
            except ValueError:
                data = {"message": response.text}
            return ApiResult(ok=True, data=data, status_code=response.status_code)
        except requests.ConnectionError:
            return ApiResult(
                ok=False,
                error=f"Cannot connect to backend at {self.base_url}. Confirm FastAPI is running.",
            )
        except requests.Timeout:
            return ApiResult(ok=False, error=f"Backend request timed out for {path}.")
        except requests.RequestException as exc:
            return ApiResult(ok=False, error=f"Backend request failed: {exc}")


def normalize_queue_payload(payload: Any) -> list[dict[str, Any]]:
    """Map backend JSON into stable table rows used by the Streamlit UI."""

    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = payload.get("patients") or payload.get("queue") or payload.get("items") or []
    else:
        records = []

    normalized: list[dict[str, Any]] = []
    for index, patient in enumerate(records, start=1):
        if not isinstance(patient, dict):
            continue
        patient_id = patient.get("patient_id") or patient.get("id") or f"patient-{index}"
        severity = _safe_int(patient.get("severity", patient.get("estimated_severity", 1)), default=1)
        priority = patient.get("priority_score", patient.get("priority", patient.get("score")))
        priority_score = _safe_float(priority, default=_priority_from_severity(severity))
        triage_logic = normalize_logic_payload(patient.get("triage_logic") or {})
        normalized.append(
            {
                "Patient ID": str(patient_id),
                "Patient Name": patient.get("patient_name") or patient.get("name") or str(patient_id),
                "Age": patient.get("age", "N/A"),
                "Severity": severity,
                "Symptoms": _symptoms_to_text(patient.get("symptoms") or patient.get("symptom_summary", "")),
                "Priority Score": priority_score,
                "Priority Band": _priority_band(priority_score, severity),
                "Assigned Doctor": patient.get("assigned_doctor") or patient.get("assigned_doctor_id") or "Unassigned",
                "Assignment Reason": patient.get("assignment_reason", "Assignment reason was not returned by backend."),
                "Estimated Wait Time": patient.get("estimated_wait_time") or patient.get("wait_time") or patient.get("waiting_time") or "N/A",
                "Status": patient.get("status", "Waiting"),
                "Decision Summary": patient.get("decision_summary") or triage_logic["reasoning"],
                "Decision Factors": triage_logic["factors"],
                "Scoring Logic": triage_logic.get("scoring_logic", ""),
                "Emergency Status": bool(patient.get("emergency_status")) or severity >= 4,
                "Created At": patient.get("created_at", ""),
            }
        )
    return normalized


def queue_from_state_payload(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    return normalize_queue_payload({"patients": payload.get("patients", [])})


def normalize_alert_payload(payload: Any) -> list[dict[str, str]]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = payload.get("alerts") or payload.get("items") or []
        if payload.get("system_escalation"):
            records = list(records) + [{"level": "critical", "message": "System-wide escalation is active."}]
        records = list(records) + list(payload.get("recent_events") or [])
    else:
        records = []

    alerts: list[dict[str, str]] = []
    for record in records:
        if isinstance(record, str):
            alerts.append({"level": "warning", "message": record})
        elif isinstance(record, dict):
            alerts.append(
                {
                    "level": str(record.get("level") or record.get("severity") or "warning").lower(),
                    "message": str(record.get("message") or record.get("detail") or record),
                    "patient_id": str(record.get("patient_id", "")),
                    "created_at": str(record.get("created_at", "")),
                }
            )
    return alerts


def alerts_from_state_payload(payload: Any) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    if not isinstance(payload, dict):
        return alerts
    for patient in payload.get("patients", []):
        if not isinstance(patient, dict):
            continue
        severity = _safe_int(patient.get("severity", patient.get("estimated_severity", 1)), default=1)
        is_emergency = bool(patient.get("emergency_flag")) or severity >= 4 or patient.get("status") == "escalated"
        if is_emergency and patient.get("status") in {None, "waiting", "escalated"}:
            patient_name = patient.get("patient_name") or patient.get("name") or patient.get("patient_id", "Unknown patient")
            alerts.append(
                {
                    "level": "critical" if severity >= 5 else "warning",
                    "message": f"{patient_name} requires urgent attention. Severity: {severity}.",
                }
            )
    return alerts


def normalize_logic_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        reasoning = payload.get("reasoning") or payload.get("logic") or payload.get("explanation")
        factors = payload.get("factors") or payload.get("rules") or []
        return {
            "reasoning": reasoning or "No detailed reasoning was returned by the backend.",
            "factors": factors if isinstance(factors, list) else [factors],
            "scoring_logic": payload.get("scoring_logic", ""),
            "severity_level": payload.get("severity_level", ""),
        }
    if isinstance(payload, str):
        return {"reasoning": payload, "factors": []}
    return {"reasoning": "No triage logic available.", "factors": []}


def _format_http_error(response: requests.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = response.text
    return f"{response.status_code} {response.reason}: {payload}"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return round(default, 2)


def _priority_from_severity(severity: int) -> float:
    return round(max(1, min(5, severity)) * 20, 2)


def _priority_band(priority_score: float, severity: int) -> str:
    if severity >= 4 or priority_score >= 70:
        return "High"
    if severity == 3 or priority_score >= 45:
        return "Medium"
    return "Low"


def _symptoms_to_text(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value or "")
