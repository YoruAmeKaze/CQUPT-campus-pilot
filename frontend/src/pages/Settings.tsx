import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
  Brain,
  Shield,
  Smartphone,
} from 'lucide-react'

interface SystemConfig {
  student_id: string
  term_start_date: string
  bark_key: string
  feishu_webhook_url: string
  deploy_mode: string
  auto_cleanup_enabled: boolean
  auto_cleanup_days: number
  chaoxing_username: string
  chaoxing_password: string
  smartestu_student_id: string
  smartestu_password: string
  deepseek_api_key: string
  deepseek_model: string
  llm_base_url: string
  feishu_app_id: string
  feishu_app_secret: string
  tunnel_server_host: string
  tunnel_server_user: string
  tunnel_remote_port: string
  tunnel_local_port: string
  tunnel_key_path: string
  vpn_host: string
  vpn_username: string
  vpn_password: string
}

function InputField({ label, field, config, updateField, type = 'text', placeholder = '', className = '' }: {
  label: string
  field: keyof SystemConfig
  config: SystemConfig
  updateField: (field: keyof SystemConfig, value: string | boolean | number) => void
  type?: string
  placeholder?: string
  className?: string
}) {
  return (
    <div className={`space-y-2 ${className}`}>
      <Label htmlFor={field}>{label}</Label>
      <Input
        id={field}
        type={type}
        value={String(config[field] ?? '')}
        onChange={(e) => updateField(field, e.target.value)}
        placeholder={placeholder}
      />
    </div>
  )
}

function SecretField({ label, field, config, updateField, placeholder = '' }: {
  label: string
  field: keyof SystemConfig
  config: SystemConfig
  updateField: (field: keyof SystemConfig, value: string | boolean | number) => void
  placeholder?: string
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={field}>{label}</Label>
      <Input
        id={field}
        type="password"
        value={String(config[field] ?? '')}
        onChange={(e) => updateField(field, e.target.value)}
        placeholder={placeholder}
      />
    </div>
  )
}

