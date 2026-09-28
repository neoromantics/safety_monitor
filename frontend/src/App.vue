<script setup>
import { ref, onMounted } from 'vue'

const status = ref({})
const events = ref([])
const backendUrl = "http://localhost:8000"

const fetchStatus = async () => {
  try {
    const res = await fetch(`${backendUrl}/api/status`)
    status.value = await res.json()
  } catch (e) {
    console.error(e)
  }
}

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

onMounted(() => {
  fetchStatus()
  fetchEvents()
  setInterval(fetchStatus, 2000)

  const eventSource = new EventSource(`${backendUrl}/api/events/stream`)
  eventSource.addEventListener("new_event", (e) => {
    const newEvent = JSON.parse(e.data)
    events.value.unshift(newEvent) // Add to top
  })
})
</script>

<template>
  <div class="dashboard">
    <header>
      <h1>AI Safety Monitor</h1>
      <div class="status-bar">
        <span class="badge">Source: {{ status.source }}</span>
      </div>
    </header>

    <main>
      <div class="video-container">
        <h2>Live Feed</h2>
        <img :src="`${backendUrl}/api/video.mjpg`" alt="Live Feed" v-if="status.status === 'running'" />
        <div v-else class="video-placeholder">Video stream unavailable</div>
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
.badge.green { background: #4CAF50; }
.badge.red { background: #f44336; }

main {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.video-container img {
  width: 100%;
  border-radius: 8px;
  background: #000;
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

table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}
.resolved {
  opacity: 0.6;
}
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
button:hover {
  background: #1976D2;
}
</style>
