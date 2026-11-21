"""
gui_app.py  -  AI Resume Analyzer  (desktop window, Tkinter - built into Python)
Advanced Programming Practice | Design by Vansh, Adiraj and Aditya

Run:  python gui_app.py
"""
import base64
import csv
import ctypes
import hashlib
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter import font as tkfont

from analyzer import (
    JobSpec, analyze_resumes, extract_min_experience, extract_photo, extract_text_from_pdf,
    split_jd_skills,
)
import ai_feedback
import auth
from skills_db import SKILLS

# ---------------------------------------------------------------------------
# Paths (always relative to this file, so it works from any folder)
# ---------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent
os.chdir(BASE)
SAMPLE_DIR = BASE / "sample_resumes"
SAMPLE_JD = BASE / "sample_job_description.txt"

# ---------------------------------------------------------------------------
# Theme: LinkedIn blue & white
# ---------------------------------------------------------------------------
BLUE, DARK, LIGHT = "#0A66C2", "#004182", "#E7F3FF"
BG, WHITE, TEXT, GREY, BORDER = "#F3F2EF", "#FFFFFF", "#1D2226", "#666666", "#E0DFDC"
GREEN, GREEN_BG, RED, RED_BG = "#137333", "#E6F4EA", "#B3261E", "#FDEAEA"
FONT = os.environ.get("APP_FONT") or ("Segoe UI" if sys.platform.startswith("win") else "Helvetica Neue" if sys.platform == "darwin" else "DejaVu Sans")

SCALE = 1.0


def px(n: float) -> int:
    """Scale a pixel size for high-DPI screens."""
    return int(n * SCALE)


# ---------------------------------------------------------------------------
# Small reusable widgets
# ---------------------------------------------------------------------------
def card(parent, **kw):
    return tk.Frame(parent, bg=WHITE, highlightthickness=1, highlightbackground=BORDER, **kw)


class RoundButton(tk.Canvas):
    """Pill-shaped button with hover effect. style = 'primary' or 'outline'."""

    def __init__(self, parent, text, command=None, style="primary", width=180, height=40,
                 parent_bg=BG, size=11):
        super().__init__(parent, width=px(width), height=px(height), bg=parent_bg,
                         highlightthickness=0, cursor="hand2")
        self.text, self.command, self.style = text, command, style
        self.w, self.h, self.size = px(width), px(height), size
        self._draw(False)
        self.bind("<Enter>", lambda e: self._draw(True))
        self.bind("<Leave>", lambda e: self._draw(False))
        self.bind("<Button-1>", lambda e: self.command() if self.command else None)

    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r,
               x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2,
               x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1]
        return self.create_polygon(pts, smooth=True, **kw)

    def _draw(self, hover):
        self.delete("all")
        if self.style == "primary":
            fill, outline, fg = (DARK if hover else BLUE), (DARK if hover else BLUE), WHITE
        elif self.style == "white":
            fill, outline, fg = (LIGHT if hover else WHITE), WHITE, DARK
        elif self.style == "ghost":
            fill, outline, fg = ("#1C74CB" if hover else "", WHITE, WHITE)
        else:
            fill, outline, fg = (LIGHT if hover else WHITE), BLUE, BLUE
        self._round_rect(1, 1, self.w - 1, self.h - 1, self.h // 2, fill=fill, outline=outline, width=2)
        self.create_text(self.w // 2, self.h // 2, text=self.text, fill=fg,
                         font=(FONT, self.size, "bold"))


class ScrollFrame(tk.Frame):
    """A vertically scrollable frame. Put widgets in .inner"""

    def __init__(self, parent, bg=BG):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.vsb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))


def install_mouse_wheel(root):
    """One global handler: scrolls whichever ScrollFrame is under the mouse."""
    def handler(event):
        try:
            w = root.winfo_containing(event.x_root, event.y_root)
        except Exception:  # noqa: BLE001
            return
        if isinstance(w, (tk.Text, tk.Listbox, ttk.Treeview)):
            return  # these scroll themselves
        while w is not None:
            if isinstance(w, ScrollFrame):
                num = getattr(event, "num", 0)
                if num == 4:
                    step = -1
                elif num == 5:
                    step = 1
                else:
                    step = -1 if event.delta > 0 else 1
                w.canvas.yview_scroll(step * 2, "units")
                return
            w = w.master
    root.bind_all("<MouseWheel>", handler)
    root.bind_all("<Button-4>", handler)
    root.bind_all("<Button-5>", handler)


class BlueSlider(tk.Canvas):
    def __init__(self, parent, lo=30, hi=90, value=60, step=5, width=280, command=None, bg=WHITE):
        super().__init__(parent, width=px(width), height=px(30), bg=bg, highlightthickness=0, cursor="hand2")
        self.lo, self.hi, self.step, self.value, self.command = lo, hi, step, value, command
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Button-1>", self._set)
        self.bind("<B1-Motion>", self._set)

    def draw(self):
        self.delete("all")
        w, h, pad = self.winfo_width(), self.winfo_height(), px(12)
        y = h // 2
        x = pad + (w - 2 * pad) * (self.value - self.lo) / (self.hi - self.lo)
        self.create_line(pad, y, w - pad, y, fill="#CFE2F5", width=px(6), capstyle="round")
        self.create_line(pad, y, x, y, fill=BLUE, width=px(6), capstyle="round")
        r = px(9)
        self.create_oval(x - r, y - r, x + r, y + r, fill=WHITE, outline=BLUE, width=px(3))

    def _set(self, e):
        pad, w = px(12), self.winfo_width()
        t = min(1.0, max(0.0, (e.x - pad) / max(w - 2 * pad, 1)))
        v = int(round((self.lo + t * (self.hi - self.lo)) / self.step) * self.step)
        self.value = min(self.hi, max(self.lo, v))
        self.draw()
        if self.command:
            self.command(self.value)


class ScoreBar(tk.Canvas):
    def __init__(self, parent, score, good):
        super().__init__(parent, height=px(10), bg=WHITE, highlightthickness=0)
        self.score, self.good = score, good
        self.bind("<Configure>", self.draw)

    def draw(self, e=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        self.create_rectangle(0, 0, w, h, fill="#E8EDF2", outline="")
        self.create_rectangle(0, 0, w * self.score / 100, h, fill=BLUE if self.good else "#E06666", outline="")


class Hero(tk.Canvas):
    """Blue gradient banner for the front page."""

    def __init__(self, parent, height=320):
        super().__init__(parent, height=px(height), highlightthickness=0, bg=BLUE)
        self.bind("<Configure>", self.redraw)

    def redraw(self, e=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        c1, c2 = (10, 102, 194), (0, 48, 105)
        for i in range(h):
            t = i / max(h - 1, 1)
            col = "#%02x%02x%02x" % tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3))
            self.create_line(0, i, w, i, fill=col)
        # decorative rings
        for r, dx, dy in ((int(h * 0.9), 0.08, 0.1), (int(h * 0.6), 0.93, 0.95), (int(h * 0.35), 0.82, 0.12)):
            cx, cy = int(w * dx), int(h * dy)
            self.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#2F7FCB", width=2)
        cx = w // 2
        # "in" logo badge
        s = int(h * 0.11)
        y0 = int(h * 0.12)
        self.create_rectangle(cx - s, y0, cx + s, y0 + 2 * s, fill=WHITE, outline="")
        self.create_text(cx, y0 + s, text="in", fill=BLUE, font=(FONT, int(s * 0.55), "bold"))
        self.create_text(cx, int(h * 0.42), text="AI Resume Analyzer", fill=WHITE, font=(FONT, 36, "bold"))
        self.create_text(cx, int(h * 0.58), text="Shortlist the right candidates from hundreds of resumes in seconds",
                         fill="#D6E8FA", font=(FONT, 13))
        # chips
        f = tkfont.Font(family=FONT, size=10, weight="bold")
        chips = ["Advanced Programming Practice", "Python", "TF-IDF Matching", "PDF Parsing"]
        pad, gap = px(16), px(10)
        widths = [f.measure(c) + 2 * pad for c in chips]
        x = cx - (sum(widths) + gap * (len(chips) - 1)) // 2
        cy, ch = int(h * 0.73), px(15)
        for c, cw in zip(chips, widths):
            self.create_rectangle(x, cy - ch, x + cw, cy + ch, fill="#1C74CB", outline="#7DB3E8")
            self.create_text(x + cw // 2, cy, text=c, fill=WHITE, font=f)
            x += cw + gap
        self.create_text(cx, int(h * 0.90), text="Design by  Vansh,  Adiraj  and  Aditya", fill=WHITE,
                         font=(FONT, 14, "bold"))


# ---------------------------------------------------------------------------
# Drawing helpers for the login page and the new front page
# ---------------------------------------------------------------------------
def rrect(cv, x1, y1, x2, y2, r, **kw):
    """Rounded rectangle on a canvas."""
    r = max(1, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
    pts = [x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y1 + r,
           x2, y2 - r, x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2,
           x1, y2, x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


def mix(c1, c2, t):
    """Blend two (r, g, b) colours -> hex string."""
    return "#%02x%02x%02x" % tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3))


def gradient(cv, w, h, c1, c2, diagonal=True):
    """Fill the canvas with a smooth gradient (drawn as thin strips)."""
    steps = 90
    for i in range(steps):
        t = i / (steps - 1)
        col = mix(c1, c2, t)
        if diagonal:                       # top-left -> bottom-right look using horizontal strips
            y1, y2 = int(h * i / steps), int(h * (i + 1) / steps) + 1
            cv.create_rectangle(0, y1, w, y2, fill=col, outline="")
        else:
            x1, x2 = int(w * i / steps), int(w * (i + 1) / steps) + 1
            cv.create_rectangle(x1, 0, x2, h, fill=col, outline="")


def rings(cv, w, h, col="#2F7FCB"):
    for r, dx, dy in ((int(h * 0.85), 0.05, 0.05), (int(h * 0.55), 0.95, 0.98), (int(h * 0.30), 0.78, 0.08),
                      (int(h * 0.18), 0.30, 0.92)):
        cx, cy = int(w * dx), int(h * dy)
        cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=col, width=2)


