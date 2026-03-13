from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, session, flash
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from forms import RegistrationForm, LoginForm, QuizForm
from datetime import timedelta
import sqlite3
import os
import logging
from fractions import Fraction

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-key-change-in-production')

csrf = CSRFProtect(app)

app.permanent_session_lifetime = timedelta(hours=2)

# ================= DATABASE =================

def get_db():
    conn = sqlite3.connect("rhythmquest.db")
    conn.row_factory = sqlite3.Row
    return conn

# ================= LOGGING =================

if not os.path.exists("logs"):
    os.makedirs("logs")

logging.basicConfig(
    filename="logs/app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# ================= ANSWER NORMALIZATION =================

def normalize_answer(answer_str):
    answer_str = answer_str.strip().lower().replace(' ', '')

    try:
        if '/' in answer_str:
            frac = Fraction(answer_str).limit_denominator()
            return str(frac), float(frac)
        else:
            num_val = float(answer_str)
            frac = Fraction(num_val).limit_denominator()
            return str(frac), num_val
    except:
        return answer_str, None


def answers_match(answer, correct_answer):
    a_norm, a_num = normalize_answer(answer)
    c_norm, c_num = normalize_answer(correct_answer)

    if a_norm == c_norm:
        return True

    if a_num is not None and c_num is not None:
        return abs(a_num - c_num) < 0.0001

    return False

# ================= ROUTES =================

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect('/dashboard')
    return redirect('/login')


# ================= REGISTER =================

@app.route('/register', methods=['GET','POST'])
def register():

    form = RegistrationForm()

    if form.validate_on_submit():

        name = form.name.data
        email = form.email.data
        password = form.password.data

        try:
            conn = get_db()
            cursor = conn.cursor()

            # Check if email already exists
            cursor.execute(
                "SELECT ID FROM STUDENT WHERE Email=?",
                (email,)
            )

            if cursor.fetchone():
                flash("Email already registered!", "danger")
                conn.close()
                return redirect('/register')

            # Hash password
            hashed_password = generate_password_hash(password)

            # Insert user
            cursor.execute(
                "INSERT INTO STUDENT (Name, Email, Password) VALUES (?, ?, ?)",
                (name, email, hashed_password)
            )

            conn.commit()
            conn.close()

            flash("Registration successful!", "success")
            return redirect('/login')

        except Exception as e:
            print(e)
            flash("Registration failed.", "danger")

    return render_template("register.html", form=form)


# ================= LOGIN =================

@app.route('/login', methods=['GET','POST'])
def login():

    form = LoginForm()

    if form.validate_on_submit():

        email = form.email.data
        password = form.password.data

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT ID,Name,Email,Password FROM STUDENT WHERE Email=?",
            (email,)
        )

        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['Password'], password):

            session['user_id'] = user['ID']
            session['user_name'] = user['Name']

            flash("Login successful!", "success")
            return redirect('/music')

        flash("Invalid login", "danger")

    return render_template("login.html", form=form)


# ================= MUSIC =================

@app.route('/music')
def music():

    if 'user_id' not in session:
        return redirect('/login')

    return render_template("music.html")


# ================= QUIZ =================

@app.route('/quiz')
def quiz():

    if 'user_id' not in session:
        return redirect('/login')

    music_score = int(request.args.get("music_score",0))

    if music_score < 60:
        flash("Score too low! Retry music challenge.", "danger")
        return redirect('/music')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT ID,Question,CorrectAnswer FROM QUESTIONS ORDER BY RANDOM() LIMIT 1"
    )

    question = cursor.fetchone()
    conn.close()

    if not question:
        flash("No questions available.", "danger")
        return redirect('/music')

    session['question_id'] = question['ID']
    session['correct_answer'] = question['CorrectAnswer']
    session['music_score'] = music_score

    form = QuizForm()

    return render_template("quiz.html", question=question['Question'], form=form)


# ================= SUBMIT QUIZ =================

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():

    if 'user_id' not in session:
        return redirect('/login')

    form = QuizForm()

    if form.validate_on_submit():

        answer = form.answer.data
        correct_answer = session.get('correct_answer')

        is_correct = answers_match(answer, correct_answer)

        academic_score = 100 if is_correct else 0

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT COUNT(*) FROM PERFORMANCE WHERE Student_ID=?",
            (session['user_id'],)
        )

        attempt = cursor.fetchone()[0] + 1

        cursor.execute(
        """
        INSERT INTO PERFORMANCE
        (Student_ID,Question_ID,Music_Score,Academic_Score,Attempt_Number)
        VALUES(?,?,?,?,?)
        """,
        (
            session['user_id'],
            session['question_id'],
            session['music_score'],
            academic_score,
            attempt
        ))

        conn.commit()
        conn.close()

        if is_correct:
            flash("Correct! 🎉", "success")
        else:
            flash(f"Incorrect. Correct answer: {correct_answer}", "danger")

        return redirect('/dashboard')


# ================= DASHBOARD =================

@app.route('/dashboard')
def dashboard():

    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT Attempt_Number,Music_Score,Academic_Score
        FROM PERFORMANCE
        WHERE Student_ID=?
        """,
        (session['user_id'],)
    )

    rows = cursor.fetchall()
    conn.close()

    attempts = [r[0] for r in rows]
    music_scores = [r[1] for r in rows]
    academic_scores = [r[2] for r in rows]

    return render_template(
        "dashboard.html",
        attempts=attempts,
        music_scores=music_scores,
        academic_scores=academic_scores
    )


# ================= INIT DATABASE =================

@app.route('/init_db')
def init_db():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS STUDENT(
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT,
    Email TEXT UNIQUE,
    Password TEXT,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS QUESTIONS(
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Question TEXT,
    CorrectAnswer TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS PERFORMANCE(
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    Student_ID INTEGER,
    Question_ID INTEGER,
    Music_Score INTEGER,
    Academic_Score INTEGER,
    Attempt_Number INTEGER
    )
    """)

    # Insert sample questions
    cursor.execute("INSERT INTO QUESTIONS (Question, CorrectAnswer) VALUES ('1/2 + 1/2', '1')")
    cursor.execute("INSERT INTO QUESTIONS (Question, CorrectAnswer) VALUES ('3/4 + 1/4', '1')")
    cursor.execute("INSERT INTO QUESTIONS (Question, CorrectAnswer) VALUES ('2/3 + 1/3', '1')")
    cursor.execute("INSERT INTO QUESTIONS (Question, CorrectAnswer) VALUES ('5/10 simplified', '1/2')")
    cursor.execute("INSERT INTO QUESTIONS (Question, CorrectAnswer) VALUES ('1/4 + 1/4', '1/2')")

    conn.commit()
    conn.close()

    return "Database initialized with sample questions!"


# ================= MAIN =================

if __name__ == "__main__":
    app.run(debug=True)