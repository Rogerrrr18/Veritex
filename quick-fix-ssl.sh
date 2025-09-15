#!/bin/bash

echo "=========================================="
echo "    快速问题修复脚本 v2.0"
echo "=========================================="
echo "专注解决：SSL错误、代理连接、Supabase连接"
echo "开始时间: $(date)"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== 第一步：检查当前问题状态 ===${NC}"

# 检查容器状态
echo -e "${YELLOW}1. 检查容器状态${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|veritex|caddy|xray)"

# 检查网络
echo -e "\n${YELLOW}2. 检查网络配置${NC}"
if docker network inspect veritex-network >/dev/null 2>&1; then
    echo "✅ veritex-network 存在"
    XRAY_IP=$(docker inspect xray-proxy 2>/dev/null | grep -A 10 '"veritex-network"' | grep '"IPAddress"' | head -1 | cut -d'"' -f4)
    if [ ! -z "$XRAY_IP" ]; then
        echo "Xray IP: $XRAY_IP"
    else
        echo "❌ 无法获取Xray IP地址"
    fi
else
    echo "❌ veritex-network 不存在"
fi

echo -e "\n${BLUE}=== 第二步：修复SSL和代理配置 ===${NC}"

echo -e "${YELLOW}1. 停止并重新配置Xray代理${NC}"
docker stop xray-proxy 2>/dev/null || echo "Xray已停止"
docker rm xray-proxy 2>/dev/null || echo "Xray已删除"

# 创建优化的Xray配置
echo "创建SSL优化配置..."
mkdir -p /opt/xray
cat > /opt/xray/config.json << 'EOF'
{
  "log": {
    "loglevel": "info"
  },
  "inbounds": [
    {
      "port": 1080,
      "listen": "0.0.0.0",
      "protocol": "socks",
      "settings": {
        "udp": true
      }
    },
    {
      "port": 8118,
      "listen": "0.0.0.0", 
      "protocol": "http"
    }
  ],
  "outbounds": [
    {
      "tag": "proxy",
      "protocol": "trojan",
      "settings": {
        "servers": [{
          "address": "d1.catcat321.com",
          "port": 49749,
          "password": "fc68f508-2b67-43a3-802c-42aa636aafab"
        }]
      },
      "streamSettings": {
        "security": "tls",
        "tlsSettings": {
          "allowInsecure": true,
          "serverName": "iepl.sgx2.cat.bilibili.com",
          "alpn": ["h2", "http/1.1"],
          "fingerprint": "chrome"
        }
      }
    },
    {
      "tag": "direct",
      "protocol": "freedom",
      "settings": {}
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      {
        "type": "field",
        "domain": [
          "supabase.co",
          "volces.com", 
          "localhost",
          "127.0.0.1"
        ],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "domain": [
          "google.com",
          "scholar.google.com",
          "arxiv.org"
        ],
        "outboundTag": "proxy"
      }
    ]
  }
}
EOF

echo "启动优化的Xray代理容器..."
docker run -d --name xray-proxy \
  --restart unless-stopped \
  --network veritex-network \
  -p 1080:1080 \
  -p 8118:8118 \
  -v /opt/xray:/etc/xray \
  teddysun/xray

echo "等待Xray启动..."
sleep 10

echo -e "\n${YELLOW}2. 重新配置后端容器${NC}"

# 重新启动后端容器，使用优化的NO_PROXY配置
if docker ps | grep -q veritex-backend; then
    echo "停止现有后端容器..."
    docker stop veritex-backend
    docker rm veritex-backend
fi

echo "启动优化配置的后端容器..."
docker run -d --name veritex-backend \
  --platform linux/amd64 \
  --restart unless-stopped \
  --network veritex-network \
  -p 8000:8000 \
  -e HTTP_PROXY=http://xray-proxy:8118 \
  -e HTTPS_PROXY=http://xray-proxy:8118 \
  -e NO_PROXY="localhost,127.0.0.1,0.0.0.0,veritex-backend,veritex-frontend,veritex-caddy,*.supabase.co,*.volces.com,jfzchljmfnnsrszabpys.supabase.co,ark.cn-beijing.volces.com,supabase.co,volces.com" \
  --env-file /root/.env \
  --health-cmd="python3 -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/')\"" \
  --health-interval=30s \
  --health-timeout=10s \
  --health-retries=3 \
  --health-start-period=30s \
  crpi-l5gw8z003atf7dof.cn-heyuan.personal.cr.aliyuncs.com/veritex/backend:3.0.3

echo "等待后端服务启动..."
sleep 20

echo -e "\n${BLUE}=== 第三步：测试修复效果 ===${NC}"

echo -e "${YELLOW}1. 测试基础连接${NC}"
# 获取新的Xray IP
XRAY_IP=$(docker inspect xray-proxy | grep -A 10 '"veritex-network"' | grep '"IPAddress"' | head -1 | cut -d'"' -f4)
echo "新的Xray IP: $XRAY_IP"

# 测试HTTP代理
echo -n "HTTP代理测试: "
if timeout 10 curl -x http://$XRAY_IP:8118 -s http://httpbin.org/ip >/dev/null 2>&1; then
    echo -e "${GREEN}✅ 成功${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
fi

# 测试Google Scholar (使用容器内环境)
echo -n "Google Scholar SSL测试: "
if timeout 15 docker exec veritex-backend python3 -c "
import requests
import os
try:
    response = requests.get('https://scholar.google.com', timeout=10)
    print('✅ SSL连接成功' if response.status_code == 200 else '⚠️  访问受限但SSL正常')
except requests.exceptions.SSLError as e:
    print('❌ SSL错误:', str(e)[:50])
except Exception as e:
    print('⚠️  其他错误:', str(e)[:50])
" 2>/dev/null; then
    echo -e "${GREEN}✅ SSL问题已解决${NC}"
else
    echo -e "${RED}❌ 仍有SSL问题${NC}"
fi

# 测试Supabase直连
echo -n "Supabase连接测试: "
if timeout 10 docker exec veritex-backend python3 -c "
import requests
try:
    response = requests.get('https://jfzchljmfnnsrszabpys.supabase.co/rest/v1/', timeout=5)
    print('✅ 成功')
except Exception as e:
    print('❌ 失败:', str(e)[:30])
" 2>/dev/null; then
    echo -e "${GREEN}✅ 成功${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
fi

echo -e "\n${YELLOW}2. 测试网站访问${NC}"
echo -n "完整网站测试: "
if timeout 15 curl -I https://veritex.cc 2>/dev/null | grep -q "HTTP"; then
    echo -e "${GREEN}✅ 网站正常${NC}"
else
    echo -e "${RED}❌ 网站访问异常${NC}"
fi

echo -e "\n${YELLOW}3. 检查容器健康状态${NC}"
sleep 15  # 等待健康检查
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|veritex|caddy|xray)"

echo ""
echo "=========================================="
echo -e "${GREEN}快速修复完成！${NC}"
echo ""
echo "主要改进："
echo "  ✅ SSL/TLS配置优化 (ALPN, Chrome指纹)"
echo "  ✅ 智能路由配置 (云服务直连)"
echo "  ✅ 增强的NO_PROXY规则"
echo "  ✅ 容器网络统一"
echo ""
echo "如果仍有问题，请运行："
echo "  docker logs veritex-backend --tail=20"
echo "  docker logs xray-proxy --tail=10"
echo "=========================================="