"""
Emergency CAD System - Call Model
For Maine Department of Public Safety
"""

from src.database import db
from datetime import datetime
import uuid

class CADCall(db.Model):
    __tablename__ = 'cad_calls'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Call Information
    time_received = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    how_received = db.Column(db.String(100))
    address_of_incident = db.Column(db.Text)
    nature = db.Column(db.String(200))
    original_notes = db.Column(db.Text)
    additional_comments = db.Column(db.Text)
    
    # Caller Information
    caller_phone = db.Column(db.String(20))
    caller_name = db.Column(db.String(100))
    caller_dob = db.Column(db.String(20))
    caller_address = db.Column(db.Text)
    
    # Dispatch Status
    status = db.Column(db.String(20), default='pending')  # pending, dispatched, completed
    dispatcher_initials = db.Column(db.String(10))
    
    # Units
    primary_unit = db.Column(db.String(50))
    primary_dispatched_time = db.Column(db.DateTime)
    
    # Additional Units (stored as JSON)
    additional_units = db.Column(db.JSON, default=list)
    
    # Radio Logs (stored as JSON)
    radio_logs = db.Column(db.JSON, default=list)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'time_received': self.time_received.isoformat() if self.time_received else None,
            'how_received': self.how_received,
            'address_of_incident': self.address_of_incident,
            'nature': self.nature,
            'original_notes': self.original_notes,
            'additional_comments': self.additional_comments,
            'caller_phone': self.caller_phone,
            'caller_name': self.caller_name,
            'caller_dob': self.caller_dob,
            'caller_address': self.caller_address,
            'status': self.status,
            'dispatcher_initials': self.dispatcher_initials,
            'primary_unit': self.primary_unit,
            'primary_dispatched_time': self.primary_dispatched_time.isoformat() if self.primary_dispatched_time else None,
            'additional_units': self.additional_units or [],
            'radio_logs': self.radio_logs or [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def create_call(cls, data):
        call = cls(
            time_received=datetime.fromisoformat(data.get('time_received', datetime.utcnow().isoformat())),
            how_received=data.get('how_received'),
            address_of_incident=data.get('address_of_incident'),
            nature=data.get('nature'),
            original_notes=data.get('original_notes'),
            additional_comments=data.get('additional_comments'),
            caller_phone=data.get('caller_phone'),
            caller_name=data.get('caller_name'),
            caller_dob=data.get('caller_dob'),
            caller_address=data.get('caller_address'),
            dispatcher_initials=data.get('dispatcher_initials'),
            primary_unit=data.get('primary_unit')
        )
        
        db.session.add(call)
        db.session.commit()
        return call
    
    def update_call(self, data):
        for key, value in data.items():
            if hasattr(self, key):
                if key == 'time_received' and isinstance(value, str):
                    setattr(self, key, datetime.fromisoformat(value))
                elif key == 'primary_dispatched_time' and isinstance(value, str):
                    setattr(self, key, datetime.fromisoformat(value))
                else:
                    setattr(self, key, value)
        
        self.updated_at = datetime.utcnow()
        db.session.commit()
        return self
    
    def add_radio_log(self, time, unit, notes):
        if not self.radio_logs:
            self.radio_logs = []
        
        self.radio_logs.append({
            'time': time,
            'unit': unit,
            'notes': notes,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        db.session.commit()
        return self
    
    def add_additional_unit(self, unit, dispatched_time=None):
        if not self.additional_units:
            self.additional_units = []
        
        self.additional_units.append({
            'unit': unit,
            'dispatched_time': dispatched_time or datetime.utcnow().isoformat()
        })
        
        db.session.commit()
        return self
    
    def dispatch_call(self, dispatcher_initials):
        self.status = 'dispatched'
        self.dispatcher_initials = dispatcher_initials
        if self.primary_unit and not self.primary_dispatched_time:
            self.primary_dispatched_time = datetime.utcnow()
        
        db.session.commit()
        return self

