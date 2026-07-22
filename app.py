"""
소방 자재승인 제조사 자료실 — render.com Web Service (FastAPI)  [2단계]
- Supabase public.mat_find(q) 로 제조사 정보 + 문서 목록 조회 → HTML 렌더
- ?type=<유형> 딥링크: 해당 유형 섹션으로 스크롤·강조
- ?t=<토큰> (카톡 연동 사용자): 자료 업로드 / 수정·삭제 요청 (검토 후 반영)
- /admin?key=<ADMIN_SECRET>: 대기 중 기여 검토(승인/반려)

환경변수(Environment):
  SUPABASE_URL                 예) https://kfprlgsbvcndomcsjwct.supabase.co
  SUPABASE_SERVICE_ROLE_KEY    Supabase 서비스 롤 키 (서버에서만 사용)
  ADMIN_SECRET                 관리자 페이지 비밀키 (임의의 긴 문자열)

로컬 실행:  uvicorn app:app --host 0.0.0.0 --port 8000
render 시작 명령:  uvicorn app:app --host 0.0.0.0 --port $PORT
"""
import os
import json
import uuid
import ssl
import smtplib
import html as _html
import urllib.request
import urllib.error
import urllib.parse
from email.message import EmailMessage

from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "").strip()
BUCKET = "material-docs"
MAX_UPLOAD = 50 * 1024 * 1024  # 50MB (이미지는 업로드 전 자동 압축)
IMG_MAXDIM = 2200              # 이미지 자동 압축 시 최대 변 길이(px)

# 이메일 알림(SMTP). 미설정 시 조용히 건너뜀. Gmail 예: SMTP_HOST=smtp.gmail.com, SMTP_PORT=587,
# SMTP_USER=본인지메일, SMTP_PASS=Google 앱 비밀번호, ADMIN_EMAIL=받을주소(미설정 시 SMTP_USER)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587") or "587")
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "") or SMTP_USER
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://firehelper-matroom.onrender.com").rstrip("/")

app = FastAPI(title="제조사 자료실")


def notify_admin(subject: str, body: str) -> None:
    """새 기여 요청이 들어오면 관리자에게 이메일. 실패해도 요청 처리엔 영향 없음."""
    if not (SMTP_USER and SMTP_PASS and ADMIN_EMAIL):
        return
    try:
        msg = EmailMessage()
        msg["From"] = SMTP_USER
        msg["To"] = ADMIN_EMAIL
        msg["Subject"] = subject
        msg.set_content(body)
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=8) as s:
            s.starttls(context=ctx)
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
    except Exception:
        pass


