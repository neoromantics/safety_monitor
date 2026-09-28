from ultralytics import YOLO
import os
import shutil

def main():
    model_dir = os.path.join(os.path.dirname(__file__), "..", "data")
    os.makedirs(model_dir, exist_ok=True)
    
    # Download and load the YOLOv8n model
    print("Downloading YOLOv8n model...")
    model_path = os.path.join(model_dir, "yolov8n.pt")
    model = YOLO("yolov8n.pt") 
    
    if os.path.exists("yolov8n.pt"):
        shutil.move("yolov8n.pt", model_path)
    
    print(f"Model downloaded and saved to {model_path}.")

if __name__ == "__main__":
    main()
