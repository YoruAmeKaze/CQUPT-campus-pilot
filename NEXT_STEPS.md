# 下一步操作清单

创建日期: 2026-05-25

---

## 📌 立即需要做的事（当你电脑在身边时）

### 1. 重新同步课表数据（优先级最高！）

数据库已用新 Schema 重建，当前为空。需要重新同步课程数据。

**操作步骤：**
- 打开浏览器访问 http://localhost:8000/docs
- 找到 `POST /api/courses/sync` 接口
- 点击"Try it out"，然后点击"Execute"

或者用命令行：
```bash
curl -X POST http://localhost:8000/api/courses/sync
```

**为什么要做：**
- 新数据库包含 `location_schedule` 字段，支持不同周显示不同地点
- 同步后，课表页和首页仪表盘才能正常显示课程

---

### 2. 验证功能是否正常

同步完成后，检查：

- 访问 http://localhost:3000 看仪表盘今日课表
- 访问 http://localhost:3000/courses 看周课表
- 切换周次（下一周/上一周），看看同一门课程在不同周的地点是否正确

---

## 📋 未来规划

- [ ] 开发飞书 Bot
- [ ] 开发作业爬虫（数你最灵/学习通）
- [ ] 完善待办事项前端页面
- [ ] 集成 LLM 进行对话

---

## 📂 相关文件

- 数据库模型：[app/db/models.py](file:///d:/vibeCoding/campusPilot/app/db/models.py)
- 课表服务：[app/services/course_service.py](file:///d:/vibeCoding/campusPilot/app/services/course_service.py)
- 教务爬虫：[app/crawlers/jwxt_crawler.py](file:///d:/vibeCoding/campusPilot/app/crawlers/jwxt_crawler.py)
- 课表页：[frontend/src/pages/Courses.tsx](file:///d:/vibeCoding/campusPilot/frontend/src/pages/Courses.tsx)
- 仪表盘：[frontend/src/pages/Dashboard.tsx](file:///d:/vibeCoding/campusPilot/frontend/src/pages/Dashboard.tsx)
