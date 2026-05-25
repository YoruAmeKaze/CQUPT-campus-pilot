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
  name: string
  type: string
  status: 'ok' | 'error' | 'pending'
  lastSync?: string
}

export default function Dashboard() {
  const [todayCourses, setTodayCourses] = useState<TodayCourse[]>([])
  const [todayCount, setTodayCount] = useState(0)
  const [weekCount, setWeekCount] = useState(0)
  const [loading, setLoading] = useState(true)

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

  const sources: SourceItem[] = [
    { name: '教务系统', type: 'jwxt', status: 'ok', lastSync: '2026-05-25 06:00' },
    { name: '数你最灵', type: 'smartestu', status: 'pending' },
    { name: '学习通', type: 'chaoxing', status: 'error', lastSync: '2026-05-24 15:30' },
  ]

  useEffect(() => {
    const fetchDashboard = async () => {
      setLoading(true)
      try {
        const [todayRes, summaryRes] = await Promise.all([
          fetch('/api/courses/today'),
          fetch('/api/courses/summary'),
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
          setWeekCount(summaryData.week_courses_count || 0)
        }
      } catch (error) {
        console.error('获取仪表盘数据失败:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchDashboard()
    const interval = setInterval(fetchDashboard, 30000)
    return () => clearInterval(interval)
  }, [])

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

        <Card className="border-destructive/50 bg-destructive/5">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              今日截止作业
            </CardTitle>
            <AlertTriangle className="h-5 w-5 text-destructive" />
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold text-destructive">0</div>
            <p className="text-xs text-muted-foreground mt-1">项待完成</p>
            <Badge variant="secondary" className="mt-3">暂无数据</Badge>
          </CardContent>
        </Card>

        <Card className="relative overflow-hidden">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              本周课程总数
            </CardTitle>
            <FileText className="h-5 w-5 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-4xl font-bold">{loading ? '...' : weekCount}</div>
            <p className="text-xs text-muted-foreground mt-1">门课程</p>
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
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Server className="h-4 w-4" />
                数据源状态
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {sources.map((source, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-2 rounded-md bg-muted/50"
                  >
                    <div className="flex items-center gap-2">
                      {source.status === 'ok' && (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                      )}
                      {source.status === 'error' && (
                        <AlertTriangle className="h-4 w-4 text-red-500" />
                      )}
                      {source.status === 'pending' && (
                        <Clock className="h-4 w-4 text-yellow-500" />
                      )}
                      <span className="text-sm font-medium">
                        {source.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          source.status === 'ok'
                            ? 'secondary'
                            : source.status === 'error'
                            ? 'destructive'
                            : 'outline'
                        }
                        className="text-xs"
                      >
                        {source.status === 'ok' && '正常'}
                        {source.status === 'error' && '异常'}
                        {source.status === 'pending' && '待配置'}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
              <Button variant="outline" className="w-full mt-4" size="sm" asChild>
                <a href="/settings">管理数据源</a>
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 border-blue-500/20">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            开发进度
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[
              { phase: 1, name: '项目骨架', status: 'done', desc: '已完成' },
              { phase: 2, name: '教务课表', status: 'done', desc: '已完成' },
              { phase: 3, name: '数你最灵', status: 'pending', desc: '待开发' },
              { phase: 5, name: '企业微信', status: 'pending', desc: '待开发' },
            ].map((item) => (
              <div key={item.phase} className="text-center p-3 rounded-lg bg-background/50">
                <div className="text-lg mb-1">
                  {item.status === 'done' ? '✅' : item.status === 'next' ? '🔜' : '⏳'}
                </div>
                <div className="font-medium text-sm">Phase {item.phase}</div>
                <div className="text-xs text-muted-foreground">{item.name}</div>
                <div className={`text-xs mt-1 ${item.status === 'done' ? 'text-green-500' : 'text-primary'}`}>
                  {item.desc}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
