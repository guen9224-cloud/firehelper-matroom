"""
소방 자재승인 제조사 자료실 — render.com Web Service (FastAPI)
- Supabase의 public.mat_find(q) RPC로 제조사 정보 + 문서 목록을 조회해 HTML 렌더
- 1단계: 읽기전용 (정보 + 문서 보기/다운로드, 없는 유형 표시)
- 2단계(예정): 연동 사용자 업로드 / 편집·삭제 요청 검토

환경변수(Environment):
  SUPABASE_URL                 예) https://kfprlgsbvcndomcsjwct.supabase.co
  SUPABASE_SERVICE_ROLE_KEY    Supabase 서비스 롤 키 (서버에서만 사용, 노출 안 됨)

로컬 실행:  uvicorn app:app --host 0.0.0.0 --port 8000
render 시작 명령:  uvicorn app:app --host 0.0.0.0 --port $PORT
"""
import os
import json
import html as _html
import urllib.request
import urllib.error

from fastapi import Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi import FastAPI

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

app = FastAPI(title="제조사 자료실")

# doc_type -> 화면 라벨 (표시 순서)
TYPES = [
    ("KFI인증서", "형식승인·자재승인 서류"),
    ("시험성적서", "시험성적서"),
    ("카달로그", "카탈로그"),
    ("KS인증서", "KS인증서"),
    ("사업자등록증", "사업자등록증"),
    ("공장등록증", "공장등록증"),
    ("기타", "기타 자료"),
]

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Malgun Gothic','Apple SD Gothic Neo',sans-serif;background:#f4f5f7;color:#1a1a1a;line-height:1.5}
.wrap{max-width:720px;margin:0 auto;padding:16px}
header{background:linear-gradient(135deg,#c0392b,#e74c3c);color:#fff;border-radius:16px;padding:22px 20px;margin-bottom:14px}
.badge{font-size:12px;opacity:.9;letter-spacing:.5px}
header h1{font-size:22px;margin-top:6px}
.info{background:#fff;border-radius:14px;padding:16px;margin-bottom:16px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.irow{font-size:14px;padding:5px 0;border-bottom:1px solid #f0f0f0}
.irow:last-child{border:0}
.irow b{display:inline-block;width:82px;color:#666;font-weight:600}
.irow a{color:#c0392b;word-break:break-all}
section{background:#fff;border-radius:14px;padding:14px 16px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
section h2{font-size:15px;display:flex;align-items:center;gap:8px;margin-bottom:10px}
.cnt{background:#eee;color:#666;font-size:12px;border-radius:10px;padding:1px 8px;font-weight:600}
.cnt.has{background:#fdecea;color:#c0392b}
.doc{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid #f4f4f4}
.doc:last-child{border:0}
.dt{font-size:14px;flex:1;word-break:break-word}
.btn{flex-shrink:0;background:#c0392b;color:#fff;text-decoration:none;font-size:13px;padding:6px 12px;border-radius:8px;white-space:nowrap}
.btn.link{background:#7f8c8d}
.none{color:#aaa;font-size:12px}
.empty{color:#999;font-size:13px;padding:6px 0}
.soon{display:inline-block;background:#f0f0f0;color:#888;font-size:11px;border-radius:6px;padding:2px 7px;margin-left:4px}
footer{text-align:center;color:#999;font-size:12px;padding:18px 8px 34px}
"""


def esc(s) -> str:
    return _html.escape(str(s if s is not None else ""))


def https_only(u) -> str:
    s = str(u or "")
    return s if s.lower().startswith("https://") else ""


def mat_find(q: str):
    """Supabase public.mat_find(q) 호출."""
    if not SB_URL or not SB_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 환경변수가 필요합니다.")
    body = json.dumps({"q": q}).encode("utf-8")
    req = urllib.request.Request(
        SB_URL + "/rest/v1/rpc/mat_find",
        data=body,
        headers={
            "Content-Type": "application/json",
            "apikey": SB_KEY,
            "Authorization": "Bearer " + SB_KEY,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8"))


def page_html(title: str, inner: str) -> str:
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{esc(title)}</title><style>{CSS}</style></head>"
        f'<body><div class="wrap">{inner}</div></body></html>'
    )


def render_manufacturer(info: dict) -> str:
    docs = info.get("docs") or []
    by_type: dict = {}
    for d in docs:
        by_type.setdefault(d.get("doc_type"), []).append(d)

    sections = ""
    for t, label in TYPES:
        lst = by_type.get(t, [])
        if lst:
            rows = ""
            for d in lst:
                file = https_only(d.get("file"))
                link = https_only(d.get("link"))
                href = file or link
                title = esc(d.get("title") or label)
                if href:
                    cls = "btn" if file else "btn link"
                    lab = "다운·보기" if file else "원본페이지"
                    rows += f'<div class="doc"><span class="dt">{title}</span><a class="{cls}" href="{esc(href)}" target="_blank" rel="noopener">{lab}</a></div>'
                else:
                    rows += f'<div class="doc"><span class="dt">{title}</span><span class="none">링크없음</span></div>'
            inner = rows
        else:
            inner = '<div class="empty">등록된 자료가 없어요. <span class="soon">업로드 준비중(연동 사용자)</span></div>'
        has = " has" if lst else ""
        sections += f'<section><h2>{esc(label)} <span class="cnt{has}">{len(lst)}</span></h2>{inner}</section>'

    rows_info = [
        ("대표", info.get("rep")),
        ("주소", info.get("address")),
        ("전화", info.get("phone")),
        ("팩스", info.get("fax")),
        ("이메일", info.get("email")),
        ("사업자번호", info.get("biz_no")),
        ("홈페이지", info.get("homepage")),
    ]
    info_rows = ""
    for k, v in rows_info:
        if not v:
            continue
        if k == "홈페이지":
            info_rows += f'<div class="irow"><b>{k}</b> <a href="{esc(v)}" target="_blank" rel="noopener">{esc(v)}</a></div>'
        else:
            info_rows += f'<div class="irow"><b>{k}</b> {esc(v)}</div>'
    if not info_rows:
        info_rows = '<div class="irow">등록된 정보가 없어요.</div>'

    total = len(docs)
    inner = (
        f'<header><div class="badge">소방 자재승인 자료실</div><h1>{esc(info.get("name"))}</h1></header>'
        f'<div class="info">{info_rows}</div>'
        f"{sections}"
        f"<footer>보유 자료 {total}건 · 공개 정보를 정리한 것입니다.<br>오류·누락은 카톡 챗봇으로 알려주세요.</footer>"
    )
    return page_html(str(info.get("name")) + " 자료실", inner)


def not_found(m: str) -> str:
    inner = (
        '<header><div class="badge">소방 자재승인 자료실</div><h1>제조사 자료실</h1></header>'
        f'<section><p>“{esc(m)}” 제조사를 찾지 못했어요.</p></section>'
    )
    return page_html("자료실", inner)


@app.get("/healthz", response_class=PlainTextResponse)
async def healthz():
    return "ok"


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    m = request.query_params.get("m") or request.query_params.get("q") or ""
    return await _serve(m)


@app.get("/m/{name}", response_class=HTMLResponse)
async def by_name(name: str):
    return await _serve(name)


async def _serve(m: str) -> HTMLResponse:
    m = (m or "").strip()
    if not m:
        inner = (
            '<header><div class="badge">소방 자재승인 자료실</div><h1>제조사 자료실</h1></header>'
            "<section><p>주소에 제조사 이름이 없어요. 예) /m/미도진흥</p></section>"
        )
        return HTMLResponse(page_html("자료실", inner))
    try:
        info = mat_find(m)
    except Exception as e:  # noqa: BLE001
        return HTMLResponse(page_html("자료실", f'<section><p>일시적 오류가 발생했어요.<br><small>{esc(e)}</small></p></section>'), status_code=502)
    if not info or info.get("matched") is not True:
        return HTMLResponse(not_found(m), status_code=404)
    return HTMLResponse(render_manufacturer(info))
