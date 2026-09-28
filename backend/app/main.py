from fastapi import FastAPI, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
import asyncio
import json
import base64
import numpy as np
import cv2
import time

from . import database, schemas, inference

app = FastAPI(title="Local AI Safety API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

database.init_db()

# Global variables
clients = [] # SSE clients

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def on_event_triggered(event_data: dict):
    db = database.SessionLocal()
    db_event = database.Event(**event_data)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    db.close()
    
    # Notify SSE clients
    event_schema = schemas.EventResponse.from_orm(db_event)
    data = event_schema.json()
    for client in clients:
        client.put_nowait(data)

worker = inference.InferenceWorker(db_session_maker=database.SessionLocal, event_callback=on_event_triggered)

@app.on_event("startup")
async def startup_event():
    # Pre-load the model so it's ready for websockets
    worker.load_model()

@app.get("/api/events", response_model=list[schemas.EventResponse])
def get_events(db: Session = Depends(get_db)):
    events = db.query(database.Event).order_by(database.Event.timestamp.desc()).all()
    return events

@app.patch("/api/events/{event_id}", response_model=schemas.EventResponse)
def update_event(event_id: int, event_update: schemas.EventUpdate, db: Session = Depends(get_db)):
    event = db.query(database.Event).filter(database.Event.id == event_id).first()
    if event:
        event.status = event_update.status
        db.commit()
        db.refresh(event)
    return event

@app.get("/api/events/stream")
async def event_stream(request: Request):
    queue = asyncio.Queue()
    clients.append(queue)
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                data = await queue.get()
                yield {"event": "new_event", "data": data}
        finally:
            clients.remove(queue)
    return EventSourceResponse(event_generator())

@app.websocket("/api/ws/video")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Setup FPS counter for this connection
    frame_count = 0
    start_time = time.time()
    current_fps = 0
    
    try:
        while True:
            data = await websocket.receive_text()
            
            # Decode base64 image
            if data.startswith('data:image/jpeg;base64,'):
                data = data.split(',')[1]
                
            img_bytes = base64.b64decode(data)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            if frame is None:
                continue
                
            # Process frame using worker logic
            t0 = time.time()
            # Predict only class 0 (person), using smaller imgsz for faster CPU inference
            results = worker.model.predict(frame, classes=[0], verbose=False, imgsz=320)
            t1 = time.time()
            latency = (t1 - t0) * 1000
            
            h, w = frame.shape[:2]
            detections = []
            
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = box.conf[0].item()
                    detections.append({
                        'box': [x1/w, y1/h, x2/w, y2/h],
                        'conf': conf
                    })
            
            # Check rule
            rule_result = worker.rule.process(detections)
            if rule_result['trigger']:
                on_event_triggered({
                    "type": rule_result['type'],
                    "confidence": rule_result['confidence'],
                    "source": "Browser Webcam",
                    "model_info": "YOLOv8n"
                })
                
            # Calculate FPS
            frame_count += 1
            elapsed = time.time() - start_time
            if elapsed > 1.0:
                current_fps = frame_count / elapsed
                frame_count = 0
                start_time = time.time()
                
            await websocket.send_json({
                "fps": current_fps,
                "latency": latency,
                "detections": detections
            })
            
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
