import os
import json
from pydantic import BaseModel, Field
from typing import List, Optional, Literal

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class MailClassificationSchema(BaseModel):
    category: Literal["staff", "notice", "placements", "competition", "others"]
    ai_summary: str
    extracted_deadline: str
    is_urgent: bool


class DraftedMailSchema(BaseModel):
    subject_line: str
    email_body: str


class EssentialNoteSchema(BaseModel):
    ai_structured_action: str
    tag: Literal["STUDY", "EXAM", "LAB", "DEADLINE", "IDEA"]


class LineAgentResponseSchema(BaseModel):
    reply: str
    should_create_widget: bool
    widget_title: Optional[str] = Field(default="")
    widget_type: Optional[Literal["STUDY_PLAN", "COUNTDOWN", "FORMULA_CARD", "PROGRESS_TRACKER"]] = Field(default="STUDY_PLAN")
    accent_red: bool = Field(default=False)
    widget_items: List[str] = Field(default_factory=list)


def _get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if GENAI_AVAILABLE and api_key and api_key != "api_key = os.getenv("GEMINI_API_KEY", "")":
        return genai.Client(api_key=api_key)
    return None


def classify_student_mail(sender: str, subject: str, body: str) -> dict:
    client = _get_client()
    if client:
        try:
            prompt = (
                f"Classify this student email into exactly one category: "
                f"'staff', 'notice', 'placements', 'competition', or 'others'.\n"
                f"Sender: {sender}\nSubject: {subject}\nBody: {body[:1200]}"
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=MailClassificationSchema,
                    temperature=0.1,
                ),
            )
            return json.loads(response.text)
        except Exception:
            pass

    text = f"{sender} {subject} {body}".lower()
    if any(k in text for k in ["placement", "hiring", "internship", "drive", "ctc", "resume", "recruiter"]):
        cat, urgent = "placements", True
    elif any(k in text for k in ["hackathon", "competition", "coding contest", "symposium", "ideathon"]):
        cat, urgent = "competition", True
    elif any(k in text for k in ["circular", "notice", "exam schedule", "holiday", "fee", "timetable"]):
        cat, urgent = "notice", False
    elif any(k in text for k in ["prof", "sir", "madam", "assignment", "lab", "lecture", "syllabus", "dr."]):
        cat, urgent = "staff", False
    else:
        cat, urgent = "others", False

    return {
        "category": cat,
        "ai_summary": f"{subject[:68]}..." if len(subject) > 68 else subject,
        "extracted_deadline": "Check mail details" if urgent else "",
        "is_urgent": urgent,
    }


def draft_tutor_email(student_profile, subject_obj, intent: str, user_notes: str = "") -> dict:
    student_name = student_profile.user.get_full_name() or student_profile.user.username
    roll_no = student_profile.roll_no
    dept = student_profile.department
    sem = student_profile.semester
    tutor_name = subject_obj.tutor.name if subject_obj and subject_obj.tutor else "Professor"
    subj_label = f"{subject_obj.code} - {subject_obj.name}" if subject_obj else "Academic Matter"

    client = _get_client()
    if client:
        try:
            prompt = (
                f"Draft a concise, formal college email from a student to their tutor.\n"
                f"Student Name: {student_name}\nRoll No: {roll_no}\nDepartment: {dept} (Sem {sem})\n"
                f"Tutor Name: {tutor_name}\nSubject: {subj_label}\n"
                f"Intent: {intent}\nAdditional Context/Notes: {user_notes}\n"
                f"Include student name, roll number, and subject code cleanly."
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DraftedMailSchema,
                    temperature=0.3,
                ),
            )
            return json.loads(response.text)
        except Exception:
            pass

    templates = {
        "leave": (
            f"Leave Request - {roll_no} ({subj_label})",
            f"Respected {tutor_name},\n\nI am {student_name} (Roll No: {roll_no}, {dept}, Semester {sem}). "
            f"I kindly request leave for {subj_label} due to {user_notes or 'personal/medical reasons'}.\n\n"
            f"I will ensure all missed lecture notes and lab work are completed promptly.\n\n"
            f"Thank you,\n{student_name}\nRoll No: {roll_no}"
        ),
        "document": (
            f"Document Submission - {roll_no} ({subj_label})",
            f"Respected {tutor_name},\n\nPlease find attached the requested academic document for {subj_label}. "
            f"{user_notes}\n\nRegards,\n{student_name}\nRoll No: {roll_no} | {dept}"
        ),
        "homework": (
            f"Homework / Assignment Submission - {roll_no} ({subj_label})",
            f"Respected {tutor_name},\n\nI have completed and attached my homework submission for {subj_label}. "
            f"{user_notes}\n\nKindly acknowledge receipt.\n\nSincerely,\n{student_name}\nRoll No: {roll_no}"
        ),
    }
    subj_line, body = templates.get(
        intent,
        (
            f"Regarding {subj_label} - {student_name} ({roll_no})",
            f"Respected {tutor_name},\n\n{user_notes}\n\nRegards,\n{student_name}\nRoll No: {roll_no} | {dept}"
        )
    )
    return {"subject_line": subj_line, "email_body": body}


