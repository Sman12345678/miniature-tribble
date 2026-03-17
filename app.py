from flask import Flask, request, jsonify,send_file, abort
import os
from flask_cors import CORS
import sqlite3
import hashlib
import uuid
import json
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app, origins="*")

DATABASE = 'chatflow.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            display_name TEXT,
            bio TEXT DEFAULT '',
            is_online BOOLEAN DEFAULT 0,
            last_seen TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Chats table
    c.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT,
            participants TEXT NOT NULL,
            admin_ids TEXT,
            unread_count INTEGER DEFAULT 0,
            is_muted BOOLEAN DEFAULT 0,
            mute_until TIMESTAMP,
            last_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Messages table
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            chat_id TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            type TEXT DEFAULT 'text',
            content TEXT NOT NULL,
            file_data TEXT,
            reactions TEXT DEFAULT '[]',
            status TEXT DEFAULT 'sent',
            is_edited BOOLEAN DEFAULT 0,
            is_deleted BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats(id),
            FOREIGN KEY (sender_id) REFERENCES users(id)
        )
    ''')
    
    # Statuses table
    c.execute('''
        CREATE TABLE IF NOT EXISTS statuses (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Games table
    c.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id TEXT PRIMARY KEY,
            chat_id TEXT NOT NULL,
            game_type TEXT NOT NULL,
            game_state TEXT NOT NULL,
            current_player TEXT,
            players TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats(id)
        )
    ''')
    
    # AI Conversations table
    c.execute('''
        CREATE TABLE IF NOT EXISTS ai_conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            messages TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# =============================================================================
# Auth Routes
# =============================================================================

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    display_name = data.get('displayName', '').strip() or username
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    user_id = str(uuid.uuid4())
    hashed_pw = hash_password(password)
    
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            'INSERT INTO users (id, username, password, display_name, is_online, last_seen) VALUES (?, ?, ?, ?, ?, ?)',
            (user_id, username, hashed_pw, display_name, True, datetime.now())
        )
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'user': {
                'id': user_id,
                'username': username,
                'displayName': display_name,
                'bio': '',
                'isOnline': True,
                'lastSeen': datetime.now().isoformat(),
                'createdAt': datetime.now().isoformat()
            }
        }), 201
        
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username already exists'}), 409

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username = ? AND password = ?', 
              (username, hash_password(password)))
    user = c.fetchone()
    
    if user:
        c.execute('UPDATE users SET is_online = ?, last_seen = ? WHERE id = ?',
                  (True, datetime.now(), user['id']))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'displayName': user['display_name'],
                'bio': user['bio'] or '',
                'isOnline': True,
                'lastSeen': datetime.now().isoformat(),
                'createdAt': user['created_at']
            }
        })
    else:
        conn.close()
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    data = request.json
    user_id = data.get('userId')
    
    if user_id:
        conn = get_db()
        c = conn.cursor()
        c.execute('UPDATE users SET is_online = ?, last_seen = ? WHERE id = ?',
                  (False, datetime.now(), user_id))
        conn.commit()
        conn.close()
    
    return jsonify({'success': True})

@app.route('/api/users', methods=['GET'])
def get_users():
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id, username, display_name, bio, is_online, last_seen, created_at FROM users')
    users = c.fetchall()
    conn.close()
    
    return jsonify([{
        'id': u['id'],
        'username': u['username'],
        'displayName': u['display_name'],
        'bio': u['bio'] or '',
        'isOnline': bool(u['is_online']),
        'lastSeen': u['last_seen'],
        'createdAt': u['created_at']
    } for u in users])

@app.route('/api/user/<user_id>', methods=['GET', 'PUT'])
def user_profile(user_id):
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'GET':
        c.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = c.fetchone()
        conn.close()
        
        if user:
            return jsonify({
                'id': user['id'],
                'username': user['username'],
                'displayName': user['display_name'],
                'bio': user['bio'] or '',
                'isOnline': bool(user['is_online']),
                'lastSeen': user['last_seen'],
                'createdAt': user['created_at']
            })
        return jsonify({'error': 'User not found'}), 404
    
    elif request.method == 'PUT':
        updates = request.json
        allowed = ['display_name', 'bio']
        sets = []
        values = []
        
        for key in allowed:
            if key in updates:
                sets.append(f"{key} = ?")
                values.append(updates[key])
        
        if sets:
            values.append(user_id)
            c.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", values)
            conn.commit()
        
        conn.close()
        return jsonify({'success': True})

# =============================================================================
# Chat Routes
# =============================================================================

