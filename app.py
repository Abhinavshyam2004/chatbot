# app.py
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
import google.generativeai as genai
import os
import logging

logging.basicConfig(level=logging.INFO)

# === Read API key from environment variable ===
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise SystemExit(
        "ERROR: GOOGLE_API_KEY environment variable is not set.\n"
        "Set it temporarily in PowerShell: $env:GOOGLE_API_KEY=\"your_key_here\"\n"
        "Or permanently (PowerShell): setx GOOGLE_API_KEY \"your_key_here\""
    )

genai.configure(api_key=API_KEY)

# You can override the model by setting GENAI_MODEL env var.
MODEL_NAME = os.getenv("GENAI_MODEL", "models/gemini-flash-latest")

app = Flask(__name__, static_folder="static", template_folder="templates")
socketio = SocketIO(app, cors_allowed_origins="*")

try:
    model = genai.GenerativeModel(MODEL_NAME)
    logging.info("Loaded model: %s", MODEL_NAME)
except Exception as e:
    logging.exception("Failed to initialise model '%s': %s", MODEL_NAME, e)
    raise

# Store chat sessions with Gemini chat instances & history
chat_histories = {}

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route("/")
def index():
    # make sure you have templates/index.html in the project
    try:
        return render_template("index.html")
    except Exception:
        # Safe fallback if template missing
        return "<h3>Flask app is running. Open /chat to POST messages.</h3>"


@app.route("/chat", methods=["POST"])
def chat_response():
    data = request.get_json(force=True, silent=True) or {}
    session_id = data.get("session_id")
    user_input = data.get("message")

    if not session_id or not user_input:
        return jsonify({"error": "Missing 'session_id' or 'message' in JSON body"}), 400

    # create chat object for this session if not exists
    if session_id not in chat_histories:
        try:
            chat = model.start_chat(history=[])
            chat_histories[session_id] = {"chat": chat, "history": []}
        except Exception as e:
            logging.exception("start_chat failed for model %s: %s", MODEL_NAME, e)
            # still create an entry (None chat) so we avoid repeated start attempts
            chat_histories[session_id] = {"chat": None, "history": []}

    chat = chat_histories[session_id]["chat"]

    try:
        if chat is not None:
            response = chat.send_message(user_input)
        else:
            # If model.start_chat not supported, try generateContent directly.
            # This block uses the model's generate_content method if available.
            if hasattr(model, "generate_content"):
                # The SDK may accept a simple text input — use the method that worked in your environment.
                # The call shape can vary by SDK version; here we call with a simple dict.
                response = model.generate_content({"input": user_input})
            else:
                raise RuntimeError("Model does not support start_chat or generate_content in this SDK version.")

        # Extract text robustly
        bot_text = getattr(response, "text", None)
        if not bot_text:
            # fallback path: response.candidates -> content.parts[0].text
            try:
                candidates = getattr(response, "candidates", None)
                if candidates and len(candidates) > 0:
                    parts = getattr(candidates[0].content, "parts", None)
                    if parts and len(parts) > 0:
                        bot_text = getattr(parts[0], "text", "") or ""
            except Exception:
                bot_text = ""

        if bot_text is None:
            bot_text = ""

        # Save history (local only)
        chat_histories[session_id]["history"].append({"role": "user", "content": user_input})
        chat_histories[session_id]["history"].append({"role": "assistant", "content": bot_text})

        return jsonify({"response": bot_text})
    except Exception as e:
        logging.exception("Error while generating response: %s", e)
        return jsonify({"error": str(e)}), 500


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    try:
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        return jsonify({"response": f"📎 File '{file.filename}' uploaded successfully.", "path": filepath})
    except Exception as e:
        logging.exception("File upload failed: %s", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # If you have eventlet installed it will be used; otherwise the default works for development.
    socketio.run(app, debug=True, host="0.0.0.0", port=5000)
