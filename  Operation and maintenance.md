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
docker restart veritex-backend
sleep 10
docker restart veritex-frontend
sleep 10
docker restart veritex-caddy
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
docker pull crpi-l5gw8z003atf7dof.cn-heyuan.personal.cr.aliyuncs.com/veritex/backend:latest

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