export default function Settings() {
  const [config, setConfig] = useState<SystemConfig>({
    student_id: '',
    term_start_date: '2026-03-02',
    bark_key: '',
    feishu_webhook_url: '',
    deploy_mode: 'laptop',
    auto_cleanup_enabled: false,
    auto_cleanup_days: 30,
    chaoxing_username: '',
    chaoxing_password: '',
    smartestu_student_id: '',
    smartestu_password: '',
    deepseek_api_key: '',
    deepseek_model: 'deepseek-chat',
    llm_base_url: 'https://api.deepseek.com',
    feishu_app_id: '',
    feishu_app_secret: '',
    tunnel_server_host: '',
    tunnel_server_user: '',
    tunnel_remote_port: '9999',
    tunnel_local_port: '8000',
    tunnel_key_path: '',
    vpn_host: 'vpn.cqupt.edu.cn',
    vpn_username: '',
    vpn_password: '',
  })
  const [cleanupResult, setCleanupResult] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<'success' | 'error' | null>(null)
  const [testingFeishu, setTestingFeishu] = useState(false)
  const [feishuTestResult, setFeishuTestResult] = useState<'success' | 'error' | null>(null)

  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    try {
      const res = await fetch('/api/config')
      if (res.ok) {
        const data: SystemConfig = await res.json()
        setConfig(data)
      }
    } catch (error) {
      console.error('获取配置失败:', error)
    }
  }

  const updateField = (field: keyof SystemConfig, value: string | boolean | number) => {
    setConfig(prev => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    try {
      const res = await fetch('/api/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          term_start_date: config.term_start_date,
          bark_key: config.bark_key,
          feishu_webhook_url: config.feishu_webhook_url,
          auto_cleanup_enabled: config.auto_cleanup_enabled,
          auto_cleanup_days: config.auto_cleanup_days,
          student_id: config.student_id,
          chaoxing_username: config.chaoxing_username,
          chaoxing_password: config.chaoxing_password,
          smartestu_student_id: config.smartestu_student_id,
          smartestu_password: config.smartestu_password,
          deepseek_api_key: config.deepseek_api_key,
          deepseek_model: config.deepseek_model,
          llm_base_url: config.llm_base_url,
          feishu_app_id: config.feishu_app_id,
          feishu_app_secret: config.feishu_app_secret,
          tunnel_server_host: config.tunnel_server_host,
          tunnel_server_user: config.tunnel_server_user,
          tunnel_remote_port: config.tunnel_remote_port,
          tunnel_local_port: config.tunnel_local_port,
          tunnel_key_path: config.tunnel_key_path,
          vpn_host: config.vpn_host,
          vpn_username: config.vpn_username,
          vpn_password: config.vpn_password,
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

  const handleTestFeishu = async () => {
    try {
      setTestingFeishu(true)
      setFeishuTestResult(null)
      const res = await fetch('/api/notification/feishu/test', {
        method: 'POST',
      })
      if (res.ok) {
        setFeishuTestResult('success')
      } else {
        setFeishuTestResult('error')
      }
    } catch (error) {
      setFeishuTestResult('error')
    } finally {
      setTestingFeishu(false)
    }
  }

  const handleClearData = () => {
    if (confirm('确定要清空所有数据吗？此操作不可恢复！')) {
      console.log('清空数据')
    }
  }

  const handleCleanup = async () => {
    setCleanupResult(null)
    try {
      const res = await fetch('/api/assignments/cleanup', { method: 'POST' })
      const data = await res.json()
      setCleanupResult(data.message || '清理完成')
    } catch (error) {
      setCleanupResult('清理失败')
    }
  }

  const handleExportData = () => {
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
          <p className="text-muted-foreground">所有配置已迁移到数据库，修改即时生效</p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={handleSave} size="sm">
            <Save className="w-4 h-4 mr-2" />
            {saved ? '保存成功' : '保存设置'}
          </Button>
          {saved && (
            <Badge variant="secondary" className="bg-green-100 text-green-700">已保存</Badge>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-6">
          {/* 用户信息 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <User className="w-5 h-5" />
                用户信息
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <InputField label="学号" field="student_id" config={config} updateField={updateField} placeholder="STUDENT_ID" />
                <div className="space-y-2">
                  <Label>部署模式</Label>
                  <div className="flex items-center gap-2 p-2 rounded-md border bg-muted/50">
                    <Badge variant="secondary" className={config.deploy_mode === 'server' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'}>
                      {config.deploy_mode === 'server' ? '服务器模式' : '本地模式'}
                    </Badge>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* DeepSeek AI 配置 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Brain className="w-5 h-5" />
                DeepSeek AI 配置
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <SecretField label="API Key" field="deepseek_api_key" config={config} updateField={updateField} placeholder="sk-..." />
                <div className="space-y-2">
                  <Label htmlFor="deepseek_model">模型选择</Label>
                  <Select value={config.deepseek_model} onValueChange={(v) => updateField('deepseek_model', v)}>
                    <SelectTrigger id="deepseek_model">
                      <SelectValue placeholder="选择模型" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="deepseek-chat">DeepSeek-V3 (Flash)</SelectItem>
                      <SelectItem value="deepseek-reasoner">DeepSeek-R1 (Pro)</SelectItem>
                      <SelectItem value="qwen2.5">Qwen2.5 (Ollama)</SelectItem>
                      <SelectItem value="deepseek-r1:7b">DeepSeek-R1:7B (Ollama)</SelectItem>
                      <SelectItem value="llama3.1">Llama3.1 (Ollama)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <InputField label="API 地址" field="llm_base_url" config={config} updateField={updateField} placeholder="https://api.deepseek.com" />
            </CardContent>
          </Card>

          {/* 飞书应用配置 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Zap className="w-5 h-5" />
                飞书应用配置
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <InputField label="App ID" field="feishu_app_id" config={config} updateField={updateField} placeholder="cli_xxxxxxxxxxxx" />
                <SecretField label="App Secret" field="feishu_app_secret" config={config} updateField={updateField} />
              </div>
              <p className="text-sm text-muted-foreground">
                用于飞书应用机器人双向对话功能，需在飞书开发者后台创建应用并配置事件回调
              </p>
            </CardContent>
          </Card>

          {/* 飞书机器人 Webhook */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bell className="w-5 h-5" />
                飞书机器人 Webhook 配置
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="feishuWebhookUrl">飞书 Webhook URL</Label>
                  <Input
                    id="feishuWebhookUrl"
                    value={config.feishu_webhook_url}
                    onChange={(e) => updateField('feishu_webhook_url', e.target.value)}
                    placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/..."
                    type="url"
                  />
                </div>
                <div className="space-y-2 flex flex-col justify-end">
                  <Button
                    onClick={handleTestFeishu}
                    disabled={!config.feishu_webhook_url || testingFeishu}
                    className="w-full"
                    variant="outline"
                  >
                    <TestTube className="w-4 h-4 mr-2" />
                    {testingFeishu ? '测试中...' : '测试推送'}
                  </Button>
                  {feishuTestResult && (
                    <div>
                      <Badge variant={feishuTestResult === 'success' ? 'secondary' : 'destructive'} className={feishuTestResult === 'success' ? 'bg-green-100 text-green-700' : ''}>
                        {feishuTestResult === 'success' ? '✓ 飞书推送测试成功！' : '✗ 飞书推送测试失败，请检查 Webhook URL'}
                      </Badge>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 学期配置 */}
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
                    value={config.term_start_date}
                    onChange={(e) => updateField('term_start_date', e.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label>当前周次</Label>
                  <div className="flex items-center gap-2 p-2 rounded-md border bg-muted/50">
                    <Clock className="w-4 h-4 text-muted-foreground" />
                    <span className="font-medium">第 {Math.max(1, Math.floor((new Date().getTime() - new Date(config.term_start_date).getTime()) / (1000 * 60 * 60 * 24 * 7)) + 1)} 周</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Bark 推送配置 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Smartphone className="w-5 h-5" />
                Bark 推送配置
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="barkKey">Bark Key</Label>
                  <Input
                    id="barkKey"
                    value={config.bark_key}
                    onChange={(e) => updateField('bark_key', e.target.value)}
                    placeholder="从 Bark App 获取的 Key"
                  />
                </div>
                <div className="space-y-2 flex flex-col justify-end">
                  <Button
                    onClick={handleTestBark}
                    disabled={!config.bark_key || testing}
                    className="w-full"
                    variant="outline"
                  >
                    <TestTube className="w-4 h-4 mr-2" />
                    {testing ? '测试中...' : '测试推送'}
                  </Button>
                  {testResult && (
                    <div>
                      <Badge variant={testResult === 'success' ? 'secondary' : 'destructive'} className={testResult === 'success' ? 'bg-green-100 text-green-700' : ''}>
                        {testResult === 'success' ? '✓ 推送测试成功！' : '✗ 推送测试失败，请检查配置'}
                      </Badge>
                    </div>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 公网服务器配置 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Server className="w-5 h-5" />
                公网服务器配置
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <InputField label="服务器 IP" field="tunnel_server_host" config={config} updateField={updateField} placeholder="SERVER_IP" />
                <InputField label="用户名" field="tunnel_server_user" config={config} updateField={updateField} placeholder="root" />
                <InputField label="远程端口" field="tunnel_remote_port" config={config} updateField={updateField} placeholder="9999" />
                <InputField label="本地端口" field="tunnel_local_port" config={config} updateField={updateField} placeholder="8000" />
                <InputField label="SSH 密钥路径" field="tunnel_key_path" config={config} updateField={updateField} placeholder="/path/to/id_rsa" className="lg:col-span-2" />
              </div>
              <p className="text-sm text-muted-foreground">
                用于 SSH 反向隧道，将本地服务暴露到公网供飞书应用回调。配置了飞书应用 App ID 和 Secret 后会自动启动。
              </p>
            </CardContent>
          </Card>

          {/* VPN 配置 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Shield className="w-5 h-5" />
                VPN 配置（仅服务器模式）
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <InputField label="VPN 地址" field="vpn_host" config={config} updateField={updateField} placeholder="vpn.cqupt.edu.cn" />
                <InputField label="用户名" field="vpn_username" config={config} updateField={updateField} placeholder="统一身份认证账号" />
                <SecretField label="密码" field="vpn_password" config={config} updateField={updateField} />
              </div>
              <p className="text-sm text-muted-foreground">
                用于服务器模式下连接校园 VPN，访问校内教务系统等资源
              </p>
            </CardContent>
          </Card>

          {/* 数据管理 */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="w-5 h-5" />
                数据管理
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-3 rounded-lg border">
                <div className="flex items-center gap-3">
                  <Trash2 className="w-5 h-5 text-muted-foreground" />
                  <div>
                    <div className="font-medium">定期清除过时作业</div>
                    <div className="text-sm text-muted-foreground">
                      自动删除已完成超过 N 天的作业
                    </div>
                  </div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={config.auto_cleanup_enabled}
                    onChange={async (e) => {
                      const enabled = e.target.checked
                      updateField('auto_cleanup_enabled', enabled)
                      try {
                        await fetch('/api/config', {
                          method: 'PUT',
                          headers: { 'Content-Type': 'application/json' },
                          body: JSON.stringify({ auto_cleanup_enabled: enabled }),
                        })
                      } catch (error) {
                        console.error('保存自动清理设置失败:', error)
                      }
                    }}
                  />
                  <div className="w-9 h-5 bg-muted peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                </label>
              </div>
              {config.auto_cleanup_enabled && (
                <div className="flex items-center gap-3 pl-2">
                  <Label className="whitespace-nowrap">保留天数</Label>
                  <Input
                    type="number"
                    min={7}
                    max={365}
                    value={config.auto_cleanup_days}
                    onChange={(e) => updateField('auto_cleanup_days', parseInt(e.target.value) || 30)}
                    className="w-24"
                  />
                  <span className="text-sm text-muted-foreground">天</span>
                  <Button variant="outline" size="sm" onClick={handleCleanup} className="ml-auto">
                    <Trash2 className="w-3.5 h-3.5 mr-1.5" />
                    立即清理
                  </Button>
                </div>
              )}
              {cleanupResult && (
                <Badge variant="secondary" className="bg-green-100 text-green-700">{cleanupResult}</Badge>
              )}
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
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          {/* 快捷导航 */}
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

          {/* 关于系统 */}
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
                  <span className="text-muted-foreground">开发作者</span>
                  <span className="font-medium">Kazever</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">更新日期</span>
                  <span className="font-medium">2026-05-25</span>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* 服务状态 */}
          <Card>
            <CardHeader>
              <CardTitle>服务状态</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center justify-between p-2 rounded-md bg-muted/50">
                <span className="text-sm">后端服务</span>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-500" />
                  <span className="text-sm text-green-600">正常</span>
                </div>
              </div>
              <div className="flex items-center justify-between p-2 rounded-md bg-muted/50">
                <span className="text-sm">定时任务</span>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-500" />
                  <span className="text-sm text-green-600">运行中</span>
                </div>
              </div>
              <div className="flex items-center justify-between p-2 rounded-md bg-muted/50">
                <span className="text-sm">Bark 推送</span>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${config.bark_key ? 'bg-green-500' : 'bg-gray-300'}`} />
                  <span className={`text-sm ${config.bark_key ? 'text-green-600' : 'text-gray-400'}`}>
                    {config.bark_key ? '已配置' : '未配置'}
                  </span>
                </div>
              </div>
              <div className="flex items-center justify-between p-2 rounded-md bg-muted/50">
                <span className="text-sm">飞书机器人</span>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${config.feishu_webhook_url ? 'bg-green-500' : 'bg-gray-300'}`} />
                  <span className={`text-sm ${config.feishu_webhook_url ? 'text-green-600' : 'text-gray-400'}`}>
                    {config.feishu_webhook_url ? '已配置' : '未配置'}
                  </span>
                </div>
              </div>
              <div className="flex items-center justify-between p-2 rounded-md bg-muted/50">
                <span className="text-sm">DeepSeek AI</span>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${config.deepseek_api_key ? 'bg-green-500' : 'bg-gray-300'}`} />
                  <span className={`text-sm ${config.deepseek_api_key ? 'text-green-600' : 'text-gray-400'}`}>
                    {config.deepseek_api_key ? '已配置' : '未配置'}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
