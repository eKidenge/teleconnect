# quickconnect/admin_fix.py
# This file adds the emergency fix without modifying your existing admin.py
# Just import this in your admin.py

import sys
from django.db import connection

def apply_emergency_fix():
    """Apply emergency fix for session deletion without modifying admin.py"""
    print("🔧 Applying emergency fix for session deletion...", file=sys.stderr)
    
    try:
        with connection.cursor() as cursor:
            # Check if session_id column exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='webrtc_webrtccall' 
                AND column_name='session_id';
            """)
            
            if cursor.fetchone():
                print("✅ session_id column already exists", file=sys.stderr)
                return True
            else:
                print("⚠ session_id column missing - applying emergency SQL fix...", file=sys.stderr)
                
                # Emergency SQL fix
                sql = """
                -- Add session_id column
                ALTER TABLE webrtc_webrtccall 
                ADD COLUMN session_id BIGINT;
                
                -- Add foreign key
                DO $$ 
                BEGIN
                    BEGIN
                        ALTER TABLE webrtc_webrtccall 
                        ADD CONSTRAINT webrtc_webrtccall_session_id_fk 
                        FOREIGN KEY (session_id) 
                        REFERENCES quickconnect_session(id) 
                        ON DELETE CASCADE;
                    EXCEPTION WHEN duplicate_object THEN
                        RAISE NOTICE 'Foreign key already exists';
                    END;
                END $$;
                
                -- Add index
                CREATE INDEX IF NOT EXISTS webrtc_webrtccall_session_id_idx 
                ON webrtc_webrtccall(session_id);
                """
                
                cursor.execute(sql)
                print("✅ Emergency database fix applied!", file=sys.stderr)
                return True
                
    except Exception as e:
        print(f"⚠ Emergency fix error: {e}", file=sys.stderr)
        return False

# Apply the fix when this module is imported
apply_emergency_fix()