FROM nginx:alpine

COPY http-only.conf /etc/nginx/http-only.conf
COPY https.conf.template /etc/nginx/https.conf.template
COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