@app.route('/api/chats', methods=['GET', 'POST'])
def chats():
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'GET':
        user_id = request.args.get('userId')
        c.execute('SELECT * FROM chats WHERE participants LIKE ?', (f'%{user_id}%',))
        chats = c.fetchall()
        
        result = []
        for chat in chats:
            # Get last message
            c.execute('SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at DESC LIMIT 1', (chat['id'],))
            last_msg = c.fetchone()
            
            # FIX: Handle empty/invalid content safely
            last_message_data = None
            if last_msg:
                try:
                    content = last_msg['content']
                    # Content is plain text, not JSON - use directly
                    last_message_data = {
                        'id': last_msg['id'],
                        'content': content,
                        'senderId': last_msg['sender_id'],
                        'type': last_msg['type'],
                        'createdAt': last_msg['created_at']
                    }
                except Exception as e:
                    print(f"Error processing last message: {e}")
                    last_message_data = None
            
            result.append({
                'id': chat['id'],
                'type': chat['type'],
                'name': chat['name'],
                'participants': json.loads(chat['participants']),
                'adminIds': json.loads(chat['admin_ids']) if chat['admin_ids'] else [],
                'unreadCount': chat['unread_count'],
                'isMuted': bool(chat['is_muted']),
                'muteUntil': chat['mute_until'],
                'lastMessage': last_message_data,
                'createdAt': chat['created_at'],
                'updatedAt': chat['updated_at']
            })
        
        conn.close()
        return jsonify(result)
    
    elif request.method == 'POST':
        data = request.json
        chat_id = str(uuid.uuid4())
        
        c.execute('''
            INSERT INTO chats (id, type, name, participants, admin_ids, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            chat_id,
            data['type'],
            data.get('name'),
            json.dumps(data['participants']),
            json.dumps(data.get('adminIds', [])),
            datetime.now()
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'id': chat_id, 'success': True}), 201

@app.route('/api/chats/<chat_id>/messages', methods=['GET', 'POST'])
def messages(chat_id):
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'GET':
        c.execute('SELECT * FROM messages WHERE chat_id = ? ORDER BY created_at ASC', (chat_id,))
        messages = c.fetchall()
        conn.close()
        
        return jsonify([{
            'id': m['id'],
            'chatId': m['chat_id'],
            'senderId': m['sender_id'],
            'type': m['type'],
            'content': m['content'],
            'fileData': json.loads(m['file_data']) if m['file_data'] else None,
            'reactions': json.loads(m['reactions']),
            'status': m['status'],
            'isEdited': bool(m['is_edited']),
            'isDeleted': bool(m['is_deleted']),
            'createdAt': m['created_at']
        } for m in messages])
    
    elif request.method == 'POST':
        data = request.json
        msg_id = str(uuid.uuid4())
        
        c.execute('''
            INSERT INTO messages (id, chat_id, sender_id, type, content, file_data, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            msg_id,
            chat_id,
            data['senderId'],
            data.get('type', 'text'),
            data['content'],
            json.dumps(data.get('fileData')) if data.get('fileData') else None,
            'sent'
        ))
        
        # Update chat updated_at
        c.execute('UPDATE chats SET updated_at = ? WHERE id = ?', (datetime.now(), chat_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'id': msg_id, 'success': True}), 201

@app.route('/api/messages/<message_id>', methods=['PUT', 'DELETE'])
def message_action(message_id):
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'PUT':
        data = request.json
        if 'content' in data:
            c.execute('UPDATE messages SET content = ?, is_edited = 1 WHERE id = ?',
                      (data['content'], message_id))
        if 'status' in data:
            c.execute('UPDATE messages SET status = ? WHERE id = ?',
                      (data['status'], message_id))
        if 'reactions' in data:
            c.execute('UPDATE messages SET reactions = ? WHERE id = ?',
                      (json.dumps(data['reactions']), message_id))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        data = request.json or {}
        if data.get('forEveryone'):
            c.execute('UPDATE messages SET is_deleted = 1, content = ? WHERE id = ?',
                      ('This message was deleted', message_id))
        else:
            c.execute('DELETE FROM messages WHERE id = ?', (message_id,))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True})

# =============================================================================
# Status Routes
# =============================================================================