def mini_candidate(cv, x, y, w, name, role, score, colour):
    """A small floating candidate card (decoration) with shadow, avatar, name, role and score bar."""
    h = px(74)
    rrect(cv, x + 4, y + 6, x + w + 4, y + h + 6, px(12), fill="#002A57", outline="")      # soft shadow
    rrect(cv, x, y, x + w, y + h, px(12), fill=WHITE, outline="")
    d = px(40)
    cv.create_oval(x + px(14), y + (h - d) // 2, x + px(14) + d, y + (h - d) // 2 + d, fill=colour, outline="")
    cv.create_text(x + px(14) + d // 2, y + h // 2, text="".join(p[0] for p in name.split()[:2]),
                   fill=WHITE, font=(FONT, 11, "bold"))
    tx = x + px(14) + d + px(12)
    cv.create_text(tx, y + px(20), text=name, anchor="w", fill=TEXT, font=(FONT, 11, "bold"))
    cv.create_text(tx, y + px(38), text=role, anchor="w", fill=GREY, font=(FONT, 9))
    bx2 = x + w - px(64)
    cv.create_rectangle(tx, y + px(54), bx2, y + px(60), fill="#E8EDF2", outline="")
    cv.create_rectangle(tx, y + px(54), tx + (bx2 - tx) * score / 100, y + px(60), fill=BLUE, outline="")
    cv.create_text(x + w - px(16), y + h // 2, text=f"{score}%", anchor="e", fill=GREEN, font=(FONT, 13, "bold"))


def logo_badge(cv, x, y, size, bg=WHITE, fg=BLUE):
    cv.create_rectangle(x, y, x + size, y + size, fill=bg, outline="")
    cv.create_text(x + size // 2, y + size // 2, text="in", fill=fg, font=(FONT, int(size * 0.5), "bold"))


class LoginArt(tk.Canvas):
    """Left half of the login page: blue gradient with a short pitch and floating candidate cards."""

    def __init__(self, parent):
        super().__init__(parent, highlightthickness=0, bg=DARK)
        self.bind("<Configure>", self.redraw)

    def redraw(self, e=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50:
            return
        gradient(self, w, h, (0, 52, 108), (10, 102, 194))
        rings(self, w, h)
        m = px(54)
        logo_badge(self, m, px(46), px(40))
        self.create_text(m + px(52), px(66), text="AI Resume Analyzer", anchor="w", fill=WHITE, font=(FONT, 16, "bold"))
        self.create_text(m, int(h * 0.27), text="Hire the right people,\nin a fraction of the time.", anchor="nw",
                         fill=WHITE, font=(FONT, 28, "bold"))
        self.create_text(m, int(h * 0.27) + px(100), anchor="nw", fill="#D6E8FA", font=(FONT, 12),
                         text="Sign in to rank hundreds of PDF resumes against\nyour job description and shortlist instantly.")
        cw = min(px(360), w - 2 * m)
        top = int(h * 0.27) + px(170)
        for i, (nm, role, sc, col) in enumerate((("Aarav Sharma", "Machine Learning Engineer", 95, "#0A66C2"),
                                                 ("Priya Mehta", "Data Scientist", 81, "#0B7285"),
                                                 ("Rohan Verma", "Python Developer", 72, "#5B6EE1"))):
            if top + i * px(86) + px(80) < h - px(50):
                mini_candidate(self, m + (i % 2) * px(34), top + i * px(86), cw, nm, role, sc, col)
        self.create_text(m, h - px(30), text="Design by  Vansh,  Adiraj  and  Aditya", anchor="w", fill="#D6E8FA",
                         font=(FONT, 10, "bold"))


class LoginPage(tk.Frame):
    """Recruiter sign-in / create-account page."""

    def __init__(self, parent, on_success):
        super().__init__(parent, bg=BG)
        self.on_success = on_success
        self.mode = "login"
        self.grid_columnconfigure(0, weight=11, uniform="lp")
        self.grid_columnconfigure(1, weight=9, uniform="lp")
        self.grid_rowconfigure(0, weight=1)
        LoginArt(self).grid(row=0, column=0, sticky="nsew")
        right = tk.Frame(self, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        box = tk.Frame(right, bg=WHITE, highlightthickness=1, highlightbackground=BORDER)
        box.place(relx=0.5, rely=0.5, anchor="center")
        body = tk.Frame(box, bg=WHITE)
        body.pack(padx=px(40), pady=px(30))

        self.title_lbl = tk.Label(body, text="", bg=WHITE, fg=TEXT, font=(FONT, 22, "bold"))
        self.title_lbl.pack(anchor="w")
        self.sub_lbl = tk.Label(body, text="", bg=WHITE, fg=GREY, font=(FONT, 10))
        self.sub_lbl.pack(anchor="w", pady=(2, 12))

        self.vars = {k: tk.StringVar() for k in ("name", "company", "email", "password", "confirm")}
        self.rows = {}
        self.entries = {}
        spec = (("name", "Full name", False), ("company", "Company", False), ("email", "Work email", False),
                ("password", "Password", True), ("confirm", "Confirm password", True))
        for key, label, secret in spec:
            row = tk.Frame(body, bg=WHITE)
            tk.Label(row, text=label, bg=WHITE, fg=TEXT, font=(FONT, 9, "bold")).pack(anchor="w")
            ent = tk.Entry(row, textvariable=self.vars[key], font=(FONT, 11), relief="flat", bd=0, width=34,
                           highlightthickness=1, highlightbackground="#BFC5CC", highlightcolor=BLUE,
                           bg=WHITE, fg=TEXT, insertbackground=TEXT, show="•" if secret else "")
            ent.pack(fill="x", ipady=px(6), pady=(3, 0))
            ent.bind("<Return>", lambda e: self.submit())
            self.rows[key], self.entries[key] = row, ent
        self.show_pw = tk.BooleanVar(value=False)
        self.show_chk = tk.Checkbutton(body, text="Show password", variable=self.show_pw, command=self._toggle_pw,
                                       bg=WHITE, activebackground=WHITE, fg=GREY, font=(FONT, 9), bd=0,
                                       highlightthickness=0, selectcolor=WHITE, cursor="hand2")
        self.err = tk.Label(body, text="", bg=WHITE, fg=RED, font=(FONT, 9, "bold"), wraplength=px(340), justify="left")
        self.btn_holder = tk.Frame(body, bg=WHITE)
        self.btn = RoundButton(self.btn_holder, "", self.submit, width=340, height=44, parent_bg=WHITE, size=11)
        self.btn.pack()
        self.switch = tk.Label(body, text="", bg=WHITE, fg=BLUE, font=(FONT, 10, "bold"), cursor="hand2")
        self.switch.bind("<Button-1>", lambda e: self.set_mode("register" if self.mode == "login" else "login"))
        self.demo = tk.Label(body, text="Try the demo recruiter account", bg=WHITE, fg=GREY,
                             font=(FONT, 9, "underline"), cursor="hand2")
        self.demo.bind("<Button-1>", lambda e: self.demo_login())
        self.note = tk.Label(body, text="Accounts are stored on this computer only.\nPasswords are saved as salted hashes, never as text.",
                             bg=WHITE, fg="#8A949E", font=(FONT, 8), justify="left")
        self.set_mode("login")

    def _toggle_pw(self):
        ch = "" if self.show_pw.get() else "•"
        for k in ("password", "confirm"):
            self.entries[k].configure(show=ch)

    def set_mode(self, mode):
        self.mode = mode
        for w in list(self.rows.values()) + [self.show_chk, self.err, self.btn_holder, self.switch, self.demo, self.note]:
            w.pack_forget()
        keys = ("email", "password") if mode == "login" else ("name", "company", "email", "password", "confirm")
        for k in keys:
            self.rows[k].pack(fill="x", pady=(0, 10))
        self.show_chk.pack(anchor="w")
        self.err.pack(anchor="w", pady=(4, 0))
        self.btn_holder.pack(pady=(6, 10))
        self.switch.pack()
        if mode == "login":
            self.demo.pack(pady=(8, 0))
        self.note.pack(anchor="w", pady=(14, 0))
        if mode == "login":
            self.title_lbl.configure(text="Recruiter sign in")
            self.sub_lbl.configure(text="Welcome back - sign in to start shortlisting.")
            self.btn.text = "Sign in"
            self.switch.configure(text="New here?  Create a recruiter account")
        else:
            self.title_lbl.configure(text="Create your account")
            self.sub_lbl.configure(text="For recruiters and hiring managers.")
            self.btn.text = "Create account"
            self.switch.configure(text="Already registered?  Sign in")
        self.btn._draw(False)
        self.err.configure(text="")
        self.entries[keys[0]].focus_set()

    def submit(self):
        v = {k: x.get() for k, x in self.vars.items()}
        try:
            if self.mode == "login":
                user = auth.login(v["email"], v["password"])
            else:
                if v["password"] != v["confirm"]:
                    raise auth.AuthError("The two passwords do not match.")
                user = auth.register(v["name"], v["company"], v["email"], v["password"])
        except auth.AuthError as e:
            self.err.configure(text=str(e))
            return
        except OSError as e:
            self.err.configure(text=f"Could not read/write the accounts file: {e}")
            return
        self.reset()
        self.on_success(user)

    def demo_login(self):
        try:
            user = auth.ensure_demo()
        except (auth.AuthError, OSError) as e:
            self.err.configure(text=str(e))
            return
        self.reset()
        self.on_success(user)

    def reset(self):
        for x in self.vars.values():
            x.set("")
        self.show_pw.set(False)
        self._toggle_pw()
        self.set_mode("login")


class Hero2(tk.Canvas):
    """Front-page banner: headline + buttons on the left, floating candidate cards on the right."""

    def __init__(self, parent, on_start, on_demo, height=400):
        super().__init__(parent, height=px(height), highlightthickness=0, bg=DARK)
        self.on_start, self.on_demo = on_start, on_demo
        self.user = None
        self.bind("<Configure>", self.redraw)

    def set_user(self, user):
        self.user = user
        self.redraw()

    def redraw(self, e=None):
        self.delete("all")
        for ch in self.winfo_children():
            ch.destroy()
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50:
            return
        gradient(self, w, h, (0, 50, 105), (10, 102, 194), diagonal=False)
        rings(self, w, h)
        m = max(px(48), int(w * 0.05))
        first = (self.user["name"].split()[0] if self.user else "").strip()
        tag = f"Welcome, {first}" if first else "For recruiters"
        f = tkfont.Font(family=FONT, size=10, weight="bold")
        tw = f.measure(tag) + px(28)
        rrect(self, m, px(40), m + tw, px(70), px(15), fill="#1C74CB", outline="#7DB3E8")
        self.create_text(m + tw // 2, px(55), text=tag, fill=WHITE, font=f)
        self.create_text(m, px(92), anchor="nw", fill=WHITE, font=(FONT, 34, "bold"),
                         text="Shortlist the right\ncandidates in seconds.")
        self.create_text(m, px(92) + px(112), anchor="nw", fill="#D6E8FA", font=(FONT, 12),
                         text="Upload PDF resumes, paste a job description and get a ranked,\nexplainable shortlist - with feedback for every rejected candidate.")
        by = px(92) + px(190)
        bw = RoundButton(self, "Start analyzing  →", self.on_start, style="white", width=200, height=46,
                         parent_bg=mix((0, 50, 105), (10, 102, 194), (m + 100) / w), size=11)
        self.create_window(m, by, window=bw, anchor="nw")
        bg2 = RoundButton(self, "Try with demo data", self.on_demo, style="ghost", width=190, height=46,
                          parent_bg=mix((0, 50, 105), (10, 102, 194), (m + 300) / w), size=11)
        self.create_window(m + px(214), by, window=bg2, anchor="nw")
        chips = ["Python", "TF-IDF", "PDF parsing", "Groq AI feedback"]
        x = m
        for c in chips:
            cw = f.measure(c) + px(24)
            rrect(self, x, h - px(52), x + cw, h - px(26), px(13), fill="#1C74CB", outline="#5E9FDB")
            self.create_text(x + cw // 2, h - px(39), text=c, fill=WHITE, font=f)
            x += cw + px(8)
        # floating candidate cards on the right
        cw = min(px(380), int(w * 0.36))
        if w > px(900):
            x0 = w - cw - max(px(48), int(w * 0.06))
            y0 = px(48)
            for i, (nm, role, sc, col) in enumerate((("Aarav Sharma", "Machine Learning Engineer", 95, "#0A66C2"),
                                                     ("Priya Mehta", "Data Scientist", 81, "#0B7285"),
                                                     ("Rohan Verma", "Python Developer", 72, "#5B6EE1"))):
                mini_candidate(self, x0 + (px(-26) if i == 1 else px(18) if i == 2 else 0), y0 + i * px(96), cw, nm, role, sc, col)
            rrect(self, x0 + px(70), y0 + 3 * px(96) + px(8), x0 + px(70) + px(210), y0 + 3 * px(96) + px(36), px(14),
                  fill=GREEN_BG, outline="")
            self.create_text(x0 + px(70) + px(105), y0 + 3 * px(96) + px(22), text="✓  3 candidates shortlisted",
                             fill=GREEN, font=(FONT, 9, "bold"))


def step_card(parent, num, title, desc):
    c = card(parent)
    top = tk.Frame(c, bg=WHITE)
    top.pack(fill="x", padx=18, pady=(18, 4))
    badge = tk.Canvas(top, width=px(38), height=px(38), bg=WHITE, highlightthickness=0)
    badge.create_oval(2, 2, px(36), px(36), fill=BLUE, outline="")
    badge.create_text(px(19), px(19), text=str(num), fill=WHITE, font=(FONT, 13, "bold"))
    badge.pack(side="left")
    tk.Label(top, text=title, bg=WHITE, fg=TEXT, font=(FONT, 12, "bold")).pack(side="left", padx=10)
    tk.Label(c, text=desc, bg=WHITE, fg=GREY, font=(FONT, 10), justify="left", wraplength=px(260)).pack(
        anchor="w", padx=18, pady=(0, 18))
    return c


def pill(parent, text, kind="ok"):
    colours = {"ok": (LIGHT, DARK), "bad": (RED_BG, RED), "neutral": ("#EEF3F8", "#44546A")}
    bg, fg = colours[kind]
    return tk.Label(parent, text=text, bg=bg, fg=fg, font=(FONT, 9, "bold"), padx=9, pady=2)


def pill_row(parent, label, items, kind):
    row = tk.Frame(parent, bg=WHITE)
    row.pack(fill="x", pady=2, anchor="w")
    tk.Label(row, text=label, bg=WHITE, fg=GREY, font=(FONT, 9), width=22, anchor="w").pack(side="left")
    if not items:
        pill(row, "none", "neutral").pack(side="left", padx=2)
    for it in items:
        pill(row, it, kind).pack(side="left", padx=2)


AVATAR_COLOURS = ["#0A66C2", "#378FE9", "#004182", "#1C74CB", "#0B7285", "#5B6EE1"]


def make_avatar(parent, name, photo=b"", size=72, bg=WHITE):
    """Round profile picture: the photo found in the PDF, otherwise a coloured initials badge."""
    if photo:
        try:
            img = tk.PhotoImage(data=base64.b64encode(photo))
            cv = tk.Canvas(parent, width=img.width() + 4, height=img.height() + 4, bg=bg, highlightthickness=0)
            cv.image = img                                   # keep a reference
            cv.create_image(2, 2, image=img, anchor="nw")
            cv.create_oval(1, 1, img.width() + 2, img.height() + 2, outline=BLUE, width=2)
            return cv
        except tk.TclError:
            pass
    d = px(size)
    cv = tk.Canvas(parent, width=d, height=d, bg=bg, highlightthickness=0)
    col = AVATAR_COLOURS[int(hashlib.md5(name.encode()).hexdigest(), 16) % len(AVATAR_COLOURS)]
    cv.create_oval(2, 2, d - 2, d - 2, fill=col, outline="")
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
    cv.create_text(d // 2, d // 2, text=initials, fill=WHITE, font=(FONT, int(d * 0.30), "bold"))
    return cv


def link_chips(parent, r, bg=WHITE):
    row = tk.Frame(parent, bg=bg)
    for label, val in (("LinkedIn", r.linkedin), ("GitHub", r.github), ("Portfolio", r.portfolio),
                       ("Photo", r.has_photo)):
        tk.Label(row, text=("\u2713 " if val else "\u2717 ") + label, bg=GREEN_BG if val else RED_BG,
                 fg=GREEN if val else RED, font=(FONT, 9, "bold"), padx=9, pady=2).pack(side="left", padx=(0, 6))
    return row


def styled_entry(parent, var, width=40):
    return tk.Entry(parent, textvariable=var, font=(FONT, 10), relief="flat", bd=0, width=width,
                    highlightthickness=1, highlightbackground=BORDER, highlightcolor=BLUE, bg=WHITE, fg=TEXT)


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        global SCALE
        SCALE = max(1.0, self.winfo_fpixels("1i") / 96)

        self.title("AI Resume Analyzer  -  Advanced Programming Practice")
        self.configure(bg=BG)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(px(1180), sw - 60), min(px(760), sh - 90)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max((sh - h) // 2 - 20, 0)}")
        self.minsize(min(px(980), sw - 60), min(px(620), sh - 90))

        self.resume_paths: list[Path] = []
        self.results = []
        self.failed = []
        self.job = None
        self.threshold = 60
        self.running = False
        self.q: queue.Queue = queue.Queue()
        self.groq_key = ai_feedback.get_api_key()      # kept only in memory
        self.req_var, self.nice_var = tk.StringVar(), tk.StringVar()
        self.exp_var = tk.IntVar(value=0)

        self._setup_styles()
        self._build_navbar()
        self.container = tk.Frame(self, bg=BG)
        self.container.pack(fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        self.pages = {}
        self.user = None
        self.pages["login"] = LoginPage(self.container, self._signed_in)
        self.pages["login"].grid(row=0, column=0, sticky="nsew")
        for name, builder in (("home", self._build_home), ("setup", self._build_setup),
                              ("results", self._build_results)):
            page = builder(self.container)
            page.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = page
        install_mouse_wheel(self)
        self.show_page("login")

    # ------------------------------------------------------------------ styles
    def _setup_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Blue.Horizontal.TProgressbar", troughcolor="#D8E6F4", background=BLUE,
                    bordercolor=BORDER, lightcolor=BLUE, darkcolor=BLUE, thickness=px(10))
        s.configure("Treeview", rowheight=px(28), font=(FONT, 10), background=WHITE, fieldbackground=WHITE,
                    bordercolor=BORDER, foreground=TEXT)
        s.configure("Treeview.Heading", background=BLUE, foreground=WHITE, font=(FONT, 10, "bold"),
                    relief="flat", padding=(6, 6))
        s.map("Treeview.Heading", background=[("active", DARK)])
        s.map("Treeview", background=[("selected", LIGHT)], foreground=[("selected", TEXT)])
        s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
        s.configure("TNotebook.Tab", padding=(20, 9), font=(FONT, 10, "bold"), background="#E4E9EE",
                    foreground=GREY, borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", WHITE)], foreground=[("selected", BLUE)])
        s.configure("Vertical.TScrollbar", background="#C9D6E3", troughcolor=BG, bordercolor=BG,
                    arrowcolor=DARK)

    # ------------------------------------------------------------------ navbar
    def _build_navbar(self):
        bar = tk.Frame(self, bg=WHITE)
        self.bar = bar                                  # shown only after the recruiter signs in
        inner = tk.Frame(bar, bg=WHITE)
        inner.pack(fill="x", padx=24, pady=8)
        logo = tk.Canvas(inner, width=px(34), height=px(34), bg=WHITE, highlightthickness=0)
        logo.create_rectangle(0, 0, px(34), px(34), fill=BLUE, outline="")
        logo.create_text(px(17), px(17), text="in", fill=WHITE, font=(FONT, 15, "bold"))
        logo.pack(side="left")
        tk.Label(inner, text="AI Resume Analyzer", bg=WHITE, fg=BLUE, font=(FONT, 15, "bold")).pack(side="left", padx=10)

        out = tk.Label(inner, text="Sign out", bg=WHITE, fg=BLUE, font=(FONT, 10, "bold"), cursor="hand2",
                       padx=10, pady=3, highlightthickness=1, highlightbackground=BLUE)
        out.pack(side="right")
        out.bind("<Button-1>", lambda e: self.logout())
        self.user_lbl = tk.Label(inner, text="", bg=WHITE, fg=TEXT, font=(FONT, 9, "bold"), justify="right", padx=10)
        self.user_lbl.pack(side="right")
        self.user_av = tk.Canvas(inner, width=px(30), height=px(30), bg=WHITE, highlightthickness=0)
        self.user_av.pack(side="right")
        tk.Frame(inner, bg=BORDER, width=1, height=px(26)).pack(side="right", padx=10)

        self.nav = {}
        for key, label in (("results", "Results"), ("setup", "Analyze"), ("home", "Home")):
            lab = tk.Label(inner, text=label, bg=WHITE, fg=GREY, font=(FONT, 10, "bold"), cursor="hand2", padx=12)
            lab.pack(side="right")
            lab.bind("<Button-1>", lambda e, k=key: self._nav_click(k))
            self.nav[key] = lab
        tk.Frame(bar, bg=BORDER, height=1).pack(fill="x")

    def _nav_click(self, key):
        if key == "results" and not self.results:
            messagebox.showinfo("Results", "Run an analysis first - results will appear here.")
            return
        self.show_page(key)

    def _signed_in(self, user):
        self.user = user
        self.user_lbl.configure(text=f"{user['name']}\n{user['company']}")
        self.user_av.delete("all")
        self.user_av.create_oval(1, 1, px(29), px(29), fill=BLUE, outline="")
        self.user_av.create_text(px(15), px(15), text="".join(w[0] for w in user["name"].split()[:2]).upper(),
                                 fill=WHITE, font=(FONT, 9, "bold"))
        self.hero.set_user(user)
        self.bar.pack(fill="x", before=self.container)
        self.show_page("home")

    def logout(self):
        if self.running:
            messagebox.showinfo("Analysis running", "Please wait for the analysis to finish before signing out.")
            return
        self.user = None
        self.results, self.failed, self.job = [], [], None
        self.clear_resumes()
        self.hero.set_user(None)
        self.bar.pack_forget()
        self.show_page("login")

    def demo_run(self):
        self.load_sample_jd()
        self.use_samples()
        self.show_page("setup")

    def show_page(self, name):
        self.pages[name].tkraise()
        for k, lab in self.nav.items():
            lab.configure(fg=BLUE if k == name else GREY)

    # ------------------------------------------------------------------ home
    def _build_home(self, parent):
        sf = ScrollFrame(parent)
        page = sf.inner
        self.hero = Hero2(page, lambda: self.show_page("setup"), self.demo_run, 400)
        self.hero.pack(fill="x")

        def heading(title, sub):
            tk.Label(page, text=title, bg=BG, fg=TEXT, font=(FONT, 18, "bold")).pack(pady=(34, 2))
            tk.Label(page, text=sub, bg=BG, fg=GREY, font=(FONT, 10)).pack(pady=(0, 14))

        heading("How it works", "Three steps from a pile of PDFs to a ranked shortlist.")
        steps = tk.Frame(page, bg=BG)
        steps.pack(fill="x", padx=56)
        for i, (t, d) in enumerate((("Add the job", "Paste the job description and list the required and nice-to-have skills."),
                                    ("Upload resumes", "Pick PDF files or a whole folder - one resume or hundreds."),
                                    ("Review the shortlist", "See scores, missing skills, charts and AI feedback, then export."))):
            steps.grid_columnconfigure(i, weight=1, uniform="s")
            step_card(steps, i + 1, t, d).grid(row=0, column=i, sticky="nsew", padx=8)

        heading("Everything a recruiter needs", "Built with Python, Tkinter and a TF-IDF matching engine.")
        row = tk.Frame(page, bg=BG)
        row.pack(fill="x", padx=56)
        feats = [("PDF", "PDF Upload", "Text, links and photo are\nextracted automatically."),
                 ("AI", "Smart Matching", "Skills, experience and TF-IDF\nsimilarity against the job."),
                 ("OK", "Auto Shortlist", "Ranked and split into shortlisted\nand not shortlisted."),
                 ("TIP", "AI Feedback", "Tell each candidate exactly\nwhat to improve.")]
        for i, (ico, title, desc) in enumerate(feats):
            row.grid_columnconfigure(i, weight=1, uniform="f")
            c = card(row)
            c.grid(row=0, column=i, sticky="nsew", padx=8)
            badge = tk.Canvas(c, width=px(52), height=px(52), bg=WHITE, highlightthickness=0)
            badge.create_oval(2, 2, px(50), px(50), fill=LIGHT, outline="")
            badge.create_text(px(26), px(26), text=ico, fill=BLUE, font=(FONT, 11, "bold"))
            badge.pack(pady=(18, 4))
            tk.Label(c, text=title, bg=WHITE, fg=BLUE, font=(FONT, 12, "bold")).pack()
            tk.Label(c, text=desc, bg=WHITE, fg=GREY, font=(FONT, 9), justify="center").pack(pady=(2, 18), padx=10)

        heading("Candidate profiles at a glance", "Photo, name and links are detected from every PDF (example preview).")
        prow = tk.Frame(page, bg=BG)
        prow.pack(fill="x", padx=56)
        demo = [("Aarav Sharma", "Machine Learning Engineer", "95%", True, True, True),
                ("Priya Mehta", "Data Scientist", "81%", True, True, False),
                ("Rohan Verma", "Python Developer", "72%", True, False, False)]
        for i, (nm, role, sc, li, gh, pf) in enumerate(demo):
            prow.grid_columnconfigure(i, weight=1, uniform="p")
            c = card(prow)
            c.grid(row=0, column=i, sticky="nsew", padx=8)
            tk.Frame(c, bg=BLUE, height=4).pack(fill="x")
            inner = tk.Frame(c, bg=WHITE)
            inner.pack(fill="x", padx=16, pady=14)
            make_avatar(inner, nm).pack(side="left", padx=(0, 12))
            txt = tk.Frame(inner, bg=WHITE)
            txt.pack(side="left")
            tk.Label(txt, text=nm, bg=WHITE, fg=TEXT, font=(FONT, 12, "bold")).pack(anchor="w")
            tk.Label(txt, text=role, bg=WHITE, fg=GREY, font=(FONT, 9)).pack(anchor="w")
            tk.Label(txt, text=f"Match {sc}", bg=GREEN_BG, fg=GREEN, font=(FONT, 9, "bold"), padx=8, pady=1).pack(anchor="w", pady=(4, 0))
            chips = tk.Frame(c, bg=WHITE)
            chips.pack(fill="x", padx=16, pady=(0, 14))
            for lab, ok in (("LinkedIn", li), ("GitHub", gh), ("Portfolio", pf)):
                tk.Label(chips, text=("\u2713 " if ok else "\u2717 ") + lab, bg=GREEN_BG if ok else RED_BG,
                         fg=GREEN if ok else RED, font=(FONT, 8, "bold"), padx=7, pady=2).pack(side="left", padx=(0, 5))

        cta = tk.Canvas(page, height=px(130), highlightthickness=0, bg=BG)
        cta.pack(fill="x", padx=64, pady=(34, 34))

        def draw_cta(e=None):
            cta.delete("all")
            for ch in cta.winfo_children():
                ch.destroy()
            w, h = cta.winfo_width(), cta.winfo_height()
            rrect(cta, 0, 0, w, h, px(18), fill=BLUE, outline="")
            cta.create_text(px(36), h // 2 - px(12), anchor="w", text="Ready to find your next hire?", fill=WHITE,
                            font=(FONT, 18, "bold"))
            cta.create_text(px(36), h // 2 + px(18), anchor="w", text="Add a job description and your resumes to begin.",
                            fill="#D6E8FA", font=(FONT, 10))
            b = RoundButton(cta, "Get Started  \u2192", lambda: self.show_page("setup"), style="white", width=190,
                            height=44, parent_bg=BLUE, size=11)
            cta.create_window(w - px(36), h // 2, window=b, anchor="e")
        cta.bind("<Configure>", draw_cta)
        return sf

    # ------------------------------------------------------------------ setup page
    def _section(self, parent, num, title):
        head = tk.Frame(parent, bg=WHITE)
        head.pack(fill="x", padx=16, pady=(14, 8))
        tk.Label(head, text=num, bg=BLUE, fg=WHITE, font=(FONT, 10, "bold"), width=2).pack(side="left")
        tk.Label(head, text=title, bg=WHITE, fg=TEXT, font=(FONT, 12, "bold")).pack(side="left", padx=8)
        return head

    def _build_setup(self, parent):
        sf = ScrollFrame(parent)
        body = tk.Frame(sf.inner, bg=BG)
        body.pack(fill="both", expand=True, padx=28, pady=18)
        tk.Label(body, text="Analyze candidates", bg=BG, fg=TEXT, font=(FONT, 20, "bold")).pack(anchor="w")
        tk.Label(body, text="Add a job description and PDF resumes, then press Analyze.", bg=BG, fg=GREY,
                 font=(FONT, 10)).pack(anchor="w", pady=(0, 6))

        grid = tk.Frame(body, bg=BG)
        grid.pack(fill="both", expand=True)
        grid.grid_columnconfigure(0, weight=1, uniform="c")
        grid.grid_columnconfigure(1, weight=1, uniform="c")

        # --- job description card
        c1 = card(grid)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=8)
        self._section(c1, "1", "Job description")
        br = tk.Frame(c1, bg=WHITE)
        br.pack(fill="x", padx=16)
        RoundButton(br, "Load sample", self.load_sample_jd, "outline", 120, 32, WHITE, 9).pack(side="left", padx=(0, 6))
        RoundButton(br, "Open file...", self.open_jd_file, "outline", 120, 32, WHITE, 9).pack(side="left", padx=(0, 6))
        RoundButton(br, "Clear", lambda: self.jd_text.delete("1.0", "end"), "outline", 90, 32, WHITE, 9).pack(side="left")
        tf = tk.Frame(c1, bg=WHITE)
        tf.pack(fill="both", expand=True, padx=16, pady=(10, 16))
        self.jd_text = tk.Text(tf, height=11, wrap="word", font=(FONT, 10), relief="flat", bd=0, padx=10, pady=8,
                               highlightthickness=1, highlightbackground=BORDER, highlightcolor=BLUE, undo=True)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.jd_text.yview)
        self.jd_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.jd_text.pack(side="left", fill="both", expand=True)

        # --- resumes card
        c2 = card(grid)
        c2.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=8)
        self._section(c2, "2", "Resumes (PDF only)")
        br2 = tk.Frame(c2, bg=WHITE)
        br2.pack(fill="x", padx=16)
        RoundButton(br2, "Add PDFs...", self.add_pdfs, "outline", 110, 32, WHITE, 9).pack(side="left", padx=(0, 6))
        RoundButton(br2, "Add folder...", self.add_folder, "outline", 120, 32, WHITE, 9).pack(side="left", padx=(0, 6))
        RoundButton(br2, "Use samples", self.use_samples, "outline", 120, 32, WHITE, 9).pack(side="left", padx=(0, 6))
        RoundButton(br2, "Clear", self.clear_resumes, "outline", 80, 32, WHITE, 9).pack(side="left")
        lf = tk.Frame(c2, bg=WHITE)
        lf.pack(fill="both", expand=True, padx=16, pady=(10, 4))
        self.listbox = tk.Listbox(lf, height=9, font=(FONT, 9), relief="flat", bd=0, activestyle="none",
                                  highlightthickness=1, highlightbackground=BORDER, selectbackground=LIGHT,
                                  selectforeground=TEXT)
        lsb = ttk.Scrollbar(lf, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=lsb.set)
        lsb.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)
        self.count_lbl = tk.Label(c2, text="0 resumes loaded", bg=WHITE, fg=BLUE, font=(FONT, 10, "bold"))
        self.count_lbl.pack(anchor="w", padx=16, pady=(0, 14))

        # --- criteria card
        c3 = card(grid)
        c3.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=8)
        head = self._section(c3, "3", "Criteria  (filled automatically from the job description - edit freely)")
        RoundButton(head, "Auto-detect", self.auto_detect, "primary", 130, 32, WHITE, 9).pack(side="right")
        form = tk.Frame(c3, bg=WHITE)
        form.pack(fill="x", padx=16, pady=(0, 6))
        form.grid_columnconfigure(1, weight=1)
        tk.Label(form, text="Required skills", bg=WHITE, fg=TEXT, font=(FONT, 10, "bold")).grid(row=0, column=0, sticky="w", pady=6)
        styled_entry(form, self.req_var).grid(row=0, column=1, sticky="ew", padx=12, pady=6, ipady=5)
        tk.Label(form, text="Nice-to-have skills", bg=WHITE, fg=TEXT, font=(FONT, 10, "bold")).grid(row=1, column=0, sticky="w", pady=6)
        styled_entry(form, self.nice_var).grid(row=1, column=1, sticky="ew", padx=12, pady=6, ipady=5)
        tk.Label(form, text="Minimum experience (years)", bg=WHITE, fg=TEXT, font=(FONT, 10, "bold")).grid(row=2, column=0, sticky="w", pady=6)
        tk.Spinbox(form, from_=0, to=30, textvariable=self.exp_var, width=5, font=(FONT, 10), relief="flat",
                   highlightthickness=1, highlightbackground=BORDER, highlightcolor=BLUE).grid(row=2, column=1, sticky="w", padx=12, pady=6, ipady=3)
        tk.Label(form, text="Shortlist threshold", bg=WHITE, fg=TEXT, font=(FONT, 10, "bold")).grid(row=3, column=0, sticky="w", pady=6)
        srow = tk.Frame(form, bg=WHITE)
        srow.grid(row=3, column=1, sticky="w", padx=12, pady=6)
        self.th_lbl = tk.Label(srow, text="60 %", bg=WHITE, fg=BLUE, font=(FONT, 11, "bold"), width=6)
        self.slider = BlueSlider(srow, 30, 90, 60, 5, 300, lambda v: self.th_lbl.configure(text=f"{v} %"))
        self.slider.pack(side="left")
        self.th_lbl.pack(side="left", padx=8)
        tk.Label(c3, text="Skill names such as: Python, SQL, Machine Learning, scikit-learn, Pandas, Docker, AWS ...",
                 bg=WHITE, fg=GREY, font=(FONT, 9)).pack(anchor="w", padx=16, pady=(0, 14))

        # --- analyze
        bottom = tk.Frame(body, bg=BG)
        bottom.pack(fill="x", pady=(8, 20))
        RoundButton(bottom, "Analyze Resumes", self.start_analysis, "primary", 280, 50, BG, 13).pack()
        self.prog = ttk.Progressbar(bottom, style="Blue.Horizontal.TProgressbar", mode="determinate", length=px(420))
        self.status_lbl = tk.Label(bottom, text="", bg=BG, fg=GREY, font=(FONT, 10))
        return sf

    # ------------------------------------------------------------------ setup actions
    def load_sample_jd(self):
        if not SAMPLE_JD.exists():
            self._offer_samples()
            if not SAMPLE_JD.exists():
                return
        self.jd_text.delete("1.0", "end")
        self.jd_text.insert("1.0", SAMPLE_JD.read_text(encoding="utf-8"))
        self.auto_detect()

    def open_jd_file(self):
        path = filedialog.askopenfilename(title="Choose job description",
                                          filetypes=[("PDF or text", "*.pdf *.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            text = (extract_text_from_pdf(path) if path.lower().endswith(".pdf")
                    else Path(path).read_text(encoding="utf-8", errors="ignore"))
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Could not read file", str(e))
            return
        self.jd_text.delete("1.0", "end")
        self.jd_text.insert("1.0", text)
        self.auto_detect()

    def auto_detect(self):
        jd = self.jd_text.get("1.0", "end").strip()
        if not jd:
            messagebox.showinfo("Auto-detect", "Add a job description first.")
            return
        req, nice = split_jd_skills(jd)
        self.req_var.set(", ".join(req))
        self.nice_var.set(", ".join(nice))
        self.exp_var.set(extract_min_experience(jd))

    def _refresh_resume_list(self):
        self.listbox.delete(0, "end")
        for p in self.resume_paths[:500]:
            self.listbox.insert("end", p.name)
        n = len(self.resume_paths)
        self.count_lbl.configure(text=f"{n} resume{'s' if n != 1 else ''} loaded")

    def _add_paths(self, paths):
        known = {p.resolve() for p in self.resume_paths}
        for p in paths:
            p = Path(p)
            if p.suffix.lower() == ".pdf" and p.resolve() not in known:
                self.resume_paths.append(p)
                known.add(p.resolve())
        self._refresh_resume_list()

    def add_pdfs(self):
        files = filedialog.askopenfilenames(title="Select resume PDFs", filetypes=[("PDF files", "*.pdf")])
        if files:
            self._add_paths(files)

    def add_folder(self):
        folder = filedialog.askdirectory(title="Select a folder containing resume PDFs")
        if folder:
            found = sorted(Path(folder).rglob("*.pdf"))
            if not found:
                messagebox.showinfo("No PDFs", "That folder has no PDF files.")
            self._add_paths(found)

    def use_samples(self):
        if not SAMPLE_DIR.exists():
            self._offer_samples()
        if SAMPLE_DIR.exists():
            self._add_paths(sorted(SAMPLE_DIR.rglob("*.pdf")))

    def _offer_samples(self):
        if messagebox.askyesno("Sample data", "Sample files were not found.\nCreate them now (12 resumes + 150 random)?"):
            try:
                subprocess.run([sys.executable, "generate_samples.py", "--bulk", "150"], cwd=BASE, check=True,
                               capture_output=True)
            except Exception as e:  # noqa: BLE001
                messagebox.showerror("Could not create samples",
                                     f"{e}\n\nInstall the library first:  pip install reportlab")

    def clear_resumes(self):
        self.resume_paths = []
        self._refresh_resume_list()

    # ------------------------------------------------------------------ analysis
    @staticmethod
    def _parse_skills(text):
        lookup = {k.lower(): k for k in SKILLS}
        ok, bad = [], []
        for item in text.split(","):
            key = item.strip().lower()
            if not key:
                continue
            (ok if key in lookup else bad).append(lookup.get(key, item.strip()))
        return list(dict.fromkeys(ok)), bad

    def start_analysis(self):
        if self.running:
            return
        jd = self.jd_text.get("1.0", "end").strip()
        if not jd:
            messagebox.showwarning("Job description missing", "Please add a job description first.")
            return
        if not self.resume_paths:
            messagebox.showwarning("No resumes", "Please add at least one PDF resume (or press 'Use samples').")
            return
        if not self.req_var.get().strip() and not self.nice_var.get().strip():
            self.auto_detect()
        req, bad1 = self._parse_skills(self.req_var.get())
        nice, bad2 = self._parse_skills(self.nice_var.get())
        if bad1 or bad2:
            messagebox.showinfo("Unknown skills ignored", "Not in the skills list: " + ", ".join(bad1 + bad2))
        try:
            min_exp = int(self.exp_var.get())
        except (tk.TclError, ValueError):
            min_exp = 0
        self.threshold = self.slider.value
        job = JobSpec(jd, req, nice, min_exp)
        self.running = True
        self.prog.configure(value=0)
        self.prog.pack(pady=(14, 4))
        self.status_lbl.pack()
        self.status_lbl.configure(text="Starting...")
        threading.Thread(target=self._worker, args=(list(self.resume_paths), job, self.threshold), daemon=True).start()
        self.after(80, self._poll)

    def _worker(self, paths, job, threshold):
        texts, photos, failed = {}, {}, []
        for i, p in enumerate(paths, 1):
            try:
                t = extract_text_from_pdf(str(p))
                if len(t.split()) < 20:
                    raise ValueError("no readable text (scanned image?)")
                key = p.name if p.name not in texts else f"{p.parent.name}/{p.name}"
                texts[key] = t
                photos[key] = extract_photo(str(p))
            except Exception as e:  # noqa: BLE001
                failed.append((p.name, str(e)))
            self.q.put(("progress", i, len(paths)))
        try:
            results = analyze_resumes(texts, job, threshold, photos) if texts else []
            self.q.put(("done", results, failed, job))
        except Exception as e:  # noqa: BLE001
            self.q.put(("error", str(e)))

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "progress":
                    _, i, n = msg
                    self.prog.configure(value=100 * i / n)
                    self.status_lbl.configure(text=f"Reading resumes...  {i} / {n}")
                elif msg[0] == "done":
                    self._finish(msg[1], msg[2], msg[3])
                    return
                else:
                    self.running = False
                    self.prog.pack_forget()
                    self.status_lbl.pack_forget()
                    messagebox.showerror("Analysis failed", msg[1])
                    return
        except queue.Empty:
            pass
        if self.running:
            self.after(80, self._poll)

    def _finish(self, results, failed, job):
        self.running = False
        self.prog.pack_forget()
        self.status_lbl.pack_forget()
        if not results:
            messagebox.showerror("Nothing to analyze", "None of the PDFs contained readable text.")
            return
        self.results, self.failed, self.job = results, failed, job
        self.render_results()
        self.show_page("results")

    # ------------------------------------------------------------------ results page
    def _build_results(self, parent):
        page = tk.Frame(parent, bg=BG)
        self.res_body = tk.Frame(page, bg=BG)
        self.res_body.pack(fill="both", expand=True, padx=28, pady=16)
        tk.Label(self.res_body, text="Results will appear here after you analyze.", bg=BG, fg=GREY,
                 font=(FONT, 12)).pack(pady=40)
        return page

    def render_results(self):
        for w in self.res_body.winfo_children():
            w.destroy()
        short = [r for r in self.results if r.status == "Shortlisted"]
        rest = [r for r in self.results if r.status != "Shortlisted"]
        avg = sum(r.score for r in self.results) / len(self.results)

        top = tk.Frame(self.res_body, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text="Results", bg=BG, fg=TEXT, font=(FONT, 20, "bold")).pack(side="left")
        RoundButton(top, "Full report CSV", lambda: self.export(False), "outline", 150, 34, BG, 9).pack(side="right", padx=(6, 0))
        RoundButton(top, "Shortlisted CSV", lambda: self.export(True), "outline", 150, 34, BG, 9).pack(side="right", padx=6)
        RoundButton(top, "\u2190 Back to setup", lambda: self.show_page("setup"), "primary", 150, 34, BG, 9).pack(side="right", padx=6)

        mrow = tk.Frame(self.res_body, bg=BG)
        mrow.pack(fill="x", pady=12)
        for i, (val, lab) in enumerate(((len(self.results), "Resumes analysed"), (len(short), "Shortlisted"),
                                        (len(rest), "Not shortlisted"), (f"{avg:.0f}%", "Average match"))):
            mrow.grid_columnconfigure(i, weight=1, uniform="m")
            m = card(mrow)
            m.grid(row=0, column=i, sticky="nsew", padx=6)
            tk.Frame(m, bg=BLUE if i != 2 else "#E06666", height=4).pack(fill="x")
            tk.Label(m, text=str(val), bg=WHITE, fg=BLUE if i != 2 else RED, font=(FONT, 26, "bold")).pack(pady=(8, 0))
            tk.Label(m, text=lab, bg=WHITE, fg=GREY, font=(FONT, 10)).pack(pady=(0, 10))

        if self.failed:
            tk.Label(self.res_body, bg=BG, fg=RED, font=(FONT, 9),
                     text=f"{len(self.failed)} file(s) could not be read: " + ", ".join(n for n, _ in self.failed[:5])
                     ).pack(anchor="w")

        nb = ttk.Notebook(self.res_body)
        nb.pack(fill="both", expand=True, pady=(4, 0))
        tabs = []
        for title in (f"Shortlisted ({len(short)})", f"Needs improvement ({len(rest)})", "Ranking table", "Chart"):
            f = tk.Frame(nb, bg=BG)
            nb.add(f, text=title)
            tabs.append(f)

        for frame, rows, empty in ((tabs[0], short, "No candidate met the criteria. Try a lower threshold."),
                                   (tabs[1], rest, "Everyone was shortlisted!")):
            sf = ScrollFrame(frame)
            sf.pack(fill="both", expand=True)
            if not rows:
                tk.Label(sf.inner, text=empty, bg=BG, fg=GREY, font=(FONT, 11)).pack(pady=30)
            for r in rows[:40]:
                self._candidate_card(sf.inner, r)
            if len(rows) > 40:
                tk.Label(sf.inner, bg=BG, fg=GREY, font=(FONT, 9),
                         text=f"Showing top 40 of {len(rows)} - export the CSV for the complete list.").pack(pady=8)

        self._build_table(tabs[2])
        chart = tk.Canvas(tabs[3], bg=WHITE, highlightthickness=0, height=px(560))
        chart.pack(fill="both", expand=True, padx=6, pady=6)
        chart.bind("<Configure>", lambda e, c=chart: self._draw_chart(c))

    def _candidate_card(self, parent, r):
        good = r.status == "Shortlisted"
        c = card(parent)
        c.pack(fill="x", padx=10, pady=6)
        tk.Frame(c, bg=GREEN if good else RED, width=5).pack(side="left", fill="y")
        body = tk.Frame(c, bg=WHITE)
        body.pack(side="left", fill="both", expand=True, padx=14, pady=10)

        head = tk.Frame(body, bg=WHITE)
        head.pack(fill="x")
        make_avatar(head, r.name, r.photo_png).pack(side="left", padx=(0, 14))
        left = tk.Frame(head, bg=WHITE)
        left.pack(side="left")
        tk.Label(left, text=r.name, bg=WHITE, fg=TEXT, font=(FONT, 13, "bold")).pack(anchor="w")
        tk.Label(left, text=f"{r.filename}    {r.email}    {r.phone}", bg=WHITE, fg=GREY, font=(FONT, 9)).pack(anchor="w")
        right = tk.Frame(head, bg=WHITE)
        right.pack(side="right")
        tk.Label(right, text=f"{r.score:g}%", bg=WHITE, fg=BLUE, font=(FONT, 22, "bold")).pack(side="right")
        tk.Label(right, text=r.status.upper(), bg=GREEN_BG if good else RED_BG, fg=GREEN if good else RED,
                 font=(FONT, 8, "bold"), padx=10, pady=3).pack(side="right", padx=(0, 14))

        ScoreBar(body, r.score, good).pack(fill="x", pady=(8, 6))
        tk.Label(body, bg=WHITE, fg=GREY, font=(FONT, 9), anchor="w",
                 text=f"Experience: {r.experience_years:g} yrs     Education: {r.education}     "
                      f"Text similarity: {r.similarity:g}%     Tier: {r.tier}").pack(fill="x", pady=(0, 4))
        pill_row(body, "Required matched", r.required_matched, "ok")
        pill_row(body, "Required missing", r.required_missing, "bad")
        pill_row(body, "Nice-to-have matched", r.nice_matched, "ok")
        prow = tk.Frame(body, bg=WHITE)
        prow.pack(fill="x", pady=(4, 2), anchor="w")
        tk.Label(prow, text="Profile detected", bg=WHITE, fg=GREY, font=(FONT, 9), width=22, anchor="w").pack(side="left")
        link_chips(prow, r).pack(side="left")
        found = [x for x in (r.linkedin, r.github, r.portfolio) if x]
        if found:
            tk.Label(body, text="    ".join(found), bg=WHITE, fg=BLUE, font=(FONT, 9), anchor="w").pack(fill="x")
        RoundButton(body, "AI Feedback (Groq)", command=lambda r=r: self.ai_feedback_window(r), style="outline",
                    width=190, height=34, parent_bg=WHITE, size=10).pack(anchor="w", pady=(8, 0))
        if r.reminders:
            rb = tk.Frame(body, bg="#FFF8E5", highlightthickness=1, highlightbackground="#F0D58A")
            rb.pack(fill="x", pady=(8, 0))
            tk.Label(rb, text="Profile reminders (auto-detected)", bg="#FFF8E5", fg="#8A5A00",
                     font=(FONT, 10, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
            rlabels = []
            for tip in r.reminders:
                lab = tk.Label(rb, text="\u26A0  " + tip, bg="#FFF8E5", fg=TEXT, font=(FONT, 9), justify="left",
                               anchor="w", wraplength=700)
                lab.pack(fill="x", padx=12, pady=1)
                rlabels.append(lab)
            tk.Frame(rb, bg="#FFF8E5", height=6).pack()
            rb.bind("<Configure>", lambda e, ls=rlabels: [l.configure(wraplength=max(e.width - 40, 200)) for l in ls])

        if r.recommendations:
            box = tk.Frame(body, bg="#F5F9FE", highlightthickness=1, highlightbackground="#CFE2F5")
            box.pack(fill="x", pady=(8, 0))
            tk.Label(box, text="How to improve this resume", bg="#F5F9FE", fg=BLUE,
                     font=(FONT, 10, "bold")).pack(anchor="w", padx=12, pady=(8, 2))
            labels = []
            for tip in r.recommendations[:7]:
                lab = tk.Label(box, text="\u2022  " + tip, bg="#F5F9FE", fg=TEXT, font=(FONT, 9), justify="left",
                               anchor="w", wraplength=700)
                lab.pack(fill="x", padx=12, pady=1)
                labels.append(lab)
            tk.Frame(box, bg="#F5F9FE", height=6).pack()
            box.bind("<Configure>", lambda e, ls=labels: [l.configure(wraplength=max(e.width - 40, 200)) for l in ls])

    # ------------------------------------------------------------------ AI feedback (Groq)
    def ai_feedback_window(self, r):
        """Ask Groq for written feedback on one candidate and show it in a pop-up window."""
        if not self.groq_key:
            key = simpledialog.askstring(
                "Groq API key",
                "Paste your Groq API key (starts with gsk_).\nIt is kept only while this program is open.",
                show="*", parent=self)
            if not key or not key.strip():
                return
            self.groq_key = key.strip()

        win = tk.Toplevel(self)
        win.title(f"AI Feedback  -  {r.name}")
        win.configure(bg=WHITE)
        win.geometry(f"{px(760)}x{px(640)}")
        tk.Label(win, text=f"AI Feedback: {r.name}", bg=WHITE, fg=BLUE, font=(FONT, 15, "bold")).pack(anchor="w", padx=18, pady=(14, 0))
        tk.Label(win, text=f"Score {r.score:g}%   |   {r.status}   |   powered by Groq", bg=WHITE, fg=GREY,
                 font=(FONT, 9)).pack(anchor="w", padx=18, pady=(0, 8))
        box = tk.Text(win, wrap="word", font=(FONT, 10), bg="#F5F9FE", fg=TEXT, relief="flat", padx=14, pady=10)
        box.pack(fill="both", expand=True, padx=18)
        box.insert("1.0", "Asking Groq for feedback... please wait.")
        box.configure(state="disabled")
        bar = tk.Frame(win, bg=WHITE)
        bar.pack(fill="x", padx=18, pady=10)

        def copy_text():
            self.clipboard_clear()
            self.clipboard_append(box.get("1.0", "end").strip())

        RoundButton(bar, "Copy", command=copy_text, style="outline", width=110, height=34, parent_bg=WHITE, size=10).pack(side="left")
        RoundButton(bar, "Close", command=win.destroy, style="primary", width=110, height=34, parent_bg=WHITE, size=10).pack(side="right")

        out: queue.Queue = queue.Queue()

        def worker():
            try:
                out.put(("ok", ai_feedback.get_feedback(self.job, r, self.groq_key)))
            except ai_feedback.AIFeedbackError as e:
                out.put(("err", str(e), e.bad_key))
            except Exception as e:  # noqa: BLE001
                out.put(("err", f"Unexpected error: {e}", False))

        def poll():
            if not win.winfo_exists():
                return
            try:
                msg = out.get_nowait()
            except queue.Empty:
                win.after(100, poll)
                return
            box.configure(state="normal")
            box.delete("1.0", "end")
            if msg[0] == "ok":
                box.insert("1.0", msg[1])
            else:
                box.insert("1.0", "Could not get AI feedback.\n\n" + msg[1])
                if msg[2]:
                    self.groq_key = ""         # ask for the key again next time
            box.configure(state="disabled")

        threading.Thread(target=worker, daemon=True).start()
        win.after(100, poll)

    def _build_table(self, frame):
        cols = ("rank", "name", "score", "status", "tier", "exp", "edu", "links", "missing", "file")
        heads = ("#", "Candidate", "Score %", "Status", "Tier", "Exp (yrs)", "Education", "Profile links", "Missing required skills", "File")
        widths = (45, 170, 80, 120, 90, 80, 100, 170, 280, 170)
        wrap = tk.Frame(frame, bg=BG)
        wrap.pack(fill="both", expand=True, padx=6, pady=6)
        tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c, h, w in zip(cols, heads, widths):
            tree.heading(c, text=h)
            tree.column(c, width=px(w), anchor="w" if c in ("name", "missing", "file", "edu") else "center")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        tree.tag_configure("short", background="#F1F8F3")
        tree.tag_configure("no", background=WHITE)
        for i, r in enumerate(self.results, 1):
            tree.insert("", "end", tags=("short" if r.status == "Shortlisted" else "no",),
                        values=(i, r.name, f"{r.score:g}", r.status, r.tier, f"{r.experience_years:g}",
                                r.education, ", ".join(n for n, v in (("LinkedIn", r.linkedin), ("GitHub", r.github), ("Portfolio", r.portfolio)) if v) or "none",
                                ", ".join(r.required_missing) or "-", r.filename))

    def _draw_chart(self, cv):
        cv.delete("all")
        w = cv.winfo_width()
        rows = self.results[:15]
        left, right, top, rowh = px(190), px(70), px(56), px(30)
        cv.create_text(px(20), px(24), text="Top 15 candidates by match score", anchor="w",
                       font=(FONT, 13, "bold"), fill=TEXT)
        bw = max(w - left - right, 50)
        for i, r in enumerate(rows):
            y = top + i * rowh
            cv.create_text(left - px(10), y + rowh // 2, text=r.name[:24], anchor="e", font=(FONT, 9), fill=TEXT)
            cv.create_rectangle(left, y + px(6), left + bw, y + rowh - px(6), fill="#EEF3F8", outline="")
            cv.create_rectangle(left, y + px(6), left + bw * r.score / 100, y + rowh - px(6),
                                fill=BLUE if r.status == "Shortlisted" else "#E06666", outline="")
            cv.create_text(left + bw + px(8), y + rowh // 2, text=f"{r.score:g}%", anchor="w",
                           font=(FONT, 9, "bold"), fill=DARK)
        x = left + bw * self.threshold / 100
        cv.create_line(x, top - px(8), x, top + len(rows) * rowh, fill=DARK, dash=(4, 3))
        cv.create_text(x, top - px(16), text=f"threshold {self.threshold}%", font=(FONT, 9, "bold"), fill=DARK)

    def export(self, only_short):
        if not self.results:
            return
        rows = [r for r in self.results if r.status == "Shortlisted"] if only_short else self.results
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV file", "*.csv")],
            initialfile="shortlisted_candidates.csv" if only_short else "all_candidates.csv")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(self.results[0].to_row().keys()))
                writer.writeheader()
                writer.writerows(r.to_row() for r in rows)
            messagebox.showinfo("Saved", f"Saved {len(rows)} rows to:\n{path}")
        except OSError as e:
            messagebox.showerror("Could not save", str(e))


def main():
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)   # crisp text on high-DPI screens
        except Exception:  # noqa: BLE001
            pass
    App().mainloop()


if __name__ == "__main__":
    main()
