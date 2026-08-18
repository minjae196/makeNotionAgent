import subprocess
import os
from pathlib import Path

def run_git_command(args: list, cwd: str = ".") -> dict:
    """Git 명령어를 안전하게 실행하고 결과를 반환합니다."""
    try:
        res = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10
        )
        if res.returncode == 0:
            return {"ok": True, "output": res.stdout.strip()}
        else:
            return {"ok": False, "error": res.stderr.strip() or "Git 명령 실패"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_repo_name(repo_path: str = ".") -> str:
    """Git 루트 디렉터리 명칭 또는 폴더명을 추출합니다."""
    res = run_git_command(["rev-parse", "--show-toplevel"], cwd=repo_path)
    if res["ok"] and res["output"]:
        return Path(res["output"]).name
    return Path(repo_path).resolve().name

def get_latest_commit_info(repo_path: str = ".") -> dict:
    """최근 커밋의 메시지, 작성자, 변경 통계 및 diff 내용을 가져옵니다."""
    repo_name = get_repo_name(repo_path)
    
    log_res = run_git_command(["log", "-1", "--pretty=format:%H|%an|%ad|%s", "--date=short"], cwd=repo_path)
    if not log_res["ok"]:
        return log_res
    
    parts = log_res["output"].split("|", 3)
    if len(parts) < 4:
        return {"ok": False, "error": "커밋 이력을 파싱할 수 없습니다."}
        
    commit_hash, author, date, message = parts
    
    stat_res = run_git_command(["show", "--stat", "--oneline", "-1"], cwd=repo_path)
    stat_text = stat_res.get("output", "")
    
    diff_res = run_git_command(["diff", "HEAD~1", "HEAD"], cwd=repo_path)
    diff_text = diff_res.get("output", "")
    if not diff_text:
        diff_res = run_git_command(["show", "-1"], cwd=repo_path)
        diff_text = diff_res.get("output", "")

    return {
        "ok": True,
        "repo_name": repo_name,
        "commit_hash": commit_hash[:8],
        "author": author,
        "date": date,
        "message": message,
        "stat": stat_text,
        "diff": diff_text[:4000]
    }

def get_working_diff(repo_path: str = ".") -> dict:
    """현재 작업 중인 변경사항(staged / unstaged)의 diff를 조회합니다."""
    repo_name = get_repo_name(repo_path)
    staged = run_git_command(["diff", "--staged"], cwd=repo_path)
    unstaged = run_git_command(["diff"], cwd=repo_path)
    
    combined = (staged.get("output", "") + "\n" + unstaged.get("output", "")).strip()
    if not combined:
        return {"ok": True, "repo_name": repo_name, "has_changes": False, "diff": "현재 변경사항이 없습니다."}
        
    return {
        "ok": True,
        "repo_name": repo_name,
        "has_changes": True,
        "diff": combined[:4000]
    }

TOOL_GIT_GET_COMMIT = {
    "name": "get_latest_commit_info",
    "description": "최근 Git 커밋의 변경 내역(diff), 커밋 메시지, 파일 변경 통계 및 저장소 명칭을 조회합니다.",
    "parameters": {
        "type": "object",
        "properties": {
            "repo_path": {
                "type": "string",
                "description": "분석할 Git 저장소 경로 (기본값: '.')"
            }
        },
        "required": []
    }
}