@app.route('/api/statuses', methods=['GET', 'POST'])
def statuses():
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'GET':
        c.execute('SELECT * FROM statuses WHERE expires_at > ? ORDER BY created_at DESC',
                  (datetime.now(),))
        statuses = c.fetchall()
        conn.close()
        
        return jsonify([{
            'id': s['id'],
            'userId': s['user_id'],
            'text': s['text'],
            'createdAt': s['created_at'],
            'expiresAt': s['expires_at']
        } for s in statuses])
    
    elif request.method == 'POST':
        data = request.json
        status_id = str(uuid.uuid4())
        
        c.execute('''
            INSERT INTO statuses (id, user_id, text, expires_at)
            VALUES (?, ?, ?, ?)
        ''', (
            status_id,
            data['userId'],
            data['text'],
            datetime.now() + timedelta(hours=24)
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'id': status_id, 'success': True}), 201

@app.route('/api/statuses/<status_id>', methods=['DELETE'])
def delete_status(status_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM statuses WHERE id = ?', (status_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# =============================================================================
# Game Routes
# =============================================================================

@app.route('/api/games', methods=['GET', 'POST'])
def games():
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'GET':
        chat_id = request.args.get('chatId')
        c.execute('SELECT * FROM games WHERE chat_id = ?', (chat_id,))
        game = c.fetchone()
        conn.close()
        
        if game:
            return jsonify({
                'id': game['id'],
                'chatId': game['chat_id'],
                'gameType': game['game_type'],
                'gameState': json.loads(game['game_state']),
                'currentPlayer': game['current_player'],
                'players': json.loads(game['players']),
                'createdAt': game['created_at'],
                'updatedAt': game['updated_at']
            })
        return jsonify(None)
    
    elif request.method == 'POST':
        data = request.json
        game_id = str(uuid.uuid4())
        
        c.execute('''
            INSERT INTO games (id, chat_id, game_type, game_state, current_player, players)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            game_id,
            data['chatId'],
            data['gameType'],
            json.dumps(data['gameState']),
            data['currentPlayer'],
            json.dumps(data['players'])
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({'id': game_id, 'success': True}), 201

@app.route('/api/games/<game_id>', methods=['PUT', 'DELETE'])
def game_action(game_id):
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'PUT':
        data = request.json
        updates = []
        values = []
        
        if 'gameState' in data:
            updates.append('game_state = ?')
            values.append(json.dumps(data['gameState']))
        if 'currentPlayer' in data:
            updates.append('current_player = ?')
            values.append(data['currentPlayer'])
        
        if updates:
            updates.append('updated_at = ?')
            values.append(datetime.now())
            values.append(game_id)
            
            c.execute(f"UPDATE games SET {', '.join(updates)} WHERE id = ?", values)
            conn.commit()
        
        conn.close()
        return jsonify({'success': True})
    
    elif request.method == 'DELETE':
        c.execute('DELETE FROM games WHERE id = ?', (game_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})

# =============================================================================
# AI Conversation Routes
# =============================================================================

@app.route('/api/ai-conversations/<user_id>', methods=['GET', 'POST'])
def ai_conversations(user_id):
    conn = get_db()
    c = conn.cursor()
    
    if request.method == 'GET':
        c.execute('SELECT * FROM ai_conversations WHERE user_id = ?', (user_id,))
        conv = c.fetchone()
        conn.close()
        
        if conv:
            return jsonify({
                'id': conv['id'],
                'userId': conv['user_id'],
                'messages': json.loads(conv['messages']),
                'createdAt': conv['created_at'],
                'updatedAt': conv['updated_at']
            })
        
        # Create new if not exists
        conv_id = str(uuid.uuid4())
        c = get_db().cursor()
        c.execute('''
            INSERT INTO ai_conversations (id, user_id, messages)
            VALUES (?, ?, ?)
        ''', (conv_id, user_id, '[]'))
        get_db().commit()
        
        return jsonify({
            'id': conv_id,
            'userId': user_id,
            'messages': [],
            'createdAt': datetime.now().isoformat(),
            'updatedAt': datetime.now().isoformat()
        })
    
    elif request.method == 'POST':
        data = request.json
        messages = json.dumps(data['messages'])
        
        c.execute('''
            UPDATE ai_conversations 
            SET messages = ?, updated_at = ?
            WHERE user_id = ?
        ''', (messages, datetime.now(), user_id))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True})




@app.route('/api/admin/download-db', methods=['GET'])
def download_db():
    token = request.args.get('Authorization')
    if token != 'Cortex-DB-Secret':
        abort(403)
    
    db_path = os.path.join(os.getcwd(), DATABASE)
    
    if not os.path.exists(db_path):
        abort(404, "Database not found")
    
    return send_file(
        db_path,
        mimetype='application/x-sqlite3',
        as_attachment=True,
        download_name='chatflow.db'
    )

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=3000, host = '0.0.0.0')
