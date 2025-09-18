# app.py – Enhanced Streamlit vocab-quiz app with comprehensive improvements
import streamlit as st
import sqlite3
import pathlib
import datetime as dt
import pytz
import time
import random
import pandas as pd
from PyDictionary import PyDictionary
import bcrypt
import logging
import json
from typing import Optional, List, Tuple, Dict
import plotly.express as px
import plotly.graph_objects as go
from collections import defaultdict

# ---------- CONFIG ----------
st.set_page_config(page_title="📚 Vocab Quiz", page_icon="📚", layout="wide")

# Enhanced CSS with better animations and mobile responsiveness
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background-color: #0e1117;
    }
    [data-testid="stHeader"] {
        background-color: #0e1117;
    }
    [data-testid="stSidebar"] {
        background-color: #1a1c23;
    }
    [data-testid="stMarkdownContainer"] {
        color: #fafafa;
    }
    [data-testid="stExpander"] {
        background-color: #262730;
    }
    .flashcard {
        background: linear-gradient(145deg, #2d3748, #4a5568);
        border-radius: 15px;
        padding: 30px;
        margin: 15px 0;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s ease;
        border: 2px solid #4a5568;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        min-height: 200px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    .flashcard:hover {
        transform: translateY(-8px);
        box-shadow: 0 12px 25px rgba(0,0,0,0.4);
        border-color: #667eea;
    }
    .achievement-badge {
        display: inline-block;
        padding: 8px 15px;
        margin: 5px;
        border-radius: 20px;
        background: linear-gradient(45deg, #667eea, #764ba2);
        color: white;
        font-weight: bold;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        transition: transform 0.2s;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    .new-achievement {
        animation: bounce 0.5s ease-in-out;
    }
    @keyframes bounce {
        0%, 20%, 50%, 80%, 100% { transform: translateY(0); }
        40% { transform: translateY(-10px); }
        60% { transform: translateY(-5px); }
    }
    .wod-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 20px;
        padding: 25px;
        margin-bottom: 25px;
        box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
        border: 1px solid rgba(255,255,255,0.1);
    }
    .stats-card {
        background: linear-gradient(145deg, #2d3748, #4a5568);
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.1);
        transition: transform 0.2s;
    }
    .stats-card:hover {
        transform: translateY(-5px);
    }
    .quiz-word-card {
        background: linear-gradient(145deg, #1a202c, #2d3748);
        border-radius: 15px;
        padding: 20px;
        margin: 10px 0;
        border: 2px solid #4a5568;
        text-align: center;
        transition: all 0.3s ease;
    }
    .quiz-word-card:hover {
        border-color: #667eea;
    }
    .progress-ring {
        transform: rotate(-90deg);
    }
    .loading-spinner {
        border: 4px solid #f3f3f3;
        border-top: 4px solid #667eea;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
        margin: 20px auto;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .error-toast {
        background-color: #fed7d7;
        color: #9b2c2c;
        padding: 10px;
        border-radius: 8px;
        border-left: 4px solid #e53e3e;
        margin: 10px 0;
    }
    .success-toast {
        background-color: #c6f6d5;
        color: #276749;
        padding: 10px;
        border-radius: 8px;
        border-left: 4px solid #38a169;
        margin: 10px 0;
    }
    @media (max-width: 768px) {
        .flashcard {
            padding: 20px;
            min-height: 150px;
        }
        .stats-card {
            padding: 15px;
        }
    }
</style>
""", unsafe_allow_html=True)

# ---------- CONSTANTS ----------
DB_U = pathlib.Path("users.db")
DB_W = pathlib.Path("words.db")
IST = pytz.timezone("Asia/Kolkata")
TODAY_IST = dt.datetime.now(IST).date()

# ---------- LOGGING SETUP ----------
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ---------- DATABASE MANAGER ----------
class DatabaseManager:
    def __init__(self):
        self.conn_u = self.init_user_db()
        self.conn_w = self.init_word_db()
        self.dictionary = PyDictionary()

    def init_user_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_U, check_same_thread=False)
        c = conn.cursor()
        # Enhanced users table
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            username TEXT PRIMARY KEY,
            pwd_hash TEXT NOT NULL,
            streak INTEGER DEFAULT 0,
            total_q INTEGER DEFAULT 0,
            correct INTEGER DEFAULT 0,
            time_spent REAL DEFAULT 0,
            last_quiz_date TEXT,
            points INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT DEFAULT CURRENT_TIMESTAMP,
            study_streak INTEGER DEFAULT 0,
            last_study_date TEXT,
            total_study_time REAL DEFAULT 0
        )""")
        # Enhanced quiz log
        c.execute("""CREATE TABLE IF NOT EXISTS quiz_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            date TEXT NOT NULL,
            quiz_type TEXT NOT NULL,
            length INTEGER NOT NULL,
            correct INTEGER NOT NULL,
            time_spent REAL NOT NULL,
            accuracy REAL,
            points_earned INTEGER DEFAULT 0,
            FOREIGN KEY (username) REFERENCES users(username)
        )""")
        # Word-user relationship with spaced repetition data
        c.execute("""CREATE TABLE IF NOT EXISTS word_user(
            username TEXT NOT NULL,
            word TEXT NOT NULL,
            status TEXT NOT NULL,
            date TEXT NOT NULL,
            attempts INTEGER DEFAULT 1,
            last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
            next_review TEXT,
            ease_factor REAL DEFAULT 2.5,
            interval_days INTEGER DEFAULT 1,
            repetitions INTEGER DEFAULT 0,
            PRIMARY KEY(username, word),
            FOREIGN KEY (username) REFERENCES users(username)
        )""")
        # Social features
        c.execute("""CREATE TABLE IF NOT EXISTS follows(
            follower TEXT NOT NULL,
            following TEXT NOT NULL,
            date_followed TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY(follower, following),
            FOREIGN KEY (follower) REFERENCES users(username),
            FOREIGN KEY (following) REFERENCES users(username)
        )""")
        # Enhanced achievements
        c.execute("""CREATE TABLE IF NOT EXISTS user_achievements(
            username TEXT NOT NULL,
            achievement TEXT NOT NULL,
            date_earned TEXT NOT NULL,
            points_earned INTEGER DEFAULT 0,
            PRIMARY KEY(username, achievement),
            FOREIGN KEY (username) REFERENCES users(username)
        )""")
        # Daily challenges
        c.execute("""CREATE TABLE IF NOT EXISTS daily_challenges(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            challenge_type TEXT NOT NULL,
            target_value INTEGER NOT NULL,
            reward_points INTEGER DEFAULT 50,
            description TEXT
        )""")
        # Challenge completions
        c.execute("""CREATE TABLE IF NOT EXISTS challenge_completions(
            username TEXT NOT NULL,
            challenge_id INTEGER NOT NULL,
            completed_date TEXT NOT NULL,
            points_earned INTEGER DEFAULT 0,
            PRIMARY KEY(username, challenge_id),
            FOREIGN KEY (username) REFERENCES users(username),
            FOREIGN KEY (challenge_id) REFERENCES daily_challenges(id)
        )""")
        # Study sessions
        c.execute("""CREATE TABLE IF NOT EXISTS study_sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            session_type TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            duration REAL,
            cards_reviewed INTEGER DEFAULT 0,
            FOREIGN KEY (username) REFERENCES users(username)
        )""")
        conn.commit()
        return conn

    def init_word_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_W, check_same_thread=False)
        c = conn.cursor()
        # Enhanced words table
        c.execute("""CREATE TABLE IF NOT EXISTS words(
            word TEXT PRIMARY KEY,
            definition TEXT NOT NULL,
            pronunciation TEXT,
            etymology TEXT,
            example1 TEXT,
            example2 TEXT,
            added_by TEXT DEFAULT 'system',
            date_added TEXT DEFAULT CURRENT_TIMESTAMP,
            usage_count INTEGER DEFAULT 0,
            last_used TEXT
        )""")
        # Enhanced suggestions
        c.execute("""CREATE TABLE IF NOT EXISTS suggestions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            username TEXT NOT NULL,
            date TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            reviewed_by TEXT,
            reviewed_date TEXT,
            notes TEXT
        )""")
        conn.commit()
        return conn

    def close_connections(self):
        """Properly close database connections"""
        try:
            self.conn_u.close()
            self.conn_w.close()
        except Exception as e:
            logger.error(f"Error closing connections: {e}")

# ---------- AUTHENTICATION MANAGER ----------
class AuthManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.ensure_default_users()

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    def ensure_default_users(self):
        try:
            # Create demo user
            demo_exists = self.db.conn_u.execute("SELECT 1 FROM users WHERE username='demo'").fetchone()
            if not demo_exists:
                demo_hash = self.hash_password("demo")
                self.db.conn_u.execute(
                    "INSERT INTO users(username, pwd_hash) VALUES(?, ?)", 
                    ("demo", demo_hash)
                )
            # Create admin user
            admin_exists = self.db.conn_u.execute("SELECT 1 FROM users WHERE username='admin'").fetchone()
            if not admin_exists:
                admin_hash = self.hash_password("admin@123")
                self.db.conn_u.execute(
                    "INSERT INTO users(username, pwd_hash) VALUES(?, ?)", 
                    ("admin", admin_hash)
                )
            self.db.conn_u.commit()
        except Exception as e:
            logger.error(f"Error creating default users: {e}")

    def authenticate(self, username: str, password: str) -> bool:
        try:
            user = self.db.conn_u.execute(
                "SELECT pwd_hash FROM users WHERE username=?", 
                (username,)
            ).fetchone()
            if user and self.verify_password(password, user[0]):
                # Update last login
                self.db.conn_u.execute(
                    "UPDATE users SET last_login=? WHERE username=?",
                    (str(dt.datetime.now(IST)), username)
                )
                self.db.conn_u.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    def register(self, username: str, password: str) -> Tuple[bool, str]:
        try:
            if not username or not password:
                return False, "Username and password are required"
            if len(username) < 3:
                return False, "Username must be at least 3 characters"
            if len(password) < 4:
                return False, "Password must be at least 4 characters"
            # Check for invalid characters
            if not username.replace("_", "").replace("-", "").isalnum():
                return False, "Username can only contain letters, numbers, hyphens, and underscores"
            existing = self.db.conn_u.execute(
                "SELECT 1 FROM users WHERE username=?", 
                (username,)
            ).fetchone()
            if existing:
                return False, "Username already taken"
            pwd_hash = self.hash_password(password)
            self.db.conn_u.execute(
                "INSERT INTO users(username, pwd_hash) VALUES(?, ?)",
                (username, pwd_hash)
            )
            self.db.conn_u.commit()
            return True, "Account created successfully"
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return False, "Registration failed"

# ---------- WORD MANAGER ----------
class WordManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def add_word(self, word: str, added_by: str = "admin") -> str:
        word = word.lower().strip()
        if not word or len(word) < 2:
            return "Invalid word"
        if self.db.conn_w.execute("SELECT 1 FROM words WHERE word=?", (word,)).fetchone():
            return "Word already exists"
        try:
            # Get word information with better error handling
            definition_text = "No definition available"
            pronunciation = ""
            examples = []
            try:
                meanings = self.db.dictionary.meaning(word)
                if meanings:
                    definition_parts = []
                    for part_of_speech, definitions in meanings.items():
                        for definition in definitions[:2]:  # Limit to 2 definitions per part
                            definition_parts.append(f"{part_of_speech}: {definition}")
                    definition_text = "; ".join(definition_parts)
            except Exception as e:
                logger.warning(f"Failed to get definition for '{word}': {e}")
            try:
                pronunciation = self.db.dictionary.phonetic(word) or ""
            except Exception as e:
                logger.warning(f"Failed to get pronunciation for '{word}': {e}")
            try:
                sentences = self.db.dictionary.sentence(word)
                if sentences:
                    examples = sentences[:2]
            except Exception as e:
                logger.warning(f"Failed to get examples for '{word}': {e}")
            # Insert word
            self.db.conn_w.execute("""
                INSERT INTO words(word, definition, pronunciation, etymology, example1, example2, added_by, date_added)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                word, definition_text, pronunciation, "",
                examples[0] if examples else "",
                examples[1] if len(examples) > 1 else "",
                added_by, str(TODAY_IST)
            ))
            self.db.conn_w.commit()
            return "Word added successfully"
        except Exception as e:
            logger.error(f"Error adding word '{word}': {e}")
            return f"Error adding word: {str(e)}"

    def get_word_details(self, word: str) -> Optional[Dict]:
        try:
            result = self.db.conn_w.execute("""
                SELECT word, definition, pronunciation, example1, example2, etymology
                FROM words WHERE word=?
            """, (word,)).fetchone()
            if result:
                return {
                    'word': result[0],
                    'definition': result[1],
                    'pronunciation': result[2],
                    'example1': result[3],
                    'example2': result[4],
                    'etymology': result[5]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting word details for '{word}': {e}")
            return None

    def update_word_usage(self, word: str):
        """Update word usage statistics"""
        try:
            self.db.conn_w.execute("""
                UPDATE words 
                SET usage_count = usage_count + 1, last_used = ?
                WHERE word = ?
            """, (str(TODAY_IST), word))
            self.db.conn_w.commit()
        except Exception as e:
            logger.error(f"Error updating word usage for '{word}': {e}")

# ---------- SPACED REPETITION SYSTEM ----------
class SpacedRepetitionManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def calculate_next_review(self, ease_factor: float, interval_days: int, repetitions: int, quality: int) -> Tuple[int, float, int]:
        """
        Calculate next review interval using SM-2 algorithm
        quality: 0-5 (0=total blackout, 5=perfect response)
        """
        repetitions += 1
        if quality < 3:
            # Reset if quality is poor
            repetitions = 0
            interval_days = 1
        else:
            if repetitions <= 2:
                interval_days = 1 if repetitions == 1 else 6
            else:
                interval_days = int(interval_days * ease_factor)
        # Update ease factor
        ease_factor = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ease_factor = max(1.3, ease_factor)  # Minimum ease factor
        return interval_days, ease_factor, repetitions

    def update_word_memory(self, username: str, word: str, quality: int):
        """Update spaced repetition data for a word"""
        try:
            # Get current data
            result = self.db.conn_u.execute("""
                SELECT ease_factor, interval_days, repetitions
                FROM word_user
                WHERE username = ? AND word = ?
            """, (username, word)).fetchone()
            if result:
                ease_factor, interval_days, repetitions = result
            else:
                ease_factor, interval_days, repetitions = 2.5, 1, 0
            # Calculate next review
            new_interval, new_ease, new_repetitions = self.calculate_next_review(
                ease_factor, interval_days, repetitions, quality
            )
            # Calculate next review date
            next_review_date = TODAY_IST + dt.timedelta(days=new_interval)
            # Update database
            self.db.conn_u.execute("""
                UPDATE word_user
                SET ease_factor = ?, interval_days = ?, repetitions = ?, 
                    next_review = ?, last_seen = ?
                WHERE username = ? AND word = ?
            """, (new_ease, new_interval, new_repetitions, 
                  str(next_review_date), str(TODAY_IST), username, word))
            self.db.conn_u.commit()
        except Exception as e:
            logger.error(f"Error updating word memory: {e}")

    def get_due_words(self, username: str, limit: int = 20) -> List[str]:
        """Get words due for review"""
        try:
            result = self.db.conn_u.execute("""
                SELECT word FROM word_user
                WHERE username = ? AND status = 'known'
                AND (next_review IS NULL OR next_review <= ?)
                ORDER BY last_seen ASC
                LIMIT ?
            """, (username, str(TODAY_IST), limit)).fetchall()
            return [word for word, in result]
        except Exception as e:
            logger.error(f"Error getting due words: {e}")
            return []

# ---------- GAMIFICATION MANAGER ----------
class GamificationManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.achievements_config = {
            # Points-based achievements
            "🥉 First Century": {"type": "points", "threshold": 100, "points": 50},
            "🥈 Half Millennium": {"type": "points", "threshold": 500, "points": 100},
            "🥇 Millennium Master": {"type": "points", "threshold": 1000, "points": 200},
            "💎 Point Collector": {"type": "points", "threshold": 2000, "points": 300},
            "🚀 Sky High": {"type": "points", "threshold": 5000, "points": 500},
            # Streak achievements
            "🔥 Week Streak": {"type": "streak", "threshold": 7, "points": 70},
            "⭐ Monthly Master": {"type": "streak", "threshold": 30, "points": 300},
            "👑 Century Streak": {"type": "streak", "threshold": 100, "points": 1000},
            # Knowledge achievements
            "📚 Vocabulary Builder": {"type": "known", "threshold": 50, "points": 100},
            "🎓 Word Scholar": {"type": "known", "threshold": 200, "points": 300},
            "🧠 Lexicon Legend": {"type": "known", "threshold": 500, "points": 500},
            "📖 Dictionary Master": {"type": "known", "threshold": 1000, "points": 1000},
            # Quiz achievements
            "🎯 Perfect Score": {"type": "perfect_quiz", "threshold": 1, "points": 50},
            "⚡ Speed Demon": {"type": "fast_quiz", "threshold": 1, "points": 30},
            "📊 Quiz Master": {"type": "total_quizzes", "threshold": 50, "points": 200},
            "🏃 Marathon Runner": {"type": "total_quizzes", "threshold": 100, "points": 400},
            # Study achievements
            "📝 Dedicated Learner": {"type": "study_time", "threshold": 3600, "points": 150},  # 1 hour
            "⏰ Time Master": {"type": "study_time", "threshold": 18000, "points": 500},  # 5 hours
            # Social achievements
            "👥 Social Butterfly": {"type": "followers", "threshold": 5, "points": 100},
            "🌟 Influencer": {"type": "followers", "threshold": 20, "points": 300},
        }

    def calculate_level(self, points: int) -> int:
        return min(int(points / 100) + 1, 50)

    def get_level_progress(self, points: int) -> Tuple[int, int, float]:
        level = self.calculate_level(points)
        next_threshold = level * 100
        current_progress = points % 100 if points % 100 != 0 else 100
        progress_ratio = current_progress / 100
        return level, next_threshold, progress_ratio

    def award_achievements(self, username: str) -> List[str]:
        try:
            # Get comprehensive user stats
            user_stats = self.db.conn_u.execute("""
                SELECT points, streak, correct, total_q, total_study_time
                FROM users WHERE username=?
            """, (username,)).fetchone()
            if not user_stats:
                return []
            points, streak, known_words, total_quizzes, study_time = user_stats
            # Get followers count
            followers_count = len(self.db.conn_u.execute(
                "SELECT follower FROM follows WHERE following=?", 
                (username,)
            ).fetchall())
            # Get existing achievements
            existing = {ach for ach, in self.db.conn_u.execute(
                "SELECT achievement FROM user_achievements WHERE username=?", 
                (username,)
            ).fetchall()}
            new_achievements = []
            for achievement, config in self.achievements_config.items():
                if achievement in existing:
                    continue
                should_award = False
                if config["type"] == "points" and points >= config["threshold"]:
                    should_award = True
                elif config["type"] == "streak" and streak >= config["threshold"]:
                    should_award = True
                elif config["type"] == "known" and known_words >= config["threshold"]:
                    should_award = True
                elif config["type"] == "total_quizzes" and total_quizzes >= config["threshold"]:
                    should_award = True
                elif config["type"] == "study_time" and study_time >= config["threshold"]:
                    should_award = True
                elif config["type"] == "followers" and followers_count >= config["threshold"]:
                    should_award = True
                if should_award:
                    self.db.conn_u.execute("""
                        INSERT INTO user_achievements(username, achievement, date_earned, points_earned)
                        VALUES(?, ?, ?, ?)
                    """, (username, achievement, str(TODAY_IST), config["points"]))
                    # Add bonus points
                    self.db.conn_u.execute(
                        "UPDATE users SET points = points + ? WHERE username = ?",
                        (config["points"], username)
                    )
                    new_achievements.append(achievement)
            if new_achievements:
                self.db.conn_u.commit()
            return new_achievements
        except Exception as e:
            logger.error(f"Error awarding achievements: {e}")
            return []

    def create_daily_challenge(self) -> bool:
        """Create daily challenge if it doesn't exist for today"""
        try:
            existing = self.db.conn_u.execute(
                "SELECT 1 FROM daily_challenges WHERE date=?",
                (str(TODAY_IST),)
            ).fetchone()
            if existing:
                return False
            # Create a random challenge
            challenges = [
                {"type": "quiz_words", "target": 20, "reward": 100, "desc": "Complete a 20-word quiz"},
                {"type": "perfect_quiz", "target": 1, "reward": 150, "desc": "Get 100% on any quiz"},
                {"type": "study_time", "target": 1800, "reward": 80, "desc": "Study for 30 minutes"},
                {"type": "learn_new", "target": 10, "reward": 120, "desc": "Learn 10 new words"},
            ]
            challenge = random.choice(challenges)
            self.db.conn_u.execute("""
                INSERT INTO daily_challenges(date, challenge_type, target_value, reward_points, description)
                VALUES(?, ?, ?, ?, ?)
            """, (str(TODAY_IST), challenge["type"], challenge["target"], 
                  challenge["reward"], challenge["desc"]))
            self.db.conn_u.commit()
            return True
        except Exception as e:
            logger.error(f"Error creating daily challenge: {e}")
            return False

    def get_daily_challenge(self) -> Optional[Dict]:
        """Get today's challenge"""
        try:
            result = self.db.conn_u.execute("""
                SELECT id, challenge_type, target_value, reward_points, description
                FROM daily_challenges WHERE date=?
            """, (str(TODAY_IST),)).fetchone()
            if result:
                return {
                    'id': result[0],
                    'type': result[1],
                    'target': result[2],
                    'reward': result[3],
                    'description': result[4]
                }
            return None
        except Exception as e:
            logger.error(f"Error getting daily challenge: {e}")
            return None

    def check_challenge_completion(self, username: str) -> Optional[str]:
        """Check if user completed today's challenge"""
        try:
            challenge = self.get_daily_challenge()
            if not challenge:
                return None
            # Check if already completed
            completed = self.db.conn_u.execute("""
                SELECT 1 FROM challenge_completions 
                WHERE username=? AND challenge_id=?
            """, (username, challenge['id'])).fetchone()
            if completed:
                return None
            # Check completion based on challenge type
            completed_now = False
            if challenge['type'] == 'quiz_words':
                # Check if user completed enough quiz words today
                total_today = self.db.conn_u.execute("""
                    SELECT SUM(length) FROM quiz_log 
                    WHERE username=? AND date=?
                """, (username, str(TODAY_IST))).fetchone()[0] or 0
                if total_today >= challenge['target']:
                    completed_now = True
            elif challenge['type'] == 'perfect_quiz':
                # Check for perfect quiz today
                perfect_quiz = self.db.conn_u.execute("""
                    SELECT 1 FROM quiz_log 
                    WHERE username=? AND date=? AND accuracy=100
                    LIMIT 1
                """, (username, str(TODAY_IST))).fetchone()
                if perfect_quiz:
                    completed_now = True
            elif challenge['type'] == 'study_time':
                # Check study time today
                study_time_today = self.db.conn_u.execute("""
                    SELECT SUM(duration) FROM study_sessions 
                    WHERE username=? AND DATE(start_time)=?
                """, (username, str(TODAY_IST))).fetchone()[0] or 0
                if study_time_today >= challenge['target']:
                    completed_now = True
            elif challenge['type'] == 'learn_new':
                # Check new words learned today
                new_words_today = self.db.conn_u.execute("""
                    SELECT COUNT(*) FROM word_user 
                    WHERE username=? AND date=? AND status='known'
                """, (username, str(TODAY_IST))).fetchone()[0] or 0
                if new_words_today >= challenge['target']:
                    completed_now = True
            if completed_now:
                # Mark as completed and award points
                self.db.conn_u.execute("""
                    INSERT INTO challenge_completions(username, challenge_id, completed_date, points_earned)
                    VALUES(?, ?, ?, ?)
                """, (username, challenge['id'], str(TODAY_IST), challenge['reward']))
                self.db.conn_u.execute("""
                    UPDATE users SET points = points + ? WHERE username = ?
                """, (challenge['reward'], username))
                self.db.conn_u.commit()
                return f"🎉 Challenge completed! Earned {challenge['reward']} points!"
            return None
        except Exception as e:
            logger.error(f"Error checking challenge completion: {e}")
            return None

# ---------- QUIZ MANAGER ----------
class QuizManager:
    def __init__(self, db_manager: DatabaseManager, word_manager: WordManager):
        self.db = db_manager
        self.word_manager = word_manager

    def get_quiz_words(self, quiz_type: str, length: int, username: str = None) -> List[Dict]:
        """Get words for quiz based on type"""
        try:
            if quiz_type == "random":
                # Get random words
                words = self.db.conn_w.execute("""
                    SELECT word FROM words ORDER BY RANDOM() LIMIT ?
                """, (length,)).fetchall()
            elif quiz_type == "review" and username:
                # Get words user got wrong
                words = self.db.conn_u.execute("""
                    SELECT DISTINCT word FROM word_user 
                    WHERE username=? AND status='wrong'
                    ORDER BY RANDOM() LIMIT ?
                """, (username, length)).fetchall()
                if len(words) < length:
                    # Fill with random words if not enough review words
                    remaining = length - len(words)
                    extra_words = self.db.conn_w.execute("""
                        SELECT word FROM words WHERE word NOT IN (
                            SELECT word FROM word_user WHERE username=?
                        ) ORDER BY RANDOM() LIMIT ?
                    """, (username, remaining)).fetchall()
                    words.extend(extra_words)
            elif quiz_type == "spaced" and username:
                # Get words due for spaced repetition
                sr_manager = SpacedRepetitionManager(self.db)
                due_words = sr_manager.get_due_words(username, length)
                words = [(word,) for word in due_words]
                if len(words) < length:
                    # Fill with random words
                    remaining = length - len(words)
                    extra_words = self.db.conn_w.execute("""
                        SELECT word FROM words ORDER BY RANDOM() LIMIT ?
                    """, (remaining,)).fetchall()
                    words.extend(extra_words)
            else:
                # Default to random
                words = self.db.conn_w.execute("""
                    SELECT word FROM words ORDER BY RANDOM() LIMIT ?
                """, (length,)).fetchall()
            # Get word details and create quiz questions
            quiz_words = []
            for word, in words[:length]:
                word_details = self.word_manager.get_word_details(word)
                if word_details:
                    # Generate multiple choice options
                    correct_def = word_details['definition']
                    # Get 3 wrong definitions
                    wrong_defs = self.db.conn_w.execute("""
                        SELECT definition FROM words 
                        WHERE word != ? AND definition != ?
                        ORDER BY RANDOM() LIMIT 3
                    """, (word, correct_def)).fetchall()
                    options = [correct_def] + [def_text for def_text, in wrong_defs]
                    random.shuffle(options)
                    quiz_words.append({
                        'word': word,
                        'definition': correct_def,
                        'options': options,
                        'correct_index': options.index(correct_def),
                        'pronunciation': word_details.get('pronunciation', ''),
                        'examples': [word_details.get('example1', ''), word_details.get('example2', '')]
                    })
                    # Update word usage
                    self.word_manager.update_word_usage(word)
            return quiz_words
        except Exception as e:
            logger.error(f"Error getting quiz words: {e}")
            return []

    def save_quiz_result(self, username: str, quiz_type: str, length: int, 
                        correct: int, time_spent: float, words_attempted: List[Dict]):
        """Save quiz results to database"""
        try:
            accuracy = (correct / length * 100) if length > 0 else 0
            points_earned = self.calculate_quiz_points(correct, length, time_spent, accuracy)
            # Save quiz log
            self.db.conn_u.execute("""
                INSERT INTO quiz_log(username, date, quiz_type, length, correct, 
                                   time_spent, accuracy, points_earned)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            """, (username, str(TODAY_IST), quiz_type, length, correct, 
                  time_spent, accuracy, points_earned))
            # Update user stats
            self.db.conn_u.execute("""
                UPDATE users 
                SET total_q = total_q + ?, correct = correct + ?, 
                    time_spent = time_spent + ?, points = points + ?,
                    last_quiz_date = ?
                WHERE username = ?
            """, (length, correct, time_spent, points_earned, str(TODAY_IST), username))
            # Update streak
            self.update_streak(username)
            # Save individual word results
            for word_data in words_attempted:
                word = word_data['word']
                is_correct = word_data['is_correct']
                status = 'known' if is_correct else 'wrong'
                # Insert or update word-user relationship
                self.db.conn_u.execute("""
                    INSERT OR REPLACE INTO word_user(username, word, status, date, attempts, last_seen)
                    VALUES(?, ?, ?, ?, 
                           COALESCE((SELECT attempts FROM word_user WHERE username=? AND word=?), 0) + 1,
                           ?)
                """, (username, word, status, str(TODAY_IST), username, word, str(TODAY_IST)))
                # Update spaced repetition if applicable
                if quiz_type == "spaced":
                    sr_manager = SpacedRepetitionManager(self.db)
                    quality = 5 if is_correct else 2
                    sr_manager.update_word_memory(username, word, quality)
            self.db.conn_u.commit()
            return points_earned
        except Exception as e:
            logger.error(f"Error saving quiz result: {e}")
            return 0

    def calculate_quiz_points(self, correct: int, total: int, time_spent: float, accuracy: float) -> int:
        """Calculate points earned from quiz"""
        base_points = correct * 10
        # Accuracy bonus
        if accuracy == 100:
            base_points += 50  # Perfect score bonus
        elif accuracy >= 80:
            base_points += 20  # High accuracy bonus
        # Speed bonus (if completed quickly)
        if time_spent < total * 5:  # Less than 5 seconds per question
            base_points += 25
        return max(base_points, 0)

    def update_streak(self, username: str):
        """Update user's quiz streak"""
        try:
            # Get last quiz date
            last_quiz = self.db.conn_u.execute(
                "SELECT last_quiz_date FROM users WHERE username=?",
                (username,)
            ).fetchone()
            if last_quiz and last_quiz[0]:
                last_date = dt.datetime.strptime(last_quiz[0], '%Y-%m-%d').date()
                days_diff = (TODAY_IST - last_date).days
                if days_diff == 0:
                    # Same day, no change to streak
                    return
                elif days_diff == 1:
                    # Consecutive day, increment streak
                    self.db.conn_u.execute(
                        "UPDATE users SET streak = streak + 1 WHERE username = ?",
                        (username,)
                    )
                else:
                    # Streak broken, reset to 1
                    self.db.conn_u.execute(
                        "UPDATE users SET streak = 1 WHERE username = ?",
                        (username,)
                    )
            else:
                # First quiz, set streak to 1
                self.db.conn_u.execute(
                    "UPDATE users SET streak = 1 WHERE username = ?",
                    (username,)
                )
            self.db.conn_u.commit()
        except Exception as e:
            logger.error(f"Error updating streak: {e}")

# ---------- ANALYTICS MANAGER ----------
class AnalyticsManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_user_stats(self, username: str) -> Dict:
        """Get comprehensive user statistics"""
        try:
            # Basic stats
            user_data = self.db.conn_u.execute("""
                SELECT points, streak, total_q, correct, time_spent, 
                       total_study_time, study_streak, created_at
                FROM users WHERE username=?
            """, (username,)).fetchone()
            if not user_data:
                return {}
            points, streak, total_q, correct, time_spent, study_time, study_streak, created_at = user_data
            # Calculate derived stats
            accuracy = (correct / total_q * 100) if total_q > 0 else 0
            avg_time_per_q = time_spent / total_q if total_q > 0 else 0
            # Get level info
            gam_manager = GamificationManager(self.db)
            level, next_threshold, progress = gam_manager.get_level_progress(points)
            # Get achievements
            achievements = self.db.conn_u.execute("""
                SELECT achievement, date_earned FROM user_achievements 
                WHERE username=? ORDER BY date_earned DESC
            """, (username,)).fetchall()
            # Get quiz history (last 30 days)
            thirty_days_ago = (TODAY_IST - dt.timedelta(days=30)).strftime('%Y-%m-%d')
            quiz_history = self.db.conn_u.execute("""
                SELECT date, accuracy, points_earned FROM quiz_log 
                WHERE username=? AND date >= ?
                ORDER BY date DESC
            """, (username, thirty_days_ago)).fetchall()
            # Get word stats
            known_words = self.db.conn_u.execute("""
                SELECT COUNT(*) FROM word_user 
                WHERE username=? AND status='known'
            """, (username,)).fetchone()[0]
            wrong_words = self.db.conn_u.execute("""
                SELECT COUNT(*) FROM word_user 
                WHERE username=? AND status='wrong'
            """, (username,)).fetchone()[0]
            # Get followers/following
            followers = len(self.db.conn_u.execute(
                "SELECT follower FROM follows WHERE following=?", (username,)
            ).fetchall())
            following = len(self.db.conn_u.execute(
                "SELECT following FROM follows WHERE follower=?", (username,)
            ).fetchall())
            return {
                'points': points,
                'level': level,
                'progress_to_next': progress,
                'streak': streak,
                'study_streak': study_streak,
                'total_quizzes': total_q,
                'correct_answers': correct,
                'accuracy': round(accuracy, 1),
                'time_spent': time_spent,
                'study_time': study_time or 0,
                'avg_time_per_question': round(avg_time_per_q, 1),
                'known_words': known_words,
                'wrong_words': wrong_words,
                'achievements': achievements,
                'quiz_history': quiz_history,
                'followers': followers,
                'following': following,
                'member_since': created_at
            }
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return {}

    def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get leaderboard data"""
        try:
            users = self.db.conn_u.execute("""
                SELECT username, points, streak, total_q, correct
                FROM users 
                ORDER BY points DESC, streak DESC
                LIMIT ?
            """, (limit,)).fetchall()
            leaderboard = []
            for i, (username, points, streak, total_q, correct) in enumerate(users, 1):
                accuracy = (correct / total_q * 100) if total_q > 0 else 0
                level = GamificationManager(self.db).calculate_level(points)
                leaderboard.append({
                    'rank': i,
                    'username': username,
                    'points': points,
                    'level': level,
                    'streak': streak,
                    'accuracy': round(accuracy, 1),
                    'total_quizzes': total_q
                })
            return leaderboard
        except Exception as e:
            logger.error(f"Error getting leaderboard: {e}")
            return []

# ---------- INITIALIZE MANAGERS ----------
@st.cache_resource
def initialize_managers():
    """Initialize all managers with caching"""
    try:
        db_manager = DatabaseManager()
        auth_manager = AuthManager(db_manager)
        word_manager = WordManager(db_manager)
        quiz_manager = QuizManager(db_manager, word_manager)
        gamification_manager = GamificationManager(db_manager)
        analytics_manager = AnalyticsManager(db_manager)
        sr_manager = SpacedRepetitionManager(db_manager)
        return {
            'db': db_manager,
            'auth': auth_manager,
            'word': word_manager,
            'quiz': quiz_manager,
            'gamification': gamification_manager,
            'analytics': analytics_manager,
            'spaced_repetition': sr_manager
        }
    except Exception as e:
        logger.error(f"Error initializing managers: {e}")
        st.error("Failed to initialize application. Please refresh the page.")
        st.stop()

# Get managers
managers = initialize_managers()

# ---------- UI HELPER FUNCTIONS ----------
def show_word_of_the_day():
    """Display word of the day"""
    try:
        # Get a random word for today (seeded by date for consistency)
        random.seed(str(TODAY_IST))
        word_data = managers['db'].conn_w.execute("""
            SELECT word, definition, pronunciation, example1 
            FROM words ORDER BY RANDOM() LIMIT 1
        """).fetchone()
        if word_data:
            word, definition, pronunciation, example = word_data
            st.markdown(f"""
            <div class="wod-container">
                <h2 style="color: white; margin: 0 0 10px 0;">📚 Word of the Day</h2>
                <h1 style="color: white; margin: 0 0 5px 0; font-size: 2.5em;">{word.title()}</h1>
                <p style="color: #e0e0e0; margin: 0 0 15px 0; font-style: italic;">{pronunciation}</p>
                <p style="color: white; margin: 0 0 10px 0; font-size: 1.1em;">{definition}</p>
                {f'<p style="color: #f0f0f0; margin: 0; font-style: italic;">"{example}"</p>' if example else ''}
            </div>
            """, unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"Error showing word of the day: {e}")

def show_achievements_section(username: str):
    """Display user achievements"""
    try:
        # Check for new achievements
        new_achievements = managers['gamification'].award_achievements(username)
        if new_achievements:
            st.balloons()
            for achievement in new_achievements:
                st.success(f"🎉 New Achievement Unlocked: **{achievement}**!")
        # Show all achievements
        achievements = managers['db'].conn_u.execute("""
            SELECT achievement, date_earned FROM user_achievements 
            WHERE username=? ORDER BY date_earned DESC
        """, (username,)).fetchall()
        if achievements:
            st.markdown("### 🏆 Your Achievements")
            # Group achievements by date
            achievement_html = ""
            for achievement, date_earned in achievements:
                badge_class = "new-achievement" if achievement in new_achievements else ""
                achievement_html += f'<span class="achievement-badge {badge_class}">{achievement}</span>'
            st.markdown(f'<div style="margin: 20px 0;">{achievement_html}</div>', unsafe_allow_html=True)
    except Exception as e:
        logger.error(f"Error showing achievements: {e}")

def show_daily_challenge(username: str):
    """Display daily challenge"""
    try:
        # Create challenge if it doesn't exist
        managers['gamification'].create_daily_challenge()
        challenge = managers['gamification'].get_daily_challenge()
        if challenge:
            # Check if completed
            completed = managers['db'].conn_u.execute("""
                SELECT 1 FROM challenge_completions 
                WHERE username=? AND challenge_id=?
            """, (username, challenge['id'])).fetchone()
            status_icon = "✅" if completed else "⏳"
            status_text = "Completed!" if completed else "In Progress"
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"""
                **🎯 Daily Challenge:** {challenge['description']}  
                **Reward:** {challenge['reward']} points
                """)
            with col2:
                st.markdown(f"**{status_icon} {status_text}**")
            # Check completion
            completion_msg = managers['gamification'].check_challenge_completion(username)
            if completion_msg:
                st.success(completion_msg)
    except Exception as e:
        logger.error(f"Error showing daily challenge: {e}")

def create_progress_ring(value: float, max_value: float, label: str, color: str = "#667eea"):
    """Create a circular progress indicator"""
    progress = min(value / max_value, 1.0) if max_value > 0 else 0
    return f"""
    <div style="text-align: center; margin: 20px;">
        <svg width="120" height="120" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r="50" fill="none" stroke="#2d3748" stroke-width="10"/>
            <circle cx="60" cy="60" r="50" fill="none" stroke="{color}" 
                    stroke-width="10" stroke-dasharray="{progress * 314.16} 314.16"
                    class="progress-ring" stroke-linecap="round"/>
            <text x="60" y="65" text-anchor="middle" fill="white" font-size="16" font-weight="bold">
                {int(value)}
            </text>
        </svg>
        <div style="color: white; font-weight: bold; margin-top: 10px;">{label}</div>
    </div>
    """

# ---------- MAIN APPLICATION ----------
def main():
    """Main application logic"""
    # Initialize session state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'quiz_active' not in st.session_state:
        st.session_state.quiz_active = False
    if 'quiz_data' not in st.session_state:
        st.session_state.quiz_data = {}

    # Show login/register if not logged in
    if not st.session_state.logged_in:
        show_auth_page()
        return

    # Main app content
    username = st.session_state.username
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown(f"### Welcome, **{username}**! 👋")
        # User level and progress
        user_stats = managers['analytics'].get_user_stats(username)
        if user_stats:
            level = user_stats['level']
            progress = user_stats['progress_to_next']
            points = user_stats['points']
            st.markdown(f"""
            **Level:** {level} ⭐  
            **Points:** {points} 💎  
            **Streak:** {user_stats['streak']} 🔥
            """)
            # Progress bar
            st.progress(progress)
        st.markdown("---")
        # Navigation
        page = st.selectbox("Navigate to:", [
            "🏠 Dashboard",
            "📝 Take Quiz",
            "🔄 Spaced Repetition",
            "📊 Flashcards",
            "📈 Analytics", 
            "🏆 Leaderboard",
            "➕ Add Words",
            "⚙️ Settings"
        ])
        st.markdown("---")
        # Quick stats
        if user_stats:
            st.markdown("### Quick Stats")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Known Words", user_stats['known_words'])
                st.metric("Accuracy", f"{user_stats['accuracy']}%")
            with col2:
                st.metric("Total Quizzes", user_stats['total_quizzes'])
                st.metric("Study Time", f"{user_stats['study_time']//3600:.0f}h")
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()

    # Main content based on selected page
    if page == "🏠 Dashboard":
        show_dashboard(username)
    elif page == "📝 Take Quiz":
        show_quiz_page(username)
    elif page == "🔄 Spaced Repetition":
        show_spaced_repetition(username)
    elif page == "📊 Flashcards":
        show_flashcards(username)
    elif page == "📈 Analytics":
        show_analytics(username)
    elif page == "🏆 Leaderboard":
        show_leaderboard()
    elif page == "➕ Add Words":
        show_add_words(username)
    elif page == "⚙️ Settings":
        show_settings(username)

def show_auth_page():
    """Show login/register page"""
    st.markdown("# 📚 Vocabulary Quiz App")
    st.markdown("### Learn, Practice, and Master New Words!")
    tab1, tab2 = st.tabs(["🔑 Login", "📝 Register"])
    
    with tab1:
        with st.form("login_form"):
            st.markdown("### Welcome Back!")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            col1, col2 = st.columns(2)
            with col1:
                login_btn = st.form_submit_button("🚀 Login", use_container_width=True)
            with col2:
                demo_btn = st.form_submit_button("👤 Demo User", use_container_width=True)
            if login_btn:
                if managers['auth'].authenticate(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error("❌ Invalid credentials")
            if demo_btn:
                if managers['auth'].authenticate("demo", "demo"):
                    st.session_state.logged_in = True
                    st.session_state.username = "demo"
                    st.success("✅ Logged in as demo user!")
                    st.rerun()
                    
    with tab2:
        with st.form("register_form"):
            st.markdown("### Join the Community!")
            new_username = st.text_input("Choose Username")
            new_password = st.text_input("Choose Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            register_btn = st.form_submit_button("🎉 Create Account", use_container_width=True)
            if register_btn:
                if new_password != confirm_password:
                    st.error("❌ Passwords don't match")
                else:
                    success, message = managers['auth'].register(new_username, new_password)
                    if success:
                        st.success(f"✅ {message}")
                        st.info("You can now log in with your credentials!")
                    else:
                        st.error(f"❌ {message}")

def show_dashboard(username: str):
    """Show main dashboard"""
    st.markdown("# 🏠 Dashboard")
    # Word of the day
    show_word_of_the_day()
    # Daily challenge
    with st.expander("🎯 Daily Challenge", expanded=True):
        show_daily_challenge(username)
    # User stats overview
    user_stats = managers['analytics'].get_user_stats(username)
    if user_stats:
        st.markdown("### 📊 Your Progress")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown(create_progress_ring(
                user_stats['level'], 50, f"Level {user_stats['level']}", "#667eea"
            ), unsafe_allow_html=True)
        with col2:
            st.markdown(create_progress_ring(
                user_stats['streak'], max(user_stats['streak'] + 10, 30), 
                f"{user_stats['streak']} Day Streak", "#f093fb"
            ), unsafe_allow_html=True)
        with col3:
            accuracy_color = "#4ade80" if user_stats['accuracy'] >= 80 else "#fbbf24" if user_stats['accuracy'] >= 60 else "#ef4444"
            st.markdown(create_progress_ring(
                user_stats['accuracy'], 100, f"{user_stats['accuracy']}% Accuracy", accuracy_color
            ), unsafe_allow_html=True)
        with col4:
            st.markdown(create_progress_ring(
                user_stats['known_words'], max(user_stats['known_words'] + 50, 100),
                f"{user_stats['known_words']} Known", "#06d6a0"
            ), unsafe_allow_html=True)
    # Recent achievements
    show_achievements_section(username)
    # Quick actions
    st.markdown("### ⚡ Quick Actions")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🎯 Quick Quiz (10 words)", use_container_width=True):
            st.session_state.quiz_active = True
            st.session_state.quiz_data = {
                'type': 'random',
                'length': 10,
                'words': managers['quiz'].get_quiz_words('random', 10, username),
                'current': 0,
                'score': 0,
                'start_time': time.time(),
                'answers': []
            }
            st.rerun()
    with col2:
        if st.button("🔄 Review Wrong Words", use_container_width=True):
            wrong_count = managers['db'].conn_u.execute("""
                SELECT COUNT(*) FROM word_user WHERE username=? AND status='wrong'
            """, (username,)).fetchone()[0]
            if wrong_count > 0:
                st.session_state.quiz_active = True
                st.session_state.quiz_data = {
                    'type': 'review',
                    'length': min(wrong_count, 15),
                    'words': managers['quiz'].get_quiz_words('review', min(wrong_count, 15), username),
                    'current': 0,
                    'score': 0,
                    'start_time': time.time(),
                    'answers': []
                }
                st.rerun()
            else:
                st.info("No words to review! Take some quizzes first.")
    with col3:
        if st.button("📖 Study Flashcards", use_container_width=True):
            st.session_state.current_page = "Flashcards"
            st.rerun()

def show_quiz_page(username: str):
    """Handle the quiz functionality"""
    if not st.session_state.quiz_active:
        st.markdown("# 📝 Take a Quiz")
        st.markdown("### Choose your quiz settings")
        with st.form("quiz_settings"):
            col1, col2 = st.columns(2)
            with col1:
                quiz_type = st.selectbox("Quiz Type", ["Random Words", "Review Mistakes", "Spaced Repetition"])
            with col2:
                quiz_length = st.slider("Number of Questions", 5, 50, 10)
            start_quiz = st.form_submit_button("🚀 Start Quiz")
            if start_quiz:
                type_map = {"Random Words": "random", "Review Mistakes": "review", "Spaced Repetition": "spaced"}
                selected_type = type_map[quiz_type]
                quiz_words = managers['quiz'].get_quiz_words(selected_type, quiz_length, username)
                if quiz_words:
                    st.session_state.quiz_active = True
                    st.session_state.quiz_data = {
                        'type': selected_type,
                        'length': len(quiz_words),
                        'words': quiz_words,
                        'current': 0,
                        'score': 0,
                        'start_time': time.time(),
                        'answers': []
                    }
                    st.rerun()
                else:
                    st.error("Could not generate quiz. Please try again.")
    else:
        # Active quiz
        quiz_data = st.session_state.quiz_data
        current_q = quiz_data['current']
        if current_q < quiz_data['length']:
            word_data = quiz_data['words'][current_q]
            st.markdown(f"# 📝 Quiz in Progress")
            st.markdown(f"### Question {current_q + 1} of {quiz_data['length']}")
            st.markdown(f"**Word:** {word_data['word'].title()}")
            if word_data['pronunciation']:
                st.markdown(f"*Pronunciation:* {word_data['pronunciation']}")
            # Display examples if available
            if any(word_data['examples']):
                with st.expander("💡 Examples"):
                    for example in word_data['examples']:
                        if example:
                            st.markdown(f"- {example}")
            # Quiz options
            user_choice = st.radio("Choose the correct definition:", word_data['options'], index=None)
            # Navigation buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⬅️ Previous" if current_q > 0 else "🏠 Home", use_container_width=True):
                    if current_q > 0:
                        st.session_state.quiz_data['current'] -= 1
                    else:
                        st.session_state.quiz_active = False
                        st.session_state.quiz_data = {}
                    st.rerun()
            with col2:
                next_button = st.button("➡️ Next" if current_q < quiz_data['length'] - 1 else "🏁 Finish Quiz", use_container_width=True)
                if next_button:
                    if user_choice is not None:
                        is_correct = (word_data['options'].index(user_choice) == word_data['correct_index'])
                        st.session_state.quiz_data['answers'].append({
                            'word': word_data['word'],
                            'chosen': user_choice,
                            'correct': word_data['definition'],
                            'is_correct': is_correct
                        })
                        if is_correct:
                            st.session_state.quiz_data['score'] += 1
                        st.session_state.quiz_data['current'] += 1
                        st.rerun()
                    else:
                        st.warning("Please select an answer before proceeding.")
        else:
            # Quiz finished
            end_time = time.time()
            time_spent = end_time - quiz_data['start_time']
            correct = quiz_data['score']
            total = quiz_data['length']
            accuracy = (correct / total) * 100
            points_earned = managers['quiz'].save_quiz_result(
                username, quiz_data['type'], total, correct, time_spent, quiz_data['answers']
            )
            st.markdown("# 🎉 Quiz Completed!")
            st.markdown(f"### 🏆 Your Score: {correct}/{total} ({accuracy:.1f}%)")
            st.markdown(f"**⏱️ Time Spent:** {time_spent:.1f} seconds")
            st.markdown(f"**💎 Points Earned:** {points_earned}")
            # Award achievements
            new_achievements = managers['gamification'].award_achievements(username)
            if new_achievements:
                st.balloons()
                for ach in new_achievements:
                    st.success(f"🎉 New Achievement: **{ach}**!")
            # Show incorrect answers
            incorrect_answers = [ans for ans in quiz_data['answers'] if not ans['is_correct']]
            if incorrect_answers:
                st.markdown("### ❌ Review Incorrect Answers")
                for ans in incorrect_answers:
                    st.markdown(f"**{ans['word'].title()}:** {ans['correct']}")
            # Buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🏠 Back to Dashboard", use_container_width=True):
                    st.session_state.quiz_active = False
                    st.session_state.quiz_data = {}
                    st.rerun()
            with col2:
                if st.button("🔄 Retake Quiz", use_container_width=True):
                    # Retake with same settings
                    quiz_words = managers['quiz'].get_quiz_words(quiz_data['type'], quiz_data['length'], username)
                    if quiz_words:
                        st.session_state.quiz_data = {
                            'type': quiz_data['type'],
                            'length': len(quiz_words),
                            'words': quiz_words,
                            'current': 0,
                            'score': 0,
                            'start_time': time.time(),
                            'answers': []
                        }
                        st.rerun()
                    else:
                        st.error("Could not generate quiz. Please try again.")

def show_spaced_repetition(username: str):
    """Show spaced repetition study session"""
    st.markdown("# 🔄 Spaced Repetition")
    st.markdown("Review words you've learned based on optimal timing for long-term memory.")
    # Get due words
    due_words = managers['spaced_repetition'].get_due_words(username, 20)
    if not due_words:
        st.info("No words are due for review right now. Great job keeping up!")
        st.markdown("You can:")
        if st.button("📚 Study Flashcards"):
            st.session_state.current_page = "Flashcards"
            st.rerun()
        if st.button("📝 Take a Quiz"):
            st.session_state.current_page = "Take Quiz"
            st.rerun()
        return
    st.markdown(f"### You have {len(due_words)} words to review")
    # Simple flashcard review for spaced repetition
    if 'sr_index' not in st.session_state:
        st.session_state.sr_index = 0
        st.session_state.sr_reviews = []
    index = st.session_state.sr_index
    if index < len(due_words):
        word = due_words[index]
        word_details = managers['word'].get_word_details(word)
        if word_details:
            st.markdown(f"""
            <div class="flashcard" onclick="this.querySelector('.definition').style.display='block'">
                <h2>{word_details['word'].title()}</h2>
                <p><em>{word_details.get('pronunciation', '')}</em></p>
                <div class="definition" style="display:none; margin-top: 20px;">
                    <p>{word_details['definition']}</p>
                    {f"<p><strong>Example:</strong> {word_details['example1']}</p>" if word_details.get('example1') else ''}
                </div>
                <p style="margin-top: 20px; font-size: 0.9em; color: #bbb;">Click card to reveal definition</p>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("### How well did you remember this word?")
            col1, col2, col3, col4 = st.columns(4)
            quality_map = {0: "Again", 2: "Hard", 3: "Good", 5: "Easy"}
            for quality, label in quality_map.items():
                if st.button(label, key=f"sr_{quality}", use_container_width=True):
                    st.session_state.sr_reviews.append((word, quality))
                    st.session_state.sr_index += 1
                    st.rerun()
        else:
            st.error("Error loading word details.")
    else:
        # Finished review
        st.success("🎉 You've finished reviewing all due words!")
        # Save spaced repetition results
        for word, quality in st.session_state.sr_reviews:
            managers['spaced_repetition'].update_word_memory(username, word, quality)
        st.markdown(f"Reviewed {len(st.session_state.sr_reviews)} words.")
        if st.button("🔄 Review Again"):
            st.session_state.sr_index = 0
            st.session_state.sr_reviews = []
            st.rerun()
        if st.button("🏠 Back to Dashboard"):
            del st.session_state.sr_index
            del st.session_state.sr_reviews
            st.rerun()

def show_flashcards(username: str):
    """Display flashcards for learning words"""
    st.markdown("# 📊 Flashcards")
    # Get a batch of words (e.g., 10 random or due words)
    # For simplicity, we'll use random words. Could be enhanced to use spaced repetition.
    words_data = managers['db'].conn_w.execute(
        "SELECT word, definition, pronunciation, example1 FROM words ORDER BY RANDOM() LIMIT 15"
    ).fetchall()
    if not words_data:
        st.info("No words available to study. Please add some words first.")
        return
    if 'flashcard_index' not in st.session_state:
        st.session_state.flashcard_index = 0
    index = st.session_state.flashcard_index
    word_data = words_data[index]
    st.markdown(f"""
    <div class="flashcard" onclick="this.querySelector('.back').style.display='block'">
        <div class="front">
            <h2>{word_data[0].title()}</h2>
            <p><em>{word_data[2] or ''}</em></p>
        </div>
        <div class="back" style="display:none; margin-top: 20px;">
            <p>{word_data[1]}</p>
            {f"<p><strong>Example:</strong> {word_data[3]}</p>" if word_data[3] else ''}
        </div>
        <p style="margin-top: 20px; font-size: 0.9em; color: #bbb;">Click card to reveal definition</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"Card {index + 1} of {len(words_data)}")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("⬅️ Previous" if index > 0 else "🏠 Home", use_container_width=True):
            if index > 0:
                st.session_state.flashcard_index -= 1
            else:
                del st.session_state.flashcard_index
            st.rerun()
    with col2:
        if st.button("🔄 Shuffle", use_container_width=True):
            random.shuffle(words_data) # This won't persist due to page rerun, but gives idea
            st.session_state.flashcard_index = 0
            st.rerun()
    with col3:
        if st.button("➡️ Next" if index < len(words_data) - 1 else "🏁 Finish", use_container_width=True):
            if index < len(words_data) - 1:
                st.session_state.flashcard_index += 1
            else:
                del st.session_state.flashcard_index
                st.success("🎉 Finished flashcard session!")
            st.rerun()

def show_analytics(username: str):
    """Display user analytics and progress"""
    st.markdown("# 📈 Your Analytics")
    user_stats = managers['analytics'].get_user_stats(username)
    if not user_stats:
        st.error("Unable to load statistics.")
        return
    # Summary stats
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Level", user_stats['level'])
    col2.metric("Points", user_stats['points'])
    col3.metric("Streak", f"{user_stats['streak']} days")
    col4.metric("Accuracy", f"{user_stats['accuracy']}%")
    # Progress chart
    if user_stats['quiz_history']:
        df_history = pd.DataFrame(user_stats['quiz_history'], columns=['Date', 'Accuracy', 'Points'])
        df_history['Date'] = pd.to_datetime(df_history['Date'])
        st.markdown("### 📅 Quiz Performance Over Time")
        fig_acc = px.line(df_history, x='Date', y='Accuracy', title='Accuracy Trend')
        st.plotly_chart(fig_acc, use_container_width=True)
        fig_pts = px.bar(df_history, x='Date', y='Points', title='Points Earned Per Day')
        st.plotly_chart(fig_pts, use_container_width=True)
    else:
        st.info("No quiz history yet. Take a quiz to see your progress!")
    # Word knowledge
    st.markdown("### 🧠 Word Knowledge")
    known = user_stats['known_words']
    wrong = user_stats['wrong_words']
    if known + wrong > 0:
        fig_words = go.Figure(data=[go.Pie(labels=['Known', 'Mistakes'], values=[known, wrong], hole=.3)])
        fig_words.update_layout(title_text='Word Mastery')
        st.plotly_chart(fig_words, use_container_width=True)
    else:
        st.info("No words studied yet.")
    # Achievements
    st.markdown("### 🏆 Achievements")
    if user_stats['achievements']:
        for achievement, date in user_stats['achievements'][:10]: # Show last 10
            st.markdown(f"- 🏅 **{achievement}** ({date})")
    else:
        st.info("No achievements yet. Keep learning to unlock them!")

def show_leaderboard():
    """Display the user leaderboard"""
    st.markdown("# 🏆 Leaderboard")
    leaderboard_data = managers['analytics'].get_leaderboard(10)
    if leaderboard_data:
        df_lb = pd.DataFrame(leaderboard_data)
        st.dataframe(df_lb[['rank', 'username', 'level', 'points', 'streak', 'accuracy']], use_container_width=True)
    else:
        st.info("No leaderboard data available.")

def show_add_words(username: str):
    """Allow users to suggest new words"""
    st.markdown("# ➕ Suggest New Words")
    st.markdown("Help expand our vocabulary database!")
    with st.form("add_word_form"):
        new_word = st.text_input("Enter a word you'd like to add:")
        submit_word = st.form_submit_button("📤 Submit Word")
        if submit_word:
            if new_word:
                # In a full implementation, you might add it to a suggestions table
                # For now, we'll just try to add it directly
                result = managers['word'].add_word(new_word, username)
                if "successfully" in result:
                    st.success(result)
                else:
                    st.warning(result)
            else:
                st.error("Please enter a word.")
    # Show user's previous suggestions
    st.markdown("### Your Previous Suggestions")
    suggestions = managers['db'].conn_w.execute(
        "SELECT word, date, status FROM suggestions WHERE username=? ORDER BY date DESC LIMIT 10",
        (username,)
    ).fetchall()
    if suggestions:
        df_suggestions = pd.DataFrame(suggestions, columns=['Word', 'Date', 'Status'])
        st.dataframe(df_suggestions, use_container_width=True)
    else:
        st.info("You haven't suggested any words yet.")

def show_settings(username: str):
    """User settings page"""
    st.markdown("# ⚙️ Settings")
    st.markdown("### Account Information")
    user_data = managers['db'].conn_u.execute(
        "SELECT created_at, last_login FROM users WHERE username=?", (username,)
    ).fetchone()
    if user_data:
        st.markdown(f"**Member since:** {user_data[0]}")
        st.markdown(f"**Last login:** {user_data[1]}")
    st.markdown("### Change Password")
    with st.form("change_password"):
        old_pwd = st.text_input("Current Password", type="password")
        new_pwd = st.text_input("New Password", type="password")
        confirm_new_pwd = st.text_input("Confirm New Password", type="password")
        change_btn = st.form_submit_button("🔐 Change Password")
        if change_btn:
            if not all([old_pwd, new_pwd, confirm_new_pwd]):
                st.error("All fields are required.")
            elif new_pwd != confirm_new_pwd:
                st.error("New passwords do not match.")
            elif len(new_pwd) < 4:
                st.error("New password must be at least 4 characters.")
            else:
                # Verify old password
                stored_hash = managers['db'].conn_u.execute(
                    "SELECT pwd_hash FROM users WHERE username=?", (username,)
                ).fetchone()[0]
                if managers['auth'].verify_password(old_pwd, stored_hash):
                    new_hash = managers['auth'].hash_password(new_pwd)
                    managers['db'].conn_u.execute(
                        "UPDATE users SET pwd_hash=? WHERE username=?", (new_hash, username)
                    )
                    managers['db'].conn_u.commit()
                    st.success("Password changed successfully!")
                else:
                    st.error("Current password is incorrect.")

if __name__ == "__main__":
    main()
    # Ensure connections are closed properly on app exit
    # Note: Streamlit doesn't have a direct 'on_exit' hook that's reliable for this.
    # Connections are typically managed per request/thread and closed by the DB.
    # The DatabaseManager's close_connections method is available if needed explicitly.
