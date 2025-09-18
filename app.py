# app.py – complete Streamlit vocab-quiz app with gamification
import streamlit as st, sqlite3, pathlib, datetime as dt, pytz, time, random, pandas as pd
from PyDictionary import PyDictionary
import bcrypt

# ---------- CONFIG ----------
st.set_page_config(page_title="📚 Vocab Quiz", page_icon="📚", layout="wide")
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
        background-color: #262730;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s ease;
        border: 2px solid #4a4a4a;
    }
    .flashcard:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.3);
    }
    .achievement-badge {
        display: inline-block;
        padding: 5px 10px;
        margin: 5px;
        border-radius: 15px;
        background-color: #1e3a8a;
        color: white;
        font-weight: bold;
    }
    .wod-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
    }
    .level-badge {
        background-color: #059669;
        color: white;
        padding: 3px 8px;
        border-radius: 10px;
        font-size: 0.8em;
    }
    .points-display {
        background-color: #7c3aed;
        color: white;
        padding: 5px 10px;
        border-radius: 15px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

DB_U      = pathlib.Path("users.db")
DB_W      = pathlib.Path("words.db")
IST       = pytz.timezone("Asia/Kolkata")
TODAY_IST = dt.datetime.now(IST).date()
dictionary = PyDictionary()

# ---------- DB BOOTSTRAP ----------
def init_user_db():
    conn = sqlite3.connect(DB_U, check_same_thread=False)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY, pwd_hash TEXT, streak INTEGER DEFAULT 0,
        total_q INTEGER DEFAULT 0, correct INTEGER DEFAULT 0,
        time_spent REAL DEFAULT 0, last_quiz_date TEXT, points INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS quiz_log(
        username TEXT, date TEXT, quiz_type TEXT, length INTEGER, correct INTEGER, time_spent REAL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS word_user(
        username TEXT, word TEXT, status TEXT, date TEXT, PRIMARY KEY(username, word))""")
    c.execute("""CREATE TABLE IF NOT EXISTS follows(
        follower TEXT, following TEXT, PRIMARY KEY(follower, following))""")
    c.execute("""CREATE TABLE IF NOT EXISTS user_achievements(
        username TEXT, achievement TEXT, date_earned TEXT, PRIMARY KEY(username, achievement))""")
    conn.commit(); return conn

def init_word_db():
    conn = sqlite3.connect(DB_W, check_same_thread=False)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS words(
        word TEXT PRIMARY KEY, def TEXT, pron TEXT, ety TEXT,
        ex1 TEXT, ex2 TEXT, added_by TEXT, date_added TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS suggestions(
        word TEXT, username TEXT, date TEXT)""")
    conn.commit(); return conn

conn_u = init_user_db()
conn_w = init_word_db()

# ---------- AUTH ----------
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# Ensure demo and admin users exist
def ensure_default_users():
    # Create demo user if it doesn't exist
    demo_exists = conn_u.execute("SELECT 1 FROM users WHERE username='demo'").fetchone()
    if not demo_exists:
        demo_hash = hash_password("demo")
        conn_u.execute("INSERT OR IGNORE INTO users(username,pwd_hash) VALUES(?,?)", ("demo", demo_hash))
    
    # Create admin user if it doesn't exist
    admin_exists = conn_u.execute("SELECT 1 FROM users WHERE username='admin'").fetchone()
    if not admin_exists:
        admin_hash = hash_password("admin@123")
        conn_u.execute("INSERT OR IGNORE INTO users(username,pwd_hash) VALUES(?,?)", ("admin", admin_hash))
    
    conn_u.commit()

ensure_default_users()

# Load credentials
c = conn_u.execute("SELECT username, pwd_hash FROM users").fetchall()
credentials = {"usernames":{u:{"name":u,"password":p} for u,p in c}}

# Simple authentication without stauth
def login_page():
    st.title("📚 Vocab Quiz - Login")
    
    # Create tabs for login and registration
    tab1, tab2 = st.tabs(["Login", "Create Account"])
    
    with tab1:
        st.write("### Login")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            if username in credentials["usernames"]:
                stored_hash = credentials["usernames"][username]["password"]
                if verify_password(password, stored_hash):
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.name = username
                    st.rerun()
                else:
                    st.error("Incorrect password")
            else:
                st.error("User not found")
    
    with tab2:
        st.write("### Create New Account")
        new_username = st.text_input("Choose Username", key="register_username")
        new_password = st.text_input("Choose Password", type="password", key="register_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_password")
        if st.button("Create Account"):
            # Validation
            if not new_username or not new_password:
                st.error("Please fill in all fields")
            elif new_password != confirm_password:
                st.error("Passwords don't match")
            else:
                # Check if user already exists
                existing = conn_u.execute("SELECT 1 FROM users WHERE username=?", (new_username,)).fetchone()
                if existing:
                    st.error("Username already taken")
                else:
                    hp = hash_password(new_password)
                    try:
                        conn_u.execute("INSERT INTO users(username,pwd_hash) VALUES(?,?)", (new_username, hp))
                        conn_u.commit()
                        # Update credentials
                        credentials["usernames"][new_username] = {"name": new_username, "password": hp}
                        st.success("Account created! Please switch to the Login tab to sign in.")
                    except sqlite3.IntegrityError:
                        st.error("Username taken")

def logout():
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.rerun()

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    login_page()
    st.stop()

username = st.session_state.username
name = st.session_state.name
logout()

# ---------- ADMIN ----------
def add_word(word, by="admin"):
    word = word.lower()
    if conn_w.execute("SELECT 1 FROM words WHERE word=?", (word,)).fetchone(): return "Exists"
    try:
        meaning = dictionary.meaning(word) or {"N/A":["No definition"]}
        pron = dictionary.getPhonetic(word) or ""
        ex   = dictionary.getSentences(word) or []
        conn_w.execute("INSERT INTO words(word,def,pron,ety,ex1,ex2,added_by,date_added) VALUES(?,?,?,?,?,?,?,?)",
                      (word, str(meaning), pron, "", ex[0] if ex else "", ex[1] if len(ex)>1 else "", by, str(TODAY_IST)))
        conn_w.commit(); return "Added"
    except Exception as e: return f"Error: {e}"

with st.sidebar:
    if username == "admin":
        st.write("### Admin Panel")
        st.info("Admin password is: `admin@123`")
        
        # Show current word count
        word_count = conn_w.execute("SELECT COUNT(*) FROM words").fetchone()[0]
        st.write(f"📚 Currently have {word_count} words in database")
        
        batch = st.text_area("Paste words (line separated)")
        if st.button("Add batch"):
            added_count = 0
            skipped_count = 0
            for w in batch.splitlines():
                if w.strip():
                    result = add_word(w.strip())
                    if result == "Added":
                        added_count += 1
                    elif result == "Exists":
                        skipped_count += 1
            st.success(f"✅ Added {added_count} words, ⚠️ Skipped {skipped_count} existing words")
        
        up = st.file_uploader("Or upload .txt file")
        if up:
            content = up.read().decode()
            added_count = 0
            skipped_count = 0
            for w in content.splitlines():
                if w.strip():
                    result = add_word(w.strip())
                    if result == "Added":
                        added_count += 1
                    elif result == "Exists":
                        skipped_count += 1
            st.success(f"✅ Added {added_count} words from file, ⚠️ Skipped {skipped_count} existing words")

# ---------- WORD OF THE DAY ----------
def get_word_of_the_day():
    # Get a random word for today
    words = conn_w.execute("SELECT word FROM words ORDER BY RANDOM() LIMIT 1").fetchall()
    if words:
        word = words[0][0]
        details = conn_w.execute("SELECT def,pron,ex1 FROM words WHERE word=?", (word,)).fetchone()
        return word, details
    return None, None

def display_word_of_the_day():
    # Check if user has hidden WOD today
    hidden_key = f"wod_hidden_{str(TODAY_IST)}"
    if st.session_state.get(hidden_key, False):
        return
    
    word, details = get_word_of_the_day()
    if word and details:
        def_text, pron, ex1 = details
        
        with st.container():
            st.markdown('<div class="wod-container">', unsafe_allow_html=True)
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"### 🌟 Word of the Day: **{word.upper()}**")
                st.write("**Pronunciation:**", pron)
                st.write("**Definition:**", def_text)
                if ex1: st.write("**Example:**", ex1)
            with col2:
                if st.button("🙈 Hide", key="hide_wod"):
                    st.session_state[hidden_key] = True
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

