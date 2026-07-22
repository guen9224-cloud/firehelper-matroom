# 제조사 자료실 (firehelper-matroom) — 2단계(위키형)

소방 자재승인 제조사별 **자료실 웹페이지**입니다. 카톡 챗봇이 "📚 자료실 열기" 버튼으로 이 페이지로 보내주고,
방문자는 제조사 정보 + 문서(카탈로그·형식승인서·시험성적서 등)를 보고 다운로드합니다.

- 데이터: Supabase `public.mat_find(q)` (배포됨)
- **?type=<유형>** 딥링크: 요청한 유형 섹션으로 자동 스크롤·강조 (예: 카톡에서 "카탈로그 줘")
- **?t=<토큰>** (카톡 연동 사용자): 자료 업로드 / 수정·삭제 요청 → **관리자 검토 후 반영**
- **/admin?key=<ADMIN_SECRET>**: 대기 중 기여 목록 승인/반려

## 파일
- `app.py` — FastAPI 앱 (페이지 + 업로드/요청 + 관리자 검토)
- `requirements.txt` — 의존성 (fastapi, uvicorn, **python-multipart**)
- `render.yaml` — render Blueprint (선택)

## 업데이트 방법 (이미 배포돼 있는 경우)
1. 이 세 파일을 GitHub 레포 `firehelper-matroom`에 **덮어쓰기**로 올립니다(커밋).
2. render가 자동으로 다시 배포합니다(1~2분).
3. render 대시보드 → 서비스 → **Environment** 에 아래 환경변수를 추가하세요.

## 환경변수 (Environment)
| Key | Value |
|---|---|
| `SUPABASE_URL` | `https://kfprlgsbvcndomcsjwct.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase 서비스 롤 키 (Settings → API → service_role) |
| `ADMIN_SECRET` | **관리자 페이지 비밀키** (직접 정한 긴 임의 문자열, 예: `mat-admin-9x7k2p...`) |

> `ADMIN_SECRET`은 관리자 검토 페이지(`/admin?key=...`) 접근용입니다. 남에게 알려주지 마세요.

## 사용
- 페이지: `https://firehelper-matroom.onrender.com/m/미도진흥`
- 유형 딥링크: `.../m/미도진흥?type=카달로그`
- 관리자: `https://firehelper-matroom.onrender.com/admin?key=<ADMIN_SECRET>`
- 헬스체크: `/healthz`

## 기여 흐름(위키형)
1. 방문자가 카톡 챗봇에서 "📚 자료실 열기"로 들어오면(연동 사용자면) 링크에 `?t=토큰`이 붙습니다.
2. 각 유형 아래 "＋ 이 유형 자료 올리기"로 파일 업로드, 각 문서 옆 "수정·삭제 요청" 가능.
3. 요청은 `material_test.contribution`에 `pending`으로 쌓이고, `/admin`에서 승인 시 자료실에 반영됩니다.
   - 업로드 승인 → 문서 신규 등록(공개)
   - 삭제 승인 → 해당 문서 숨김 처리(자료실에서 제외)
   - 수정 승인 → 유형/제목 변경
