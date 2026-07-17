export default function DmcaPage() {
  return (
    <div className="space-y-4 text-sm leading-relaxed">
      <h1 className="text-xl font-semibold">DMCA / 저작권 신고</h1>
      <p className="text-white/70">
        Studio는 사용자가 업로드하거나 요청한 콘텐츠를 일시적으로 처리하는 도구이며, 처리 결과물은
        24시간 후 자동 삭제됩니다 (§15.2). 저작권 침해가 의심되는 콘텐츠를 발견하신 경우 아래 정보와
        함께 신고해 주세요.
      </p>
      <ul className="list-disc pl-5 text-white/70 space-y-1">
        <li>침해되었다고 주장하는 저작물에 대한 설명</li>
        <li>문제가 되는 콘텐츠의 URL 또는 식별 정보</li>
        <li>신고인의 연락처 및 권리자 확인 정보</li>
      </ul>
      <p className="text-white/50 text-xs">
        지정 대리인(designated agent) 연락처는 서비스 정식 운영 시 이 페이지에 게시됩니다. 24시간
        내 처리를 목표로 합니다.
      </p>
    </div>
  );
}
