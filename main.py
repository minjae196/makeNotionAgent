import sys
import os
from pathlib import Path
from config import NOTION_API_KEY, NOTION_DATABASE_ID, GEMINI_API_KEY
from agent.ui import print_banner, get_user_input, display_session_token_summary, console
from agent.core import DevLogAgent
from tools.notion_tool import get_database_info, auto_setup_database_properties

def check_env_status():
    """환경변수 상태를 점검합니다."""
    missing = []
    if not NOTION_API_KEY:
        missing.append("NOTION_API_KEY")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
        
    if missing:
        console.print(f"[bold red]환경 변수 미설정:[/bold red] {', '.join(missing)}")
        console.print("[dim].env 파일에 API 키를 입력해 주세요.[/dim]\n")

def install_git_hook(target_repo: str = "."):
    """지정된 Git 저장소에 post-commit 자동 기록 훅을 설치합니다."""
    base = Path(target_repo).resolve()
    git_dir = base / ".git"
    if not git_dir.exists():
        console.print(f"[bold red][Error][/bold red] '{target_repo}' 경로는 Git 저장소가 아닙니다.")
        return
        
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    post_commit_path = hooks_dir / "post-commit"
    
    agent_main = Path(__file__).resolve()
    hook_script = f"""#!/bin/bash
# Notion DevLog Agent 자동 발동 훅
python3 "{agent_main}" commit &
"""
    with open(post_commit_path, "w", encoding="utf-8") as f:
        f.write(hook_script)
        
    os.chmod(post_commit_path, 0o755)
    console.print(f"[bold green][Success][/bold green] '{base.name}' 저장소에 Git 커밋 자동 기록 훅(post-commit)이 설치되었습니다.")
    console.print("[dim]이제 git commit 명령을 실행할 때마다 에이전트가 백그라운드에서 노션에 자동 기록합니다.[/dim]")

def run_cli_loop():
    print_banner()
    check_env_status()
    
    agent = DevLogAgent()
    
    while True:
        user_input = get_user_input()
        if user_input.lower() in ["exit", "quit", "q"]:
            console.print("[bold cyan]에이전트를 종료합니다.[/bold cyan]")
            break
        elif user_input.lower() in ["clear", "cls"]:
            os.system("clear")
            print_banner()
            continue
        elif user_input.lower() in ["--help", "-h", "help"]:
            print_banner()
            continue
        elif user_input.lower() in ["tokens", "usage", "token"]:
            display_session_token_summary(agent.session_usage)
            continue
        elif user_input.lower() == "setup":
            console.print("[bold yellow]노션 데이터베이스 속성 동기화를 진행합니다...[/bold yellow]")
            res = auto_setup_database_properties()
            if res.get("ok"):
                console.print(f"[bold green]{res.get('message')}[/bold green]")
            else:
                console.print(f"[bold red]{res.get('error')}[/bold red]")
            continue
        elif user_input.lower().startswith("install-hook") or user_input.lower().startswith("hook"):
            parts = user_input.split(maxsplit=1)
            target = parts[1] if len(parts) > 1 else "."
            install_git_hook(target)
            continue
        elif user_input.lower() == "commit":
            user_input = "도구 get_latest_commit_info()를 호출하여 최근 커밋의 변경 내역(diff)을 수집하고 노션에 기술 문서로 기록해주세요."
        elif user_input.lower().startswith("scan"):
            parts = user_input.split(maxsplit=1)
            target = parts[1] if len(parts) > 1 else "."
            user_input = f"도구 scan_repository_overview(target_dir='{target}')를 즉시 호출하여 디렉터리 구조와 주요 설정 파일을 수집하고 아키텍처 다이어그램과 함께 노션에 기록해주세요."
        elif user_input.lower().startswith("sum"):
            parts = user_input.split(maxsplit=1)
            target = parts[1] if len(parts) > 1 else "."
            user_input = f"도구 read_code_file(file_path='{target}')를 즉시 호출하여 소스 코드를 읽고 주요 구현 로직, 시각화, 개선 보완점을 노션에 기록해주세요."

        if not user_input.strip():
            continue
            
        agent.chat_turn(user_input)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in ["--help", "-h", "help"]:
            print_banner()
            sys.exit(0)
            
        agent = DevLogAgent()
        
        if cmd == "commit":
            agent.chat_turn("도구 get_latest_commit_info()를 호출하여 최근 커밋의 변경 내역(diff)을 수집하고 노션에 기술 문서로 기록해주세요.")
        elif cmd == "scan":
            target = sys.argv[2] if len(sys.argv) > 2 else "."
            agent.chat_turn(f"도구 scan_repository_overview(target_dir='{target}')를 즉시 호출하여 디렉터리 구조와 주요 설정 파일을 수집하고 아키텍처 다이어그램과 함께 노션에 기록해주세요.")
        elif cmd in ["sum", "summarize"]:
            target = sys.argv[2] if len(sys.argv) > 2 else "."
            agent.chat_turn(f"도구 read_code_file(file_path='{target}')를 즉시 호출하여 소스 코드를 읽고 주요 구현 로직, 시각화, 개선 보완점을 노션에 기록해주세요.")
        elif cmd == "setup":
            res = auto_setup_database_properties()
            print(res)
        elif cmd in ["install-hook", "hook"]:
            target = sys.argv[2] if len(sys.argv) > 2 else "."
            install_git_hook(target)
        else:
            agent.chat_turn(" ".join(sys.argv[1:]))
    else:
        run_cli_loop()
