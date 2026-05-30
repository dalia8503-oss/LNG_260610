import streamlit as st
import streamlit.components.v1 as components
import random
import hashlib
import base64
import copy
import threading
import time
import requests
from PIL import Image
import io
import zipfile
from streamlit_autorefresh import st_autorefresh

st.set_page_config(
    page_title="LNG선공사팀 Cheer-up day",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ════════════════════════════════════════════════════════════
# 공유 데이터 저장소 — st.cache_resource (모든 접속자 동기화)
# ════════════════════════════════════════════════════════════
@st.cache_resource
def _store() -> dict:
    return {
        "score_old": 0,
        "score_new": 0,
        "cheers":    [],   # list of {"team","name","msg"}
        "mission":   None,
        "photos":    [],   # list of {"orig_name","size","team","uploader","data":bytes}
        "broadcast":       None, # {"team","name","msg","bid":str} or None
        "broadcast_queue": [],   # 대기 중인 응원 멘트 방송
        "mission_flash":   None, # {"mission":str,"mid":str,"expires":float} or None
        "_lock":     threading.Lock(),
    }


def load_data() -> dict:
    s = _store()
    with s["_lock"]:
        if s["broadcast"] and time.time() > s["broadcast"].get("expires", 0):
            if s["broadcast_queue"]:
                _next = s["broadcast_queue"].pop(0)
                s["broadcast"] = {**_next, "bid": hashlib.md5(str(random.random()).encode()).hexdigest()[:8], "expires": time.time() + 9}
            else:
                s["broadcast"] = None
        if s["mission_flash"] and time.time() > s["mission_flash"].get("expires", 0):
            s["mission_flash"] = None
        return {
            "score_old": s["score_old"],
            "score_new": s["score_new"],
            "cheers":    copy.deepcopy(s["cheers"]),
            "mission":   s["mission"],
            "photos":    list(s["photos"]),   # 사진 bytes는 참조 공유
            "broadcast":       s["broadcast"],
            "broadcast_queue": list(s["broadcast_queue"]),
            "mission_flash":   s["mission_flash"],
        }


def save_data(data: dict):
    s = _store()
    with s["_lock"]:
        for k in ("score_old", "score_new", "cheers", "mission", "photos", "broadcast", "broadcast_queue", "mission_flash"):
            s[k] = data[k]


# ── 세션 초기화 (사용자별 로컬 데이터만) ──────────────────────
for _k, _v in {"user_name": "", "user_team": "", "join_pick": "", "cheer_draft": ""}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── URL 쿼리 파라미터로 로그인 상태 복원 ──────────────────────
if not st.session_state.user_name:
    _qp_name = st.query_params.get("name", "")
    _qp_team = st.query_params.get("team", "")
    if _qp_name and _qp_team:
        st.session_state.user_name = _qp_name
        st.session_state.user_team = _qp_team

MISSIONS = [
    "🟣 짐볼 찬스!",
    "🌊 모세의 기적!",
    "💧 물병 세우고 달리기!",
    "📸 단체 포즈 미션!",
]


def generate_ai_cheer(team: str, score_old: int, score_new: int, api_key: str) -> str:
    if score_old > score_new:
        situation = f"세기말 팀이 {score_old}:{score_new}으로 리드 중"
    elif score_new > score_old:
        situation = f"새천년 팀이 {score_new}:{score_old}으로 리드 중"
    else:
        situation = f"{score_old}:{score_new} 동점 팽팽한 접전"

    prompt = (
        f"지금 회사 체육행사 발야구 경기가 한창입니다.\n"
        f"현재 상황: {situation}\n"
        f"내 팀: {team} 팀\n\n"
        f"{team} 팀을 응원하는 유쾌하고 텐션 높은 멘트를 딱 1개만 만들어줘.\n"
        f"- 세기말 팀이면 레트로 감성, 새천년 팀이면 최신 밈(럭키비키 등)을 살짝 반영할 것\n"
        f"- 25자 이내로 짧고 강렬하게\n"
        f"- 이모지 1~2개 포함\n"
        f"- 설명이나 따옴표 없이 멘트 텍스트만 출력"
    )
    resp = requests.post(
        "https://api.upstage.ai/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "solar-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 80,
            "temperature": 1.1,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip().strip('"').strip("'")




# ── 전역 스타일 ──────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Noto+Sans+KR:wght@400;700&display=swap');
  html, body, [class*="css"] { font-family: 'Noto Sans KR', 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', sans-serif; }

  /* ── 다크 배경 별빛 ── */
  .stApp { background: radial-gradient(ellipse at 20% 20%, #1a0033 0%, #0a0010 60%, #000510 100%) !important; }

  /* ── 입장 카드 ── */
  .join-wrap { max-width: 680px; margin: 0 auto; padding: 20px 12px 40px; }
  .join-title { font-family: 'Black Han Sans', sans-serif; font-size: clamp(1.8rem, 6vw, 3rem); color: #ffffff; text-align: center; text-shadow: 0 0 24px rgba(255,255,255,0.35); margin-bottom: 4px; }
  .join-sub { text-align: center; color: #888; font-size: 0.9rem; letter-spacing: 2px; margin-bottom: 32px; }
  .team-join-card { border-radius: 20px; padding: 28px 16px 20px; text-align: center; transition: transform 0.15s ease; margin-bottom: 8px; }
  .team-join-card:hover { transform: translateY(-3px); }
  .card-old-join { background: linear-gradient(145deg, #33001a, #660033); border: 3px solid #ff4499; }
  .card-old-join.selected { border-color: #ff99cc; box-shadow: 0 0 32px #ff449988, 0 0 0 4px #ff449944; }
  .card-new-join { background: linear-gradient(145deg, #001a33, #003366); border: 3px solid #66ccff; }
  .card-new-join.selected { border-color: #aaddff; box-shadow: 0 0 32px #66ccff88, 0 0 0 4px #66ccff44; }
  .card-team-name { font-family: 'Black Han Sans', sans-serif; font-size: clamp(1.5rem, 5vw, 2.2rem); letter-spacing: 4px; margin-bottom: 6px; }
  .card-team-sub  { font-size: 0.85rem; letter-spacing: 2px; opacity: 0.75; margin-bottom: 10px; }
  .card-check     { font-size: 2rem; margin-top: 8px; min-height: 2.4rem; }

  /* ── 점수 카드 공통 ── */
  .score-card {
    border-radius: 24px;
    padding: 28px 20px 20px;
    text-align: center;
    position: relative;
    overflow: hidden;
  }
  .score-card::before {
    content: '';
    position: absolute; inset: 0;
    border-radius: 24px;
    padding: 3px;
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    animation: borderSpin 3s linear infinite;
  }

  /* ── 세기말 팀 (핑크) ── */
  .card-old {
    background: linear-gradient(160deg, #33001a 0%, #660033 50%, #33001a 100%);
    border: 2px solid transparent;
    box-shadow: 0 0 40px #ff449966, 0 0 80px #ff449922, inset 0 0 30px #ff449911;
    animation: glowOld 2.4s ease-in-out infinite;
  }
  .card-old::before {
    background: conic-gradient(from 0deg, #ff4499, #ff99cc, #ffccee, #ff4499);
  }
  .card-old .team-name {
    font-family: 'Black Han Sans', sans-serif;
    font-size: clamp(1.4rem, 4vw, 2rem);
    color: #ff99cc;
    text-shadow: 0 0 10px #ff4499cc, 0 0 20px #ff449988, 0 0 40px #ff449944;
    letter-spacing: 4px;
    animation: flickerOld 4s ease-in-out infinite;
  }
  .card-old .score-num {
    font-family: 'Black Han Sans', sans-serif;
    font-size: clamp(4rem, 14vw, 8rem);
    color: #ffffff;
    text-shadow:
      0 0 10px #ff99cc,
      0 0 20px #ff4499dd,
      0 0 40px #ff4499aa,
      0 0 80px #ff449966,
      0 4px 0 #660033;
    line-height: 1.1;
    animation: scorePulseOld 2s ease-in-out infinite;
  }
  .card-old .sub-text { color: #ff4499; font-size: 0.85rem; letter-spacing: 2px; opacity: 0.85; }

  /* ── 새천년 팀 (하늘) ── */
  .card-new {
    background: linear-gradient(160deg, #001a33 0%, #003366 50%, #001a33 100%);
    border: 2px solid transparent;
    box-shadow: 0 0 40px #66ccff66, 0 0 80px #66ccff22, inset 0 0 30px #66ccff11;
    animation: glowNew 2.4s ease-in-out infinite;
  }
  .card-new::before {
    background: conic-gradient(from 0deg, #66ccff, #aaddff, #66ffff, #66ccff);
  }
  .card-new .team-name {
    font-family: 'Black Han Sans', sans-serif;
    font-size: clamp(1.4rem, 4vw, 2rem);
    color: #aaddff;
    text-shadow: 0 0 10px #66ccffcc, 0 0 20px #66ccff88, 0 0 40px #66ccff44;
    letter-spacing: 4px;
    animation: flickerNew 4s ease-in-out infinite;
  }
  .card-new .score-num {
    font-family: 'Black Han Sans', sans-serif;
    font-size: clamp(4rem, 14vw, 8rem);
    color: #ffffff;
    text-shadow:
      0 0 10px #aaddff,
      0 0 20px #66ccffdd,
      0 0 40px #66ccffaa,
      0 0 80px #66ccff66,
      0 4px 0 #003366;
    line-height: 1.1;
    animation: scorePulseNew 2s ease-in-out infinite;
  }
  .card-new .sub-text { color: #66ccff; font-size: 0.85rem; letter-spacing: 2px; opacity: 0.85; }

  /* ── VS 배지 ── */
  .vs-badge {
    font-family: 'Black Han Sans', sans-serif;
    font-size: clamp(1.8rem, 5vw, 3rem);
    color: #ffffff;
    text-shadow: 0 0 20px #fff, 0 0 40px #ffdd0088;
    text-align: center;
    padding-top: 40px;
    animation: vsFlash 1.6s ease-in-out infinite;
  }

  /* ── 키프레임 ── */
  @keyframes glowOld {
    0%, 100% { box-shadow: 0 0 40px #ff449966, 0 0 80px #ff449922, inset 0 0 30px #ff449911; }
    50%       { box-shadow: 0 0 60px #ff4499aa, 0 0 120px #ff449944, inset 0 0 50px #ff449922; }
  }
  @keyframes glowNew {
    0%, 100% { box-shadow: 0 0 40px #66ccff66, 0 0 80px #66ccff22, inset 0 0 30px #66ccff11; }
    50%       { box-shadow: 0 0 60px #66ccffaa, 0 0 120px #66ccff44, inset 0 0 50px #66ccff22; }
  }
  @keyframes scorePulseOld {
    0%, 100% { text-shadow: 0 0 10px #ff99cc, 0 0 20px #ff4499dd, 0 0 40px #ff4499aa, 0 0 80px #ff449966, 0 4px 0 #660033; }
    50%       { text-shadow: 0 0 20px #ffffff, 0 0 40px #ff99cc,   0 0 80px #ff4499,   0 0 120px #ff4499aa, 0 4px 0 #660033; }
  }
  @keyframes scorePulseNew {
    0%, 100% { text-shadow: 0 0 10px #aaddff, 0 0 20px #66ccffdd, 0 0 40px #66ccffaa, 0 0 80px #66ccff66, 0 4px 0 #003366; }
    50%       { text-shadow: 0 0 20px #ffffff, 0 0 40px #aaddff,   0 0 80px #66ccff,   0 0 120px #66ccffaa, 0 4px 0 #003366; }
  }
  @keyframes flickerOld {
    0%,  19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; }
    20%, 24%, 55% { opacity: 0.7; }
  }
  @keyframes flickerNew {
    0%,  32%, 34%, 36%, 38%, 67%, 69%, 100% { opacity: 1; }
    33%, 37%, 68% { opacity: 0.7; }
  }
  @keyframes vsFlash {
    0%, 100% { opacity: 1; transform: scale(1); }
    50%       { opacity: 0.6; transform: scale(1.08); }
  }
  @keyframes borderSpin {
    from { --angle: 0deg; }
    to   { --angle: 360deg; }
  }
  @property --angle { syntax: '<angle>'; initial-value: 0deg; inherits: false; }

  /* ── 미션 박스 ── */
  .mission-box {
    background: linear-gradient(135deg, #1a0033, #330066);
    border: 3px solid #cc00ff;
    border-radius: 20px; padding: 30px; text-align: center;
    box-shadow: 0 0 40px #cc00ff66, 0 0 80px #cc00ff22;
    animation: missionGlow 1.5s ease-in-out infinite;
    margin-top: 16px;
  }
  .mission-text {
    font-family: 'Black Han Sans', sans-serif;
    font-size: clamp(1.8rem, 6vw, 3.5rem);
    color: #ff66ff;
    text-shadow: 0 0 20px #ff00ffcc, 0 0 40px #ff00ff88;
    animation: pulse 1.2s ease-in-out infinite;
  }
  @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.8; transform: scale(1.04); } }
  @keyframes missionGlow {
    0%, 100% { box-shadow: 0 0 40px #cc00ff66, 0 0 80px #cc00ff22; border-color: #cc00ff; }
    50%       { box-shadow: 0 0 70px #ff00ffaa, 0 0 140px #cc00ff44; border-color: #ff66ff; }
  }

  /* ── 응원 전광판 ── */
  .cheer-item { border-radius: 10px; padding: 12px 16px; margin-bottom: 10px; font-size: clamp(1rem, 3.2vw, 1.5rem); color: #ffffff; font-weight: 700; word-break: break-all; display: flex; align-items: flex-start; gap: 10px; }
  .cheer-item.latest { font-size: clamp(1.3rem, 4vw, 2rem); }
  .cheer-badge-old { background: #ff4499; color: #33001a; border-radius: 6px; padding: 2px 8px; font-size: 0.78rem; white-space: nowrap; font-weight: 900; letter-spacing: 1px; flex-shrink: 0; margin-top: 3px; }
  .cheer-badge-new { background: #66ccff; color: #001a33; border-radius: 6px; padding: 2px 8px; font-size: 0.78rem; white-space: nowrap; font-weight: 900; letter-spacing: 1px; flex-shrink: 0; margin-top: 3px; }
  .cheer-bg-old { background: rgba(255,68,153,0.12); border-left: 5px solid #ff4499; }
  .cheer-bg-new { background: rgba(102,204,255,0.10); border-left: 5px solid #66ccff; }

  /* ── 공통 버튼/탭 ── */
  button[data-baseweb="tab"] { font-size: 1.1rem !important; font-weight: 700 !important; }
  div.stButton > button { width: 100%; border-radius: 12px; font-weight: 700; font-size: 1rem; padding: 10px 0; border: none; transition: all 0.15s ease; }
  div.stButton > button:active { transform: scale(0.97); }
  hr { border-color: rgba(255,255,255,0.1); margin: 24px 0; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
# JOIN PAGE
# ════════════════════════════════════════════════════════════
if not st.session_state.user_name:

    st.markdown('<div class="join-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="join-title"><span style="color:#00ccff;text-shadow:0 0 10px #00ccff99,0 0 28px #00ccff44;">LNG선공사팀</span><br><span style="font-size:clamp(1.4rem,5vw,2.4rem);color:#ff8800;text-shadow:0 0 10px #ff880099,0 0 28px #ff880044;">Cheer-up day</span></div>', unsafe_allow_html=True)
    st.markdown('<div class="join-title" style="font-size:clamp(1.2rem,4vw,2rem);margin-top:-8px;">⚾ 발야구 대결 ⚾</div>', unsafe_allow_html=True)
    st.markdown('<div class="join-sub">팀을 선택하고 이름을 입력해 입장하세요</div>', unsafe_allow_html=True)

    picked_old = st.session_state.join_pick == "세기말"
    picked_new = st.session_state.join_pick == "새천년"

    _tsel_css = """<style>
div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"] div[data-testid="stButton"] button {
    min-height: 160px !important; border-radius: 22px !important; padding: 24px 16px !important;
    font-size: 1rem !important; line-height: 1.8 !important; transition: all 0.25s ease !important;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"] div[data-testid="stButton"] button p {
    white-space: pre-line !important; line-height: 1.8 !important; font-size: 1rem !important; margin: 0 !important;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:first-of-type div[data-testid="stButton"] button {
    background: linear-gradient(135deg,#2a0a1f 60%,#4a1040) !important;
    border: 2px solid #ff4499 !important; color: #ffaacc !important; box-shadow: 0 0 30px #ff449944 !important;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:last-of-type div[data-testid="stButton"] button {
    background: linear-gradient(135deg,#0a1a2f 60%,#103050) !important;
    border: 2px solid #66ccff !important; color: #aaddff !important; box-shadow: 0 0 30px #66ccff44 !important;
}"""
    if picked_old:
        _tsel_css += """
div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:first-of-type div[data-testid="stButton"] button {
    border: 4px solid #ffffff !important; filter: brightness(1.25) !important;
    box-shadow: 0 0 0 3px #ffffff66, 0 0 60px #ff4499cc !important;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:last-of-type div[data-testid="stButton"] button {
    opacity: 0.2 !important; filter: grayscale(0.5) brightness(0.5) !important;
}"""
    elif picked_new:
        _tsel_css += """
div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:first-of-type div[data-testid="stButton"] button {
    opacity: 0.2 !important; filter: grayscale(0.5) brightness(0.5) !important;
}
div[data-testid="stHorizontalBlock"] div[data-testid="stColumn"]:last-of-type div[data-testid="stButton"] button {
    border: 4px solid #ffffff !important; filter: brightness(1.25) !important;
    box-shadow: 0 0 0 3px #ffffff66, 0 0 60px #66ccffcc !important;
}"""
    st.markdown(_tsel_css + "</style>", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        _lbl_old = ("✅ **선택됨**  \n" if picked_old else "") + "99년생 + 홀수 출생  \n**세기말 팀**  \n🩷"
        if st.button(_lbl_old, key="btn_pick_old", use_container_width=True):
            st.session_state.join_pick = '세기말'
            st.rerun()
    with col_b:
        _lbl_new = ("✅ **선택됨**  \n" if picked_new else "") + "00년생 + 짝수 출생  \n**새천년 팀**  \n🩵"
        if st.button(_lbl_new, key="btn_pick_new", use_container_width=True):
            st.session_state.join_pick = '새천년'
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    with st.form("join_form"):
        name_input = st.text_input("이름", placeholder="이름을 입력하세요", label_visibility="collapsed")
        if st.form_submit_button("🚀 입장하기!", use_container_width=True):
            name_val = name_input.strip()
            if name_val.lower() == "admin":
                st.session_state.user_name = "관리자"
                st.session_state.user_team = "admin"
                st.query_params["name"] = "관리자"
                st.query_params["team"] = "admin"
                st.rerun()
            elif not st.session_state.join_pick:
                st.error("먼저 팀을 선택해 주세요!")
            elif not name_val:
                st.error("이름을 입력해 주세요!")
            else:
                st.session_state.user_name = name_val
                st.session_state.user_team = st.session_state.join_pick
                st.query_params["name"] = name_val
                st.query_params["team"] = st.session_state.join_pick
                st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()


# ════════════════════════════════════════════════════════════
# ADMIN DASHBOARD
# ════════════════════════════════════════════════════════════
if st.session_state.user_team == "admin":
    st_autorefresh(interval=4000, key="admin_refresh")

    st.markdown("""
    <div style="text-align:center; padding:12px 0 4px;">
      <span style="font-family:'Black Han Sans',sans-serif; font-size:clamp(1.6rem,5vw,2.8rem);
                   color:#00ccff; text-shadow:0 0 10px #00ccff99,0 0 28px #00ccff44;">
        LNG선공사팀
      </span><br>
      <span style="font-family:'Black Han Sans',sans-serif; font-size:clamp(1.4rem,4.5vw,2.4rem);
                   color:#ff8800; text-shadow:0 0 10px #ff880099,0 0 28px #ff880044;">
        Cheer-up day
      </span><br>
      <span style="font-family:'Black Han Sans',sans-serif; font-size:clamp(1rem,3vw,1.8rem);
                   color:#ffffff; text-shadow:0 0 16px rgba(255,255,255,0.3);">
        ⚾ 발야구 대결 ⚾
      </span><br><br>
      <span style="background:#cc0000; color:#fff; font-weight:900; border-radius:8px;
                   padding:4px 18px; font-size:1rem; letter-spacing:3px; box-shadow:0 0 16px #cc000088;">
        🔑 관리자 모드
      </span>
    </div>""", unsafe_allow_html=True)

    _, col_adm_exit = st.columns([9, 1])
    with col_adm_exit:
        if st.button("퇴장", key="admin_exit"):
            st.session_state.user_name = ""
            st.session_state.user_team = ""
            st.query_params.clear()
            st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    data = load_data()
    atab1, atab2, atab3, atab4 = st.tabs(["📊 전체 현황", "🎮 게임 제어", "📣 응원 관리", "📸 사진 관리"])

    with atab1:
        ac1, avc, ac2 = st.columns([5, 1, 5])
        with ac1:
            st.markdown(f'<div class="score-card card-old"><div class="sub-text">99년생 + 홀수 출생</div><div class="team-name">세기말 팀</div><div class="score-num">{data["score_old"]}</div><div class="sub-text">점</div></div>', unsafe_allow_html=True)
        with avc:
            st.markdown('<div class="vs-badge">VS</div>', unsafe_allow_html=True)
        with ac2:
            st.markdown(f'<div class="score-card card-new"><div class="sub-text">00년생 + 짝수 출생</div><div class="team-name">새천년 팀</div><div class="score-num">{data["score_new"]}</div><div class="sub-text">점</div></div>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("세기말 팀 점수", f"{data['score_old']}점")
        m2.metric("새천년 팀 점수", f"{data['score_new']}점")
        m3.metric("응원 멘트", f"{len(data['cheers'])}개")
        m4.metric("업로드 사진", f"{len(data['photos'])}장")
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**현재 미션**")
        if data["mission"]:
            st.markdown(f'<div class="mission-box" style="padding:16px 24px;"><div class="mission-text" style="font-size:clamp(1.4rem,4vw,2.4rem);">{data["mission"]}</div></div>', unsafe_allow_html=True)
        else:
            st.info("현재 발동된 미션 없음")

    with atab2:
        st.markdown("#### 🏟️ 점수 조작")
        data = load_data()
        gc1, gvs, gc2 = st.columns([5, 1, 5])
        with gc1:
            st.markdown(f'<div class="score-card card-old" style="padding:16px;"><div class="team-name">세기말 팀</div><div class="score-num">{data["score_old"]}</div></div>', unsafe_allow_html=True)
            st.markdown("")
            gb1, gb2 = st.columns(2)
            with gb1:
                if st.button("➕ +1점", key="adm_old_up", use_container_width=True):
                    d = load_data(); d["score_old"] += 1; save_data(d); st.rerun()
            with gb2:
                if st.button("➖ -1점", key="adm_old_dn", use_container_width=True, disabled=data["score_old"] <= 0):
                    d = load_data(); d["score_old"] -= 1; save_data(d); st.rerun()
        with gvs:
            st.markdown('<div class="vs-badge" style="padding-top:20px;">VS</div>', unsafe_allow_html=True)
        with gc2:
            st.markdown(f'<div class="score-card card-new" style="padding:16px;"><div class="team-name">새천년 팀</div><div class="score-num">{data["score_new"]}</div></div>', unsafe_allow_html=True)
            st.markdown("")
            gb3, gb4 = st.columns(2)
            with gb3:
                if st.button("➕ +1점", key="adm_new_up", use_container_width=True):
                    d = load_data(); d["score_new"] += 1; save_data(d); st.rerun()
            with gb4:
                if st.button("➖ -1점", key="adm_new_dn", use_container_width=True, disabled=data["score_new"] <= 0):
                    d = load_data(); d["score_new"] -= 1; save_data(d); st.rerun()
        _, col_adm_reset, _ = st.columns([3, 2, 3])
        with col_adm_reset:
            if st.button("🔄 점수 초기화", key="adm_reset", use_container_width=True):
                d = load_data(); d["score_old"] = 0; d["score_new"] = 0; save_data(d); st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("#### 🎲 미션 제어")
        _m1, _m2 = st.columns(2)
        _m3, _m4 = st.columns(2)
        for _col, _mission_btn, _btn_key in [
            (_m1, MISSIONS[0], "adm_m0"),
            (_m2, MISSIONS[1], "adm_m1"),
            (_m3, MISSIONS[2], "adm_m2"),
            (_m4, MISSIONS[3], "adm_m3"),
        ]:
            with _col:
                if st.button(_mission_btn, key=_btn_key, use_container_width=True):
                    d = load_data()
                    d["mission"] = _mission_btn
                    d["mission_flash"] = {"mission": _mission_btn, "mid": hashlib.md5(str(random.random()).encode()).hexdigest()[:8], "expires": time.time() + 11}
                    save_data(d)
                    st.balloons(); st.rerun()
        data = load_data()
        if data["mission"]:
            st.markdown(f'<div class="mission-box" style="padding:20px;"><div class="mission-text" style="font-size:clamp(1.4rem,4vw,2.4rem);">{data["mission"]}</div></div>', unsafe_allow_html=True)
        _, col_adm_mc, _ = st.columns([3, 2, 3])
        with col_adm_mc:
            if st.button("❌ 미션 초기화", key="adm_mission_clr", use_container_width=True):
                d = load_data(); d["mission"] = None; save_data(d); st.rerun()

    with atab3:
        data = load_data()

        st.markdown("#### 📢 공지 방송")
        _admin_bc_msg = st.text_input("공지 내용", placeholder="전체 공지 내용을 입력하세요", key="admin_bc_input", label_visibility="collapsed")
        _, _col_bc_btn, _ = st.columns([2, 3, 2])
        with _col_bc_btn:
            if st.button("📡 전광판 방송", key="admin_bc_send", use_container_width=True):
                if _admin_bc_msg.strip():
                    d = load_data()
                    d["broadcast"] = {
                        "team": "공지",
                        "name": "관리자",
                        "msg":  _admin_bc_msg.strip(),
                        "bid":  hashlib.md5(str(random.random()).encode()).hexdigest()[:8],
                        "expires": time.time() + 9,
                    }
                    save_data(d); st.rerun()
                else:
                    st.warning("공지 내용을 입력해 주세요.")

        st.markdown("<hr>", unsafe_allow_html=True)

        if data.get("broadcast"):
            bc = data["broadcast"]
            bc_team = bc.get("team", "")
            bc_color = "#ff4499" if bc_team == "세기말" else ("#ffdd00" if bc_team == "공지" else "#66ccff")
            bc_label = f"📢 공지 — {bc.get('msg','')}" if bc_team == "공지" else f"{bc_team} 팀 {bc.get('name','')} — {bc.get('msg','')}"
            st.markdown(
                f'<div style="background:rgba(255,100,0,0.15);border:2px solid #ff6600;border-radius:12px;'
                f'padding:12px 16px;margin-bottom:12px;">'
                f'<span style="color:#ff9900;font-weight:900;">📡 전광판 방송 중&nbsp;&nbsp;</span>'
                f'<span style="color:{bc_color};font-weight:700;">{bc_label}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            _, col_adm_bc_clr, _ = st.columns([3, 2, 3])
            with col_adm_bc_clr:
                if st.button("📡 방송 종료", key="adm_broadcast_clr", use_container_width=True):
                    d = load_data(); d["broadcast"] = None; save_data(d); st.rerun()
            st.markdown("")

        st.markdown(f"#### 📣 응원 멘트 목록 ({len(data['cheers'])}개)")
        if data["cheers"]:
            _, col_adm_ca, _ = st.columns([3, 2, 3])
            with col_adm_ca:
                if st.button("🗑️ 전체 삭제", key="adm_cheer_all", use_container_width=True):
                    d = load_data(); d["cheers"] = []; save_data(d); st.rerun()
            st.markdown("")
            for idx, item in enumerate(data["cheers"]):
                team = item.get("team", "")
                badge_cls = "cheer-badge-old" if team == "세기말" else "cheer-badge-new"
                bg_cls    = "cheer-bg-old"    if team == "세기말" else "cheer-bg-new"
                row_l, row_bc, row_r = st.columns([8, 1, 1])
                with row_l:
                    st.markdown(f'<div class="cheer-item {bg_cls}" style="font-size:1rem;"><span class="{badge_cls}">{team} 팀</span><span><b>{item.get("name","")}</b>&nbsp; {item.get("msg","")}</span></div>', unsafe_allow_html=True)
                with row_bc:
                    if st.button("📢", key=f"adm_broadcast_{idx}", use_container_width=True, help="전광판 방송"):
                        d = load_data()
                        d["broadcast"] = {**item, "bid": hashlib.md5(str(random.random()).encode()).hexdigest()[:8], "expires": time.time() + 9}
                        save_data(d); st.rerun()
                with row_r:
                    if st.button("✕", key=f"adm_del_cheer_{idx}", use_container_width=True):
                        d = load_data(); d["cheers"].pop(idx); save_data(d); st.rerun()
        else:
            st.info("등록된 응원 멘트가 없습니다.")

    with atab4:
        data = load_data()
        st.markdown(f"#### 📸 업로드 사진 목록 ({len(data['photos'])}장)")
        if data["photos"]:
            _, col_adm_dl, col_adm_pa, _ = st.columns([2, 2, 2, 2])
            with col_adm_dl:
                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for i, p in enumerate(data["photos"]):
                        fname = p.get("orig_name") or f"photo_{i+1}.jpg"
                        zf.writestr(fname, p["data"])
                zip_buf.seek(0)
                st.download_button("⬇️ 전체 다운로드", data=zip_buf, file_name="발야구_현장사진.zip", mime="application/zip", use_container_width=True, key="adm_photo_dl")
            with col_adm_pa:
                if st.button("🗑️ 전체 삭제", key="adm_photo_all", use_container_width=True):
                    d = load_data(); d["photos"] = []; save_data(d); st.rerun()
            st.markdown("")
            cols_per_row = 3
            photo_rows = [list(enumerate(data["photos"]))[i : i + cols_per_row]
                          for i in range(0, len(data["photos"]), cols_per_row)]
            for row in photo_rows:
                p_cols = st.columns(cols_per_row)
                for col, (idx, photo) in zip(p_cols, row):
                    with col:
                        cap = f"{photo.get('team','')} 팀 · {photo.get('uploader','')}"
                        st.image(Image.open(io.BytesIO(photo["data"])), use_container_width=True, caption=cap)
                        if st.button("🗑️ 삭제", key=f"adm_del_photo_{idx}", use_container_width=True):
                            d = load_data(); d["photos"].pop(idx); save_data(d); st.rerun()
        else:
            st.info("업로드된 사진이 없습니다.")

    st.markdown('<div style="text-align:center;color:#444;font-size:0.8rem;margin-top:48px;padding-bottom:16px;">⚾ LNG선공사팀 발야구 대회 | 관리자 모드 ⚾</div>', unsafe_allow_html=True)
    st.stop()


# ════════════════════════════════════════════════════════════
# 일반 참가자 뷰 — 4초마다 자동 갱신
# ════════════════════════════════════════════════════════════
st_autorefresh(interval=4000, key="autorefresh")

is_old      = st.session_state.user_team == "세기말"
badge_bg    = "#ff4499" if is_old else "#66ccff"
badge_color = "#33001a" if is_old else "#001a33"

st.markdown(f"""
<div style="text-align:center; padding: 12px 0 4px;">
  <span style="font-family:'Black Han Sans',sans-serif; font-size:clamp(1.6rem,5vw,2.8rem);
               color:#00ccff; text-shadow:0 0 10px #00ccff99,0 0 28px #00ccff44;">
    LNG선공사팀
  </span><br>
  <span style="font-family:'Black Han Sans',sans-serif; font-size:clamp(1.4rem,4.5vw,2.4rem);
               color:#ff8800; text-shadow:0 0 10px #ff880099,0 0 28px #ff880044;">
    Cheer-up day
  </span><br>
  <span style="font-family:'Black Han Sans',sans-serif; font-size:clamp(0.9rem,2.5vw,1.5rem);
               color:#ffffff; text-shadow:0 0 14px rgba(255,255,255,0.3);">
    ⚾ 발야구 대결 ⚾
  </span><br>
  <span style="color:#aaaaaa; font-size:0.9rem; letter-spacing:2px;">세기말 팀 🆚 새천년 팀</span>
  &nbsp;&nbsp;
  <span style="background:{badge_bg}; color:{badge_color}; font-weight:900; border-radius:8px;
               padding:3px 12px; font-size:0.85rem; letter-spacing:1px;">
    {st.session_state.user_team} 팀 · {st.session_state.user_name}
  </span>
</div>
""", unsafe_allow_html=True)

_, col_exit = st.columns([8, 1])
with col_exit:
    if st.button("퇴장", key="exit_btn"):
        st.session_state.user_name = ""
        st.session_state.user_team = ""
        st.session_state.join_pick = ""
        st.query_params.clear()
        st.rerun()

st.markdown("<hr>", unsafe_allow_html=True)

# ── 전광판 방송 오버레이 ──────────────────────────────────────
_bdata = load_data()
if _bdata.get("broadcast"):
    _bc        = _bdata["broadcast"]
    _bc_team   = _bc.get("team", "")
    _bc_name   = _bc.get("name", "").replace("'", "\\'")
    _bc_msg    = _bc.get("msg",  "").replace("'", "\\'")
    _bc_id     = _bc.get("bid",  "x")
    _bc_color  = "#ff4499" if _bc_team == "세기말" else ("#ffdd00" if _bc_team == "공지" else "#66ccff")
    _bc_bg     = "linear-gradient(135deg,#33001a,#660033)" if _bc_team == "세기말" else ("linear-gradient(135deg,#332200,#554400)" if _bc_team == "공지" else "linear-gradient(135deg,#001a33,#003366)")
    _bc_label  = "📢 공지" if _bc_team == "공지" else f"{_bc_team} 팀 · {_bc.get('name','')}"
    components.html(f"""
<script>
(function() {{
    var bid      = '{_bc_id}';
    var keyShown = 'bcast_'      + bid;
    var keyDone  = 'bcast_done_' + bid;
    var keyTime  = 'bcast_t_'    + bid;

    var s = null;
    try {{ s = parent.sessionStorage; }} catch(e) {{}}
    if (!s) {{ try {{ s = sessionStorage; }} catch(e) {{}} }}

    var doc2 = null;
    try {{ doc2 = parent.document; }} catch(e) {{}}
    if (!doc2) doc2 = document;

    if (s && s.getItem(keyDone)) return;

    var cleanup = function() {{
        if (s && s.getItem(keyDone)) return;
        if (s) s.setItem(keyDone, '1');
        var el  = doc2.getElementById('bov_' + bid);
        if (el  && el.parentNode)  el.parentNode.removeChild(el);
        var sel = doc2.getElementById('bst_' + bid);
        if (sel && sel.parentNode) sel.parentNode.removeChild(sel);
        var tabs = doc2.querySelectorAll('button[data-baseweb="tab"]');
        if (tabs && tabs.length > 0) tabs[0].click();
    }};

    if (s && s.getItem(keyShown)) {{
        var t = parseInt(s.getItem(keyTime) || '0');
        if (t && Date.now() - t >= 8500) {{ cleanup(); }}
        return;
    }}

    if (s) {{
        s.setItem(keyShown, '1');
        s.setItem(keyTime, Date.now().toString());
    }}
    if (doc2.getElementById('bov_' + bid)) return;

    var stEl = doc2.createElement('style');
    stEl.id = 'bst_' + bid;
    stEl.textContent =
        '@keyframes bshow_' + bid + ' {{ 0% {{ opacity:0;transform:scale(0.88); }} 12% {{ opacity:1;transform:scale(1); }} 82% {{ opacity:1;transform:scale(1); }} 100% {{ opacity:0;transform:scale(0.95); }} }}' +
        '@keyframes bpulse_' + bid + ' {{ 0%,100% {{ transform:scale(1); }} 50% {{ transform:scale(1.04); }} }}';
    doc2.head.appendChild(stEl);

    var ov = doc2.createElement('div');
    ov.id = 'bov_' + bid;
    ov.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:99999;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none;';
    ov.style.background = '{_bc_bg}';
    ov.style.animation  = 'bshow_' + bid + ' 8s ease-in-out 1 forwards';

    var badge = doc2.createElement('div');
    badge.textContent = '{_bc_label}';
    badge.style.cssText = 'color:#fff;border:3px solid {_bc_color};border-radius:10px;padding:8px 28px;font-size:clamp(1rem,3.5vw,2rem);font-weight:900;margin-bottom:36px;background:rgba(0,0,0,0.4);letter-spacing:2px;';
    badge.style.fontFamily = "'Noto Sans KR', sans-serif";
    badge.style.boxShadow  = '0 0 12px {_bc_color}, 0 0 28px {_bc_color}';
    badge.style.textShadow = '0 0 6px #fff';

    var msg = doc2.createElement('div');
    msg.textContent = '{_bc_msg}';
    msg.style.cssText = 'color:#fff;font-size:clamp(2rem,8vw,5.5rem);font-weight:700;letter-spacing:4px;text-align:center;padding:0 40px;line-height:1.3;';
    msg.style.fontFamily = "'Noto Sans KR', sans-serif";
    msg.style.textShadow = '0 0 4px #fff, 0 0 20px {_bc_color}, 0 0 60px {_bc_color}';
    msg.style.animation  = 'bpulse_' + bid + ' 1.6s ease-in-out infinite';

    ov.appendChild(badge);
    ov.appendChild(msg);
    doc2.body.appendChild(ov);

    ov.addEventListener('animationend', cleanup);

    // 효과음: 공지 → 띵동, 팀응원 → 팡파레
    (function() {{
        try {{
            var AC = null;
            try {{ AC = parent.AudioContext || parent.webkitAudioContext; }} catch(e) {{}}
            if (!AC) AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return;
            var actx = new AC();
            var bcTeam = '{_bc_team}';
            var playBell = function(freq, t0, dur, vol) {{
                var osc = actx.createOscillator();
                var gain = actx.createGain();
                osc.type = 'sine';
                osc.frequency.value = freq;
                gain.gain.setValueAtTime(0.001, t0);
                gain.gain.linearRampToValueAtTime(vol, t0 + 0.01);
                gain.gain.exponentialRampToValueAtTime(0.001, t0 + dur);
                osc.connect(gain); gain.connect(actx.destination);
                osc.start(t0); osc.stop(t0 + dur + 0.05);
            }};
            var play = function() {{
                if (bcTeam === '공지') {{
                    playBell(880, actx.currentTime + 0.0,  1.2, 0.4);
                    playBell(587, actx.currentTime + 0.45, 1.0, 0.35);
                }} else {{
                    var notes = [
                        [523.25, 0.00, 0.20],
                        [659.25, 0.22, 0.20],
                        [784.00, 0.44, 0.20],
                        [1046.5, 0.66, 1.00],
                    ];
                    notes.forEach(function(n) {{
                        var osc  = actx.createOscillator();
                        var gain = actx.createGain();
                        var t0   = actx.currentTime + n[1];
                        osc.type = 'triangle';
                        osc.frequency.value = n[0];
                        gain.gain.setValueAtTime(0.001, t0);
                        gain.gain.linearRampToValueAtTime(0.35, t0 + 0.03);
                        gain.gain.exponentialRampToValueAtTime(0.001, t0 + n[2]);
                        osc.connect(gain); gain.connect(actx.destination);
                        osc.start(t0); osc.stop(t0 + n[2] + 0.05);
                    }});
                }}
            }};
            if (actx.state === 'suspended') {{ actx.resume().then(play); }}
            else {{ play(); }}
        }} catch(e) {{}}
    }})();
}})();
</script>
""", height=0)

# ── 깜짝 미션 전체화면 오버레이 ──────────────────────────────
if _bdata.get("mission_flash"):
    _mf      = _bdata["mission_flash"]
    _mf_mid  = _mf.get("mid", "x")
    _mf_text = _mf.get("mission", "").replace("'", "\\'")
    components.html(f"""
<script>
(function() {{
    var mid      = '{_mf_mid}';
    var keyShown = 'mflash_'      + mid;
    var keyDone  = 'mflash_done_' + mid;
    var keyTime  = 'mflash_t_'    + mid;

    var s = null;
    try {{ s = parent.sessionStorage; }} catch(e) {{}}
    if (!s) {{ try {{ s = sessionStorage; }} catch(e) {{}} }}

    var doc2 = null;
    try {{ doc2 = parent.document; }} catch(e) {{}}
    if (!doc2) doc2 = document;

    if (s && s.getItem(keyDone)) return;

    var cleanup = function() {{
        if (s && s.getItem(keyDone)) return;
        if (s) s.setItem(keyDone, '1');
        var el  = doc2.getElementById('mov_' + mid);
        if (el  && el.parentNode)  el.parentNode.removeChild(el);
        var sel = doc2.getElementById('mst_' + mid);
        if (sel && sel.parentNode) sel.parentNode.removeChild(sel);
        var tabs = doc2.querySelectorAll('button[data-baseweb="tab"]');
        if (tabs && tabs.length > 0) tabs[0].click();
    }};

    if (s && s.getItem(keyShown)) {{
        var t = parseInt(s.getItem(keyTime) || '0');
        if (t && Date.now() - t >= 10500) {{ cleanup(); }}
        return;
    }}

    if (s) {{
        s.setItem(keyShown, '1');
        s.setItem(keyTime, Date.now().toString());
    }}
    if (doc2.getElementById('mov_' + mid)) return;

    var stEl = doc2.createElement('style');
    stEl.id = 'mst_' + mid;
    stEl.textContent =
        '@keyframes mflash_' + mid + ' {{ 0% {{ opacity:0;transform:scale(0.85); }} 12% {{ opacity:1;transform:scale(1); }} 80% {{ opacity:1;transform:scale(1); }} 100% {{ opacity:0;transform:scale(0.9); }} }}' +
        '@keyframes mtext_'  + mid + ' {{ 0%,100% {{ transform:scale(1); }} 50% {{ transform:scale(1.06); }} }}';
    doc2.head.appendChild(stEl);

    var ov = doc2.createElement('div');
    ov.id = 'mov_' + mid;
    ov.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:99999;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none;background:linear-gradient(135deg,#1a0033,#330066);';
    ov.style.animation = 'mflash_' + mid + ' 10s ease-in-out 1 forwards';

    var lbl = doc2.createElement('div');
    lbl.textContent = '✨ 깜짝 미션 발동 ✨';
    lbl.style.cssText = 'color:#cc99ff;font-size:clamp(1rem,3vw,1.8rem);letter-spacing:4px;margin-bottom:28px;font-weight:700;';
    lbl.style.fontFamily = "'Noto Sans KR', sans-serif";
    lbl.style.textShadow = '0 0 12px #cc99ff';

    var mEl = doc2.createElement('div');
    mEl.textContent = '{_mf_text}';
    mEl.style.cssText = 'color:#fff;font-size:clamp(1.6rem,6vw,3.8rem);font-weight:700;text-align:center;padding:0 32px;line-height:1.3;letter-spacing:2px;';
    mEl.style.fontFamily = "'Noto Sans KR', sans-serif";
    mEl.style.textShadow = '0 0 4px #fff, 0 0 20px #cc00ff, 0 0 50px #cc00ff';
    mEl.style.animation  = 'mtext_' + mid + ' 1.4s ease-in-out infinite';

    ov.appendChild(lbl);
    ov.appendChild(mEl);
    doc2.body.appendChild(ov);

    ov.addEventListener('animationend', cleanup);

    // 깜짝 미션 효과음: 상승 스케일 → 웅장한 화음
    (function() {{
        try {{
            var AC = null;
            try {{ AC = parent.AudioContext || parent.webkitAudioContext; }} catch(e) {{}}
            if (!AC) AC = window.AudioContext || window.webkitAudioContext;
            if (!AC) return;
            var actx = new AC();
            // [주파수, 시작(s), 지속(s), 볼륨]
            var notes = [
                [261.63, 0.00, 0.07, 0.18],
                [329.63, 0.07, 0.07, 0.18],
                [392.00, 0.14, 0.07, 0.18],
                [523.25, 0.21, 0.07, 0.18],
                [659.25, 0.28, 0.07, 0.18],
                [783.99, 0.35, 0.07, 0.18],
                [1046.5, 0.42, 0.07, 0.20],
                // 화음 울림
                [523.25, 0.52, 1.60, 0.28],
                [659.25, 0.52, 1.60, 0.25],
                [783.99, 0.52, 1.60, 0.22],
            ];
            var play = function() {{
                notes.forEach(function(n) {{
                    var osc  = actx.createOscillator();
                    var gain = actx.createGain();
                    var t0   = actx.currentTime + n[1];
                    osc.type = 'triangle';
                    osc.frequency.value = n[0];
                    gain.gain.setValueAtTime(0.001, t0);
                    gain.gain.linearRampToValueAtTime(n[3], t0 + 0.02);
                    gain.gain.exponentialRampToValueAtTime(0.001, t0 + n[2]);
                    osc.connect(gain);
                    gain.connect(actx.destination);
                    osc.start(t0);
                    osc.stop(t0 + n[2] + 0.05);
                }});
            }};
            if (actx.state === 'suspended') {{ actx.resume().then(play); }}
            else {{ play(); }}
        }} catch(e) {{}}
    }})();
}})();
</script>
""", height=0)

tab1, tab2 = st.tabs(["🏟️ 전광판 & 미션", "📸 현장 르포 사진방"])


# ── TAB 1: 전광판 & 미션 ─────────────────────────────────────
with tab1:
    data = load_data()

    col_old, col_vs, col_new = st.columns([5, 1, 5])
    with col_old:
        st.markdown(f'<div class="score-card card-old"><div class="sub-text">99년생 + 홀수 출생</div><div class="team-name">세기말 팀</div><div class="score-num">{data["score_old"]}</div><div class="sub-text">점</div></div>', unsafe_allow_html=True)
    with col_vs:
        st.markdown('<div class="vs-badge">VS</div>', unsafe_allow_html=True)
    with col_new:
        st.markdown(f'<div class="score-card card-new"><div class="sub-text">00년생 + 짝수 출생</div><div class="team-name">새천년 팀</div><div class="score-num">{data["score_new"]}</div><div class="sub-text">점</div></div>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    data = load_data()
    if data["mission"]:
        st.markdown(f'<div class="mission-box"><div style="color:#cc99ff;font-size:0.9rem;margin-bottom:8px;letter-spacing:3px;">✨ 미션 발동 ✨</div><div class="mission-text">{data["mission"]}</div></div>', unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    st.markdown("""
    <div style="text-align:center; font-family:'Black Han Sans',sans-serif;
                font-size:clamp(1.2rem,3.5vw,1.8rem); color:#ffdd00;
                text-shadow:0 0 10px #ffdd0088; margin-bottom:8px;">
      📣 실시간 응원 전광판
    </div>""", unsafe_allow_html=True)

    cheer_text = st.text_input(
        label="응원 멘트",
        value=st.session_state.cheer_draft,
        placeholder="직접 입력하거나 AI에게 맡겨보세요! 🔥",
        label_visibility="collapsed",
    )
    ai_col, reg_col = st.columns([3, 1])
    with ai_col:
        if st.button("🤖 AI 응원 멘트 생성", key="ai_gen_btn", use_container_width=True):
            try:
                api_key = st.secrets["UPSTAGE_API_KEY"]
                with st.spinner("AI가 응원 멘트를 생각 중...✨"):
                    d = load_data()
                    result = generate_ai_cheer(
                        st.session_state.user_team, d["score_old"], d["score_new"], api_key
                    )
                st.session_state.cheer_draft = result
                st.rerun()
            except KeyError:
                st.error("⚠️ API 키 미설정")
            except Exception as e:
                st.error(f"AI 생성 실패: {e}")
    with reg_col:
        if st.button("📣 등록", key="cheer_reg_btn", use_container_width=True):
            text = cheer_text.strip()
            if text:
                d = load_data()
                new_cheer = {"team": st.session_state.user_team, "name": st.session_state.user_name, "msg": text}
                d["cheers"].insert(0, new_cheer)
                if not d.get("broadcast"):
                    d["broadcast"] = {**new_cheer, "bid": hashlib.md5(str(random.random()).encode()).hexdigest()[:8], "expires": time.time() + 9}
                else:
                    d["broadcast_queue"].append(new_cheer)
                save_data(d)
                st.session_state.cheer_draft = ""
                st.rerun()

    data = load_data()
    if data["cheers"]:
        for i, item in enumerate(data["cheers"][:20]):
            team       = item.get("team", "")
            bg_cls     = "cheer-bg-old"    if team == "세기말" else "cheer-bg-new"
            badge_cls  = "cheer-badge-old" if team == "세기말" else "cheer-badge-new"
            latest_cls = "latest" if i == 0 else ""
            icon = "🔥 " if i == 0 else "💬 "
            st.markdown(
                f'<div class="cheer-item {bg_cls} {latest_cls}">'
                f'<span class="{badge_cls}">{team} 팀</span>'
                f'<span><b>{item.get("name","")}</b>&nbsp;{icon}{item.get("msg","")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        latest   = data["cheers"][0]
        tts_text = f"{latest.get('name', '')}님의 응원. {latest.get('msg', '')}"
        msg_id   = hashlib.md5(tts_text.encode("utf-8")).hexdigest()
        msg_b64  = base64.b64encode(tts_text.encode("utf-8")).decode("ascii")
        components.html(f"""
        <script>
        (function() {{
            var id='{msg_id}',b64='{msg_b64}',key='lastCheerSpoken';
            var s=null;
            try{{s=parent.sessionStorage;}}catch(e){{}}
            if(!s){{try{{s=sessionStorage;}}catch(e){{}}}}
            if(!s||s.getItem(key)===id) return;
            s.setItem(key,id);
            var bytes=Uint8Array.from(atob(b64),function(c){{return c.charCodeAt(0);}});
            var text=new TextDecoder('utf-8').decode(bytes);
            var synth=(parent&&parent.speechSynthesis)?parent.speechSynthesis:window.speechSynthesis;
            if(!synth) return;
            synth.cancel();
            var u=new SpeechSynthesisUtterance(text);
            u.lang='ko-KR';u.rate=0.92;u.pitch=1.1;u.volume=1.0;
            synth.speak(u);
        }})();
        </script>""", height=0)

        st.markdown("")
    else:
        st.markdown('<div style="text-align:center;color:#555;padding:20px;font-size:1rem;">아직 응원 멘트가 없습니다. 첫 번째 응원을 남겨주세요! 🙌</div>', unsafe_allow_html=True)


# ── TAB 2: 현장 르포 사진방 ──────────────────────────────────
with tab2:
    st.markdown("""
    <div style="text-align:center; font-family:'Black Han Sans',sans-serif;
                font-size:clamp(1.2rem,3.5vw,1.8rem); color:#44ddff;
                text-shadow:0 0 10px #44ddff88; margin-bottom:16px;">
      📸 현장 르포 사진 게시판
    </div>""", unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "사진을 업로드하세요 (여러 장 동시 가능)",
        type=["jpg", "jpeg", "png", "webp", "gif"],
        accept_multiple_files=True,
        label_visibility="visible",
    )

    if "photo_rotations" not in st.session_state:
        st.session_state.photo_rotations = {}

    if uploaded:
        current_names = {f.name for f in uploaded}
        st.session_state.photo_rotations = {k: v for k, v in st.session_state.photo_rotations.items() if k in current_names}

        st.markdown('<div style="color:#aaa;font-size:0.9rem;margin:8px 0 4px;">↩️ ↪️ 버튼으로 회전 후 등록하세요</div>', unsafe_allow_html=True)
        prev_rows = [uploaded[i:i+3] for i in range(0, len(uploaded), 3)]
        for row_files in prev_rows:
            prev_cols = st.columns(len(row_files))
            for col, file in zip(prev_cols, row_files):
                with col:
                    rot = st.session_state.photo_rotations.get(file.name, 0)
                    try:
                        img = Image.open(io.BytesIO(file.getvalue()))
                        if rot:
                            img = img.rotate(rot, expand=True)
                        st.image(img, use_container_width=True, caption=file.name)
                    except Exception:
                        st.warning(f"이미지 오류: {file.name}")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("↩️", key=f"rot_l_{file.name}", use_container_width=True, help="왼쪽 90° 회전"):
                            st.session_state.photo_rotations[file.name] = (rot + 90) % 360
                            st.rerun()
                    with c2:
                        if st.button("↪️", key=f"rot_r_{file.name}", use_container_width=True, help="오른쪽 90° 회전"):
                            st.session_state.photo_rotations[file.name] = (rot - 90) % 360
                            st.rerun()

        if st.button("📸 사진 등록하기", use_container_width=True, type="primary"):
            new_count = 0
            d = load_data()
            for file in uploaded:
                orig_bytes = file.getvalue()
                if any(p["orig_name"] == file.name and p["size"] == len(orig_bytes) for p in d["photos"]):
                    continue
                try:
                    rot = st.session_state.photo_rotations.get(file.name, 0)
                    img = Image.open(io.BytesIO(orig_bytes))
                    if rot:
                        img = img.rotate(rot, expand=True)
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=85)
                    d["photos"].insert(0, {
                        "orig_name": file.name,
                        "size":      len(orig_bytes),
                        "team":      st.session_state.user_team,
                        "uploader":  st.session_state.user_name,
                        "data":      buf.getvalue(),
                    })
                    new_count += 1
                except Exception:
                    st.warning(f"'{file.name}' 은 유효하지 않은 이미지입니다.")
            if new_count > 0:
                save_data(d)
                st.session_state.photo_rotations = {}
                st.success(f"✅ {new_count}장의 사진이 추가되었습니다!")
                st.rerun()

    data = load_data()
    st.markdown(f'<div style="color:#888;font-size:0.9rem;margin:8px 0 16px;text-align:right;">총 {len(data["photos"])}장 업로드됨</div>', unsafe_allow_html=True)

    if data["photos"]:
        cols_per_row = 3
        photo_indexed = list(enumerate(data["photos"]))
        rows = [photo_indexed[i : i + cols_per_row] for i in range(0, len(photo_indexed), cols_per_row)]
        for row in rows:
            cols = st.columns(cols_per_row)
            for col, (idx, photo) in zip(cols, row):
                with col:
                    caption = f"{photo.get('team','')} 팀 · {photo.get('uploader','')}"
                    st.image(Image.open(io.BytesIO(photo["data"])), use_container_width=True, caption=caption)
                    if photo.get("uploader") == st.session_state.user_name:
                        if st.button("🗑️ 삭제", key=f"del_my_photo_{idx}", use_container_width=True):
                            d = load_data(); d["photos"].pop(idx); save_data(d); st.rerun()
        st.markdown("")
        _, col_dlphoto, _ = st.columns([2, 3, 2])
        with col_dlphoto:
            zip_buf = io.BytesIO()
            with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, p in enumerate(data["photos"]):
                    fname = p.get("orig_name") or f"photo_{i+1}.jpg"
                    zf.writestr(fname, p["data"])
            zip_buf.seek(0)
            st.download_button("⬇️ 전체 다운로드", data=zip_buf, file_name="발야구_현장사진.zip", mime="application/zip", use_container_width=True)
    else:
        st.markdown('<div style="text-align:center;color:#555;padding:48px 20px;font-size:1rem;border:2px dashed #333;border-radius:16px;">📷 아직 업로드된 사진이 없습니다.<br>위 버튼을 눌러 현장 사진을 공유해 주세요!</div>', unsafe_allow_html=True)

st.markdown('<div style="text-align:center;color:#444;font-size:0.8rem;margin-top:48px;padding-bottom:16px;">⚾ LNG선공사팀 발야구 대회 | 세기말 vs 새천년 ⚾</div>', unsafe_allow_html=True)
