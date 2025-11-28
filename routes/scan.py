from flask import Blueprint, request, jsonify, render_template

scan_bp = Blueprint('scan', __name__)

@scan_bp.route('/')
def index():
    return render_template('index.html')

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

