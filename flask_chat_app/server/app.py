from flask import Flask, render_template, request, jsonify, send_from_directory, url_for
from cryptography.fernet import Fernet  # Mã hóa và giải mã hóa đối xứng
import json
import hashlib  # sử dụng hàm băm sha256
import os
from datetime import datetime
import uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__, static_folder=None)
app.secret_key = '14022005'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * \
    1024  # giới hạn kích thước file 16MB
USER_DB = 'users.json'
MESSAGE_DB = 'messages.json'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt'}


class ChatServer:
    def __init__(self):
        self.online_users = set()
        self.key = Fernet.generate_key()
        self.cipher = Fernet(self.key)

        if not os.path.exists(USER_DB):
            with open(USER_DB, 'w') as f:
                json.dump({}, f)
        if not os.path.exists(MESSAGE_DB):
            with open(MESSAGE_DB, 'w') as f:
                json.dump({}, f)

    def register_user(self, username, password):
        with open(USER_DB, 'r') as f:
            users = json.load(f)

        if username in users:
            return False

        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        users[username] = hashed_pw

        with open(USER_DB, 'w') as f:
            json.dump(users, f)

        return True

    def authenticate_user(self, username, password):
        with open(USER_DB, 'r') as f:
            users = json.load(f)

        if username not in users:
            return False

        hashed_pw = hashlib.sha256(password.encode()).hexdigest()
        return users[username] == hashed_pw

    def save_message(self, sender, recipient, message, file_url=None, file_name=None):
        with open(MESSAGE_DB, 'r') as f:
            messages = json.load(f)

        key = f"{sender}_{recipient}" if sender < recipient else f"{recipient}_{sender}"

        if key not in messages:
            messages[key] = []

        messages[key].append({
            'sender': sender,
            'recipient': recipient,
            'message': message,
            'file_url': file_url,
            'file_name': file_name,
            'timestamp': str(datetime.now()),
            'type': 'file' if file_url else 'text'
        })

        with open(MESSAGE_DB, 'w') as f:
            json.dump(messages, f)

    def get_messages(self, user1, user2):
        with open(MESSAGE_DB, 'r') as f:
            messages = json.load(f)

        key = f"{user1}_{user2}" if user1 < user2 else f"{user2}_{user1}"
        return messages.get(key, [])


@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    if server.register_user(data['username'], data['password']):
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Username already exists'}), 400


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    if server.authenticate_user(data['username'], data['password']):
        server.online_users.add(data['username'])
        return jsonify({
            'status': 'success',
            'encryption_key': server.key.decode()
        })
    return jsonify({'status': 'error', 'message': 'Invalid credentials'}), 401


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def server_dashboard():
    return render_template('server.html', online_users=list(server.online_users))


@app.route('/api/send_message', methods=['POST'])
def send_message():
    data = request.json
    server.save_message(
        data['sender'],
        data['recipient'],
        data['message'],
        data.get('file_url'),
        data.get('file_name')
    )
    return jsonify({'status': 'success'})


@app.route('/api/get_messages', methods=['GET'])
def get_messages():
    user1 = request.args.get('user1')
    user2 = request.args.get('user2')
    messages = server.get_messages(user1, user2)
    return jsonify({'status': 'success', 'messages': messages})


@app.route('/api/online_users', methods=['GET'])
def online_users():
    return jsonify({'status': 'success', 'users': list(server.online_users)})


@app.route('/api/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'message': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        try:
            # Tạo tên file duy nhất
            filename = str(uuid.uuid4()) + '.' + \
                file.filename.rsplit('.', 1)[1].lower()

            # Đảm bảo thư mục uploads tồn tại
            os.makedirs(UPLOAD_FOLDER, exist_ok=True)

            # Đường dẫn đầy đủ đến file
            file_path = os.path.join(UPLOAD_FOLDER, filename)

            # Lưu file
            file.save(file_path)

            # Tạo URL cho client (http://localhost:5000/static-files/filename)
            file_url = f'http://localhost:5000/static-files/{filename}'

            print(f"File saved at: {file_path}")
            print(f"URL generated: {file_url}")

            return jsonify({
                'status': 'success',
                'file_url': file_url,
                'file_name': file.filename
            })
        except Exception as e:
            print(f"Error uploading file: {str(e)}")
            return jsonify({'status': 'error', 'message': f'Upload error: {str(e)}'}), 500

    return jsonify({'status': 'error', 'message': 'File type not allowed'}), 400

@app.route('/download-file/<filename>')
def force_download_file(filename):
    """
    API cụ thể để download file, với as_attachment=True để buộc browser tải xuống
    """
    try:
        print(f"Attempting to download: {filename}")
        return send_from_directory(
            UPLOAD_FOLDER,
            filename,
            as_attachment=True
        )
    except Exception as e:
        print(f"Error downloading file: {str(e)}")
        return jsonify({'status': 'error', 'message': f'Download error: {str(e)}'}), 404


server = ChatServer()
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
