from fastapi import FastAPI, Depends, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
import asyncio
import json

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
    import os
    source = os.getenv("VIDEO_SOURCE", 0)
    if str(source).isdigit():
        source = int(source)
    # Attempt to start worker with configured source
    worker.start(source=source)

@app.on_event("shutdown")
async def shutdown_event():
    worker.stop()

@app.get("/api/status")
def get_status():
    return {
        "status": worker.status,
        "fps": worker.fps,
        "latency": worker.latency,
        "source": str(worker.source)
    }

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

def video_generator():
    while True:
        if worker.current_frame:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + worker.current_frame + b'\r\n')
        else:
            time.sleep(0.1)
import time

@app.get("/api/video.mjpg")
def video_feed():
    return StreamingResponse(video_generator(), media_type="multipart/x-mixed-replace; boundary=frame")
