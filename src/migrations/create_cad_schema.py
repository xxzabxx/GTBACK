#!/usr/bin/env python3
"""
Emergency CAD System Database Migration
Creates tables for Maine Department of Public Safety CAD system
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.database import db
from src.models.cad_call import CADCall
from src.main import create_app

def create_cad_tables():
    """Create CAD system tables"""
    print("Creating CAD system database tables...")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Create CAD tables
            db.create_all()
            
            print("✅ CAD tables created successfully:")
            print("   - cad_calls")
            
            # Verify table creation
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'cad_calls' in tables:
                print("✅ CAD system database ready for emergency use")
                return True
            else:
                print("❌ CAD table creation failed")
                return False
                
        except Exception as e:
            print(f"❌ Error creating CAD tables: {e}")
            return False

if __name__ == "__main__":
    success = create_cad_tables()
    if success:
        print("\n🚨 EMERGENCY CAD SYSTEM READY 🚨")
        print("Maine Department of Public Safety CAD system is operational")
    else:
        print("\n❌ CAD system setup failed")
        sys.exit(1)

