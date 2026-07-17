# Studio — 오디오 워크스테이션 (MVP)

`오디오_플랫폼_설계서_v1.0.md`의 Phase 1 MVP 범위를 구현한 로컬 개발용 스캐폴딩입니다.
유튜브 URL 또는 파일 업로드 → 보컬/MR 분리 → 키 변경 → 내보내기까지의 파이프라인이 동작합니다.

## 이 환경에서 달라진 점

설계서는 GPU(CUDA) 서버 배포를 전제로 하지만, 이 저장소는 **로컬 개발 환경(Windows + Docker
Desktop + AMD GPU)** 기준으로 조정되어 있습니다.

- **분리 워커는 CPU로 동작합니다.** AMD GPU는 PyTorch/Demucs의 CUDA 경로를 쓸 수 없어서입니다.
  4분 곡 분리에 GPU 대비 훨씬 오래 걸립니다(수 분 단위 예상). 엔비디아 GPU가 있는 머신에서는
  `.env`의 `DEMUCS_DEVICE=cuda`로 바꾸고 `services/workers/Dockerfile.separate`의 베이스 이미지를
  CUDA 지원 PyTorch 이미지로 교체하면 됩니다.
- **레지덴셜 프록시가 없습니다.** 유튜브 봇 탐지(§5.1.3)에 취약합니다 — 다운로드가 간헐적으로
  실패할 수 있습니다. `.env`의 `PROXY_URL`에 프록시를 넣으면 사용됩니다.
- **인증/회원 기능은 없습니다.** 설계서상 Phase 2 항목이라 제외했습니다. 사용량 제한은 IP 해시
  기준으로만 동작합니다(§14.1).
- **템포 조절, 4/6스템 분리, 결제, 모바일 앱, 모니터링 스택(Sentry/Prometheus)** 은 Phase 2/3
  항목으로 이번 스캐폴딩에 포함하지 않았습니다.

## 빠른 시작

```bash
cp .env.example .env      # 로컬 개발용 기본값 그대로 사용 가능
docker compose up --build
```

첫 빌드는 `worker-separate` 이미지에서 Demucs `htdemucs`(fast 티어) 모델을 미리 받기 때문에 시간이
좀 걸립니다. `htdemucs_ft`(pro 티어)는 첫 실제 사용 시점에 지연 로딩됩니다.

기동 후:
- 프론트엔드: http://localhost:3000
- API: http://localhost:8000 (`/health`, OpenAPI 문서는 `/docs`)
- MinIO 콘솔: http://localhost:9001 (계정: `minioadmin` / `minioadmin`)

`api` 컨테이너는 시작할 때 `alembic upgrade head`를 자동 실행해 DB 스키마를 만듭니다.

### GUI로 관리하기 (Windows)

터미널 명령이 번거로우면 저장소 루트의 **`Studio 서버 관리.vbs`** 를 더블클릭하세요. 버튼으로
전체/개별 서비스 시작·중지·재시작을 하고, 실시간 로그도 같은 창에서 볼 수 있습니다. 자세한 내용은
[`tools/server-manager/README.md`](tools/server-manager/README.md) 참고.

## 모노레포 구조

```
apps/web/                Next.js 15 프론트엔드
services/api/             FastAPI (라우터 · 스키마 · alembic 마이그레이션)
services/workers/         Celery 워커 (download / separation / dsp)
services/common/          api·workers가 공유하는 DB 모델, 캐시, 스토리지, yt-dlp 설정 등
tools/server-manager/     서버 시작/중지/로그 확인용 Windows GUI
```

`services/common`은 두 이미지(`services/api/Dockerfile`, `services/workers/Dockerfile*`)에
각각 복사되어 들어갑니다 — 별도 pip 패키지로 배포하지 않고 빌드 컨텍스트 공유로 처리합니다.

## 동작 확인 (설계서 §16 Phase 0/1에 해당)

1. `curl http://localhost:8000/health` → `{"status":"ok"}`
2. 프론트엔드에서 짧은 CC 라이선스 유튜브 영상 URL을 넣고 "가져오기" → 곡 정보가 나오는지 확인
   (프록시 없이 실패할 수 있음 — §5.1.3 참고)
3. 짧은 mp3 파일을 업로드 → `studio/[id]` 페이지로 이동 → 자동으로 보컬/MR 분리가 시작되는지 확인
   (CPU라 수 분 소요)
4. 분리가 끝나면 스템 플레이어가 뜨는지, 키 컨트롤로 반음을 조절하고 "적용하고 내보내기"를 눌러
   최종 믹스 다운로드 링크가 나오는지 확인

## 알려진 제약

- Rubber Band CLI는 libsndfile 포맷(WAV/AIFF/FLAC)만 읽고 쓸 수 있어, 그 외 포맷은 ffmpeg으로
  WAV 변환 후 처리합니다 (`services/common/audio_convert.py`).
- `packages/shared-types`에 해당하는 OpenAPI → TypeScript 코드 생성 스텝은 아직 없고,
  `apps/web/lib/types.ts`가 API 스키마를 손으로 맞춰 유지합니다.
- 프론트엔드 npm 감사에 postcss 관련 moderate 취약점 1건이 next의 번들 의존성에 남아있습니다
  (직접 의존성은 패치됨). 빌드 타임 CSS 처리 이슈로 런타임 영향은 없습니다.

## 라이선스

`THIRD_PARTY_LICENSES.md` 참고. 특히 Rubber Band(GPL v2)는 서버 사이드 전용으로만 사용합니다 (§6.1).
