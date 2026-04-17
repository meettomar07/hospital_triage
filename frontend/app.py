"""Hospital Triage System Streamlit frontend.

Setup:
    pip install -r frontend/requirements.txt
    streamlit run frontend/app.py

Configuration:
    The default FastAPI backend URL is http://127.0.0.1:8000.
    You can override it from the sidebar or with:
        TRIAGE_API_BASE_URL=http://127.0.0.1:8000

Backend integration:
    POST /intake sends patient intake data.
    GET  /queue fetches patient queue rows and decision explanations.
    GET  /alerts fetches emergency alerts and recent emergency events.
    GET  /triage-logic/{patient_id} fetches detailed reasoning for one patient.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import streamlit as st

from api_client import DEFAULT_BASE_URL, TriageApiClient


COMMON_SYMPTOMS = [
    "Chest pain",
    "Shortness of breath",
    "Heavy bleeding",
    "High fever",
    "Confusion",
    "Seizure",
    "Trauma injury",
    "Severe headache",
    "Wheezing",
    "Abdominal pain",
]


st.set_page_config(
    page_title="Hospital Triage System",
    page_icon="H",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def get_client(base_url: str) -> TriageApiClient:
    return TriageApiClient(base_url=base_url)


def initialize_state() -> None:
    """Store UI-only values across Streamlit reruns.

    `last_submission` is used to highlight a newly added patient in the queue.
    `last_updated_at` tells staff when queue data was last fetched.
    """

    st.session_state.setdefault("last_submission", None)
    st.session_state.setdefault("last_updated_at", None)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.4rem; }
        .section-card {
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            padding: 1rem;
            background: #ffffff;
            color: #111827;
            margin-bottom: 0.8rem;
        }
        .patient-card {
            border: 1px solid #e5e7eb;
            border-left-width: 8px;
            border-radius: 14px;
            padding: 1rem 1.1rem;
            margin-bottom: 0.9rem;
            background: #ffffff;
            color: #111827;
        }
        .patient-card h4,
        .patient-card p,
        .patient-card strong,
        .patient-card li {
            color: #111827;
        }
        .priority-high { border-left-color: #dc2626; }
        .priority-medium { border-left-color: #d97706; }
        .priority-low { border-left-color: #16a34a; }
        .patient-new { box-shadow: 0 0 0 2px #2563eb22; background: #f8fbff; }
        .pill {
            display: inline-block;
            border-radius: 999px;
            padding: 0.2rem 0.55rem;
            font-size: 0.78rem;
            font-weight: 700;
            margin-right: 0.35rem;
        }
        .pill-high { background: #fee2e2; color: #991b1b; }
        .pill-medium { background: #fef3c7; color: #92400e; }
        .pill-low { background: #dcfce7; color: #166534; }
        .pill-neutral { background: #eef2f7; color: #334155; }
        .muted { color: #64748b; font-size: 0.9rem; }
        .decision-box {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 0.75rem;
            margin-top: 0.7rem;
            color: #111827;
        }
        .decision-box p,
        .decision-box strong,
        .decision-box li {
            color: #111827;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> tuple[str, bool]:
    st.sidebar.title("Settings")
    st.sidebar.caption("Backend connection for local development.")

    default_url = os.getenv("TRIAGE_API_BASE_URL", DEFAULT_BASE_URL)
    base_url = st.sidebar.text_input("Backend API URL", value=default_url)
    show_raw_debug = st.sidebar.toggle("Show raw API responses", value=False)

    return base_url.rstrip("/"), show_raw_debug


def render_health(client: TriageApiClient) -> None:
    result = client.health()
    if result.ok:
        st.sidebar.success("Backend connected")
    else:
        st.sidebar.error("Backend unavailable")
        st.sidebar.caption(result.error)


def render_intake_form(client: TriageApiClient, show_raw_debug: bool) -> None:
    st.subheader("Patient Intake")
    st.caption("Enter symptoms manually or select common symptoms to speed up intake.")

    # clear_on_submit resets all intake widgets after the submit callback completes.
    # We keep submission feedback in session_state separately so it does not repopulate the form.
    with st.form("patient_intake_form", clear_on_submit=True):
        patient_name = st.text_input("Patient Name", placeholder="e.g., Anika Sharma")
        age = st.number_input("Age", min_value=0, max_value=120, value=35, step=1)
        selected_symptoms = st.multiselect(
            "Common Symptoms",
            options=COMMON_SYMPTOMS,
            help="Optional. These are combined with the free-text symptom notes below.",
        )
        free_text_symptoms = st.text_area(
            "Additional Symptom Notes",
            placeholder="Add duration, severity, vital signs, or context such as 'pain radiating to left arm'.",
            height=110,
        )
        severity = st.selectbox(
            "Severity Level",
            options=[1, 2, 3, 4, 5],
            index=2,
            format_func=lambda value: {
                1: "1 - Low",
                2: "2 - Mild",
                3: "3 - Moderate",
                4: "4 - Urgent",
                5: "5 - Emergency",
            }[value],
            help="Severity 4-5 will be emphasized in the emergency section.",
        )
        submitted = st.form_submit_button("Submit to Triage", type="primary", use_container_width=True)

    if not submitted:
        return

    symptoms = _combine_symptoms(selected_symptoms, free_text_symptoms)
    if not patient_name.strip() or not symptoms.strip():
        st.warning("Patient name and at least one symptom are required.")
        return

    with st.spinner("Submitting patient to triage..."):
        result = client.submit_intake(patient_name, int(age), symptoms, int(severity))

    if result.ok:
        st.session_state["last_submission"] = result.data
        st.success("Patient submitted successfully. The queue has been updated.")
        submitted_patient = result.data or {}
        st.info(
            f"New patient: {submitted_patient.get('patient_name', patient_name)} | "
            f"Priority: {submitted_patient.get('priority_score', 'N/A')} | "
            f"Assigned: {submitted_patient.get('assigned_doctor', 'Unassigned')}"
        )
        if show_raw_debug:
            st.json(result.data)
    else:
        st.error("Could not submit patient intake.")
        st.caption(result.error)


def render_alerts(client: TriageApiClient) -> None:
    st.subheader("Emergency Alerts")
    alerts_result = client.get_alerts()

    if not alerts_result.ok:
        st.warning("Unable to load escalation alerts.")
        st.caption(alerts_result.error)
        return

    alerts = _dedupe_alerts(alerts_result.data or [])
    active_alerts = [alert for alert in alerts if str(alert.get("level", "")).lower() in {"critical", "high", "5"}]

    if active_alerts:
        st.error(f"{len(active_alerts)} active emergency alert(s) need immediate attention.")
    elif alerts:
        st.warning("Urgent cases are present. Continue monitoring the queue.")
    else:
        st.success("No active emergency escalations.")

    if alerts:
        st.markdown("**Recent emergency events**")
        for alert in alerts[:5]:
            level = str(alert.get("level", "warning")).lower()
            message = str(alert.get("message", "Escalation requires attention."))
            if level in {"critical", "high", "5"}:
                st.error(message)
            else:
                st.warning(message)


def render_queue_dashboard(client: TriageApiClient) -> list[dict[str, Any]]:
    title_col, seed_col, action_col = st.columns([0.58, 0.2, 0.22], vertical_alignment="center")
    with title_col:
        st.subheader("Live Queue Dashboard")
        st.caption("Priority color: red = high, yellow = medium, green = low.")
    with seed_col:
        if st.button("Load Demo Patients", use_container_width=True):
            with st.spinner("Loading demo queue..."):
                result = client.seed_demo_patients()
            if result.ok:
                st.session_state["last_submission"] = None
                st.success("Demo patients loaded.")
                st.rerun()
            else:
                st.error("Could not load demo patients.")
                st.caption(result.error)
    with action_col:
        if st.button("Refresh Queue", use_container_width=True):
            st.rerun()

    queue_result = client.get_queue()
    if not queue_result.ok:
        st.error("Unable to load patient queue.")
        st.caption(queue_result.error)
        return []

    queue_rows = queue_result.data or []
    st.session_state["last_updated_at"] = datetime.now().strftime("%H:%M:%S")
    st.caption(f"Last updated: {st.session_state['last_updated_at']}")

    if not queue_rows:
        st.info("No patients are currently present in the queue.")
        return []

    grouped_rows = _group_by_priority(queue_rows)
    high_count = len(grouped_rows["High"])
    medium_count = len(grouped_rows["Medium"])
    low_count = len(grouped_rows["Low"])

    metric_col_1, metric_col_2, metric_col_3, metric_col_4 = st.columns(4)
    metric_col_1.metric("Total Patients", len(queue_rows))
    metric_col_2.metric("High Priority", high_count)
    metric_col_3.metric("Medium Priority", medium_count)
    metric_col_4.metric("Low Priority", low_count)

    last_patient_id = _last_submitted_patient_id()
    for band, title in [
        ("High", "High Priority"),
        ("Medium", "Medium Priority"),
        ("Low", "Low Priority"),
    ]:
        rows = grouped_rows[band]
        if not rows:
            continue
        st.markdown(f"### {title}")
        for row in rows:
            render_patient_card(row, is_new=row.get("Patient ID") == last_patient_id)

    return queue_rows


def render_patient_card(row: dict[str, Any], is_new: bool) -> None:
    band = str(row.get("Priority Band", "Low"))
    priority_text = f"{band} Priority | Severity {row.get('Severity', 'N/A')} | {row.get('Status', 'Waiting')}"

    with st.container(border=True):
        status_message = priority_text
        if is_new:
            status_message = f"New patient | {status_message}"

        if band == "High":
            st.error(status_message)
        elif band == "Medium":
            st.warning(status_message)
        else:
            st.success(status_message)

        name_col, score_col, wait_col, status_col = st.columns([0.43, 0.2, 0.2, 0.17])
        name_col.markdown(f"#### {row.get('Patient Name', 'Unknown Patient')}")
        name_col.caption(f"ID: {row.get('Patient ID', '')} | Age: {row.get('Age', 'N/A')}")
        score_col.metric("Priority Score", row.get("Priority Score", "N/A"))
        wait_col.metric("Estimated Wait", row.get("Estimated Wait Time", "N/A"))
        status_col.metric("Status", row.get("Status", "Waiting"))

        detail_col, doctor_col = st.columns([0.62, 0.38])
        detail_col.markdown(f"**Symptoms:** {row.get('Symptoms', '')}")
        doctor_col.markdown(f"**Assigned Doctor:** {row.get('Assigned Doctor', 'Unassigned')}")
        doctor_col.caption(row.get("Assignment Reason", "Assignment reason unavailable."))

        st.markdown("**Decision Summary**")
        st.info(row.get("Decision Summary", "No reasoning available."))

        with st.expander("View details", expanded=False):
            st.markdown("**Reasoning steps**")
            factors = row.get("Decision Factors") or ["No detailed factors returned by backend."]
            for factor in factors[:5]:
                st.write(f"- {factor}")
            if row.get("Scoring Logic"):
                st.caption(row["Scoring Logic"])


def render_triage_logic(queue_rows: list[dict[str, Any]]) -> None:
    st.subheader("Triage Logic")
    st.caption("A compact explanation of how priority and assignments are determined.")

    rule_col, detail_col = st.columns([0.42, 0.58], gap="large")
    with rule_col:
        st.info("Priority starts with severity, then increases for critical symptoms and age risk.")
        with st.expander("View scoring rules", expanded=False):
            st.markdown(
                """
                - Severity contributes the base score: `severity x 15`.
                - Critical symptom keywords add priority points.
                - Pediatric and elderly patients receive age risk modifiers.
                - Severity 4-5 cases are treated as urgent or emergency.
                - Doctor matching is based on symptom category and emergency status.
                """
            )
    with detail_col:
        if not queue_rows:
            st.info("Submit a patient to see patient-specific reasoning.")
            return

        patient_labels = [
            f"{row.get('Patient Name', 'Unknown')} ({row.get('Patient ID', '')})"
            for row in queue_rows
        ]
        selected_label = st.selectbox("Review patient reasoning", patient_labels)
        selected_index = patient_labels.index(selected_label)
        row = queue_rows[selected_index]

        st.markdown(f"**{row.get('Patient Name', 'Selected patient')}**")
        st.write(row.get("Decision Summary", "No reasoning available."))
        st.caption(row.get("Assignment Reason", "Assignment reason unavailable."))
        with st.expander("View patient reasoning details", expanded=False):
            st.markdown("**Reasoning steps**")
            for factor in row.get("Decision Factors") or ["No detailed factors returned by backend."]:
                st.write(f"- {factor}")
            if row.get("Scoring Logic"):
                st.caption(row["Scoring Logic"])


def render_main() -> None:
    initialize_state()
    inject_styles()
    base_url, show_raw_debug = render_sidebar()
    client = get_client(base_url)
    render_health(client)

    st.title("Hospital Triage System")
    st.markdown(
        "A staff-facing control panel for patient intake, queue visibility, "
        "emergency monitoring, and triage decision review."
    )

    render_system_insights(client)

    intake_col, alert_col = st.columns([0.48, 0.52], gap="large")
    with intake_col:
        render_intake_form(client, show_raw_debug)
    with alert_col:
        render_alerts(client)

    st.divider()
    queue_rows = render_queue_dashboard(client)
    st.divider()
    render_triage_logic(queue_rows)


def render_system_insights(client: TriageApiClient) -> None:
    """Backend integration: GET /system-insights powers this compact status panel."""

    result = client.get_system_insights()
    if not result.ok:
        st.warning("System insights unavailable.")
        st.caption(result.error)
        return

    insights = result.data or {}
    st.markdown("### System Overview")
    metric_col_1, metric_col_2, metric_col_3 = st.columns(3)
    metric_col_1.metric(
        "Doctors Available",
        f"{insights.get('doctors_available', 0)} / {insights.get('total_doctors', 0)}",
    )
    metric_col_2.metric("Active Emergencies", insights.get("active_emergencies", 0))
    metric_col_3.metric("Avg Wait", f"{insights.get('average_wait_minutes', 0)} min")
    metric_col_1.caption("Currently unassigned clinical teams")
    metric_col_2.caption("Severity 4-5 or escalated patients")
    metric_col_3.caption("Average estimated wait across the queue")
    st.divider()


def _combine_symptoms(selected_symptoms: list[str], free_text_symptoms: str) -> str:
    parts = [symptom.strip() for symptom in selected_symptoms if symptom.strip()]
    if free_text_symptoms.strip():
        parts.append(free_text_symptoms.strip())
    return "; ".join(parts)


def _last_submitted_patient_id() -> str:
    last_submission = st.session_state.get("last_submission")
    if isinstance(last_submission, dict):
        return str(last_submission.get("patient_id", ""))
    return ""


def _group_by_priority(queue_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {"High": [], "Medium": [], "Low": []}
    for row in queue_rows:
        band = str(row.get("Priority Band", "Low"))
        if band not in grouped:
            band = "Low"
        grouped[band].append(row)
    return grouped


def _dedupe_alerts(alerts: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for alert in alerts:
        message = str(alert.get("message", ""))
        if message in seen:
            continue
        seen.add(message)
        deduped.append(alert)
    return deduped


if __name__ == "__main__":
    render_main()
