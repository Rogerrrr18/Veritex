# Veritex 网站运维指南

## 1. 日常监控

### 检查服务状态
```bash
# 检查所有容器状态
docker ps -a | grep veritex

# 查看容器资源使用
docker stats --no-stream

# 检查磁盘空间
df -h
```

### 查看日志
```bash
# 实时查看各服务日志
docker logs -f --tail=200 veritex-backend
docker logs -f --tail=200 veritex-frontend
docker logs -f --tail=200 veritex-caddy

# 查看最近错误
docker logs --tail=100 veritex-backend | grep -i error
```

## 2. SSL证书管理

### 证书自动续期
Caddy会自动续期，但需要监控：
```bash
# 检查证书有效期
openssl s_client -servername veritex.cc -connect veritex.cc:443 2>/dev/null | openssl x509 -noout -dates

# 强制续期（如有问题）
docker restart veritex-caddy
```

## 3. 备份策略

### 数据库备份
Supabase云端已保护，但建议定期检查：
```bash
# 检查重要配置文件
cp /tmp/Caddyfile /root/backups/Caddyfile.$(date +%Y%m%d)

# 备份Docker配置
docker inspect veritex-backend > /root/backups/backend-config.$(date +%Y%m%d).json
```

### 定期快照
- 在阿里云控制台设置ECS实例自动快照
- 建议每天自动快照，保留7天

## 4. 性能优化

### 监控资源使用
```bash
# 系统资源监控
htop
free -h
iostat -x 1

# 检查网络连接
netstat -tnlp | grep -E ':80|:443|:8000'
```

### 清理Docker资源
```bash
# 清理未使用的镜像和容器（每周执行）
docker system prune -f

# 清理日志（防止占用过多空间）
docker logs veritex-backend 2>/dev/null | wc -l
```

## 5. 安全维护

### 系统更新
```bash
# 定期更新系统（每月）
yum update -y

# 检查安全漏洞
docker scan veritex-backend
```

### 防火墙检查
```bash
# 验证只开放必要端口
ss -tlnp | grep -E ':80|:443|:8000|:22'

# 检查异常连接
netstat -an | grep ESTABLISHED | wc -l
```

## 6. 故障排查

### 常见问题处理

#### 1. 网站无法访问
```bash
# 检查顺序
curl -I https://veritex.cc  # 测试连通性
docker ps -a | grep veritex  # 检查容器状态
docker logs veritex-caddy --tail=20  # 查看代理日志
```

#### 2. 502错误
```bash
# 重启顺序很重要
na
```

#### 3. SSL证书问题
```bash
# 检查证书状态
docker logs veritex-caddy | grep -i certificate

# 重新申请证书
docker stop veritex-caddy
docker rm veritex-caddy
# 重新部署caddy容器
```

## 7. 监控告警设置

### 简单监控脚本
创建 `/root/check-website.sh`:
```bash
#!/bin/bash
if ! curl -f -s https://veritex.cc > /dev/null; then
    echo "$(date): Website down!" >> /var/log/website-check.log
    # 可以配置邮件通知
fi
```

### 定时任务：
```bash
# 每5分钟检查一次
crontab -e
*/5 * * * * /root/check-website.sh
```

## 8. 更新部署

### 安全更新流程
```bash
# 1. 备份当前状态
docker export veritex-backend > backup-backend-$(date +%Y%m%d).tar

# 2. 拉取新镜像
    - 后端: docker pull crpi-l5gw8z003atf7dof.cn-heyuan.personal.cr.aliyuncs.com/veritex/backend:3.0.1
    - 前端: docker pull crpi-l5gw8z003atf7dof.cn-heyuan.personal.cr.aliyuncs.com/veritex/frontend:3.0.1
# 3. 滚动更新（避免服务中断）
docker stop veritex-backend
docker run -d --name veritex-backend-new ...
# 测试通过后删除旧容器
```

## 9. 成本优化

