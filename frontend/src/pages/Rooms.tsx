import { useState, useEffect } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Search, RefreshCw, MapPin, Users, Building2 } from 'lucide-react'

const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const SLOT_OPTIONS = [
  { value: '1', label: '1-2节 (08:00-09:40)' },
  { value: '3', label: '3-4节 (10:15-11:55)' },
  { value: '5', label: '5-6节 (14:00-15:40)' },
  { value: '7', label: '7-8节 (16:15-17:55)' },
  { value: '9', label: '9-10节 (19:00-20:40)' },
  { value: '11', label: '11-12节 (20:50-22:30)' },
]

interface Room {
  room_name: string
  room_type: string
  capacity: number
  building: string
}

function getTodayWeekday(): number {
  return new Date().getDay() || 7
}

function getCurrentWeek(): number {
  return parseInt(localStorage.getItem('currentWeek') || '1')
}

export default function Rooms() {
  const [rooms, setRooms] = useState<Room[]>([])
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [stats, setStats] = useState<any>(null)

  // 查询条件
  const [week, setWeek] = useState(getCurrentWeek())
  const [dayOfWeek, setDayOfWeek] = useState(getTodayWeekday())
  const [startSlot, setStartSlot] = useState('5')
  const [building, setBuilding] = useState('')
  const [roomType, setRoomType] = useState('')
  const [minCapacity, setMinCapacity] = useState('')

  const [buildings, setBuildings] = useState<{ name: string; type: string }[]>([])
  const [hasData, setHasData] = useState(true)

  useEffect(() => {
    loadBuildings()
    loadStats()
    searchRooms()
  }, [])

  async function loadBuildings() {
    try {
      const resp = await fetch('/api/rooms/buildings')
      const data = await resp.json()
      if (data.success) setBuildings(data.buildings)
    } catch {}
  }

  async function loadStats() {
    try {
      const resp = await fetch('/api/rooms/stats')
      const data = await resp.json()
      if (data.success) setStats(data.stats)
    } catch {}
  }

  async function searchRooms() {
    setLoading(true)
    try {
      const params = new URLSearchParams()
      params.set('week', String(week))
      params.set('day_of_week', String(dayOfWeek))
      if (startSlot) {
        params.set('start_slot', startSlot)
        params.set('end_slot', String(parseInt(startSlot) + 1))
      }
      if (building) params.set('building', building)
      if (roomType) params.set('room_type', roomType)
      if (minCapacity) params.set('min_capacity', minCapacity)

      const resp = await fetch(`/api/rooms/empty?${params}`)
      const data = await resp.json()
      if (data.success) {
        setRooms(data.rooms)
        setHasData(data.rooms.length > 0)
      }
    } catch (err) {
      console.error('查询失败', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleRefresh() {
    setRefreshing(true)
    try {
      const resp = await fetch('/api/rooms/refresh', { method: 'POST' })
      const data = await resp.json()
      if (data.success) {
        await loadStats()
        await searchRooms()
      } else {
        alert(data.message || '刷新失败')
      }
    } catch (err) {
      console.error('刷新失败', err)
    } finally {
      setRefreshing(false)
    }
  }

  const buildingNames = [...new Set(buildings.filter(b => b.type === '教室').map(b => b.name))].filter(Boolean).filter(n => n !== '教室')

  return (
    <div className="space-y-6">
      {/* 标题区 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">空教室查询</h1>
          <p className="text-muted-foreground text-sm mt-1">
            查询重邮各教学楼的空闲自习教室
            {stats && (
              <span className="ml-2 text-xs">
                · 共 {stats.total_rooms} 个场地
              </span>
            )}
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleRefresh}
          disabled={refreshing}
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? '刷新中...' : '刷新数据'}
        </Button>
      </div>

      {/* 筛选条件 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Search className="w-4 h-4" />
            查询条件
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div>
              <label className="block text-xs text-muted-foreground mb-1">周次</label>
              <input
                type="number"
                min={1}
                max={21}
                value={week}
                onChange={e => setWeek(Number(e.target.value))}
                className="form-input"
              />
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">星期</label>
              <select
                value={dayOfWeek}
                onChange={e => setDayOfWeek(Number(e.target.value))}
                className="form-input"
              >
                {WEEKDAYS.map((day, i) => (
                  <option key={i} value={i + 1}>{day}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">时段</label>
              <select
                value={startSlot}
                onChange={e => setStartSlot(e.target.value)}
                className="form-input"
              >
                <option value="">全天</option>
                {SLOT_OPTIONS.map(opt => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">教学楼</label>
              <select
                value={building}
                onChange={e => setBuilding(e.target.value)}
                className="form-input"
              >
                <option value="">全部</option>
                {buildingNames.map(name => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">类型</label>
              <select
                value={roomType}
                onChange={e => setRoomType(e.target.value)}
                className="form-input"
              >
                <option value="">全部</option>
                <option value="教室">教室</option>
                <option value="实验室">实验室</option>
                <option value="室外">室外</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-muted-foreground mb-1">最少座位</label>
              <input
                type="number"
                min={0}
                step={10}
                value={minCapacity}
                onChange={e => setMinCapacity(e.target.value)}
                placeholder="不限"
                className="form-input"
              />
            </div>
          </div>
          <div className="mt-4">
            <Button onClick={searchRooms} disabled={loading}>
              <Search className="w-4 h-4 mr-2" />
              {loading ? '查询中...' : '查询空教室'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 结果列表 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center justify-between">
            <span className="flex items-center gap-2">
              <MapPin className="w-4 h-4" />
              查询结果
            </span>
            {rooms.length > 0 && (
              <span className="text-sm font-normal text-muted-foreground">
                找到 {rooms.length} 间空教室
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="text-center py-12 text-muted-foreground">
              查询中...
            </div>
          ) : !hasData ? (
            <div className="text-center py-12 text-muted-foreground">
              <Building2 className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p>该时间段没有空教室</p>
              <p className="text-xs mt-1">试试调整查询条件</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-2 font-medium text-muted-foreground">教室</th>
                    <th className="text-left py-2 px-2 font-medium text-muted-foreground">教学楼</th>
                    <th className="text-left py-2 px-2 font-medium text-muted-foreground">类型</th>
                    <th className="text-right py-2 px-2 font-medium text-muted-foreground">座位</th>
                  </tr>
                </thead>
                <tbody>
                  {rooms.map((room) => (
                    <tr
                      key={room.room_name}
                      className="border-b border-border/50 hover:bg-muted/30 transition-colors"
                    >
                      <td className="py-3 px-2">
                        <span className="font-medium">{room.room_name}</span>
                      </td>
                      <td className="py-3 px-2 text-muted-foreground">
                        {room.building || '-'}
                      </td>
                      <td className="py-3 px-2">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          room.room_type === '教室'
                            ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                            : room.room_type === '实验室'
                            ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'
                            : room.room_type === '室外'
                            ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400'
                            : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                        }`}>
                          {room.room_type === '室外' ? '🌳 室外' : room.room_type}
                        </span>
                      </td>
                      <td className="py-3 px-2 text-right">
                        <span className="flex items-center justify-end gap-1 text-muted-foreground">
                          <Users className="w-3.5 h-3.5" />
                          {room.capacity || '-'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
