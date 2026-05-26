import { NavLink } from 'react-router-dom'
import { useState, useEffect } from 'react'
import {
  LayoutDashboard,
  Calendar,
  FileText,
  Settings,
  GraduationCap,
  CheckSquare,
  Bell,
  Clock,
  DoorOpen,
} from 'lucide-react'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: '仪表盘' },
  { to: '/courses', icon: Calendar, label: '课表' },
  { to: '/assignments', icon: FileText, label: '作业' },
  { to: '/todos', icon: CheckSquare, label: '待办' },
  { to: '/rooms', icon: DoorOpen, label: '空教室' },
  { to: '/notifications', icon: Bell, label: '通知' },
  { to: '/schedules', icon: Clock, label: '定时' },
  { to: '/settings', icon: Settings, label: '配置' },
]

function computeWeek(termStartDate: string): number {
  if (!termStartDate) return 0
  const diff = new Date().getTime() - new Date(termStartDate).getTime()
  return Math.max(1, Math.floor(diff / (1000 * 60 * 60 * 24 * 7)) + 1)
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const [currentWeek, setCurrentWeek] = useState(15)

  useEffect(() => {
    fetch('/api/config')
      .then(r => r.json())
      .then(config => setCurrentWeek(computeWeek(config.term_start_date)))
      .catch(() => {})
  }, [])
  return (
    <div className="flex h-screen bg-background">
      {/* 侧边栏 - 始终显示 */}
      <aside className="w-64 flex-shrink-0 border-r border-border bg-card">
        <div className="flex h-16 items-center px-6 border-b border-border">
          <GraduationCap className="h-7 w-7 text-primary mr-3" />
          <div>
            <h1 className="text-xl font-bold text-primary">CampusPilot</h1>
            <p className="text-xs text-muted-foreground">学业智能助理</p>
          </div>
        </div>

        <nav className="mt-4 space-y-1 px-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all ${
                  isActive
                    ? 'bg-primary/10 text-primary shadow-sm'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground'
                }`
              }
            >
              <item.icon className="h-5 w-5" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* 底部信息 */}
        <div className="absolute bottom-0 w-64 p-4 border-t border-border bg-card/50">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-xs font-medium text-green-400">系统在线</span>
          </div>
          <p className="text-xs text-muted-foreground">CampusPilot v2.0</p>
          <p className="text-xs text-muted-foreground">重庆邮电大学</p>
        </div>
      </aside>

      {/* 主内容区 */}
      <main className="flex-1 overflow-auto">
        {/* 顶部栏 */}
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-card/80 backdrop-blur-sm px-8">
          <h2 className="text-lg font-semibold text-foreground">个人学业智能助理</h2>
          
          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-medium">{new Date().toLocaleDateString('zh-CN', { 
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
              })}</p>
              <p className="text-xs text-muted-foreground">第 {currentWeek} 周 • 夏季学期</p>
            </div>
          </div>
        </header>

        {/* 页面内容 */}
        <div className="p-8">
          {children}
        </div>
      </main>
    </div>
  )
}
