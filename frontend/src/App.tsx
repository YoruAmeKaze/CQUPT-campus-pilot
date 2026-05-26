import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Courses from './pages/Courses'
import Assignments from './pages/Assignments'
import Todos from './pages/Todos'
import Notifications from './pages/Notifications'
import Schedules from './pages/Schedules'
import Tools from './pages/Tools'
import Settings from './pages/Settings'
import Rooms from './pages/Rooms'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/courses" element={<Courses />} />
          <Route path="/assignments" element={<Assignments />} />
          <Route path="/todos" element={<Todos />} />
          <Route path="/rooms" element={<Rooms />} />
          <Route path="/notifications" element={<Notifications />} />
          <Route path="/schedules" element={<Schedules />} />
          <Route path="/tools" element={<Tools />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App
