import os
import json

AUDIT_DIR = os.path.join(os.path.dirname(__file__), "audit")

def log_audit(job_id: str, agent_name: str, step_type: str, data: dict):
    """
    Logs input or output payload for a specific agent during a job run.
    step_type: 'input' or 'output'
    """
    if not job_id:
        return
        
    job_dir = os.path.join(AUDIT_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    file_path = os.path.join(job_dir, f"{agent_name}_{step_type}.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    except Exception as e:
        print(f"[AuditLogger] Failed to write audit log for {agent_name} {step_type}: {e}")
