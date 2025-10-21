#!/bin/bash
# Veritex 3.0.5.2 服务器完整更新指令
# 解决浏览器和代理缓存问题

echo "🚀 开始 Veritex 3.0.5.2 完整更新流程..."

# 1. 强制停止并清理现有容器
echo "📦 第一步：清理现有容器..."
docker stop veritex-frontend 2>/dev/null || true
docker rm veritex-frontend 2>/dev/null || true

# 2. 清理Docker镜像缓存
echo "🧹 第二步：清理Docker镜像缓存..."
docker rmi crpi-l5gw8z003atf7dof.cn-heyuan.personal.cr.aliyuncs.com/veritex/frontend:3.0.5.2 2>/dev/null || true
docker system prune -f

# 3. 强制拉取最新镜像（跳过缓存）
echo "📥 第三步：强制拉取最新镜像..."
docker pull --platform linux/amd64 crpi-l5gw8z003atf7dof.cn-heyuan.personal.cr.aliyuncs.com/veritex/frontend:3.0.5.2

# 4. 重新启动前端容器（添加无缓存头）
echo "🚀 第四步：启动新容器..."
docker run -d \
  --name veritex-frontend \
  --restart always \
  -p 80:80 \
  -e NGINX_CACHE_CONTROL="no-cache, no-store, must-revalidate" \
  crpi-l5gw8z003atf7dof.cn-heyuan.personal.cr.aliyuncs.com/veritex/frontend:3.0.5.2

# 5. 验证容器状态
echo "✅ 第五步：验证部署状态..."
sleep 5
docker ps | grep veritex-frontend
docker logs --tail=10 veritex-frontend

# 6. 添加版本验证接口
echo "🔍 第六步：验证版本信息..."
curl -I http://localhost/

echo ""
echo "🎉 服务器更新完成！"
echo ""
echo "📋 用户端清理缓存指令："
echo "1. Chrome: Ctrl+Shift+Delete (选择'所有时间'和'图像和文件')"
echo "2. 或者使用硬刷新: Ctrl+F5"
echo "3. 或者无痕模式访问测试"
echo ""
echo "🔧 如仍有问题，请执行以下代理缓存清理："
echo "mihomo -f /opt/clash/config.yaml -d /opt/clash &"
echo "systemctl restart mihomo"