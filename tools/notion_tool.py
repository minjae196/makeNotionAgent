import urllib.request
import json
import re
from datetime import datetime
from config import NOTION_API_KEY, NOTION_DATABASE_ID

def send_notion_request(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Notion API에 HTTP 요청을 전송합니다."""
    url = f"https://api.notion.com/v1/{endpoint}"
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            res_body = res.read().decode("utf-8")
            return {"ok": True, "status": res.status, "data": json.loads(res_body)}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        return {"ok": False, "status": e.code, "error": f"Notion API 에러 ({e.code}): {err_msg}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_database_info() -> dict:
    """노션 데이터베이스의 현재 스키마 및 속성 정보를 조회합니다."""
    return send_notion_request(f"databases/{NOTION_DATABASE_ID}")

def auto_setup_database_properties() -> dict:
    """에이전트가 기록하기 좋은 표준 속성(저장소, 분류, 작성일, 태그)을 노션 DB에 자동 구성합니다."""
    payload = {
        "properties": {
            "저장소": {
                "select": {}
            },
            "분류": {
                "select": {
                    "options": [
                        {"name": "Commit Log", "color": "blue"},
                        {"name": "Repo Analysis", "color": "purple"},
                        {"name": "Code Summary", "color": "green"},
                        {"name": "Architecture", "color": "pink"},
                        {"name": "Dev Note", "color": "orange"}
                    ]
                }
            },
            "작성일": {
                "date": {}
            },
            "태그": {
                "multi_select": {
                    "options": [
                        {"name": "Git", "color": "gray"},
                        {"name": "Refactor", "color": "yellow"},
                        {"name": "Feature", "color": "green"},
                        {"name": "Fix", "color": "red"},
                        {"name": "Architecture", "color": "pink"},
                        {"name": "Review", "color": "purple"}
                    ]
                }
            }
        }
    }
    res = send_notion_request(f"databases/{NOTION_DATABASE_ID}", method="PATCH", data=payload)
    if res["ok"]:
        return {"ok": True, "message": "노션 데이터베이스 속성(저장소, 분류, 작성일, 태그)이 동기화되었습니다."}
    return res

def parse_inline_rich_text(text: str) -> list:
    """
    마크다운 인라인 문법(**굵게**, `인라인코드`, *기울임*)을 노션 Rich Text Annotation 객체로 변환합니다.
    """
    if not text:
        return []
        
    pattern = re.compile(r'(\*\*(?:[^*]|\*(?!\*))+?\*\*|`[^`\n]+?`|\*(?:[^*])+?\*)')
    rich_text_list = []
    last_idx = 0
    
    for match in pattern.finditer(text):
        start, end = match.span()
        if start > last_idx:
            plain = text[last_idx:start]
            if plain:
                rich_text_list.append({"type": "text", "text": {"content": plain[:2000]}})
                
        token = match.group(0)
        if token.startswith("**") and token.endswith("**") and len(token) >= 4:
            content = token[2:-2]
            if content.startswith("`") and content.endswith("`") and len(content) >= 2:
                rich_text_list.append({
                    "type": "text",
                    "text": {"content": content[1:-1][:2000]},
                    "annotations": {"bold": True, "code": True}
                })
            else:
                rich_text_list.append({
                    "type": "text",
                    "text": {"content": content[:2000]},
                    "annotations": {"bold": True}
                })
        elif token.startswith("`") and token.endswith("`") and len(token) >= 2:
            rich_text_list.append({
                "type": "text",
                "text": {"content": token[1:-1][:2000]},
                "annotations": {"code": True}
            })
        elif token.startswith("*") and token.endswith("*") and len(token) >= 2:
            rich_text_list.append({
                "type": "text",
                "text": {"content": token[1:-1][:2000]},
                "annotations": {"italic": True}
            })
        last_idx = end
        
    if last_idx < len(text):
        plain = text[last_idx:]
        if plain:
            rich_text_list.append({"type": "text", "text": {"content": plain[:2000]}})
            
    return rich_text_list if rich_text_list else [{"type": "text", "text": {"content": text[:2000]}}]

def markdown_to_notion_blocks(markdown_text: str) -> list:
    """마크다운 문자열을 Mermaid 시각화 다이어그램을 포함한 노션 API 블록 구조로 변환합니다."""
    blocks = []
    lines = markdown_text.strip().split("\n")
    i = 0
    
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        if not stripped:
            i += 1
            continue
            
        # 코드 블록 및 Mermaid 다이어그램 블록
        if stripped.startswith("```"):
            lang = stripped[3:].strip().lower() or "plain text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_content = "\n".join(code_lines)
            
            valid_languages = [
                "mermaid", "python", "javascript", "typescript", "java", "json",
                "html", "css", "bash", "shell", "markdown", "sql", "yaml", "dockerfile", "go"
            ]
            selected_lang = lang if lang in valid_languages else "plain text"
            
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": code_content[:2000]}}],
                    "language": selected_lang
                }
            })
            i += 1
            continue
            
        # Heading 1
        if stripped.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": parse_inline_rich_text(stripped[2:].strip())
                }
            })
        # Heading 2
        elif stripped.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": parse_inline_rich_text(stripped[3:].strip())
                }
            })
        # Heading 3
        elif stripped.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": parse_inline_rich_text(stripped[4:].strip())
                }
            })
        # 구분선
        elif stripped in ["---", "***", "___"]:
            blocks.append({
                "object": "block",
                "type": "divider",
                "divider": {}
            })
        # 인용구 / 콜아웃
        elif stripped.startswith("> "):
            blocks.append({
                "object": "block",
                "type": "callout",
                "callout": {
                    "rich_text": parse_inline_rich_text(stripped[2:].strip())
                }
            })
        # 불릿 목록
        elif stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": parse_inline_rich_text(stripped[2:].strip())
                }
            })
        # 번호 목록
        elif len(stripped) > 2 and stripped[0].isdigit() and stripped[1:3] in [". ", ") "]:
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": parse_inline_rich_text(stripped[3:].strip())
                }
            })
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": parse_inline_rich_text(stripped)
                }
            })
        i += 1
        
    return blocks

def create_notion_record(title: str, category: str, markdown_content: str, repo_name: str = None, tags: list = None) -> dict:
    """
    노션 데이터베이스에 분석 및 요약 내용을 새 페이지로 기록합니다.
    저장소(repo_name) 속성을 명시적으로 기록하여 레포지토리 단위 필터링/그룹화를 완벽 지원합니다.
    """
    if not NOTION_API_KEY:
        return {"ok": False, "error": "NOTION_API_KEY가 설정되지 않았습니다."}
    if not NOTION_DATABASE_ID:
        return {"ok": False, "error": "NOTION_DATABASE_ID가 설정되지 않았습니다."}

    # 기본 저장소 명칭 자동 감지
    if not repo_name:
        from tools.git_tool import get_repo_name
        repo_name = get_repo_name(".")
        
    # 제목에 저장소명이 없으면 접두어 추가: [repo_name] title
    formatted_title = title.strip()
    if repo_name and not formatted_title.startswith(f"[{repo_name}]"):
        # 기존 [Commit] 같은 태그 정리 후 [repo_name] [Commit] 형식으로
        formatted_title = f"[{repo_name}] {formatted_title}"

    db_info = get_database_info()
    if not db_info["ok"]:
        return db_info
        
    properties_schema = db_info["data"].get("properties", {})
    
    title_prop_name = None
    repo_prop_name = None
    category_prop_name = None
    date_prop_name = None
    tags_prop_name = None
    
    for name, prop in properties_schema.items():
        p_type = prop.get("type")
        if p_type == "title":
            title_prop_name = name
        elif p_type in ["select"] and name in ["저장소", "Repo", "Repository", "프로젝트"]:
            repo_prop_name = name
        elif p_type in ["select"] and name in ["분류", "Category", "유형"]:
            category_prop_name = name
        elif p_type in ["date"] and name in ["날짜", "작성일", "Date", "생성일"]:
            date_prop_name = name
        elif p_type in ["multi_select"] and name in ["태그", "Tags", "키워드"]:
            tags_prop_name = name

    if not title_prop_name:
        title_prop_name = "이름"

    page_properties = {
        title_prop_name: {
            "title": [{"type": "text", "text": {"content": formatted_title[:100]}}]
        }
    }
    
    if repo_prop_name and repo_name:
        page_properties[repo_prop_name] = {"select": {"name": str(repo_name)[:50]}}
        
    if category_prop_name and category:
        page_properties[category_prop_name] = {"select": {"name": category}}
        
    if date_prop_name:
        today_str = datetime.now().strftime("%Y-%m-%d")
        page_properties[date_prop_name] = {"date": {"start": today_str}}
        
    if tags_prop_name and tags:
        page_properties[tags_prop_name] = {
            "multi_select": [{"name": str(t)} for t in tags[:5]]
        }

    blocks = markdown_to_notion_blocks(markdown_content)
    
    payload = {
        "parent": {"database_id": NOTION_DATABASE_ID},
        "properties": page_properties,
        "children": blocks[:100]
    }

    res = send_notion_request("pages", method="POST", data=payload)
    if res["ok"]:
        page_url = res["data"].get("url", "")
        return {
            "ok": True, 
            "message": "노션에 성공적으로 기록되었습니다.",
            "page_url": page_url,
            "title": formatted_title,
            "repo_name": repo_name
        }
    return res

TOOL_NOTION_CREATE = {
    "name": "create_notion_record",
    "description": "분석하고 요약한 내용을 사용자의 노션(Notion) 데이터베이스에 새 페이지로 기록합니다.",
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "노션 페이지 제목 (예: 'Git 유틸리티 모듈 분석' 또는 '로그인 토큰 갱신 로직 리팩토링')"
            },
            "repo_name": {
                "type": "string",
                "description": "분석 대상 레포지토리 명칭 (예: 'makeNotionAgent', 'k8s-config-repo', 'jpa_practice')"
            },
            "category": {
                "type": "string",
                "enum": ["Commit Log", "Repo Analysis", "Code Summary", "Architecture", "Dev Note"],
                "description": "기록의 분류"
            },
            "markdown_content": {
                "type": "string",
                "description": "가독성을 극대화한 기술 문서 마크다운. 구분선(---), Mermaid 다이어그램(```mermaid), 핵심 구현사항, 그리고 반드시 '코드 리뷰 및 개선 보완점' 섹션을 포함하세요."
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "관련 태그 목록 (예: ['Git', 'Refactor', 'Review'])"
            }
        },
        "required": ["title", "category", "markdown_content", "repo_name"]
    }
}
