"""
console_app.py  -  AI Resume Analyzer (terminal version)
Advanced Programming Practice | Design by Vansh, Adiraj and Aditya
Run:  python console_app.py      (the window version is:  python gui_app.py)
"""
import csv
import os
import shutil
import sys
from pathlib import Path

from analyzer import (
    JobSpec, analyze_resumes, extract_min_experience, extract_photo, extract_text_from_pdf,
    split_jd_skills,
)
from skills_db import SKILLS

os.system("")
RESET, BOLD = "\033[0m", "\033[1m"
BLUE = "\033[38;5;32m"
WHITE_ON_BLUE = "\033[1;97;48;5;25m"
GREEN, RED, GREY = "\033[38;5;34m", "\033[38;5;160m", "\033[38;5;245m"
SAMPLE_JD = Path("sample_job_description.txt")


def width() -> int:
    return max(70, min(shutil.get_terminal_size((100, 20)).columns, 110))


def banner_line(text: str = "") -> str:
    return f"{WHITE_ON_BLUE}{text.center(width())}{RESET}"


def front_page() -> None:
    os.system("cls" if os.name == "nt" else "clear")
    for t in ("", "in  |  AI  RESUME  ANALYZER", "", "Advanced Programming Practice", "Design by Vansh, Adiraj and Aditya", ""):
        print(banner_line(t))
    print(f"{BLUE}{'-' * width()}{RESET}")


def bar(score: float, size: int = 20) -> str:
    filled = int(round(score / 100 * size))
    return f"{GREEN if score >= 60 else RED}{'█' * filled}{GREY}{'░' * (size - filled)}{RESET}"


def ask(prompt: str, default: str = "") -> str:
    try:
        return input(f"{BLUE}{prompt}{f' [{default}]' if default else ''}: {RESET}").strip() or default
    except EOFError:
        sys.exit(0)


def title(text: str) -> None:
    print(f"\n{BOLD}{BLUE}== {text} =={RESET}")


class State:
    jd_text, required, nice, min_exp = "", [], [], 0
    folder, threshold, results = Path("sample_resumes"), 60.0, []


S = State()


def show_criteria() -> None:
    title("Current criteria")
    print(f"Job description : {'loaded (' + str(len(S.jd_text.split())) + ' words)' if S.jd_text else 'NOT loaded'}")
    print(f"Required skills : {', '.join(S.required) or '-'}")
    print(f"Nice-to-have    : {', '.join(S.nice) or '-'}")
    print(f"Min experience  : {S.min_exp} years\nResume folder   : {S.folder}\nThreshold       : {S.threshold:g}%")


def load_jd() -> None:
    title("Job description")
    print("1) Use the sample job description\n2) Load from a .txt or .pdf file\n3) Type / paste it here")
    choice = ask("Choose", "1")
    if choice == "1":
        if not SAMPLE_JD.exists():
            print(f"{RED}Sample not found. Run: python generate_samples.py{RESET}")
            return
        S.jd_text = SAMPLE_JD.read_text(encoding="utf-8")
    elif choice == "2":
        path = Path(ask("File path").strip('"'))
        if not path.exists():
            print(f"{RED}File not found.{RESET}")
            return
        S.jd_text = extract_text_from_pdf(str(path)) if path.suffix.lower() == ".pdf" else path.read_text(encoding="utf-8", errors="ignore")
    else:
        print("Paste the job description. Type END on a new line when finished:")
        lines = []
        while (line := input()).strip().upper() != "END":
            lines.append(line)
        S.jd_text = "\n".join(lines)
    S.required, S.nice = split_jd_skills(S.jd_text)
    S.min_exp = extract_min_experience(S.jd_text)
    print(f"{GREEN}Job description loaded. Skills detected automatically.{RESET}")
    show_criteria()


def edit_criteria() -> None:
    show_criteria()
    print(f"\n{GREY}Type skill names separated by commas. Press Enter to keep the current value.{RESET}")
    lookup = {k.lower(): k for k in SKILLS}

    def parse(text, current):
        if not text:
            return current
        out = []
        for item in text.split(","):
            key = item.strip().lower()
            if key in lookup:
                out.append(lookup[key])
            elif key:
                print(f"{RED}  Unknown skill ignored: {item.strip()}{RESET}")
        return out

    S.required = parse(ask("Required skills"), S.required)
    S.nice = parse(ask("Nice-to-have skills"), S.nice)
    exp = ask("Minimum years of experience", str(S.min_exp))
    S.min_exp = int(exp) if exp.isdigit() else S.min_exp
    try:
        S.threshold = min(90.0, max(30.0, float(ask("Shortlist threshold % (30-90)", f"{S.threshold:g}"))))
    except ValueError:
        pass
    S.folder = Path(ask("Resume folder (PDF files, subfolders included)", str(S.folder)).strip('"'))


def analyze() -> None:
    if not S.jd_text:
        print(f"{RED}Load a job description first (option 1).{RESET}")
        return
    files = sorted(S.folder.rglob("*.pdf")) if S.folder.exists() else []
    if not files:
        print(f"{RED}No PDF files found in '{S.folder}'. Use option 2 or run generate_samples.py.{RESET}")
        return
    texts, photos, failed = {}, {}, []
    for i, f in enumerate(files, 1):
        print(f"\r{BLUE}Reading PDFs... {i}/{len(files)}{RESET}", end="", flush=True)
        try:
            t = extract_text_from_pdf(str(f))
            if len(t.split()) < 20:
                raise ValueError("no readable text (scanned image?)")
            texts[f.name] = t
            photos[f.name] = extract_photo(str(f))
        except Exception as e:  # noqa: BLE001
            failed.append((f.name, str(e)))
    print()
    S.results = analyze_resumes(texts, JobSpec(S.jd_text, S.required, S.nice, S.min_exp), S.threshold, photos)
    show_summary(failed)


