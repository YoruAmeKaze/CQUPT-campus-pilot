import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { 
  User, 
  Calendar, 
  Database, 
  Info, 
  Bell, 
  Clock,
  Save,
  Download,
  Trash2,
  ChevronRight,
  TestTube,
  Zap,
  Server,
  RefreshCw,
} from 'lucide-react'

interface SystemConfig {
  student_id: string
  term_start_date: string
  bark_key: string
  deploy_mode: string
}

interface SchedulerJob {
  id: string
  name: string
  trigger: string
  next_run_time: string | null
  enabled: boolean
}

export default function Settings() {
  const [studentId, setStudentId] = useState('')
  const [termStartDate, setTermStartDate] = useState('2026-03-02')
  const [barkKey, setBarkKey] = useState('')
  const [deployMode, setDeployMode] = useState('laptop')
  const [saved, setSaved] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<'success' | 'error' | null>(null)
  const [jobs, setJobs] = useState<SchedulerJob[]>([])
  const [loadingJobs, setLoadingJobs] = useState(true)

  useEffect(() => {
    fetchConfig()
    fetchSchedulerStatus()
  }, [])

  const fetchConfig = async () => {
    try {
      const res = await fetch('/api/config')
      if (res.ok) {
        const config: SystemConfig = await res.json()
        setStudentId(config.student_id)
        setTermStartDate(config.term_start_date)
        setBarkKey(config.bark_key)
        setDeployMode(config.deploy_mode)
      }
    } catch (error) {
      console.error('获取配置失败:', error)
    }
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

  const handleSave = async () => {
    try {
      const res = await fetch('/api/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          student_id: studentId,
          term_start_date: termStartDate,
          bark_key: barkKey,
        }),
      })
      if (res.ok) {
        setSaved(true)
        setTimeout(() => setSaved(false), 2000)
      }
    } catch (error) {
      console.error('保存配置失败:', error)
    }
  }

  const handleTestBark = async () => {
    try {
      setTesting(true)
      setTestResult(null)
      const res = await fetch('/api/notification/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: '测试消息', title: 'CampusPilot 测试' }),
      })
      if (res.ok) {
        setTestResult('success')
      } else {
        setTestResult('error')
      }
    } catch (error) {
      setTestResult('error')
    } finally {
      setTesting(false)
    }
  }

  const handleClearData = () => {
    if (confirm('确定要清空所有数据吗？此操作不可恢复！')) {
      console.log('清空数据')
    }
  }

  const handleExportData = () => {
    console.log('导出数据')
    alert('数据导出功能开发中...')
  }

  const quickActions = [
    { 
      icon: <Bell className="w-5 h-5" />, 
      title: '通知设置', 
      description: '管理推送通知的类型和时间',
      href: '/notifications',
    },
    { 
      icon: <Calendar className="w-5 h-5" />, 
      title: '课表配置', 
      description: '配置学号和同步课表',
      href: '/courses',
    },
    { 
      icon: <Database className="w-5 h-5" />, 
      title: '作业数据源', 
      description: '配置学习通、数你最灵等平台',
      href: '/assignments',
    },
  ]

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">系统配置</h1>
          <p className="text-muted-foreground">管理个人设置和系统配置</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            onClick={fetchSchedulerStatus}
            size="sm"
            variant="outline"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            刷新状态
          </Button>
          <Button onClick={handleSave} size="sm" className={saved ? 'bg-green-600' : ''}>
            <Save className="w-4 h-4 mr-2" />
            {saved ? '保存成功' : '保存设置'}
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="w-5 h-5" />
                用户信息
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="studentId">学号</Label>
                  <Input
                    id="studentId"
                    value={studentId}
                    onChange={(e) => setStudentId(e.target.value)}
                    placeholder="请输入学号"
                  />
                </div>
                <div className="space-y-2">
                  <Label>部署模式</Label>
                  <div className="flex items-center gap-2 p-2 rounded-md border bg-muted/50">
                    <Badge variant="secondary" className={deployMode === 'server' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}>
                      {deployMode === 'server' ? '服务器模式' : '本地模式'}
                    </Badge>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="w-5 h-5" />
                学期配置
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="termStartDate">学期开始日期</Label>
                  <Input
                    id="termStartDate"
                    type="date"
                    value={termStartDate}
                    onChange={(e) => setTermStartDate(e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>当前周次</Label>
                  <div className="flex items-center gap-2 p-2 rounded-md border bg-muted/50">
                    <Clock className="w-4 h-4 text-muted-foreground" />
                    <span className="font-medium">第 15 周</span>
                  </div>
                </div>
              </div>
              <p className="text-sm text-muted-foreground">
                学期开始日期用于计算当前周次和课程安排，请确保设置正确。
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bell className="w-5 h-5" />
                Bark 推送配置
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="barkKey">Bark Key</Label>
                  <Input
                    id="barkKey"
                    value={barkKey}
                    onChange={(e) => setBarkKey(e.target.value)}
                    placeholder="从 Bark App 获取的 Key"
                  />
                </div>
                <div className="space-y-2 flex flex-col justify-end">
                  <Button
                    onClick={handleTestBark}
                    disabled={!barkKey || testing}
                    className="w-full"
                    variant="outline"
                  >
                    <TestTube className="w-4 h-4 mr-2" />
                    {testing ? '测试中...' : '测试推送'}
                  </Button>
                  {testResult && (
                    <div className={`text-sm ${testResult === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                      {testResult === 'success' ? '✓ 推送测试成功！' : '✗ 推送测试失败，请检查配置'}
                    </div>
                  )}
                </div>
              </div>
              <div className="p-3 rounded-lg bg-muted/50">
                <p className="text-sm text-muted-foreground">
                  <strong className="text-foreground">使用说明：</strong>
                  在 iOS 设备上安装 Bark App，复制 App 显示的 Key 粘贴到上方输入框。
                  Bark 可以将通知推送到你的 iPhone，支持自定义铃声和图标。
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Server className="w-5 h-5" />
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

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="w-5 h-5" />
                数据管理
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={handleExportData}
                >
                  <Download className="w-4 h-4 mr-2" />
                  导出数据
                </Button>
                <Button
                  variant="outline"
                  className="w-full justify-start text-destructive hover:text-destructive"
                  onClick={handleClearData}
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  清空数据
                </Button>
              </div>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div className="p-4 rounded-lg bg-muted/50">
                  <div className="text-2xl font-bold">15</div>
                  <div className="text-sm text-muted-foreground">课程</div>
                </div>
                <div className="p-4 rounded-lg bg-muted/50">
                  <div className="text-2xl font-bold">2</div>
                  <div className="text-sm text-muted-foreground">作业</div>
                </div>
                <div className="p-4 rounded-lg bg-muted/50">
                  <div className="text-2xl font-bold">0</div>
                  <div className="text-sm text-muted-foreground">待办</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>快捷导航</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {quickActions.map((action) => (
                  <a
                    key={action.title}
                    href={action.href}
                    className="flex items-center justify-between p-3 rounded-lg hover:bg-accent/50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-lg bg-primary/10 text-primary">
                        {action.icon}
                      </div>
                      <div className="text-left">
                        <div className="font-medium">{action.title}</div>
                        <div className="text-sm text-muted-foreground">{action.description}</div>
                      </div>
                    </div>
                    <ChevronRight className="w-4 h-4 text-muted-foreground" />
                  </a>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Info className="w-5 h-5" />
                关于系统
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">系统名称</span>
                  <span className="font-medium">CampusPilot</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">版本</span>
                  <span className="font-medium">v2.0.0</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">开发团队</span>
                  <span className="font-medium">CQUPT</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">更新日期</span>
                  <span className="font-medium">2026-05-25</span>
                </div>
              </div>
              <div className="p-3 rounded-lg bg-primary/5 border border-primary/20">
                <p className="text-sm text-primary">
                  CampusPilot 是重庆邮电大学个人学业智能助理，帮助你管理课表、作业和待办事项。
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>服务状态</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm">后端服务</span>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  <span className="text-sm text-green-600">正常</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">定时任务</span>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  <span className="text-sm text-green-600">运行中</span>
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm">Bark 推送</span>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${barkKey ? 'bg-green-500 animate-pulse' : 'bg-gray-300'}`} />
                  <span className={`text-sm ${barkKey ? 'text-green-600' : 'text-gray-400'}`}>
                    {barkKey ? '已配置' : '未配置'}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="w-5 h-5" />
                使用提示
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="text-sm space-y-2">
                <p><strong>课表同步：</strong>在课表页面点击"同步课表"按钮可以从教务系统获取最新课表。</p>
                <p><strong>作业抓取：</strong>在作业页面配置学习通等数据源后，系统会自动抓取作业。</p>
                <p><strong>通知设置：</strong>在通知页面可以自定义推送时间和内容模板。</p>
                <p><strong>Bark 推送：</strong>配置 Bark Key 后可以接收 iOS 推送通知。</p>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}