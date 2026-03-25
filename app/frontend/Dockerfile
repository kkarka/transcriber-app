# ---------- Build Stage ----------
FROM node:18-alpine AS builder

WORKDIR /app

RUN npm install -g pnpm

COPY frontend/package*.json frontend/pnpm-lock.yaml* ./
# Use ci for faster, cleaner, deterministic builds in automated pipelines
RUN pnpm install --frozen-lockfile

COPY frontend .
RUN pnpm run build

# ---------- Runtime Stage ----------
# Use the official unprivileged image. It runs as user 'nginx' (UID 101) by default.
FROM nginxinc/nginx-unprivileged:alpine

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

# Copy the built React/Vue app
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]