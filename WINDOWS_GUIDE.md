# CampusPilot Windows 快速使用指南

## ✅ 问题已修复！

**你遇到的问题原因：**
- 旧版 `deploy.bat` 调用 Bash 脚本时，CMD 无法正确处理 UTF-8 编码和特殊字符
- 导致中文乱码、命令被截断、换行符解析错误

**解决方案：** 已重写为 **100% 纯 Windows Batch 实现**，完全不依赖 Bash

---

## 🚀 立即开始（3 步）

### 第 1 步：启动本地开发环境
```bash
双击运行: start-dev.bat
```
或命令行：
```cmd
start-dev.bat
```

**将自动完成：**
- ✓ 检测 Python 环境
- ✓ 创建虚拟环境（如需要）
- ✓ 安装所有依赖
- ✓ 启动后端 API (http://localhost:8000)
- ✓ 启动前端界面 (http://localhost:3000)

---

### 第 2 步：运行测试
```bash
双击运行: deploy.bat
选择: [1] Run Tests
```
或命令行：
```cmd
deploy.bat 1
```

**测试内容：**
- 后端单元测试（pytest）
- 数据库模型验证
- API 接口测试
- 配置模块测试

---

### 第 3 步：部署到服务器（首次需配置 SSH）

#### 📌 首次配置 SSH 密钥
```bash
deploy.bat
选择: [2] Setup SSH Keys (First Time)
```

**向导会引导你：**

1. **生成密钥对** - 自动创建 RSA 4096 位密钥
   - 私钥位置：`C:\Users\你的用户名\.ssh\campuspilot_deploy`
   - 公钥会显示在屏幕上（需要复制到服务器）

2. **输入服务器信息**
   ```
   Server IP or domain: 123.45.67.89      ← 你的服务器 IP
   SSH username (default: root): root       ← 用户名
   SSH port (default: 22): 22               ← 端口
   ```

3. **部署公钥到服务器**
   - 如果安装了 Git for Windows → 自动使用 `ssh-copy-id`
   - 否则 → 显示手动操作指引

4. **测试连接** - 自动验证 SSH 是否可用

**配置保存位置：** `deploy.config` 文件（可手动编辑）

---

#### 📌 正式部署
```bash
deploy.bat
选择: [3] Deploy to Server
```

**自动执行流程：**
1. 检查 SSH 连接
2. 上传代码（排除 node_modules 等）
3. 上传 .env 配置文件（权限 600）
4. 在服务器构建 Docker 镜像
5. 启动服务（docker-compose up）
6. 健康检查（最多等待 60 秒）

**成功后显示：**
```
===========================================
     DEPLOYMENT COMPLETED
===========================================
Access URLs:
  Backend API: http://123.45.67.89:8000/docs
  Frontend:    http://123.45.67.89
  Health:      http://123.45.67.89:8000/health
```

---

## 📋 所有可用命令

| 菜单选项 | 命令行参数 | 功能说明 |
|---------|-----------|----------|
| **[1]** | `deploy.bat 1` 或 `deploy.bat test` | 运行自动化测试 |
| **[2]** | `deploy.bat 2` 或 `deploy.bat setup` | SSH 密钥配置向导 |
| **[3]** | `deploy.bat 3` 或 `deploy.bat deploy` | 完整部署到服务器 |
| **[4]** | `deploy.bat 4` 或 `deploy.bat status` | 查看服务器状态和日志 |
| **[5]** | `deploy.bat 5` 或 `deploy.bat logs` | 查看实时日志流 |
| **[6]** | `deploy.bat 6` 或 `deploy.bat rollback` | 回滚到上一版本 |
| **[7]** | `deploy.bat 7` 或 `start-dev.bat` | 启动本地开发环境 |
| **[0]** | `deploy.bat 0` | 退出程序 |

---

## 🔧 常见问题解决

### ❌ "Python not found"
**原因：** 未安装 Python 或未添加到 PATH

**解决：**
1. 下载 Python 3.11+：https://www.python.org/downloads/
2. 安装时勾选 **"Add Python to PATH"**
3. 重启 CMD，再次运行

---

### ❌ "ssh-keygen not found"
**原因：** 未安装 Git for Windows 或 OpenSSH

**解决：**
1. 安装 Git for Windows：https://git-for-windows.github.io/
2. 或在 Windows 设置中启用 OpenSSH 客户端：
   - 设置 → 应用 → 可选功能 → 添加功能 → OpenSSH 客户端

---

### ❌ "Connection refused" 或 "Permission denied"
**原因：** SSH 连接失败

**排查步骤：**
1. 检查服务器 IP、端口、用户名是否正确
2. 确认公钥已添加到服务器的 `~/.ssh/authorized_keys`
3. 检查服务器防火墙是否开放 SSH 端口（默认 22）
4. 确认服务器 SSH 服务正在运行：`sudo systemctl status sshd`

**快速测试连接：**
```cmd
ssh -i "%USERPROFILE%\.ssh\campuspilot_deploy" root@你的服务器IP
```

---

### ❌ "rsync not found"
**现象：** 部署时提示 rsync 不可用

**说明：** 脚本会自动降级使用 scp，不影响部署

**可选优化：** 安装 cwRsync 或通过 WSL 使用 Linux 版 rsync

---

### ❌ Docker 构建失败
**排查方法：**
```bash
# 登录服务器查看详细日志
deploy.bat
选择: [5] View Logs

# 或 SSH 手动构建
ssh root@你的服务器IP
cd /opt/campus-pilot
docker compose build backend --no-cache
docker compose logs backend
```

**常见原因：**
- 服务器内存不足（建议 ≥ 2GB）
- 网络问题导致无法下载基础镜像
- Dockerfile 语法错误

---

### ❌ 健康检查超时
**现象：** 部署后提示 "Health check timed out"

**可能原因：**
1. 首次启动数据库初始化较慢（正常）
2. Playwright 浏览器下载慢（首次约 5 分钟）
3. 端口被占用

**解决：**
```bash
# 手动检查
ssh root@你的服务器IP
curl http://localhost:8000/health

# 查看容器状态
cd /opt/campus-pilot
docker compose ps

# 查看日志
docker compose logs backend
```

---

## 💡 高级用法

### 修改默认配置

编辑 `deploy.config` 文件：
```ini
REMOTE_HOST=123.45.67.89
REMOTE_USER=root
REMOTE_PORT=22
```

或直接修改 `deploy.bat` 顶部的变量。

---

### 多环境部署

复制 `deploy.config` 为多个文件：
```cmd
copy deploy.config deploy-prod.config    # 生产环境
copy deploy.config deploy-staging.config # 测试环境
```

分别填入不同服务器的地址。

---

### 仅更新代码（不重建镜像）

当只修改了 Python/前端代码时：
```bash
deploy.bat
选择: [3] Deploy to Server
```

脚本会检测变化并仅重启容器（比完整部署快很多）。

---

### 回滚版本

发现线上 Bug 时：
```bash
deploy.bat
选择: [6] Rollback Version
确认: y
```

**回滚过程：**
1. 停止当前服务
2. 从备份恢复数据库和配置
3. 重启服务
4. 自动健康检查

---

## 📂 重要文件说明

| 文件/目录 | 用途 | 是否提交到 Git |
|-----------|------|---------------|
| `deploy.bat` | Windows 主工具 | ✅ 是 |
| `start-dev.bat` | 本地开发启动器 | ✅ 是 |
| `deploy.config` | 服务器连接配置 | ❌ 否（含敏感信息）|
| `.env` | 环境变量配置 | ❌ 否（含密码）|
| `.ssh/campuspilot_deploy` | SSH 私钥 | ❌ 绝对不要提交！|
| `data/*.db` | SQLite 数据库 | ❌ 否 |

**⚠️ 安全提醒：**
- `deploy.config` 包含服务器地址
- `.env` 包含所有密码和 Token
- SSH 私钥泄露 = 服务器完全失控
- 这些文件已在 `.gitignore` 中排除

---

## 🔄 典型工作流示例

### 日常开发
```bash
# 1. 启动开发环境
start-dev.bat

# 2. 编写代码...（IDE 中编辑）

# 3. 运行测试
deploy.bat 1

# 4. 提交代码
git add .
git commit -m "feat: 新功能"
git push origin main

# 5. （可选）自动部署到服务器
deploy.bat 3
```

### 紧急修复
```bash
# 1. 发现线上 Bug
deploy.bat 4        # 查看状态和日志

# 2. 本地修复 Bug
start-dev.bat      # 启动本地环境
# ... 修复代码 ...

# 3. 测试
deploy.bat 1

# 4. 部署修复
deploy.bat 3

# 5. 如果新版本有问题，立即回滚
deploy.bat 6
```

---

## 🆘 获取帮助

如果遇到其他问题：

1. **查看日志：** `deploy.bat 5`
2. **检查状态：** `deploy.bat 4`
3. **查看文档：** `DEPLOYMENT.md`（完整技术文档）
4. **GitHub Issues：** 提交 Issue 到项目仓库

---

## ✨ 下一步

现在你可以：

✅ **本地开发** - 运行 `start-dev.bat`  
✅ **运行测试** - 运行 `deploy.bat test`  
✅ **配置 SSH** - 运行 `deploy.bat setup`  
✅ **部署上线** - 运行 `deploy.bat deploy`  

**推荐操作顺序：**
1. 先运行 `start-dev.bat` 确保本地环境正常
2. 再运行 `deploy.bat test` 通过所有测试
3. 最后运行 `deploy.bat setup` + `deploy.bat deploy` 部署到服务器

祝使用愉快！🎉
