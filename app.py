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
                pronunciation = self.db.dictionary.getPhonetic(word) or ""
            except Exception as e:
                logger.warning(f"Failed to get pronunciation for '{word}': {e}")
            
            try:
                examples = self.db.dictionary.getSentences(word) or []
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
            
            elif
