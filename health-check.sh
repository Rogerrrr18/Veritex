#!/bin/bash

# Veritex 系统健康检查脚本
# 用途：日常监控、问题排查、性能检测

echo "============================================="
echo "     Veritex 系统健康检查报告"
echo "============================================="
echo "检查时间: $(date)"
echo "服务器: $(hostname) ($(uname -m))"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m'

# 健康状态计数
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

# 检查函数
check_status() {
    local name="$1"
    local command="$2"
    local expected="$3"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    echo -n "检查 $name: "
    
    if eval "$command" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ 正常${NC}"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        echo -e "${RED}❌ 异常${NC}"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        return 1
    fi
}

check_warning() {
    local name="$1"
    local command="$2"
    
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    echo -n "检查 $name: "
    
    result=$(eval "$command" 2>/dev/null)
    if [ ! -z "$result" ]; then
        echo -e "${GREEN}✅ $result${NC}"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        echo -e "${YELLOW}⚠️ 需要注意${NC}"
        WARNING_CHECKS=$((WARNING_CHECKS + 1))
        return 1
    fi
}

echo -e "${BLUE}=== 1. 基础系统检查 ===${NC}"

# 系统资源
echo "系统资源状态："
echo -n "  磁盘使用率: "
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    echo -e "${GREEN}${DISK_USAGE}% ✅${NC}"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
elif [ "$DISK_USAGE" -lt 90 ]; then
    echo -e "${YELLOW}${DISK_USAGE}% ⚠️${NC}"
    WARNING_CHECKS=$((WARNING_CHECKS + 1))
else
    echo -e "${RED}${DISK_USAGE}% ❌ 危险${NC}"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

echo -n "  内存使用率: "
MEMORY_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ "$MEMORY_USAGE" -lt 80 ]; then
    echo -e "${GREEN}${MEMORY_USAGE}% ✅${NC}"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo -e "${YELLOW}${MEMORY_USAGE}% ⚠️${NC}"
    WARNING_CHECKS=$((WARNING_CHECKS + 1))
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

echo -n "  Docker服务: "
if systemctl is-active docker >/dev/null 2>&1; then
    echo -e "${GREEN}✅ 运行中${NC}"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo -e "${RED}❌ 未运行${NC}"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

echo ""
echo -e "${BLUE}=== 2. 容器服务检查 ===${NC}"

# 检查关键容器
containers=("veritex-backend" "veritex-frontend" "veritex-caddy" "xray-proxy")
for container in "${containers[@]}"; do
    check_status "$container 容器" "docker ps | grep -q $container"
done

# 检查容器健康状态
echo ""
echo "容器详细状态："
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|veritex|caddy|xray)"

echo ""
echo -e "${BLUE}=== 3. 网络连通性检查 ===${NC}"

# 检查网络配置
check_status "Docker网络配置" "docker network inspect veritex-network >/dev/null"

# 获取Xray IP
if docker ps | grep -q xray-proxy; then
    XRAY_IP=$(docker inspect xray-proxy 2>/dev/null | grep -A 10 '"veritex-network"' | grep '"IPAddress"' | head -1 | cut -d'"' -f4)
    if [ ! -z "$XRAY_IP" ]; then
        echo "  Xray代理IP: $XRAY_IP"
        
        # 测试代理连接
        check_status "HTTP代理连接" "timeout 10 curl -x http://$XRAY_IP:8118 -s http://httpbin.org/ip"
        check_status "代理到Google Scholar" "timeout 15 curl -x http://$XRAY_IP:8118 -I -s https://scholar.google.com | grep -q HTTP"
    else
        echo -e "${RED}❌ 无法获取Xray IP地址${NC}"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    fi
else
    echo -e "${RED}❌ Xray代理容器未运行${NC}"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
fi

# 检查外部服务连通性
check_status "Supabase服务" "timeout 10 curl -s https://jfzchljmfnnsrszabpys.supabase.co/rest/v1/"
check_status "网站HTTPS访问" "timeout 15 curl -I -s https://veritex.cc | grep -q HTTP"

echo ""
echo -e "${BLUE}=== 4. 服务间通信检查 ===${NC}"

# 检查服务间通信
if docker ps | grep -q veritex-frontend && docker ps | grep -q veritex-backend; then
    check_status "前端→后端通信" "timeout 10 docker exec veritex-frontend curl -s http://veritex-backend:8000/ >/dev/null"
