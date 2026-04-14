from flask import Flask, request, session, redirect, render_template, send_from_directory
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import random

app = Flask(__name__)
app.secret_key = 'secret123'

# ---------------- CONFIG ----------------
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Haresh@2004'
app.config['MYSQL_DB'] = 'deepfake_db'

mysql = MySQL(app)

# ---------------- SERVE UPLOADED FILES ----------------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ---------------- HOME ----------------
@app.route('/')
def home():
    return '''
    <h1>Deepfake Detection System</h1>
    <a href="/register">Register</a><br><br>
    <a href="/login">Login</a>
    '''

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return '''
        <h2>Register</h2>
        <form method="POST">
            <input name="username"><br>
            <input name="email" type="email"><br>
            <input name="password" type="password"><br>
            <button type="submit">Register</button>
        </form>
        '''

    username = request.form['username']
    email = request.form['email']
    password = generate_password_hash(request.form['password'])

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO users(username,email,password) VALUES(%s,%s,%s)",
        (username, email, password)
    )
    mysql.connection.commit()
    cur.close()

    return "Registered Successfully!"

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return '''
        <h2>Login</h2>
        <form method="POST">
            <input name="email" type="email"><br>
            <input name="password" type="password"><br>
            <button type="submit">Login</button>
        </form>
        '''

    email = request.form['email']
    password = request.form['password']

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()

    if user and check_password_hash(user[3], password):
        session['user_id'] = user[0]
        session['username'] = user[1]
        return redirect('/dashboard')
    else:
        return "Invalid Login ❌"

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()

    # Theme
    cur.execute("SELECT theme FROM users WHERE id=%s", (session['user_id'],))
    theme = cur.fetchone()[0]

    # Stats
    cur.execute("SELECT COUNT(*) FROM history WHERE user_id=%s AND result='FAKE'", (session['user_id'],))
    fake_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM history WHERE user_id=%s AND result='REAL'", (session['user_id'],))
    real_count = cur.fetchone()[0]

    cur.close()

    return render_template(
        "dashboard.html",
        username=session['username'],
        theme=theme,
        fake_count=fake_count,
        real_count=real_count
    )

# ---------------- DUMMY AI ----------------
def predict_image(path):
    result = random.choice(["REAL", "FAKE"])
    confidence = random.uniform(0.7, 0.99)
    return result, confidence

# ---------------- UPLOAD ----------------
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user_id' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute("SELECT theme FROM users WHERE id=%s", (session['user_id'],))
    theme = cur.fetchone()[0]
    cur.close()

    if request.method == 'POST':
        file = request.files['file']

        if file.filename == '':
            return "No file selected"

        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        filepath = filename  # ✅ only store filename

        result, confidence = predict_image(filepath)

        # Save to DB
        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO history(user_id, file_path, result, confidence) VALUES(%s,%s,%s,%s)",
            (session['user_id'], filepath, result, confidence)
        )
        mysql.connection.commit()
        cur.close()

        return render_template("upload.html", result=result, confidence=confidence, theme=theme)

    return render_template("upload.html", theme=theme)

# ---------------- HISTORY ----------------
@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT file_path, result, confidence, created_at FROM history WHERE user_id=%s",
        (session['user_id'],)
    )
    data = cur.fetchall()

    cur.execute("SELECT theme FROM users WHERE id=%s", (session['user_id'],))
    theme = cur.fetchone()[0]

    cur.close()

    return render_template("history.html", data=data, theme=theme)

# ---------------- THEME TOGGLE ----------------
@app.route('/toggle-theme')
def toggle_theme():
    if 'user_id' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute("SELECT theme FROM users WHERE id=%s", (session['user_id'],))
    current = cur.fetchone()[0]

    new_theme = 'dark' if current == 'light' else 'light'

    cur.execute("UPDATE users SET theme=%s WHERE id=%s", (new_theme, session['user_id']))
    mysql.connection.commit()
    cur.close()

    return redirect('/dashboard')

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)