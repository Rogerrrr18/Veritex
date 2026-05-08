# 多阶段构建：先用 node 构建，再用 nginx 提供静态资源

# 允许覆盖基础镜像，规避 docker.io 网络问题
ARG BASE_IMAGE_NODE=node:20-bullseye-slim
ARG BASE_IMAGE_NGINX=nginx:1.27-alpine

FROM ${BASE_IMAGE_NODE} AS build
WORKDIR /app

# 可配置 NPM 镜像源，默认使用 npmmirror 加速
ARG NPM_REGISTRY=https://registry.npmmirror.com

COPY package.json ./
RUN npm config set registry ${NPM_REGISTRY} \
  && npm install --no-audit --no-fund

COPY . .
RUN npm run build

# ========== 运行时（Nginx） ==========
FROM ${BASE_IMAGE_NGINX} AS runtime

# 允许选择 nginx 配置文件（默认无缓存配置，可在构建时用 --build-arg NGINX_CONF=nginx.conf 切换到带后端代理的配置）
ARG NGINX_CONF=nginx_no_cache.conf
COPY ${NGINX_CONF} /etc/nginx/conf.d/default.conf

# 复制构建产物
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -qO- http://127.0.0.1/health >/dev/null 2>&1 || exit 0

CMD ["nginx", "-g", "daemon off;"]

# ========== 运行时（Node 静态服务） ==========
FROM ${BASE_IMAGE_NODE} AS runtime-node
WORKDIR /app

# 允许使用镜像源安装静态服务器
ARG NPM_REGISTRY=https://registry.npmmirror.com
RUN npm config set registry ${NPM_REGISTRY} \
  && npm install -g serve --no-audit --no-fund

# 复制构建产物
COPY --from=build /app/dist /app/dist

EXPOSE 3000

CMD ["serve", "-s", "dist", "-l", "3000"]

# ========== 运行时（Python http.server，使用预编译 dist） ==========
FROM python:3.11-slim AS runtime-python
WORKDIR /app

# 直接从构建上下文复制 dist（需确保未被 .dockerignore 忽略）
COPY dist /app/dist

EXPOSE 3000
CMD ["python", "-m", "http.server", "3000", "--directory", "dist"]