fi

if docker ps | grep -q veritex-backend; then
    check_status "后端服务响应" "timeout 10 curl -s http://localhost:8000/ >/dev/null"
fi

echo ""
echo -e "${BLUE}=== 5. 性能指标检查 ===${NC}"

# Docker容器资源使用
echo "容器资源使用情况："
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" | head -6

# 端口监听检查
echo ""
echo "关键端口监听状态："
ports=("80" "443" "8000" "1080" "8118")
for port in "${ports[@]}"; do
    echo -n "  端口 $port: "
    if netstat -tlnp 2>/dev/null | grep -q ":$port "; then
        service=$(netstat -tlnp 2>/dev/null | grep ":$port " | awk '{print $7}' | cut -d'/' -f2 | head -1)
        echo -e "${GREEN}✅ 监听中 ($service)${NC}"
    else
        echo -e "${RED}❌ 未监听${NC}"
    fi
done

echo ""
echo -e "${BLUE}=== 6. 日志健康检查 ===${NC}"

# 检查最近的错误日志
echo "最近的错误日志 (最多显示3条)："
containers_for_logs=("veritex-backend" "xray-proxy" "veritex-caddy")
for container in "${containers_for_logs[@]}"; do
    if docker ps | grep -q "$container"; then
        echo "  $container:"
        error_logs=$(docker logs "$container" --since="1h" 2>&1 | grep -i -E "(error|fail|exception)" | tail -2)
        if [ ! -z "$error_logs" ]; then
            echo "$error_logs" | sed 's/^/    /'
        else
            echo -e "    ${GREEN}无严重错误${NC}"
        fi
    fi
done

echo ""
echo -e "${BLUE}=== 7. 建议和告警 ===${NC}"

# 根据检查结果给出建议
if [ "$FAILED_CHECKS" -gt 0 ]; then
    echo -e "${RED}⚠️  发现 $FAILED_CHECKS 个严重问题，建议立即处理：${NC}"
    if ! docker ps | grep -q xray-proxy; then
        echo "  • 运行修复脚本: ./quick-fix-ssl.sh"
    fi
    if [ "$DISK_USAGE" -gt 90 ]; then
        echo "  • 清理磁盘空间: docker system prune -f"
    fi
    echo "  • 查看详细日志: docker logs veritex-backend --tail=20"
fi

if [ "$WARNING_CHECKS" -gt 0 ]; then
    echo -e "${YELLOW}⚠️  发现 $WARNING_CHECKS 个需要关注的项目${NC}"
fi

if [ "$PASSED_CHECKS" -eq "$TOTAL_CHECKS" ]; then
    echo -e "${GREEN}🎉 系统运行正常，所有检查通过！${NC}"
fi

echo ""
echo "============================================="
echo "健康检查总结:"
echo -e "  总检查项: $TOTAL_CHECKS"
echo -e "  通过: ${GREEN}$PASSED_CHECKS${NC}"
echo -e "  警告: ${YELLOW}$WARNING_CHECKS${NC}"
echo -e "  失败: ${RED}$FAILED_CHECKS${NC}"
echo ""

# 计算健康分数
HEALTH_SCORE=$(( (PASSED_CHECKS * 100) / TOTAL_CHECKS ))
echo -n "系统健康分数: "
if [ "$HEALTH_SCORE" -ge 90 ]; then
    echo -e "${GREEN}$HEALTH_SCORE% 优秀${NC}"
elif [ "$HEALTH_SCORE" -ge 70 ]; then
    echo -e "${YELLOW}$HEALTH_SCORE% 良好${NC}"
else
    echo -e "${RED}$HEALTH_SCORE% 需要改进${NC}"
fi

echo ""
echo "检查完成时间: $(date)"
echo "============================================="

# 生成简要报告文件
cat > /tmp/veritex-health-report.txt << EOF
Veritex 系统健康检查报告
检查时间: $(date)
健康分数: $HEALTH_SCORE%
总检查项: $TOTAL_CHECKS (通过: $PASSED_CHECKS, 警告: $WARNING_CHECKS, 失败: $FAILED_CHECKS)
EOF

echo "💾 详细报告已保存到: /tmp/veritex-health-report.txt"