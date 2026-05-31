import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  BookOpen,
  Clock,
  FileText,
  AlertTriangle,
  CheckCircle,
  Server,
  Activity,
  Bot,
  Brain,
  Wifi,
  MessageSquare,
  Send,
  Database,
  Bell,
} from 'lucide-react'

interface CourseItem {
  id: number
  name: string
  teacher: string
  location: string
  day_of_week: number
  start_time: string
  end_time: string
  start_slot: number
  end_slot: number
}

interface TodayCourse extends CourseItem {
  current?: boolean
}

interface SourceItem {
  id: number
  name: string
  type: string
  enabled: boolean
  sync_status: string
  last_sync: string | null
}

interface DataSourceAPIItem {
  id: number
  type: string
  name: string
  enabled: boolean
  username: string
  last_sync: string | null
  sync_status: string
}

interface ServiceStatus {
  status: 'ok' | 'warning' | 'error'
  label: string
  icon: string
}

interface BotHealth {
  overall: string
  message: string
  services: Record<string, ServiceStatus>
}

export default function Dashboard() {
  const [todayCourses, setTodayCourses] = useState<TodayCourse[]>([])
  const [todayCount, setTodayCount] = useState(0)
  const [pendingTodoCount, setPendingTodoCount] = useState(0)
  const [todayDueCount, setTodayDueCount] = useState(0)
  const [todayDueLoading, setTodayDueLoading] = useState(true)
  const [loading, setLoading] = useState(true)
  const [sources, setSources] = useState<SourceItem[]>([])
  const [sourcesLoading, setSourcesLoading] = useState(true)
  const [botHealth, setBotHealth] = useState<BotHealth | null>(null)
  const [botHealthLoading, setBotHealthLoading] = useState(true)
  const [testMessage, setTestMessage] = useState('')
  const [testReply, setTestReply] = useState('')
  const [testLoading, setTestLoading] = useState(false)

  const getCurrentTimeSlot = (): number => {
    const now = new Date()
    const h = now.getHours()
    const m = now.getMinutes()
    const time = h * 60 + m
    if (time >= 8 * 60 && time < 9 * 60 + 40) return 1
    if (time >= 10 * 60 + 15 && time < 11 * 60 + 55) return 3
    if (time >= 14 * 60 && time < 15 * 60 + 40) return 5
    if (time >= 16 * 60 + 15 && time < 17 * 60 + 55) return 7
    if (time >= 19 * 60 && time < 20 * 60 + 40) return 9
    if (time >= 20 * 60 + 50 && time < 22 * 60 + 30) return 11
    return -1
  }

  useEffect(() => {
    const fetchDashboard = async () => {
      setLoading(true)
      try {
        const [todayRes, summaryRes, sourcesRes, todayAssignRes, todosRes, healthRes] = await Promise.all([
          fetch('/api/courses/today'),
          fetch('/api/courses/summary'),
          fetch('/api/data-sources'),
          fetch('/api/assignments/today'),
          fetch('/api/todos?status=pending'),
          fetch('/api/health/detailed'),
        ])

        if (todayRes.ok) {
          const todayData = await todayRes.json()
          const currentSlot = getCurrentTimeSlot()
          setTodayCourses(
            (todayData.courses || []).map((c: CourseItem) => ({
              ...c,
              current: c.start_slot <= currentSlot && c.end_slot >= currentSlot,
            }))
          )
        }

        if (summaryRes.ok) {
          const summaryData = await summaryRes.json()
          setTodayCount(summaryData.today_courses_count || 0)
        }

        if (sourcesRes.ok) {
          const data: DataSourceAPIItem[] = await sourcesRes.json()
          setSources(data.map(s => ({
            id: s.id,
            name: s.name,
            type: s.type,
            enabled: s.enabled,
            sync_status: s.sync_status,
            last_sync: s.last_sync,
          })))
        }

        if (todayAssignRes.ok) {
          const data = await todayAssignRes.json()
          setTodayDueCount(data.assignments?.length || 0)
        }

        if (todosRes.ok) {
          const todosData = await todosRes.json()
          setPendingTodoCount(todosData.todos?.length || 0)
        }

        if (healthRes.ok) {
          const healthData: BotHealth = await healthRes.json()
          setBotHealth(healthData)
        }
      } catch (error) {
        console.error('获取仪表盘数据失败:', error)
      } finally {
        setLoading(false)
        setSourcesLoading(false)
        setTodayDueLoading(false)
        setBotHealthLoading(false)
      }
    }

    fetchDashboard()
    const interval = setInterval(fetchDashboard, 30000)
    return () => clearInterval(interval)
  }, [])

  async function handleTestBot() {
    if (!testMessage.trim() || testLoading) return
    setTestLoading(true)
    setTestReply('')
    try {
      const resp = await fetch('/api/llm/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: testMessage }),
      })
      const data = await resp.json()
      setTestReply(data.reply || '（无回复）')
    } catch (err) {
      setTestReply('❌ 测试失败: ' + (err as Error).message)
    } finally {
      setTestLoading(false)
    }
  }

  function getStatusIcon(iconName: string) {
    const icons: Record<string, JSX.Element> = {
      server: <Server className="w-4 h-4" />,
      database: <Database className="w-4 h-4" />,
      brain: <Brain className="w-4 h-4" />,
      bot: <Bot className="w-4 h-4" />,
      webhook: <Bell className="w-4 h-4" />,
      bell: <Bell className="w-4 h-4" />,
      tunnel: <Wifi className="w-4 h-4" />,
      clock: <Clock className="w-4 h-4" />,
    }
    return icons[iconName] || <Server className="w-4 h-4" />
  }

  const formatTime = (time: string) => {
    return time.substring(0, 5)
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">仪表盘</h1>
        <p className="text-muted-foreground mt-1">
          欢迎回来！这是您的学业概览
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Card className="relative overflow-hidden">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              今日课程
            </CardTitle>
            <BookOpen className="h-5 w-5 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold">{loading ? '...' : todayCount}</div>
            <p className="text-xs text-muted-foreground mt-1">节</p>
            <div className="mt-3 h-1 w-full bg-secondary rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all"
                style={{ width: `${Math.min(todayCount * 10, 100)}%` }}
              />
            </div>
          </CardContent>
        </Card>

        <Card className={todayDueCount > 0 ? 'border-destructive/50 bg-destructive/5' : ''}>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              今日截止作业
            </CardTitle>
            {todayDueCount > 0 ? (
              <AlertTriangle className="h-5 w-5 text-destructive" />
            ) : (
              <CheckCircle className="h-5 w-5 text-green-500" />
            )}
          </CardHeader>
          <CardContent>
            <div className={`text-4xl font-bold ${todayDueCount > 0 ? 'text-destructive' : ''}`}>
              {todayDueLoading ? '...' : todayDueCount}
            </div>
            <p className="text-xs text-muted-foreground mt-1">项待完成</p>
            {!todayDueLoading && todayDueCount > 0 && (
              <Badge variant="destructive" className="mt-3">
                需尽快完成
              </Badge>
            )}
            {!todayDueLoading && todayDueCount === 0 && (
              <Badge variant="secondary" className="mt-3">暂无未完成</Badge>
            )}
          </CardContent>
        </Card>

        <Card className="relative overflow-hidden">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              待办事项
            </CardTitle>
            <FileText className="h-5 w-5 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold">{loading ? '...' : pendingTodoCount}</div>
            <p className="text-xs text-muted-foreground mt-1">项待完成</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-7">
        <Card className="lg:col-span-4">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>今日课表</CardTitle>
              <Button variant="outline" size="sm" asChild>
                <a href="/courses">查看全部</a>
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center h-32">
                <Activity className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : todayCourses.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">今天没有课程安排</p>
            ) : (
              <div className="space-y-4">
                {todayCourses
                  .sort((a, b) => a.start_slot - b.start_slot)
                  .map((course) => (
                    <div
                      key={course.id}
                      className={`flex items-start gap-4 p-3 rounded-lg transition-colors ${
                        course.current
                          ? 'bg-primary/10 border border-primary/20'
                          : 'hover:bg-accent'
                      }`}
                    >
                      <div className="text-sm font-medium text-muted-foreground min-w-[100px] pt-0.5">
                        {formatTime(course.start_time)} - {formatTime(course.end_time)}
                      </div>
                      <div className="flex-1">
                        <div className="font-medium">{course.name}</div>
                        <div className="text-sm text-muted-foreground flex gap-3 mt-1">
                          <span>{course.teacher}</span>
                          <span>•</span>
                          <span>{course.location}</span>
                        </div>
                      </div>
                      {course.current && (
                        <Badge variant="default" className="shrink-0">
                          进行中
                        </Badge>
                      )}
                    </div>
                  ))}
              </div>
            )}
          </CardContent>
        </Card>

        <div className="lg:col-span-3 space-y-6">
          {/* 机器人连接状态 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Bot className="h-4 w-4" />
                机器人连接状态
                {!botHealthLoading && botHealth && (
                  <Badge
                    variant={botHealth.overall === 'ok' ? 'secondary' : 'outline'}
                    className={botHealth.overall === 'ok' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'text-yellow-600'}
                  >
                    {botHealth.overall === 'ok' ? '🟢 全部正常' : '🟡 部分异常'}
                  </Badge>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {botHealthLoading ? (
                <p className="text-center text-muted-foreground py-4">加载中...</p>
              ) : botHealth ? (
                <div className="space-y-2">
                  {Object.entries(botHealth.services).map(([key, svc]) => (
                    <div key={key} className="flex items-center justify-between p-2 rounded-md bg-muted/50">
                      <div className="flex items-center gap-2">
                        {getStatusIcon(svc.icon)}
                        <span className="text-sm font-medium">{svc.label}</span>
                      </div>
                      <Badge
                        variant={
                          svc.status === 'ok' ? 'secondary' :
                          svc.status === 'warning' ? 'outline' : 'destructive'
                        }
                        className={`text-xs ${
                          svc.status === 'ok' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                          svc.status === 'warning' ? 'text-yellow-600' : ''
                        }`}
                      >
                        {svc.status === 'ok' ? '正常' :
                         svc.status === 'warning' ? '未配置' : '异常'}
                      </Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-muted-foreground py-4">无法获取状态</p>
              )}
            </CardContent>
          </Card>

          {/* 测试机器人对话 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                测试机器人对话
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {testReply && (
                  <div className="p-3 rounded-lg bg-muted/50 text-sm whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                    {testReply}
                  </div>
                )}
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={testMessage}
                    onChange={e => setTestMessage(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') handleTestBot(); }}
                    placeholder="输入消息测试机器人回复..."
                    className="flex-1 h-9 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                  />
                  <Button
                    size="sm"
                    onClick={handleTestBot}
                    disabled={testLoading || !testMessage.trim()}
                  >
                    <Send className={`w-4 h-4 mr-1 ${testLoading ? 'animate-pulse' : ''}`} />
                    {testLoading ? '发送中...' : '发送'}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  提示：输入"今天有什么课"、"有哪些作业"、"想去自习"等来测试机器人功能
                </p>
              </div>
            </CardContent>
          </Card>

          {/* 数据源状态 */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Server className="h-4 w-4" />
                数据源状态
              </CardTitle>
            </CardHeader>
            <CardContent>
              {sourcesLoading ? (
                <p className="text-center text-muted-foreground py-4">加载中...</p>
              ) : sources.length === 0 ? (
                <p className="text-center text-muted-foreground py-4">暂无数据源</p>
              ) : (
                <div className="space-y-3">
                  {sources.map((source) => (
                    <div
                      key={source.id}
                      className="flex items-center justify-between p-2 rounded-md bg-muted/50"
                    >
                      <div className="flex items-center gap-2">
                        {source.sync_status === 'ok' && (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        )}
                        {source.sync_status === 'error' && (
                          <AlertTriangle className="h-4 w-4 text-red-500" />
                        )}
                        {source.sync_status === 'pending' && (
                          <Clock className="h-4 w-4 text-yellow-500" />
                        )}
                        <span className="text-sm font-medium">
                          {source.name}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={
                            source.sync_status === 'ok'
                              ? 'secondary'
                              : source.sync_status === 'error'
                              ? 'destructive'
                              : 'outline'
                          }
                          className="text-xs"
                        >
                          {source.sync_status === 'ok' && '正常'}
                          {source.sync_status === 'error' && '异常'}
                          {source.sync_status === 'pending' && '待配置'}
                        </Badge>
                      </div>
                    </div>
                  ))}
              </div>
              )}
              <Button variant="outline" className="w-full mt-4" size="sm" asChild>
                <a href="/settings">管理数据源</a>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
