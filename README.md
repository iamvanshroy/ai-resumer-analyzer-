# AI Resume Analyzer
Advanced Programming Practice - Design by Vansh, Adiraj and Aditya

Pure Python. Upload PDF resumes + a job description -> candidates are ranked and shortlisted,
the rest get recommendations. Profile photo, LinkedIn, GitHub and portfolio links are
detected automatically from each PDF, and missing ones show up as reminders.

## Run in VS Code (open the folder that contains gui_app.py first!)
    pip install pypdf reportlab pillow
    python generate_samples.py --bulk 150
    python gui_app.py          <- desktop window (LinkedIn blue & white)
    python console_app.py      <- terminal version

Tkinter (used by gui_app.py) is included with the normal Python installer from python.org.

## Files
gui_app.py          Desktop window - main version
console_app.py      Terminal version
analyzer.py         PDF text/photo extraction, TF-IDF, skills, links, scoring, recommendations, reminders
skills_db.py        Skills dictionary with aliases
generate_samples.py Sample PDFs (with photos and links) + sample job description (+ --bulk N random resumes)

## Score (0-100)
50% required skills + 15% nice-to-have + 25% TF-IDF similarity + 10% experience.
Shortlisted = score >= threshold AND at least half of the required skills present.

## AI Feedback (Groq) - optional

Each candidate card has an **AI Feedback (Groq)** button (console: menu option 8). It sends the job
description, the analyzer result and the resume text to the Groq API and shows written feedback:
verdict, strengths, gaps, how to improve, a rewritten summary and interview questions.

1. Create a free API key at https://console.groq.com (API Keys). It starts with `gsk_`.
2. Give the key to the program in ONE of three ways:
   - open `groq_key.txt`, replace `PASTE_YOUR_GROQ_KEY_HERE` with your key, and save (easiest)
   - Windows PowerShell, before starting the program: `$env:GROQ_API_KEY="gsk_your_key"` then `python gui_app.py`
   - or just click the button and paste the key in the box that appears (kept only while the program is open).
3. No extra pip install is needed. An internet connection is required for this feature only.

Notes: never put the key inside the code or share it. The AI does not change the score or the shortlist
decision. To use another model set `GROQ_MODEL` (default `openai/gpt-oss-120b`; the old llama-3.3-70b-versatile was retired by Groq).

## Recruiter login (new)
The app now opens on a **recruiter sign-in page**. Create an account (name, company, email, password) or use
**"Try the demo recruiter account"** (demo@recruiter.com / Demo@123). Accounts are saved in `recruiters.json`
on this computer only; passwords are stored as salted PBKDF2-SHA256 hashes (see `auth.py`), never as plain text.