### 阿里云资源监控
- 定期检查ECS使用率，避免资源浪费
- 监控流量费用，设置告警阈值
- 考虑使用CDN加速静态资源

### Docker资源限制
```bash
# 为容器设置资源限制
docker update --memory=512m veritex-backend
docker update --cpus=1 veritex-frontend
```

## 10. 应急联系清单

### 保存重要信息：
- 阿里云账号和密码
- 域名注册商信息
- Docker镜像仓库访问凭据
- 数据库连接信息
- SSL证书申请邮箱：yhr180414@163.com

### 快速恢复命令：
```bash
# 一键重启所有服务
docker restart veritex-backend veritex-frontend veritex-caddy

# 紧急情况下的服务检查
curl -I https://veritex.cc && echo "网站正常" || echo "网站异常"
```

---

## 运维时间表建议

- **每天**: 检查服务状态、查看错误日志
- **每周**: 清理Docker资源、检查磁盘空间
- **每月**: 系统更新、安全检查、备份验证
- **每季度**: 性能优化、成本分析

> **记住：监控比修复更重要，预防性维护能避免大部分问题！**

---

## 快速命令参考

```bash
# 服务状态检查
docker ps -a | grep veritex
curl -I https://veritex.cc

# 查看日志
docker logs -f --tail=200 veritex-backend
docker logs -f --tail=200 veritex-frontend
docker logs -f --tail=200 veritex-caddy

# 重启服务
docker restart veritex-backend veritex-frontend veritex-caddy

# 系统监控
htop
df -h
free -h

# 网络检查
ss -tlnp | grep -E ':80|:443|:8000'
```

---

## 应急处理流程

1. **发现问题** → 执行快速检查命令
2. **定位问题** → 查看相关日志
3. **尝试重启** → 按顺序重启相关服务
4. **验证恢复** → 测试网站访问
5. **记录问题** → 更新运维日志

**紧急联系**: 47.117.247.166 (服务器IP)
**网站域名**: https://veritex.cc
**服务器实例**: iZuf68g76f80bqsuucvv3zZ

