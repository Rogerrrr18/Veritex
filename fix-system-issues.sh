#!/bin/bash

echo "==========================================="
echo "    Veritex 系统问题诊断和修复工具"
echo "==========================================="
echo "开始时间: $(date)"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 第一阶段：系统状态诊断
echo -e "${BLUE}=== 第一阶段：系统状态诊断 ===${NC}"
echo ""

echo -e "${YELLOW}1. 检查所有容器状态${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|veritex|caddy|xray)"

echo -e "\n${YELLOW}2. 检查网络配置${NC}"
echo "当前网络列表："
docker network ls | grep veritex

echo -e "\n检查veritex-network详细信息："
if docker network inspect veritex-network >/dev/null 2>&1; then
    echo "✅ veritex-network 存在"
    docker network inspect veritex-network | grep -A 20 "Containers" | head -25
else
    echo "❌ veritex-network 不存在，需要创建"
fi

echo -e "\n${YELLOW}3. 检查代理容器状态${NC}"
if docker ps | grep -q xray-proxy; then
    echo "✅ xray-proxy 容器运行中"
    XRAY_IP=$(docker inspect xray-proxy | grep -A 10 '"veritex-network"' | grep '"IPAddress"' | head -1 | cut -d'"' -f4)
    echo "Xray代理IP: $XRAY_IP"
    
    # 测试代理连接
    echo -n "测试代理连接: "
    if curl -x http://$XRAY_IP:8118 -s http://httpbin.org/ip --connect-timeout 5 >/dev/null 2>&1; then
        echo -e "${GREEN}✅ 代理工作正常${NC}"
    else
        echo -e "${RED}❌ 代理连接失败${NC}"
    fi
    
    # 检查代理日志
    echo -e "\nXray代理日志 (最新10条):"
    docker logs xray-proxy --tail=10
else
    echo -e "${RED}❌ xray-proxy 容器未运行${NC}"
fi

echo -e "\n${YELLOW}4. 检查后端容器环境变量${NC}"
if docker ps | grep -q veritex-backend; then
    echo "后端容器代理配置："
    docker exec veritex-backend env | grep -E "(PROXY|proxy)" || echo "未找到代理环境变量"
else
    echo -e "${RED}❌ veritex-backend 容器未运行${NC}"
fi

echo -e "\n${YELLOW}5. 测试关键服务连通性${NC}"

# 测试Supabase连接
echo -n "Supabase连接测试: "
if curl -s "https://jfzchljmfnnsrszabpys.supabase.co/rest/v1/" --connect-timeout 10 >/dev/null 2>&1; then
    echo -e "${GREEN}✅ 正常${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
fi

# 测试豆包API连接
echo -n "豆包API连接测试: "
if curl -s "https://ark.cn-beijing.volces.com" --connect-timeout 10 >/dev/null 2>&1; then
    echo -e "${GREEN}✅ 正常${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
fi

# 测试Google Scholar (通过代理)
if [ ! -z "$XRAY_IP" ]; then
    echo -n "Google Scholar代理测试: "
    if curl -x http://$XRAY_IP:8118 -s "https://scholar.google.com" --connect-timeout 15 | grep -q "scholar" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ 正常${NC}"
    else
        echo -e "${RED}❌ 失败${NC}"
    fi
fi

echo ""
echo -e "${BLUE}=== 第二阶段：问题修复 ===${NC}"
echo ""

# 修复1：重新创建统一网络
echo -e "${YELLOW}修复1: 确保统一网络配置${NC}"
if ! docker network inspect veritex-network >/dev/null 2>&1; then
    echo "创建 veritex-network..."
    docker network create veritex-network
fi

# 确保所有容器都在统一网络中
for container in veritex-backend veritex-frontend veritex-caddy xray-proxy; do
    if docker ps -q -f name=$container >/dev/null; then
        echo "将 $container 连接到 veritex-network..."
        docker network connect veritex-network $container 2>/dev/null || echo "$container 已在网络中"
    fi
done

# 修复2：重新配置代理
echo -e "\n${YELLOW}修复2: 修复代理配置${NC}"