# ---------- GAMIFICATION ----------
def calculate_level(points):
    return int(points / 100) + 1

def award_achievements(username, points, streak, total_known):
    achievements = []
    
    # Points-based achievements
    if points >= 100: achievements.append("🥉 First Century")
    if points >= 500: achievements.append("🥈 Half Millennium")
    if points >= 1000: achievements.append("🥇 Millennium Master")
    
    # Streak achievements
    if streak >= 7: achievements.append("🔥 Week Streak")
    if streak >= 30: achievements.append("⭐ Monthly Master")
    if streak >= 100: achievements.append("👑 Century Streak")
    
    # Knowledge achievements
    if total_known >= 50: achievements.append("📚 Vocabulary Builder")
    if total_known >= 200: achievements.append("🎓 Word Scholar")
    if total_known >= 500: achievements.append("🧠 Lexicon Legend")
    
    # Award new achievements
    for achievement in achievements:
        exists = conn_u.execute("SELECT 1 FROM user_achievements WHERE username=? AND achievement=?", 
                               (username, achievement)).fetchone()
        if not exists:
            conn_u.execute("INSERT INTO user_achievements(username, achievement, date_earned) VALUES(?,?,?)",
                          (username, achievement, str(TODAY_IST)))
            conn_u.commit()
    
    return achievements

