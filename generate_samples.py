"""
generate_samples.py
-------------------
Creates test data:
  * sample_resumes/*.pdf  - 12 hand-written resumes with profile photos and
                            LinkedIn / GitHub / portfolio links (some deliberately missing)
  * sample_job_description.txt
  * --bulk N also creates N random resumes in sample_resumes/bulk/

Run:  python generate_samples.py            (12 resumes)
      python generate_samples.py --bulk 150 (12 + 150 resumes)
"""
import argparse
import io
import random
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path("sample_resumes")

JOB_DESCRIPTION = """Machine Learning Engineer - Python

About the role
We are looking for a Machine Learning Engineer to build and deploy prediction models
for our product. You will work with data scientists and backend engineers.

Requirements
- 2+ years of experience in a similar role
- Strong Python programming
- Hands-on Machine Learning with scikit-learn
- Data handling with Pandas and NumPy
- Good knowledge of SQL
- Version control with Git

Nice to have
- TensorFlow or PyTorch
- Docker
- AWS
- NLP
"""

RESUMES = [
    dict(name="Aarav Sharma", email="aarav.sharma@example.com", phone="9810011001",
         summary="Machine Learning Engineer with 4 years of experience building production ML models in Python.",
         skills="Python, SQL, Machine Learning, scikit-learn, Pandas, NumPy, TensorFlow, Docker, AWS, NLP, Git",
         experience=[("ML Engineer, FinTech Labs (2022 - Present)", ["Built a churn model with scikit-learn that improved retention by 14%.", "Deployed models using Docker on AWS serving 20000 users.", "Wrote SQL pipelines and Pandas feature engineering code."]),
                     ("Data Analyst, DataWorks (2020 - 2022)", ["Automated reports in Python and SQL saving 10 hours per week."])],
         projects=["Resume classifier using NLP and TensorFlow with 91% accuracy.", "Sales forecasting with NumPy and Pandas."],
         education="B.Tech Computer Science, Delhi University (2016 - 2020)", certs="AWS Cloud Practitioner, Deep Learning Specialization"),
    dict(name="Priya Mehta", email="priya.mehta@example.com", phone="9810022002",
         summary="Data scientist with 3 years of experience in Python and machine learning.",
         skills="Python, SQL, Machine Learning, scikit-learn, Pandas, NumPy, PyTorch, Git, Statistics",
         experience=[("Data Scientist, RetailIQ (2023 - Present)", ["Developed demand forecasting models with scikit-learn, reducing error by 18%.", "Maintained Git workflows for a team of 6."]),
                     ("ML Intern, AI Studio (2022 - 2023)", ["Trained PyTorch models for image tagging."])],
         projects=["Credit risk scoring with scikit-learn.", "Customer segmentation using Pandas and NumPy."],
         education="M.Sc Statistics, IIT Delhi", certs="Google Data Analytics Certificate"),
    dict(name="Divya Reddy", email="divya.reddy@example.com", phone="9810033003",
         summary="NLP engineer with 5 years of experience delivering language models.",
         skills="Python, NLP, spaCy, Transformers, Machine Learning, scikit-learn, Pandas, NumPy, SQL, Git, Docker, PyTorch",
         experience=[("NLP Engineer, TextAI (2021 - Present)", ["Fine-tuned BERT models improving F1 by 9%.", "Containerised services with Docker."]),
                     ("Software Engineer, CloudSoft (2019 - 2021)", ["Built Python APIs and SQL reports."])],
         projects=["Chatbot using transformers and NLP.", "Topic modelling on 100000 documents."],
         education="B.Tech Information Technology", certs="Hugging Face NLP course"),
    dict(name="Rohan Verma", email="rohan.verma@example.com", phone="9810044004",
         summary="Python developer with 2 years of experience moving into machine learning.",
         skills="Python, Pandas, NumPy, SQL, Git, Machine Learning, Matplotlib",
         experience=[("Python Developer, Webify (2024 - Present)", ["Built data cleaning scripts with Pandas and NumPy.", "Wrote SQL queries for dashboards."])],
         projects=["House price prediction with linear regression.", "Movie recommender using Pandas."],
         education="B.Tech Computer Science", certs="Machine Learning course on Coursera"),
    dict(name="Mohit Singh", email="mohit.singh@example.com", phone="9810055005",
         summary="Final-year student passionate about machine learning and Python.",
         skills="Python, Machine Learning, NumPy, Pandas, Git",
         experience=[("Intern, StartupHub (2025 - 2025)", ["Cleaned datasets using Pandas."])],
         projects=["Spam classifier using Python and Machine Learning.", "Digit recognition with NumPy."],
         education="B.Tech Computer Science (2022 - 2026)", certs=""),
    dict(name="Sneha Iyer", email="sneha.iyer@example.com", phone="9810066006",
         summary="Backend developer with 3 years of experience building web services in Python.",
         skills="Python, Django, Flask, REST API, SQL, Git, Docker",
         experience=[("Backend Developer, ShopEase (2023 - Present)", ["Built Django REST APIs serving 50000 users.", "Dockerised microservices."])],
         projects=["Inventory management system in Flask."],
         education="B.Tech Computer Science", certs="Docker Certified Associate"),
    dict(name="Vikram Rao", email="vikram.rao@example.com", phone="9810077007",
         summary="Data analyst with 3 years of experience in dashboards and reporting.",
         skills="SQL, Excel, Tableau, Power BI, Python, Pandas, Data Analysis",
         experience=[("Data Analyst, BizMetrics (2023 - Present)", ["Built Tableau dashboards used by 40 managers.", "Wrote complex SQL queries."])],
         projects=["Sales dashboard in Power BI."],
         education="B.Sc Statistics", certs="Tableau Desktop Specialist"),
    dict(name="Arjun Nair", email="arjun.nair@example.com", phone="9810088008",
         summary="DevOps engineer with 4 years of experience automating cloud infrastructure.",
         skills="Docker, Kubernetes, AWS, Linux, Git, CI/CD, Python, Jenkins",
         experience=[("DevOps Engineer, CloudNine (2022 - Present)", ["Cut deployment time by 60% using Jenkins and Kubernetes."])],
         projects=["Auto-scaling setup on AWS."],
         education="B.Tech Electronics", certs="AWS Solutions Architect Associate"),
    dict(name="Karan Malhotra", email="karan.m@example.com", phone="9810099009",
         summary="Java developer with 3 years of experience in enterprise applications.",
         skills="Java, Spring Boot, MySQL, Git, REST API, Agile",
         experience=[("Java Developer, BankTech (2023 - Present)", ["Developed Spring Boot services for payments."])],
         projects=["Library management system in Java."],
         education="B.Tech Computer Science", certs="Oracle Java SE"),
    dict(name="Ananya Gupta", email="ananya.gupta@example.com", phone="9810010010",
         summary="Frontend developer with 2 years of experience building responsive websites.",
         skills="HTML, CSS, JavaScript, React, Git, Figma",
         experience=[("Frontend Developer, PixelPerfect (2024 - Present)", ["Built React dashboards used by 5000 users."])],
         projects=["Portfolio website using React."],
         education="BCA", certs="Meta Front-End Developer Certificate"),
    dict(name="Neha Kapoor", email="neha.kapoor@example.com", phone="9810011011",
         summary="Accountant with 6 years of experience in bookkeeping and GST filing.",
         skills="Accounting, Tally, GST, Excel, Communication",
         experience=[("Senior Accountant, Kapoor & Co (2020 - Present)", ["Managed GST filing for 40 clients."])],
         projects=[], education="B.Com", certs="Tally Professional"),
    dict(name="Ishita Joshi", email="ishita.joshi@example.com", phone="9810012012",
         summary="Graphic designer with 4 years of experience in branding.",
         skills="Photoshop, Illustrator, Figma, Canva, Graphic Design, Communication",
         experience=[("Designer, Brandly (2022 - Present)", ["Designed identities for 25 clients."])],
         projects=["Rebranding of a local cafe chain."], education="Diploma in Design", certs=""),
]

