# Local AI Safety Monitoring System

A full-stack, model-driven camera monitoring system that runs entirely locally on CPU. It analyzes a webcam feed to detect people and automatically triggers safety events when a person enters a designated restricted zone.

## System Requirements
- **OS:** macOS, Linux, or Windows
- **Python:** 3.10+
- **Node.js:** 20+
- **Hardware:** Standard multi-core CPU (no specialized GPU required)
- **Webcam:** Required for live inference

## Architecture

The system is split into two lightweight services communicating via REST and Server-Sent Events (SSE):

- **Backend (FastAPI & OpenCV):** Reads the webcam feed, runs YOLO inference locally, evaluates the safety rule, logs to SQLite, and streams annotated video and real-time events.
- **Frontend (Vue 3 & Vite):** A reactive dashboard that displays the live video, system metrics, and dynamically updates the event table without page refreshes.

## Model Documentation
- **Model Selected:** Ultralytics YOLOv8n (Nano)
- **Source:** [Ultralytics GitHub](https://github.com/ultralytics/ultralytics)
- **License:** AGPL-3.0
- **Input Format:** RGB images. The system grabs frames via OpenCV, resizes them to 640px wide to reduce overhead, and passes them to the model with `imgsz=320` to maximize CPU performance.
- **Why it fits:** YOLOv8n is extremely lightweight, providing accurate real-time person detection (COCO class 0) on standard laptop CPUs without requiring paid cloud APIs.

## Safety Rule Engine
The system enforces a **Restricted Zone** rule:
- **Zone Definition:** The right 40% of the camera frame.
- **Trigger Logic:** The system calculates the bottom-center coordinate of the detected person's bounding box.
- **Confidence Threshold:** Detections must be `>= 0.45` confidence to be considered.
- **Temporal Smoothing:** To prevent flickering, a person must be detected inside the zone for at least **3 out of the last 5 frames**.
- **Event Cooldown:** Once an event triggers, a **5-second cooldown** prevents duplicate alerts.
- **Zone Cleared:** When the person fully leaves the zone, a `zone_cleared` event is logged to indicate the situation is safe.

## Setup Instructions

This project uses `uv` for ultra-fast Python package management.

### 1. Start the Backend
Open a terminal and navigate to the `backend` folder:
```bash
cd backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```
*Note: The first time this runs, it will automatically download `yolov8n.pt` and may prompt you for Camera permissions.*

### 2. Start the Frontend Dashboard
Open a second terminal and navigate to the `frontend` folder:
```bash
cd frontend
npm install
npm run dev
```
Open your browser to `http://localhost:5173`.

## Test Steps
1. Start both the frontend and backend servers.
2. Open the dashboard in your browser. Verify the "Source: 0" and "Status: running" badges appear.
3. Observe the live annotated video feed. Note the red vertical line designating the restricted zone on the right side.
4. **Positive Test:** Step into the right side of your camera view. A `restricted_zone_entry` event will automatically populate in the events table below.
5. **Negative Test:** Step out of the zone into the left side. A `zone_cleared` event will populate. Remaining on the left side will not trigger any further alerts.
6. Click the **Ack** and **Resolve** buttons on the dashboard to change the status of the events.
7. Refresh the page to verify that the SQLite database has persisted your events and their states.

## Evaluation
Please see [EVALUATION.md](./EVALUATION.md) for detailed performance metrics, latency observations, scenario evaluations, and known false-positive risks.
