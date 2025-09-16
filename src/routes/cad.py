"""
Emergency CAD System API Routes
For Maine Department of Public Safety
No authentication required - emergency use only
"""

from flask import Blueprint, request, jsonify
from src.models.cad_call import CADCall
from src.database import db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

cad_bp = Blueprint('cad', __name__)

@cad_bp.route('/calls', methods=['GET'])
def get_all_calls():
    """Get all CAD calls for dashboard view"""
    try:
        calls = CADCall.query.order_by(CADCall.created_at.desc()).all()
        return jsonify({
            'calls': [call.to_dict() for call in calls],
            'count': len(calls)
        })
    except Exception as e:
        logger.error(f"Error getting CAD calls: {e}")
        return jsonify({'error': 'Failed to retrieve calls'}), 500

@cad_bp.route('/calls', methods=['POST'])
def create_call():
    """Create a new CAD call"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('address_of_incident'):
            return jsonify({'error': 'Address of incident is required'}), 400
        
        call = CADCall.create_call(data)
        
        return jsonify({
            'message': 'Call created successfully',
            'call': call.to_dict()
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating CAD call: {e}")
        return jsonify({'error': 'Failed to create call'}), 500

@cad_bp.route('/calls/<call_id>', methods=['PUT'])
def update_call(call_id):
    """Update an existing CAD call"""
    try:
        call = CADCall.query.get(call_id)
        if not call:
            return jsonify({'error': 'Call not found'}), 404
        
        data = request.get_json()
        call.update_call(data)
        
        return jsonify({
            'message': 'Call updated successfully',
            'call': call.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error updating CAD call: {e}")
        return jsonify({'error': 'Failed to update call'}), 500

@cad_bp.route('/calls/<call_id>/dispatch', methods=['POST'])
def dispatch_call(call_id):
    """Mark a call as dispatched"""
    try:
        call = CADCall.query.get(call_id)
        if not call:
            return jsonify({'error': 'Call not found'}), 404
        
        data = request.get_json()
        dispatcher_initials = data.get('dispatcher_initials', '')
        
        call.dispatch_call(dispatcher_initials)
        
        return jsonify({
            'message': 'Call dispatched successfully',
            'call': call.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error dispatching CAD call: {e}")
        return jsonify({'error': 'Failed to dispatch call'}), 500

@cad_bp.route('/calls/<call_id>/radio-log', methods=['POST'])
def add_radio_log(call_id):
    """Add a radio log entry to a call"""
    try:
        call = CADCall.query.get(call_id)
        if not call:
            return jsonify({'error': 'Call not found'}), 404
        
        data = request.get_json()
        time = data.get('time', datetime.utcnow().strftime('%H:%M'))
        unit = data.get('unit', '')
        notes = data.get('notes', '')
        
        call.add_radio_log(time, unit, notes)
        
        return jsonify({
            'message': 'Radio log added successfully',
            'call': call.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error adding radio log: {e}")
        return jsonify({'error': 'Failed to add radio log'}), 500

@cad_bp.route('/calls/<call_id>/additional-unit', methods=['POST'])
def add_additional_unit(call_id):
    """Add an additional unit to a call"""
    try:
        call = CADCall.query.get(call_id)
        if not call:
            return jsonify({'error': 'Call not found'}), 404
        
        data = request.get_json()
        unit = data.get('unit', '')
        dispatched_time = data.get('dispatched_time')
        
        call.add_additional_unit(unit, dispatched_time)
        
        return jsonify({
            'message': 'Additional unit added successfully',
            'call': call.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error adding additional unit: {e}")
        return jsonify({'error': 'Failed to add additional unit'}), 500

@cad_bp.route('/calls/<call_id>', methods=['DELETE'])
def delete_call(call_id):
    """Delete a CAD call (emergency use only)"""
    try:
        call = CADCall.query.get(call_id)
        if not call:
            return jsonify({'error': 'Call not found'}), 404
        
        db.session.delete(call)
        db.session.commit()
        
        return jsonify({'message': 'Call deleted successfully'})
        
    except Exception as e:
        logger.error(f"Error deleting CAD call: {e}")
        return jsonify({'error': 'Failed to delete call'}), 500

@cad_bp.route('/status', methods=['GET'])
def get_system_status():
    """Get CAD system status"""
    try:
        total_calls = CADCall.query.count()
        pending_calls = CADCall.query.filter_by(status='pending').count()
        dispatched_calls = CADCall.query.filter_by(status='dispatched').count()
        
        return jsonify({
            'status': 'operational',
            'total_calls': total_calls,
            'pending_calls': pending_calls,
            'dispatched_calls': dispatched_calls,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({'error': 'Failed to get system status'}), 500

