# 🐝🇫🇷 Jeu d'Épellation en Français

## 📖 Description

This project is a French web-based Spelling Bee Practice Game developed entirely independently using Python and the Streamlit framework. It was created as a personalized educational tool to help prepare for a real French spelling bee competition. The application played a key role in improving spelling performance and contributed to successful results in the competition.

The system uses a SQLite3 database to store words along with their corresponding context phrases and difficulty levels (**Easy, Medium, Hard**). It supports multiple users, including an admin account, allowing personalized tracking of progress and performance over time.

---

## 🧭 Features

The interface includes a sidebar navigation system with four main features:

### 1️⃣ Spelling Game
Users select a difficulty level and participate in a timed spelling session. Each word is pronounced aloud along with a context phrase, and the user has 30 seconds to input the correct spelling.

The evaluation requires full accuracy, including proper use of French accents (e.g., â, é, è, ê, î, ç), ensuring precise linguistic correctness. Unanswered words are marked as timeouts.

At the end of the session, results are displayed in a summary table showing correct and incorrect answers.

---

### 2️⃣ Performance Analysis
Provides detailed insights into user performance across sessions, including:

- Most frequently misspelled words  
- Average response time  
- Accuracy trends  
- Word-level performance  

Data is visualized through interactive graphs and tables.

---

### 3️⃣ Word Search
Allows users to search for specific words in the database and view their associated context phrases, reinforcing learning outside of gameplay.

---

### 4️⃣ Settings / Parameters
Enables customization of the number of words per session, allowing flexibility based on the user’s learning pace.

---

## 🧠 Project Highlights

- Developed entirely independently from concept to deployment  
- Combines backend data management with an interactive web-based GUI  
- Uses SQLite3 for persistent data storage  
- Implements real-time feedback and performance tracking  
- Applies software development to solve a real-world educational problem  

---

## 🎯 Impact

This application was specifically created to support preparation for a French spelling bee competition in Ontario. It significantly improved spelling accuracy and confidence, contributing to strong performance in the contest.

---

## 🛠️ Technologies Used

- Python  
- Streamlit  
- SQLite3  
- Text-to-Speech (TTS)  
- Data Visualization (charts & tables)  

---

## ▶️ How to Run

```bash
pip install streamlit
python -m streamlit run app.py
