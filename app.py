from werkzeug.security import generate_password_hash, check_password_hash
from flask import Flask, render_template, request, redirect, session, flash
from flask_mysqldb import MySQL
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from forms import RegistrationForm, LoginForm, QuizForm
from datetime import datetime, timedelta
import os
import logging
import re
from fractions import Fraction

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-key-change-in-production')

# Session timeout configuration (in seconds)
app.permanent_session_lifetime = timedelta(hours=2)

# MySQL Configuration (from .env file)
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQL_PORT', 3306))

# Enable CSRF Protection
csrf = CSRFProtect(app)

# ==================== CACHE CONTROL ====================
@app.after_request
def set_cache_headers(response):
    """Prevent browser caching to ensure fresh page loads"""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-UA-Compatible'] = 'IE=edge'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

# ==================== LOGGING SETUP ====================
# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure logging
logging.basicConfig(
    filename='logs/app.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

mysql = MySQL(app)

def normalize_answer(answer_str):
    """
    Normalize answer for comparison.
    Handles fractions (1/2), decimals (0.5), and whole numbers.
    Returns the normalized string and numeric value for comparison.
    """
    answer_str = answer_str.strip().lower().replace(' ', '')
    
    try:
        # Try to parse as a fraction first (e.g., "1/2")
        if '/' in answer_str:
            frac = Fraction(answer_str).limit_denominator()
            return str(frac), float(frac)
        # Try to parse as a decimal or whole number
        else:
            num_val = float(answer_str)
            frac = Fraction(num_val).limit_denominator()
            return str(frac), num_val
    except (ValueError, ZeroDivisionError):
        # If parsing fails, return the normalized string as-is
        return answer_str, None

def answers_match(answer, correct_answer):
    """
    Compare two answers accounting for equivalent fractions and decimals.
    """
    answer_normalized, answer_num = normalize_answer(answer)
    correct_normalized, correct_num = normalize_answer(correct_answer)
    
    # First try exact string match
    if answer_normalized == correct_normalized:
        return True
    
    # If both could be converted to numbers, compare with small tolerance
    if answer_num is not None and correct_num is not None:
        return abs(answer_num - correct_num) < 0.0001
    
    # Also try case-insensitive string comparison
    return answer.strip().lower().replace(' ', '') == correct_answer.strip().lower().replace(' ', '')

@app.route('/')
def home():
    """Redirect to login if not authenticated, else redirect to dashboard"""
    if 'user_id' in session:
        return redirect('/dashboard')
    return redirect('/login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration with form validation"""
    form = RegistrationForm()
    
    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        password = form.password.data
        
        try:
            cursor = mysql.connection.cursor()
            
            # Check if email already exists
            cursor.execute("SELECT ID FROM STUDENT WHERE Email=%s", (email,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                cursor.close()
                flash('Email already registered! Please use a different email.', 'danger')
                logger.warning(f'Registration attempt with existing email: {email}')
                return redirect('/register')
            
            # Hash the password
            hashed_password = generate_password_hash(password)
            
            # Insert new user
            cursor.execute(
                "INSERT INTO STUDENT(Name, Email, Password) VALUES (%s, %s, %s)",
                (name, email, hashed_password)
            )
            mysql.connection.commit()
            cursor.close()
            
            flash('Registration successful! Please login.', 'success')
            logger.info(f'New user registered: {email}')
            return redirect('/login')
            
        except Exception as e:
            logger.error(f'Registration error for {email}: {str(e)}')
            flash('An error occurred during registration. Please try again.', 'danger')
            return redirect('/register')
    
    # If form has errors, display them
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{error}', 'danger')
    
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login with form validation"""
    form = LoginForm()
    
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        
        try:
            cursor = mysql.connection.cursor()
            cursor.execute(
                "SELECT ID, Name, Email, Password FROM STUDENT WHERE Email=%s",
                (email,)
            )
            user = cursor.fetchone()
            cursor.close()
            
            if user and check_password_hash(user[3], password):
                session['user_id'] = user[0]
                session['user_name'] = user[1]
                session['user_email'] = user[2]
                flash(f'Welcome back, {user[1]}!', 'success')
                logger.info(f'User logged in: {email}')
                return redirect('/music')
            else:
                flash('Invalid email or password. Please try again.', 'danger')
                logger.warning(f'Failed login attempt for email: {email}')
                return redirect('/login')
                
        except Exception as e:
            logger.error(f'Login error for {email}: {str(e)}')
            flash('An error occurred during login. Please try again.', 'danger')
            return redirect('/login')
    
    # If form has errors, display them
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'{error}', 'danger')
    
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    """Clear user session and redirect to login"""
    session.clear()
    flash('You have been logged out successfully!', 'success')
    return redirect('/login')

@app.route('/music')
def music():
    if 'user_id' not in session:
        return redirect('/login')

    return render_template('music.html')

@app.route('/quiz')
def quiz():
    """Show random quiz question from database"""
    if 'user_id' not in session:
        return redirect('/login')

    try:
        music_score = int(request.args.get('music_score', 0))
    except (ValueError, TypeError):
        flash('Invalid music score. Please complete the music challenge first.', 'danger')
        return redirect('/music')

    if music_score < 60:
        flash('Score too low! Please retry the music challenge. (Minimum: 60)', 'danger')
        return redirect('/music')

    session['music_score'] = music_score
    
    try:
        cursor = mysql.connection.cursor()
        # Get a random question from database
        cursor.execute("SELECT ID, Question, CorrectAnswer FROM QUESTIONS ORDER BY RAND() LIMIT 1")
        question = cursor.fetchone()
        cursor.close()
        
        if not question:
            flash('No questions available. Please try again.', 'danger')
            logger.warning('No questions found in database')
            return redirect('/music')
        
        # Store question info in session
        session['question_id'] = question[0]
        session['correct_answer'] = question[2]
        
        form = QuizForm()
        return render_template('quiz.html', question=question[1], form=form)
        
    except Exception as e:
        logger.error(f'Quiz loading error: {str(e)}')
        flash('An error occurred while loading the quiz.', 'danger')
        return redirect('/music')

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT Attempt_Number, Music_Score, Academic_Score
        FROM PERFORMANCE
        WHERE Student_ID = %s
    """, (session['user_id'],))

    records = cursor.fetchall()
    cursor.close()

    attempts = []
    music_scores = []
    academic_scores = []

    for row in records:
        attempts.append(row[0])
        music_scores.append(row[1])
        academic_scores.append(row[2])

    return render_template(
        "dashboard.html",
        attempts=attempts,
        music_scores=music_scores,
        academic_scores=academic_scores
    )

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    """Submit quiz answer and save performance"""
    if 'user_id' not in session:
        return redirect('/login')

    # Check if quiz session data is valid
    if 'question_id' not in session or 'correct_answer' not in session:
        flash('Quiz session expired. Please start a new quiz.', 'warning')
        return redirect('/music')

    form = QuizForm()
    
    if form.validate_on_submit():
        answer = form.answer.data.strip()
        correct_answer = session.get('correct_answer', '')
        
        # Validate answer is not empty
        if not answer:
            flash('Please enter an answer', 'danger')
            return redirect('/quiz')
        
        # Use smart comparison that handles fractions, decimals, and equivalent values
        is_correct = answers_match(answer, correct_answer)
        academic_score = 100 if is_correct else 0
        
        try:
            cursor = mysql.connection.cursor()
            
            # Get attempt number
            cursor.execute(
                "SELECT COUNT(*) FROM PERFORMANCE WHERE Student_ID=%s",
                (session['user_id'],)
            )
            attempt_number = cursor.fetchone()[0] + 1
            
            # Insert performance record with question_id
            cursor.execute("""
                INSERT INTO PERFORMANCE
                (Student_ID, Question_ID, Music_Score, Academic_Score, Attempt_Number)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                session['user_id'],
                session.get('question_id'),
                session.get('music_score', 0),
                academic_score,
                attempt_number
            ))
            
            mysql.connection.commit()
            cursor.close()
            
            # Clear quiz session data
            session.pop('question_id', None)
            session.pop('correct_answer', None)
            session.pop('music_score', None)
            
            if academic_score == 100:
                flash('Correct! 🎉', 'success')
                logger.info(f'User {session["user_id"]} answered quiz correctly')
            else:
                flash(f'Incorrect. The answer was: {correct_answer}', 'danger')
                logger.info(f'User {session["user_id"]} answered quiz incorrectly')
            
            return redirect('/dashboard')
            
        except Exception as e:
            logger.error(f'Quiz submission error for user {session["user_id"]}: {str(e)}')
            flash('An error occurred while submitting your answer.', 'danger')
            return redirect('/quiz')
    else:
        flash('Please enter an answer', 'danger')
        return redirect('/quiz')

@app.route('/profile')
def profile():
    """Show user profile with performance statistics"""
    if 'user_id' not in session:
        return redirect('/login')
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get user info
        cursor.execute(
            "SELECT Name, Email, CreatedAt FROM STUDENT WHERE ID=%s",
            (session['user_id'],)
        )
        user = cursor.fetchone()
        
        # Get performance statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_attempts,
                AVG(Music_Score) as avg_music,
                AVG(Academic_Score) as avg_academic,
                MAX(Music_Score) as max_music,
                MAX(Academic_Score) as max_academic,
                SUM(CASE WHEN Academic_Score = 100 THEN 1 ELSE 0 END) as correct_answers
            FROM PERFORMANCE
            WHERE Student_ID=%s
        """, (session['user_id'],))
        
        stats = cursor.fetchone()
        cursor.close()
        
        # Format statistics
        profile_data = {
            'name': user[0],
            'email': user[1],
            'joined': user[2].strftime('%B %d, %Y') if user[2] else 'N/A',
            'total_attempts': stats[0] or 0,
            'avg_music': round(stats[1], 2) if stats[1] else 0,
            'avg_academic': round(stats[2], 2) if stats[2] else 0,
            'max_music': stats[3] or 0,
            'max_academic': stats[4] or 0,
            'correct_answers': stats[5] or 0
        }
        
        return render_template('profile.html', profile=profile_data)
        
    except Exception as e:
        logger.error(f'Profile loading error for user {session["user_id"]}: {str(e)}')
        flash('An error occurred while loading your profile.', 'danger')
        return redirect('/dashboard')

@app.route('/leaderboard')
def leaderboard():
    """Show top 10 students by combined average score"""
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("""
            SELECT 
                s.Name,
                COUNT(p.ID) as attempts,
                ROUND(AVG(p.Music_Score), 2) as avg_music,
                ROUND(AVG(p.Academic_Score), 2) as avg_academic,
                ROUND((AVG(p.Music_Score) + AVG(p.Academic_Score))/2, 2) as combined_score
            FROM STUDENT s
            INNER JOIN PERFORMANCE p ON s.ID = p.Student_ID
            GROUP BY s.ID
            ORDER BY combined_score DESC, attempts DESC
            LIMIT 10
        """)
        
        leaders = []
        for row in cursor.fetchall():
            leaders.append({
                'name': row[0],
                'attempts': row[1] or 0,
                'avg_music': row[2] or 0,
                'avg_academic': row[3] or 0,
                'combined_score': row[4] or 0
            })
        
        cursor.close()
        
        # If no leaders found, show friendly message
        if not leaders:
            flash('No performance data available yet.', 'info')
        
        return render_template('leaderboard.html', leaders=leaders)
        
    except Exception as e:
        logger.error(f'Leaderboard loading error: {str(e)}')
        flash('An error occurred while loading the leaderboard.', 'danger')
        return redirect('/dashboard')

# ==================== BEFORE REQUEST ====================

@app.before_request
def before_request():
    """Set session as permanent and check session timeout"""
    session.permanent = True
    app.permanent_session_lifetime = timedelta(hours=2)
    
    # Auto-check and award achievements on every request
    if 'user_id' in session:
        check_and_award_achievements(session['user_id'])

# ==================== HELPER FUNCTIONS ====================

def check_and_award_achievements(user_id):
    """Check and award achievements based on user performance"""
    try:
        cursor = mysql.connection.cursor()
        
        # Get user stats
        cursor.execute("""
            SELECT COUNT(*) as attempts,
                   SUM(CASE WHEN Academic_Score = 100 THEN 1 ELSE 0 END) as perfect_scores,
                   AVG(Academic_Score) as avg_score,
                   MAX(Music_Score) as best_music
            FROM PERFORMANCE
            WHERE Student_ID=%s
        """, (user_id,))
        
        stats = cursor.fetchone()
        if not stats or stats[0] == 0:
            cursor.close()
            return
        
        attempts, perfect_scores, avg_score, best_music = stats
        perfect_scores = perfect_scores or 0
        avg_score = avg_score or 0
        best_music = best_music or 0
        
        achievements_to_award = []
        
        # Check achievement criteria
        if attempts >= 1:
            achievements_to_award.append('First Step')
        if attempts >= 5:
            achievements_to_award.append('Getting Started')
        if attempts >= 25:
            achievements_to_award.append('Quiz Master')
        if perfect_scores >= 1:
            achievements_to_award.append('Perfect Score')
        if best_music >= 100:
            achievements_to_award.append('Speed Racer')
        if perfect_scores >= 10:
            achievements_to_award.append('Perfectionist')
        if avg_score >= 80:
            achievements_to_award.append('Consistent')
        if attempts >= 50:
            achievements_to_award.append('Marathoner')
        if avg_score >= 90:
            achievements_to_award.append('Legend')
        
        # Check Climber achievement - user must be in top 10 on leaderboard
        cursor.execute("""
            SELECT s.ID, ROUND((AVG(p.Music_Score) + AVG(p.Academic_Score))/2, 2) as combined_score
            FROM STUDENT s
            INNER JOIN PERFORMANCE p ON s.ID = p.Student_ID
            GROUP BY s.ID
            ORDER BY combined_score DESC, COUNT(p.ID) DESC
            LIMIT 10
        """)
        
        top_10_users = [row[0] for row in cursor.fetchall()]
        if user_id in top_10_users:
            achievements_to_award.append('Climber')
        
        # Award achievements
        for achievement_name in achievements_to_award:
            cursor.execute("SELECT ID FROM ACHIEVEMENTS WHERE Name=%s", (achievement_name,))
            achievement = cursor.fetchone()
            
            if achievement:
                # Check if already awarded
                cursor.execute(
                    "SELECT ID FROM USER_ACHIEVEMENTS WHERE Student_ID=%s AND Achievement_ID=%s",
                    (user_id, achievement[0])
                )
                
                if not cursor.fetchone():
                    # Award new achievement
                    cursor.execute("""
                        INSERT INTO USER_ACHIEVEMENTS (Student_ID, Achievement_ID)
                        VALUES (%s, %s)
                    """, (user_id, achievement[0]))
                    mysql.connection.commit()
                    logger.info(f'User {user_id} earned achievement: {achievement_name}')
        
        cursor.close()
    except Exception as e:
        logger.error(f'Achievement check error: {str(e)}')

# ==================== ADMIN ROUTES ====================

@app.route('/admin')
def admin_dashboard():
    """Admin dashboard - manage questions and view analytics"""
    # Check if user is admin (for now, first user is admin)
    if 'user_id' not in session or session['user_id'] != 1:
        flash('Access denied. Admin only.', 'danger')
        logger.warning(f'Unauthorized admin access attempt by user {session.get("user_id")}')
        return redirect('/login')
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get statistics
        cursor.execute("SELECT COUNT(*) FROM STUDENT")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM QUESTIONS")
        total_questions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM PERFORMANCE")
        total_attempts = cursor.fetchone()[0]
        
        # Get all questions
        cursor.execute("SELECT ID, Question, CorrectAnswer, Difficulty FROM QUESTIONS ORDER BY ID DESC")
        questions = cursor.fetchall()
        
        cursor.close()
        
        return render_template('admin.html', 
                             total_users=total_users,
                             total_questions=total_questions,
                             total_attempts=total_attempts,
                             questions=questions)
    
    except Exception as e:
        logger.error(f'Admin dashboard error: {str(e)}')
        flash('Error loading admin dashboard.', 'danger')
        return redirect('/dashboard')

@app.route('/admin/add_question', methods=['POST'])
def add_question():
    """Add a new question to the database"""
    if 'user_id' not in session or session['user_id'] != 1:
        return redirect('/login')
    
    try:
        question = request.form.get('question', '').strip()
        answer = request.form.get('answer', '').strip()
        difficulty = request.form.get('difficulty', 'medium')
        
        if not question or not answer:
            flash('Question and answer are required.', 'danger')
            return redirect('/admin')
        
        cursor = mysql.connection.cursor()
        cursor.execute("""
            INSERT INTO QUESTIONS (Question, CorrectAnswer, Difficulty, Category)
            VALUES (%s, %s, %s, 'math')
        """, (question, answer, difficulty))
        
        mysql.connection.commit()
        cursor.close()
        
        flash('Question added successfully!', 'success')
        logger.info(f'Admin added new question: {question}')
        
    except Exception as e:
        logger.error(f'Error adding question: {str(e)}')
        flash('Error adding question.', 'danger')
    
    return redirect('/admin')

@app.route('/admin/delete_question/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    """Delete a question from the database"""
    if 'user_id' not in session or session['user_id'] != 1:
        return redirect('/login')
    
    try:
        cursor = mysql.connection.cursor()
        cursor.execute("DELETE FROM QUESTIONS WHERE ID=%s", (question_id,))
        mysql.connection.commit()
        cursor.close()
        
        flash('Question deleted successfully!', 'success')
        logger.info(f'Admin deleted question ID: {question_id}')
        
    except Exception as e:
        logger.error(f'Error deleting question: {str(e)}')
        flash('Error deleting question.', 'danger')
    
    return redirect('/admin')

@app.route('/achievements')
def achievements():
    """View all achievements and user progress"""
    if 'user_id' not in session:
        return redirect('/login')
    
    try:
        cursor = mysql.connection.cursor()
        
        # Get all achievements
        cursor.execute("SELECT ID, Name, Description, Icon FROM ACHIEVEMENTS ORDER BY ID")
        all_achievements = cursor.fetchall()
        
        # Get user's earned achievements
        cursor.execute("""
            SELECT Achievement_ID FROM USER_ACHIEVEMENTS
            WHERE Student_ID=%s
        """, (session['user_id'],))
        
        earned_ids = [row[0] for row in cursor.fetchall()]
        cursor.close()
        
        # Format achievements
        achievements_list = []
        for ach in all_achievements:
            achievements_list.append({
                'id': ach[0],
                'name': ach[1],
                'description': ach[2],
                'icon': ach[3],
                'earned': ach[0] in earned_ids
            })
        
        return render_template('achievements.html', achievements=achievements_list)
        
    except Exception as e:
        logger.error(f'Achievements loading error: {str(e)}')
        flash('Error loading achievements.', 'danger')
        return redirect('/dashboard')

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def page_not_found(error):
    """Handle 404 - Page Not Found"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(error):
    """Handle 500 - Internal Server Error"""
    return render_template('500.html'), 500

@app.errorhandler(403)
def forbidden(error):
    """Handle 403 - Access Forbidden"""
    return render_template('403.html'), 403

# ==================== MAIN ====================

if __name__ == '__main__':
    # Use debug=False for production!
    debug_mode = os.getenv('FLASK_ENV', 'development') == 'development'
    app.run(debug=debug_mode, host='0.0.0.0', port=5000)

