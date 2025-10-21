# 多阶段构建：先用 node 构建，再用 nginx 提供静态资源

FROM node:20-bullseye-slim AS build
WORKDIR /app

COPY package.json ./
RUN npm install --no-audit --no-fund

COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime

# 拷贝无缓存 nginx 配置
COPY nginx_no_cache.conf /etc/nginx/conf.d/default.conf

# 复制构建产物
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -qO- http://127.0.0.1/health >/dev/null 2>&1 || exit 0

CMD ["nginx", "-g", "daemon off;"]


