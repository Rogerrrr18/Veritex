#!/bin/bash

# SakuraCat节点连通性测试脚本
# 用于测试所有可用的SakuraCat节点连通性
# 创建时间: 2025-09-15
# 用途: 为多节点负载均衡选择最佳节点

echo "=========================================="
echo "    SakuraCat节点连通性测试工具"
echo "=========================================="
echo "开始时间: $(date)"
echo ""

# 测试函数
test_with_telnet() {
    local server=$1
    local port=$2
    local name=$3
    local sni=$4
    
    echo -n "测试 $name ($server:$port) ... "
    
    # 使用原生TCP连接测试
    timeout 8 bash -c "
        exec 3<>/dev/tcp/$server/$port 2>/dev/null && 
        echo '连接成功' && 
        exec 3>&- || 
        echo '连接失败'
    " 2>/dev/null | grep -q "连接成功"
    
    if [ $? -eq 0 ]; then
        echo "✅ 可用"
        # 记录格式: 服务器:端口:名称:SNI
        echo "$server:$port:$name:$sni" >> /tmp/working_nodes.txt
        return 0
    else
        echo "❌ 失败"
        return 1
    fi
}

# 测试延迟
test_latency() {
    local server=$1
    echo -n "延迟测试 $server ... "
    
    ping_result=$(ping -c 3 -W 2 "$server" 2>/dev/null | grep "time=" | tail -1 | sed 's/.*time=\([0-9.]*\).*/\1/')
    if [ -n "$ping_result" ]; then
        echo "${ping_result}ms"
        return 0
    else
        echo "超时"
        return 1
    fi
}

# 清空结果文件
> /tmp/working_nodes.txt
> /tmp/node_latency.txt

echo "=== 第一阶段：连通性测试 ==="
echo ""

# 测试香港节点
echo "🇭🇰 香港节点测试："
test_with_telnet "sgsQLdsv.catcat321.com" "20038" "香港-IEPL01" "iepl.hkx1.cat.bilibili.com"
test_with_telnet "sgsQLdsv.catcat321.com" "20054" "香港-IEPL02" "iepl.hkx2.cat.bilibili.com"
test_with_telnet "sgsQLdsv.catcat321.com" "20055" "香港-IEPL03" "iepl.hkx3.cat.bilibili.com"
test_with_telnet "R2.tube-cat.com" "9140" "香港-中转03" "hkq2.cat.bilibili.com"
test_with_telnet "R3.tube-cat.com" "9150" "香港-中转02" "hkq1.cat.bilibili.com"

echo ""

# 测试新加坡节点
echo "🇸🇬 新加坡节点测试："
test_with_telnet "sgsQLdsv.catcat321.com" "20067" "新加坡-IEPL01" "iepl.sgx1.cat.bilibili.com"
test_with_telnet "d1.catcat321.com" "49749" "新加坡-IEPL02" "iepl.sgx2.cat.bilibili.com"
test_with_telnet "d1.catcat321.com" "45366" "新加坡-IEPL03" "iepl.sgx3.cat.bilibili.com"
test_with_telnet "R3.tube-cat.com" "9215" "新加坡-中转01" "sgx2.cat.bilibili.com"
test_with_telnet "R2.tube-cat.com" "9215" "新加坡-中转02" "sgx2.cat.bilibili.com"

echo ""

# 测试台湾节点
echo "🇹🇼 台湾节点测试："
test_with_telnet "sgsQLdsv.catcat321.com" "20021" "台湾-IEPL01" "iepl.twx1.cat.bilibili.com"
test_with_telnet "d1.catcat321.com" "43799" "台湾-IEPL02" "iepl.twq1.cat.bilibili.com"
test_with_telnet "R2.tube-cat.com" "9310" "台湾-中转01" "twq1.cat.bilibili.com"
test_with_telnet "R3.tube-cat.com" "9310" "台湾-中转02" "twq1.cat.bilibili.com"

echo ""

