from flask import render_template, request, redirect, url_for, session, jsonify
from app import app

# Sample questions
questions = [
    {"question": "What is the capital of France?", "options": ["Berlin", "Madrid", "Paris", "Rome"], "answer": "Paris"},
    {"question": "Which planet is known as the Red Planet?", "options": ["Earth", "Mars", "Jupiter", "Venus"], "answer": "Mars"},
    {"question": "What is the largest ocean on Earth?", "options": ["Atlantic", "Indian", "Arctic", "Pacific"], "answer": "Pacific"}
]

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/quiz")
def quiz():
    return render_template("quizpage.html")


@app.route('/get_questions')
def get_questions():
    return jsonify(questions)

@app.route('/submit-answers', methods=['POST'])
def submit_answers():
    try:
        data = request.get_json()

        # Ensure data is present
        if not data or "answers" not in data or "times" not in data:
            return jsonify({"message": "Invalid data format"}), 400
        
        user_answers = data.get("answers", {})
        time_spent = data.get("times", [])

        # Ensure we have valid data structures
        if not isinstance(user_answers, dict) or not isinstance(time_spent, list):
            return jsonify({"message": "Invalid data structure"}), 400
        
        # Convert string indices to integers and create a clean answers dict
        clean_answers = {}
        for index, answer in user_answers.items():
            try:
                clean_answers[int(index)] = answer
            except ValueError:
                continue

        # Count correct answers
        correct_count = 0
        for i, answer in clean_answers.items():
            if i < len(questions) and answer == questions[i]["answer"]:
                correct_count += 1

        # Calculate total time
        total_time = sum(time_spent)
        minutes = total_time // 60
        seconds = total_time % 60
        
        print("User answers:", clean_answers)
        print("Time spent per question:", time_spent)
        print(f"Total time: {minutes}m {seconds}s")
        
        return jsonify({
            "message": f"Quiz completed!\nYou got {correct_count} out of {len(questions)} correct!\nTotal time: {minutes}m {seconds}s",
            "details": {
                "correct_count": correct_count,
                "total_questions": len(questions),
                "time_spent": time_spent,
                "total_time": total_time
            }
        })

    except Exception as e:
        print("Error processing quiz submission:", str(e))
        return jsonify({"message": "Error processing request", "error": str(e)}), 500