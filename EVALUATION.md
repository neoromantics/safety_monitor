# System Evaluation Report

This document outlines the performance, scenario testing, and known limitations of the Local AI Safety Monitoring System.

## 1. Scenario Evaluation

### Positive Scenario (Expected to Trigger)
- **Setup:** A person walks into the right 40% of the camera frame (the designated restricted zone) and stands there for at least 5 frames.
- **Result:** The system correctly identified the person and their bounding box intersected the restricted zone polygon. After the temporal smoothing requirement was met (3 out of 5 frames), a `restricted_zone_entry` event was automatically triggered and pushed to the dashboard via SSE.
- **Success Criteria:** Event is generated with >45% confidence, no manual trigger was required.

### Negative Scenario (Expected NOT to Trigger)
- **Setup:** A person walks into the left 60% of the camera frame (the safe zone) and moves around without crossing the boundary.
- **Result:** The model successfully detects the person, but because the center-bottom of their bounding box does not intersect the right 40% polygon, the rule engine's temporal counter remains at 0. No event is triggered.
- **Success Criteria:** System remains silent, no false `restricted_zone_entry` events are recorded.

## 2. Performance Metrics
- **Hardware:** Apple Silicon CPU (Mac)
- **Model:** YOLOv8n (Nano) CPU execution
- **Input Resolution:** Scaled down to 320x320 for inference
- **Observed FPS:** ~15-25 FPS (depending on lighting and scene complexity)
- **Observed Latency:** ~40-60 ms per frame

## 3. Risks & Limitations

### False-Positive Risks
- **Reflections/Posters:** A highly realistic poster of a human or a reflection in a mirror located inside the restricted zone could trick the YOLO model into detecting a person, triggering a false safety event.
- **Occlusion near boundaries:** If a person stands in the safe zone but extends an arm into the restricted zone, the bounding box might expand into the restricted area, causing the center-bottom point calculation to falsely flag them as being inside the zone.

### False-Negative Risks
- **Poor Lighting:** In very dark conditions or severe backlighting, the YOLO model may fail to detect the person entirely, meaning they could enter the restricted zone without triggering an alert.
- **Severe Occlusion:** If only a person's head is visible (e.g., hiding behind a desk), the model's confidence might drop below the 0.45 threshold.

## 4. Future Improvements (Reducing False Alerts)
If given more time, false alerts could be reduced by:
1. **Person Tracking:** Implementing a tracker (like ByteTrack or DeepSORT) to assign IDs to individuals. This would prevent a single person flickering in and out of detection from generating multiple cooldown cycles.
2. **Keypoint/Pose Detection:** Instead of using the bounding box center-bottom (which can be skewed by outstretched arms), using a Pose model to specifically track the `ankle` or `foot` keypoints would provide vastly more accurate zone intersection checks.
3. **Background Subtraction / Static Object Filtering:** Keeping a memory of static detections (like a poster on the wall) and ignoring them if they haven't moved for 5 minutes.
