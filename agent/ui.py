from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.prompt import Prompt
import time
import json

console = Console()

def print_banner():
    banner_text = """
[bold cyan]======================================================================
               Notion DevLog AI Agent (개발 기록 자동화)
                 - 시니어 엔지니어링 분석 및 노션 연동 -
======================================================================[/bold cyan]
[dim]명령어 안내:
  commit       : 최근 Git 커밋 내역 분석 및 노션 기록
  scan [경로]   : 저장소 아키텍처 및 디렉터리 분석
  sum <파일>   : 특정 소스 코드 로직 분석 및 기술 요약
  setup        : 노션 데이터베이스 스키마 속성 동기화
  exit         : 프로그램 종료[/dim]
"""
    console.print(banner_text)

def get_user_input() -> str:
    try:
        console.print("\n[bold green]사용자[/bold green]")
        return Prompt.ask("[green]❯[/green]").strip()
    except (KeyboardInterrupt, EOFError):
        return "exit"

def get_status_spinner(msg: str = "분석을 진행 중입니다..."):
    return console.status(f"[bold cyan]{msg}[/bold cyan]", spinner="dots", refresh_per_second=15)

def display_tool_call(tool_name: str, args: dict):
    tool_descriptions = {
        "get_latest_commit_info": "Git 커밋 이력 및 Diff 데이터를 조회합니다.",
        "get_working_diff": "현재 작업 트리의 변경사항(Diff)을 수집합니다.",
        "scan_repository_overview": "저장소 디렉터리 구조 및 설정 파일을 스캔합니다.",
        "read_code_file": f"소스 코드를 분석합니다. ({args.get('file_path', '')})",
        "create_notion_record": f"노션 데이터베이스에 문서를 등록합니다. ({args.get('title', '')})"
    }
    desc = tool_descriptions.get(tool_name, f"도구 실행 ({tool_name})")
    console.print(f"[bold yellow][Action][/bold yellow] {desc}")

def display_tool_result(tool_name: str, result: dict):
    is_ok = result.get("ok", True)
    if is_ok:
        if "page_url" in result:
            console.print(f"[bold green][Success][/bold green] 노션 등록 완료: [underline cyan]{result['page_url']}[/underline cyan]")
        else:
            console.print(f"[bold green][Success][/bold green] {tool_name} 실행 완료")
    else:
        err = result.get("error", "오류 발생")
        console.print(f"[bold red][Error][/bold red] {tool_name} 실패: {err}")

def display_final_response(text: str):
    console.print("\n[bold blue][Agent Response][/bold blue]")
    console.print(Markdown(text))
