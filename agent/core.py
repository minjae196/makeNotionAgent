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
    display_final_response, display_token_usage, display_session_token_summary,
    console
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
1. `scan_repository_overview(target_dir="..")`: 레포지토리 폴더 구조 및 주요 설정 파일 스캔
2. `read_code_file(file_path="...")`: 특정 소스 코드 파일 내용 읽기
3. `get_latest_commit_info(repo_path="..")`: 최근 Git 커밋 내역(diff, commit message, repo_name 등) 조회
4. `get_working_diff(repo_path="..")`: 현재 작업 중인 코드 변경사항(diff, repo_name) 조회
5. `create_notion_record(title="...", repo_name="...", category="Commit Log|Repo Analysis|Code Summary|Architecture|Dev Note", markdown_content="...", tags=["..."])`: 노션 데이터베이스에 페이지 생성

[도구 호출 규칙 (매우 중요)]
- 사용자가 분석이나 조사를 요구하면 인사말을 하지 말고, 반드시 1단계에서 적절한 도구 호출 JSON을 즉시 출력하세요.
- 도구를 호출할 때는 반드시 아래 형식의 JSON 블록만 출력해야 합니다:
```json
{
  "tool": "도구이름",
  "args": { "인자명": "값" }
}
```
- 모든 도구 실행과 `create_notion_record` 호출이 완료된 후에만 사용자에게 최종 완료 안내 마크다운 텍스트를 출력하세요.
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
        self.session_usage = {
            "prompt_tokens": 0,
            "output_tokens": 0,
            "api_calls": 0
        }

    def call_gemini_api(self, contents: list, system_text: str = "") -> tuple:
        """Gemini REST API를 직접 호출하고 텍스트 및 사용 토큰 메타데이터를 반환합니다."""
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
                with urllib.request.urlopen(req, timeout=12) as res:
                    data = json.loads(res.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    usage = data.get("usageMetadata", {})
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            text = parts[0].get("text", "")
                            
                            p_cnt = usage.get("promptTokenCount", 0)
                            c_cnt = usage.get("candidatesTokenCount", 0)
                            self.session_usage["prompt_tokens"] += p_cnt
                            self.session_usage["output_tokens"] += c_cnt
                            self.session_usage["api_calls"] += 1
                            
                            return text, usage
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
        """텍스트에서 JSON 도구 호출 블록을 유연하고 강력하게 추출합니다."""
        if not text:
            return None
            
        # 1. 마크다운 코드 블록 (```json ... ``` 또는 ``` ... ```)
        pattern = r"```(?:json)?\s*(\{[\s\S]*?\})\s*```"
        match = re.search(pattern, text)
        if match:
            raw = match.group(1)
            try:
                data = json.loads(raw, strict=False)
                if "tool" in data:
                    return data
            except Exception:
                pass

        # 2. 본문 전체에서 { ... "tool" : ... } 형태의 최외곽 JSON 탐색
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidate = text[start_idx:end_idx+1]
            try:
                data = json.loads(candidate, strict=False)
                if "tool" in data:
                    return data
            except Exception:
                try:
                    cleaned = re.sub(r'[\r\n\t]', ' ', candidate)
                    data = json.loads(cleaned, strict=False)
                    if "tool" in data:
                        return data
                except Exception:
                    pass

        # 3. 정규표현식으로 create_notion_record 직접 파싱
        if '"tool": "create_notion_record"' in text or "'tool': 'create_notion_record'" in text:
            try:
                title_match = re.search(r'"title"\s*:\s*"([^"]+)"', text)
                repo_match = re.search(r'"repo_name"\s*:\s*"([^"]+)"', text)
                cat_match = re.search(r'"category"\s*:\s*"([^"]+)"', text)
                content_match = re.search(r'"markdown_content"\s*:\s*"([\s\S]+?)"\s*,\s*"(?:tags|repo_name)', text)
                
                if title_match and cat_match and content_match:
                    return {
                        "tool": "create_notion_record",
                        "args": {
                            "title": title_match.group(1),
                            "repo_name": repo_match.group(1) if repo_match else "default",
                            "category": cat_match.group(1),
                            "markdown_content": content_match.group(1).replace("\\n", "\n").replace('\\"', '"')
                        }
                    }
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
        
        MAX_TURNS = 7
        turn = 0
        turn_total_usage = {"promptTokenCount": 0, "candidatesTokenCount": 0, "totalTokenCount": 0}
        
        while turn < MAX_TURNS:
            turn += 1
            spinner_text = "코드를 분석하고 다이어그램을 설계하는 중..." if turn == 1 else "분석 결과를 기반으로 기술 문서를 작성하는 중..."
            with get_status_spinner(spinner_text):
                try:
                    llm_response, usage = self.call_gemini_api(contents, full_system)
                    turn_total_usage["promptTokenCount"] += usage.get("promptTokenCount", 0)
                    turn_total_usage["candidatesTokenCount"] += usage.get("candidatesTokenCount", 0)
                    turn_total_usage["totalTokenCount"] += usage.get("totalTokenCount", 0)
                except Exception as e:
                    display_final_response(f"LLM 호출 실패: {e}")
                    return

            tool_call = self.extract_tool_call(llm_response)
            
            # 첫 턴인데 도구를 안 부르고 인사말만 한 경우, 도구 호출을 다시 강제
            if not tool_call and turn == 1 and any(k in user_msg.lower() for k in ["scan", "스캔", "분석", "commit", "커밋", "sum", "요약"]):
                contents.append({"role": "model", "parts": [{"text": llm_response}]})
                contents.append({
                    "role": "user",
                    "parts": [{"text": "인사말 대신 실제 코드/디렉터리 데이터를 수집할 수 있도록 적절한 도구(scan_repository_overview, read_code_file, get_latest_commit_info)를 호출하는 JSON을 즉시 출력하십시오."}]
                })
                continue

            # 도구 호출이 없는 경우 = 최종 사용자 답변
            if not tool_call:
                display_final_response(llm_response)
                display_token_usage(turn_total_usage, self.session_usage)
                break

            # 도구 호출 실행
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
                    "text": f"[도구 '{tool_name}' 실행 결과]\n{json.dumps(tool_result, ensure_ascii=False)}\n\n위 결과를 바탕으로 추가 조사가 필요하면 read_code_file 등을 호출하고, 분석이 완료되었으면 create_notion_record 도구를 호출하여 노션에 기술 문서를 등록하세요."
                }]
            })