def show_summary(failed=()) -> None:
    short = [r for r in S.results if r.status == "Shortlisted"]
    rest = [r for r in S.results if r.status != "Shortlisted"]
    title("Summary")
    print(f"Analysed: {len(S.results)}   {GREEN}Shortlisted: {len(short)}{RESET}   {RED}Not shortlisted: {len(rest)}{RESET}   "
          f"Average match: {sum(r.score for r in S.results) / len(S.results):.0f}%")
    for name, err in failed:
        print(f"{RED}Could not read {name}: {err}{RESET}")

    def table(rows, heading, limit=15):
        title(f"{heading} (showing {min(limit, len(rows))} of {len(rows)})")
        print(f"{BOLD}{'#':<4}{'Candidate':<20}{'Score':>7}  {'':<20} {'Exp':>4}  {'LI GH PF':<9} Missing required{RESET}")
        for i, r in enumerate(rows[:limit], 1):
            links = " ".join("✓ " if v else "✗ " for v in (r.linkedin, r.github, r.portfolio))
            print(f"{i:<4}{r.name[:19]:<20}{r.score:>6.1f}%  {bar(r.score)} {r.experience_years:>3g}y  {links:<9} {(', '.join(r.required_missing) or '-')[:34]}")

    table(short, "SHORTLISTED CANDIDATES")
    table(rest, "NOT SHORTLISTED")
    print(f"\n{GREY}Option 4 shows full details, recommendations and profile reminders for a candidate.{RESET}")


def candidate_details() -> None:
    if not S.results:
        print(f"{RED}Run the analysis first (option 3).{RESET}")
        return
    query = ask("Candidate name (or part of it)").lower()
    for r in [r for r in S.results if query and query in r.name.lower()][:3]:
        title(r.name)
        print(f"File       : {r.filename}\nContact    : {r.email} {r.phone}")
        print(f"Score      : {r.score:g}%  {bar(r.score)}  ({r.tier})")
        print(f"Status     : {(GREEN if r.status == 'Shortlisted' else RED)}{r.status}{RESET}")
        print(f"Experience : {r.experience_years:g} years   Education: {r.education}")
        print(f"Matched    : {GREEN}{', '.join(r.required_matched) or '-'}{RESET}")
        print(f"Missing    : {RED}{', '.join(r.required_missing) or '-'}{RESET}")
        print(f"LinkedIn   : {r.linkedin or 'not found'}\nGitHub     : {r.github or 'not found'}\n"
              f"Portfolio  : {r.portfolio or 'not found'}\nPhoto      : {'detected' if r.has_photo else 'not found'}")
        if r.reminders:
            print(f"\n{BOLD}Profile reminders:{RESET}")
            for tip in r.reminders:
                print(f"  ! {tip}")
        if r.recommendations:
            print(f"\n{BOLD}{BLUE}Recommendations - add these to your resume:{RESET}")
            for i, tip in enumerate(r.recommendations, 1):
                print(f"  {i}. {tip}")
    else:
        if not query:
            return


def ai_feedback_cmd() -> None:
    """Option 8: AI written feedback for one candidate (Groq API)."""
    import getpass
    import ai_feedback
    if not S.results:
        print(f"{RED}Run the analysis first (option 3).{RESET}")
        return
    query = ask("Candidate name (or part of it)").lower()
    matches = [r for r in S.results if query and query in r.name.lower()][:1]
    if not matches:
        print(f"{RED}No candidate found.{RESET}")
        return
    key = ai_feedback.get_api_key() or getpass.getpass("Groq API key (hidden): ").strip()
    r = matches[0]
    print(f"{BLUE}Asking Groq about {r.name}... please wait.{RESET}")
    try:
        text = ai_feedback.get_feedback(JobSpec(S.jd_text, S.required, S.nice, S.min_exp), r, key)
    except ai_feedback.AIFeedbackError as e:
        print(f"{RED}{e}{RESET}")
        return
    title(f"AI FEEDBACK - {r.name}")
    print(text)


def export_csv() -> None:
    if not S.results:
        print(f"{RED}Run the analysis first (option 3).{RESET}")
        return
    for name, rows in (("shortlisted_candidates.csv", [r for r in S.results if r.status == "Shortlisted"]),
                       ("all_candidates.csv", S.results)):
        with open(name, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(S.results[0].to_row().keys()))
            w.writeheader()
            w.writerows(r.to_row() for r in rows)
        print(f"{GREEN}Saved {name} ({len(rows)} rows){RESET}")


def make_samples() -> None:
    n = ask("How many extra random resumes to create (0 for none)", "100")
    os.system(f'"{sys.executable}" generate_samples.py --bulk {int(n) if n.isdigit() else 0}')


def main() -> None:
    front_page()
    ask("Press Enter to start")
    actions = {"1": load_jd, "2": edit_criteria, "3": analyze, "4": candidate_details,
               "5": export_csv, "6": make_samples, "7": show_criteria, "8": ai_feedback_cmd}
    while True:
        title("MAIN MENU")
        print("1) Load job description\n2) Edit criteria\n3) Analyze resumes & shortlist\n"
              "4) Candidate details + recommendations\n5) Export results to CSV\n"
              "6) Generate sample / test resumes\n7) Show current criteria\n8) AI feedback for a candidate (Groq)\n0) Exit")
        choice = ask("Select option")
        if choice == "0":
            print(f"{BLUE}Thank you for using AI Resume Analyzer.{RESET}")
            break
        actions.get(choice, lambda: print(f"{RED}Invalid option.{RESET}"))()


if __name__ == "__main__":
    main()
