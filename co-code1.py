import sqlite3
import pandas as pd

def get_quiz_performance(user_id, quiz_id):
    """ Fetches quiz performance data for a given user and quiz attempt """
    
    conn = sqlite3.connect('quiz.db')
    
    # Fetch quiz attempt data
    df = pd.read_sql_query(
        """
        SELECT topic, is_correct, time_taken
        FROM student_performance
        WHERE user_id = ? AND quiz_id = ?
        """, conn, params=(user_id, quiz_id)
    )
    
    conn.close()

    if df.empty:
        return "No data found for this quiz attempt."
    
    # Calculate overall accuracy
    accuracy = df['is_correct'].mean() * 100

    # Calculate average response time
    avg_response_time = df['time_taken'].mean()

    # Analyze strengths & weaknesses
    topic_analysis = df.groupby('topic')['is_correct'].mean() * 100
    strong_topics = topic_analysis[topic_analysis >= 80].index.tolist()
    weak_topics = topic_analysis[topic_analysis < 50].index.tolist()

    # Generate feedback
    feedback = generate_feedback(accuracy, strong_topics, weak_topics)

    # Display Results
    result = {
        "Accuracy (%)": round(accuracy, 2),
        "Avg Response Time (s)": round(avg_response_time, 2),
        "Strong Topics": strong_topics,
        "Weak Topics": weak_topics,
        "Feedback": feedback
    }
    
    return result


def generate_feedback(accuracy, strong_topics, weak_topics):
    """ Generates personalized feedback based on quiz performance """
    
    feedback = []
    
    if accuracy >= 80:
        feedback.append("Great job! Keep up the good work.")
    elif accuracy >= 50:
        feedback.append("You're doing well, but there's room for improvement.")
    else:
        feedback.append("Consider reviewing the material again for better understanding.")
    
    if strong_topics:
        feedback.append(f"You're strong in: {', '.join(strong_topics)}. Keep practicing!")
    
    if weak_topics:
        feedback.append(f"You need to work on: {', '.join(weak_topics)}. Consider revisiting these topics.")

    return " ".join(feedback)


# Example Usage:
user_id = 123
quiz_id = 10

performance_summary = get_quiz_performance(user_id, quiz_id)
print(performance_summary)
