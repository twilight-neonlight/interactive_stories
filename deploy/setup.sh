#!/bin/bash
# Oracle Cloud (Ubuntu 22.04) 초기 서버 설정 스크립트
# 실행: bash setup.sh <도메인명>  (예: bash setup.sh stories.example.com)
# 도메인 없이 IP만 쓸 경우: bash setup.sh  (SSL 설정 건너뜀)

set -e
DOMAIN="${1:-}"
APP_DIR="/opt/interactive-stories"
APP_USER="stories"

echo "=== 1. 시스템 패키지 업데이트 ==="
sudo apt-get update && sudo apt-get upgrade -y

echo "=== 2. Python 3.11, nginx, certbot 설치 ==="
sudo apt-get install -y python3.11 python3.11-venv python3-pip nginx certbot python3-certbot-nginx git

echo "=== 3. 앱 사용자 생성 ==="
sudo useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER" || true

echo "=== 4. 앱 디렉터리 설정 ==="
sudo mkdir -p "$APP_DIR"
sudo chown "$APP_USER:$APP_USER" "$APP_DIR"

echo "=== 5. 코드 복제 (또는 pull) ==="
if [ -d "$APP_DIR/.git" ]; then
  sudo -u "$APP_USER" git -C "$APP_DIR" pull
else
  sudo -u "$APP_USER" git clone https://github.com/YOUR_USERNAME/interactive_stories.git "$APP_DIR"
fi

echo "=== 6. Python 가상환경 및 의존성 ==="
sudo -u "$APP_USER" python3.11 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

echo "=== 7. data 디렉터리 생성 ==="
sudo -u "$APP_USER" mkdir -p "$APP_DIR/backend/data"

echo "=== 8. .env 파일 설정 ==="
if [ ! -f "$APP_DIR/backend/.env" ]; then
  echo "⚠️  $APP_DIR/backend/.env 파일이 없습니다. 아래 내용으로 생성해주세요:"
  echo ""
  echo "GOOGLE_API_KEY=your_gemini_api_key_here"
  echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
  echo "INVITE_CODE=your_invite_code_here"
  echo ""
  echo ".env 파일 생성 후 다시 스크립트를 실행하거나 서비스를 시작하세요."
fi

echo "=== 9. systemd 서비스 설치 ==="
sudo cp "$APP_DIR/deploy/interactive-stories.service" /etc/systemd/system/
sudo sed -i "s|/opt/interactive-stories|$APP_DIR|g" /etc/systemd/system/interactive-stories.service
sudo systemctl daemon-reload
sudo systemctl enable interactive-stories

echo "=== 10. nginx 설정 ==="
sudo cp "$APP_DIR/deploy/nginx.conf" /etc/nginx/sites-available/interactive-stories
if [ -n "$DOMAIN" ]; then
  sudo sed -i "s/YOUR_DOMAIN/$DOMAIN/g" /etc/nginx/sites-available/interactive-stories
fi
sudo ln -sf /etc/nginx/sites-available/interactive-stories /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

if [ -n "$DOMAIN" ]; then
  echo "=== 11. SSL 인증서 발급 (Let's Encrypt) ==="
  sudo certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m admin@"$DOMAIN"
fi

echo ""
echo "=== 설정 완료 ==="
echo "1. $APP_DIR/backend/.env 파일에 API 키를 입력하세요."
echo "2. sudo systemctl start interactive-stories"
echo "3. sudo systemctl status interactive-stories"
if [ -n "$DOMAIN" ]; then
  echo "4. 접속: https://$DOMAIN"
else
  echo "4. 접속: http://$(curl -s ifconfig.me)"
fi
