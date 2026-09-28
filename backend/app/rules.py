import time

class RestrictedZoneRule:
    def __init__(self, polygon, confidence_threshold=0.45, min_frames=3, window_frames=5, cooldown_secs=5):
        self.polygon = polygon # list of (x, y) tuples, normalized 0.0-1.0
        self.confidence_threshold = confidence_threshold
        self.min_frames = min_frames
        self.window_frames = window_frames
        self.cooldown_secs = cooldown_secs
        
        self.history = []
        self.last_event_time = 0
        self.current_state = "ok"

    def check_point_in_polygon(self, x, y):
        # Ray casting algorithm
        n = len(self.polygon)
        inside = False
        p1x, p1y = self.polygon[0]
        for i in range(n + 1):
            p2x, p2y = self.polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xints:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def process(self, detections):
        # Detections: list of dicts {'box': [x1, y1, x2, y2], 'conf': float} (normalized coords)
        inside_this_frame = False
        avg_conf = 0
        if detections:
            confs = []
            for d in detections:
                if d['conf'] >= self.confidence_threshold:
                    # check bottom center
                    x1, y1, x2, y2 = d['box']
                    cx = (x1 + x2) / 2
                    cy = y2
                    if self.check_point_in_polygon(cx, cy):
                        inside_this_frame = True
                        confs.append(d['conf'])
            if confs:
                avg_conf = sum(confs) / len(confs)

        self.history.append((inside_this_frame, avg_conf))
        if len(self.history) > self.window_frames:
            self.history.pop(0)

        # Check rule condition
        frames_inside = sum(1 for h in self.history if h[0])
        now = time.time()
        
        if frames_inside >= self.min_frames and (now - self.last_event_time) > self.cooldown_secs:
            self.last_event_time = now
            self.current_state = "violation"
            # avg confidence of frames inside
            event_conf = sum(h[1] for h in self.history if h[0]) / frames_inside
            return {"trigger": True, "type": "restricted_zone_entry", "confidence": event_conf}
            
        elif frames_inside == 0 and self.current_state == "violation":
            self.current_state = "ok"
            return {"trigger": True, "type": "zone_cleared", "confidence": 1.0}

        return {"trigger": False}
