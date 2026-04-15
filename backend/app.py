from flask import Flask, request, session, redirect, render_template, send_from_directory
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
import os
import tensorflow as tf
import numpy as np
from PIL import Image
import random

app = Flask(__name__)
app.secret_key = 'secret123'

# ---------------- CONFIG ----------------
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------------- DB CONFIG ----------------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Haresh@2004'
app.config['MYSQL_DB'] = 'deepfake_db'

mysql = MySQL(app)

# ---------------- MAIL CONFIG ----------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'hareshhariharan31@gmail.com'   # CHANGE THIS
app.config['MAIL_PASSWORD'] = 'ikryqawocyjiifyv'      # CHANGE THIS

mail = Mail(app)

# ---------------- LOAD MODEL ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model", "deepfake_model.h5")

model = tf.keras.models.load_model(MODEL_PATH)

# ---------------- SERVE UPLOADED FILES ----------------
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ---------------- HOME ----------------
@app.route('/')
def home():
    return render_template("home.html")

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template("register.html")

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

    return redirect('/login')

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template("login.html")

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

    cur.execute("SELECT theme FROM users WHERE id=%s", (session['user_id'],))
    theme = cur.fetchone()[0]

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

# ---------------- AI PREDICTION ----------------
def predict_image(path):
    img = Image.open(path).convert("RGB").resize((224, 224))
    img = np.array(img) / 255.0
    img = np.expand_dims(img, axis=0)

    pred = model.predict(img)[0][0]

    if pred > 0.5:
        return "FAKE", float(pred)
    else:
        return "REAL", float(1 - pred)

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
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(full_path)

        result, confidence = predict_image(full_path)

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO history(user_id, file_path, result, confidence) VALUES(%s,%s,%s,%s)",
            (session['user_id'], filename, result, confidence)
        )
        mysql.connection.commit()
        cur.close()

        return render_template(
            "upload.html",
            result=result,
            confidence=confidence,
            theme=theme
        )

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

# ---------------- FORGOT PASSWORD ----------------
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template("forgot.html")

    email = request.form['email']

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()

    if not user:
        return "Email not found ❌"

    otp = str(random.randint(100000, 999999))

    session['reset_email'] = email
    session['otp'] = otp

    msg = Message(
        'Password Reset OTP',
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )
    msg.body = f'Your OTP is: {otp}'

    mail.send(msg)

    return redirect('/verify-otp')

# ---------------- VERIFY OTP ----------------
@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'GET':
        return render_template("otp.html")

    user_otp = request.form['otp']

    if user_otp == session.get('otp'):
        return redirect('/reset-password')
    else:
        return "Invalid OTP ❌"

# ---------------- RESET PASSWORD ----------------
@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'GET':
        return render_template("reset.html")

    password = request.form['password']
    confirm = request.form['confirm']

    if password != confirm:
        return "Passwords do not match ❌"

    hashed = generate_password_hash(password)

    cur = mysql.connection.cursor()
    cur.execute(
        "UPDATE users SET password=%s WHERE email=%s",
        (hashed, session.get('reset_email'))
    )
    mysql.connection.commit()
    cur.close()

    session.pop('otp', None)
    session.pop('reset_email', None)

    return redirect('/login')

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