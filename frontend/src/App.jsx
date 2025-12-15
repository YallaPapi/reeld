import { useState, useEffect } from 'react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts'

const API_BASE = '/api'

// KPI Card component
function KpiCard({ label, value, trend, trendDirection }) {
  return (
    <div className="kpi-card">
      <div className="label">{label}</div>
      <div className="value">{typeof value === 'number' ? value.toLocaleString() : value}</div>
      {trend && (
        <div className={`trend ${trendDirection}`}>
          {trendDirection === 'up' ? '+' : ''}{trend}
        </div>
      )}
    </div>
  )
}

// Pipeline status indicator
function PipelineStatus({ status }) {
  return (
    <div className="status">
      <div className={`status-dot ${status.is_running ? 'running' : ''}`}
           style={{ background: status.is_running ? '#3b82f6' : '#22c55e' }} />
      <span>
        {status.is_running
          ? `Running: ${status.current_step || 'Unknown'} (${status.progress_pct?.toFixed(0) || 0}%)`
          : 'Idle'}
      </span>
    </div>
  )
}

// Runs table component
function RunsTable({ runs }) {
  if (!runs?.length) {
    return <div className="loading">No runs recorded yet</div>
  }

  return (
    <table className="runs-table">
      <thead>
        <tr>
          <th>Script</th>
          <th>Started</th>
          <th>Duration</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => (
          <tr key={run.id}>
            <td>{run.script_name}</td>
            <td>{new Date(run.start_time).toLocaleString()}</td>
            <td>
              {run.duration_seconds
                ? `${Math.round(run.duration_seconds)}s`
                : run.status === 'running' ? '...' : '-'}
            </td>
            <td>
              <span className={`status-badge ${run.status}`}>
                {run.status}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

// Main Dashboard App
export default function App() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [todayMetrics, setTodayMetrics] = useState({})
  const [weeklyMetrics, setWeeklyMetrics] = useState([])
  const [runs, setRuns] = useState([])
  const [pipelineStatus, setPipelineStatus] = useState({ is_running: false })
  const [apiUsage, setApiUsage] = useState({})

  // Fetch all data
  const fetchData = async () => {
    try {
      setLoading(true)
      setError(null)

      const [todayRes, weekRes, runsRes, statusRes, apiRes] = await Promise.all([
        fetch(`${API_BASE}/metrics/today`),
        fetch(`${API_BASE}/metrics/7`),
        fetch(`${API_BASE}/runs?limit=10`),
        fetch(`${API_BASE}/pipeline-status`),
        fetch(`${API_BASE}/api-usage`),
      ])

      if (!todayRes.ok || !weekRes.ok || !runsRes.ok) {
        throw new Error('Failed to fetch data from API')
      }

      setTodayMetrics(await todayRes.json())
      setWeeklyMetrics((await weekRes.json()).reverse()) // Oldest first for chart
      setRuns(await runsRes.json())
      setPipelineStatus(await statusRes.json())
      setApiUsage(await apiRes.json())

    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  // Initial fetch and auto-refresh
  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  // Prepare chart data
  const chartData = weeklyMetrics.map(day => ({
    date: day.date.slice(5), // MM-DD
    videos: day.metrics.videos_processed || day.metrics.videos_spoofed || 0,
    captions: day.metrics.captions_generated || 0,
    apiCalls: day.metrics.claude_api_calls || 0,
    errors: day.metrics.errors || 0,
  }))

  // Pie chart data for API usage
  const pieData = [
    { name: 'Successful', value: apiUsage.successful_calls || 0, color: '#22c55e' },
    { name: 'Failed', value: apiUsage.failed_calls || 0, color: '#ef4444' },
  ].filter(d => d.value > 0)

  if (loading && !todayMetrics.videos_processed) {
    return (
      <div className="dashboard">
        <div className="loading">Loading dashboard...</div>
      </div>
    )
  }

  return (
    <div className="dashboard">
      {/* Header */}
      <div className="header">
        <h1>Reeld Analytics Dashboard</h1>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <PipelineStatus status={pipelineStatus} />
          <button className="refresh-btn" onClick={fetchData} disabled={loading}>
            {loading ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Error message */}
      {error && (
        <div className="error">
          Error: {error}. Make sure the API server is running on port 8080.
        </div>
      )}

      {/* KPI Cards */}
      <div className="kpi-grid">
        <KpiCard
          label="Videos Processed Today"
          value={todayMetrics.videos_processed || todayMetrics.videos_spoofed || 0}
        />
        <KpiCard
          label="Captions Generated"
          value={todayMetrics.captions_generated || 0}
        />
        <KpiCard
          label="Claude API Calls"
          value={todayMetrics.claude_api_calls || 0}
        />
        <KpiCard
          label="Errors"
          value={todayMetrics.errors || 0}
        />
        <KpiCard
          label="Est. API Cost (Week)"
          value={`$${(apiUsage.estimated_cost_usd || 0).toFixed(2)}`}
        />
      </div>

      {/* Charts */}
      <div className="charts-section">
        {/* Line Chart - 7 Day Trends */}
        <div className="chart-card">
          <h3>7-Day Processing Trends</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="date" stroke="#94a3b8" />
              <YAxis stroke="#94a3b8" />
              <Tooltip
                contentStyle={{ background: '#1e293b', border: 'none', borderRadius: '8px' }}
                labelStyle={{ color: '#f8fafc' }}
              />
              <Line type="monotone" dataKey="videos" stroke="#3b82f6" strokeWidth={2} name="Videos" />
              <Line type="monotone" dataKey="captions" stroke="#22c55e" strokeWidth={2} name="Captions" />
              <Line type="monotone" dataKey="apiCalls" stroke="#a855f7" strokeWidth={2} name="API Calls" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Pie Chart - API Success Rate */}
        <div className="chart-card">
          <h3>API Success Rate</h3>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={2}
                  dataKey="value"
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={index} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: 'none', borderRadius: '8px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="loading">No API calls recorded yet</div>
          )}
        </div>
      </div>

      {/* Bar Chart - Daily Breakdown */}
      <div className="chart-card" style={{ marginBottom: '32px' }}>
        <h3>Daily Error Rate</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis dataKey="date" stroke="#94a3b8" />
            <YAxis stroke="#94a3b8" />
            <Tooltip
              contentStyle={{ background: '#1e293b', border: 'none', borderRadius: '8px' }}
              labelStyle={{ color: '#f8fafc' }}
            />
            <Bar dataKey="errors" fill="#ef4444" name="Errors" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Recent Runs */}
      <div className="runs-section">
        <h3>Recent Pipeline Runs</h3>
        <RunsTable runs={runs} />
      </div>
    </div>
  )
}
