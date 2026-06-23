#!/usr/bin/env python3
"""
✅ Approval Handler — Process Abdo's approve/reject commands
Called by 3my when Abdo replies with approve/reject commands
"""

import sqlite3
import sys
import json
from pathlib import Path

AGENCY_DIR = Path(__file__).parent.parent
DB_PATH = AGENCY_DIR / "agency-leads.db"

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def approve_task(task_id):
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return f"Task #{task_id} not found"
    
    conn.execute("UPDATE tasks SET status='approved', completed_at=CURRENT_TIMESTAMP WHERE id=?", (task_id,))
    
    # If it's an outreach approval, mark the outreach as approved
    if task['task_type'] == 'review_outreach':
        # Find the corresponding outreach_log entry and update status
        desc = task['description']
        # Extract company name from description like "Review and approve outreach to Cal.com (score: 95)"
        import re
        match = re.search(r'outreach to (.+?) \(score:', desc)
        if match:
            company = match.group(1)
            conn.execute("""
                UPDATE outreach_log SET status='approved' 
                WHERE lead_id IN (SELECT id FROM leads WHERE company_name=?) AND status='ready'
            """, (company,))
    
    conn.commit()
    conn.close()
    return f"✅ Task #{task_id} APPROVED: {task['description']}"

def reject_task(task_id):
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return f"Task #{task_id} not found"
    
    conn.execute("UPDATE tasks SET status='rejected', completed_at=CURRENT_TIMESTAMP WHERE id=?", (task_id,))
    
    # If outreach rejection, mark accordingly
    if task['task_type'] == 'review_outreach':
        import re
        match = re.search(r'outreach to (.+?) \(score:', task['description'])
        if match:
            company = match.group(1)
            conn.execute("""
                UPDATE outreach_log SET status='rejected' 
                WHERE lead_id IN (SELECT id FROM leads WHERE company_name=?) AND status='ready'
            """, (company,))
    
    conn.commit()
    conn.close()
    return f"❌ Task #{task_id} REJECTED: {task['description']}"

def list_pending():
    conn = get_db()
    tasks = conn.execute("""
        SELECT * FROM tasks WHERE agent='approver' AND status='pending'
        ORDER BY created_at DESC
    """).fetchall()
    conn.close()
    
    if not tasks:
        return "No pending approvals"
    
    result = "⏳ PENDING APPROVALS:\n"
    for t in tasks:
        result += f"  #{t['id']}: {t['description']}\n"
    result += "\nReply: approve [#] / reject [#]"
    return result

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 approval_handler.py [list|approve <id>|reject <id>]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    if cmd == "list":
        print(list_pending())
    elif cmd == "approve" and len(sys.argv) > 2:
        print(approve_task(int(sys.argv[2])))
    elif cmd == "reject" and len(sys.argv) > 2:
        print(reject_task(int(sys.argv[2])))
    else:
        print("Usage: python3 approval_handler.py [list|approve <id>|reject <id>]")
