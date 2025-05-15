import os
import jwt
import bcrypt

from flask import Flask, request, jsonify
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from uuid import uuid4
from urllib.parse import quote_plus

load_dotenv()

app = Flask(__name__)

SECRET_KEY = os.getenv('JWT_SECRET_KEY')
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = str(os.getenv('MYSQL_PASSWORD'))
MYSQL_PORT = os.getenv('MYSQL_PORT','')

password = quote_plus(MYSQL_PASSWORD)

app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql://{MYSQL_USER}:{password}@{MYSQL_HOST}{MYSQL_PORT}/microservices"
print(app.config['SQLALCHEMY_DATABASE_URI'])

db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'USERS'
    id = db.Column(db.String(36), primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)


@app.route('/api/v1/auth/login', methods=["POST"])
def login():
    email = request.form['email']
    password = request.form['password']

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    if not bcrypt.checkpw(password.encode('utf-8'), user.password.encode('utf-8')):
        return jsonify({"error": "Invalid email or password"}), 401

    payload = {
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.utcnow() + timedelta(hours=1)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')

    return jsonify({"token": token}), 200


@app.route('/api/v1/auth/signup', methods=["POST"])
def signup():
    email = request.form['email']
    password = request.form['password']

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "Email already registered"}), 401

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    new_user = User(
        id=str(uuid4()),
        email=email,
        password=hashed_password.decode('utf-8')
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"}), 201


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
