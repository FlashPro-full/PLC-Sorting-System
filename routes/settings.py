from flask import Blueprint, request, jsonify, render_template #type: ignore
import json

settings_bp = Blueprint('settings', __name__)

DISTANCE_LABELS = [
    "FBA", "MF", "Reject Blu-ray", "Reject Book", "Reject Music",
    "Reject DVD", "Reject Video Game", "Extra", "None"
]

DEFAULT_PUSHERS = ["Pusher 1", "Pusher 2", "Pusher 3", "Pusher 4", "Pusher 5", "Pusher 6", "Pusher 7", "Pusher 8"]

@settings_bp.route('/settings')
def settings_page():
    return render_template('settings.html', labels=DISTANCE_LABELS, pushers=DEFAULT_PUSHERS)

@settings_bp.route('/get-settings', methods=['GET'])
def get_settings():
    try:
        with open("settings.json", "r") as f:
            return jsonify(json.load(f))
    except FileNotFoundError:
        return jsonify({})
    except json.JSONDecodeError:
        return jsonify({})

@settings_bp.route('/update-pushers', methods=['POST'])
def update_pushers():
    data = request.json or {}
    pushers = data.get("pushers", {})
    settings = {}
    
    if not isinstance(pushers, dict):
        return jsonify({"error": "Invalid input format"}), 400
    
    try:
        with open("settings.json", "r") as f:
            settings = json.load(f)
        with open("settings.json", "w") as f:
            json.dump({**settings, "pushers": pushers}, f, indent=2)
        
        from plc import write_pushers
        write_pushers([pusher.get("distance") for pusher in pushers.values()])
        return jsonify({"message": "Pushers updated successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/trigger-pusher', methods=['POST'])
def trigger_pusher():
    data = request.json or {}
    try:
        pusher = int(data.get("pusher", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid pusher number"}), 400
    if pusher < 1 or pusher > 8:
        return jsonify({"error": "Pusher must be 1-8"}), 400
    try:
        from plc import write_trigger_pusher
        result = write_trigger_pusher(pusher)
        if result == 1:
            return jsonify({"message": f"Pusher {pusher} triggered"})
        return jsonify({"error": "Trigger failed"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@settings_bp.route('/update-belt-speed', methods=['POST'])
def update_belt_speed():
    data = request.json or {}
    try:
        speed = float(data.get("speed", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid speed value"}), 400
    if speed <= 0:
        return jsonify({"error": "Speed must be positive"}), 400
    try:
        with open("settings.json", "r") as f:
            settings = json.load(f)
        with open("settings.json", "w") as f:
            json.dump({**settings, "belt_speed": speed}, f, indent=2)

        from plc import write_belt_speed
        write_belt_speed(speed)
        return jsonify({"message": "Belt speed updated successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

