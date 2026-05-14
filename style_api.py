import sys
from pathlib import Path

from flask import Flask, request, jsonify

SRC_DIR = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC_DIR))

from buffer import StyleBuffer, choose_style_mode
from main import generate_styled_reply
from profile_store import load_profile

app = Flask(__name__)

buffer = StyleBuffer()


@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "status": "running",
        "endpoints": {
            "observe": "POST /observe",
            "reply": "POST /reply",
        },
    })


# -------------------------------------------------
# Observe outgoing messages (learning phase)
# -------------------------------------------------
@app.route("/observe", methods=["POST"])
def observe():

    data = request.get_json(silent=True) or {}

    message = data.get("message")
    contact = data.get("contact")

    if not message or not contact:
        return jsonify({"error": "message/contact missing"}), 400

    buffer.observe(contact, message)

    return jsonify({
        "status": "observed",
        "contact": contact
    })


# -------------------------------------------------
# Generate styled reply
# -------------------------------------------------
@app.route("/reply", methods=["POST"])
def reply():

    data = request.get_json(silent=True) or {}

    incoming_message = data.get("message")
    contact = data.get("contact")

    if not incoming_message or not contact:
        return jsonify({"error": "message/contact missing"}), 400

    global_profile = load_profile("global")
    contact_profile = load_profile(contact)
    mode = choose_style_mode(global_profile, contact_profile)

    generated_reply = generate_styled_reply(
        incoming_message,
        contact,
        mode,
        global_profile,
        contact_profile,
    )

    return jsonify({
        "mode": mode,
        "reply": generated_reply
    })


if __name__ == "__main__":
    app.run(port=5001, debug=True)
