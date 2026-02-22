# Korea Weather MCP Server

[![smithery badge](https://smithery.ai/badge/@ohhan777/korea_weather)](https://smithery.ai/server/@ohhan777/korea_weather)

본 MCP 서버는 **기상청 단기예보 조회서비스 API**를 기반으로 동작하는 MCP 서버입니다.

## 소개

**Korea Weather MCP Server**는 기상청의 날씨 정보를 수집하여, MCP 프로토콜을 통해 Claude나 Cursor와 같은 MCP 클라이언트(Host)에 제공합니다.
이 서버는 기상 정보를 활용하는 다양한 응용 서비스에 쉽게 연동될 수 있습니다.

![MCP Example](assets/mcp_example.png)

## 주요 기능

- 기상청 단기예보 API 연동
- MCP 형식의 기상 정보 제공

## 설치 및 사용 방법

### Smithery를 이용한 설치

1. [data.go.kr](https://www.data.go.kr/)에서 **기상청 단기예보 API**를 신청하고 API 키를 발급받습니다.
2. 다음 명령어를 사용해 [Smithery](https://smithery.ai/server/@ohhan777/korea_weather)에서 서버를 설치하고 Claude Desktop에 등록합니다.
   설치 과정에서 API 키 입력을 요구하면 발급받은 키를 입력합니다.
   ```bash
   npx -y @smithery/cli mcp add ohhan777/korea_weather --client claude
   ```
3. Claude Desktop을 재시작하여 사용하면 됩니다.

### 로컬 개발 (Smithery CLI)

1. 소스코드를 클론하고 의존성을 설치합니다.
   ```bash
   git clone https://github.com/ohhan777/korea_weather.git
   cd korea_weather
   uv sync
   ```
2. 환경변수에 API 키를 설정합니다.
   ```bash
   export KOREA_WEATHER_API_KEY="발급받은_API_키"
   ```
3. 개발 서버를 실행합니다.
   ```bash
   # HTTP 모드로 실행 (http://localhost:8081)
   uv run smithery dev

   # 또는 Smithery Playground로 대화형 테스트
   uv run smithery playground
   ```

### GitHub에서 직접 설치하는 방법

1. [data.go.kr](https://www.data.go.kr/)에서 기상청 단기예보 API 활용 신청 후 API 키를 발급받습니다.
2. [github](https://github.com/ohhan777/korea_weather)에서 소스코드를 다운받아 실행해봅니다.
   ```
   git clone https://github.com/ohhan777/korea_weather.git
   cd korea_weather
   uv sync
   uv run korea_weather.py
   ```
3. MCP 클라이언트(Host)에 서버를 등록합니다.

   - **Claude Desktop**의 설정 파일은 보통 아래 경로에 위치합니다.
     `C:\Users\[사용자 이름]\AppData\Roaming\Claude\claude_desktop_config.json`
     (파일이 없다면 새로 생성)

   - **Cursor**의 경우: 상단의 톱니바퀴 아이콘 → **MCP → Add new global MCP server** 선택

   아래 예시와 같은 형식으로 설정 파일을 작성합니다. (디렉토리 경로와 API 키는 환경에 맞게 수정)

   ```json
   {
     "mcpServers": {
       "korea_weather": {
         "command": "uv",
         "args": [
           "--directory",
           "C:\\ai\\PyProjects\\korea_weather",
           "run",
           "korea_weather.py"
         ],
         "env": {
           "KOREA_WEATHER_API_KEY": "Input Your API Key Here!"
         }
       }
     }
   }
   ```

### Smithery에 배포하기

GitHub에 코드를 푸시한 후, [smithery.ai/new](https://smithery.ai/new)에서 GitHub 저장소를 연결하면 Smithery가 자동으로 서버를 빌드하고 호스팅합니다.

### 프롬프트 예제
```
>> 제주 국제 공항 현재 날씨를 알려줘.
>> 내일 오후에 서울 남대문에 놀러가려고 하는데 우산을 챙겨야할까?
>> 오늘 오후에 세차하기에 괜찮은 날씨일까?
```

## 의존성

`pyproject.toml` 참고

## 라이선스

본 프로젝트는 내부 시험용으로 개발되었으며, 별도의 라이선스 규정 없이 자유롭게 배포 및 수정이 가능합니다.

## 문의

개발자: 한국항공우주연구원 오한 (ohhan@kari.re.kr)


## 수정 이력
- 2026-02: Smithery v4 연동 — `smithery dev`/`smithery playground` 로컬 개발 지원, `create_server()` 팩토리 패턴 도입
- 2026-02: 서버 구조를 리팩터링하고(공통 API 요청 처리, 좌표 변환 캐시), MCP 도구 설명을 보강했습니다.
- 2026-02: `httpx`/`dotenv` 미설치 환경에서도 동작하도록 표준 라이브러리 기반 HTTP fallback 경로를 추가했습니다.
- 2026-02: 오프라인 환경에서도 실행 가능한 단위 테스트(`tests/test_korea_weather.py`)를 추가했습니다.
