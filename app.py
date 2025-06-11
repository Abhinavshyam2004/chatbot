from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import google.generativeai as genai
import os
import mimetypes

# --- CONFIGURATION ---
genai.configure(api_key="AIzaSyAXNUMB2Tm5I8zpXTcJgd9LQnrjap5j_uU")  # Move this to env var

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

model = genai.GenerativeModel('gemini-1.5-flash')

# --- SESSION DATA ---
chat_histories = {}

# --- FILE UPLOAD SETUP ---
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/chat', methods=['POST'])
def chat_response():
    data = request.json
    session_id = data.get('session_id')
    user_input = data.get('message')

    if not session_id or not user_input:
        return jsonify({"error": "Missing session_id or message"}), 400

    if session_id not in chat_histories:
        chat_histories[session_id] = {
            "chat": model.start_chat(history=[]),
            "history": []
        }

    chat = chat_histories[session_id]["chat"]

    try:
        response = chat.send_message(user_input)
        bot_text = response.text

        chat_histories[session_id]["history"].append({"role": "user", "content": user_input})
        chat_histories[session_id]["history"].append({"role": "assistant", "content": bot_text})

        return jsonify({"response": bot_text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    try:
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        return jsonify({
            "response": f"📎 File '{file.filename}' uploaded successfully.",
            "filename": file.filename
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/read-file', methods=['POST'])
def read_file():
    data = request.get_json()
    filename = data.get('filename')

    if not filename:
        return jsonify({"error": "No filename provided"}), 400

    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "File does not exist"}), 404

    try:
        mime_type, _ = mimetypes.guess_type(filepath)
        ext = os.path.splitext(filename)[1].lower()

        if mime_type and mime_type.startswith("text"):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
        elif ext in ['.pdf']:
            import fitz  # PyMuPDF
            doc = fitz.open(filepath)
            content = "\n".join([page.get_text() for page in doc])
        elif ext in ['.doc', '.docx']:
            import docx
            doc = docx.Document(filepath)
            content = "\n".join([p.text for p in doc.paragraphs])
        elif ext in ['.csv', '.xlsx']:
            import pandas as pd
            if ext == '.csv':
                df = pd.read_csv(filepath)
            else:
                df = pd.read_excel(filepath)
            content = df.to_string(index=False)
        else:
            return jsonify({"response": f"📁 '{filename}' uploaded but content type not supported for reading."})

        prompt = f"Summarize the content of this file:\n{content[:3000]}"
        summary = model.generate_content(prompt).text
        return jsonify({"response": summary})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# --- RUN APP ---
if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
