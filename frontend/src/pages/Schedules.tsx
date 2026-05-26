import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Clock, RefreshCw, Plus, Trash2, AlarmClock } from 'lucide-react'

interface SchedulerJob {
  id: string
  name: string
  trigger: string
  next_run_time: string | null
  enabled: boolean
}

interface CustomReminder {
  id: number
  name: string
  title: string
  content: string | null
  repeat_type: string
  repeat_day: number | null
  reminder_time: string
  enabled: boolean
}

export default function Schedules() {
  const [jobs, setJobs] = useState<SchedulerJob[]>([])
  const [loadingJobs, setLoadingJobs] = useState(true)
  const [customReminders, setCustomReminders] = useState<CustomReminder[]>([])
  const [showAddReminder, setShowAddReminder] = useState(false)
  const [newReminder, setNewReminder] = useState({ name: '', title: '', content: '', repeat_type: 'daily', repeat_day: '', reminder_time: '' })

  useEffect(() => {
    fetchSchedulerStatus()
    fetchCustomReminders()
  }, [])

  const fetchCustomReminders = async () => {
    try {
      const res = await fetch('/api/custom-reminders')
      if (res.ok) setCustomReminders(await res.json())
    } catch { /* ignore */ }
  }

  const fetchSchedulerStatus = async () => {
    try {
      setLoadingJobs(true)
      const res = await fetch('/api/config/scheduler')
      if (res.ok) {
        const data = await res.json()
        setJobs(data.jobs || [])
      }
    } catch (error) {
      console.error('获取定时任务状态失败:', error)
    } finally {
      setLoadingJobs(false)
    }
  }

  const handleCreateReminder = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const body: any = {
        name: newReminder.name,
        title: newReminder.title,
        content: newReminder.content || null,
        repeat_type: newReminder.repeat_type,
        reminder_time: newReminder.reminder_time,
      }
      if (newReminder.repeat_type !== 'daily') {
        body.repeat_day = parseInt(newReminder.repeat_day)
      }
      const res = await fetch('/api/custom-reminders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (res.ok) {
        setShowAddReminder(false)
        setNewReminder({ name: '', title: '', content: '', repeat_type: 'daily', repeat_day: '', reminder_time: '' })
        fetchCustomReminders()
      }
    } catch { /* ignore */ }
  }

  const handleDeleteReminder = async (id: number) => {
    if (!confirm('确定要删除这个提醒吗？')) return
    try {
      const res = await fetch(`/api/custom-reminders/${id}`, { method: 'DELETE' })
      if (res.ok) fetchCustomReminders()
    } catch { /* ignore */ }
  }

  const handleToggleReminder = async (reminder: CustomReminder) => {
    try {
      await fetch(`/api/custom-reminders/${reminder.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: !reminder.enabled }),
      })
      fetchCustomReminders()
    } catch { /* ignore */ }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">定时任务</h1>
          <p className="text-muted-foreground">管理自定义定时提醒和系统定时任务</p>
        </div>
        <Button onClick={fetchSchedulerStatus} size="sm" variant="outline">
          <RefreshCw className="w-4 h-4 mr-2" />
          刷新状态
        </Button>
      </div>

      {/* 自定义定时提醒 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <AlarmClock className="w-5 h-5" />
              自定义定时提醒
            </CardTitle>
            <Button size="sm" variant="outline" onClick={() => setShowAddReminder(true)}>
              <Plus className="w-4 h-4 mr-1" />
              添加提醒
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {customReminders.length === 0 ? (
            <p className="text-center text-muted-foreground py-4 text-sm">暂无自定义提醒，点击上方按钮添加</p>
          ) : (
            <div className="space-y-3">
              {customReminders.map((r) => {
                const typeLabel = r.repeat_type === 'daily' ? '每天' : r.repeat_type === 'weekly' ? ['周一','周二','周三','周四','周五','周六','周日'][r.repeat_day ?? 0] : `每月${r.repeat_day}日`
                return (
                  <div key={r.id} className="flex items-center justify-between p-3 rounded-lg border">
                    <div className="space-y-1 min-w-0 flex-1">
                      <div className="font-medium truncate">{r.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {typeLabel} {r.reminder_time}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={() => handleToggleReminder(r)}
                        className={`relative w-9 h-5 rounded-full transition-colors ${r.enabled ? 'bg-primary' : 'bg-muted'}`}
                      >
                        <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${r.enabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
                      </button>
                      <button onClick={() => handleDeleteReminder(r.id)} className="p-1 text-muted-foreground hover:text-destructive">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 定时任务状态 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="w-5 h-5" />
            定时任务状态
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loadingJobs ? (
            <p className="text-center text-muted-foreground py-8">加载中...</p>
          ) : jobs.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">暂无定时任务</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-4 text-sm font-medium">任务名称</th>
                    <th className="text-left py-3 px-4 text-sm font-medium">触发器</th>
                    <th className="text-left py-3 px-4 text-sm font-medium">下次执行</th>
                    <th className="text-left py-3 px-4 text-sm font-medium">状态</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr key={job.id} className="border-b">
                      <td className="py-3 px-4">
                        <span className="font-medium">{job.name}</span>
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {job.trigger}
                      </td>
                      <td className="py-3 px-4 text-sm text-muted-foreground">
                        {job.next_run_time ? job.next_run_time.split('+')[0] : '-'}
                      </td>
                      <td className="py-3 px-4">
                        {job.enabled ? (
                          <Badge variant="secondary" className="bg-green-100 text-green-700">运行中</Badge>
                        ) : (
                          <Badge variant="secondary" className="bg-gray-100 text-gray-500">已暂停</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 添加自定义提醒模态框 */}
      {showAddReminder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg bg-card p-6 shadow-xl">
            <h3 className="text-xl font-bold mb-4">添加自定义提醒</h3>
            <form onSubmit={handleCreateReminder} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">提醒名称 *</label>
                <input type="text" value={newReminder.name} onChange={(e) => setNewReminder({...newReminder, name: e.target.value})}
                  className="bg-background w-full rounded-md border border-input px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary" placeholder="如：喝水提醒" required />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">推送标题 *</label>
                <input type="text" value={newReminder.title} onChange={(e) => setNewReminder({...newReminder, title: e.target.value})}
                  className="bg-background w-full rounded-md border border-input px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary" placeholder="如：💧 喝水时间" required />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">推送内容</label>
                <textarea value={newReminder.content} onChange={(e) => setNewReminder({...newReminder, content: e.target.value})}
                  className="bg-background w-full rounded-md border border-input px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary" rows={2} placeholder="可选" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">重复类型</label>
                  <select value={newReminder.repeat_type} onChange={(e) => setNewReminder({...newReminder, repeat_type: e.target.value})}
                    className="bg-background w-full rounded-md border border-input px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary">
                    <option value="daily">每天</option>
                    <option value="weekly">每周</option>
                    <option value="monthly">每月</option>
                  </select>
                </div>
                {newReminder.repeat_type !== 'daily' && (
                  <div>
                    <label className="block text-sm font-medium mb-1">{newReminder.repeat_type === 'weekly' ? '星期几' : '日期'}</label>
                    {newReminder.repeat_type === 'weekly' ? (
                      <select value={newReminder.repeat_day} onChange={(e) => setNewReminder({...newReminder, repeat_day: e.target.value})}
                        className="bg-background w-full rounded-md border border-input px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary">
                        <option value="0">周一</option><option value="1">周二</option><option value="2">周三</option>
                        <option value="3">周四</option><option value="4">周五</option><option value="5">周六</option><option value="6">周日</option>
                      </select>
                    ) : (
                      <input type="number" min={1} max={31} value={newReminder.repeat_day} onChange={(e) => setNewReminder({...newReminder, repeat_day: e.target.value})}
                        className="bg-background w-full rounded-md border border-input px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary" />
                    )}
                  </div>
                )}
                {newReminder.repeat_type === 'daily' && <div />}
                <div>
                  <label className="block text-sm font-medium mb-1">推送时间</label>
                  <input type="time" value={newReminder.reminder_time} onChange={(e) => setNewReminder({...newReminder, reminder_time: e.target.value})}
                    className="bg-background w-full rounded-md border border-input px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary" required />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setShowAddReminder(false)}
                  className="flex-1 rounded-md border border-input px-4 py-2 text-sm font-medium hover:bg-accent transition-colors">取消</button>
                <button type="submit"
                  className="flex-1 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors">创建</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}