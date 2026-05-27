#!/bin/bash
# 변경이 있을 때만 pull + 재시작
# cron 등록: */5 * * * * /opt/interactive-stories/deploy/auto-update.sh >> /var/log/auto-update.log 2>&1
APP_DIR="/opt/interactive-stories"

git -C "$APP_DIR" fetch origin main --quiet

LOCAL=$(git -C "$APP_DIR" rev-parse HEAD)
REMOTE=$(git -C "$APP_DIR" rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    exit 0  # 변경 없음 — 재시작 안 함
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 새 커밋 감지: ${LOCAL:0:7} → ${REMOTE:0:7}"
git -C "$APP_DIR" pull --ff-only --quiet
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt" -q
sudo systemctl restart interactive-stories
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 서비스 재시작 완료"