##关于代理配置
太好了！我来详细解释代理成功配置的完整过程和原理：

  🎯 代理配置成功的关键步骤

  步骤1：从订阅链接获取节点信息

  # 你的SakuraCat订阅链接解码后得到trojan节点
  trojan://fc68f508-2b67-43a3-802c-42aa636aafab@R3.tube-cat.com:9120

  解析出的关键信息：
  - 协议：trojan
  - 密码：fc68f508-2b67-43a3-802c-42aa636aafab
  - 服务器：R3.tube-cat.com
  - 端口：9120
  - SNI：hkx1.cat.bilibili.com

  步骤2：Docker容器化部署Xray

  # 使用Docker运行xray代理
  docker run -d --name xray-proxy \
    --restart unless-stopped \
    -p 1080:1080 \  # SOCKS5代理端口
    -p 8118:8118 \  # HTTP代理端口
    -v /opt/xray:/etc/xray \  # 配置文件挂载
    teddysun/xray

  步骤3：创建Xray配置文件

  {
    "inbounds": [
      {
        "port": 1080,
        "listen": "0.0.0.0",  // 监听所有接口
        "protocol": "socks"   // 提供SOCKS5代理
      },
      {
        "port": 8118,
        "listen": "0.0.0.0",  // 监听所有接口
        "protocol": "http"    // 提供HTTP代理
      }
    ],
    "outbounds": [
      {
        "protocol": "trojan",  // 使用trojan协议连接SakuraCat
        "settings": {
          "servers": [{
            "address": "R3.tube-cat.com",
            "port": 9120,
            "password": "fc68f508-2b67-43a3-802c-42aa636aafab"
          }]
        },
        "streamSettings": {
          "security": "tls",
          "tlsSettings": {
            "allowInsecure": true,
            "serverName": "hkx1.cat.bilibili.com"
          }
        }
      }
    ]
  }

  步骤4：配置Docker容器使用代理

  # 后端容器添加代理环境变量
  docker run -d --name veritex-backend \
    -e HTTP_PROXY=http://172.19.0.1:8118 \   # Docker网桥IP
    -e HTTPS_PROXY=http://172.19.0.1:8118 \
    -e NO_PROXY=localhost,127.0.0.1,veritex-frontend,veritex-caddy \
    # 其他配置...

  🔧 技术原理详解

  1. 网络架构图

  Internet请求 → Veritex后端 → Docker网桥 → Xray代理 → SakuraCat服务器 → Google Scholar
       ↑              ↑              ↑           ↑              ↑              ↑
     用户访问      容器内应用      172.19.0.1   协议转换    trojan加密     目标网站

  2. Docker网络原理

  # Docker默认创建bridge网络
  docker network ls
  # veritex-net: 172.19.0.0/16
  # bridge: 172.17.0.0/16

  # 容器间通信
  veritex-backend (172.19.0.4) → 172.19.0.1:8118 (宿主机) → xray-proxy容器

  3. 代理协议转换

  HTTP请求 → xray容器(HTTP:8118) → trojan协议加密 → SakuraCat服务器 → 解密 → Google Scholar
  HTTPS请求 → xray容器(SOCKS5:1080) → trojan协议加密 → SakuraCat服务器 → 解密 → Google Scholar

  4. 环境变量生效原理

  # Python应用自动读取代理环境变量
  import os
  import requests

  # 系统自动应用这些环境变量
  proxies = {
      'http': os.getenv('HTTP_PROXY'),
      'https': os.getenv('HTTPS_PROXY')
  }

  # requests库自动使用代理
  response = requests.get('https://scholar.google.com', proxies=proxies)

  ✅ 成功的关键因素

  1. 容器网络隔离

  # 只有后端容器使用代理，前端和caddy不受影响
  -e NO_PROXY=localhost,127.0.0.1,veritex-frontend,veritex-caddy

  2. 端口映射正确

  # 宿主机端口映射到容器
  -p 1080:1080  # SOCKS5
  -p 8118:8118  # HTTP

  3. TLS配置匹配

  {
    "tlsSettings": {
      "allowInsecure": true,  // 允许不安全连接
      "serverName": "hkx1.cat.bilibili.com"  // SNI伪装
    }
  }

  4. 重启顺序正确

  # 先启动代理 → 再启动使用代理的应用
  docker start xray-proxy
  sleep 5
  docker start veritex-backend

  🎯 为什么代理成功了？

  验证成功的证据：

  1. HTTP/1.1 200 OK - Google Scholar正常响应
  2. Server: scholar - 真实的Google服务器
  3. 后端日志无超时错误 - 网络连接正常
  4. 多源搜索引擎初始化成功 - 代理生效

  流量路径：

  用户搜索 → Caddy(443) → Frontend(80) → Backend(8000) → Xray(8118) → SakuraCat → Google Scholar
     ↓                                      ↑
  直连阿里云                               走代理访问


