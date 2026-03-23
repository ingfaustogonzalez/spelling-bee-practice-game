# $ pipenv shell
# $ pipenv sync
# $ streamlit run game.py
# $ deactivate

import streamlit as st
import streamlit.components.v1 as components  # for embedding custom HTML/JS
import sqlite3
import random
import os
import time
import json
from datetime import datetime, timedelta
from gtts import gTTS
import pandas as pd  # Needed for data handling
import plotly.express as px  # For advanced scatter/bar charts
import altair as alt         # For advanced box plots


# ------------- DEFAULT VALUES ---------------- #
DB_FILE = "spelling_bee.db"
DEFAULT_NUM_WORDS = 10
DEFAULT_TIME = 30       # time in seconds
PRACTICE_MODE = False
DEFAULT_USER_ID = 1     # For USER = admin, use USER_ID = 1
DEFAULT_LEVEL_ID = 1    # For LEVEL_ID = 1 -> Facile.

# ------------- CONFIGURATION FILE FUNCTIONS ---------------- #
CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    else:
        return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

# Load configuration on startup; if "num_words" not found, set it to DEFAULT_NUM_WORDS.
config = load_config()
if "num_words" not in config:
    config["num_words"] = DEFAULT_NUM_WORDS
    save_config(config)
persistent_num_words = config["num_words"]

# ------------- UTILITY FUNCTIONS ---------------- #

def speak_french(text, filename="tts.mp3"):
    """
    Convert text to French speech, play it, and then remove the temporary file.
    """
    try:
        tts = gTTS(text=text, lang='fr')
        tts.save(filename)
        status = os.system(f"afplay {filename}")
        if status != 0:
            raise Exception("Error playing the audio (afplay returned non-zero status)")
    except Exception as e:
        print(f"An error occurred in speak_french: {e}")
    finally:
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception as cleanup_error:
                print(f"An error occurred while removing the temporary file: {cleanup_error}")

def get_users():
    with sqlite3.connect(DB_FILE) as conn:
        return conn.execute("SELECT id, name FROM users").fetchall()

def get_user_name(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT name FROM users WHERE id = ?", (user_id,)).fetchone()
        return row[0] if row else None

def get_levels():
    with sqlite3.connect(DB_FILE) as conn:
        return conn.execute("SELECT id, name FROM levels").fetchall()

def get_level_name(level_id):
    with sqlite3.connect(DB_FILE) as conn:
        row = conn.execute("SELECT name FROM levels WHERE id = ?", (level_id,)).fetchone()
        return row[0] if row else None

def create_user(name):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name) VALUES (?)", (name,))
        conn.commit()
        return cursor.lastrowid

def create_session(user_id, level_id, date_value=None):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        if date_value is None:
            date_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO sessions (user_id, level_id, date) VALUES (?, ?, ?)",
                       (user_id, level_id, date_value))
        conn.commit()
        return cursor.lastrowid

