from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.prompt import Prompt
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
  tokens       : 세션 누적 토큰 사용량 및 비용 확인
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

def display_token_usage(turn_usage: dict, session_usage: dict):
    """이번 턴 및 세션 누적 토큰 사용량을 깔끔한 패널/텍스트로 표시합니다."""
    t_prompt = turn_usage.get("promptTokenCount", 0)
    t_cand = turn_usage.get("candidatesTokenCount", 0)
    t_total = turn_usage.get("totalTokenCount", 0)
    
    s_prompt = session_usage.get("prompt_tokens", 0)
    s_cand = session_usage.get("output_tokens", 0)
    s_total = s_prompt + s_cand
    
    usage_text = (
        f"[dim]📊 [bold cyan]토큰 사용량[/bold cyan] | "
        f"이번 요청: [bold]{t_total:,}[/bold] tokens (입력: {t_prompt:,}, 출력: {t_cand:,}) | "
        f"세션 누적: [bold green]{s_total:,}[/bold green] tokens (입력: {s_prompt:,}, 출력: {s_cand:,})[/dim]"
    )
    console.print(usage_text)

def display_session_token_summary(session_usage: dict):
    """세션 전체 토큰 사용 통계 테이블을 출력합니다."""
    table = Table(title="📊 세션 누적 토큰 사용량 및 통계", border_style="cyan")
    table.add_column("구분", style="cyan", justify="left")
    table.add_column("토큰 수 (Tokens)", style="magenta", justify="right")
    table.add_column("비율", style="white", justify="right")
    
    p = session_usage.get("prompt_tokens", 0)
    o = session_usage.get("output_tokens", 0)
    tot = p + o
    
    p_pct = f"{(p / tot * 100):.1f}%" if tot > 0 else "0.0%"
    o_pct = f"{(o / tot * 100):.1f}%" if tot > 0 else "0.0%"
    
    table.add_row("입력 프롬프트 (Prompt)", f"{p:,}", p_pct)
    table.add_row("출력 응답 (Output/Candidates)", f"{o:,}", o_pct)
    table.add_row("[bold]총 사용 토큰 (Total)[/bold]", f"[bold]{tot:,}[/bold]", "[bold]100.0%[/bold]")
    table.add_row("API 호출 횟수", f"{session_usage.get('api_calls', 0)}회", "-")
    
    console.print(table)