def display_achievements(username):
    achievements = conn_u.execute("SELECT achievement FROM user_achievements WHERE username=? ORDER BY date_earned DESC", 
                                 (username,)).fetchall()
    if achievements:
        st.write("### 🏆 Your Achievements")
        for ach, in achievements[:10]:  # Show latest 10
            st.markdown(f'<span class="achievement-badge">{ach}</span>', unsafe_allow_html=True)

# ---------- SOCIAL FEATURES ----------
def follow_user(follower, following):
    if follower != following:
        conn_u.execute("INSERT OR IGNORE INTO follows(follower, following) VALUES(?,?)", (follower, following))
        conn_u.commit()

def unfollow_user(follower, following):
    conn_u.execute("DELETE FROM follows WHERE follower=? AND following=?", (follower, following))
    conn_u.commit()

def get_following(username):
    return [u for u, in conn_u.execute("SELECT following FROM follows WHERE follower=?", (username,)).fetchall()]

def get_followers(username):
    return [u for u, in conn_u.execute("SELECT follower FROM follows WHERE following=?", (username,)).fetchall()]

# ---------- STUDY MODE (FLASHCARDS) ----------
def study_mode(username):
    st.write("### 🃏 Flashcard Study Mode")
    
    # Get known words for this user - FIXED QUERY
    try:
        known_words = conn_u.execute("""
            SELECT w.word, w.def, w.pron, w.ex1 
            FROM word_user wu 
            JOIN words w ON wu.word = w.word 
            WHERE wu.username=? AND wu.status='known'
        """, (username,)).fetchall()
    except:
        known_words = []  # Handle case where tables are empty or query fails
    
    if not known_words:
        st.info("You don't have any known words yet. Take a quiz to learn some words first!")
        return
    
    # Session state for flashcard navigation
    if 'current_card' not in st.session_state:
        st.session_state.current_card = 0
    if 'show_back' not in st.session_state:
        st.session_state.show_back = False
    
    current_idx = st.session_state.current_card
    if current_idx >= len(known_words):
        st.session_state.current_card = 0
        current_idx = 0
    
    if len(known_words) > 0:
        word, definition, pronunciation, example = known_words[current_idx]
        
        # Flashcard display
        if st.button(" Flip Card " if not st.session_state.show_back else " Flip Back ", key="flip"):
            st.session_state.show_back = not st.session_state.show_back
            st.rerun()
        
        st.markdown('<div class="flashcard">', unsafe_allow_html=True)
        if not st.session_state.show_back:
            st.markdown(f"### {word.upper()}")
            st.write("*Click 'Flip Card' to see definition*")
        else:
            st.write("**Pronunciation:**", pronunciation)
            st.write("**Definition:**", definition)
            if example: st.write("**Example:**", example)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Navigation
        col1, col2, col3 = st.columns([1,2,1])
        with col1:
            if st.button("⬅️ Previous") and current_idx > 0:
                st.session_state.current_card -= 1
                st.session_state.show_back = False
                st.rerun()
        with col2:
            st.write(f"Card {current_idx + 1} of {len(known_words)}")
        with col3:
            if st.button("Next ➡️") and current_idx < len(known_words) - 1:
                st.session_state.current_card += 1
                st.session_state.show_back = False
                st.rerun()

