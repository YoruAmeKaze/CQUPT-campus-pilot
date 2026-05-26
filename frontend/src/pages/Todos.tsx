import { useState, useEffect, useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Plus, Check, Trash2, Calendar, AlertCircle, ArrowUpDown, Clock } from 'lucide-react'

interface Todo {
  id: number
  title: string
  description?: string
  due_time?: string
  priority: 'low' | 'normal' | 'high'
  is_completed: boolean
  source: string
  reminder_enabled: boolean
  reminder_sent: boolean
  created_at: string
}

export default function Todos() {
  const [todos, setTodos] = useState<Todo[]>([])
  const [filter, setFilter] = useState('all') // all | pending | completed
  const [sortBy, setSortBy] = useState<'due_time' | 'priority'>('priority')
  const [showAddModal, setShowAddModal] = useState(false)
  const [newTodo, setNewTodo] = useState({
    title: '',
    description: '',
    due_time: '',
    priority: 'normal' as 'low' | 'normal' | 'high',
    reminder_enabled: false,
  })
  const [loading, setLoading] = useState(true)

  // 加载待办事项
  useEffect(() => {
    fetchTodos()
  }, [filter])

  const fetchTodos = async () => {
    try {
      setLoading(true)
      const params = new URLSearchParams()
      if (filter !== 'all') {
        params.append('status', filter)
      }

      const res = await fetch(`/api/todos?${params.toString()}`)
      const data = await res.json()
      if (data.success) {
        setTodos(data.todos)
      }
    } catch (err) {
      console.error('加载待办事项失败:', err)
    } finally {
      setLoading(false)
    }
  }

  // 创建待办事项
  const handleCreateTodo = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const body = {
        title: newTodo.title,
        description: newTodo.description || null,
        due_time: newTodo.due_time || null,
        priority: newTodo.priority,
        source: 'manual',
        reminder_enabled: newTodo.reminder_enabled,
      }
      const res = await fetch('/api/todos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (data.success) {
        setShowAddModal(false)
        setNewTodo({ title: '', description: '', due_time: '', priority: 'normal', reminder_enabled: false })
        fetchTodos()
      }
    } catch (err) {
      console.error('创建待办事项失败:', err)
    }
  }

  // 标记完成
  const handleCompleteTodo = async (id: number) => {
    try {
      const res = await fetch(`/api/todos/${id}/complete`, {
        method: 'POST',
      })
      const data = await res.json()
      if (data.success) {
        fetchTodos()
      }
    } catch (err) {
      console.error('标记完成失败:', err)
    }
  }

  // 删除待办事项
  const handleDeleteTodo = async (id: number) => {
    if (!confirm('确定要删除这个待办事项吗？')) return
    try {
      const res = await fetch(`/api/todos/${id}`, {
        method: 'DELETE',
      })
      const data = await res.json()
      if (data.success) {
        fetchTodos()
      }
    } catch (err) {
      console.error('删除失败:', err)
    }
  }

  // 优先级颜色
  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return 'bg-red-100 text-red-700 border-red-200'
      case 'normal':
        return 'bg-yellow-100 text-yellow-700 border-yellow-200'
      case 'low':
        return 'bg-green-100 text-green-700 border-green-200'
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200'
    }
  }

  // 优先级权重
  const getPriorityWeight = (priority: string) => {
    switch (priority) {
      case 'high': return 3
      case 'normal': return 2
      case 'low': return 1
      default: return 0
    }
  }

  // 格式化日期
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return ''
    return new Date(dateStr).toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  // 排序后的待办列表
  const sortedTodos = useMemo(() => {
    return [...todos].sort((a, b) => {
      if (sortBy === 'due_time') {
        // 按截止时间排序，没有截止时间的排在最后
        if (!a.due_time) return 1
        if (!b.due_time) return -1
        return new Date(a.due_time).getTime() - new Date(b.due_time).getTime()
      } else {
        // 按优先级排序，高优先级在前
        return getPriorityWeight(b.priority) - getPriorityWeight(a.priority)
      }
    })
  }, [todos, sortBy])

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">待办事项</h1>
          <p className="text-muted-foreground">
            管理您的待办事项，支持通过飞书自然语言创建
          </p>
        </div>

        {/* 添加按钮 */}
        <button
          onClick={() => setShowAddModal(true)}
          className="flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Plus className="h-4 w-4" />
          添加待办
        </button>
      </div>

      {/* 筛选和排序按钮 */}
      <div className="flex flex-wrap gap-2 items-center">
        {['all', 'pending', 'completed'].map((status) => (
          <button
            key={status}
            onClick={() => setFilter(status)}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              filter === status
                ? 'bg-primary text-primary-foreground'
                : 'border border-input hover:bg-accent'
            }`}
          >
            {status === 'all' && '全部'}
            {status === 'pending' && '未完成'}
            {status === 'completed' && '已完成'}
          </button>
        ))}
        
        <div className="h-6 w-px bg-gray-200 mx-2" />
        
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground flex items-center gap-1">
            <ArrowUpDown className="h-4 w-4" />
            排序:
          </span>
          <button
            onClick={() => setSortBy('priority')}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors flex items-center gap-1 ${
              sortBy === 'priority'
                ? 'bg-primary text-primary-foreground'
                : 'border border-input hover:bg-accent'
            }`}
          >
            <AlertCircle className="h-4 w-4" />
            重要性
          </button>
          <button
            onClick={() => setSortBy('due_time')}
            className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors flex items-center gap-1 ${
              sortBy === 'due_time'
                ? 'bg-primary text-primary-foreground'
                : 'border border-input hover:bg-accent'
            }`}
          >
            <Clock className="h-4 w-4" />
            截止时间
          </button>
        </div>
      </div>

      {/* 待办列表 */}
      <Card>
        <CardHeader>
          <CardTitle>待办列表 ({todos.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex h-[400px] items-center justify-center text-muted-foreground">
              <p>加载中...</p>
            </div>
          ) : todos.length === 0 ? (
            <div className="flex h-[400px] items-center justify-center text-muted-foreground">
              <div className="text-center space-y-2">
                <p className="text-lg">✅</p>
                <p>暂无待办事项</p>
                <p className="text-sm">点击上方按钮添加新待办</p>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {sortedTodos.map((todo) => (
                <div
                  key={todo.id}
                  className={`flex items-center justify-between p-4 rounded-lg border ${
                    todo.is_completed ? 'bg-muted/30 border-border/50' : 'bg-card border-border'
                  }`}
                >
                  <div className="flex items-start gap-4">
                    <button
                      onClick={() => handleCompleteTodo(todo.id)}
                      className={`mt-1 rounded-full border-2 p-1 transition-colors ${
                        todo.is_completed
                          ? 'bg-green-500 border-green-500 text-white'
                          : 'border-gray-300 hover:border-green-500'
                      }`}
                      disabled={todo.is_completed}
                    >
                      {todo.is_completed && <Check className="h-3 w-3" />}
                    </button>
                    <div className="space-y-1">
                      <p
                        className={`font-medium ${
                          todo.is_completed ? 'text-gray-400 line-through' : 'text-foreground'
                        }`}
                      >
                        {todo.title}
                      </p>
                      {todo.description && (
                        <p className="text-sm text-muted-foreground">{todo.description}</p>
                      )}
                      <div className="flex items-center gap-3">
                        <span
                          className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium border ${getPriorityColor(
                            todo.priority
                          )}`}
                        >
                          {todo.priority === 'high' && <AlertCircle className="h-3 w-3" />}
                          {todo.priority === 'normal' && '普通'}
                          {todo.priority === 'low' && '低'}
                          {todo.priority === 'high' && '高'}
                        </span>
                        {todo.due_time && (
                          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                            <Calendar className="h-3 w-3" />
                            {formatDate(todo.due_time)}
                          </span>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {todo.source === 'llm' ? '🤖 来自 LLM' : '✏️ 手动创建'}
                        </span>
                        {todo.reminder_enabled && (
                          <span className="inline-flex items-center gap-1 text-xs text-amber-500" title={todo.reminder_sent ? '提醒已发送' : '提醒已开启'}>
                            {todo.reminder_sent ? '🔔 已提醒' : '🔕 提醒中'}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {!todo.is_completed && (
                      <button
                        onClick={() => handleCompleteTodo(todo.id)}
                        className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-green-600 transition-colors"
                        title="标记完成"
                      >
                        <Check className="h-4 w-4" />
                      </button>
                    )}
                    <button
                      onClick={() => handleDeleteTodo(todo.id)}
                      className="rounded-md p-2 text-muted-foreground hover:bg-accent hover:text-red-600 transition-colors"
                      title="删除"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 添加待办模态框 */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-lg bg-card p-6 shadow-xl">
            <h3 className="text-xl font-bold mb-4">添加待办事项</h3>
            <form onSubmit={handleCreateTodo} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">标题 *</label>
                <input
                  type="text"
                  value={newTodo.title}
                  onChange={(e) => setNewTodo({ ...newTodo, title: e.target.value })}
                  className="w-full rounded-md border border-input px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="输入待办事项标题"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">描述</label>
                <textarea
                  value={newTodo.description}
                  onChange={(e) => setNewTodo({ ...newTodo, description: e.target.value })}
                  className="w-full rounded-md border border-input px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="输入详细描述（可选）"
                  rows={3}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">截止时间</label>
                  <input
                    type="datetime-local"
                    value={newTodo.due_time}
                    onChange={(e) => setNewTodo({ ...newTodo, due_time: e.target.value })}
                    className="w-full rounded-md border border-input px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">优先级</label>
                  <select
                    value={newTodo.priority}
                    onChange={(e) => setNewTodo({ ...newTodo, priority: e.target.value as any })}
                    className="w-full rounded-md border border-input px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="low">低</option>
                    <option value="normal">普通</option>
                    <option value="high">高</option>
                  </select>
                </div>
              </div>
              <div className="flex items-center gap-2 p-3 rounded-lg bg-muted/50">
                <input
                  type="checkbox"
                  id="reminder_enabled"
                  checked={newTodo.reminder_enabled}
                  onChange={(e) => setNewTodo({ ...newTodo, reminder_enabled: e.target.checked })}
                  className="rounded border-gray-300"
                />
                <label htmlFor="reminder_enabled" className="text-sm cursor-pointer">
                  到期前 1 小时推送提醒（需配置 Bark 或飞书）
                </label>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="flex-1 rounded-md border border-input px-4 py-2 text-sm font-medium hover:bg-accent transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="flex-1 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
                >
                  创建
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
