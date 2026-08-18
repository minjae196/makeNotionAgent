import urllib.request
import urllib.error
import json
import re
import time
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

[도구 호출 규칙]
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
        # 500 RPD 무료 넉넉한 쿼터를 가진 Gemini 3.1 Flash Lite를 1순위로 배치
        self.models = [
            "gemini-3.1-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-3.5-flash-lite",
            "gemini-3.6-flash",
            "gemini-flash-latest"
        ]
        self.session_usage = {
            "prompt_tokens": 0,
            "output_tokens": 0,
            "api_calls": 0
        }

    def call_gemini_api(self, contents: list, system_text: str = "") -> tuple:
        """Gemini REST API를 호출하며 429 발생 시 즉시 가용 모델로 자동 페일오버합니다."""
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY가 설정되지 않았습니다.")
            
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 8192
            }
        }
        if system_text:
            payload["systemInstruction"] = {
                "parts": [{"text": system_text}]
            }
            
        body = json.dumps(payload).encode("utf-8")
        last_err = None
        
        for model in self.models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
            req = urllib.request.Request(
                url, data=body,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=20) as res:
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
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code == 429:
                    time.sleep(0.5)
                    continue
                else:
                    continue
            except Exception as e:
                last_err = e
                continue
                
        raise RuntimeError(f"Gemini API 호출에 실패했습니다: {last_err}")

    def execute_tool(self, tool_name: str, args: dict) -> dict:
        """도구를 실행하고 실시간 시각화 결과를 반환합니다."""
        tool_descriptions = {
            "get_latest_commit_info": "Git 커밋 데이터 및 변경 Diff 수집 중...",
            "get_working_diff": "작업 중인 소스 코드 Diff 수집 중...",
            "scan_repository_overview": "레포지토리 전 계층 심층 스캔 중...",
            "read_code_file": "소스 코드 상세 내용 분석 중...",
            "create_notion_record": "상세 기술 문서 및 다이어그램 노션 등록 중..."
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
            
        pattern = r"```(?:json)?\s*(\{[\s\S]*?\})\s*```"
        match = re.search(pattern, text)
        candidates = []
        if match:
            candidates.append(match.group(1))
            
        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidates.append(text[start_idx:end_idx+1])
            
        for cand in candidates:
            try:
                data = json.loads(cand, strict=False)
                if isinstance(data, dict) and "tool" in data:
                    return data
            except Exception:
                pass

        if "create_notion_record" in text:
            try:
                title_m = re.search(r'["\']title["\']\s*:\s*["\']([^"\']+)["\']', text)
                repo_m = re.search(r'["\']repo_name["\']\s*:\s*["\']([^"\']+)["\']', text)
                cat_m = re.search(r'["\']category["\']\s*:\s*["\']([^"\']+)["\']', text)
                
                tags = []
                tags_idx = text.find('"tags"')
                if tags_idx != -1:
                    tags_block = text[tags_idx:text.find(']', tags_idx)+1]
                    tags = re.findall(r'["\']([^"\'\[\],]+)["\']', tags_block)
                    if tags and tags[0] == "tags":
                        tags = tags[1:]

                content_idx = text.find('"markdown_content"')
                if content_idx == -1:
                    content_idx = text.find("'markdown_content'")
                    
                if content_idx != -1:
                    sub = text[content_idx:]
                    first_colon = sub.find(':')
                    after_colon = sub[first_colon+1:].lstrip()
                    if after_colon.startswith('"') or after_colon.startswith("'"):
                        quote_char = after_colon[0]
                        body_start = 1
                        last_brace = after_colon.rfind('}')
                        last_quote = after_colon.rfind(quote_char, 0, last_brace if last_brace != -1 else len(after_colon))
                        raw_content = after_colon[body_start:last_quote if last_quote > body_start else len(after_colon)]
                        
                        cleaned = (raw_content
                                   .replace('\\n', '\n')
                                   .replace('\\"', '"')
                                   .replace("\\'", "'")
                                   .replace('\\\\', '\\'))
                        
                        return {
                            "tool": "create_notion_record",
                            "args": {
                                "title": title_m.group(1) if title_m else "시스템 아키텍처 분석 보고서",
                                "repo_name": repo_m.group(1) if repo_m else "default",
                                "category": cat_m.group(1) if cat_m else "Repo Analysis",
                                "tags": tags if tags else ["Architecture"],
                                "markdown_content": cleaned
                            }
                        }
            except Exception:
                pass

        for tool_name in ["scan_repository_overview", "read_code_file", "get_latest_commit_info", "get_working_diff"]:
            if f'"{tool_name}"' in text or f"'{tool_name}'" in text:
                try:
                    target_m = re.search(r'["\'](?:target_dir|file_path|repo_path)["\']\s*:\s*["\']([^"\']+)["\']', text)
                    param_name = "target_dir" if tool_name == "scan_repository_overview" else ("file_path" if tool_name == "read_code_file" else "repo_path")
                    args = {param_name: target_m.group(1)} if target_m else {}
                    return {"tool": tool_name, "args": args}
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
            spinner_text = "코드를 심층 분석하고 아키텍처 다이어그램을 설계하는 중..." if turn == 1 else "심층 분석 결과를 바탕으로 고품질 기술 문서를 작성하는 중..."
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
            
            if not tool_call and turn == 1 and any(k in user_msg.lower() for k in ["scan", "스캔", "분석", "commit", "커밋", "sum", "요약"]):
                contents.append({"role": "model", "parts": [{"text": llm_response}]})
                contents.append({
                    "role": "user",
                    "parts": [{"text": "인사말 대신 실제 코드 데이터를 수집할 수 있도록 적절한 도구(scan_repository_overview, read_code_file 등)를 호출하는 JSON을 즉시 출력하십시오."}]
                })
                continue

            if not tool_call:
                display_final_response(llm_response)
                display_token_usage(turn_total_usage, self.session_usage)
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
                    "text": f"[도구 '{tool_name}' 실행 결과]\n{json.dumps(tool_result, ensure_ascii=False)}\n\n위 결과를 바탕으로 피상적인 요약이 아닌, 각 계층의 역할, 핵심 로직, 구체적인 코드 리뷰/개선점을 포함한 상세하고 깊이 있는(In-depth) 기술 문서를 작성하여 create_notion_record 도구를 호출하세요."
                }]
            })