# ---------- STREAK ----------
def streak_info(username):
    row = conn_u.execute("SELECT streak, last_quiz_date FROM users WHERE username=?", (username,)).fetchone()
    if not row or not row[1]: return 0
    last = dt.date.fromisoformat(row[1])
    if (TODAY_IST - last).days == 0: return row[0]
    if (TODAY_IST - last).days == 1: return row[0]
    return 0

def update_streak(username):
    s = streak_info(username)
    row = conn_u.execute("SELECT last_quiz_date FROM users WHERE username=?", (username,)).fetchone()
    last = row[0] if row and row[0] else None
    if last is None or dt.date.fromisoformat(last) < TODAY_IST:
        if last is None or (TODAY_IST - dt.date.fromisoformat(last)).days == 1: s += 1
        else: s = 1
        conn_u.execute("UPDATE users SET streak=?, last_quiz_date=? WHERE username=?", (s, str(TODAY_IST), username))
        conn_u.commit()
    return s

# ---------- QUIZ ----------
def pick_words(username, mode, length):
    known   = {w for w, in conn_u.execute("SELECT word FROM word_user WHERE username=? AND status='known'", (username,))}
    all_w   = {w for w, in conn_w.execute("SELECT word FROM words").fetchall()}
    unknown = all_w - known
    if mode == "refresher": pool = list(known)
    elif mode == "new":     pool = list(unknown) if unknown else list(all_w)
    else:                   pool = list(all_w)
    random.shuffle(pool); return pool[:length]

def run_quiz(username, words, mode):
    st.write(f"**{mode.title()} quiz – {len(words)} words**")
    known, unknown = [], []
    start = time.time()
    prog = st.progress(0)
    for idx, word in enumerate(words):
        c1, c2, c3 = st.columns([3,1,1])
        c1.markdown(f"## {word.upper()}")
        know = c2.button("Know",  key=f"k{idx}", type="primary")
        dont = c3.button("Don't", key=f"d{idx}")
        if know:
            known.append(word)
            conn_u.execute("REPLACE INTO word_user(username,word,status,date) VALUES(?,?,?,?)",
                          (username, word, "known", str(TODAY_IST)))
        elif dont:
            unknown.append(word)
            conn_u.execute("REPLACE INTO word_user(username,word,status,date) VALUES(?,?,?,?)",
                          (username, word, "unknown", str(TODAY_IST)))
        conn_u.commit()
        prog.progress((idx+1)/len(words))
        if know or dont: st.rerun()
    elapsed = time.time() - start
    corr = len(known)
    
    # Update points and level
    points_earned = corr * 10
    conn_u.execute("""
        UPDATE users 
        SET total_q=total_q+?, correct=correct+?, time_spent=time_spent+?, points=points+?
        WHERE username=?
    """, (len(words), corr, elapsed, points_earned, username))
    
    conn_u.execute("INSERT INTO quiz_log(username,date,quiz_type,length,correct,time_spent) VALUES(?,?,?,?,?,?)",
                  (username, str(TODAY_IST), mode, len(words), corr, elapsed))
    conn_u.commit()
    
    st.success(f"{corr}/{len(words)} known in {elapsed:.1f} s (+{points_earned} points)")
    
    # Award achievements
    user_data = conn_u.execute("SELECT points, streak, correct FROM users WHERE username=?", (username,)).fetchone()
    if user_data:
        points, streak, total_correct = user_data
        award_achievements(username, points, streak, total_correct)
    
    for w in words:
        r = conn_w.execute("SELECT def,pron,ex1,ex2 FROM words WHERE word=?", (w,)).fetchone()
        if r:
            d, p, e1, e2 = r
            with st.expander(w.upper()):
                st.write("**Pronunciation:**", p); st.write("**Definition:**", d)
                if e1: st.write("**Ex1:**", e1)
                if e2: st.write("**Ex2:**", e2)
    s = update_streak(username)
    if s: st.balloons(); st.info(f"🔥 Streak: {s}")

# ---------- MAIN UI ----------
st.title("📚 Daily Vocab Quiz")

# Display Word of the Day
display_word_of_the_day()

# User stats
user_data = conn_u.execute("SELECT streak, correct, points, level FROM users WHERE username=?", (username,)).fetchone()
if user_data:
    streak, correct, points, level = user_data
    next_level = (level + 1) * 100
    progress = (points % 100) / 100 if points % 100 != 0 else 1
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🔥 Streak", streak)
    col2.metric("✅ Known", correct)
    col3.metric("⭐ Level", level)
    col4.metric("💎 Points", points)
    
    st.progress(progress, f"Progress to Level {level + 1}: {points % 100}/100 points")

