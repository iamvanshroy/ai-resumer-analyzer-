"""
analyzer.py
-----------
Core engine of the AI Resume Analyzer (pure Python, no heavy ML libraries).

Pipeline
  1. PDF  ->  text + profile photo     (pypdf, Pillow)
  2. text ->  tokens                   (regex + stop-words)
  3. TF-IDF + cosine similarity        (implemented from scratch)
  4. Skills / experience / education / profile links extraction
  5. Weighted score -> shortlist / recommendations / profile reminders
"""

from __future__ import annotations

import io
import math
import re
from collections import Counter
from dataclasses import dataclass, field, asdict

from pypdf import PdfReader

from skills_db import SKILLS, NON_TECH


# --------------------------------------------------------------------------- #
# 1. PDF extraction
# --------------------------------------------------------------------------- #
def extract_text_from_pdf(file_like) -> str:
    """Extract and clean text from a PDF (path or file-like object)."""
    reader = PdfReader(file_like)
    pages = [(page.extract_text() or "") for page in reader.pages]
    text = "\n".join(pages)
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_photo(file_like, size: int = 76) -> bytes:
    """
    Find a profile photo in the first two pages and return it as a round-cropped
    PNG (bytes). Returns b"" when the PDF has no photo (or Pillow is missing).
    """
    try:
        from PIL import Image, ImageDraw
        reader = PdfReader(file_like)
        for page in reader.pages[:2]:
            for img in page.images:
                im = img.image
                w, h = im.size
                if w < 40 or h < 40 or not (0.6 <= w / h <= 1.7):
                    continue                      # too small / not photo-shaped (logos, lines)
                side = min(w, h)
                im = im.convert("RGB").crop(((w - side) // 2, (h - side) // 2,
                                              (w + side) // 2, (h + side) // 2)).resize((size, size))
                mask = Image.new("L", (size * 4, size * 4), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
                mask = mask.resize((size, size), Image.LANCZOS)
                canvas = Image.new("RGB", (size, size), "white")
                canvas.paste(im, (0, 0), mask)
                out = io.BytesIO()
                canvas.save(out, format="PNG")
                return out.getvalue()
    except Exception:  # noqa: BLE001
        pass
    return b""


# --------------------------------------------------------------------------- #
# 2. Text helpers
# --------------------------------------------------------------------------- #
STOPWORDS = set("""
a an and are as at be been by for from has have in is it its of on or that the
to was were will with we you your our their this these those who whom which
about into over under per using use used work working experience years year
required requirements responsibilities candidate role job team looking strong
good knowledge ability skills skill etc also such including within across
""".split())


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z+#.\-]*", text.lower())
    out = []
    for t in tokens:
        t = t.strip(".-")
        if len(t) > 1 and t not in STOPWORDS:
            out.append(t)
    return out


def tf_idf_vectors(docs: list[list[str]]) -> list[dict[str, float]]:
    n = len(docs)
    df = Counter()
    for d in docs:
        df.update(set(d))
    idf = {t: math.log((1 + n) / (1 + c)) + 1 for t, c in df.items()}
    vectors = []
    for d in docs:
        counts = Counter(d)
        total = max(len(d), 1)
        vectors.append({t: (c / total) * idf[t] for t, c in counts.items()})
    return vectors


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


# --------------------------------------------------------------------------- #
# 3. Information extraction
# --------------------------------------------------------------------------- #
def _alias_pattern(alias: str) -> re.Pattern:
    return re.compile(r"(?<![A-Za-z0-9+#])" + re.escape(alias) + r"(?![A-Za-z0-9+#])", re.I)


_SKILL_PATTERNS = {skill: [_alias_pattern(a) for a in aliases] for skill, aliases in SKILLS.items()}


def find_skills(text: str) -> set[str]:
    found = set()
    for skill, patterns in _SKILL_PATTERNS.items():
        if any(p.search(text) for p in patterns):
            found.add(skill)
    return found


_NICE_HEAD = re.compile(r"nice to have|preferred|good to have|bonus|\bplus\b|desirable", re.I)
_REQ_HEAD = re.compile(r"required|requirements|must have|responsibilit|qualification", re.I)


def split_jd_skills(jd_text: str) -> tuple[list[str], list[str]]:
    """Split skills found in a JD into (required, nice_to_have) using headings."""
    required, nice = set(), set()
    in_nice = False
    for line in jd_text.splitlines():
        if _NICE_HEAD.search(line) and len(line) < 80:
            in_nice = True
        elif _REQ_HEAD.search(line) and len(line) < 80:
            in_nice = False
        (nice if in_nice else required).update(find_skills(line))
    nice -= required
    return sorted(required), sorted(nice)


def extract_min_experience(jd_text: str) -> int:
    m = re.search(r"(\d+)\s*\+?\s*(?:years?|yrs?)", jd_text, re.I)
    return int(m.group(1)) if m else 0


def extract_experience_years(text: str) -> float:
    """Explicit '4 years of experience' statements, else sum of date ranges in the Experience section."""
    explicit = [int(x) for x in re.findall(
        r"(\d+)\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)", text, re.I)]
    if explicit:
        return float(max(explicit))
    m = re.search(r"^\s*(?:work\s+)?experience\s*$(.*?)(?=^\s*(?:projects?|education|certifications?)\s*$|\Z)",
                  text, re.I | re.S | re.M)
    section = m.group(1) if m else ""
    total = 0.0
    for start, end in re.findall(r"((?:19|20)\d{2})\s*[-–to]+\s*((?:19|20)\d{2}|present|current)", section, re.I):
        end_year = 2026 if end.lower() in ("present", "current") else int(end)
        if end_year >= int(start):
            total += end_year - int(start)
    return min(total, 40.0)


def extract_education(text: str) -> str:
    levels = [
        ("PhD", r"ph\.?d|doctorate"),
        ("Master's", r"m\.?tech|m\.?sc|\bmca\b|\bmba\b|master"),
        ("Bachelor's", r"b\.?tech|b\.?e\b|b\.?sc|b\.?com|\bbca\b|\bbba\b|bachelor"),
        ("Diploma", r"diploma"),
    ]
    for label, pat in levels:
        if re.search(pat, text, re.I):
            return label
    return "Not detected"


def extract_name(text: str, fallback: str) -> str:
    for line in text.splitlines()[:6]:
        line = line.strip()
        if 2 <= len(line) <= 40 and "@" not in line and not re.search(r"\d", line):
            if 1 < len(line.split()) <= 4 and line.replace(" ", "").replace(".", "").isalpha():
                return line.title()
    return fallback


def extract_contact(text: str) -> tuple[str, str]:
    email = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    phone = re.search(r"(?:\+?\d{1,3}[\s-]?)?\d{10}|\d{3}[\s-]\d{3}[\s-]\d{4}", text)
    return (email.group(0) if email else ""), (phone.group(0) if phone else "")


def extract_links(text: str) -> tuple[str, str, str]:
    """Return (linkedin, github, portfolio) found in the resume text ('' when missing)."""
    no_mail = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", " ", text)
    li = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-%]+", no_mail, re.I)
    gh = re.search(r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+", no_mail, re.I)
    portfolio = ""
    pattern = (r"(?:https?://|www\.)[^\s,;|)]+"
               r"|\b[\w\-]+\.(?:github\.io|vercel\.app|netlify\.app|dev|io|me)\b(?:/[^\s,;|)]*)?")
    for m in re.finditer(pattern, no_mail, re.I):
        url = m.group(0).rstrip(".")
        low = url.lower()
        if "linkedin.com" in low or re.search(r"(?<![\w.])github\.com", low):
            continue
        portfolio = url
        break
    return (li.group(0) if li else ""), (gh.group(0) if gh else ""), portfolio


# --------------------------------------------------------------------------- #
# 4. Scoring
# --------------------------------------------------------------------------- #
@dataclass
class JobSpec:
    description: str
    required_skills: list[str]
    nice_skills: list[str] = field(default_factory=list)
    min_experience: int = 0


@dataclass
class Result:
    filename: str
    name: str
    email: str
    phone: str
    score: float
    status: str                      # "Shortlisted" / "Not shortlisted"
    tier: str                        # Excellent / Good / Average / Low
    required_matched: list[str]
    required_missing: list[str]
    nice_matched: list[str]
    nice_missing: list[str]
    similarity: float                # 0-100
    experience_years: float
    education: str
    word_count: int
    recommendations: list[str]
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""
    has_photo: bool = False
    reminders: list[str] = field(default_factory=list)
    photo_png: bytes = field(default=b"", repr=False)
    text: str = field(default="", repr=False)          # full resume text (used by the AI feedback)

    def to_row(self) -> dict:
        d = asdict(self)
        d.pop("photo_png", None)
        d.pop("text", None)
        for k in ("required_matched", "required_missing", "nice_matched", "nice_missing"):
            d[k] = ", ".join(d[k])
        for k in ("recommendations", "reminders"):
            d[k] = " | ".join(d[k])
        d["has_photo"] = "Yes" if d["has_photo"] else "No"
        return d


W_REQUIRED, W_NICE, W_SIM, W_EXP = 50, 15, 25, 10   # weights (sum = 100)


def profile_reminders(job: JobSpec, linkedin: str, github: str, portfolio: str, has_photo: bool) -> list[str]:
    """Reminders about profile links that were NOT detected in the resume."""
    out = []
    tech_role = any(s not in NON_TECH for s in job.required_skills) or not job.required_skills
    if not linkedin:
        out.append("LinkedIn link not found - add your LinkedIn profile URL in the header; recruiters check it first.")
    if tech_role and not github:
        out.append("GitHub link not found - add your GitHub profile so reviewers can see real code.")
    if not portfolio:
        out.append("Portfolio link not found - add a personal website or portfolio URL showing your best work.")
    if not has_photo:
        out.append("Profile photo not detected (optional) - add a clear, professional photo if the company's format allows it.")
    return out


def _recommendations(text, job, req_missing, nice_missing, exp_years, jd_vec, res_vec, email, phone):
    recs: list[str] = []
    for s in req_missing:
        recs.append(f"Add '{s}' to your Skills section and back it with a project or experience bullet that shows how you used it.")
    if nice_missing:
        recs.append("Bonus skills that would strengthen your profile: " + ", ".join(nice_missing[:5]) + ".")
    if job.min_experience and exp_years < job.min_experience:
        recs.append(f"The role asks for {job.min_experience}+ years of experience (detected ~{exp_years:g}). Highlight internships, freelance work and major projects with dates.")
    top_jd = sorted(jd_vec.items(), key=lambda kv: kv[1], reverse=True)
    missing_kw = [t for t, _ in top_jd if t not in res_vec and t not in {s.lower() for s in job.required_skills}][:6]
    if missing_kw:
        recs.append("Use more of the job description's keywords where truthful: " + ", ".join(missing_kw) + ".")
    sections = {
        "Summary/Objective": r"summary|objective|profile",
        "Projects": r"projects?",
        "Education": r"education|b\.?tech|degree",
        "Experience": r"experience|internship",
        "Certifications": r"certification|certified|course",
    }
    absent = [name for name, pat in sections.items() if not re.search(pat, text, re.I)]
    if absent:
        recs.append("Add missing section(s): " + ", ".join(absent) + ".")
    if len(re.findall(r"\d+\s*%|\$\s*\d+|\d+\s*(?:users|clients|projects|models)", text, re.I)) < 2:
        recs.append("Quantify achievements (e.g. 'improved accuracy by 12%', 'served 5,000 users').")
    if not email or not phone:
        recs.append("Add a clear email address and phone number in the header.")
    if len(text.split()) < 150:
        recs.append("Your resume is very short - add more detail about projects and responsibilities.")
    return recs


def tier_for(score: float) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 65:
        return "Good"
    if score >= 45:
        return "Average"
    return "Low"


def analyze_resumes(resumes: dict[str, str], job: JobSpec, threshold: float = 60.0,
                    photos: dict[str, bytes] | None = None) -> list[Result]:
    """
    resumes : {filename: extracted_text}
    photos  : optional {filename: png_bytes} from extract_photo()
    Returns results sorted by score (best first).
    """
    photos = photos or {}
    names = list(resumes.keys())
    token_docs = [tokenize(job.description)] + [tokenize(resumes[n]) for n in names]
    vectors = tf_idf_vectors(token_docs)
    jd_vec, res_vecs = vectors[0], vectors[1:]

    req = list(dict.fromkeys(job.required_skills))
    nice = list(dict.fromkeys(job.nice_skills))
    results: list[Result] = []

    for fname, rvec in zip(names, res_vecs):
        text = resumes[fname]
        have = find_skills(text)
        req_ok = [s for s in req if s in have]
        req_bad = [s for s in req if s not in have]
        nice_ok = [s for s in nice if s in have]
        nice_bad = [s for s in nice if s not in have]

        similarity = min(1.0, cosine(jd_vec, rvec) / 0.45)    # 0.45 cosine ~ "very close"
        req_ratio = len(req_ok) / len(req) if req else similarity
        nice_ratio = len(nice_ok) / len(nice) if nice else req_ratio
        exp_years = extract_experience_years(text)
        exp_ratio = min(1.0, exp_years / job.min_experience) if job.min_experience else 1.0

        score = 100 * (W_REQUIRED * req_ratio + W_NICE * nice_ratio + W_SIM * similarity + W_EXP * exp_ratio) \
            / (W_REQUIRED + W_NICE + W_SIM + W_EXP)
        score = round(score, 1)

        email, phone = extract_contact(text)
        linkedin, github, portfolio = extract_links(text)
        photo = photos.get(fname, b"")
        shortlisted = score >= threshold and (not req or req_ratio >= 0.5)
        recs = [] if shortlisted and not req_bad else _recommendations(
            text, job, req_bad, nice_bad, exp_years, jd_vec, rvec, email, phone)

        results.append(Result(
            filename=fname,
            name=extract_name(text, fname.rsplit(".", 1)[0]),
            email=email, phone=phone,
            score=score, status="Shortlisted" if shortlisted else "Not shortlisted", tier=tier_for(score),
            required_matched=req_ok, required_missing=req_bad,
            nice_matched=nice_ok, nice_missing=nice_bad,
            similarity=round(similarity * 100, 1),
            experience_years=exp_years, education=extract_education(text),
            word_count=len(text.split()), recommendations=recs,
            linkedin=linkedin, github=github, portfolio=portfolio,
            has_photo=bool(photo),
            reminders=profile_reminders(job, linkedin, github, portfolio, bool(photo)),
            photo_png=photo,
            text=text,
        ))

    results.sort(key=lambda r: r.score, reverse=True)
    return results