# (linkedin, github, portfolio, photo) - some are missing on purpose so the reminders can be tested
PROFILE = {
    "Aarav Sharma": (1, 1, 1, 1), "Priya Mehta": (1, 1, 0, 1), "Divya Reddy": (1, 1, 1, 1),
    "Rohan Verma": (1, 0, 0, 1), "Mohit Singh": (0, 1, 0, 0), "Sneha Iyer": (1, 0, 1, 1),
    "Vikram Rao": (1, 0, 0, 0), "Arjun Nair": (1, 1, 0, 1), "Karan Malhotra": (0, 0, 0, 1),
    "Ananya Gupta": (1, 0, 1, 1), "Neha Kapoor": (0, 0, 0, 0), "Ishita Joshi": (1, 0, 1, 1),
}

# ---------- bulk generator -------------------------------------------------
FIRST = "Aditi Rahul Meera Sahil Tanvi Nikhil Pooja Yash Kriti Dev Simran Harsh Riya Amit Kavya Manav Naina Rishi Tara Zoya".split()
LAST = "Sharma Verma Gupta Singh Mehta Iyer Nair Rao Khan Joshi Kapoor Bansal Malik Chopra Reddy Das Patel Saxena".split()
PROFILES = {
    "ml": ["Python", "SQL", "Machine Learning", "scikit-learn", "Pandas", "NumPy", "Git", "TensorFlow", "Docker", "AWS", "NLP", "PyTorch"],
    "web": ["HTML", "CSS", "JavaScript", "React", "Node.js", "MongoDB", "Git", "REST API"],
    "backend": ["Java", "Spring Boot", "MySQL", "SQL", "Git", "REST API", "Docker"],
    "data": ["SQL", "Excel", "Tableau", "Power BI", "Python", "Pandas", "Data Analysis"],
    "devops": ["Docker", "Kubernetes", "AWS", "Linux", "CI/CD", "Git", "Python"],
}