display_achievements(username)

# Main tabs
tab1, tab2, tab3, tab4 = st.tabs(["🎮 Quiz", "🃏 Study Mode", "👥 Social", "🏆 Leaderboard"])

with tab1:
    mode = st.radio("Mode", ["New words", "Refresher (known words)", "Mixed"])
    length = st.selectbox("How many words?", [10, 20, 30, 50])
    if st.button("Start quiz"):
        words = pick_words(username, mode.lower().split()[0], length)
        if not words: st.warning("Ask admin to add words"); st.stop()
        run_quiz(username, words, mode.lower().split()[0])

with tab2:
    study_mode(username)

with tab3:
    st.write("### 👥 Social Features")
    
    # Follow users
    all_users = [u for u, in conn_u.execute("SELECT username FROM users WHERE username!=?", (username,)).fetchall()]
    if all_users:
        st.write("#### Follow Friends")
        for user in all_users[:10]:  # Show first 10 users
            col1, col2 = st.columns([3, 1])
            col1.write(f"**{user}**")
            is_following = conn_u.execute("SELECT 1 FROM follows WHERE follower=? AND following=?", 
                                         (username, user)).fetchone()
            if is_following:
                if col2.button("Unfollow", key=f"unfollow_{user}"):
                    unfollow_user(username, user)
                    st.rerun()
            else:
                if col2.button("Follow", key=f"follow_{user}"):
                    follow_user(username, user)
                    st.rerun()
    
    # Show following/followers
    following = get_following(username)
    followers = get_followers(username)
    
    col1, col2 = st.columns(2)
    with col1:
        st.write("#### Following")
        if following:
            for user in following:
                st.write(f"👤 {user}")
        else:
            st.info("You're not following anyone yet")
    
    with col2:
        st.write("#### Followers")
        if followers:
            for user in followers:
                st.write(f"👥 {user}")
        else:
            st.info("No followers yet")

with tab4:
    st.write("### 🏆 Leaderboard")
    
    # Friend leaderboard (people you follow + you)
    following = get_following(username)
    friend_list = following + [username]
    friend_list = list(set(friend_list))  # Remove duplicates
    
    df = pd.read_sql_query("""
        SELECT username, streak, correct, points, level
        FROM users 
        WHERE username IN ({})
        ORDER BY points DESC, streak DESC
    """.format(','.join('?' * len(friend_list))), conn_u, params=friend_list)
    
    if not df.empty:
        df['rank'] = range(1, len(df) + 1)
        df = df[['rank', 'username', 'level', 'points', 'streak', 'correct']]
        df.columns = ['Rank', 'User', 'Level', 'Points', 'Streak', 'Known']
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Follow some friends to see a personalized leaderboard!")
    
    # Global leaderboard
    st.write("### 🌍 Global Leaderboard")
    global_df = pd.read_sql_query("""
        SELECT username, level, points, streak, correct
        FROM users 
        ORDER BY points DESC, streak DESC
        LIMIT 10
    """, conn_u)
    
    if not global_df.empty:
        global_df['rank'] = range(1, len(global_df) + 1)
        global_df = global_df[['rank', 'username', 'level', 'points', 'streak', 'correct']]
        global_df.columns = ['Rank', 'User', 'Level', 'Points', 'Streak', 'Known']
        st.dataframe(global_df, use_container_width=True, hide_index=True)

with st.expander("Suggest a new word"):
    sw = st.text_input("Word")
    if st.button("Suggest"):
        conn_w.execute("INSERT INTO suggestions(word,username,date) VALUES(?,?,?)", (sw, username, str(TODAY_IST)))
        conn_w.commit(); st.success("Suggested!")

# Add some sample words for testing
if username == "admin":
    if st.sidebar.button("Add Sample Words"):
        sample_words = ["serendipity", "ephemeral", "ubiquitous", "eloquent", "pragmatic"]
        added = 0
        skipped = 0
        for word in sample_words:
            result = add_word(word, "admin")
            if result == "Added":
                added += 1
            elif result == "Exists":
                skipped += 1
        st.sidebar.success(f"Added {added} sample words, skipped {skipped} existing words!")
