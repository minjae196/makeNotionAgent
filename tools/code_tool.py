import os
from pathlib import Path
from tools.git_tool import get_repo_name

IGNORE_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".idea", ".vscode", ".gemini"}

def get_directory_tree(start_path: str, max_depth: int = 3, current_depth: int = 0) -> str:
    """디렉터리 계층 구조를 텍스트 트리로 생성합니다."""
    if current_depth > max_depth:
        return ""
    
    tree_str = ""
    try:
        entries = sorted(os.listdir(start_path))
        for entry in entries:
            if entry in IGNORE_DIRS or entry.startswith('.'):
                continue
            
            full_path = os.path.join(start_path, entry)
            indent = "  " * current_depth
            
            if os.path.isdir(full_path):
                tree_str += f"{indent}📁 {entry}/\n"
                tree_str += get_directory_tree(full_path, max_depth, current_depth + 1)
            else:
                tree_str += f"{indent}📄 {entry}\n"
    except Exception as e:
        tree_str += f"[디렉터리 접근 오류: {e}]\n"
        
    return tree_str

def scan_repository_overview(target_dir: str = ".") -> dict:
    """레포지토리의 전체 구조, README, 설정 파일을 스캔하여 개요를 수집합니다."""
    try:
        base = Path(target_dir).resolve()
        if not base.exists():
            base = (Path("..") / target_dir).resolve()
        if not base.exists():
            return {"ok": False, "error": f"경로가 존재하지 않습니다: {target_dir}"}
            
        repo_name = get_repo_name(str(base))
        tree = get_directory_tree(str(base), max_depth=3)
        
        important_files = ["README.md", "package.json", "requirements.txt", "pom.xml", "build.gradle", "go.mod", "Dockerfile", "docker-compose.yml"]
        file_snippets = {}
        
        for f_name in important_files:
            f_path = base / f_name
            if f_path.exists() and f_path.is_file():
                try:
                    with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                        file_snippets[f_name] = f.read(2500)
                except Exception:
                    pass

        return {
            "ok": True,
            "repo_name": repo_name,
            "root_path": str(base),
            "directory_tree": tree[:3000],
            "key_files_found": list(file_snippets.keys()),
            "key_file_contents": file_snippets
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def read_code_file(file_path: str) -> dict:
    """지정된 코드 파일의 전체 또는 일부 내용을 유연하게 경로를 탐색하여 읽습니다."""
    try:
        candidates = [
            Path(file_path),
            Path("..") / file_path,
            Path(".") / file_path,
            Path(file_path.replace("makeNotionAgent/", "")) if "makeNotionAgent/" in file_path else None,
            Path("..") / file_path.replace("makeNotionAgent/", "") if "makeNotionAgent/" in file_path else None
        ]
        
        target = None
        for cand in candidates:
            if cand and cand.exists() and cand.is_file():
                target = cand.resolve()
                break
                
        if not target:
            return {"ok": False, "error": f"파일을 찾을 수 없습니다: {file_path}"}
            
        repo_name = get_repo_name(str(target.parent))
        with open(target, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(6000)
            
        return {
            "ok": True,
            "repo_name": repo_name,
            "file_name": target.name,
            "relative_path": str(file_path),
            "content": content
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

TOOL_SCAN_REPO = {
    "name": "scan_repository_overview",
    "description": "프로젝트/레포지토리의 폴더 구조(트리), README, 핵심 설정 파일 및 레포지토리명을 스캔합니다.",
    "parameters": {
        "type": "object",
        "properties": {
            "target_dir": {
                "type": "string",
                "description": "분석할 디렉터리 경로 (기본값: '.')"
            }
        },
        "required": []
    }
}

TOOL_READ_CODE_FILE = {
    "name": "read_code_file",
    "description": "특정 소스 코드 파일의 내용과 소속 레포지토리명을 조회합니다.",
    "parameters": {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "읽을 파일 경로 (예: 'agent/core.py')"
            }
        },
        "required": ["file_path"]
    }
}
