from flask import render_template, request, send_file, session, jsonify,redirect, url_for
from app import app
import csv
import random
import sqlite3
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import joblib
import base64
import io
import os

model = joblib.load('updated_model.pkl')  
DB_PATH = "quiz_data.db"
app.config['SECRET_KEY'] = 'your-secret-key-here'


def initialize_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Update questions table to include topic_mastery
    cursor.execute("""
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
            correct_answer TEXT,
            topic_mastery REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_performance (
            quiz_id INTEGER,
            question_id INTEGER,
            difficulty TEXT,
            is_correct INTEGER,
            time_taken INTEGER,
            topic TEXT,
            topic_mastery REAL,
            attempt_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP,
            total_questions INTEGER,
            score INTEGER,
            avg_topic_mastery REAL
        )
    """)

    cursor.execute("SELECT COUNT(*) FROM questions")
    count = cursor.fetchone()[0]

    if count == 0:
        load_questions_from_csv(cursor)

    conn.commit()
    conn.close()

def calculate_topic_mastery(difficulty):
    # Base mapping for difficulty levels
    difficulty_base = {
        'Very Easy': 0.9,
        'Easy': 0.7,
        'Moderate': 0.5,
        'Tricky': 0.3,
        'Tough': 0.1
    }
    
    difficulty = str(difficulty).strip()
    if difficulty not in difficulty_base:
        print(f"Warning: Unknown difficulty level '{difficulty}', defaulting to Moderate")
        return 0.5

    # Add small random variation while keeping values close
    mastery = round(difficulty_base[difficulty] + np.random.uniform(-0.05, 0.05), 2)
    # Ensure values stay within 0-1 range
    return max(0, min(1, mastery))