# 检查并重启xray代理
if ! docker ps | grep -q xray-proxy; then
    echo "启动Xray代理容器..."
    
    # 确保配置文件存在
    mkdir -p /opt/xray
    
    # 创建最新的工作配置
    cat > /opt/xray/config.json << 'EOF'
{
  "log": {
    "loglevel": "info"
  },
  "inbounds": [
    {
      "port": 1080,
      "listen": "0.0.0.0",
      "protocol": "socks"
    },
    {
      "port": 8118,
      "listen": "0.0.0.0",
      "protocol": "http"
    }
  ],
  "outbounds": [
    {
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
          "serverName": "iepl.sgx2.cat.bilibili.com"
        }
      }
    }
  ]
}
EOF

    docker run -d --name xray-proxy \
      --restart unless-stopped \
      --network veritex-network \
      -p 1080:1080 \
      -p 8118:8118 \
      -v /opt/xray:/etc/xray \
      teddysun/xray

    echo "等待Xray启动..."
    sleep 10
fi

# 修复3：重新配置后端容器环境变量
echo -e "\n${YELLOW}修复3: 修复后端代理环境变量${NC}"

# 停止后端容器准备重新配置
if docker ps | grep -q veritex-backend; then
    echo "重新配置后端容器..."
    docker stop veritex-backend
    docker rm veritex-backend
    
    # 重新启动后端容器（优化的代理配置）
    docker run -d --name veritex-backend \
      --platform linux/amd64 \
      --restart unless-stopped \
      --network veritex-network \
      -p 8000:8000 \
      -e HTTP_PROXY=http://xray-proxy:8118 \
      -e HTTPS_PROXY=http://xray-proxy:8118 \
      -e NO_PROXY="localhost,127.0.0.1,0.0.0.0,veritex-frontend,veritex-caddy,*.supabase.co,*.volces.com,jfzchljmfnnsrszabpys.supabase.co,ark.cn-beijing.volces.com" \
      --env-file /root/.env \
      --health-cmd="python3 -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/')\"" \
      --health-interval=30s \
      --health-timeout=10s \
      --health-retries=3 \
      --health-start-period=30s \
      crpi-l5gw8z003atf7dof.cn-heyuan.personal.cr.aliyuncs.com/veritex/backend:3.0.3

    echo "等待后端服务启动..."
    sleep 20
fi

echo ""
echo -e "${BLUE}=== 第三阶段：验证修复效果 ===${NC}"
echo ""

echo -e "${YELLOW}1. 检查容器状态${NC}"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|veritex|caddy|xray)"

echo -e "\n${YELLOW}2. 测试代理功能${NC}"
XRAY_IP=$(docker inspect xray-proxy | grep -A 10 '"veritex-network"' | grep '"IPAddress"' | head -1 | cut -d'"' -f4)
echo "代理IP: $XRAY_IP"

# 测试HTTP代理
echo -n "HTTP代理测试: "
if curl -x http://$XRAY_IP:8118 -s http://httpbin.org/ip --connect-timeout 10 >/dev/null; then
    echo -e "${GREEN}✅ 成功${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
fi

# 测试HTTPS通过代理
echo -n "HTTPS代理测试: "
if curl -x http://$XRAY_IP:8118 -s -I https://scholar.google.com --connect-timeout 15 | grep -q "HTTP" >/dev/null; then
    echo -e "${GREEN}✅ 成功${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
fi

echo -e "\n${YELLOW}3. 测试服务间通信${NC}"

# 测试前端到后端
echo -n "前端→后端通信: "
if docker exec veritex-frontend curl -s http://veritex-backend:8000/ --connect-timeout 5 >/dev/null 2>&1; then
    echo -e "${GREEN}✅ 成功${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
fi

# 测试后端健康检查
echo -n "后端健康检查: "
if curl -s http://localhost:8000/ --connect-timeout 5 >/dev/null; then
    echo -e "${GREEN}✅ 成功${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
fi

echo -e "\n${YELLOW}4. 测试网站访问${NC}"
echo -n "完整网站测试: "
if curl -I https://veritex.cc --connect-timeout 15 | grep -q "HTTP" >/dev/null 2>&1; then
    echo -e "${GREEN}✅ 成功${NC}"
else
    echo -e "${RED}❌ 失败${NC}"
fi

echo ""
echo "==========================================="
echo -e "${GREEN}修复完成！${NC}"
echo "如果还有问题，请检查具体的错误日志："
echo "  docker logs veritex-backend --tail=20"
echo "  docker logs xray-proxy --tail=20"
echo "  docker logs veritex-caddy --tail=20"
echo "==========================================="