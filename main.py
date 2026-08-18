import sys
import os
from pathlib import Path
from config import NOTION_API_KEY, NOTION_DATABASE_ID, GEMINI_API_KEY
from agent.ui import print_banner, get_user_input, console
from agent.core import DevLogAgent
from tools.notion_tool import get_database_info, auto_setup_database_properties

def check_env_status():
    """환경변수 상태를 점검합니다."""
    missing = []
    if not NOTION_API_KEY or "your_notion" in NOTION_API_KEY:
        missing.append("NOTION_API_KEY")
    if not GEMINI_API_KEY or "your_gemini" in GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
        
    if missing:
        console.print(f"[bold red]⚠️  환경 변수 미설정:[/bold red] {', '.join(missing)}")
        console.print("[dim]`makeNotionAgent/.env` 파일에 API 키를 입력해 주세요.[/dim]\n")

def run_cli_loop():
    print_banner()
    check_env_status()
    
    agent = DevLogAgent()
    
    while True:
        user_input = get_user_input()
        if user_input.lower() in ["exit", "quit", "q"]:
            console.print("[bold cyan]👋 에이전트를 종료합니다. 즐거운 코딩 되세요![/bold cyan]")
            break
        elif user_input.lower() in ["clear", "cls"]:
            os.system("clear")
            print_banner()
            continue
        elif user_input.lower() == "setup":
            console.print("[bold yellow]⚙️ 노션 데이터베이스 연결 확인 및 속성 정리를 진행합니다...[/bold yellow]")
            res = auto_setup_database_properties()
            if res.get("ok"):
                console.print(f"[bold green]✅ {res.get('message')}[/bold green]")
            else:
                console.print(f"[bold red]❌ {res.get('error')}[/bold red]")
            continue
        elif user_input.lower() == "commit":
            user_input = "최근 Git 커밋 변경사항을 분석해서 내 말투로 노션에 기록해줘."
        elif user_input.lower().startswith("scan"):
            parts = user_input.split(maxsplit=1)
            target = parts[1] if len(parts) > 1 else "."
            user_input = f"'{target}' 디렉터리의 레포지토리 구조와 핵심 아키텍처를 분석해서 가독성 좋게 노션에 기록해줘."
        elif user_input.lower().startswith("sum"):
            parts = user_input.split(maxsplit=1)
            target = parts[1] if len(parts) > 1 else "."
            user_input = f"'{target}' 코드를 정확하게 요약하고 로직 흐름을 분석해서 노션에 기록해줘."

        if not user_input.strip():
            continue
            
        agent.chat_turn(user_input)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        agent = DevLogAgent()
        
        if cmd == "commit":
            agent.chat_turn("최근 Git 커밋 변경사항을 분석해서 내 말투로 노션에 기록해줘.")
        elif cmd == "scan":
            target = sys.argv[2] if len(sys.argv) > 2 else "."
            agent.chat_turn(f"'{target}' 디렉터리의 레포지토리 구조와 핵심 아키텍처를 분석해서 가독성 좋게 노션에 기록해줘.")
        elif cmd in ["sum", "summarize"]:
            target = sys.argv[2] if len(sys.argv) > 2 else "."
            agent.chat_turn(f"'{target}' 코드를 정확하게 요약하고 로직 흐름을 분석해서 노션에 기록해줘.")
        elif cmd == "setup":
            res = auto_setup_database_properties()
            print(res)
        else:
            agent.chat_turn(" ".join(sys.argv[1:]))
    else:
        run_cli_loop()
