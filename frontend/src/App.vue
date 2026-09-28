<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const status = ref({ status: 'running', source: 'Browser Webcam' })
const events = ref([])
const backendUrl = import.meta.env.PROD ? "" : "http://localhost:8000"
const wsUrl = import.meta.env.PROD 
  ? `wss://${window.location.host}/api/ws/video`
  : "ws://localhost:8000/api/ws/video"

const videoRef = ref(null)
const canvasRef = ref(null)
let ws = null
let captureInterval = null

const fetchEvents = async () => {
  try {
    const res = await fetch(`${backendUrl}/api/events`)
    events.value = await res.json()
  } catch (e) {
    console.error(e)
  }
}

const updateEventStatus = async (id, newStatus) => {
  try {
    await fetch(`${backendUrl}/api/events/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus })
    })
    fetchEvents()
  } catch (e) {
    console.error(e)
  }
}

const startCamera = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true })
    if (videoRef.value) {
      videoRef.value.srcObject = stream
    }
    
    // Setup WebSocket
    ws = new WebSocket(wsUrl)
    ws.onopen = () => {
      console.log("WebSocket connected")
      status.value.status = 'running'
    }
    
    let lastMetricsUpdate = 0
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      
      // Update metrics text only twice a second so it's readable
      const now = Date.now()
      if (now - lastMetricsUpdate > 500) {
        status.value.fps = data.fps
        status.value.latency = data.latency
        lastMetricsUpdate = now
      }
      
      drawDetections(data.detections)
    }
    ws.onerror = () => {
      status.value.status = 'error'
    }

    // Send frames to backend
    const hiddenCanvas = document.createElement('canvas')
    const ctx = hiddenCanvas.getContext('2d', { willReadFrequently: true })
    
    captureInterval = setInterval(() => {
      if (!videoRef.value || !ws || ws.readyState !== WebSocket.OPEN) return
      
      const width = videoRef.value.videoWidth
      const height = videoRef.value.videoHeight
      if (!width || !height) return

      hiddenCanvas.width = width
      hiddenCanvas.height = height
      
      // Mirror the frame so the backend sees exactly what the user sees
      ctx.save()
      ctx.translate(width, 0)
      ctx.scale(-1, 1)
      ctx.drawImage(videoRef.value, 0, 0, width, height)
      ctx.restore()
      
      // Send as jpeg
      const base64 = hiddenCanvas.toDataURL('image/jpeg', 0.6)
      ws.send(base64)
    }, 50) // 20 FPS
    
  } catch (err) {
    console.error("Camera access denied:", err)
    status.value.status = 'camera_denied'
  }
}

const drawDetections = (detections) => {
  if (!canvasRef.value || !videoRef.value) return
  const canvas = canvasRef.value
  const ctx = canvas.getContext('2d')
  
  canvas.width = videoRef.value.videoWidth
  canvas.height = videoRef.value.videoHeight
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  
  // Draw Restricted Zone (Right 40%)
  ctx.fillStyle = 'rgba(255, 0, 0, 0.2)'
  ctx.fillRect(canvas.width * 0.6, 0, canvas.width * 0.4, canvas.height)
  ctx.strokeStyle = 'red'
  ctx.lineWidth = 2
  ctx.beginPath()
  ctx.moveTo(canvas.width * 0.6, 0)
  ctx.lineTo(canvas.width * 0.6, canvas.height)
  ctx.stroke()

  // Draw Detections
  for (const d of detections) {
    const [x1, y1, x2, y2] = d.box
    const px1 = x1 * canvas.width
    const py1 = y1 * canvas.height
    const px2 = x2 * canvas.width
    const py2 = y2 * canvas.height
    
    ctx.strokeStyle = 'lime'
    ctx.lineWidth = 3
    ctx.strokeRect(px1, py1, px2 - px1, py2 - py1)
    
    ctx.fillStyle = 'lime'
    ctx.font = '16px Arial'
    ctx.fillText(`Person ${(d.conf * 100).toFixed(0)}%`, px1, py1 - 5)
  }
}

onMounted(() => {
  fetchEvents()
  startCamera()

  const eventSource = new EventSource(`${backendUrl}/api/events/stream`)
  eventSource.addEventListener("new_event", (e) => {
    const newEvent = JSON.parse(e.data)
    events.value.unshift(newEvent)
  })
})

onUnmounted(() => {
  if (captureInterval) clearInterval(captureInterval)
  if (ws) ws.close()
})
</script>

<template>
  <div class="dashboard">
    <header>
      <h1>AI Safety Monitor</h1>
      <div class="status-bar">
      </div>
    </header>

    <main>
      <div class="video-container">
        <h2>Live Feed</h2>
        <div class="feed-wrapper" v-if="status.status === 'running'">
          <video ref="videoRef" autoplay playsinline muted></video>
          <canvas ref="canvasRef"></canvas>
        </div>
        <div v-else class="video-placeholder">
          {{ status.status === 'camera_denied' ? 'Camera Permission Denied' : 'Connecting to Server...' }}
        </div>
        <div class="metrics" v-if="status.fps">
          FPS: {{ status.fps.toFixed(1) }} | Latency: {{ status.latency.toFixed(1) }}ms
        </div>
      </div>

      <div class="events-container">
        <h2>Recent Events</h2>
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Type</th>
              <th>Confidence</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="event in events" :key="event.id" :class="{'resolved': event.status === 'resolved'}">
              <td>{{ new Date(event.timestamp).toLocaleTimeString() }}</td>
              <td>{{ event.type }}</td>
              <td>{{ (event.confidence * 100).toFixed(1) }}%</td>
              <td>
                <span :class="['status-badge', event.status]">{{ event.status }}</span>
              </td>
              <td>
                <button v-if="event.status === 'open'" @click="updateEventStatus(event.id, 'acknowledged')">Ack</button>
                <button v-if="event.status !== 'resolved'" @click="updateEventStatus(event.id, 'resolved')">Resolve</button>
              </td>
            </tr>
            <tr v-if="events.length === 0">
              <td colspan="5" class="no-events">No events detected.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </main>
  </div>
</template>

<style scoped>
.dashboard {
  font-family: Arial, sans-serif;
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}
header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 2px solid #eee;
  padding-bottom: 10px;
  margin-bottom: 20px;
}
.status-bar {
  display: flex;
  gap: 10px;
}
.badge {
  padding: 5px 10px;
  background: #333;
  color: white;
  border-radius: 4px;
  font-size: 0.9em;
}
main {
  display: flex;
  flex-direction: column;
  gap: 30px;
}
.video-container {
  display: flex;
  flex-direction: column;
}
.feed-wrapper {
  position: relative;
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
  background: #000;
  display: flex;
  justify-content: center;
}
video {
  width: 100%;
  max-height: 60vh;
  transform: scaleX(-1); /* Mirror camera naturally */
}
canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.video-placeholder {
  width: 100%;
  aspect-ratio: 16/9;
  background: #222;
  color: #888;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
}
.metrics {
  margin-top: 10px;
  font-weight: bold;
  color: #555;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}
.resolved { opacity: 0.6; }
.status-badge {
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 0.8em;
  text-transform: uppercase;
}
.status-badge.open { background: #ffebee; color: #c62828; }
.status-badge.acknowledged { background: #fff3e0; color: #ef6c00; }
.status-badge.resolved { background: #e8f5e9; color: #2e7d32; }
button {
  margin-right: 5px;
  padding: 4px 8px;
  cursor: pointer;
  background: #2196F3;
  color: white;
  border: none;
  border-radius: 4px;
}
button:hover { background: #1976D2; }
</style>
