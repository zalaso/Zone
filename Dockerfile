# Local container only. No provider SDKs/credentials or private worlds in the image.
FROM node:22-alpine AS web
WORKDIR /web
RUN npm install --global pnpm@10.28.0
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src ./src
COPY frontend/scripts/check-source.mjs frontend/scripts/check-bundle.mjs ./scripts/
RUN pnpm lint && pnpm build && pnpm check:bundle

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLBACKEND=Agg MPLCONFIGDIR=/tmp/zone-mpl ZONE_ENV=local
WORKDIR /app
COPY pyproject.toml README.md LICENSE constraints-ci.txt ./
COPY hidden_lab ./hidden_lab
RUN pip install --no-cache-dir -c constraints-ci.txt '.[backend]' \
    && groupadd --gid 10001 zone \
    && useradd --uid 10001 --gid zone --no-create-home zone \
    && mkdir /data && chown zone:zone /data
COPY --from=web /web/dist ./web
USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8765/health/ready', timeout=3).close()"
ENTRYPOINT ["python", "-m", "hidden_lab"]
CMD ["serve", "--db", "/data/zone.sqlite3", "--host", "0.0.0.0", "--container-local", "--web-dir", "/app/web"]