def get_words_with_attempts(level_id, user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        query = """
        SELECT
            w.id,
            w.word,
            w.context_phrase,
            (
                SELECT COUNT(*)
                FROM attempts AS a
                INNER JOIN sessions AS s ON a.session_id = s.id
                WHERE a.word_id = w.id AND s.user_id = ?
            ) AS num_attempts
        FROM words w
        WHERE w.level_id = ?
        ORDER BY num_attempts;
        """
        cursor.execute(query, (user_id, level_id))
        results = cursor.fetchall()
    return results

def get_words_with_errors(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                w.word, 
                l.name AS Niveau, 
                COUNT(e.id) AS error_count
            FROM errors e
            JOIN attempts a ON e.attempt_id = a.id
            JOIN words w ON a.word_id = w.id
            JOIN levels l ON w.level_id = l.id
            JOIN sessions s ON a.session_id = s.id
            WHERE s.user_id = ?
            GROUP BY w.word, l.name
            ORDER BY error_count DESC;
        """
        cursor.execute(query, (user_id,))
        results = cursor.fetchall()
    return results


def get_due_words(level_id, user_id):
    """
    Returns a list of words to be reviewed.

    Parameters:
    level_id (int): Level representing the difficulty of the word.
    user_id (int): User.

    Returns:
    (list): Words that are due for review.
    """
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        query = """
        SELECT 
            w.id,
            w.word,
            w.context_phrase,
            COALESCE(uws.repetition, 0) as repetition
        FROM words w
        LEFT JOIN user_word_state uws 
           ON w.id = uws.word_id AND uws.user_id = ?
        WHERE w.level_id = ?
          AND (uws.next_review IS NULL OR uws.next_review <= date('now'))
        ORDER BY uws.next_review ASC, w.word;
        """
        cursor.execute(query, (user_id, level_id))
        results = cursor.fetchall()
    return results

def select_quiz_words(words_attempts, num_selected_words):
    """
    Returns a list with the words that are going to be reviewed in this session.

    Parameters:
    words_attempts (list):      A list of words, where each item looks like a tuple/list
                                and index 3 (w[3]) represents the number of attempts or mistakes.
    num_selected_words (int):   Number of words to be selected for the quiz.

    Returns:
    (list): Returns a list of words selected for this session. Words with the lowest attempt count
            (i.e., those the user struggles with) are prioritized, and the remaining words are filled
            in randomly. This results in a quiz composed of 80% weak words and 20% random variety.
            The returned list is shuffled.
    """
    
    total_words = len(words_attempts)
    if num_selected_words >= total_words:
        return words_attempts.copy()
    
    num_least = max(int(num_selected_words * 0.8), 1)
    min_value = words_attempts[0][3]
    group_lowest = [w for w in words_attempts if w[3] == min_value]
    
    if len(group_lowest) >= num_least:
        selected_least = random.sample(group_lowest, num_least)
    else:
        selected_least = group_lowest.copy()
        remaining_needed = num_selected_words - len(selected_least)
        remaining_candidates = [w for w in words_attempts if w not in selected_least]
        if remaining_needed > len(remaining_candidates):
            selected_least.extend(remaining_candidates)
        else:
            selected_least.extend(random.sample(remaining_candidates, remaining_needed))
    
    remaining_needed = num_selected_words - len(selected_least)
    remaining_pool = [w for w in words_attempts if w not in selected_least]
    if remaining_needed > len(remaining_pool):
        random_selected = remaining_pool.copy()
    else:
        random_selected = random.sample(remaining_pool, remaining_needed)
    
    selected_words = selected_least + random_selected
    random.shuffle(selected_words)
    return selected_words

def update_sm2_schedule(user_id, word_id, quality):
    """
    This function is based on the SM‑2 spaced repetition update function.
    This is the algorithm used by Anki, SuperMemo, and many SRS systems.
    This function updates the spaced‑repetition schedule for a given user and word
    based on the quality score (0–5) the user gave after reviewing the word.
    
    This function updates the spaced‑repetition schedule for a given user and word
    based on the quality score (0–5) the user gave after reviewing the word.
    
    Returns:
    (void)
    
    It updates:
    * repetition → how many successful reviews in a row
    * ease_factor → how easy the word is for the user
    * interval → how many days until the next review
    * next_review → the actual date when the word should appear again

    All of this is stored in the table user_word_state.
    """
    
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT repetition, ease_factor, interval 
            FROM user_word_state 
            WHERE user_id = ? AND word_id = ?
        """, (user_id, word_id))
        row = cursor.fetchone()
        
        if row is None:
            repetition = 0
            ease_factor = 2.5
            interval = 0
        else:
            repetition, ease_factor, interval = row
        
        if quality < 3:
            repetition = 0
            interval = 1
        else:
            repetition += 1
            if repetition == 1:
                interval = 1
            elif repetition == 2:
                interval = 6
            else:
                interval = int(round(interval * ease_factor))
            new_ef = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            ease_factor = max(new_ef, 1.3)
        
        next_review = (datetime.now() + timedelta(days=interval)).strftime("%Y-%m-%d")
        
        if row is None:
            cursor.execute("""
                INSERT INTO user_word_state (user_id, word_id, repetition, ease_factor, interval, next_review)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, word_id, repetition, ease_factor, interval, next_review))
        else:
            cursor.execute("""
                UPDATE user_word_state 
                SET repetition = ?, ease_factor = ?, interval = ?, next_review = ?
                WHERE user_id = ? AND word_id = ?
            """, (repetition, ease_factor, interval, next_review, user_id, word_id))
        conn.commit()

def record_attempt(session_id, word_id, correct, duration, misspelling=None):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO attempts (session_id, word_id, correct, duration)
            VALUES (?, ?, ?, ?)
        """, (session_id, word_id, int(correct), duration))
        attempt_id = cursor.lastrowid
        if not correct:
            cursor.execute("INSERT INTO errors (attempt_id, misspelling) VALUES (?, ?)", (attempt_id, misspelling))
        conn.commit()

def countdown_timer(seconds):
    html_code = f"""
    <div id="timer" style="font-size:24px; font-weight:bold;">Temps restant: {seconds} secondes</div>
    <script>
    var seconds = {seconds};
    var timerDiv = document.getElementById("timer");
    var interval = setInterval(function(){{
        seconds--;
        if(seconds < 0) {{
            clearInterval(interval);
        }} else {{
            timerDiv.innerHTML = "Temps restant: " + seconds + " secondes";
        }}
    }}, 1000);
    </script>
    """
    components.html(html_code, height=50)

def get_user_sessions_analytics(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        query = """
            SELECT
                s.date,
                l.name AS level,
                COUNT(a.id) AS total_attempts,
                SUM(CASE WHEN a.correct = 1 THEN 1 ELSE 0 END) AS correct_attempts,
                AVG(a.duration) AS avg_duration
            FROM sessions s
            JOIN attempts a ON s.id = a.session_id
            JOIN levels l ON s.level_id = l.id
            WHERE s.user_id = ?
            GROUP BY s.id
            ORDER BY s.date ASC;
        """
        cursor.execute(query, (user_id,))
        data = cursor.fetchall()
    return data

def get_word_performance(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                w.word,
                l.name AS Niveau,
                COUNT(a.id) AS total_attempts,
                SUM(CASE WHEN a.correct = 1 THEN 1 ELSE 0 END) AS correct_attempts,
                AVG(a.duration) AS avg_duration
            FROM attempts a
            JOIN words w ON a.word_id = w.id
            JOIN sessions s ON a.session_id = s.id
            JOIN levels l ON s.level_id = l.id
            WHERE s.user_id = ?
            GROUP BY w.word, l.name
            ORDER BY w.word ASC;
        """
        cursor.execute(query, (user_id,))
        results = cursor.fetchall()
    return results

def get_daily_attempts(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        query = """
            SELECT 
                date(s.date) as day, 
                l.name as level, 
                a.correct as outcome, 
                COUNT(a.id) as count
            FROM sessions s
            JOIN attempts a ON s.id = a.session_id
            JOIN levels l ON s.level_id = l.id
            WHERE s.user_id = ?
            GROUP BY day, level, outcome
            ORDER BY day ASC;
        """
        df = pd.read_sql_query(query, conn, params=[user_id])
    df["Outcome"] = df["outcome"].apply(lambda x: "Correct" if x == 1 else "Incorrect")
    return df

# ------------- STREAMLIT APP ---------------- #

st.set_page_config(page_title="Spelling Bee", page_icon="🐝")
st.title("🐝🇫🇷 Jeu d'Épellation en Français")

# Initialize session state if not already defined.
if "stage" not in st.session_state:
    if PRACTICE_MODE:
        st.session_state.stage = "select_level"
        st.session_state.user_id = DEFAULT_USER_ID
        st.session_state.user_name = get_user_name(st.session_state.user_id)
        st.session_state.level_id = DEFAULT_LEVEL_ID
    else:
        st.session_state.stage = "select_user"
        st.session_state.user_id = None
        st.session_state.level_id = None

    st.session_state.session_id = None
    st.session_state.words = []
    st.session_state.current_index = 0
    st.session_state.correct_count = 0
    st.session_state.errors = []
    if "num_words" not in st.session_state:
        st.session_state.num_words = persistent_num_words
    st.session_state.play_sound = True


# --- Disable navigation when the actual quiz is in progress (only during "play" or "summary") ---
quiz_active = st.session_state.stage in ["play", "summary"]
if quiz_active:
    st.sidebar.markdown("**Session de quiz en cours – navigation désactivée**")
    nav_option = "Quiz"
else:
    nav_option = st.sidebar.radio("Navigation", ["Quiz", "Analyses", "Recherche de mot", "Paramètres"])


# ===================== QUIZ ===================== #
if nav_option == "Quiz":
    if st.session_state.stage == "select_user":
        st.subheader("👤 Sélectionnez un utilisateur")
        users = get_users()
        if len(users) == 0:
            st.selectbox("Utilisateur existant:", [], disabled=True)
            st.button("Continuer", disabled=True)
        else:
            user_map = {f"{u[1]} (ID: {u[0]})": u[0] for u in users}
            user_placeholder = st.empty()
            with user_placeholder.container():
                selected_user = st.selectbox("Utilisateur existant:", list(user_map.keys()))
                continue_button = st.button("Continuer", key="continue_active")
            if continue_button:
                st.session_state.user_id = user_map[selected_user]
                st.session_state.user_name = get_user_name(st.session_state.user_id)
                user_placeholder.empty()
                st.markdown("**En cours de transition vers le niveau...**")
                st.session_state.stage = "select_level"
                st.rerun()
        with st.expander("Créer un nouvel utilisateur"):
            form = st.form(key="response_form")
            new_name = form.text_input("Nom:", value="")
            submitted = form.form_submit_button("Créer")
            if submitted and new_name.strip():
                new_id = create_user(new_name.strip())
                st.success(f"Utilisateur {new_name} créé avec ID {new_id}.")
                st.session_state.user_id = new_id
                st.session_state.user_name = new_name
                st.session_state.stage = "select_level"
                st.rerun()
    elif st.session_state.stage == "select_level":
        st.header(f"Bienvenue, {st.session_state.user_name}!")
        st.subheader("🎯 Choisissez un niveau")
        levels = get_levels()
        level_map = {f"{lvl[1]}": lvl[0] for lvl in levels}
        level_choice = st.radio("Niveau:", list(level_map.keys()), index=(st.session_state.level_id), disabled=PRACTICE_MODE)
        if st.button("Démarrer la session"):
            st.session_state.level_id = level_map[level_choice]
            st.session_state.session_id = create_session(st.session_state.user_id, st.session_state.level_id, None)
            due_words = get_due_words(st.session_state.level_id, st.session_state.user_id)
            if len(due_words) == 0:
                due_words = get_words_with_attempts(st.session_state.level_id, st.session_state.user_id)
            st.session_state.words = select_quiz_words(due_words, st.session_state.num_words)
            st.session_state.current_index = 0
            st.session_state.start_time = time.time()
            st.session_state.play_sound = True
            st.session_state.stage = "play"
            st.rerun()
    elif st.session_state.stage == "play":
        idx = st.session_state.current_index
        st.subheader(f"🎯 Niveau: {get_level_name(st.session_state.level_id)}")
        if idx < len(st.session_state.words):
            st.markdown(f"### 📘 Mot {idx + 1} sur {len(st.session_state.words)}")
            word_id, word, context, _ = st.session_state.words[idx]
            if st.session_state.get("play_sound", True):
                sound_placeholder = st.empty()
                sound_placeholder.markdown("Lecture du mot et du contexte dans quelques instants...")
                time.sleep(1)
                speak_french(word)
                time.sleep(1)
                speak_french(context)
                st.session_state.play_sound = False
                st.session_state.start_time = time.time()
                sound_placeholder.empty()
            elapsed = time.time() - st.session_state.start_time
            remaining = max(0, DEFAULT_TIME - int(elapsed))
            countdown_timer(remaining)
            if st.button("🔊 Répéter"):
                speak_french(word)
                time.sleep(1)
                speak_french(context)
                st.session_state.start_time = time.time()
                st.rerun()
            form = st.form(key="response_form")
            response = form.text_input("Tapez votre réponse:", value="", key=f"text_input_{idx}")
            components.html(
                f"""
                <script>
                window.setTimeout(function() {{
                    var input_elem = window.parent.document.querySelector("input[id^='text_input_']")
                    if (input_elem) {{
                        input_elem.focus();
                    }}
                }}, 500);
                </script>
                """,
                height=0,
            )
            submitted = form.form_submit_button("Soumettre")
            if submitted or remaining == 0:
                is_timeout = remaining == 0
                is_correct = (response.strip().lower() == word.lower() and not is_timeout)
                duration = float(DEFAULT_TIME) if is_timeout else elapsed
                miss = "___TIMEOUT___" if is_timeout else response.strip()
                quality = 5 if is_correct else (2 if is_timeout else 3)
                update_sm2_schedule(st.session_state.user_id, word_id, quality)
                record_attempt(st.session_state.session_id, word_id, is_correct, duration, miss if not is_correct else None)
                st.session_state.current_index += 1
                st.session_state.play_sound = True
                if is_timeout:
                    st.warning("⏱️ Temps écoulé !")
                elif is_correct:
                    st.success("✅ Correct")
                else:
                    st.error("❌ Incorrect")
                time.sleep(2)
                st.rerun()
        else:
            st.session_state.stage = "summary"
            st.rerun()
    elif st.session_state.stage == "summary":
        st.header("🎉 Résultats de la session")
        st.subheader(f"🎯 Niveau: {get_level_name(st.session_state.level_id)}")
        summary = []
        correct_attempts = 0
        with sqlite3.connect(DB_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, word_id, correct, duration FROM attempts WHERE session_id = ?", (st.session_state.session_id,))
            attempts = cursor.fetchall()
            for attempt in attempts:
                attempt_id, word_id, correct, duration = attempt
                cursor.execute("SELECT word FROM words WHERE id = ?", (word_id,))
                row = cursor.fetchone()
                word = row[0] if row else "N/A"
                if correct:
                    correct_attempts += 1
                    user_ans = word
                    status = "Correct"
                else:
                    cursor.execute("SELECT misspelling FROM errors WHERE attempt_id = ?", (attempt_id,))
                    err = cursor.fetchone()
                    user_ans = err[0] if err else ""
                    status = "Temps écoulé" if user_ans == "___TIMEOUT___" else "Incorrect"
                summary.append({
                    "Word": word,
                    "Your Answer": user_ans,
                    "Correct": word,
                    "Status": status
                })
        total_attempts = len(attempts)
        st.write(f"Vous avez eu **{correct_attempts} bonnes réponses sur {total_attempts}**.")
        percentage = correct_attempts / total_attempts if total_attempts > 0 else 0
        if percentage <= 0.6:
            st.info("Il faut vous améliorer.")
        elif percentage <= 0.8:
            st.info("Pas mal, mais vous pouvez faire encore mieux.")
        elif percentage < 1:
            st.success("Bravo!")
        else:
            st.balloons()
            st.success("Parfait!")
        df_summary = pd.DataFrame(summary)
        df_summary = df_summary.rename(columns={"Correct": "Mot", "Your Answer": "Votre Réponse", "Status": "Statut"})
        df_summary = df_summary[["Mot", "Votre Réponse", "Statut"]]
        df_summary.index = range(1, len(df_summary) + 1)
        def highlight_status(row):
            if row['Statut'] == 'Correct':
                return ['background-color: lightgreen'] * len(row)
            elif row['Statut'] == 'Incorrect':
                return ['background-color: lightcoral'] * len(row)
            elif row['Statut'] == 'Temps écoulé':
                return ['background-color: yellow'] * len(row)
            else:
                return [''] * len(row)
        styled_df = df_summary.style.apply(highlight_status, axis=1)
        st.subheader("📊 Tableau des résultats")
        st.dataframe(styled_df, use_container_width=True)
        if st.button("Retour à l'accueil"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# ===================== ANALYSES ===================== #
elif nav_option == "Analyses":
    st.header("📈 Analyses")
    users = get_users()
    if users:
        user_map = {f"{user[1]} (ID: {user[0]})": user[0] for user in users}
        selected_user_display = st.selectbox("Sélectionnez un utilisateur pour les analyses", list(user_map.keys()))
        selected_user_id = user_map[selected_user_display]

        # ========= 1. Résumé Global des Sessions =========
        analytics_data = get_user_sessions_analytics(selected_user_id)
        if analytics_data:
            df_sessions = pd.DataFrame(analytics_data, columns=["Date", "Niveau", "Nombre d'essais", "Essais corrects", "Durée moyenne"])
            df_sessions["Date"] = pd.to_datetime(df_sessions["Date"])
            df_sessions["Précision (%)"] = (df_sessions["Essais corrects"] / df_sessions["Nombre d'essais"] * 100).round(2)
            df_sessions.index = range(1, len(df_sessions) + 1)
            st.subheader("Résumé Global des Sessions")
            st.dataframe(df_sessions)
            st.subheader("Évolution de la Précision (%)")
            st.line_chart(df_sessions.set_index("Date")["Précision (%)"])
            st.subheader("Durée Moyenne de Réponse (s)")
            st.line_chart(df_sessions.set_index("Date")["Durée moyenne"])
            st.subheader("Progression Cumulée des Réponses Correctes")
            df_sessions = df_sessions.sort_values("Date")
            df_sessions["Cumul_correct"] = df_sessions["Essais corrects"].cumsum()
            st.line_chart(df_sessions.set_index("Date")["Cumul_correct"])
        else:
            st.info("Aucune donnée de session disponible pour cet utilisateur.")

        # ========= 2. Visualisations Avancées des Sessions =========
        st.markdown("---")
        st.subheader("Visualisations Avancées des Sessions")
        if not df_sessions.empty:
            st.markdown("**Nuage de points : Précision (%) vs Durée moyenne**")
            scatter_fig = px.scatter(
                df_sessions,
                x="Durée moyenne",
                y="Précision (%)",
                hover_data=["Date", "Niveau", "Nombre d'essais", "Essais corrects"],
                labels={"Durée moyenne": "Durée moyenne (s)", "Précision (%)": "Précision (%)"}
            )
            st.plotly_chart(scatter_fig)
            st.markdown("**Diagramme en boîte : Distribution des durées par niveau**")
            box_chart = alt.Chart(df_sessions).mark_boxplot().encode(
                x=alt.X('Niveau:N', sort=["Facile", "Moyen", "Difficile"],
                        title='Niveau',
                        scale=alt.Scale(domain=["Facile", "Moyen", "Difficile"])),
                y=alt.Y('Durée moyenne:Q', title='Durée moyenne (s)'),
                color=alt.Color('Niveau:N',
                                scale=alt.Scale(domain=["Facile", "Moyen", "Difficile"],
                                                range=["green", "blue", "#FF6600"]))
            )
            st.altair_chart(box_chart, use_container_width=True)
        else:
            st.info("Aucune donnée pour les visualisations avancées.")

        # ========= 3. Performance par Mot =========
        st.markdown("---")
        st.subheader("Performance par Mot")
        word_performance = get_word_performance(selected_user_id)
        if word_performance:
            df_word = pd.DataFrame(word_performance, columns=["Mot", "Niveau", "Total", "Correct", "Durée moyenne"])
            df_word["Précision (%)"] = (df_word["Correct"] / df_word["Total"] * 100).round(2)
            df_word.index = range(1, len(df_word) + 1)
            st.sidebar.markdown("### Filtrer par mot spécifique")
            word_list = sorted(df_word["Mot"].unique())
            selected_word = st.sidebar.selectbox("Choisissez un mot", ["Tous"] + word_list)
            if selected_word != "Tous":
                df_word = df_word[df_word["Mot"] == selected_word]
            st.dataframe(df_word)
            st.markdown("**Heatmap : Performance par Mot**")
            df_heat = df_word.set_index("Mot")[["Total", "Correct", "Précision (%)"]]
            fig_heatmap = px.imshow(df_heat,
                                    text_auto=True,
                                    aspect="auto",
                                    color_continuous_scale="Blues",
                                    labels={"x": "Métrique", "color": "Valeur"})
            st.plotly_chart(fig_heatmap)
        else:
            st.info("Aucune donnée de performance par mot disponible.")

        # ========= 4. Mots avec le Plus d'Erreurs =========
        st.markdown("---")
        st.subheader("Mots avec le Plus d'Erreurs")
        error_data = get_words_with_errors(selected_user_id)
        if error_data:
            df_errors = pd.DataFrame(error_data, columns=["Mot", "Niveau", "Nombre d'erreurs"])
            df_errors.index = range(1, len(df_errors) + 1)
            st.dataframe(df_errors)
            st.markdown("**Diagramme en barres : Nombre d'erreurs par mot**")
            fig_errors = px.bar(
                df_errors,
                x="Mot",
                y="Nombre d'erreurs",
                text="Nombre d'erreurs",
                color="Niveau",
                color_discrete_map={"Facile": "green", "Moyen": "blue", "Difficile": "#FF6600"},
                labels={"Mot": "Mot", "Nombre d'erreurs": "Nombre d'erreurs", "Niveau": "Niveau"}
            )
            st.plotly_chart(fig_errors)
        else:
            st.info("Aucune erreur enregistrée pour cet utilisateur.")

        # ========= 5. Tentatives Quotidiennes par Niveau =========
        st.markdown("---")
        st.subheader("Tentatives Quotidiennes par Niveau (Correct/Incorrect)")
        df_daily = get_daily_attempts(selected_user_id)
        selected_levels_daily = st.sidebar.multiselect("Filtrer le graphique quotidien par niveau",
                                                         options=["Facile", "Moyen", "Difficile"],
                                                         default=["Facile", "Moyen", "Difficile"])
        df_daily["level"] = pd.Categorical(df_daily["level"], 
                                            categories=["Facile", "Moyen", "Difficile"], 
                                            ordered=True)
        df_daily = df_daily[df_daily["level"].isin(selected_levels_daily)]
        df_daily["Outcome"] = pd.Categorical(df_daily["Outcome"], 
                                              categories=["Correct", "Incorrect"],
                                              ordered=True)
        df_daily = df_daily.sort_values(by=["day", "level", "Outcome"])
        if not df_daily.empty:
            fig_daily = px.bar(
                df_daily, 
                x="day", 
                y="count", 
                color="level", 
                pattern_shape="Outcome",
                category_orders={"level": ["Facile", "Moyen", "Difficile"]},
                color_discrete_map={"Facile": "green", "Moyen": "blue", "Difficile": "#FF6600"},
                labels={"day": "Date", "count": "Nombre de mots tentés", "level": "Niveau", "Outcome": "Résultat"},
                title="Nombre de mots essayés par jour, par niveau"
            )
            fig_daily.update_layout(barmode="stack")
            st.plotly_chart(fig_daily)
        else:
            st.info("Aucune donnée pour le graphique quotidien.")
    else:
        st.error("Aucun utilisateur trouvé. Veuillez d'abord ajouter un utilisateur.")


# ===================== RECHERCHE DE MOT ===================== #
elif nav_option == "Recherche de mot":
    # --- Section: Recherche et tableau des mots ---
    st.header("Recherche de mot et affichage du tableau")

    # Query to select word, context phrase, and level name
    with sqlite3.connect(DB_FILE) as conn:
        query = """
            SELECT 
                w.word AS Mot, 
                w.context_phrase AS "Phrase de contexte", 
                l.name AS Niveau
            FROM words w
            JOIN levels l ON w.level_id = l.id
            ORDER BY w.word;
        """
        df_words = pd.read_sql_query(query, conn)
        df_words.index = range(1, len(df_words) + 1)

    # Display the full table
    st.dataframe(df_words)

    # Optionally, add a search/selectbox to narrow down the table.
    selected_mot = st.selectbox("Rechercher un mot", options=df_words["Mot"].unique())
    if selected_mot:
        df_filtered = df_words[df_words["Mot"] == selected_mot]
        st.subheader("Résultat de la recherche pour : " + selected_mot)
        st.dataframe(df_filtered)

# ===================== PARAMÈTRES ===================== #
elif nav_option == "Paramètres":
    st.header("⚙️ Paramètres")
    # Display in the main area
    disabled_widget = st.session_state.session_id is not None
    options = [5, 10, 15, 20]
    default_index = options.index(st.session_state.num_words) if st.session_state.num_words in options else 0
    new_num_words = st.selectbox(
        "Nombre de mots par session",
        options,
        index=default_index,
        disabled=disabled_widget
    )
    if new_num_words != st.session_state.num_words:
        st.session_state.num_words = new_num_words
        config["num_words"] = new_num_words
        save_config(config)
