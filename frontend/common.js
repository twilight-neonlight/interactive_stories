// 준비 중 알림 토스트
function showComingSoon(label) {
  const toast = document.createElement('div');
  toast.innerHTML = `<strong>${label}</strong>은(는) 아직 준비 중입니다`;
  Object.assign(toast.style, {
    position: 'fixed', bottom: '32px', left: '50%',
    transform: 'translateX(-50%) translateY(8px)',
    background: 'var(--bg-primary)', border: '1px solid var(--border-strong)',
    borderRadius: '8px', padding: '11px 22px',
    fontFamily: "'Noto Serif KR',serif", fontSize: '13px',
    color: 'var(--text-secondary)',
    boxShadow: '0 4px 18px rgba(0,0,0,0.10)',
    opacity: '0', transition: 'opacity 0.22s, transform 0.22s',
    zIndex: '300', whiteSpace: 'nowrap',
  });
  document.body.appendChild(toast);
  requestAnimationFrame(() => {
    toast.style.opacity = '1';
    toast.style.transform = 'translateX(-50%) translateY(0)';
  });
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(-50%) translateY(8px)';
    setTimeout(() => toast.remove(), 300);
  }, 2300);
}