def random_resume(rng: random.Random, i: int) -> dict:
    kind = rng.choices(list(PROFILES), weights=[4, 3, 3, 3, 2])[0]
    pool = PROFILES[kind]
    skills = rng.sample(pool, k=rng.randint(max(3, len(pool) // 2), len(pool)))
    years = rng.randint(0, 7)
    name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    start = 2026 - years
    exp = [(f"{kind.upper()} Engineer, Company{i} ({start} - Present)",
            [f"Worked with {', '.join(skills[:3])} and improved delivery by {rng.randint(5, 40)}%."])] if years else []
    return dict(
        name=name, email=f"{name.lower().replace(' ', '.')}{i}@example.com", phone=f"98{rng.randint(10000000, 99999999)}",
        summary=f"{kind} professional with {years} years of experience." if years else f"Fresher interested in {kind} roles.",
        skills=", ".join(skills), experience=exp,
        projects=[f"Mini project using {skills[0]} and {skills[-1]}."] if rng.random() > 0.3 else [],
        education=rng.choice(["B.Tech Computer Science", "BCA", "B.Sc IT", "M.Tech", "MCA"]),
        certs=rng.choice(["", "Coursera certification", "NPTEL course"]),
        flags=tuple(int(rng.random() < p) for p in (0.6, 0.4, 0.3, 0.6)))


# ---------- sample profile photo (generated avatar, not a real person) ----------
def avatar_png(seed: str) -> bytes:
    rng = random.Random(seed)
    s = 240
    im = Image.new("RGB", (s, s), rng.choice([(10, 102, 194), (55, 143, 233), (0, 65, 130), (11, 114, 133), (91, 110, 225)]))
    d = ImageDraw.Draw(im)
    d.ellipse([s * .12, s * .64, s * .88, s * 1.35], fill=rng.choice([(40, 50, 70), (250, 250, 250), (215, 228, 245)]))
    d.ellipse([s * .33, s * .20, s * .67, s * .62], fill=rng.choice([(241, 194, 150), (224, 172, 125), (198, 134, 94), (141, 85, 60)]))
    d.pieslice([s * .30, s * .15, s * .70, s * .52], 180, 360, fill=rng.choice([(30, 25, 25), (70, 45, 30), (20, 20, 30), (110, 80, 50)]))
    out = io.BytesIO()
    im.save(out, format="PNG")
    return out.getvalue()


# ---------- PDF rendering --------------------------------------------------
def build_pdf(data: dict, path: Path, flags=(1, 1, 1, 1)) -> None:
    li, gh, pf, photo = flags
    slug = data["name"].lower().replace(" ", "-")
    ss = getSampleStyleSheet()
    blue = colors.HexColor("#0A66C2")
    h_name = ParagraphStyle("n", parent=ss["Title"], fontSize=22, textColor=blue, alignment=0, spaceAfter=2)
    h_sec = ParagraphStyle("s", parent=ss["Heading3"], textColor=blue, spaceBefore=8, spaceAfter=2)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=10, leading=13)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm, title=data["name"], author=data["name"])

    links = []
    if li:
        links.append(f"LinkedIn: linkedin.com/in/{slug}")
    if gh:
        links.append(f"GitHub: github.com/{slug}")
    if pf:
        links.append(f"Portfolio: https://{slug.split('-')[0]}.dev")
    left = [Paragraph(data["name"], h_name), Paragraph(f'{data["email"]} | {data["phone"]}', body)]
    if links:
        left.append(Paragraph("<br/>".join(links), body))
    if photo:
        img = RLImage(io.BytesIO(avatar_png(data["name"])), width=28 * mm, height=28 * mm)
        head = Table([[left, img]], colWidths=[130 * mm, 30 * mm])
        head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                                  ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
        story = [head]
    else:
        story = left

    story += [HRFlowable(width="100%", color=blue, thickness=1.2, spaceBefore=4, spaceAfter=2),
              Paragraph("SUMMARY", h_sec), Paragraph(data["summary"], body),
              Paragraph("SKILLS", h_sec), Paragraph(data["skills"], body)]
    if data["experience"]:
        story.append(Paragraph("EXPERIENCE", h_sec))
        for title, bullets in data["experience"]:
            story.append(Paragraph(f"<b>{title}</b>", body))
            story += [Paragraph(f"- {b}", body) for b in bullets]
            story.append(Spacer(1, 3))
    if data["projects"]:
        story.append(Paragraph("PROJECTS", h_sec))
        story += [Paragraph(f"- {p}", body) for p in data["projects"]]
    story += [Paragraph("EDUCATION", h_sec), Paragraph(data["education"], body)]
    if data["certs"]:
        story += [Paragraph("CERTIFICATIONS", h_sec), Paragraph(data["certs"], body)]
    doc.build(story)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bulk", type=int, default=0, help="also create N random resumes")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    Path("sample_job_description.txt").write_text(JOB_DESCRIPTION, encoding="utf-8")
    for r in RESUMES:
        build_pdf(r, OUT / f'{r["name"].replace(" ", "_")}.pdf', PROFILE[r["name"]])
    print(f"Created {len(RESUMES)} sample resumes in ./{OUT}/ and sample_job_description.txt")

    if args.bulk:
        bulk = OUT / "bulk"
        bulk.mkdir(exist_ok=True)
        rng = random.Random(42)
        for i in range(1, args.bulk + 1):
            r = random_resume(rng, i)
            build_pdf(r, bulk / f"candidate_{i:03d}.pdf", r["flags"])
        print(f"Created {args.bulk} random resumes in ./{bulk}/")


if __name__ == "__main__":
    main()
