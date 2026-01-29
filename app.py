from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from gradio_client import Client
import json
import threading
import time
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'stream-moderator-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize HuggingFace client
hf_client = Client("duchaba/Friendly_Text_Moderation")

# Global state
replay_state = {
    'is_playing': False,
    'speed': 1.0,
    'current_index': 0,
    'chat_data': [],
    'stats': {
        'total_messages': 0,
        'flagged_messages': 0,
        'blocked_messages': 0,
        'users_warned': set(),
        'toxicity_timeline': []
    }
}
replay_thread = None

def load_chat_data():
    """Load historical chat data from JSON file"""
    data_path = os.path.join(os.path.dirname(__file__), 'data', 'chat_history.json')
    with open(data_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def analyze_toxicity(text, safer=0.02):
    """Analyze text toxicity using HuggingFace API"""
    try:
        result = hf_client.predict(
            msg=text,
            safer=safer,
            api_name="/fetch_toxicity_level"
        )
        # Parse the JSON result
        analysis = json.loads(result[1]) if isinstance(result[1], str) else result[1]
        max_val = analysis.get('max_value', 0)
        print(f"[API] '{text[:30]}...' -> max_value: {max_val:.3f}", flush=True)
        return analysis
    except Exception as e:
        print(f"[API ERROR] '{text[:30]}...': {e}", flush=True)
        return {"max_value": 0, "error": str(e)}

def get_toxicity_level(analysis):
    """Determine toxicity level from analysis"""
    if isinstance(analysis, dict):
        # API returns max_value as the highest toxicity score across categories
        toxicity = analysis.get('max_value', analysis.get('toxicity', 0))
        if toxicity > 0.7:
            return 'high', toxicity
        elif toxicity > 0.4:
            return 'medium', toxicity
        else:
            return 'low', toxicity
    return 'low', 0

def process_message(username, message, timestamp=None, is_historical=True):
    """Process a single message through moderation"""
    if timestamp is None:
        timestamp = datetime.now().strftime("%H:%M:%S")

    # Analyze toxicity
    analysis = analyze_toxicity(message)
    level, score = get_toxicity_level(analysis)

    # Update stats
    replay_state['stats']['total_messages'] += 1

    action = 'allowed'
    if level == 'high':
        replay_state['stats']['blocked_messages'] += 1
        replay_state['stats']['users_warned'].add(username)
        action = 'blocked'
    elif level == 'medium':
        replay_state['stats']['flagged_messages'] += 1
        action = 'flagged'

    # Add to timeline
    replay_state['stats']['toxicity_timeline'].append({
        'time': timestamp,
        'score': score
    })
    # Keep only last 50 for performance
    if len(replay_state['stats']['toxicity_timeline']) > 50:
        replay_state['stats']['toxicity_timeline'].pop(0)

    return {
        'username': username,
        'message': message,
        'timestamp': timestamp,
        'toxicity_level': level,
        'toxicity_score': round(score, 3),
        'action': action,
        'is_historical': is_historical,
        'analysis': analysis
    }

def replay_worker():
    """Background worker that replays historical chat"""
    global replay_state

    while replay_state['is_playing'] and replay_state['current_index'] < len(replay_state['chat_data']):
        if not replay_state['is_playing']:
            break

        msg_data = replay_state['chat_data'][replay_state['current_index']]

        # Process the message
        result = process_message(
            msg_data['username'],
            msg_data['message'],
            msg_data.get('timestamp', f"00:{replay_state['current_index']:02d}:00"),
            is_historical=True
        )

        # Emit to all clients
        socketio.emit('new_message', result)
        socketio.emit('stats_update', {
            'total': replay_state['stats']['total_messages'],
            'flagged': replay_state['stats']['flagged_messages'],
            'blocked': replay_state['stats']['blocked_messages'],
            'warned_users': len(replay_state['stats']['users_warned']),
            'timeline': replay_state['stats']['toxicity_timeline']
        })

        replay_state['current_index'] += 1

        # Wait based on speed (base delay 1.5 seconds)
        delay = 1.5 / replay_state['speed']
        time.sleep(delay)

    if replay_state['current_index'] >= len(replay_state['chat_data']):
        replay_state['is_playing'] = False
        socketio.emit('replay_ended', {})

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('stats_update', {
        'total': replay_state['stats']['total_messages'],
        'flagged': replay_state['stats']['flagged_messages'],
        'blocked': replay_state['stats']['blocked_messages'],
        'warned_users': len(replay_state['stats']['users_warned']),
        'timeline': replay_state['stats']['toxicity_timeline']
    })

@socketio.on('start_replay')
def handle_start_replay():
    global replay_thread, replay_state

    if not replay_state['is_playing']:
        # Load chat data if not loaded
        if not replay_state['chat_data']:
            replay_state['chat_data'] = load_chat_data()

        replay_state['is_playing'] = True
        replay_thread = threading.Thread(target=replay_worker)
        replay_thread.daemon = True
        replay_thread.start()
        emit('replay_started', {'total_messages': len(replay_state['chat_data'])})

@socketio.on('pause_replay')
def handle_pause_replay():
    global replay_state
    replay_state['is_playing'] = False
    emit('replay_paused', {})

@socketio.on('reset_replay')
def handle_reset_replay():
    global replay_state
    replay_state['is_playing'] = False
    replay_state['current_index'] = 0
    replay_state['stats'] = {
        'total_messages': 0,
        'flagged_messages': 0,
        'blocked_messages': 0,
        'users_warned': set(),
        'toxicity_timeline': []
    }
    emit('replay_reset', {})
    emit('stats_update', {
        'total': 0,
        'flagged': 0,
        'blocked': 0,
        'warned_users': 0,
        'timeline': []
    })

@socketio.on('set_speed')
def handle_set_speed(data):
    global replay_state
    replay_state['speed'] = float(data.get('speed', 1.0))
    emit('speed_changed', {'speed': replay_state['speed']})

@socketio.on('user_message')
def handle_user_message(data):
    """Handle message typed by the user"""
    username = data.get('username', 'You')
    message = data.get('message', '')

    if message.strip():
        result = process_message(username, message, is_historical=False)
        emit('new_message', result, broadcast=True)
        emit('stats_update', {
            'total': replay_state['stats']['total_messages'],
            'flagged': replay_state['stats']['flagged_messages'],
            'blocked': replay_state['stats']['blocked_messages'],
            'warned_users': len(replay_state['stats']['users_warned']),
            'timeline': replay_state['stats']['toxicity_timeline']
        }, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
