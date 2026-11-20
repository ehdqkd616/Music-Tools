// @ts-nocheck
'use client';
// 로그인하지 않은 방문자에게 보여 주는 서비스 소개 홈 화면.
// 내용은 아래 LANDING 객체만 고치면 된다. 스타일은 landing.css(.lp- 접두사)에만 있다.
import './landing.css';

export const LANDING = {
  "icon": "🎧",
  "name": "Studio",
  "tagline": "보컬/MR 분리부터 키 변경까지, 웹에서 쓰는 오디오 작업실",
  "intro": "유튜브 링크나 음원 파일을 넣으면 보컬과 반주를 나누고, 키와 템포를 바꿔서 원하는 형식으로 내보낼 수 있어요.",
  "access": "회원가입 후 관리자 승인을 받으면 사용할 수 있어요.",
  "features": [
    {
      "icon": "🔗",
      "title": "유튜브·파일 가져오기",
      "desc": "유튜브 주소로 음원을 받거나 내 파일을 올려 작업을 시작해요."
    },
    {
      "icon": "🎛️",
      "title": "보컬 / MR 분리",
      "desc": "AI로 노래에서 보컬과 반주(MR)를 따로 뽑아내요."
    },
    {
      "icon": "🎤",
      "title": "보컬·코러스 추출",
      "desc": "보컬 전체, 코러스를 뺀 메인 보컬, 코러스만 각각 받을 수 있어요."
    },
    {
      "icon": "🎼",
      "title": "키·템포 조절",
      "desc": "내 음역에 맞게 키를 바꾸고 속도를 조절한 뒤 MP3·WAV 등으로 내보내요."
    }
  ],
  "steps": [
    "회원가입하고 관리자 승인을 기다려요.",
    "유튜브 링크를 넣거나 음원 파일을 올려요.",
    "스튜디오에서 분리·키 변경을 하고 내보내요."
  ]
};

export default function Landing({ LinkComponent, loginHref = '/login', signupHref = '/signup', className = '', accent }: { LinkComponent?: any; loginHref?: string; signupHref?: string; className?: string; accent?: string }) {
  const L = LinkComponent ?? ((p) => <a href={p.to} className={p.className}>{p.children}</a>);
  const d = LANDING;
  return (
    <div className={`lp ${className}`} style={accent ? { '--lp-accent': accent, '--lp-accent-text': '#0f0f14' } : undefined}>
      <section className="lp-hero">
        <div className="lp-icon" aria-hidden="true">{d.icon}</div>
        <h1 className="lp-title">{d.name}</h1>
        <p className="lp-tagline">{d.tagline}</p>
        {d.intro && <p className="lp-intro">{d.intro}</p>}
        <div className="lp-cta">
          <L to={loginHref} className="lp-btn lp-btn-primary">로그인</L>
          {signupHref && <L to={signupHref} className="lp-btn">{d.signupLabel ?? '회원가입'}</L>}
        </div>
        {d.access && <p className="lp-access">{d.access}</p>}
      </section>

      <section className="lp-section">
        <h2 className="lp-h2">이런 걸 할 수 있어요</h2>
        <ul className="lp-features">
          {d.features.map((f) => (
            <li key={f.title} className="lp-feature">
              <span className="lp-feature-icon" aria-hidden="true">{f.icon}</span>
              <div>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      {d.steps?.length > 0 && (
        <section className="lp-section">
          <h2 className="lp-h2">사용 방법</h2>
          <ol className="lp-steps">
            {d.steps.map((s) => <li key={s}>{s}</li>)}
          </ol>
        </section>
      )}

      <footer className="lp-footer">
        <a href="https://multi-tools.hotgarlic.dedyn.io">다른 프로젝트 둘러보기 →</a>
      </footer>
    </div>
  );
}
