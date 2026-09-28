import cv2
import time
import os
import threading
from ultralytics import YOLO
from .rules import RestrictedZoneRule

class InferenceWorker:
    def __init__(self, db_session_maker, event_callback):
        self.model = None
        self.running = False
        self.source = 0 # default webcam
        self.thread = None
        self.db_session_maker = db_session_maker
        self.event_callback = event_callback
        
        self.current_frame = None
        self.fps = 0
        self.latency = 0
        self.status = "stopped" # model_unavailable, source_unavailable, running, stopped
        
        # default polygon: right 2/5 of the screen
        self.rule = RestrictedZoneRule(polygon=[(0.6, 0.0), (1.0, 0.0), (1.0, 1.0), (0.6, 1.0)])
        
    def load_model(self):
        model_path = os.path.join(os.path.dirname(__file__), "..", "data", "yolov8n.pt")
        if not os.path.exists(model_path):
            self.status = "model_unavailable"
            return False
        try:
            self.model = YOLO(model_path)
            return True
        except Exception as e:
            print("Error loading model:", e)
            self.status = "model_unavailable"
            return False

    def start(self, source=0):
        self.source = source
        if not self.model:
            if not self.load_model():
                return False
        
        self.running = True
        self.status = "running"
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
        self.status = "stopped"

    def _run_loop(self):
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            self.status = "source_unavailable"
            self.running = False
            return

        frame_count = 0
        start_time = time.time()
        
        while self.running:
            ret, frame = cap.read()
            if not ret:
                # If video ends, loop or stop. Let's just stop for now, or rewind if it's a file
                if isinstance(self.source, str):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    self.status = "camera_unavailable"
                    break

            if isinstance(self.source, int):
                frame = cv2.flip(frame, 1)

            # Resize frame to reduce MJPEG encoding time and drawing overhead
            h, w = frame.shape[:2]
            target_w = 640
            if w > target_w:
                target_h = int(h * (target_w / w))
                frame = cv2.resize(frame, (target_w, target_h))

            t0 = time.time()
            # Predict only class 0 (person), using smaller imgsz for faster CPU inference
            results = self.model.predict(frame, classes=[0], verbose=False, imgsz=320)
            t1 = time.time()
            self.latency = (t1 - t0) * 1000 # ms
            
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
                    # Draw box
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    cv2.putText(frame, f"Person {conf:.2f}", (int(x1), int(y1)-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2)

            # Draw polygon
            poly_pts = [(int(pt[0]*w), int(pt[1]*h)) for pt in self.rule.polygon]
            poly_pts_np = [poly_pts] # needs to be list of arrays for polylines if using numpy, but we can draw lines
            for i in range(len(poly_pts)):
                p1 = poly_pts[i]
                p2 = poly_pts[(i+1)%len(poly_pts)]
                cv2.line(frame, p1, p2, (0, 0, 255), 2)

            # Process rule
            rule_result = self.rule.process(detections)
            if rule_result['trigger']:
                self.event_callback({
                    "type": rule_result['type'],
                    "confidence": rule_result['confidence'],
                    "source": str(self.source),
                    "model_info": "YOLOv8n"
                })

            # Calculate FPS and average latency
            frame_count += 1
            elapsed = time.time() - start_time
            if elapsed > 1.0:
                self.fps = frame_count / elapsed
                self.display_latency = self.latency # Just snapshot the latest latency or we could average it
                frame_count = 0
                start_time = time.time()

            # Add overlays
            cv2.putText(frame, f"FPS: {self.fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,0), 2)
            
            # Use display_latency if it exists, otherwise latency
            disp_lat = getattr(self, 'display_latency', self.latency)
            cv2.putText(frame, f"Latency: {disp_lat:.1f}ms", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,255,0), 2)
            
            # Encode frame for MJPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                self.current_frame = buffer.tobytes()

        cap.release()
