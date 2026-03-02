#!/usr/bin/env bash
# =============================================================================
# Claw Agents Provisioner -- Let's Encrypt Initial Certificate Generation
# =============================================================================
# Generates real TLS certificates from Let's Encrypt for production use.
# Replaces the self-signed dev certificates created during Docker build.
#
# Prerequisites:
#   - Domain DNS A record pointing to this server's public IP
#   - Ports 80 and 443 open in firewall
#   - Docker and docker compose installed
#
# Usage:
#   ./scripts/init-letsencrypt.sh <domain> [email]
#
# Examples:
#   ./scripts/init-letsencrypt.sh claw.example.com admin@example.com
#   ./scripts/init-letsencrypt.sh claw.example.com  # uses --register-unsafely-without-email
#
# =============================================================================
set -euo pipefail

# -----------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------
DOMAIN="${1:-}"
EMAIL="${2:-}"
STAGING="${LETSENCRYPT_STAGING:-0}"  # Set to 1 for testing (avoids rate limits)
COMPOSE_FILE="docker-compose.production.yml"
NGINX_SERVICE="nginx-proxy"
DATA_PATH="./data/certbot"

# -----------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------
if [ -z "$DOMAIN" ]; then
    echo ""
    echo "  ERROR: Domain name is required."
    echo ""
    echo "  Usage: $0 <domain> [email]"
    echo "  Example: $0 claw.example.com admin@example.com"
    echo ""
    exit 1
fi

echo ""
echo "  ============================================"
echo "  Let's Encrypt Certificate Setup"
echo "  ============================================"
echo "  Domain:  $DOMAIN"
echo "  Email:   ${EMAIL:-<not provided>}"
echo "  Staging: ${STAGING}"
echo "  ============================================"
echo ""

# -----------------------------------------------------------------------
# Create required directories
# -----------------------------------------------------------------------
echo "  [1/5] Creating directories..."
mkdir -p "$DATA_PATH/conf"
mkdir -p "$DATA_PATH/www"

# -----------------------------------------------------------------------
# Download recommended TLS parameters
# -----------------------------------------------------------------------
echo "  [2/5] Downloading recommended TLS parameters..."
if [ ! -e "$DATA_PATH/conf/options-ssl-nginx.conf" ]; then
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf \
        > "$DATA_PATH/conf/options-ssl-nginx.conf"
fi

if [ ! -e "$DATA_PATH/conf/ssl-dhparams.pem" ]; then
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem \
        > "$DATA_PATH/conf/ssl-dhparams.pem"
fi

# -----------------------------------------------------------------------
# Create dummy certificate (so nginx can start)
# -----------------------------------------------------------------------
echo "  [3/5] Creating temporary self-signed certificate..."
CERT_PATH="$DATA_PATH/conf/live/$DOMAIN"
mkdir -p "$CERT_PATH"

if [ ! -e "$CERT_PATH/fullchain.pem" ]; then
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout "$CERT_PATH/privkey.pem" \
        -out "$CERT_PATH/fullchain.pem" \
        -subj "/CN=$DOMAIN" 2>/dev/null
fi

# -----------------------------------------------------------------------
# Start nginx with dummy certificate
# -----------------------------------------------------------------------
echo "  [4/5] Starting nginx for ACME challenge..."
docker compose -f "$COMPOSE_FILE" --profile production up -d "$NGINX_SERVICE"

# Wait for nginx to be ready
sleep 5

# Remove dummy certificate
rm -rf "$CERT_PATH"

# -----------------------------------------------------------------------
# Request real certificate from Let's Encrypt
# -----------------------------------------------------------------------
echo "  [5/5] Requesting certificate from Let's Encrypt..."

STAGING_FLAG=""
if [ "$STAGING" = "1" ]; then
    STAGING_FLAG="--staging"
    echo "         (Using staging environment -- certificate will NOT be trusted)"
fi

EMAIL_FLAG="--register-unsafely-without-email"
if [ -n "$EMAIL" ]; then
    EMAIL_FLAG="--email $EMAIL"
fi

docker compose -f "$COMPOSE_FILE" --profile production run --rm certbot \
    certonly --webroot \
    --webroot-path=/var/www/certbot \
    $STAGING_FLAG \
    $EMAIL_FLAG \
    --domain "$DOMAIN" \
    --agree-tos \
    --no-eff-email \
    --force-renewal

# -----------------------------------------------------------------------
# Reload nginx with real certificate
# -----------------------------------------------------------------------
echo ""
echo "  Reloading nginx with new certificate..."
docker compose -f "$COMPOSE_FILE" --profile production exec "$NGINX_SERVICE" nginx -s reload

echo ""
echo "  ============================================"
echo "  Certificate installed successfully!"
echo "  ============================================"
echo "  Domain:     https://$DOMAIN"
echo "  Cert path:  $DATA_PATH/conf/live/$DOMAIN/"
echo "  Auto-renew: Enabled (daily cron in nginx container)"
echo "  ============================================"
echo ""
echo "  NOTE: Update nginx/conf.d/default.conf to set:"
echo "    server_name $DOMAIN;"
echo "    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;"
echo "    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;"
echo ""
echo "  Then restart: docker compose -f $COMPOSE_FILE --profile production restart $NGINX_SERVICE"
echo ""