def load_questions_from_csv(cursor):
    with open('questions.csv', mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)

        for row in reader:
            difficulty_level = row.get("Difficulty Level", "").strip()
            topic_mastery = calculate_topic_mastery(difficulty_level)
            cursor.execute("""
                INSERT INTO questions (
                    subject, chapter, question, difficulty, 
                    option1, option2, option3, option4, 
                    correct_answer, topic_mastery
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["Subject"].strip(),
                row["Chapter"].strip(),
                row["Question"].strip(),
                row["Difficulty Level"].strip(),
                row["Option 1"].strip(),
                row["Option 2"].strip(),
                row["Option 3"].strip(),
                row["Option 4"].strip(),
                row["Correct Answer"].strip(),
                topic_mastery
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
    
    cursor.execute("""
        SELECT question_id, question, option1, option2, option3, option4, 
               correct_answer, difficulty, chapter, topic_mastery
        FROM questions
        WHERE subject = ?
    """, (subject,))
    
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
            "chapter": row[8],
            "topic_mastery": row[9]
        } for row in questions
    ]

    random_questions = random.sample(formatted_questions, min(10, len(formatted_questions)))
    print(random_questions)
    return jsonify(random_questions)

@app.route('/submit-answers', methods=['POST'])
def submit_answers():
    try:
        data = request.get_json()
        subject = session['subject']

        if not data or "answers" not in data or "times" not in data:
            return jsonify({"message": "Invalid data format"}), 400

        user_answers = data["answers"]
        print(user_answers)
        time_spent = data["times"]
        print(time_spent)

        if not isinstance(user_answers, dict) or not isinstance(time_spent, list):
            return jsonify({"message": "Invalid data structure"}), 400

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO quizzes (subject, start_time)
            VALUES (?, CURRENT_TIMESTAMP)
        """, (subject,))
        quiz_id = cursor.lastrowid

        cursor.execute("""
            SELECT question_id, correct_answer, difficulty, chapter, topic_mastery 
            FROM questions
        """)
        question_dict = {
            row[0]: {
                "answer": row[1], 
                "difficulty": row[2], 
                "chapter": row[3],
                "topic_mastery": row[4]
            } for row in cursor.fetchall()
        }

        correct_count = 0
        results = []
        total_mastery = 0
        
        for i, (question_id, user_answer) in enumerate(user_answers.items()):
            question_id = int(question_id)
            question_info = question_dict.get(question_id, {})
            correct_answer = question_info.get("answer", None)
            is_correct = 1 if user_answer == correct_answer else 0
            difficulty = question_info.get("difficulty", "Unknown")
            topic = question_info.get("chapter", "Unknown")
            topic_mastery = question_info.get("topic_mastery", 0.0)
            time_taken = time_spent[i] if i < len(time_spent) else 0
            print(f"QID: {question_id}, User: {user_answer}, Correct: {correct_answer}")


            if is_correct:
                correct_count += 1
                total_mastery += topic_mastery

            results.append((
                quiz_id, question_id, difficulty, is_correct, 
                time_taken, topic, topic_mastery
            ))

        # Calculate average topic mastery for correct answers
        avg_topic_mastery = total_mastery / correct_count if correct_count > 0 else 0

        # Insert the student performance records
        cursor.executemany("""
            INSERT INTO student_performance (
                quiz_id, question_id, difficulty, is_correct, 
                time_taken, topic, topic_mastery
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, results)

        # Update the quiz with final score and average topic mastery
        cursor.execute("""
            UPDATE quizzes 
            SET end_time = CURRENT_TIMESTAMP,
                score = ?,
                total_questions = ?,
                subject = ?,
                avg_topic_mastery = ?
            WHERE quiz_id = ?
        """, (correct_count, len(user_answers), subject, avg_topic_mastery, quiz_id))

        conn.commit()
        conn.close()

        return redirect(url_for("quiz_results"))

    except Exception as e:
        print("Error processing quiz submission:", str(e))
        return jsonify({"message": "Error processing request", "error": str(e)}), 500
    
@app.route("/quiz_subject")
def subject():
    return render_template("quiz.html")

@app.route('/plot_performance')
def plot_performance_trend():
    conn = sqlite3.connect('quiz_data.db')
    
    df = pd.read_sql_query(
        """
        SELECT quiz_id, 
               AVG(is_correct) * 100 as accuracy, 
               AVG(time_taken) as avg_time_taken
        FROM student_performance
        GROUP BY quiz_id
        ORDER BY quiz_id
        """, 
        conn
    )
    
    conn.close()
    
    if not df.empty:
        fig, ax1 = plt.subplots(figsize=(10, 5))

        # Plot Accuracy Trend (Blue Line)
        ax1.set_xlabel("Quiz Number")
        ax1.set_ylabel("Accuracy (%)", color='b')
        ax1.plot(df['quiz_id'], df['accuracy'], marker='o', linestyle='-', color='b', label="Accuracy")
        ax1.tick_params(axis='y', labelcolor='b')

        # Create second y-axis for Average Answer Time
        ax2 = ax1.twinx()  
        ax2.set_ylabel("Avg Answer Time (s)", color='r')
        ax2.plot(df['quiz_id'], df['avg_time_taken'], marker='s', linestyle='--', color='r', label="Avg Time Taken")
        ax2.tick_params(axis='y', labelcolor='r')

        # Titles & Legend
        plt.title("Student Performance: Accuracy & Avg Answer Time Over Time")
        fig.tight_layout()
        plt.show()

        img_io = io.BytesIO()
        fig.savefig(img_io, format='png')
        img_io.seek(0)

        # Encode the image as Base64
        img_base64 = base64.b64encode(img_io.read()).decode('utf-8')

        return jsonify({"image": img_base64})
    else:
        return jsonify({"error": "No data available for this user."})
    
@app.route('/predict')
def predict():
    conn = sqlite3.connect('quiz_data.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT quiz_id
        FROM student_performance
        ORDER BY attempt_date DESC
        LIMIT 1
    """)
    
    quiz_data = cursor.fetchone()
    
    if quiz_data:
        quiz_id = quiz_data[0]
        
        # Fetch all records for the last quiz of the given student
        cursor.execute("""
            SELECT 
                is_correct, 
                time_taken, 
                difficulty, 
                topic_mastery
            FROM student_performance
            WHERE quiz_id = ?
        """, (quiz_id,))
        
        questions_data = cursor.fetchall()
        
        if questions_data:
            # Initialize variables
            total_marks = 0
            total_time = 0
            total_difficulty = 0
            total_topic_mastery = 0
            num_questions = len(questions_data)
            
            # Difficulty mapping
            difficulty_mapping = {
                "very easy": 0,
                "easy": 0,
                "moderate": 1,
                "tricky": 1,
                "tough": 2
            }
            
            # Loop through all the questions and calculate the features
            for data in questions_data:
                total_marks += data[0]  # Add 'is_correct' (1 for correct, 0 for incorrect)
                total_time += data[1]  # Add 'time_taken'
                
                # Convert difficulty to numeric value using the mapping
                difficulty_value = difficulty_mapping.get(data[2].lower(), 0)  # Default to 0 if the difficulty is unknown
                total_difficulty += difficulty_value  # Add 'difficulty'
                
                total_topic_mastery += data[3]  # Add 'topic_mastery'

            # Calculate average difficulty and average topic mastery
            avg_difficulty = total_difficulty / num_questions
            avg_topic_mastery = total_topic_mastery / num_questions


            max_marks = 10
            max_difficulty = 2
            max_topic_mastery = 1

            normalized_marks = int(total_marks) / max_marks
            normalized_difficulty = avg_difficulty / max_difficulty
            normalized_topic_mastery = float(avg_topic_mastery) / max_topic_mastery

            normalized_time = total_time / 60.0

            # Prepare the normalized input data for the model
            input_data = np.array([normalized_marks, normalized_time, normalized_difficulty, normalized_topic_mastery]).reshape(1, -1)

            
            # Predict using your model
            prediction = model.predict(input_data)
            
            # Return the prediction result
            return jsonify({'prediction': prediction.tolist()})
        else:
            return jsonify({'error': 'No question data found for the latest quiz'}), 404
    else:
        return jsonify({'error': 'No quiz data found for the given student'}), 404
    

@app.route('/quiz_results')
def quiz_results():
    
    conn = sqlite3.connect('quiz_data.db')  # Adjust your database path
    cursor = conn.cursor()

    cursor.execute("""
        SELECT difficulty, COUNT(*) 
        FROM student_performance 
        WHERE is_correct = 1
        AND quiz_id = (SELECT quiz_id FROM student_performance ORDER BY attempt_date DESC LIMIT 1)
        GROUP BY difficulty
    """)

    difficulty_data = cursor.fetchall()  # Get difficulty data
    conn.close()

    score = sum(data[1] for data in difficulty_data) 
    difficulties = [data[0] for data in difficulty_data]
    correct_answers = [data[1] for data in difficulty_data]

    # Plotting the bar chart
    plt.figure(figsize=(8, 6))
    plt.bar(difficulties, correct_answers, color='g')
    plt.xlabel('Difficulty Level')
    plt.ylabel('Correct Answers')
    plt.title('Correct Answers by Difficulty Level')
    plt.grid(True, axis='y')
    
    # Save the plot to a BytesIO object
    img_io = io.BytesIO()
    plt.savefig(img_io, format='png')
    img_io.seek(0)

    # Encode the image as Base64
    img_base64 = base64.b64encode(img_io.read()).decode('utf-8')

    # Return the rendered template with the score and image
    return render_template('QuizResults.html', score=score, total_questions=10, img_url=img_base64)

