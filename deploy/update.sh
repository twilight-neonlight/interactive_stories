#!/bin/bash
# 서버에서 최신 코드로 업데이트할 때 실행
# 실행: bash /opt/interactive-stories/deploy/update.sh

set -e
APP_DIR="/opt/interactive-stories"

echo "=== 코드 업데이트 ==="
git -C "$APP_DIR" pull

echo "=== 의존성 업데이트 ==="
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt" -q

echo "=== 서비스 재시작 ==="
sudo systemctl restart interactive-stories
sudo systemctl status interactive-stories --no-pager