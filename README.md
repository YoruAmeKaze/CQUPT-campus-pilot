# CampusPilot 🎓

**重庆邮电大学个人学业智能助理** — 自动抓取课表、作业，通过 Web 界面和飞书机器人管理学业

## 功能

- 📅 **课表管理** — 自动从教务系统抓取课表，周视图展示
- 📝 **作业提醒** — 自动抓取学习通、数你最灵作业，截止时间提醒
- ✅ **待办管理** — Web 端和飞书端创建待办，支持自然语言
- 🤖 **飞书机器人** — 双向对话，查询课表/作业/待办
- 🧠 **AI 智能查询** — 自然语言问："这周有什么作业？"
- 📊 **Web 仪表盘** — 可视化学业概览

---

## 快速开始

### 方式一：Windows 直接运行（推荐）

#### 前置条件

| 软件 | 版本 | 下载 |
|------|------|------|
| Python | 3.11+ | https://www.python.org/downloads/ |
| Node.js | 18+ | https://nodejs.org/ |

> Python 安装时请勾选 **"Add Python to PATH"**

#### 一键启动

```bat
# 双击运行（或在终端中执行）
start.bat
```

脚本会自动完成：
1. ✅ 检测 Python 和 Node.js 环境
2. ✅ 创建 Python 虚拟环境并安装依赖
3. ✅ 自动生成加密密钥（FERNET_KEY）
4. ✅ 安装 Playwright Chromium 浏览器（爬虫用）
5. ✅ 安装前端依赖并编译
6. ✅ 启动后端服务 (http://localhost:8000)
7. ✅ 启动前端界面 (http://localhost:3000)

启动后，在浏览器打开 **http://localhost:3000** 即可使用。

### 方式二：Docker 运行

#### 前置条件

| 软件 | 下载 |
|------|------|
| Docker Desktop | https://www.docker.com/products/docker-desktop/ |

#### 一键启动

```bat
# Windows
docker-start.bat
```

```bash
# Linux/Mac
docker compose up -d --build
```

脚本会自动完成：
1. ✅ 检测 Docker 环境
2. ✅ 自动生成加密密钥
3. ✅ 构建前后端 Docker 镜像
4. ✅ 启动容器服务

启动后，在浏览器打开 **http://localhost:3000** 即可使用。

---

## 首次使用配置

启动后打开 http://localhost:3000，进入 **"设置"** 页面配置以下内容：

### 基础配置（必填）
| 配置项 | 说明 |
|--------|------|
| 学号 | 用于教务系统课表抓取 |
| DeepSeek API Key | 用于 AI 智能查询功能（[获取 Key](https://platform.deepseek.com/)）|

### 数据源配置（按需）
| 配置项 | 说明 |
|--------|------|
| 学习通账号/密码 | 自动抓取学习通作业 |
| 数你最灵账号/密码 | 自动抓取数你最灵作业 |

### 推送配置（按需）

配置后，课表提醒、作业截止、待办提醒等消息会推送到你的手机。

---

#### 方式一：飞书群机器人推送（推荐，最简单）

通过飞书群机器人将消息推送到你的飞书群。适合平时用飞书的同学。

**配置步骤：**

1. **打开飞书**，进入任意一个群聊（也可以自己建一个只有自己的群）
2. 点击群右上角的 **"···"** → **"设置"** → **"群机器人"**
3. 点击 **"添加机器人"**，搜索并添加 **"自定义机器人"**
4. 给机器人起个名字（比如"课表助手"），点击 **"添加"**
5. 复制弹窗中的 **Webhook URL**（类似 `https://open.feishu.cn/open-apis/bot/v2/hook/xxxxx`）
6. 回到 CampusPilot 设置页面，粘贴到 **"飞书 Webhook URL"** 输入框，保存即可

> 💡 如果不想被群里其他人看到消息，可以建一个只有你自己的群。

---

#### 方式二：Bark iOS 推送（iPhone 用户）

通过 Bark App 将消息推送到你的 iPhone。适合用 iPhone 的同学。

**配置步骤：**

1. 在 App Store 搜索 **"Bark"** 并下载安装（免费）
2. 打开 Bark App，你会看到一个网址，类似 `https://api.day.app/你的Key`
3. 复制这个网址中的 **"你的Key"** 部分（一串字母数字）
4. 回到 CampusPilot 设置页面，粘贴到 **"Bark Key"** 输入框，保存即可
5. 建议在 Bark App 中打开 **"推送历史"** 开关，方便查看历史消息

> 💡 Bark 的推送会直接出现在 iPhone 的锁屏通知上，和微信消息一样及时。

---

#### 方式三：飞书应用双向对话（高级功能，需公网服务器）

创建一个飞书应用，可以：
- ✅ 在飞书里直接给机器人发消息，**查询课表、作业、待办**
- ✅ 机器人主动推送通知到你的飞书**私信**
- ✅ 不需要群聊，个人直接对话

> ⚠️ 这个配置比较复杂，需要一台**有公网 IP 的服务器**。如果只是为了收推送通知，建议先用 **方式一（群机器人）**，简单又够用。

**配置步骤：**

##### 第一步：创建飞书应用

1. 打开 [飞书开放平台](https://open.feishu.cn/)（建议用电脑浏览器打开）
2. 点击右上角 **"开发者登录"**，用你的飞书账号扫码登录
3. 登录后，点击顶部 **"创建应用"** → **"企业自建应用"**
4. 填写应用名称（比如"CampusPilot"）、描述，上传一个图标，点击 **"确定创建"**

##### 第二步：获取 App ID 和 App Secret

1. 创建成功后，进入应用详情页
2. 在左侧菜单点击 **"凭证与基础信息"**
3. 你会看到 **App ID** 和 **App Secret** 两个字段
4. 点击 App Secret 后面的 **"查看"** 按钮，复制保存（后面要用）
5. 同时记下 App ID

##### 第三步：配置机器人权限

1. 在左侧菜单点击 **"权限管理"**
2. 在搜索框搜索并添加以下权限（点击"开通"）：
   - `im:message` - 获取用户发送的消息
   - `im:message:send_as_bot` - 以机器人身份发送消息
   - `contact:user.base:readonly` - 读取用户基本信息
3. 点击右上角 **"发布"** 按钮

##### 第四步：配置事件订阅（让机器人能接收消息）

1. 在左侧菜单点击 **"事件与回调"**
2. 点击 **"添加事件"**
3. 搜索并添加以下事件：
   - **"接收消息"**（`im.message.receive_v1`）
4. 在 **"回调配置"** 中，**回调 URL** 填写你的服务器地址（需要公网可访问）
   - 格式：`https://你的域名或IP:端口/api/webhook/feishu`
5. 按照页面提示下载验证文件，放到服务器指定目录完成验证

##### 第五步：配置公网访问

飞书需要你的服务器能通过公网访问。如果你有**云服务器**（比如阿里云、腾讯云），直接在服务器上运行 CampusPilot 并配置域名即可。

CampusPilot 已内置 SSH 隧道支持，相关配置在设置页面填写。

##### 第六步：在设置页面填写配置

1. 回到 CampusPilot 设置页面
2. 填写 **"飞书 App ID"** 和 **"飞书 App Secret"**（前面第二步获取的）
3. 填写 **"公网服务器信息"**（IP、端口、用户名等）
4. 保存后，你的飞书应用就配置完成了

> 💡 配置成功后，打开飞书 → 通讯录 → 搜索你的应用名称 → 就可以开始和机器人对话了！

---

## 开机自启（Windows）

启动 `start.bat` 后，脚本会询问是否设置开机自启，选择 `y` 即可。

或者手动运行以下命令：

```bat
# 设置开机自启（用户登录时自动启动）
schtasks /create /tn "CampusPilot" /tr "'C:\路径\到\start.bat'" /sc onlogon /ru "%USERNAME%" /f

# 取消开机自启
schtasks /delete /tn "CampusPilot" /f

# 查看任务状态
schtasks /query /tn "CampusPilot"
```

---

## 目录结构

```
CampusPilot/
├── start.bat                # Windows 一键启动
├── start.sh                 # Linux/Mac 一键启动
├── docker-start.bat         # Docker 一键启动
├── .env                     # 环境变量（自动管理）
│
├── app/                     # 后端 Python 代码
├── frontend/                # 前端 React 代码
├── docs/                    # 开发文档
├── scripts/                 # 服务器部署脚本
├── tests/                   # 测试
│
├── Dockerfile               # 后端 Docker 构建
├── docker-compose.yml       # Docker Compose 编排
└── requirements.txt         # Python 依赖
```

---

## 管理命令

### 停止服务
- **直接运行模式**：关闭 CampusPilot-Backend 和 CampusPilot-Frontend 的终端窗口
- **Docker 模式**：

  ```bash
  docker compose down
  ```

### 查看日志
- **Docker 模式**：

  ```bash
  docker compose logs -f
  ```

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy / APScheduler |
| 前端 | React 18 / TypeScript / Tailwind CSS / shadcn/ui |
| 数据库 | SQLite（零配置） |
| AI | DeepSeek (Text-to-SQL) |
| 爬虫 | Playwright / BeautifulSoup / httpx |
| 部署 | Docker / Docker Compose |

---

## 开发参考

详细技术文档见 [docs/AI_开发指南.md](docs/AI_开发指南.md)。
