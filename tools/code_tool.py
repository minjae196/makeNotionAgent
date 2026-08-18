import os
from pathlib import Path
from tools.git_tool import get_repo_name

IGNORE_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".idea", ".vscode", ".gemini", ".gradle", "target", "bin", "out", ".mvn"
}

CODE_EXTENSIONS = {
    ".java", ".kt", ".py", ".ts", ".js", ".go", ".rs", ".cpp", ".c",
    ".yml", ".yaml", ".json", ".sql", ".gradle", ".xml", ".properties"
}

def get_full_directory_tree(start_path: Path, max_depth: int = 8, current_depth: int = 0) -> list:
    """디렉터리를 깊이 탐색하여 전체 파일 목록과 계층 구조를 수집합니다."""
    if current_depth > max_depth:
        return []
        
    collected_files = []
    try:
        entries = sorted(os.listdir(start_path))
        for entry in entries:
            if entry in IGNORE_DIRS or entry.startswith('.'):
                continue
            
            full_path = start_path / entry
            if full_path.is_dir():
                collected_files.extend(get_full_directory_tree(full_path, max_depth, current_depth + 1))
            else:
                collected_files.append(full_path)
    except Exception:
        pass
        
    return collected_files

def scan_repository_overview(target_dir: str = ".") -> dict:
    """
    레포지토리의 모든 하위 폴더와 소스 코드를 심층(Deep) 스캔하여
    아키텍처 계층별 파일 목록과 핵심 소스 코드들을 종합 수집합니다.
    """
    try:
        base = Path(target_dir).resolve()
        if not base.exists():
            base = (Path("..") / target_dir).resolve()
        if not base.exists():
            return {"ok": False, "error": f"경로를 찾을 수 없습니다: {target_dir}"}
            
        repo_name = get_repo_name(str(base))
        all_files = get_full_directory_tree(base, max_depth=10)
        
        # 1. 파일 유형 및 계층별 분류
        layer_summary = {
            "Controllers / Endpoints": [],
            "Services / Business Logic": [],
            "Repositories / Data Access": [],
            "Entities / Domain Models": [],
            "Configurations / Infrastructure": [],
            "Other Source Files": []
        }
        
        important_snippets = {}
        total_code_files = 0
        
        for file_path in all_files:
            rel_path = file_path.relative_to(base).as_posix()
            ext = file_path.suffix.lower()
            name = file_path.name.lower()
            
            if ext not in CODE_EXTENSIONS and name not in ["dockerfile", "makefile"]:
                continue
                
            total_code_files += 1
            
            # 아키텍처 계층 자동 분류
            if any(k in name for k in ["controller", "resource", "router", "endpoint", "api", "view"]):
                layer_summary["Controllers / Endpoints"].append(rel_path)
            elif any(k in name for k in ["service", "usecase", "manager", "handler", "logic"]):
                layer_summary["Services / Business Logic"].append(rel_path)
            elif any(k in name for k in ["repository", "dao", "mapper", "query"]):
                layer_summary["Repositories / Data Access"].append(rel_path)
            elif any(k in name for k in ["entity", "model", "dto", "domain", "schema"]):
                layer_summary["Entities / Domain Models"].append(rel_path)
            elif any(k in name for k in ["config", "properties", "application", "docker", "build", "pom", "settings"]):
                layer_summary["Configurations / Infrastructure"].append(rel_path)
            else:
                layer_summary["Other Source Files"].append(rel_path)
                
            # 2. 핵심 아키텍처 파일(설정, 메인 진입점, 주요 컨트롤러/서비스) 내용 샘플링 (최대 12개 파일)
            is_priority = (
                name in ["build.gradle", "pom.xml", "application.yml", "application.properties", "readme.md", "dockerfile"] or
                "application" in name or
                "controller" in name or
                "service" in name or
                "config" in name
            )
            
            if is_priority and len(important_snippets) < 12:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(3000) # 파일당 최대 3000자
                        important_snippets[rel_path] = content
                except Exception:
                    pass

        # 3. 비어있는 계층 정리
        layer_summary = {k: v for k, v in layer_summary.items() if v}

        return {
            "ok": True,
            "repo_name": repo_name,
            "root_path": str(base),
            "total_files_scanned": len(all_files),
            "total_code_files": total_code_files,
            "architecture_layers": layer_summary,
            "key_file_contents": important_snippets
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

def read_code_file(file_path: str) -> dict:
    """지정된 코드 파일의 전체 내용을 읽습니다."""
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
            content = f.read(8000)
            
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
    "description": "프로젝트/레포지토리의 모든 하위 폴더를 깊이 탐색하여 Controller, Service, Repository, Entity, Config 등 전체 아키텍처 계층과 핵심 소스 코드들을 종합 수집합니다.",
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
                "description": "읽을 파일 경로 (예: 'src/main/java/.../UserController.java')"
            }
        },
        "required": ["file_path"]
    }
}
