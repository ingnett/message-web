from flask import Flask, render_template, request, session, redirect, url_for
from cryptography.fernet import Fernet #Fernet: Là mã hóa đối xứng 
import requests #Gửi các request như GET, POST,..
from flask import jsonify #chuyển dict, list thành json 
import os
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', '14022005')#Thiết lập khóa bí mật 

SERVER_URL = 'http://localhost:5000'

#Trang chủ
@app.route('/')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('chat'))
#Login register 
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username')
        password = request.form.get('password')
        
        if action == 'register':
            response = requests.post(f"{SERVER_URL}/api/register", json={
                'username': username,
                'password': password
            })
            if response.json().get('status') == 'success':
                return render_template('login.html', message='Registration successful! Please login.')
        
        response = requests.post(f"{SERVER_URL}/api/login", json={
            'username': username,
            'password': password
        })
        
        data = response.json()
        if data.get('status') == 'success':
            session['username'] = username
            session['encryption_key'] = data['encryption_key']
            return redirect(url_for('chat'))
        
        return render_template('login.html', message='Invalid credentials')
    
    return render_template('login.html')

#Chat
@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    
    # Danh sách user online
    try:
        response = requests.get(f"{SERVER_URL}/api/online_users")
        response.raise_for_status()
        online_users = [u for u in response.json().get('users', []) if u != username]
    except requests.RequestException as e:
        return render_template('chat.html', username=username, error=f"Error fetching online users: {str(e)}")
    
    # gửi tin nhắn đi 
    if request.method == 'POST':
        recipient = request.form.get('recipient')
        message = request.form.get('message')
        file_url = None
        file_name = None

        if 'file' in request.files and request.files['file'].filename:
            file = request.files['file']
            try:
                response = requests.post(f"{SERVER_URL}/api/upload_file", files={'file': (file.filename, file.stream, file.mimetype)})
                response.raise_for_status()
                if response.json().get('status') == 'success':
                    file_url = response.json()['file_url']
                    file_name = file.filename
                else:
                    return render_template('chat.html', username=username, online_users=online_users, 
                                        selected_user=recipient, messages=[], error=f"Failed to upload file: {response.json().get('message')}")
            except requests.RequestException as e:
                return render_template('chat.html', username=username, online_users=online_users, 
                                    selected_user=recipient, messages=[], error=f"File upload error: {str(e)}")

        try:
            cipher = Fernet(session['encryption_key'].encode())
            encrypted_msg = cipher.encrypt(message.encode()).decode() if message else ''
        except Exception as e:
            return render_template('chat.html', username=username, online_users=online_users, 
                                selected_user=recipient, messages=[], error=f"Encryption error: {str(e)}")

        try:
            response = requests.post(f"{SERVER_URL}/api/send_message", json={
                'sender': username,
                'recipient': recipient,
                'message': encrypted_msg,
                'file_url': file_url,
                'file_name': file_name
            })
            response.raise_for_status()
        except requests.RequestException as e:
            return render_template('chat.html', username=username, online_users=online_users, 
                                selected_user=recipient, messages=[], error=f"Message sending error: {str(e)}")

        
        return redirect(url_for('chat', **{'with': recipient}))


    # Lấy tin nhắn giữa 2 người dùng 
    selected_user = request.args.get('with', online_users[0] if online_users else None)
    
    messages = []
    if selected_user:
        try:
            response = requests.get(f"{SERVER_URL}/api/get_messages", params={
                'user1': username,
                'user2': selected_user
            })
            response.raise_for_status()
            cipher = Fernet(session['encryption_key'].encode())
            for msg in response.json().get('messages', []):
                try:
                    decrypted_msg = cipher.decrypt(msg['message'].encode()).decode() if msg['message'] else ''
                    messages.append({
                        'sender': msg['sender'],
                        'message': decrypted_msg,
                        'file_url': msg.get('file_url'),
                        'file_name': msg.get('file_name'),
                        'timestamp': msg['timestamp'],
                        'type': msg.get('type', 'text')
                    })
                except Exception:
                    continue
        except requests.RequestException as e:
            return render_template('chat.html', username=username, online_users=online_users, 
                                 selected_user=selected_user, messages=[], error=f"Error fetching messages: {str(e)}")
    
    return render_template('chat.html',
                         username=username,
                         online_users=online_users,
                         selected_user=selected_user,
                         messages=messages)

#Danh sách các tin nhắn giữa 2 người ùng 
@app.route('/api/get_messages', methods=['GET'])
def get_messages_api():
    user1 = request.args.get('user1')
    user2 = request.args.get('user2')

    try:
        response = requests.get(f"{SERVER_URL}/api/get_messages", params={
            'user1': user1,
            'user2': user2
        })
        response.raise_for_status()
        #Giai mã 
        cipher = Fernet(session['encryption_key'].encode())
        messages = []
        for msg in response.json().get('messages', []):
            try:
                decrypted_msg = cipher.decrypt(msg['message'].encode()).decode() if msg['message'] else ''
                messages.append({
                    'sender': msg['sender'],
                    'message': decrypted_msg,
                    'file_url': msg.get('file_url'),
                    'file_name': msg.get('file_name'),
                    'timestamp': msg['timestamp'],
                    'type': msg.get('type', 'text')
                })
            except Exception:
                continue
        return jsonify({'messages': messages})

    except requests.RequestException as e:
        return jsonify({'error': str(e)}), 500
#Logout
@app.route('/logout')
def logout():
    username = session.get('username')
    if username:
        try:
            requests.post(f"{SERVER_URL}/api/logout", json={'username': username})
        except requests.RequestException:
            pass  # Có thể log lỗi nếu cần
    session.pop('username', None)
    session.pop('encryption_key', None)
    return redirect(url_for('login'))

SERVER_URL = 'http://localhost:5000'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)