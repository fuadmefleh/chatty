import json
import subprocess
from datetime import datetime

from fastapi import APIRouter, Depends

from src.web import config, state
from src.web.auth import require_api_key

router = APIRouter(prefix="/api/chatty/system", tags=["system"], dependencies=[Depends(require_api_key)])


@router.get("")
async def get_system():
    # Skills
    skill_list = []
    if state.skills_manager:
        for name, skill in state.skills_manager.skills.items():
            skill_list.append({
                "name": name,
                "description": skill.description,
                "tool_count": len(skill.tools),
                "tools": [t.name for t in skill.tools],
            })

    # pm2 status
    pm2_processes = []
    try:
        result = subprocess.run(
            ["pm2", "jlist"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            procs = json.loads(result.stdout)
            for p in procs:
                pm2_processes.append({
                    "name": p.get("name"),
                    "status": p.get("pm2_env", {}).get("status"),
                    "pid": p.get("pid"),
                    "uptime": p.get("pm2_env", {}).get("pm_uptime"),
                    "restarts": p.get("pm2_env", {}).get("restart_time", 0),
                })
    except Exception as e:
        pm2_processes = [{"error": str(e)}]

    return {
        "skills": skill_list,
        "pm2": pm2_processes,
        "web_user_id": config.WEB_USER_ID,
        "timestamp": datetime.utcnow().isoformat(),
    }
