import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Check, Trash2, Plus, ChevronDown, ChevronUp, RefreshCw, Clock, BookOpen, Calendar } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface Assignment {
  id: number
  title: string
  description: string
  course_name: string
  due_time: string
  is_completed: boolean
  created_at: string
}

interface DataSource {
  id: number
  type: string
  name: string
  enabled: boolean
  credentials: {
    username?: string
    password?: string
  }
  last_sync: string
  sync_status: string
}

const DATA_SOURCE_TYPES = [
  { value: 'chaoxing', label: '学习通', description: '超星学习通作业抓取' },
  { value: 'smartestu', label: '数你最灵', description: '数你最灵作业抓取' },
]

export default function Assignments() {
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [loading, setLoading] = useState(true)
  const [sources, setSources] = useState<DataSource[]>([
    {
      id: 1,
      type: 'chaoxing',
      name: '学习通',
      enabled: true,
      credentials: { username: '' },
      last_sync: '2026-05-25 11:00',
      sync_status: 'ok',
    },
  ])
  const [expandedSource, setExpandedSource] = useState<number | null>(null)
  const [showAddSource, setShowAddSource] = useState(false)
  const [newSource, setNewSource] = useState({
    type: '',
    username: '',
    password: '',
  })

  useEffect(() => {
    fetchAssignments()
  }, [])

  const fetchAssignments = async () => {
    try {
      setLoading(true)
      const res = await fetch('/api/assignments')
      if (res.ok) {
        const data = await res.json()
        setAssignments(data.assignments || [])
      }
    } catch (error) {
      console.error('获取作业失败:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleMarkCompleted = async (id: number) => {
    try {
      const res = await fetch(`/api/assignments/${id}/complete`, { method: 'POST' })
      if (res.ok) {
        fetchAssignments()
      }
    } catch (error) {
      console.error('标记完成失败:', error)
    }
  }

  const handleSync = async () => {
    try {
      const res = await fetch('/api/assignments/sync', { method: 'POST' })
      if (res.ok) {
        fetchAssignments()
      }
    } catch (error) {
      console.error('同步作业失败:', error)
    }
  }

  const handleAddSource = () => {
    if (newSource.type && newSource.username) {
      const sourceType = DATA_SOURCE_TYPES.find(t => t.value === newSource.type)
      const newItem: DataSource = {
        id: Date.now(),
        type: newSource.type,
        name: sourceType?.label || newSource.type,
        enabled: true,
        credentials: {
          username: newSource.username,
          password: newSource.password,
        },
        last_sync: '-',
        sync_status: 'pending',
      }
      setSources([...sources, newItem])
      setShowAddSource(false)
      setNewSource({ type: '', username: '', password: '' })
    }
  }

  const handleToggleSource = (id: number) => {
    setSources(sources.map(s =>
      s.id === id ? { ...s, enabled: !s.enabled } : s
    ))
  }

  const handleDeleteSource = (id: number) => {
    setSources(sources.filter(s => s.id !== id))
  }

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '-'
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'ok':
        return <Badge variant="secondary" className="bg-green-100 text-green-700 hover:bg-green-100">正常</Badge>
      case 'error':
        return <Badge variant="secondary" className="bg-red-100 text-red-700 hover:bg-red-100">异常</Badge>
      default:
        return <Badge variant="secondary" className="bg-yellow-100 text-yellow-700 hover:bg-yellow-100">待同步</Badge>
    }
  }

  const pendingAssignments = assignments.filter(a => !a.is_completed)
  const completedAssignments = assignments.filter(a => a.is_completed)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">作业</h1>
          <p className="text-muted-foreground">管理学习平台的作业任务</p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={handleSync} size="sm" variant="outline">
            <RefreshCw className="w-4 h-4 mr-2" />
            同步作业
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BookOpen className="w-5 h-5" />
              数据源配置
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {sources.map(source => {
                const typeInfo = DATA_SOURCE_TYPES.find(t => t.value === source.type)
                return (
                  <div key={source.id} className="border rounded-lg overflow-hidden">
                    <div
                      className="flex items-center justify-between p-4 hover:bg-accent/50 cursor-pointer"
                      onClick={() => setExpandedSource(expandedSource === source.id ? null : source.id)}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${source.enabled ? 'bg-green-500' : 'bg-gray-300'}`} />
                        <div>
                          <div className="font-medium">{source.name}</div>
                          <div className="text-sm text-muted-foreground">{typeInfo?.description}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        {getStatusBadge(source.sync_status)}
                        {expandedSource === source.id ? (
                          <ChevronUp className="w-4 h-4" />
                        ) : (
                          <ChevronDown className="w-4 h-4" />
                        )}
                      </div>
                    </div>
                    {expandedSource === source.id && (
                      <div className="p-4 pt-0 space-y-4">
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <Label className="text-xs">账号</Label>
                            <p className="text-muted-foreground">{source.credentials.username || '-'}</p>
                          </div>
                          <div>
                            <Label className="text-xs">最后同步</Label>
                            <p className="text-muted-foreground">{source.last_sync}</p>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleToggleSource(source.id)
                            }}
                          >
                            {source.enabled ? '禁用' : '启用'}
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="text-destructive hover:text-destructive"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleDeleteSource(source.id)
                            }}
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                )
              })}
              <Button
                variant="outline"
                className="w-full mt-2"
                onClick={() => setShowAddSource(true)}
              >
                <Plus className="w-4 h-4 mr-2" />
                添加数据源
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock className="w-5 h-5" />
              待完成作业
              {pendingAssignments.length > 0 && (
                <Badge variant="secondary">{pendingAssignments.length}</Badge>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-center text-muted-foreground py-8">加载中...</p>
            ) : pendingAssignments.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">暂无待完成作业</p>
            ) : (
              <div className="space-y-3">
                {pendingAssignments.map(assignment => (
                  <div
                    key={assignment.id}
                    className="flex items-center gap-3 p-3 rounded-lg border hover:bg-accent/50"
                  >
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleMarkCompleted(assignment.id)}
                      className="h-8 w-8"
                    >
                      <Check className="w-4 h-4" />
                    </Button>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{assignment.title}</div>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <span>{assignment.course_name}</span>
                        <span>·</span>
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {formatDate(assignment.due_time)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {completedAssignments.length > 0 && (
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>已完成作业</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {completedAssignments.map(assignment => (
                  <div
                    key={assignment.id}
                    className="flex items-center gap-3 p-3 rounded-lg border opacity-60"
                  >
                    <div className="w-8 h-8 rounded-full bg-green-100 flex items-center justify-center">
                      <Check className="w-4 h-4 text-green-600" />
                    </div>
                    <div className="flex-1">
                      <div className="font-medium line-through">{assignment.title}</div>
                      <div className="text-sm text-muted-foreground">
                        {assignment.course_name}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      <Dialog open={showAddSource} onOpenChange={setShowAddSource}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>添加数据源</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>平台类型</Label>
              <Select value={newSource.type} onValueChange={(v) => setNewSource({ ...newSource, type: v })}>
                <SelectTrigger>
                  <SelectValue placeholder="请选择平台" />
                </SelectTrigger>
                <SelectContent>
                  {DATA_SOURCE_TYPES.map(type => (
                    <SelectItem key={type.value} value={type.value}>
                      {type.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>账号</Label>
              <Input
                value={newSource.username}
                onChange={(e) => setNewSource({ ...newSource, username: e.target.value })}
                placeholder="请输入账号"
              />
            </div>
            <div className="space-y-2">
              <Label>密码</Label>
              <Input
                type="password"
                value={newSource.password}
                onChange={(e) => setNewSource({ ...newSource, password: e.target.value })}
                placeholder="请输入密码"
              />
            </div>
            <Button onClick={handleAddSource} className="w-full">
              添加数据源
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
