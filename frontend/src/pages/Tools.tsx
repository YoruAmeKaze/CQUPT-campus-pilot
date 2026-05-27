import { useState } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { ArrowLeft, Search } from 'lucide-react'
import Rooms from './Rooms'

type ToolId = 'empty-rooms'

interface ToolDef {
  id: ToolId
  name: string
  description: string
  icon: typeof Search
  color: string
}

const tools: ToolDef[] = [
  {
    id: 'empty-rooms',
    name: '空教室查询',
    description: '查询各教学楼空闲教室，按时间、教学楼、座位数筛选',
    icon: Search,
    color: 'text-emerald-500',
  },
]

export default function Tools() {
  const [activeTool, setActiveTool] = useState<ToolId | null>(null)

  if (activeTool === 'empty-rooms') {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setActiveTool(null)}
            className="shrink-0"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <h1 className="text-xl font-bold">空教室查询</h1>
            <p className="text-sm text-muted-foreground">
              返回工具列表
            </p>
          </div>
        </div>
        <Rooms />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">工具</h1>
        <p className="text-muted-foreground text-sm mt-1">
          选择工具开始使用
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {tools.map((tool) => {
          const Icon = tool.icon
          return (
            <Card
              key={tool.id}
              className="cursor-pointer transition-all hover:border-primary/50 hover:shadow-md hover:-translate-y-0.5"
              onClick={() => setActiveTool(tool.id)}
            >
              <CardContent className="p-5">
                <div className="flex items-start gap-4">
                  <div className={`p-2.5 rounded-lg bg-primary/10 ${tool.color}`}>
                    <Icon className="w-6 h-6" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-base mb-1">{tool.name}</h3>
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {tool.description}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