🚀 标准DevOps流程设计                                                                                                            │ │
│ │                                                                                                                                  │ │
│ │ 阶段1：本地开发和测试                                                                                                            │ │
│ │                                                                                                                                  │ │
│ │ - 代码修改：在IDE中修改前后端代码                                                                                                │ │
│ │ - 本地测试：使用npm run dev(前端) + python backend.py(后端)                                                                      │ │
│ │ - 单元测试：运行测试套件验证功能                                                                                                 │ │
│ │ - 本地Docker测试：构建镜像进行容器化测试                                                                                         │ │
│ │                                                                                                                                  │ │
│ │ 阶段2：版本控制和CI                                                                                                              │ │
│ │                                                                                                                                  │ │
│ │ - Git提交：代码推送到指定分支(如beta2)                                                                                           │ │
│ │ - 自动触发CI：GitHub Actions或GitLab CI自动构建                                                                                  │ │
│ │ - 多架构构建：同时构建amd64和arm64镜像                                                                                           │ │
│ │ - 自动测试：运行完整测试套件                                                                                                     │ │
│ │                                                                                                                                  │ │
│ │ 阶段3：镜像构建和推送                                                                                                            │ │
│ │                                                                                                                                  │ │
│ │ - Docker构建：使用多阶段构建优化镜像大小                                                                                         │ │
│ │ - 镜像标签规范：使用语义化版本(如v1.2.3, latest)                                                                                 │ │
│ │ - 推送到镜像仓库：统一推送到阿里云容器镜像服务                                                                                   │ │
│ │ - 安全扫描：检查镜像漏洞                                                                                                         │ │
│ │                                                                                                                                  │ │
│ │ 阶段4：部署和验证                                                                                                                │ │
│ │                                                                                                                                  │ │
│ │ - 拉取最新镜像：服务器自动或手动拉取                                                                                             │ │
│ │ - 滚动更新：无停机更新服务                                                                                                       │ │
│ │ - 健康检查：验证服务正常运行                                                                                                     │ │
│ │ - 回滚机制：出问题时快速回退                                                                                                     │ │
│ │                                                                                                                                  │ │
│ │ 🛠️ 具体实施方案                                                                                                                 │ │
│ │                                                                                                                                  │ │
│ │ 1. 创建标准化构建脚本                                                                                                            │ │
│ │                                                                                                                                  │ │
│ │ - build.sh：本地构建脚本                                                                                                         │ │
│ │ - deploy.sh：部署脚本                                                                                                            │ │
│ │ - docker-compose.yml：服务编排文件                                                                                               │ │
│ │                                                                                                                                  │ │
│ │ 2. 建立CI/CD流水线                                                                                                               │ │
│ │                                                                                                                                  │ │
│ │ - GitHub Actions工作流                                                                                                           │ │
│ │ - 自动化测试和构建                                                                                                               │ │
│ │ - 多环境部署(开发、测试、生产)                                                                                                   │ │
│ │                                                                                                                                  │ │
│ │ 3. 镜像版本管理规范                                                                                                              │ │
│ │                                                                                                                                  │ │
│ │ - 使用Git标签触发版本构建                                                                                                        │ │
│ │ - 语义化版本控制(SemVer)                                                                                                         │ │
│ │ - 明确的latest标签策略                                                                                                           │ │
│ │                                                                                                                                  │ │
│ │ 4. 监控和日志体系                                                                                                                │ │
│ │                                                                                                                                  │ │
│ │ - 应用性能监控(APM)                                                                                                              │ │
│ │ - 集中化日志管理                                                                                                                 │ │
│ │ - 告警通知机制                                                                                                                   │ │
│ │                                                                                                                                  │ │
│ │ 💡 解决当前问题的优先级                                                                                                          │ │
│ │                                                                                                                                  │ │
│ │ 高优先级：                                                                                                                       │ │
│ │ 1. 创建docker-compose.yml统一管理服务                                                                                            │ │
│ │ 2. 建立标准的构建和部署脚本                                                                                                      │ │
│ │ 3. 清理和规范镜像标签                                                                                                            │ │
│ │                                                                                                                                  │ │
│ │ 中优先级：                                                                                                                       │ │
│ │ 1. 建立CI/CD流水线                                                                                                               │ │
│ │ 2. 添加自动化测试                                                                                                                │ │
│ │ 3. 实施健康检查和监控                                                                                                            │ │
│ │                                                                                                                                  │ │
│ │ 低优先级：                                                                                                                       │ │
│ │ 1. 多环境部署策略                                                                                                                │ │
│ │ 2. 高可用架构优化                                                                                                                │ │
│ │ 3. 性能调优                                                                                                                      │ │
│ ╰────────────────────────

---

## 🔄 代理重新配置命令集

### 完整代理重新部署流程

