from flask import Blueprint, request, jsonify, render_template
import time
import os

scan_bp = Blueprint('scan', __name__)

@scan_bp.route('/')
def index():
    return render_template('index.html')

@scan_bp.route('/scan', methods=['GET', 'POST'])
def scan():
    from palletiq_api import request_palletiq_sync
    
    data = request.json or {}
    barcode = data.get("scan")
    
    if not barcode:
        return jsonify({"error": "scan is required"}), 400
    
    try:
        response = request_palletiq_sync(barcode)
        if not response:
            return jsonify({"error": "Failed to get routing information"}), 500
        
        return jsonify({
            "routing": {
                "pusher": response.get("pusher_number", 8),
                "label": response.get("label", "Unknown"),
                "distance": response.get("distance", 0)
            }
        })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Error in /scan endpoint for barcode {barcode}: {e}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

@scan_bp.route('/get-location', methods=['GET'])
def get_location():
    from plc import read_photo_eye, is_plc_connected
    
    plc_connected = is_plc_connected()
    photo_eye_value = read_photo_eye() if plc_connected else None
    
    return jsonify({
        "available": photo_eye_value == 0,
        "location": 101 if photo_eye_value == 0 else None,
        "plc_connected": plc_connected
    })

@scan_bp.route('/active-items', methods=['GET'])
def get_active_items():
    try:
        from app import book_dict, book_dict_lock
    except ImportError:
        return jsonify({"items": {}, "count": 0, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")})
    
    try:
        with book_dict_lock:
            return jsonify({
                "items": book_dict,
                "count": len(book_dict),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Error in /active-items endpoint: {e}", exc_info=True)
        return jsonify({"items": {}, "count": 0, "error": str(e), "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")})

@scan_bp.route('/mark-item-routed', methods=['POST'])
def mark_item_routed():
    try:
        from app import book_dict, book_dict_lock, broadcast_book_dict
    except ImportError:
        return jsonify({"success": False, "error": "App not available"}), 500
    
    data = request.json or {}
    barcode = data.get('barcode')
    
    if not barcode:
        return jsonify({"error": "Barcode required"}), 400
    
    try:
        with book_dict_lock:
            if barcode in book_dict:
                del book_dict[barcode]
                broadcast_book_dict()
                return jsonify({"success": True})
        
        return jsonify({"success": False, "error": "Item not found"}), 404
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Error in /mark-item-routed endpoint for barcode {barcode}: {e}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@scan_bp.route('/test-integration', methods=['GET'])
def test_integration():
    from barcode_scanner import is_barcode_scanner_connected
    from plc import is_plc_connected
    
    results = {
        "overall_status": "pass",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {"passed": 0, "failed": 0, "warnings": 0, "skipped": 0},
        "tests": []
    }
    
    plc_connected = is_plc_connected()
    scanner_connected = is_barcode_scanner_connected()
    
    results["tests"].append({
        "name": "PLC Connection",
        "status": "pass" if plc_connected else "fail",
        "message": "Connected" if plc_connected else "Disconnected"
    })
    if plc_connected:
        results["summary"]["passed"] += 1
    else:
        results["summary"]["failed"] += 1
        results["overall_status"] = "fail"
    
    results["tests"].append({
        "name": "Barcode Scanner Connection",
        "status": "pass" if scanner_connected else "fail",
        "message": "Connected" if scanner_connected else "Disconnected"
    })
    if scanner_connected:
        results["summary"]["passed"] += 1
    else:
        results["summary"]["failed"] += 1
        results["overall_status"] = "fail"
    
    return jsonify(results)

