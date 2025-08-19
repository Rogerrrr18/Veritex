FROM node:20-bullseye-slim AS build
WORKDIR /app

# 仅复制依赖清单以最大化缓存利用
# 注意：不复制 package-lock.json，避免 npm 在 CI 环境中错误跳过 rollup 的可选依赖安装
COPY package.json ./
RUN npm install --include=optional --no-audit --progress=false

# 复制源码并构建
COPY . .
RUN npm run build


FROM nginx:1.27-alpine AS runtime

# 拷贝自定义 nginx 配置（包含 SPA 回退与 API 反代）
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 清理默认站点并拷贝静态文件
RUN rm -rf /usr/share/nginx/html/*
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]


