# 오픈소스 라이선스 고지

이 문서는 `오디오_플랫폼_설계서_v1.0.md` §6의 라이선스 검토를 기준으로 작성되었습니다.
상업화 규모가 커지면 IP 변호사 검토를 권장합니다 (§6.3, §15.3).

## 사용 중인 라이브러리

| 라이브러리 | 용도 | 라이선스 | 비고 |
|---|---|---|---|
| yt-dlp | 유튜브 추출 | Unlicense (PD) | |
| Demucs v4 | 소스 분리 | MIT | |
| PyTorch / torchaudio | ML 런타임 | BSD-3 | CPU 빌드 사용 (§ README 참고) |
| librosa | 오디오 분석 | ISC | |
| pyloudnorm | 라우드니스 측정 | MIT | |
| soundfile / libsndfile | 오디오 I/O | LGPL v2.1 | 동적 링크로 사용 |
| numpy / scipy | 수치 연산 | BSD | |
| FastAPI, SQLAlchemy, Celery, boto3 등 | 백엔드 프레임워크 | MIT / Apache 2.0 / BSD | |
| Next.js, React, WaveSurfer.js, Tailwind CSS | 프론트엔드 | MIT | |

## ⚠️ 주의가 필요한 라이브러리

### Rubber Band Library — GPL v2 또는 상용 이중 라이선스

키 변경(pitch shift)과 템포 조절(time stretch)에 Rubber Band CLI를 별도 프로세스로 호출합니다
(`services/workers/dsp/pitch.py`). 링크하지 않고 subprocess로만 호출합니다.

- **서버 사이드 사용**: 네트워크 서비스로 제공하는 것은 GPL이 말하는 "배포"에 해당하지 않으므로
  소스 공개 의무가 발생하지 않습니다 (AGPL이었다면 발생했을 것입니다). 이 서비스는 서버 사이드
  전용으로만 Rubber Band를 사용합니다.
- **모바일 앱을 만들 경우**: 앱 배포는 GPL의 "배포" 트리거에 해당합니다. 온디바이스 처리를 넣지
  않고 서버 API만 호출하도록 설계되어 있어(§6.1, §11.2) 이 문제를 원천 차단합니다. 앱에서
  온디바이스 처리가 꼭 필요해지면 Rubber Band 상용 라이선스(Breakfast Quay) 구매 또는
  SoundTouch(LGPL)로 교체를 검토해야 합니다.

### FFmpeg — LGPL 2.1+ 기본 / GPL (`--enable-gpl`)

코덱 변환에는 LGPL 빌드만 사용합니다. `--enable-gpl`로 활성화되는 ffmpeg의 rubberband 필터는
사용하지 않고, 대신 Rubber Band CLI를 독립 프로세스로 호출합니다 (§6.2). 두 GPL 컴포넌트를
링크하지 않고 프로세스로 분리합니다.

## 사용하지 않는 라이브러리 (검토 후 제외)

| 라이브러리 | 용도 | 라이선스 | 제외 사유 |
|---|---|---|---|
| Essentia | 키 감지 | AGPL v3 | SaaS 제공 시에도 소스 공개 의무 발생 |
| madmom | 비트 추적 | BSD + 비상업 한정 | 상업적 사용 시 별도 계약 필요 |
| aubio | 오디오 분석 | GPL v3 | 링크 시 전염 |
| KeyFinder | 키 감지 | GPL v3 | 링크 시 전염 |

키/BPM 감지는 대신 librosa(ISC) 기반으로 직접 구현했습니다
(`services/common/analysis.py`, Krumhansl-Schmuckler 프로파일 상관법).

## 체크리스트 (§6.3)

- [x] 이 문서 작성 및 웹사이트에 게시 예정
- [x] Rubber Band GPL 고지 포함
- [x] LGPL 라이브러리(soundfile/libsndfile, ffmpeg)는 동적 링크만 사용
- [ ] 모바일 앱 출시 전 라이선스 재감사 (Phase 3 항목)
- [ ] 상업화 규모 확대 시 IP 변호사 검토 1회
