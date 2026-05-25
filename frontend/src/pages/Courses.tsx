import { useState, useEffect, Fragment } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Settings2, RefreshCw } from 'lucide-react'

const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const TIME_SLOTS = [
  { label: '1-2节', start: '08:00', end: '09:40' },
  { label: '3-4节', start: '10:15', end: '11:55' },
  { label: '5-6节', start: '14:00', end: '15:40' },
  { label: '7-8节', start: '16:15', end: '17:55' },
  { label: '9-10节', start: '19:00', end: '20:40' },
  { label: '11-12节', start: '20:50', end: '22:30' },
]



interface Course {
  id: number
  name: string
  teacher: string
  location: string
  day_of_week: number
  start_week: number
  end_week: number
  start_slot: number
  end_slot: number
  start_time: string
  end_time: string
}

interface CourseCard {
  course: Course
  col: number
  rowStart: number
  rowEnd: number
}

function buildCourseCards(courses: Course[]): CourseCard[] {
  return courses.map(course => {
    const col = course.day_of_week + 1
    const numSlots = course.end_slot - course.start_slot + 1
    const rowStart = Math.floor((course.start_slot - 1) / 2) + 2
    let rowEnd = rowStart
    if (numSlots <= 2) {
      rowEnd = rowStart + 1
    } else if (numSlots === 3) {
      rowEnd = rowStart + 2
    } else {
      rowEnd = rowStart + Math.ceil(numSlots / 2)
    }
    return { course, col, rowStart, rowEnd }
  })
}

export default function Courses() {
  const [currentWeek, setCurrentWeek] = useState(13)
  const [courses, setCourses] = useState<Course[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [studentId, setStudentId] = useState(localStorage.getItem('studentId') || '')
  const [showConfig, setShowConfig] = useState(false)

  useEffect(() => {
    fetchCourses()
  }, [currentWeek])

  const fetchCourses = async () => {
    try {
      setLoading(true)
      setError(null)
      const res = await fetch(`/api/courses?week=${currentWeek}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setCourses(data.courses || [])
    } catch (error) {
      console.error('获取课表失败:', error)
      setError('获取课表失败，请检查后端服务是否正常运行')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveStudentId = () => {
    if (studentId) {
      localStorage.setItem('studentId', studentId)
      setShowConfig(false)
    }
  }

  const handleSyncCourses = async () => {
    try {
      const res = await fetch('/api/courses/sync', { method: 'POST' })
      if (res.ok) {
        fetchCourses()
      }
    } catch (error) {
      console.error('同步课表失败:', error)
    }
  }

  if (loading) {
    return (
      <div className="flex h-[600px] items-center justify-center">
        <p className="text-muted-foreground">加载课表中...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-[600px] items-center justify-center">
        <div className="text-center space-y-2">
          <p className="text-destructive">{error}</p>
          <button
            onClick={fetchCourses}
            className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90"
          >
            重新加载
          </button>
        </div>
      </div>
    )
  }

  const courseCards = buildCourseCards(courses)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">课表</h1>
          <p className="text-muted-foreground">查看本周课程安排</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setCurrentWeek(Math.max(1, currentWeek - 1))}
            className="rounded-md border border-input bg-background px-3 py-2 text-sm hover:bg-accent"
          >
            上一周
          </button>
          <span className="px-4 py-2 text-sm font-medium">
            第 {currentWeek} 周
          </span>
          <button
            onClick={() => setCurrentWeek(currentWeek + 1)}
            className="rounded-md border border-input bg-background px-3 py-2 text-sm hover:bg-accent"
          >
            下一周
          </button>
          <Button
            onClick={fetchCourses}
            size="sm"
            variant="outline"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            刷新
          </Button>
          <Button
            onClick={handleSyncCourses}
            size="sm"
          >
            同步课表
          </Button>
          <Dialog open={showConfig} onOpenChange={setShowConfig}>
            <DialogTrigger asChild>
              <Button size="sm" variant="outline">
                <Settings2 className="w-4 h-4 mr-2" />
                学号配置
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>学号配置</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="studentId">学号</Label>
                  <Input
                    id="studentId"
                    value={studentId}
                    onChange={(e) => setStudentId(e.target.value)}
                    placeholder="请输入学号"
                  />
                </div>
                <Button onClick={handleSaveStudentId} className="w-full">
                  保存配置
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <div
              className="grid min-w-[900px]"
              style={{
                gridTemplateColumns: '80px repeat(7, 1fr)',
                gridTemplateRows: 'auto repeat(6, minmax(80px, 1fr))',
              }}
            >
              {/* 表头：节次 */}
              <div
                className="sticky top-0 z-10 border-b border-r bg-muted/50 p-2 text-center text-xs font-medium flex items-center justify-center"
                style={{ gridArea: '1/1/2/2' }}
              >
                节次
              </div>

              {/* 表头：星期 */}
              {WEEKDAYS.map((day, i) => (
                <div
                  key={day}
                  className="sticky top-0 z-10 border-b border-r bg-muted/50 p-2 text-center text-xs font-medium flex items-center justify-center"
                  style={{ gridArea: `1/${i + 2}/2/${i + 3}` }}
                >
                  {day}
                </div>
              ))}

              {/* 时间标签和背景格子 */}
              {TIME_SLOTS.map((slot, rowIdx) => (
                <Fragment key={`row-${rowIdx}`}>
                  <div
                    className="border-b border-r p-2 text-center flex flex-col items-center justify-center"
                    style={{ gridArea: `${rowIdx + 2}/1/${rowIdx + 3}/2` }}
                  >
                    <div className="text-xs font-medium leading-tight">{slot.label}</div>
                    <div className="text-[10px] text-muted-foreground leading-tight mt-0.5">
                      {slot.start}
                    </div>
                    <div className="text-[10px] text-muted-foreground leading-tight">
                      {slot.end}
                    </div>
                  </div>
                  {WEEKDAYS.map((_, dayIdx) => (
                    <div
                      key={`bg-${rowIdx}-${dayIdx}`}
                      className="border-b border-r"
                      style={{ gridArea: `${rowIdx + 2}/${dayIdx + 2}/${rowIdx + 3}/${dayIdx + 3}` }}
                    />
                  ))}
                </Fragment>
              ))}

              {/* 课程卡片 */}
              {courseCards.map(({ course, col, rowStart, rowEnd }) => (
                <div
                  key={course.id}
                  className="p-1 overflow-hidden"
                  style={{
                    gridColumn: `${col} / ${col + 1}`,
                    gridRow: `${rowStart} / ${rowEnd}`,
                  }}
                >
                  <div className="rounded bg-blue-100 dark:bg-blue-900/30 p-1.5 text-xs leading-tight h-full flex flex-col justify-center">
                    <div className="font-medium truncate" title={course.name}>
                      {course.name}
                    </div>
                    <div className="text-muted-foreground truncate" title={course.teacher}>
                      {course.teacher}
                    </div>
                    <div className="truncate" title={course.location}>
                      {course.location}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>第{currentWeek}周课程 ({courses.length}门)</CardTitle>
        </CardHeader>
        <CardContent>
          {courses.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">本周没有课程安排</p>
          ) : (
            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
              {courses.map(course => (
                <div key={course.id} className="rounded-lg border p-3 space-y-1">
                  <div className="font-medium">{course.name}</div>
                  <div className="text-sm text-muted-foreground flex justify-between">
                    <span>{WEEKDAYS[course.day_of_week - 1]}</span>
                    <span>{course.start_time}-{course.end_time}</span>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {course.teacher} | {course.location}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
