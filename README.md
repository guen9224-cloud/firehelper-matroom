# 제조사 자료실 (firehelper-matroom)

소방 자재승인 제조사별 **자료실 웹페이지**를 서빙하는 render.com 웹서비스입니다.
카톡 챗봇이 제조사 질문에 이 페이지 링크를 주면, 방문자는 제조사 정보 + 문서(카탈로그·형식승인서·시험성적서 등)를 보고 다운로드할 수 있습니다.

- 데이터는 Supabase의 `public.mat_find(q)` 함수(이미 배포됨)에서 가져옵니다.
- 1단계: **읽기 전용** (정보 + 문서 보기/다운로드, 없는 유형 표시)
- 2단계(예정): 연동 사용자 업로드 + 편집/삭제 요청 검토(위키형)

## 파일
- `app.py` — FastAPI 앱 (페이지 렌더링)
- `requirements.txt` — 의존성
- `render.yaml` — render Blueprint (선택)

## render.com 배포 (둘 중 하나)

### 방법 A) Blueprint (가장 쉬움)
1. 이 4개 파일을 GitHub 새 레포에 올립니다.
2. render 대시보드 → **New → Blueprint** → 그 레포 선택.
3. 배포 중 환경변수 2개를 입력합니다(아래).

### 방법 B) 수동 Web Service
1. render → **New → Web Service** → 레포 연결 (Runtime: Python).
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. 환경변수 2개 입력.

## 환경변수 (Environment)
| Key | Value |
|---|---|
| `SUPABASE_URL` | `https://kfprlgsbvcndomcsjwct.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase 서비스 롤 키 (Settings → API → service_role) |

> 서비스 롤 키는 **서버에서만** 사용되고 브라우저엔 노출되지 않습니다. 코드에 넣지 말고 render 환경변수로만 넣으세요.

## 사용
배포 후 URL 예시:
- `https://firehelper-matroom.onrender.com/m/미도진흥`
- 또는 `https://firehelper-matroom.onrender.com/?m=미도진흥`
- 헬스체크: `/healthz`

## 다음 단계
배포되면 **그 URL을 알려주세요.** 제가 카톡 챗봇(mat-bot)이 제조사 응답에 "📚 자료실 열기" 링크를 함께 주도록 연결하고, 이어서 2단계(업로드·편집 검토)를 붙이겠습니다.
