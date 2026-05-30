# ⚾ LNG선공사팀 발야구 대회

LNG선공사팀 체육행사 발야구 경기를 위한 실시간 응원 웹앱입니다.  
점수판, 응원 전광판, 깜짝 미션, 현장 사진 게시판을 제공합니다.

## 주요 기능

- **실시간 점수판** — 세기말 팀 vs 새천년 팀 점수 동기화 (4초 자동 갱신)
- **응원 전광판** — 팀별 응원 멘트 등록 및 TTS 자동 낭독
- **AI 응원 멘트 생성** — Upstage Solar AI가 상황에 맞는 응원 멘트 자동 생성
- **깜짝 미션** — 랜덤 미션 발동 (짐볼 찬스, 모세의 기적 등)
- **현장 사진 게시판** — 여러 장 동시 업로드 지원
- **관리자 모드** — 점수 조작, 미션 제어, 응원/사진 관리

## 팀 구성

| 팀 | 대상 | 색상 |
|---|---|---|
| 세기말 팀 | 99년생 + 홀수 출생 | 보라 |
| 새천년 팀 | 00년생 + 짝수 출생 | 하늘 |

## 시작하기

### 1. 가상환경 생성 및 활성화

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 2. 패키지 설치

```powershell
pip install -r requirements.txt
```

### 3. API 키 설정

`.streamlit/secrets.toml` 파일에 Upstage API 키를 입력합니다.

```toml
UPSTAGE_API_KEY = "your-upstage-api-key"
```

### 4. 앱 실행

```powershell
streamlit run app.py
```

## 관리자 모드

이름 입력란에 `admin` 을 입력하면 관리자 대시보드에 접속됩니다.  
점수 조작, 미션 발동/초기화, 응원 멘트 및 사진 관리를 할 수 있습니다.

## 기술 스택

- [Streamlit](https://streamlit.io/)
- [Pillow](https://pillow.readthedocs.io/)
- [streamlit-autorefresh](https://github.com/kmcgrady/streamlit-autorefresh)
- [Upstage Solar API](https://console.upstage.ai/) — AI 응원 멘트 생성

## 가상환경 생성

python -m venv venv

## 가상환경 활성화

.\venv\Scripts\Activate.ps1

## 패키지 설치

pip install -r requirements.txt

## API 키 설정

`.streamlit/secrets.toml` 파일에 Upstage API 키를 입력합니다.UPSTAGE_API_KEY = "your-upstage-api-key"

## 앱 실행

streamlit run app.py    