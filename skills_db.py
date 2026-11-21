"""
skills_db.py
------------
Skills dictionary used by the analyzer.
Key   = canonical skill name (what the recruiter sees)
Value = list of aliases that may appear in a resume / job description
"""

SKILLS = {
    # Programming languages
    "Python": ["python", "python3"],
    "Java": ["java"],
    "JavaScript": ["javascript", "js", "es6"],
    "TypeScript": ["typescript"],
    "C++": ["c++"],
    "C#": ["c#"],
    "Go": ["golang"],
    "PHP": ["php"],
    "Kotlin": ["kotlin"],
    "Swift": ["swift"],
    "SQL": ["sql", "mysql", "postgresql", "postgres", "sqlite", "oracle sql"],
    "MongoDB": ["mongodb", "mongo"],
    # Web
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "React": ["react", "reactjs", "react.js"],
    "Angular": ["angular"],
    "Node.js": ["node.js", "nodejs", "node"],
    "Django": ["django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Spring Boot": ["spring boot", "spring"],
    "REST API": ["rest api", "rest apis", "restful", "rest"],
    # Data / ML
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning", "neural networks", "neural network"],
    "NLP": ["nlp", "natural language processing"],
    "Computer Vision": ["computer vision", "opencv"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "TensorFlow": ["tensorflow", "keras"],
    "PyTorch": ["pytorch"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Data Analysis": ["data analysis", "data analytics", "eda"],
    "Data Visualization": ["data visualization", "matplotlib", "seaborn", "plotly"],
    "Tableau": ["tableau"],
    "Power BI": ["power bi", "powerbi"],
    "Excel": ["excel", "ms excel", "microsoft excel"],
    "Statistics": ["statistics", "statistical analysis"],
    "Transformers": ["transformers", "hugging face", "huggingface", "bert"],
    "spaCy": ["spacy"],
    # DevOps / Cloud
    "Git": ["git", "github", "gitlab"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "GCP": ["gcp", "google cloud"],
    "Linux": ["linux", "unix", "bash"],
    "CI/CD": ["ci/cd", "jenkins", "github actions"],
    # CS fundamentals
    "Data Structures": ["data structures", "dsa"],
    "Algorithms": ["algorithms"],
    "OOP": ["oop", "object oriented", "object-oriented"],
    "Agile": ["agile", "scrum"],
    # Non-tech (so resumes of other fields are recognised too)
    "Accounting": ["accounting", "tally", "gst", "bookkeeping"],
    "Graphic Design": ["photoshop", "illustrator", "figma", "graphic design", "canva"],
    "Communication": ["communication", "presentation skills"],
}

NON_TECH = {"Accounting", "Graphic Design", "Communication"}
