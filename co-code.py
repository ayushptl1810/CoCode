
CREATE TABLE IF NOT EXISTS student_performance (
    user_id INTEGER,
    quiz_id INTEGER,
    question_id INTEGER,
    difficulty TEXT,       -- Easy, Medium, Hard
    is_correct INTEGER,    -- 1 if correct, 0 if incorrect
    time_taken INTEGER,    -- Time in seconds
    topic TEXT,            -- Topic of the question
    attempt_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


#Calculate Overall Accuracy Rate 
import sqlite3

def get_accuracy_rate(user_id):
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()
    
    query = """SELECT COUNT(*) as total, SUM(is_correct) as correct
               FROM student_performance WHERE user_id = ?"""
    cursor.execute(query, (user_id,))
    total, correct = cursor.fetchone()
    
    conn.close()
    
    return round((correct / total) * 100, 2) if total > 0 else 0

#Track Average Response Time Per Question
def get_avg_response_time(user_id):
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()

    query = """SELECT AVG(time_taken) FROM student_performance WHERE user_id = ?"""
    cursor.execute(query, (user_id,))
    avg_time = cursor.fetchone()[0]

    conn.close()
    
    return round(avg_time, 2) if avg_time else "No data"

#Analyze Topic-Wise Strengths & Weaknesses
def get_topic_performance(user_id):
    conn = sqlite3.connect('quiz.db')
    cursor = conn.cursor()

    query = """SELECT topic, COUNT(*) as total, SUM(is_correct) as correct
               FROM student_performance
               WHERE user_id = ?
               GROUP BY topic"""
    cursor.execute(query, (user_id,))
    results = cursor.fetchall()
    conn.close()

    topic_performance = {topic: round((correct / total) * 100, 2) for topic, total, correct in results}
    return topic_performance

#Plot Accuracy Over Time and plot avg response time
import matplotlib.pyplot as plt
import pandas as pd
import sqlite3

def plot_performance_trend(user_id):
    conn = sqlite3.connect('quiz.db')
    
    df = pd.read_sql_query(
        """
        SELECT DATE(attempt_date) as date, 
               AVG(is_correct) * 100 as accuracy, 
               AVG(time_taken) as avg_time_taken
        FROM student_performance
        WHERE user_id = ?
        GROUP BY DATE(attempt_date)
        """, 
        conn, params=(user_id,)
    )
    
    conn.close()
    
    if not df.empty:
        fig, ax1 = plt.subplots(figsize=(10, 5))

        # Plot Accuracy Trend (Blue Line)
        ax1.set_xlabel("Date")
        ax1.set_ylabel("Accuracy (%)", color='b')
        ax1.plot(df['date'], df['accuracy'], marker='o', linestyle='-', color='b', label="Accuracy")
        ax1.tick_params(axis='y', labelcolor='b')

        # Create second y-axis for Average Answer Time
        ax2 = ax1.twinx()  
        ax2.set_ylabel("Avg Answer Time (s)", color='r')
        ax2.plot(df['date'], df['avg_time_taken'], marker='s', linestyle='--', color='r', label="Avg Time Taken")
        ax2.tick_params(axis='y', labelcolor='r')

        # Titles & Legend
        plt.title("Student Performance: Accuracy & Avg Answer Time Over Time")
        fig.tight_layout()
        plt.show()
    else:
        print("No data available for this user.")



#Personalized Feedback System
def generate_feedback(user_id):
    accuracy = get_accuracy_rate(user_id)
    topic_performance = get_topic_performance(user_id)

    feedback = []

    # Overall performance
    if accuracy > 80:
        feedback.append("Great job! Keep up the good work. 🎉")
    elif accuracy > 50:
        feedback.append("You're doing well, but there's room for improvement. Keep practicing!")
    else:
        feedback.append("You need more practice. Try reviewing the questions you got wrong. 💡")

    # Topic-specific feedback
    for topic, score in topic_performance.items():
        if score < 50:
            feedback.append(f"You are struggling with {topic}. Consider revising it!")

    return feedback
