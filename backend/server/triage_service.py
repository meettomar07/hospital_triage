"""App-facing triage service used by the Streamlit dashboard.

This module is intentionally separate from ``hospital_environment.py``. The
OpenEnv simulator remains unchanged, while these helpers provide a simpler
patient-intake API for the staff-facing frontend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class IntakeRequest(BaseModel):
    patient_name: str = Field(min_length=1, max_length=120)
    age: int = Field(ge=0, le=120)
    symptoms: str = Field(min_length=1, max_length=2_000)
    severity: int = Field(ge=1, le=5)


@dataclass
class TriageRecord:
    patient_id: str
    patient_name: str
    age: int
    symptoms: str
    severity: int
    priority_score: float
    assigned_doctor: str
    estimated_wait_time: str
    status: str
    triage_logic: dict[str, Any]
    assignment_reason: str
    created_at: str


@dataclass
class TriageService:
    records: list[TriageRecord] = field(default_factory=list)
    doctor_roster: tuple[str, ...] = ("Emergency Team", "Dr. Cardiology", "Dr. Trauma", "Dr. General")

    def intake(self, request: IntakeRequest) -> dict[str, Any]:
        priority_score, logic = self._calculate_priority(request)
        assigned_doctor = self._match_doctor(request.symptoms, request.severity)
        assignment_reason = self._assignment_reason(assigned_doctor, request.symptoms, request.severity)
        status = self._status_for(request.severity, priority_score)
        record = TriageRecord(
            patient_id=f"pt-{uuid4().hex[:8]}",
            patient_name=request.patient_name.strip(),
            age=request.age,
            symptoms=request.symptoms.strip(),
            severity=request.severity,
            priority_score=priority_score,
            assigned_doctor=assigned_doctor,
            estimated_wait_time=self._estimated_wait_time(request.severity, priority_score),
            status=status,
            triage_logic=logic,
            assignment_reason=assignment_reason,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.records.append(record)
        self._refresh_wait_times()
        return self._record_to_dict(record)

    def seed_demo_patients(self) -> dict[str, Any]:
        """Load a small, realistic demo queue for hackathon presentations."""

        demo_patients = [
            IntakeRequest(
                patient_name="Anika Sharma",
                age=42,
                symptoms="Chest pain and shortness of breath",
                severity=5,
            ),
            IntakeRequest(
                patient_name="Meet Tomar",
                age=18,
                symptoms="High fever, severe headache, abdominal pain for the last 5-6 days",
                severity=4,
            ),
            IntakeRequest(
                patient_name="Ravi Mehta",
                age=31,
                symptoms="Trauma injury with heavy bleeding after road accident",
                severity=5,
            ),
            IntakeRequest(
                patient_name="Sara Khan",
                age=27,
                symptoms="Mild cough and sore throat",
                severity=2,
            ),
        ]
        self.records.clear()
        created = [self.intake(patient) for patient in demo_patients]
        return {"created": len(created), "patients": created}

    def queue(self) -> list[dict[str, Any]]:
        sorted_records = sorted(
            self.records,
            key=lambda record: (-record.priority_score, record.created_at, record.patient_name.lower()),
        )
        return [self._record_to_dict(record) for record in sorted_records]

    def alerts(self) -> dict[str, Any]:
        alerts: list[dict[str, str]] = []
        escalated_count = 0
        for record in self.records:
            if record.severity >= 4 or record.status == "Escalated":
                escalated_count += 1
                level = "critical" if record.severity == 5 else "warning"
                alerts.append(
                    {
                        "level": level,
                        "message": (
                            f"{record.patient_name} requires urgent review "
                            f"(severity {record.severity}, priority {record.priority_score})."
                        ),
                    }
                )
        return {
            "system_escalation": escalated_count >= 3,
            "alerts": alerts,
            "recent_events": alerts[-5:],
        }

    def logic_for(self, patient_id: str) -> dict[str, Any] | None:
        for record in self.records:
            if record.patient_id == patient_id:
                return record.triage_logic
        return None

    def system_insights(self) -> dict[str, Any]:
        active_emergencies = len(
            [
                record
                for record in self.records
                if record.severity >= 4 or record.status == "Escalated"
            ]
        )
        wait_minutes = [self._wait_minutes(record.estimated_wait_time) for record in self.records]
        average_wait = round(sum(wait_minutes) / len(wait_minutes), 1) if wait_minutes else 0.0
        assigned_doctors = {record.assigned_doctor for record in self.records if record.status != "Completed"}
        return {
            "total_doctors": len(self.doctor_roster),
            "doctors_available": max(0, len(self.doctor_roster) - len(assigned_doctors)),
            "active_emergencies": active_emergencies,
            "average_wait_minutes": average_wait,
        }

    @staticmethod
    def _record_to_dict(record: TriageRecord) -> dict[str, Any]:
        return {
            "patient_id": record.patient_id,
            "patient_name": record.patient_name,
            "age": record.age,
            "symptoms": record.symptoms,
            "severity": record.severity,
            "priority_score": record.priority_score,
            "assigned_doctor": record.assigned_doctor,
            "assignment_reason": record.assignment_reason,
            "estimated_wait_time": record.estimated_wait_time,
            "status": record.status,
            "created_at": record.created_at,
            "triage_logic": record.triage_logic,
            "decision_summary": record.triage_logic.get("reasoning", "No reasoning available."),
            "emergency_status": record.severity >= 4 or record.status == "Escalated",
        }

    def _calculate_priority(self, request: IntakeRequest) -> tuple[float, dict[str, Any]]:
        symptoms = request.symptoms.lower()
        factors: list[str] = [f"Severity level {request.severity} contributes {request.severity * 15} points."]
        score = request.severity * 15

        keyword_rules = {
            "chest pain": 22,
            "breathing": 20,
            "shortness of breath": 20,
            "stroke": 24,
            "unconscious": 25,
            "bleeding": 18,
            "trauma": 16,
            "confusion": 12,
            "seizure": 22,
            "fever": 6,
        }
        for keyword, points in keyword_rules.items():
            if keyword in symptoms:
                score += points
                factors.append(f"Symptom keyword match: {keyword} -> +{points} priority points.")

        if request.age >= 70:
            score += 8
            factors.append("Age risk modifier: 70+ -> +8 priority points.")
        elif request.age <= 5:
            score += 6
            factors.append("Age risk modifier: pediatric patient -> +6 priority points.")

        priority_score = round(min(100.0, max(1.0, float(score))), 2)
        if priority_score >= 85:
            reasoning = "High-priority triage due to severity, emergency status, and/or critical symptom signals."
            factors.append("Emergency status: active high-priority review required.")
        elif priority_score >= 55:
            reasoning = "Moderate-priority triage based on reported severity, symptoms, and expected resource need."
            factors.append("Emergency status: monitor closely; escalate if symptoms worsen.")
        else:
            reasoning = "Routine triage priority based on currently reported information."
            factors.append("Emergency status: no immediate escalation signal detected.")
        return priority_score, {
            "reasoning": reasoning,
            "factors": factors,
            "severity_level": request.severity,
            "scoring_logic": "Base score = severity x 15, plus symptom keyword and age risk modifiers.",
        }

    @staticmethod
    def _match_doctor(symptoms: str, severity: int) -> str:
        text = symptoms.lower()
        if severity >= 5 or "unconscious" in text or "stroke" in text or "seizure" in text:
            return "Emergency Team"
        if "chest" in text or "cardiac" in text or "heart" in text:
            return "Dr. Cardiology"
        if "trauma" in text or "bleeding" in text or "fracture" in text or "injury" in text:
            return "Dr. Trauma"
        if "breathing" in text or "shortness of breath" in text or "wheezing" in text:
            return "Emergency Team"
        return "Dr. General"

    @staticmethod
    def _assignment_reason(assigned_doctor: str, symptoms: str, severity: int) -> str:
        text = symptoms.lower()
        if assigned_doctor == "Emergency Team":
            if severity >= 5:
                return "Assigned to Emergency Team because severity is emergency-level."
            if "shortness of breath" in text or "breathing" in text or "wheezing" in text:
                return "Assigned to Emergency Team due to breathing-related symptoms."
            return "Assigned to Emergency Team due to critical symptom indicators."
        if assigned_doctor == "Dr. Cardiology":
            return "Assigned to cardiology because symptoms suggest cardiac risk."
        if assigned_doctor == "Dr. Trauma":
            return "Assigned to trauma because symptoms include injury, trauma, fracture, or bleeding."
        return "Assigned to general care because no specialist-triggering symptom was detected."

    @staticmethod
    def _status_for(severity: int, priority_score: float) -> str:
        if severity >= 5 or priority_score >= 90:
            return "Escalated"
        if severity >= 4 or priority_score >= 70:
            return "Waiting"
        return "Waiting"

    @staticmethod
    def _estimated_wait_time(severity: int, priority_score: float) -> str:
        if severity >= 5 or priority_score >= 90:
            return "Immediate"
        if severity >= 4 or priority_score >= 70:
            return "5-10 min"
        if severity >= 3 or priority_score >= 45:
            return "15-25 min"
        return "30-45 min"

    def _refresh_wait_times(self) -> None:
        for record in self.records:
            record.estimated_wait_time = self._estimated_wait_time(record.severity, record.priority_score)

    @staticmethod
    def _wait_minutes(wait_time: str) -> float:
        if wait_time == "Immediate":
            return 0.0
        if "-" in wait_time:
            first, second = wait_time.replace("min", "").split("-", maxsplit=1)
            try:
                return (float(first.strip()) + float(second.strip())) / 2
            except ValueError:
                return 0.0
        return 0.0
