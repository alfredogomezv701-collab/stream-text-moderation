# Real-time Stream Chat Moderator

An AI-powered stream chat moderation system that demonstrates real-time content moderation using the Hugging Face Friendly Text Moderation API.

Built as part of an AI Solution Architecture course assignment.

## Features

- **Historical Chat Replay**: Replay chat logs at adjustable speeds (0.5x to 5x)
- **Real-time Moderation**: Every message is analyzed for toxicity as it appears
- **Live Dashboard**: Visual statistics including:
  - Total messages processed
  - Flagged messages (medium toxicity)
  - Blocked messages (high toxicity)
  - Users warned
- **Toxicity Timeline**: Bar visualization showing toxicity scores over time
- **Flagged Message Log**: Detailed log of all problematic content
- **Interactive Testing**: Type your own messages to test the moderation system

## Visual Indicators

- **Blue**: Safe message (toxicity < 40%)
- **Yellow with ⚠️**: Flagged message (toxicity 40-70%)
- **Red with 🚫 + strikethrough**: Blocked message (toxicity > 70%)

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. Open your browser to `http://localhost:5000`

## Usage

1. Click **Play** to start the historical chat replay
2. Watch as messages stream in and get moderated in real-time
3. Use the **Speed** control to adjust replay speed
4. Type your own messages in the chat input to test moderation
5. View flagged/blocked messages in the dashboard
6. Click **Reset** to start over

## Architecture

```
stream_moderator/
├── app.py                  # Flask + SocketIO backend
├── templates/
│   └── index.html          # Single-page application UI
├── data/
│   └── chat_history.json   # Sample chat data for replay
├── requirements.txt
└── README.md
```

## How It Works

1. **WebSocket Connection**: Browser connects via Socket.IO for real-time updates
2. **Replay Worker**: Background thread reads chat history and emits messages
3. **Moderation Pipeline**: Each message is sent to HuggingFace API for toxicity analysis
4. **Classification**:
   - Score < 0.4: Allowed (shown normally)
   - Score 0.4-0.7: Flagged (shown with warning)
   - Score > 0.7: Blocked (shown with strikethrough)
5. **Dashboard Updates**: Stats and charts update in real-time via WebSocket

## Customization

### Add Your Own Chat Data

Replace `data/chat_history.json` with your own data in this format:
```json
[
  {"username": "User1", "message": "Hello world", "timestamp": "00:00:05"},
  {"username": "User2", "message": "Hi there!", "timestamp": "00:00:12"}
]
```

### Adjust Toxicity Thresholds

Modify the `get_toxicity_level()` function in `app.py` to change sensitivity.

## Credits

- **Toxicity Detection API**: [Friendly Text Moderation](https://huggingface.co/spaces/duchaba/Friendly_Text_Moderation) by duchaba on Hugging Face
- **Chat Data**: Synthetic dataset created for demonstration purposes

## License

MIT License - see [LICENSE](LICENSE) file for details.
