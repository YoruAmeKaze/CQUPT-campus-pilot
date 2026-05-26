import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { 
  Bell, 
  BellOff, 
  Clock, 
  Calendar, 
  BookOpen, 
  FileText, 
  Save,
  RotateCcw,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface NotificationSetting {
  id: string
  name: string
  description: string
  enabled: boolean
  type: 'daily' | 'course' | 'assignment' | 'deadline'
  schedule: {
    time?: string
    beforeMinutes?: number
  }
  content: {
    title: string
    message: string
  }
}

const DEFAULT_SETTINGS: NotificationSetting[] = [
  {
    id: 'daily_schedule',
    name: '全天课程提醒',
    description: '每日早上推送今日课表概览',
    enabled: true,
    type: 'daily',
    schedule: { time: '07:50' },
    content: {
      title: '📅 今日课表',
      message: '{course_count}门课程，加油！',
    },
  },
  {
    id: 'course_reminder',
    name: '即将开始课程提醒',
    description: '课程开始前推送提醒',
    enabled: true,
    type: 'course',
    schedule: { beforeMinutes: 15 },
    content: {
      title: '⏰ 课程提醒',
      message: '{course_name}即将开始，地点：{location}',
    },
  },
  {
    id: 'new_assignment',
    name: '新作业提醒',
    description: '检测到新作业时推送通知',
    enabled: true,
    type: 'assignment',
    schedule: {},
    content: {
      title: '📝 新作业',
      message: '{course_name}发布了新作业：{title}',
    },
  },
  {
    id: 'deadline_reminder',
    name: '作业截止提醒',
    description: '作业截止前推送提醒',
    enabled: true,
    type: 'deadline',
    schedule: { beforeMinutes: 1440 },
    content: {
      title: '⚠️ 作业截止提醒',
      message: '{course_name}的作业「{title}」还有{hours_left}小时截止',
    },
  },
]

export default function Notifications() {
  const [settings, setSettings] = useState<NotificationSetting[]>(DEFAULT_SETTINGS)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    const saved = localStorage.getItem('notificationSettings')
    if (saved) {
      try {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed) && parsed.length > 0) {
          setSettings(parsed)
        }
      } catch {
        // ignore corrupt data
      }
    }
  }, [])

  const toggleSetting = (id: string) => {
    setSettings(settings.map(s =>
      s.id === id ? { ...s, enabled: !s.enabled } : s
    ))
  }

  const updateSetting = (id: string, updates: Partial<NotificationSetting>) => {
    setSettings(settings.map(s =>
      s.id === id ? { ...s, ...updates } : s
    ))
  }

  const handleSave = () => {
    localStorage.setItem('notificationSettings', JSON.stringify(settings))
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleReset = () => {
    setSettings(DEFAULT_SETTINGS)
    localStorage.removeItem('notificationSettings')
  }

  const getIcon = (type: string) => {
    switch (type) {
      case 'daily':
        return <Calendar className="w-5 h-5" />
      case 'course':
        return <BookOpen className="w-5 h-5" />
      case 'assignment':
        return <FileText className="w-5 h-5" />
      case 'deadline':
        return <Clock className="w-5 h-5" />
      default:
        return <Bell className="w-5 h-5" />
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">通知设置</h1>
          <p className="text-muted-foreground">管理推送通知的类型和时间</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={handleReset}
            size="sm"
            variant="outline"
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            重置默认
          </Button>
          <Button onClick={handleSave} size="sm" className={saved ? 'bg-green-600' : ''}>
            <Save className="w-4 h-4 mr-2" />
            {saved ? '保存成功' : '保存设置'}
          </Button>
        </div>
      </div>

      <div className="space-y-4">
        {settings.map(setting => (
          <Card key={setting.id}>
            <CardHeader className="cursor-pointer" onClick={() => setExpandedId(expandedId === setting.id ? null : setting.id)}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${setting.enabled ? 'bg-primary/10 text-primary' : 'bg-muted text-muted-foreground'}`}>
                    {getIcon(setting.type)}
                  </div>
                  <div>
                    <CardTitle className="text-base">{setting.name}</CardTitle>
                    <p className="text-sm text-muted-foreground">{setting.description}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {setting.enabled ? (
                    <Badge variant="secondary" className="bg-green-100 text-green-700">已开启</Badge>
                  ) : (
                    <Badge variant="secondary" className="bg-gray-100 text-gray-500">已关闭</Badge>
                  )}
                  {expandedId === setting.id ? (
                    <ChevronUp className="w-4 h-4" />
                  ) : (
                    <ChevronDown className="w-4 h-4" />
                  )}
                </div>
              </div>
            </CardHeader>
            {expandedId === setting.id && (
              <CardContent className="pt-0">
                <div className="space-y-6">
                  <div className="flex items-center justify-between p-4 bg-muted/50 rounded-lg">
                    <div className="flex items-center gap-2">
                      {setting.enabled ? (
                        <Bell className="w-5 h-5 text-green-500" />
                      ) : (
                        <BellOff className="w-5 h-5 text-muted-foreground" />
                      )}
                      <span>{setting.enabled ? '通知已开启' : '通知已关闭'}</span>
                    </div>
                    <button
                      onClick={() => toggleSetting(setting.id)}
                      className={`relative w-12 h-6 rounded-full transition-colors ${setting.enabled ? 'bg-primary' : 'bg-muted'}`}
                    >
                      <div className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${setting.enabled ? 'translate-x-7' : 'translate-x-1'}`} />
                    </button>
                  </div>

                  {setting.type === 'daily' && (
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <Label>推送时间</Label>
                        <Input
                          type="time"
                          value={setting.schedule.time}
                          onChange={(e) => updateSetting(setting.id, { schedule: { ...setting.schedule, time: e.target.value } })}
                        />
                      </div>
                    </div>
                  )}

                  {(setting.type === 'course' || setting.type === 'deadline') && (
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <Label>提前提醒时间</Label>
                        <Select
                          value={String(setting.schedule.beforeMinutes)}
                          onValueChange={(v) => updateSetting(setting.id, { schedule: { ...setting.schedule, beforeMinutes: Number(v) } })}
                        >
                          <SelectTrigger>
                            <SelectValue placeholder="选择时间" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="5">5分钟前</SelectItem>
                            <SelectItem value="10">10分钟前</SelectItem>
                            <SelectItem value="15">15分钟前</SelectItem>
                            <SelectItem value="30">30分钟前</SelectItem>
                            <SelectItem value="60">1小时前</SelectItem>
                            <SelectItem value="120">2小时前</SelectItem>
                            <SelectItem value="720">12小时前</SelectItem>
                            <SelectItem value="1440">1天前</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  )}

                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label>通知标题</Label>
                      <Input
                        value={setting.content.title}
                        onChange={(e) => updateSetting(setting.id, { content: { ...setting.content, title: e.target.value } })}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>通知内容</Label>
                      <textarea
                        className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-none"
                        value={setting.content.message}
                        onChange={(e) => updateSetting(setting.id, { content: { ...setting.content, message: e.target.value } })}
                        placeholder="支持变量：{course_name}, {location}, {title}, {course_count}, {hours_left}"
                      />
                    </div>
                    <p className="text-xs text-muted-foreground">
                      可用变量：{setting.type === 'daily' && '{course_count}'}
                      {setting.type === 'course' && '{course_name}, {location}'}
                      {(setting.type === 'assignment' || setting.type === 'deadline') && '{course_name}, {title}, {hours_left}'}
                    </p>
                  </div>
                </div>
              </CardContent>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}
