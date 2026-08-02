# Cloud Run frontend image: build the static bundle, serve it with Caddy on
# $PORT (Cloud Run injects this). Talks to the backend Cloud Run service
# cross-origin via VITE_API_BASE, baked in at build time (Vite env vars are
# build-time only, not runtime) — pass it with:
#   docker build --build-arg VITE_API_BASE=https://<backend-url>/api .

FROM node:20-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_API_BASE
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
COPY Caddyfile.container /etc/caddy/Caddyfile
EXPOSE 8080
