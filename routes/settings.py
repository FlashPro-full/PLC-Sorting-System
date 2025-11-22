from flask import Blueprint, request, jsonify, render_template
import json
import os

settings_bp = Blueprint('settings', __name__)

DISTANCE_LABELS = [
    "FBA", "MF", "SBYB", "Reject Book", "Reject Music",
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

@settings_bp.route('/update-settings', methods=['POST'])
def update_settings():
    from plc import write_settings
    
    data = request.json or {}
    new_settings = data.get("settings")
    
    if not isinstance(new_settings, dict):
        return jsonify({"error": "Invalid input format"}), 400
    
    try:
        with open("settings.json", "w") as f:
            json.dump(new_settings, f, indent=2)
        write_settings(new_settings)
        return jsonify({"message": "Settings updated successfully!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

