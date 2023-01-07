import os
import random
import string
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = './uploads'
db = SQLAlchemy()
migrate = Migrate()
db.init_app(app)
migrate.init_app(app, db)


class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    p = db.Column(db.Text, nullable=False)
    public_key_1 = db.Column(db.Text, nullable=False)
    public_key_2 = db.Column(db.Text)
    ip_1 = db.Column(db.String, nullable=False)
    ip_2 = db.Column(db.String)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_number = db.Column(db.String, nullable=False)
    text = db.Column(db.Text)
    file = db.Column(db.String, unique=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'))


def generate_name() -> str:
    symbols = string.ascii_letters + string.digits
    name = ''.join([random.choice(symbols) for _ in range(50)])
    return name


@app.get('/')
def home():
    return render_template('home.html')


@app.get('/room/<name>')
def get_room(name):
    room = db.session.query(Room).filter_by(name=name).first()
    if room is not None:
        data = {
            'name': room.name,
            'p': room.p,
            'public_key_1': room.public_key_1,
            'public_key_2': room.public_key_2
        }
        return jsonify(data)
    else:
        return jsonify({'error': 'Room not found'})


@app.get('/room/<name>/messages')
def get_messages(name):
    room = db.session.query(Room).filter_by(name=name).first()
    if room is not None:
        messages = db.session.query(Message).filter_by(room_id=room.id).order_by(Message.timestamp).all()
        data = []
        for i in messages:
            data.append({
                'sender_number': i.sender_number,
                'text': i.text,
                'file': i.file
            })
        return jsonify({'messages': data})
    else:
        return jsonify({'error': 'Room not found'})


@app.post('/create-room')
def create_room():
    p = request.form['p']
    public_key_1 = request.form['public_key_1']
    ip = request.remote_addr
    if db.session.query(Room).filter_by(ip_1=ip).first() is None and db.session.query(Room).filter_by(ip_2=ip).first() is None:
        if len(p) == 309 and len(public_key_1) <= 309:
            while True:
                name = generate_name()
                if db.session.query(Room).filter_by(name=name).first() is not None:
                    continue
                else:
                    break
            room = Room(name=name, p=p, public_key_1=public_key_1, ip_1=ip)
            db.session.add(room)
            db.session.commit()
            return jsonify({'success': f'Room {name} successfully created.\nKeep it in a safe place. Share the name of the room with the interlocutor.'})
        else:
            return jsonify({'error': 'Incorrect input'})
    else:
        return jsonify({'error': f'Your IP ({ip}) is already linked to another room'})


@app.post('/confirm-room')
def confirm_room():
    name = request.form['name']
    public_key_2 = request.form['public_key_2']
    ip = request.remote_addr
    room = db.session.query(Room).filter_by(name=name).first()
    if room is not None:
        if ip != room.ip_1 and ip != room.ip_2:
            if room.public_key_2 is None:
                if public_key_2 != room.public_key_1 and len(public_key_2) <= 309:
                    room.public_key_2 = public_key_2
                    room.ip_2 = ip
                    db.session.commit()
                    return jsonify({'success': 'Room is confirmed'})
                else:
                    return jsonify({'error': 'Incorrect public key'})
            else:
                return jsonify({'error': 'Room is already confirmed'})
        else:
            return jsonify({'error': f'Your IP ({ip}) is already linked to another room'})
    else:
        return jsonify({'error': 'Room not found'})


@app.post('/delete-room')
def delete_room():
    name = request.form['name']
    public_key = request.form['public_key']
    room = db.session.query(Room).filter_by(name=name).first()
    if room is not None:
        if public_key == room.public_key_1 or public_key == room.public_key_2:
            messages = db.session.query(Message).filter_by(room_id=room.id).all()
            db.session.delete(room)
            for i in messages:
                db.session.delete(i)
            db.session.commit()
            return jsonify({'success': 'Room is deleted'})
        else:
            return jsonify({'error': 'Incorrect public key'})
    else:
        return jsonify({'error': 'Room not found'})


@app.post('/new-text-message')
def new_text_message():
    name = request.form['name']
    text = request.form['text']
    sender_number = request.form['sender_number']
    room = db.session.query(Room).filter_by(name=name).first()
    if room is not None:
        if sender_number in ('1', '2'):
            messages = db.session.query(Message).filter_by(room_id=room.id, sender_number=sender_number).all()
            length = 0
            for i in messages:
                if i.text is not None:
                    length += len(i.text)
            print(length)
            if length < 50000:
                message = Message(room_id=room.id, sender_number=sender_number, text=text)
                db.session.add(message)
                db.session.commit()
                return jsonify({'success': 'Message sent'})
        else:
            return jsonify({'error': 'Room not found'})
    else:
        return jsonify({'error': 'Room not found'})


@app.post('/upload-file')
def upload_file():
    name = request.form['name']
    file = request.files['file']
    sender_number = request.form['sender_number']
    room = db.session.query(Room).filter_by(name=name).first()
    if room is not None:
        if sender_number in ('1', '2'):
            filename = secure_filename(file.filename)
            file_format = filename[len(filename) - 3:]
            if file_format in ('png', 'wav'):
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                while True:
                    new_filename = generate_name() + '.' + file_format
                    if db.session.query(Message).filter_by(file=new_filename).first() is not None:
                        continue
                    else:
                        break
                message = Message(room_id=room.id, sender_number=sender_number, file=new_filename)
                db.session.add(message)
                db.session.commit()
                os.rename(os.path.join(app.config['UPLOAD_FOLDER'], filename), os.path.join(app.config['UPLOAD_FOLDER'], new_filename))
                return jsonify({'success': 'File sent'})
            else:
                return jsonify({'error': 'Incorrect format'})
        else:
            return jsonify({'error': 'Room not found'})
    else:
        return jsonify({'error': 'Room not found'})


@app.get('/uploads/<name>')
def open_file(name):
    return send_from_directory(app.config['UPLOAD_FOLDER'], name)


@app.get('/clean-db')
def clean_db():
    rooms = db.session.query(Room).all()
    for i in rooms:
        message = db.session.query(Message).filter_by(room_id=i.id).first()
        diff = datetime.utcnow() - message.timestamp
        if diff.days > 365:
            db.session.delete(message)
            db.session.commit()
    return jsonify({'success': 'Cleaned'})


if __name__ == '__main__':
    app.run(host='0.0.0.0')