# 测试日本节点
echo "🇯🇵 日本节点测试："
test_with_telnet "R2.tube-cat.com" "9405" "日本-中转01" "jpx1.cat.bilibili.com"
test_with_telnet "R1.tube-cat.com" "9405" "日本-中转02" "jpx1.cat.bilibili.com"
test_with_telnet "sgsQLdsv.catcat321.com" "20005" "日本-IEPL01" "iepl.jpx1.cat.bilibili.com"
test_with_telnet "d1.catcat321.com" "43402" "日本原生-IEPL01" "iepl.jphq1.cat.bilibili.com"

echo ""

# 测试美国节点
echo "🇺🇸 美国节点测试："
test_with_telnet "d1.catcat321.com" "47704" "美国-IEPL01" "iepl.usq1.cat.bilibili.com"
test_with_telnet "d1.catcat321.com" "42834" "美国-IEPL02" "iepl.usq2.cat.bilibili.com"
test_with_telnet "R2.tube-cat.com" "8300" "美国-中转01" "usq1.cat.bilibili.com"
test_with_telnet "R2.tube-cat.com" "8210" "美国-隧道01" "us.catxstar.com"

echo ""
echo "=== 第二阶段：延迟测试 ==="
echo ""

# 对可用节点进行延迟测试
if [ -s /tmp/working_nodes.txt ]; then
    echo "对可用节点进行延迟测试："
    while IFS=: read -r server port name sni; do
        echo -n "$name ($server) ... "
        ping_result=$(ping -c 3 -W 2 "$server" 2>/dev/null | grep "time=" | tail -1 | sed 's/.*time=\([0-9.]*\).*/\1/')
        if [ -n "$ping_result" ]; then
            echo "${ping_result}ms"
            echo "$server:$port:$name:$sni:$ping_result" >> /tmp/node_latency.txt
        else
            echo "延迟测试失败"
            echo "$server:$port:$name:$sni:999" >> /tmp/node_latency.txt
        fi
    done < /tmp/working_nodes.txt
fi

echo ""
echo "=========================================="
echo "           测试结果汇总"
echo "=========================================="

if [ -s /tmp/working_nodes.txt ]; then
    total_nodes=$(wc -l < /tmp/working_nodes.txt)
    echo "✅ 发现 $total_nodes 个可用节点："
    echo ""
    
    # 显示所有可用节点
    echo "所有可用节点列表："
    cat /tmp/working_nodes.txt | while IFS=: read -r server port name sni; do
        echo "  - $name: $server:$port (SNI: $sni)"
    done
    
    echo ""
    
    # 如果有延迟数据，按延迟排序显示推荐节点
    if [ -s /tmp/node_latency.txt ]; then
        echo "推荐节点（按延迟排序）："
        sort -t: -k5 -n /tmp/node_latency.txt | head -5 | while IFS=: read -r server port name sni latency; do
            echo "  🌟 $name: $server:$port (${latency}ms)"
        done
        
        echo ""
        echo "多节点负载均衡建议："
        echo "选择以下 3-5 个延迟最低的节点用于负载均衡配置"
        
        # 生成Xray配置建议
        echo ""
        echo "=== Xray配置建议 ==="
        echo "最佳的5个节点配置参数："
        sort -t: -k5 -n /tmp/node_latency.txt | head -5 | while IFS=: read -r server port name sni latency; do
            echo "节点: $name"
            echo "  地址: $server"
            echo "  端口: $port"
            echo "  SNI: $sni"
            echo "  延迟: ${latency}ms"
            echo ""
        done
    fi
    
else
    echo "❌ 未发现任何可用节点"
    echo "建议检查："
    echo "  1. 网络连接是否正常"
    echo "  2. 防火墙设置是否正确"
    echo "  3. SakuraCat订阅是否有效"
fi

echo "=========================================="
echo "测试完成时间: $(date)"
echo "结果文件:"
echo "  - 可用节点: /tmp/working_nodes.txt"
echo "  - 延迟数据: /tmp/node_latency.txt"
echo "=========================================="