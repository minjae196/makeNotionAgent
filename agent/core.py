import urllib.request
import json
import re
from config import GEMINI_API_KEY, NOTION_API_KEY, GEMINI_MODEL
from memory.persona import SYSTEM_PROMPT
from tools.notion_tool import create_notion_record, get_database_info, auto_setup_database_properties
from tools.git_tool import get_latest_commit_info, get_working_diff
from tools.code_tool import scan_repository_overview, read_code_file
from agent.ui import (
    get_status_spinner, display_tool_call, display_tool_result,
    display_final_response, console
)

TOOL_FUNCTIONS = {
    "create_notion_record": create_notion_record,
    "get_latest_commit_info": get_latest_commit_info,
    "get_working_diff": get_working_diff,
    "scan_repository_overview": scan_repository_overview,
    "read_code_file": read_code_file
}

TOOLS_PROMPT = """
[사용 가능한 도구(Tools) 목록]
1. `get_latest_commit_info(repo_path="..")`: 최근 Git 커밋 내역(diff, commit message, repo_name 등) 조회
2. `get_working_diff(repo_path="..")`: 현재 작업 중인 코드 변경사항(diff, repo_name) 조회
3. `scan_repository_overview(target_dir="..")`: 레포지토리 폴더 구조 및 주요 설정 파일 스캔
4. `read_code_file(file_path="...")`: 특정 소스 코드 파일 내용 읽기
5. `create_notion_record(title="...", repo_name="...", category="Commit Log|Repo Analysis|Code Summary|Architecture|Dev Note", markdown_content="...", tags=["..."])`: 노션 데이터베이스에 페이지 생성 (Mermaid 다이어그램 시각화 포함 가능)

[도구 호출 규칙]
도구를 호출할 때는 반드시 아래와 같이 단일 JSON 블록만 출력하세요:
```json
{
  "tool": "도구이름",
  "args": { "인자명": "값" }
}
```
분석과 노션 작성이 모두 완료되어 사용자에게 최종 안내할 때는 JSON 없이 일반 마크다운 텍스트로 전문적으로 답변하세요.
"""

class DevLogAgent:
    def __init__(self):
        preferred = GEMINI_MODEL if GEMINI_MODEL.startswith("models/") else f"models/{GEMINI_MODEL}"
        candidate_list = [
            preferred,
            "models/gemini-3-flash-preview",
            "models/gemini-3.7-flash",
            "models/gemini-3.1-flash-lite-preview"
        ]
        self.models = list(dict.fromkeys(candidate_list))

    def call_gemini_api(self, contents: list, system_text: str = "") -> str:
        """Gemini REST API를 직접 호출합니다."""
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")
            
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 4096
            }
        }
        if system_text:
            payload["systemInstruction"] = {
                "parts": [{"text": system_text}]
            }
            
        body = json.dumps(payload).encode("utf-8")
        last_err = None
        
        for model in self.models:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent?key={GEMINI_API_KEY}"
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as res:
                    data = json.loads(res.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
            except Exception as e:
                last_err = e
                continue
                
        raise RuntimeError(f"Gemini API 호출에 실패했습니다: {last_err}")

    def execute_tool(self, tool_name: str, args: dict) -> dict:
        """도구를 실행하고 실시간 시각화 결과를 반환합니다."""
        tool_descriptions = {
            "get_latest_commit_info": "Git 커밋 데이터 및 변경 Diff 수집 중...",
            "get_working_diff": "작업 중인 소스 코드 Diff 수집 중...",
            "scan_repository_overview": "레포지토리 구조 및 설정 파일 스캔 중...",
            "read_code_file": "소스 코드 내용 분석 중...",
            "create_notion_record": "노션 문서 등록 및 다이어그램 블록 생성 중..."
        }
        status_msg = tool_descriptions.get(tool_name, f"도구 실행 중 ({tool_name})...")
        
        with get_status_spinner(status_msg):
            display_tool_call(tool_name, args)
            func = TOOL_FUNCTIONS.get(tool_name)
            if not func:
                result = {"ok": False, "error": f"알 수 없는 도구입니다: {tool_name}"}
            else:
                try:
                    result = func(**args)
                except Exception as e:
                    result = {"ok": False, "error": f"도구 실행 중 오류 발생: {str(e)}"}
                    
        display_tool_result(tool_name, result)
        return result

    def extract_tool_call(self, text: str):
        """텍스트에서 JSON 도구 호출 블록을 추출합니다."""
        pattern = r"```json\s*(\{.*?\})\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if "tool" in data:
                    return data
            except Exception:
                pass
        try:
            data = json.loads(text.strip())
            if "tool" in data:
                return data
        except Exception:
            pass
        return None

    def chat_turn(self, user_msg: str):
        """에이전트 판단 및 실행 루프"""
        if not GEMINI_API_KEY:
            display_final_response("`GEMINI_API_KEY`가 설정되지 않았습니다.")
            return

        full_system = SYSTEM_PROMPT + "\n\n" + TOOLS_PROMPT
        contents = [
            {"role": "user", "parts": [{"text": user_msg}]}
        ]
        
        MAX_TURNS = 6
        turn = 0
        
        while turn < MAX_TURNS:
            turn += 1
            spinner_text = "코드를 분석하고 다이어그램을 설계하는 중..." if turn == 1 else "분석 결과를 기반으로 기술 문서를 작성하는 중..."
            with get_status_spinner(spinner_text):
                try:
                    llm_response = self.call_gemini_api(contents, full_system)
                except Exception as e:
                    display_final_response(f"LLM 호출 실패: {e}")
                    return

            tool_call = self.extract_tool_call(llm_response)
            
            if not tool_call:
                display_final_response(llm_response)
                break

            tool_name = tool_call["tool"]
            tool_args = tool_call.get("args", {})
            
            contents.append({
                "role": "model",
                "parts": [{"text": llm_response}]
            })
            
            tool_result = self.execute_tool(tool_name, tool_args)
            
            contents.append({
                "role": "user",
                "parts": [{
                    "text": f"[도구 '{tool_name}' 실행 결과]\n{json.dumps(tool_result, ensure_ascii=False)}\n\n위 결과를 바탕으로 필요한 다음 도구를 호출하거나 최종 기술 문서를 작성해주세요."
                }]
            })