def admin_link() -> str:
    return PUBLIC_BASE_URL + "/admin?key=" + urllib.parse.quote(ADMIN_SECRET, safe="")

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
UPLOAD_TYPES = [t for t, _ in TYPES]

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
section{background:#fff;border-radius:14px;padding:14px 16px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.06);scroll-margin-top:12px}
section h2{font-size:15px;display:flex;align-items:center;gap:8px;margin-bottom:10px}
.cnt{background:#eee;color:#666;font-size:12px;border-radius:10px;padding:1px 8px;font-weight:600}
.cnt.has{background:#fdecea;color:#c0392b}
.doc{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid #f4f4f4}
.doc:last-child{border:0}
.dt{font-size:14px;flex:1;word-break:break-word}
.btn{flex-shrink:0;background:#c0392b;color:#fff;text-decoration:none;font-size:13px;padding:6px 12px;border-radius:8px;white-space:nowrap;border:0;cursor:pointer}
.btn.link{background:#7f8c8d}
.btn.ghost{background:#fff;color:#c0392b;border:1px solid #e0b4ae;padding:5px 10px;font-size:12px}
.none{color:#aaa;font-size:12px}
.empty{color:#999;font-size:13px;padding:6px 0}
.hl{outline:2px solid #c0392b;box-shadow:0 0 0 5px rgba(192,57,43,.12)}
.contrib{margin-top:10px;border-top:1px dashed #eee;padding-top:10px}
.contrib summary{font-size:12px;color:#c0392b;cursor:pointer;list-style:none}
.contrib summary::-webkit-details-marker{display:none}
.form{margin-top:10px;display:flex;flex-direction:column;gap:8px}
.form input[type=text],.form select,.form textarea{width:100%;font-size:13px;padding:8px;border:1px solid #ddd;border-radius:8px;font-family:inherit}
.form textarea{min-height:50px;resize:vertical}
.form input[type=file]{font-size:12px}
.hint{font-size:11px;color:#999}
.banner{background:#eaf6ec;border:1px solid #bfe3c6;color:#2e6b3a;border-radius:12px;padding:12px 14px;font-size:13px;margin-bottom:14px}
.banner.warn{background:#fff7e6;border-color:#f0d9a8;color:#8a6d1f}
.banner.err{background:#fdecea;border-color:#f2b8b1;color:#a23b30}
.docmeta{display:flex;gap:8px;align-items:center}
.docact{display:flex;gap:6px;flex-shrink:0}
footer{text-align:center;color:#999;font-size:12px;padding:18px 8px 34px}
.adm{background:#fff;border-radius:12px;padding:14px 16px;margin-bottom:10px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
.adm .k{display:inline-block;font-size:11px;font-weight:700;color:#fff;background:#c0392b;border-radius:6px;padding:1px 7px;margin-right:6px}
.adm .k.edit{background:#2980b9}.adm .k.delete{background:#7f8c8d}
.admrow{display:flex;gap:8px;margin-top:8px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.tab{text-decoration:none;font-size:13px;padding:7px 12px;border-radius:999px;background:#fff;color:#555;border:1px solid #e2e2e2}
.tab.on{background:#c0392b;color:#fff;border-color:#c0392b}
.filter{display:flex;gap:6px;margin-bottom:12px}
.filter input{flex:1;font-size:13px;padding:8px;border:1px solid #ddd;border-radius:8px}
.st{display:inline-block;font-size:11px;font-weight:700;border-radius:6px;padding:1px 7px;margin-left:6px}
.st.approved{background:#eaf6ec;color:#2e6b3a}.st.rejected{background:#fdecea;color:#a23b30}
.rn{font-size:12px;color:#777;margin-top:4px}
#ld{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:9999;align-items:center;justify-content:center}
.ldbox{background:#fff;padding:22px 28px;border-radius:14px;font-size:15px;text-align:center;box-shadow:0 8px 30px rgba(0,0,0,.25)}
.ldbox .sp{width:26px;height:26px;border:3px solid #eee;border-top-color:#c0392b;border-radius:50%;margin:0 auto 10px;animation:spin 0.8s linear infinite}
.ldbox small{color:#999}
@keyframes spin{to{transform:rotate(360deg)}}
"""


def esc(s) -> str:
    return _html.escape(str(s if s is not None else ""))


def https_only(u) -> str:
    s = str(u or "")
    return s if s.lower().startswith("https://") else ""


def _rpc(fn: str, payload: dict):
    if not SB_URL or not SB_KEY:
        raise RuntimeError("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY 환경변수가 필요합니다.")
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SB_URL + "/rest/v1/rpc/" + fn,
        data=body,
        headers={
            "Content-Type": "application/json",
            "apikey": SB_KEY,
            "Authorization": "Bearer " + SB_KEY,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def mat_find(q: str):
    return _rpc("mat_find", {"q": q})


def check_token(tok: str) -> dict:
    if not tok:
        return {"ok": False}
    try:
        r = _rpc("mat_check_token", {"p_token": tok})
        return r if isinstance(r, dict) else {"ok": False}
    except Exception:
        return {"ok": False}


def storage_upload(path: str, data: bytes, content_type: str) -> str:
    """material-docs 버킷에 업로드하고 공개 URL 반환. requests 우선, 실패 시 urllib."""
    up_url = SB_URL + "/storage/v1/object/" + BUCKET + "/" + urllib.parse.quote(path)
    pub_url = SB_URL + "/storage/v1/object/public/" + BUCKET + "/" + urllib.parse.quote(path)
    headers = {
        "apikey": SB_KEY,
        "Authorization": "Bearer " + SB_KEY,
        "Content-Type": content_type or "application/octet-stream",
        "x-upsert": "true",
        "User-Agent": "matroom/1.0",
    }
    # 1) requests (대용량 전송에 안정적)
    try:
        import requests  # type: ignore
        resp = requests.post(up_url, data=data, headers=headers, timeout=300)
        if resp.status_code >= 300:
            raise RuntimeError(f"storage {resp.status_code}: {resp.text[:300]}")
        return pub_url
    except ImportError:
        pass
    # 2) urllib 폴백
    req = urllib.request.Request(up_url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            r.read()
    except urllib.error.HTTPError as e:  # 실제 에러 본문을 노출
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        raise RuntimeError(f"storage {e.code}: {body}") from None
    return pub_url


def maybe_compress(data: bytes, content_type: str, filename: str):
    """이미지면 자동으로 축소·재압축해서 (data, content_type, filename) 반환. 실패 시 원본 그대로."""
    fn = (filename or "").lower()
    is_image = (content_type or "").lower().startswith("image/") or fn.endswith(
        (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif")
    )
    if not is_image:
        return data, content_type, filename
    try:
        import io
        from PIL import Image, ImageOps
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im)
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        w, h = im.size
        if max(w, h) > IMG_MAXDIM:
            im.thumbnail((IMG_MAXDIM, IMG_MAXDIM))
        out = io.BytesIO()
        im.save(out, format="JPEG", quality=82, optimize=True)
        nd = out.getvalue()
        if 0 < len(nd) < len(data):
            base = os.path.splitext(os.path.basename(filename or "image"))[0] or "image"
            return nd, "image/jpeg", base + ".jpg"
    except Exception:
        pass
    return data, content_type, filename


def page_html(title: str, inner: str, focus: str = "") -> str:
    js = (
        "<script>(function(){var p=new URLSearchParams(location.search).get('type');"
        "if(p){var el=document.querySelector('section[data-type=\"'+(window.CSS&&CSS.escape?CSS.escape(p):p)+'\"]');"
        "if(el){el.scrollIntoView({behavior:'smooth',block:'start'});el.classList.add('hl');"
        "setTimeout(function(){el.classList.remove('hl')},2600);}}"
        "document.addEventListener('submit',function(e){var f=e.target;if(!f||f.tagName!=='FORM')return;"
        "var ld=document.getElementById('ld');if(ld)ld.style.display='flex';"
        "try{(e.submitter||f.querySelector('button[type=submit]')).disabled=true;}catch(_){}"
        "},true);})();</script>"
    )
    overlay = ('<div id="ld"><div class="ldbox"><div class="sp"></div>'
               '⏳ 처리 중이에요… 잠시만요<br><small>파일이 크면 시간이 걸릴 수 있어요</small></div></div>')
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{esc(title)}</title><style>{CSS}</style></head>"
        f'<body><div class="wrap">{inner}</div>{overlay}{js}</body></html>'
    )


def qname(name: str) -> str:
    return urllib.parse.quote(str(name or ""), safe="")


def upload_form(name: str, token: str, doc_type: str) -> str:
    act = f"/m/{qname(name)}/upload"
    opts = "".join(
        f'<option value="{esc(t)}"{" selected" if t == doc_type else ""}>{esc(dict(TYPES)[t])}</option>'
        for t in UPLOAD_TYPES
    )
    return (
        '<details class="contrib"><summary>＋ 이 유형 자료 올리기</summary>'
        f'<form class="form" action="{act}" method="post" enctype="multipart/form-data">'
        f'<input type="hidden" name="t" value="{esc(token)}">'
        f'<select name="doc_type">{opts}</select>'
        '<input type="text" name="title" placeholder="자료 제목(선택) 예) 2024 카탈로그">'
        '<input type="file" name="file">'
        '<input type="text" name="link_url" placeholder="또는 파일 링크(URL) — 대용량 PDF는 구글드라이브 등 링크">'
        '<div class="hint">파일 또는 링크 중 하나. 사진은 자동으로 용량을 줄여 올려요. 파일 최대 50MB.</div>'
        '<button class="btn" type="submit">업로드 요청(검토 후 반영)</button>'
        "</form></details>"
    )


def request_form(name: str, token: str, doc: dict) -> str:
    act = f"/m/{qname(name)}/request"
    did = esc(doc.get("id"))
    opts = "".join(
        f'<option value="{esc(t)}"{" selected" if t == doc.get("doc_type") else ""}>{esc(dict(TYPES)[t])}</option>'
        for t in UPLOAD_TYPES
    )
    return (
        '<details class="contrib"><summary>수정·삭제 요청</summary>'
        f'<form class="form" action="{act}" method="post">'
        f'<input type="hidden" name="t" value="{esc(token)}">'
        f'<input type="hidden" name="target_doc_id" value="{did}">'
        f'<select name="doc_type">{opts}</select>'
        f'<input type="text" name="title" value="{esc(doc.get("title") or "")}" placeholder="새 제목">'
        '<textarea name="note" placeholder="사유(예: 유형이 잘못됨 / 최신본으로 교체 요청)"></textarea>'
        '<div style="display:flex;gap:8px">'
        '<button class="btn" type="submit" name="kind" value="edit">수정 요청</button>'
        '<button class="btn link" type="submit" name="kind" value="delete">삭제 요청</button>'
        "</div></form></details>"
    )


def render_manufacturer(info: dict, token: str = "", can: bool = False, msg: str = "") -> str:
    docs = info.get("docs") or []
    by_type: dict = {}
    for d in docs:
        by_type.setdefault(d.get("doc_type"), []).append(d)

    banner = ""
    if msg:
        cls = "banner"
        if msg.startswith("!"):
            cls = "banner err"; msg = msg[1:]
        banner = f'<div class="{cls}">{esc(msg)}</div>'
    if can:
        banner += '<div class="banner">✅ 연동 확인됨 — 자료 업로드 및 수정·삭제 요청을 하실 수 있어요. (관리자 검토 후 반영)</div>'
    else:
        banner += '<div class="banner warn">ℹ️ 자료를 올리거나 수정·삭제를 요청하려면 카카오톡 챗봇에서 <b>“📚 자료실 열기”</b> 버튼으로 다시 들어와 주세요(연동 사용자 전용).</div>'

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
                act = ""
                if href:
                    cls = "btn" if file else "btn link"
                    lab = "다운·보기" if file else "원본페이지"
                    act = f'<a class="{cls}" href="{esc(href)}" target="_blank" rel="noopener">{lab}</a>'
                else:
                    act = '<span class="none">링크없음</span>'
                rows += (
                    f'<div class="doc"><span class="dt">{title}</span>'
                    f'<span class="docact">{act}</span></div>'
                )
                if can:
                    rows += request_form(info.get("name"), token, d)
            inner = rows
        else:
            inner = '<div class="empty">등록된 자료가 없어요.</div>'
        if can:
            inner += upload_form(info.get("name"), token, t)
        has = " has" if lst else ""
        sections += (
            f'<section data-type="{esc(t)}"><h2>{esc(label)} '
            f'<span class="cnt{has}">{len(lst)}</span></h2>{inner}</section>'
        )

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
        f"{banner}"
        f'<div class="info">{info_rows}</div>'
        f"{sections}"
        f"<footer>보유 자료 {total}건 · 공개 정보를 정리한 것입니다.<br>오류·누락은 카톡 챗봇 또는 위 요청으로 알려주세요.</footer>"
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
    return await _serve(m, request)


@app.get("/m/{name}", response_class=HTMLResponse)
async def by_name(name: str, request: Request):
    return await _serve(name, request)


async def _serve(m: str, request: Request) -> HTMLResponse:
    m = (m or "").strip()
    tok = request.query_params.get("t") or ""
    msg = request.query_params.get("msg") or ""
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
    can = bool(check_token(tok).get("ok")) if tok else False
    return HTMLResponse(render_manufacturer(info, token=tok, can=can, msg=msg))


def _mid_of(info: dict) -> int:
    ids = info.get("ids") or []
    return int(ids[0]) if ids else 0


def _back(name: str, tok: str, msg: str) -> RedirectResponse:
    url = f"/m/{qname(name)}?t={urllib.parse.quote(tok, safe='')}&msg={urllib.parse.quote(msg, safe='')}"
    return RedirectResponse(url, status_code=303)


async def _store_upload(file, link_url: str, path_prefix: str):
    """파일(있으면 압축) 또는 링크를 저장. 반환: (storage_url, display_name, error_or_None)."""
    link_url = (link_url or "").strip()
    data = b""
    if file is not None and getattr(file, "filename", ""):
        data = await file.read()
    if data:
        safe = os.path.basename(file.filename or "file").replace(" ", "_")
        data, ctype, safe = maybe_compress(data, file.content_type or "", safe)
        if len(data) > MAX_UPLOAD:
            return None, None, ("!파일이 너무 커요(최대 50MB). 큰 PDF는 아래 '파일 링크(URL)' 칸에 "
                                "구글드라이브·드롭박스 공유 링크를 붙여 등록해 주세요.")
        path = f"{path_prefix}/{uuid.uuid4().hex}_{safe}"
        try:
            purl = storage_upload(path, data, ctype or "application/octet-stream")
        except Exception as e:  # noqa: BLE001
            return None, None, f"!업로드 실패: {e}"
        return purl, safe, None
    if link_url:
        if not link_url.lower().startswith(("http://", "https://")):
            return None, None, "!링크는 http(s):// 로 시작하는 주소여야 해요."
        nm = os.path.basename(urllib.parse.urlparse(link_url).path) or "링크 자료"
        return link_url, nm, None
    return None, None, "!파일을 첨부하거나 파일 링크(URL)를 입력해 주세요."


@app.post("/m/{name}/upload")
async def do_upload(name: str, t: str = Form(""), doc_type: str = Form("기타"),
                    title: str = Form(""), link_url: str = Form(""),
                    file: UploadFile = File(None)):
    chk = check_token(t)
    if not chk.get("ok"):
        return _back(name, t, "!토큰이 유효하지 않아요. 카톡 자료실 열기로 다시 들어와 주세요.")
    try:
        info = mat_find(name)
    except Exception:
        return _back(name, t, "!일시적 오류가 발생했어요.")
    if not info or info.get("matched") is not True:
        return _back(name, t, "!제조사를 찾지 못했어요.")
    mid = _mid_of(info)
    if doc_type not in UPLOAD_TYPES:
        doc_type = "기타"
    purl, safe, err = await _store_upload(file, link_url, f"contrib/{mid}")
    if err:
        return _back(name, t, err)
    try:
        r = _rpc("mat_submit_contrib", {
            "p_token": t, "p_manufacturer_id": mid, "p_kind": "upload",
            "p_doc_type": doc_type, "p_title": title or safe, "p_storage_url": purl,
            "p_target_doc_id": None, "p_note": None,
        })
    except Exception as e:  # noqa: BLE001
        return _back(name, t, f"!요청 저장 실패: {e}")
    if isinstance(r, dict) and not r.get("ok"):
        return _back(name, t, "!" + str(r.get("error") or "요청 실패"))
    notify_admin(
        f"[자료실] 업로드 요청 · {info.get('name')} · {dict(TYPES).get(doc_type, doc_type)}",
        f"제조사: {info.get('name')}\n유형: {dict(TYPES).get(doc_type, doc_type)}\n제목: {title or safe}\n"
        f"파일: {purl}\n\n검토(승인/반려): {admin_link()}",
    )
    return _back(name, t, "📩 업로드 요청이 접수됐어요. 관리자 검토 후 자료실에 반영됩니다. 감사합니다!")


@app.post("/m/{name}/request")
async def do_request(name: str, t: str = Form(""), kind: str = Form("edit"),
                     target_doc_id: str = Form(""), doc_type: str = Form(""),
                     title: str = Form(""), note: str = Form("")):
    chk = check_token(t)
    if not chk.get("ok"):
        return _back(name, t, "!토큰이 유효하지 않아요. 카톡 자료실 열기로 다시 들어와 주세요.")
    try:
        info = mat_find(name)
    except Exception:
        return _back(name, t, "!일시적 오류가 발생했어요.")
    mid = _mid_of(info)
    if kind not in ("edit", "delete"):
        kind = "edit"
    try:
        tid = int(target_doc_id) if target_doc_id else None
    except ValueError:
        tid = None
    try:
        r = _rpc("mat_submit_contrib", {
            "p_token": t, "p_manufacturer_id": mid, "p_kind": kind,
            "p_doc_type": doc_type or None, "p_title": title or None, "p_storage_url": None,
            "p_target_doc_id": tid, "p_note": note or None,
        })
    except Exception as e:  # noqa: BLE001
        return _back(name, t, f"!요청 저장 실패: {e}")
    if isinstance(r, dict) and not r.get("ok"):
        return _back(name, t, "!" + str(r.get("error") or "요청 실패"))
    label = "삭제" if kind == "delete" else "수정"
    notify_admin(
        f"[자료실] {label} 요청 · {info.get('name')}",
        f"제조사: {info.get('name')}\n종류: {label} 요청\n대상 문서#: {tid}\n"
        f"바꿀 유형: {dict(TYPES).get(doc_type, doc_type or '-')}\n바꿀 제목: {title or '-'}\n사유: {note or '-'}\n\n"
        f"검토(승인/반려): {admin_link()}",
    )
    return _back(name, t, f"📩 {label} 요청이 접수됐어요. 관리자 검토 후 반영됩니다. 감사합니다!")


# ---------- 신규(미등록) 제조사 자료 등록 ----------

@app.get("/new", response_class=HTMLResponse)
async def new_page(request: Request):
    name = (request.query_params.get("name") or "").strip()
    tok = request.query_params.get("t") or ""
    msg = request.query_params.get("msg") or ""
    can = bool(check_token(tok).get("ok")) if tok else False
    banner = ""
    if msg:
        cls = "banner"
        if msg.startswith("!"):
            cls = "banner err"; msg = msg[1:]
        banner = f'<div class="{cls}">{esc(msg)}</div>'
    if not can:
        banner += '<div class="banner warn">ℹ️ 자료 등록은 카카오톡 챗봇에서 <b>“📤 자료 등록하기”</b> 버튼으로 들어오셔야 가능해요(연동 사용자 전용).</div>'
        inner = (
            '<header><div class="badge">소방 자재승인 자료실</div><h1>새 제조사 자료 등록</h1></header>'
            f"{banner}"
        )
        return HTMLResponse(page_html("자료 등록", inner))
    opts = "".join(f'<option value="{esc(t)}">{esc(dict(TYPES)[t])}</option>' for t in UPLOAD_TYPES)
    form = (
        f'<section><form class="form" action="/new/upload" method="post" enctype="multipart/form-data">'
        f'<input type="hidden" name="t" value="{esc(tok)}">'
        '<div class="irow"><b>제조사명</b></div>'
        f'<input type="text" name="name" value="{esc(name)}" placeholder="제조사 이름 (예: 원일산업)" required>'
        f'<select name="doc_type">{opts}</select>'
        '<input type="text" name="title" placeholder="자료 제목(선택) 예) 2024 카탈로그">'
        '<input type="file" name="file">'
        '<input type="text" name="link_url" placeholder="또는 파일 링크(URL) — 대용량 PDF는 구글드라이브 등 링크">'
        '<div class="hint">파일 또는 링크 중 하나. 사진은 자동으로 용량을 줄여 올려요. 파일 최대 50MB.</div>'
        '<button class="btn" type="submit">등록 요청 (검토 후 반영)</button>'
        '</form></section>'
    )
    inner = (
        '<header><div class="badge">소방 자재승인 자료실</div><h1>새 제조사 자료 등록</h1></header>'
        f"{banner}"
        '<div class="banner">✅ 연동 확인됨 — 아직 자료실에 없는 제조사의 자료를 올리실 수 있어요. 승인되면 자료실에 새로 등록돼요.</div>'
        f"{form}"
    )
    return HTMLResponse(page_html("자료 등록", inner))


@app.post("/new/upload")
async def new_upload(name: str = Form(""), t: str = Form(""), doc_type: str = Form("기타"),
                     title: str = Form(""), link_url: str = Form(""),
                     file: UploadFile = File(None)):
    name = (name or "").strip()
    chk = check_token(t)
    if not chk.get("ok"):
        return _new_back(name, t, "!토큰이 유효하지 않아요. 카톡에서 다시 들어와 주세요.")
    if not name:
        return _new_back(name, t, "!제조사 이름을 입력해 주세요.")
    if doc_type not in UPLOAD_TYPES:
        doc_type = "기타"
    purl, safe, err = await _store_upload(file, link_url, "contrib/new")
    if err:
        return _new_back(name, t, err)
    try:
        r = _rpc("mat_submit_new", {
            "p_token": t, "p_proposed_name": name, "p_doc_type": doc_type,
            "p_title": title or safe, "p_storage_url": purl, "p_note": None,
        })
    except Exception as e:  # noqa: BLE001
        return _new_back(name, t, f"!요청 저장 실패: {e}")
    if isinstance(r, dict) and not r.get("ok"):
        return _new_back(name, t, "!" + str(r.get("error") or "요청 실패"))
    notify_admin(
        f"[자료실] 신규 제조사 등록 요청 · {name}",
        f"신규 제조사: {name}\n유형: {dict(TYPES).get(doc_type, doc_type)}\n제목: {title or safe}\n"
        f"파일: {purl}\n\n검토(승인 시 제조사 신규 생성): {admin_link()}",
    )
    return _new_back(name, t, "📩 등록 요청이 접수됐어요. 관리자 검토 후 자료실에 새로 등록됩니다. 감사합니다!")


def _new_back(name: str, tok: str, msg: str) -> RedirectResponse:
    url = (f"/new?name={urllib.parse.quote(name, safe='')}"
           f"&t={urllib.parse.quote(tok, safe='')}&msg={urllib.parse.quote(msg, safe='')}")
    return RedirectResponse(url, status_code=303)


# ---------- 관리자 검토 ----------

def _adm_card(c: dict, key: str) -> str:
    kind = c.get("kind")
    kcls = " " + kind if kind in ("edit", "delete") else ""
    klab = {"upload": "업로드", "edit": "수정", "delete": "삭제"}.get(kind, kind)
    status = c.get("status")
    surl = https_only(c.get("storage_url"))
    preview = f' · <a href="{esc(surl)}" target="_blank" rel="noopener">파일보기</a>' if surl else ""
    tid = f' · 대상문서#{esc(c.get("target_doc_id"))}' if c.get("target_doc_id") else ""
    note = f'<div style="font-size:13px;color:#555;margin-top:4px">사유/메모: {esc(c.get("note"))}</div>' if c.get("note") else ""
    stbadge = ""
    if status == "approved":
        stbadge = '<span class="st approved">승인됨</span>'
    elif status == "rejected":
        stbadge = '<span class="st rejected">반려됨</span>'
    head = (
        f'<div><span class="k{kcls}">{esc(klab)}</span>'
        f'<b>{esc(c.get("mname") or ("#" + str(c.get("mid"))))}</b> · '
        f'{esc(dict(TYPES).get(c.get("doc_type"), c.get("doc_type")))}'
        f' · {esc(c.get("title") or "")}{tid}{preview}{stbadge}</div>'
        f'<div style="font-size:12px;color:#999;margin-top:2px">요청자 {esc((c.get("submitter") or "")[:10])}… · {esc(str(c.get("created_at"))[:19])}</div>'
        f"{note}"
    )
    if status == "pending":
        action = (
            f'<form class="admrow" action="/admin/review" method="post">'
            f'<input type="hidden" name="key" value="{esc(key)}">'
            f'<input type="hidden" name="id" value="{esc(c.get("id"))}">'
            '<input type="text" name="note" placeholder="검토 메모(선택)" style="flex:1;font-size:13px;padding:7px;border:1px solid #ddd;border-radius:8px">'
            '<button class="btn" type="submit" name="action" value="approve">승인</button>'
            '<button class="btn link" type="submit" name="action" value="reject">반려</button>'
            "</form>"
        )
    else:
        rn = f'검토 {esc(str(c.get("reviewed_at"))[:19])}'
        if c.get("reviewer_note"):
            rn += f' · 메모: {esc(c.get("reviewer_note"))}'
        action = f'<div class="rn">{rn}</div>'
    return f'<div class="adm">{head}{action}</div>'


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    key = (request.query_params.get("key") or "").strip()
    msg = request.query_params.get("msg") or ""
    status = request.query_params.get("status") or "pending"
    q = (request.query_params.get("q") or "").strip()
    if status not in ("pending", "approved", "rejected", "all"):
        status = "pending"
    if not ADMIN_SECRET or key != ADMIN_SECRET:
        return HTMLResponse(page_html("관리자", '<section><p>접근 권한이 없어요.</p></section>'), status_code=403)
    try:
        counts = _rpc("mat_contrib_counts", {})
        rows = _rpc("mat_contrib_list", {"p_status": status})
    except Exception as e:  # noqa: BLE001
        return HTMLResponse(page_html("관리자", f'<section><p>오류: {esc(e)}</p></section>'), status_code=502)
    counts = counts if isinstance(counts, dict) else {}
    rows = rows if isinstance(rows, list) else []
    if q:
        ql = q.lower()
        rows = [c for c in rows if ql in str(c.get("mname") or "").lower()]

    def kq(extra: dict) -> str:
        p = {"key": key}
        p.update(extra)
        return "/admin?" + urllib.parse.urlencode(p)

    tabs_def = [("pending", "대기", counts.get("pending", 0)),
                ("approved", "승인", counts.get("approved", 0)),
                ("rejected", "반려", counts.get("rejected", 0)),
                ("all", "전체", counts.get("total", 0))]
    tabs = "".join(
        f'<a class="tab{" on" if status == s else ""}" href="{esc(kq({"status": s, "q": q}))}">{esc(lab)} {n}</a>'
        for s, lab, n in tabs_def
    )
    filt = (
        f'<form class="filter" action="/admin" method="get">'
        f'<input type="hidden" name="key" value="{esc(key)}">'
        f'<input type="hidden" name="status" value="{esc(status)}">'
        f'<input type="text" name="q" value="{esc(q)}" placeholder="제조사 이름으로 검색">'
        '<button class="btn" type="submit">검색</button>'
        + (f'<a class="btn ghost" href="{esc(kq({"status": status}))}">초기화</a>' if q else "")
        + "</form>"
    )
    cards = "".join(_adm_card(c, key) for c in rows)
    if not cards:
        empty = "대기 중인 기여가 없어요. 👍" if status == "pending" else "해당 항목이 없어요."
        cards = f'<section><p>{esc(empty)}</p></section>'
    banner = f'<div class="banner">{esc(msg)}</div>' if msg else ""
    inner = (
        '<header><div class="badge">관리자 검토</div><h1>기여 관리</h1></header>'
        f"{banner}{tabs}{filt}{cards}"
    )
    return HTMLResponse(page_html("관리자 검토", inner))


@app.post("/admin/review")
async def admin_review(key: str = Form(""), id: str = Form(""),
                       action: str = Form("approve"), note: str = Form("")):
    key = (key or "").strip()
    if not ADMIN_SECRET or key != ADMIN_SECRET:
        return HTMLResponse("forbidden", status_code=403)
    if action not in ("approve", "reject"):
        action = "reject"
    try:
        cid = int(id)
    except ValueError:
        cid = 0
    try:
        r = _rpc("mat_review", {"p_id": cid, "p_action": action, "p_note": note or None})
        res = r.get("result") if isinstance(r, dict) else ""
        m = {"approved": "✅ 승인 완료 — 자료실에 반영했어요.", "rejected": "↩️ 반려 처리했어요."}.get(res, "처리했어요.")
    except Exception as e:  # noqa: BLE001
        m = f"오류: {e}"
    url = f"/admin?key={urllib.parse.quote(key, safe='')}&msg={urllib.parse.quote(m, safe='')}"
    return RedirectResponse(url, status_code=303)