#### 1. 停止现有容器
```bash
# 停止现有的Xray代理容器（如果存在）
docker stop xray-proxy 2>/dev/null || echo '容器不存在'
docker rm xray-proxy 2>/dev/null || echo '容器不存在'

# 停止后端容器准备重新配置
docker stop veritex-backend 2>/dev/null || echo '后端容器不存在'
```

#### 2. 创建Xray配置文件
```bash
# 创建Xray配置目录
mkdir -p /opt/xray

# 创建配置文件
cat > /opt/xray/config.json << 'EOF'
{
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
          "address": "R3.tube-cat.com",
          "port": 9120,
          "password": "fc68f508-2b67-43a3-802c-42aa636aafab"
        }]
      },
      "streamSettings": {
        "security": "tls",
        "tlsSettings": {
          "allowInsecure": true,
          "serverName": "hkx1.cat.bilibili.com"
        }
      }
    }
  ]
}
EOF

echo '✅ Xray配置文件已创建'
```

#### 3. 部署Xray代理容器
```bash
# 拉取Xray镜像并运行代理容器
docker pull teddysun/xray:latest

# 启动Xray代理容器
docker run -d --name xray-proxy \
  --restart unless-stopped \
  -p 1080:1080 \
  -p 8118:8118 \
  -v /opt/xray:/etc/xray \
  teddysun/xray

echo '✅ Xray代理容器已启动'

# 等待5秒让容器完全启动
sleep 5

# 检查容器状态
docker ps | grep xray-proxy
```

#### 4. 配置后端容器（使用代理）
```bash
# 重新启动Veritex后端容器，添加代理环境变量
# 注意：请根据实际的镜像名称和网络配置调整以下命令

# 方法1：如果使用docker run启动
docker run -d --name veritex-backend \
  --restart unless-stopped \
  -p 8000:8000 \
  -e HTTP_PROXY=http://172.19.0.1:8118 \
  -e HTTPS_PROXY=http://172.19.0.1:8118 \
  -e NO_PROXY=localhost,127.0.0.1,veritex-frontend,veritex-caddy \
  --env-file .env \
  crpi-l5gw8z003atf7dof.cn-heyuan.personal.cr.aliyuncs.com/veritex/backend:3.0.3

# 方法2：如果使用docker-compose，需要修改docker-compose.yml文件添加：
# environment:
#   HTTP_PROXY: http://172.19.0.1:8118
#   HTTPS_PROXY: http://172.19.0.1:8118
#   NO_PROXY: localhost,127.0.0.1,veritex-frontend,veritex-caddy

echo '✅ 后端容器配置完成'
```

#### 5. 测试代理连接
```bash
# 测试代理连接的命令

# 1. 检查Xray容器日志
echo '=== 检查Xray容器日志 ==='
docker logs xray-proxy --tail=20

echo -e '\n=== 测试HTTP代理连接 ==='
# 2. 测试HTTP代理是否工作
curl -x http://127.0.0.1:8118 -I https://scholar.google.com --connect-timeout 10

echo -e '\n=== 测试SOCKS5代理连接 ==='
# 3. 测试SOCKS5代理（需要安装curl的socks支持）
curl --socks5 127.0.0.1:1080 -I https://scholar.google.com --connect-timeout 10

echo -e '\n=== 检查代理端口监听状态 ==='
# 4. 检查端口是否正确监听
netstat -tlnp | grep -E ':1080|:8118'

echo '✅ 代理测试完成'
```

#### 6. 重启完整Veritex服务
```bash
# 重启完整Veritex服务的正确顺序

# 1. 确保代理服务正常运行
echo '=== 检查代理容器状态 ==='
docker ps | grep xray-proxy

# 2. 按正确顺序重启服务
echo -e '\n=== 重启服务顺序 ==='
echo '步骤1: 启动/确认Xray代理'
docker start xray-proxy 2>/dev/null || echo 'Xray已运行'

echo '步骤2: 等待5秒确保代理稳定'
sleep 5

echo '步骤3: 启动后端（带代理配置）'
docker start veritex-backend

echo '步骤4: 启动前端'
docker start veritex-frontend 2>/dev/null || echo '前端需要单独启动'

echo '步骤5: 启动Caddy代理'
docker start veritex-caddy 2>/dev/null || echo 'Caddy需要单独启动'

# 3. 最终验证
echo -e '\n=== 最终验证 ==='
docker ps | grep veritex  # 检查所有服务状态
curl -I https://veritex.cc  # 测试网站访问

echo '✅ 服务重启完成'
```