def process_essential_key_capture(raw_input: str) -> dict:
    client = _get_client()
    if client:
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"Convert this quick note captured via Nothing Essential Key into a crisp action item and tag: {raw_input}",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=EssentialNoteSchema,
                    temperature=0.2,
                ),
            )
            return json.loads(response.text)
        except Exception:
            pass

    lower = raw_input.lower()
    if "exam" in lower or "cia" in lower or "quiz" in lower:
        tag = "EXAM"
    elif "lab" in lower or "code" in lower:
        tag = "LAB"
    elif "due" in lower or "submit" in lower or "deadline" in lower or "notice" in lower:
        tag = "DEADLINE"
    else:
        tag = "STUDY"

    return {
        "ai_structured_action": f"Action: {raw_input.strip()[:120]}",
        "tag": tag,
    }


def run_line_study_agent(student_profile, user_message: str, academic_context: str) -> dict:
    client = _get_client()
    if client:
        try:
            system_prompt = (
                "You are LINE, the AI Co-Pilot inside a Nothing OS Student Management System. "
                "Be crisp, tactical, and helpful. You have live context of the user's academic telemetry. "
                "If a student asks for a study plan, exam countdown, revision cheat-sheet, or task tracker "
                "(or uses words like 'pin', 'widget', 'plan', 'schedule', 'track', 'create'), set should_create_widget=True "
                "and populate widget_title, widget_type, and 3-5 actionable widget_items."
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"Context:\n{academic_context}\n\nQuery: {user_message}",
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=LineAgentResponseSchema,
                    temperature=0.4,
                ),
            )
            return json.loads(response.text)
        except Exception:
            pass

    wants_widget = (student_profile is not None) and any(
        w in user_message.lower()
        for w in ["widget", "plan", "schedule", "roadmap", "track", "pin", "revision", "create"]
    )
    return {
        "reply": (
            f"LINE AI Online. Telemetry analyzed ({academic_context[:115]}...). "
            f"Prioritize low-attendance alerts (<75%), pending homework submissions, and upcoming CIA assessments."
            + (" I have generated and pinned a new dynamic widget onto your Overall Dashboard." if wants_widget else "")
        ),
        "should_create_widget": wants_widget,
        "widget_title": "LINE TACTICAL SPRINT WIDGET" if wants_widget else "",
        "widget_type": "STUDY_PLAN",
        "accent_red": True,
        "widget_items": [
            "Block 1 (45m): Review core lecture concepts & CIA question bank",
            "Block 2 (30m): Complete pending lab / homework deliverable",
            "Block 3 (15m): Active recall self-check before wrap-up",
        ] if wants_widget else [],
    }


def get_ai_engine_status() -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    is_live = bool(GENAI_AVAILABLE and api_key and api_key != "your_gemini_api_key_here")
    return {
        "is_live": is_live,
        "label": "GEMINI 2.5 LIVE" if is_live else "OFFLINE ENGINE (ADD API KEY)",
        "model": "gemini-2.5-flash" if is_live else "deterministic-fallback",
    }
