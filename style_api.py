import sys
from pathlib import Path

from flask import Flask, request, jsonify

SRC_DIR = Path(__file__).resolve().parent / "src"
BACKEND_DIR = Path(__file__).resolve().parent / "Backend"
sys.path.insert(0, str(SRC_DIR))
sys.path.insert(0, str(BACKEND_DIR))

from app.buffer import StyleBuffer
from app.style_engine import generate_style_adapted_response

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
    contact = data.get("contact") or data.get("contact_id")

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
    contact = data.get("contact") or data.get("contact_id")
    risk_level = data.get("risk_level")
    action_type = data.get("action_type")

    if not incoming_message or not contact:
        return jsonify({"error": "message/contact missing"}), 400

    result = generate_style_adapted_response(
        incoming_message=incoming_message,
        contact_id=contact,
        risk_level=risk_level,
        action_type=action_type,
    )

    return jsonify(result)


if __name__ == "__main__":
    app.run(port=5001, debug=True)
