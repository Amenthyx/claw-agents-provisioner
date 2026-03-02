# =============================================================================
# Claw Agents Provisioner -- Nginx TLS Reverse Proxy
# =============================================================================
# Nginx with certbot for Let's Encrypt auto-renewal.
# Generates DH params and self-signed certs at build time for dev use.
# Replace with real certs via init-letsencrypt.sh for production.
# =============================================================================

FROM nginx:1.25-alpine

# Install certbot and openssl
RUN apk add --no-cache \
    certbot \
    certbot-nginx \
    openssl \
    bash \
    curl

# Create directories
RUN mkdir -p /etc/nginx/ssl \
             /var/www/certbot \
             /etc/letsencrypt \
             /var/log/nginx

# Generate DH parameters (2048-bit -- takes ~30s at build time)
RUN openssl dhparam -out /etc/nginx/ssl/dhparam.pem 2048

# Generate self-signed certificate for development / initial startup
# Production deployments should run init-letsencrypt.sh to replace these
RUN openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/privkey.pem \
    -out /etc/nginx/ssl/fullchain.pem \
    -subj "/C=US/ST=State/L=City/O=Claw/OU=Dev/CN=localhost"

# Copy nginx configuration
COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/conf.d/ /etc/nginx/conf.d/

# Create certbot renewal cron script
RUN echo '#!/bin/sh' > /etc/periodic/daily/certbot-renew && \
    echo 'certbot renew --quiet --deploy-hook "nginx -s reload" 2>&1 | tee -a /var/log/nginx/certbot-renew.log' >> /etc/periodic/daily/certbot-renew && \
    chmod +x /etc/periodic/daily/certbot-renew

# Custom entrypoint that starts crond for cert renewal + nginx
RUN echo '#!/bin/sh' > /docker-entrypoint-custom.sh && \
    echo 'set -e' >> /docker-entrypoint-custom.sh && \
    echo '# Start cron daemon for certbot auto-renewal' >> /docker-entrypoint-custom.sh && \
    echo 'crond -b -l 8' >> /docker-entrypoint-custom.sh && \
    echo '# Start nginx in foreground' >> /docker-entrypoint-custom.sh && \
    echo 'exec nginx -g "daemon off;"' >> /docker-entrypoint-custom.sh && \
    chmod +x /docker-entrypoint-custom.sh

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -sf http://localhost:80/ || exit 1

ENTRYPOINT ["/docker-entrypoint-custom.sh"]
