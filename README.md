# 📝 Notion DevLog AI Agent

> 코딩과 개발 과정을 분석하여 노션(Notion)에 레포지토리별로 자동 기록하고 시각화하는 로컬 AI 에이전트

## ✨ 주요 기능
- **Git 커밋 자동 분석**: 최근 커밋 변경사항(Diff) 분석 및 전문 기술 문서 포맷 노션 자동 기록
- **레포지토리 아키텍처 스캔**: 프로젝트 구조 및 핵심 모듈 분석 후 Mermaid 다이어그램으로 시각화
- **온디맨드 코드 요약**: 특정 소스 코드의 로직 및 데이터 흐름 정밀 분석
- **코드 리뷰 & 개선점 제안**: 엣지 케이스, 리팩토링 및 성능/보안 보완 권장사항 자동 생성
- **노션 DB 속성 자동 동기화**: `저장소`, `분류`, `작성일`, `태그` 컬럼 자동 구성

## 🚀 빠른 시작

### 1. 환경 변수 설정
`.env` 파일을 생성하고 발급받은 API 키를 입력합니다.
```env
NOTION_API_KEY=ntn_your_notion_api_key
NOTION_DATABASE_ID=your_notion_database_id
GEMINI_API_KEY=your_gemini_api_key
```

### 2. 실행 방법
```bash
# 대화형 CLI 모드 실행
python3 main.py

# 원클릭 단축 명령어
python3 main.py commit          # 최신 커밋 노션 기록
python3 main.py scan <경로>      # 레포지토리 아키텍처 분석 및 시각화
python3 main.py sum <파일명>     # 특정 코드 파일 요약
python3 main.py setup           # 노션 데이터베이스 속성 자동 세팅
```
