FROM node:22-alpine AS client-builder
WORKDIR /client
COPY client/package.json client/package-lock.json ./
RUN npm install -g npm@11.18.0 && npm ci --legacy-peer-deps
COPY client/ .
RUN npm run build

FROM python:3.13-slim AS server-base
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY server/pyproject.toml ./
RUN uv sync --no-dev
COPY server/ .

FROM server-base AS production
COPY --from=client-builder /client/dist /app/client/dist
ENV APP_ENV=production
ENV CLIENT_DIST_PATH=client/dist
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM server-base AS dev
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
