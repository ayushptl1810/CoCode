from flask import render_template, request, redirect, url_for, session, jsonify
from app import app
import csv
import random
import sqlite3
import time


DB_PATH = "quiz_data.db"
app.config['SECRET_KEY'] = 'your-secret-key-here'


def initialize_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            question_id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            chapter TEXT NOT NULL,
            question TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            option1 TEXT,
            option2 TEXT,
            option3 TEXT,
            option4 TEXT,
            correct_answer TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_performance (
            quiz_id INTEGER,
            question_id INTEGER,
            difficulty TEXT,
            is_correct INTEGER,
            time_taken INTEGER,
            topic TEXT,
            attempt_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP,
            total_questions INTEGER,
            score INTEGER
        )
    ''')

    cursor.execute("SELECT COUNT(*) FROM questions")
    count = cursor.fetchone()[0]

    if count == 0:
        load_questions_from_csv(cursor)

    conn.commit()
    conn.close()

def load_questions_from_csv(cursor):
    with open('questions_dataset.csv', mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)

        for row in reader:
            cursor.execute('''
                INSERT INTO questions (subject, chapter, question, difficulty, option1, option2, option3, option4, correct_answer)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row["Subject"].strip(),
                row["Chapter"].strip(),
                row["Question"].strip(),
                row["Difficulty Level"].strip(),
                row["Option 1"].strip(),
                row["Option 2"].strip(),
                row["Option 3"].strip(),
                row["Option 4"].strip(),
                row["Correct Answer"].strip()
            ))

initialize_db()


@app.route("/")
def home():
    return render_template("home.html")

@app.route("/quiz")
def quiz():
    subject = request.args.get('subject', '').strip()
    session['subject'] = subject
    
    return render_template("quizpage.html")

@app.route('/get_questions')
def get_questions():
    subject = session['subject']
    if not subject:
        return jsonify({"error": "Subject parameter is required"}), 400

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT question_id, question, option1, option2, option3, option4, correct_answer, difficulty, chapter
        FROM questions
        WHERE subject = ?
    ''', (subject,))
    
    questions = cursor.fetchall()
    conn.close()

    if not questions:
        return jsonify({"error": "No questions found for the given subject"}), 404

    formatted_questions = [
        {
            "question_id": row[0],
            "question": row[1],
            "options": [row[2], row[3], row[4], row[5]],
            "answer": row[6],
            "difficulty": row[7],
            "chapter": row[8]
        } for row in questions
    ]

    random_questions = random.sample(formatted_questions, min(10, len(formatted_questions)))
    return jsonify(random_questions)

@app.route('/submit-answers', methods=['POST'])
def submit_answers():
    try:
        data = request.get_json()
        subject = session['subject']

        if not data or "answers" not in data or "times" not in data:
            return jsonify({"message": "Invalid data format"}), 400

        user_answers = data["answers"]
        time_spent = data["times"]

        if not isinstance(user_answers, dict) or not isinstance(time_spent, list):
            return jsonify({"message": "Invalid data structure"}), 400

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO quizzes (start_time)
            VALUES (CURRENT_TIMESTAMP)
        ''')
        quiz_id = cursor.lastrowid

        cursor.execute("SELECT question_id, correct_answer, difficulty, chapter FROM questions")
        question_dict = {row[0]: {"answer": row[1], "difficulty": row[2], "chapter": row[3]} for row in cursor.fetchall()}

        correct_count = 0
        results = []
        
        for i, (question_id, user_answer) in enumerate(user_answers.items()):
            question_id = int(question_id)
            correct_answer = question_dict.get(question_id, {}).get("answer", None)
            is_correct = 1 if user_answer == correct_answer else 0
            difficulty = question_dict.get(question_id, {}).get("difficulty", "Unknown")
            topic = question_dict.get(question_id, {}).get("chapter", "Unknown")
            time_taken = time_spent[i] if i < len(time_spent) else 0

            if is_correct:
                correct_count += 1

            results.append((quiz_id, question_id, difficulty, is_correct, time_taken, topic))

        # Insert the student performance records
        cursor.executemany('''
            INSERT INTO student_performance (quiz_id, question_id, difficulty, is_correct, time_taken, topic)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', results)

        # Update the quiz with final score
        cursor.execute('''
            UPDATE quizzes 
            SET end_time = CURRENT_TIMESTAMP,
                score = ?,
                total_questions = ?
                subject = ?
            WHERE quiz_id = ?
        ''', (correct_count, len(user_answers), subject, quiz_id))

        conn.commit()
        conn.close()

        total_time = sum(time_spent)
        minutes = total_time // 60
        seconds = total_time % 60

        return jsonify({
            "message": f"Quiz completed! You got {correct_count} out of {len(user_answers)} correct!\nTotal time: {minutes}m {seconds}s",
            "details": {
                "correct_count": correct_count,
                "total_questions": len(user_answers),
                "time_spent": time_spent,
                "total_time": total_time,
                "quiz_id": quiz_id
            }
        })

    except Exception as e:
        print("Error processing quiz submission:", str(e))
        return jsonify({"message": "Error processing request", "error": str(e)}), 500
    
@app.route("/quiz_subject")
def subject():
    return render_template("quiz.html")