### 🚨 重要注意事项

1. **执行环境**: 这些命令需要在阿里云服务器上以root权限执行
2. **启动顺序**: 必须严格按照 Xray → 后端 → 前端 → Caddy 的顺序启动
3. **网络配置**: 确保Docker网桥IP为172.19.0.1，如不同请相应调整
4. **凭据安全**: SakuraCat凭据已配置，如需更新请修改config.json文件

### 📋 快速重启脚本

如需要快速重新部署，可以创建脚本文件：

```bash
#!/bin/bash
# 文件名: redeploy-proxy.sh

echo "🚀 开始重新部署代理服务..."

# 执行上述所有步骤
# （此处可以将上面的命令整合成一个完整脚本）

echo "✅ 代理服务重新部署完成！"
```

使用方法：
```bash
chmod +x redeploy-proxy.sh
./redeploy-proxy.sh
```

---

## 🔍 SakuraCat节点测试工具

### 节点连通性测试脚本

项目中包含专用的节点测试工具：`test-sakura-nodes.sh`

#### 使用方法：
```bash
# 给脚本执行权限
chmod +x test-sakura-nodes.sh

# 运行完整的节点测试
./test-sakura-nodes.sh

# 查看测试结果
cat /tmp/working_nodes.txt    # 可用节点列表
cat /tmp/node_latency.txt     # 延迟测试结果
```

#### 脚本功能：
1. **全面节点测试** - 测试所有地区的SakuraCat节点
2. **连通性检查** - 使用原生TCP连接测试
3. **延迟测量** - 对可用节点进行ping延迟测试
4. **智能排序** - 按延迟自动排序推荐最佳节点
5. **配置建议** - 生成Xray多节点配置参数

#### 测试覆盖：
- 🇭🇰 **香港节点** (IEPL + 中转线路)
- 🇸🇬 **新加坡节点** (IEPL + 中转线路)  
- 🇹🇼 **台湾节点** (IEPL + 中转线路)
- 🇯🇵 **日本节点** (普通 + 原生 + IEPL线路)
- 🇺🇸 **美国节点** (IEPL + 中转 + 隧道线路)

#### 输出示例：
```
✅ 发现 6 个可用节点：

推荐节点（按延迟排序）：
  🌟 香港-IEPL01: sgsQLdsv.catcat321.com:20038 (45.2ms)
  🌟 新加坡-IEPL02: d1.catcat321.com:49749 (52.8ms)
  🌟 香港-中转03: R2.tube-cat.com:9140 (48.1ms)
```

#### 故障排查：
如果所有节点都失败，检查：
```bash
# 1. 安装必要工具
yum install -y telnet nc

# 2. 检查基础网络
ping -c 3 8.8.8.8

# 3. 检查DNS解析
nslookup sgsQLdsv.catcat321.com

# 4. 检查防火墙规则
iptables -L OUTPUT | grep -E "(REJECT|DROP)"
```

### 🔄 基于测试结果的多节点配置

根据节点测试结果，选择延迟最低的3-5个节点配置多节点负载均衡：

#### 配置更新流程：
1. 运行 `./test-sakura-nodes.sh` 获取最佳节点
2. 根据结果更新 `/opt/xray/config.json`
3. 重启Xray容器应用新配置
4. 验证负载均衡效果

#### 推荐节点选择策略：
- **主力节点**: 选择延迟最低的2-3个IEPL线路
- **备用节点**: 选择不同服务器的中转线路
- **地域分布**: 优先香港、新加坡节点（大陆访问速度较快）