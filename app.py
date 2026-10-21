import json
import os
import random
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'super_secret_key_10_class'

DB_FILE = 'quizzes.json'
UPLOAD_FOLDER = os.path.join('static', 'uploads')

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def load_data():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_data(data):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


@app.route("/", methods=["GET", "POST"])
def create_quiz():
    """1. КРЕАТИВ-ЗОНА"""
    if request.method == "POST":
        title = request.form.get('quiz_title')
        q_count = int(request.form.get('questions_count', 1))
        
        questions_list = []
        for i in range(1, q_count + 1):
            q_text = request.form.get(f'question_text_{i}')
            if q_text:
                image_file = request.files.get(f'q_image_{i}')
                image_name = None
                if image_file and image_file.filename != '':
                    image_name = f"img_{random.randint(100000, 999999)}_{image_file.filename}"
                    image_file.save(os.path.join(UPLOAD_FOLDER, image_name))
                
                options = []
                j = 1
                while True:
                    opt = request.form.get(f'q_{i}_option_{j}')
                    if opt is None:
                        break
                    options.append(opt)
                    j += 1
                
                correct_idx = int(request.form.get(f'q_{i}_correct', 0))
                
                questions_list.append({
                    "id": i,
                    "text": q_text,
                    "image": image_name,
                    "options": options,
                    "correct": correct_idx,
                    "stats": [0] * len(options)
                })

        quiz_content = {
            "title": title,
            "current_question_index": -1, # Начинаем в Лобби
            "questions": questions_list,
            "connected_players": [],
            "results": {}
        }
        
        quiz_id = str(random.randint(1000, 9999))
        db = load_data()
        db[quiz_id] = quiz_content
        save_data(db)
        
        student_link = request.host_url.rstrip("/") + f"/q/{quiz_id}"
        teacher_link = request.host_url.rstrip("/") + f"/t/{quiz_id}"
        
        return render_template("create.html", step="done", student_link=student_link, teacher_link=teacher_link)
        
    return render_template("create.html", step="form")


@app.route("/q/<quiz_id>", methods=["GET", "POST"])
def student_join(quiz_id):
    """2. РЕГИСТРАЦИЯ УЧЕНИКА"""
    db = load_data()
    if quiz_id not in db:
        return "<h1>Викторина не найдена!</h1>", 404
        
    if request.method == "POST":
        username = request.form.get('username', 'Аноним').strip()
        session['username'] = username
        session['score'] = 0
        session['current_q_index'] = -1 
        
        if username not in db[quiz_id]['connected_players']:
            db[quiz_id]['connected_players'].append(username)
            save_data(db)
            
        return redirect(url_for('student_wait_next', quiz_id=quiz_id))
        
    quiz = db[quiz_id]
    return render_template("start.html", title=quiz['title'], quiz_id=quiz_id)
@app.route("/q/<quiz_id>/question", methods=["GET", "POST"])
def student_question(quiz_id):
    """3. ОКНО ВОПРОСА ДЛЯ УЧЕНИКА"""
    db = load_data()
    if quiz_id not in db:
        return "<h1>Викторина не найдена!</h1>", 404
        
    quiz = db[quiz_id]
    questions = quiz['questions']
    teacher_q_idx = quiz['current_question_index']
    
    if teacher_q_idx == -1:
        return redirect(url_for('student_wait_next', quiz_id=quiz_id))
    if teacher_q_idx >= len(questions):
        return redirect(url_for('student_final', quiz_id=quiz_id))
        
    session['current_q_index'] = teacher_q_idx
    current_question = questions[teacher_q_idx]
    
    if request.method == "POST":
        user_choice = request.form.get('answer')
        if user_choice is not None:
            user_choice = int(user_choice)
            if user_choice == current_question['correct']:
                session['score'] = session.get('score', 0) + 1
            
            db[quiz_id]['questions'][teacher_q_idx]['stats'][user_choice] += 1
            save_data(db)
            
            return redirect(url_for('student_wait_next', quiz_id=quiz_id))
            
    return render_template(
        "question.html", 
        quiz=quiz, 
        question=current_question, 
        q_num=teacher_q_idx + 1, 
        total_q=len(questions),
        quiz_id=quiz_id
    )


@app.route("/q/<quiz_id>/wait")
def student_wait_next(quiz_id):
    """4. ОКНО ОЖИДАНИЯ С УМНЫМ ОБНОВЛЕНИЕМ"""
    db = load_data()
    if quiz_id not in db:
        return "<h1>Викторина не найдена!</h1>", 404
    quiz = db[quiz_id]
    
    if quiz['current_question_index'] >= len(quiz['questions']):
        return redirect(url_for('student_final', quiz_id=quiz_id))
    
    if quiz['current_question_index'] != session.get('current_q_index', -1):
        return redirect(url_for('student_question', quiz_id=quiz_id))
        
    return render_template("wait.html", quiz_id=quiz_id, current_q_idx=session.get('current_q_index', -1))


@app.route("/api/status/<quiz_id>")
def get_quiz_status(quiz_id):
    db = load_data()
    if quiz_id not in db:
        return jsonify({"status": "error"}), 404
    
    quiz = db[quiz_id]
    current_q = quiz['current_question_index']
    
    current_stats = []
    if 0 <= current_q < len(quiz['questions']):
        current_stats = quiz['questions'][current_q]['stats']
        
    return jsonify({
        "current_question_index": current_q,
        "total_questions": len(quiz['questions']),
        "players": quiz['connected_players'],
        "stats": current_stats
    })


@app.route("/q/<quiz_id>/final")
def student_final(quiz_id):
    """Экран финала для ученика"""
    db = load_data()
    if quiz_id not in db:
        return "Викторина завершена", 404
    
    username = session.get('username', 'Аноним')
    final_score = session.get('score', 0)
    
    db[quiz_id]['results'][username] = final_score
    save_data(db)
    
    sorted_results = sorted(db[quiz_id]['results'].items(), key=lambda item: item[1], reverse=True)
    return render_template("results.html", quiz=db[quiz_id], sorted_results=sorted_results, student_view=True, my_score=final_score)


@app.route("/t/<quiz_id>", methods=["GET", "POST"])
def teacher_panel(quiz_id):
    """5. ПАНЕЛЬ УПРАВЛЕНИЯ УЧИТЕЛЯ"""
    db = load_data()
    if quiz_id not in db:
        return "<h1>Панель управления не найдена!</h1>", 404
        
    quiz = db[quiz_id]
    current_q = quiz['current_question_index']
    total_q = len(quiz['questions'])
    
    if request.method == "POST":
        if current_q < total_q - 1:
            db[quiz_id]['current_question_index'] += 1
            save_data(db)
            return redirect(url_for('teacher_panel', quiz_id=quiz_id))
        else:
            db[quiz_id]['current_question_index'] = total_q
            save_data(db)
            sorted_results = sorted(quiz['results'].items(), key=lambda item: item[1], reverse=True)
            return render_template("results.html", quiz=quiz, sorted_results=sorted_results, student_view=False)
            
    return render_template("teacher.html", quiz=quiz, current_q=current_q, total_q=total_q, quiz_id=quiz_id)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=4252, debug=True)
