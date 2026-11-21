"""
ai_feedback.py
--------------
Optional AI feedback for one candidate, using the Groq API (https://console.groq.com).

* Uses only the Python standard library (urllib), so no extra pip install is needed.
* The API key is NEVER stored in the code. It is read from the environment variable GROQ_API_KEY,
  or from the file groq_key.txt, or typed by the user while the program runs (kept only in memory).
* The analyzer's own score/shortlist decision is not changed by the AI. The AI only
  writes written feedback for the recruiter or the candidate.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b"          # change here, or set the GROQ_MODEL variable
# If the model above is ever retired by Groq (error 404), these are tried next, in order.
FALLBACK_MODELS = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]


class AIFeedbackError(Exception):
    """Raised with a short, user-friendly message when the AI call fails."""

    def __init__(self, message: str, bad_key: bool = False):
        super().__init__(message)
        self.bad_key = bad_key


KEY_FILE = Path(__file__).resolve().parent / "groq_key.txt"     # paste your key inside this file
PLACEHOLDER = "PASTE_YOUR_GROQ_KEY_HERE"


def get_api_key() -> str:
    """Key from the GROQ_API_KEY variable, else from the first non-comment line of groq_key.txt."""
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key:
        return key
    try:
        for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and line != PLACEHOLDER:
                return line
    except OSError:
        pass
    return ""


def build_messages(job, r) -> list[dict]:
    """Build the chat messages: a system rule set and one user message with all facts."""
    system = (
        "You are a careful career coach and recruiter. Give honest, specific, helpful feedback on ONE resume "
        "for ONE job. Use only facts that appear in the resume text; never invent skills, jobs or numbers. "
        "Do not judge by name, gender, age or photo. Write plain text only (no markdown symbols such as ** or #). "
        "Use exactly these headings, each on its own line: VERDICT, STRENGTHS, GAPS, HOW TO IMPROVE, "
        "REWRITTEN SUMMARY, INTERVIEW QUESTIONS. Under STRENGTHS, GAPS and HOW TO IMPROVE give 3 to 5 short "
        "lines starting with '- '. REWRITTEN SUMMARY is 2 to 3 sentences the candidate could paste in the resume. "
        "INTERVIEW QUESTIONS has 3 questions starting with '- '."
    )
    facts = (
        f"JOB DESCRIPTION:\n{job.description[:3000]}\n\n"
        f"Required skills: {', '.join(job.required_skills) or '-'}\n"
        f"Nice-to-have skills: {', '.join(job.nice_skills) or '-'}\n"
        f"Minimum experience: {job.min_experience} years\n\n"
        "ANALYZER RESULT FOR THIS CANDIDATE:\n"
        f"Score: {r.score:g}% ({r.tier}), status: {r.status}\n"
        f"Required skills found: {', '.join(r.required_matched) or '-'}\n"
        f"Required skills missing: {', '.join(r.required_missing) or '-'}\n"
        f"Nice-to-have found: {', '.join(r.nice_matched) or '-'}\n"
        f"Experience detected: {r.experience_years:g} years; education: {r.education}\n\n"
        f"RESUME TEXT:\n{(getattr(r, 'text', '') or '')[:6000]}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": facts}]


def _post(payload: dict, api_key: str, timeout: int) -> dict:
    req = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ai-resume-analyzer/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _model_missing(e: urllib.error.HTTPError, detail: str) -> bool:
    return e.code == 404 or "does not exist" in detail or "decommissioned" in detail


def get_feedback(job, r, api_key: str, model: str | None = None, timeout: int = 60) -> str:
    """Return the AI feedback text for candidate `r`. Raises AIFeedbackError on any problem."""
    if not api_key:
        raise AIFeedbackError("No Groq API key was given.", bad_key=True)
    first = model or os.environ.get("GROQ_MODEL") or DEFAULT_MODEL
    models = [first] + [m for m in FALLBACK_MODELS if m != first]
    messages = build_messages(job, r)
    last_error = ""
    for m in models:
        payload = {"model": m, "messages": messages, "temperature": 0.3, "max_tokens": 2500}
        if m.startswith("openai/gpt-oss"):
            payload["reasoning_effort"] = "low"        # short thinking, so the answer is not cut off
        try:
            data = _post(payload, api_key, timeout)
            text = (data["choices"][0]["message"].get("content") or "").strip()
            if not text:
                raise AIFeedbackError("Groq returned an empty answer. Try again.")
            return text
        except urllib.error.HTTPError as e:
            try:
                detail = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
            except Exception:  # noqa: BLE001
                detail = ""
            if e.code in (401, 403):
                raise AIFeedbackError("Groq rejected the API key. Check the key and try again.", bad_key=True)
            if e.code == 429:
                raise AIFeedbackError("Groq rate limit reached. Wait a minute and try again.")
            if _model_missing(e, detail):
                last_error = f"model {m}: {detail or e.reason}"
                continue                                # try the next model
            raise AIFeedbackError(f"Groq error {e.code}: {detail or e.reason}")
        except urllib.error.URLError as e:
            raise AIFeedbackError(f"Could not reach Groq. Check your internet connection. ({e.reason})")
        except (KeyError, IndexError, ValueError):
            raise AIFeedbackError("Groq sent an answer in an unexpected format.")
        except TimeoutError:
            raise AIFeedbackError("Groq took too long to answer. Try again.")
    raise AIFeedbackError("No Groq model was available. Set GROQ_MODEL to a current model from "
                          "console.groq.com/docs/models. Last error: " + last_error)
