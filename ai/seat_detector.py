import cv2
import json
import time
import os
import csv
import argparse
import numpy as np
import paho.mqtt.client as mqtt
from ultralytics import YOLO

# COCO Class IDs for luggage/items
LUGGAGE_CLASSES = {
    24: 'backpack',
    25: 'umbrella',
    26: 'handbag',
    27: 'tie',
    28: 'suitcase',
    63: 'laptop',
    66: 'keyboard',
    67: 'cell phone',
    73: 'book'
}
PERSON_CLASS = 0

def main():
    parser = argparse.ArgumentParser(description="AI Library Seat Status Detector")
    parser.add_argument("--source", type=str, default="0", help="Webcam index or path to video file")
    parser.add_argument("--roi", type=str, default="seats_roi.json", help="Path to ROI json file")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="YOLOv8 model weights path")
    parser.add_argument("--mqtt-host", type=str, default="broker.hivemq.com", help="MQTT Broker host")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT Broker port")
    parser.add_argument("--mqtt-topic", type=str, default="internal/seats/event", help="MQTT publish topic")
    parser.add_argument("--metrics", type=str, default="metrics.csv", help="Path to save metrics log")
    parser.add_argument("--fps-limit", type=int, default=10, help="Process limit (FPS)")
    parser.add_argument("--debounce-frames", type=int, default=15, help="Number of consecutive frames to confirm state change")
    args = parser.parse_args()

    # Initialize MQTT client safely across different library versions
    print(f"Connecting to MQTT Broker {args.mqtt_host}:{args.mqtt_port}...")
    try:
        # Paho-MQTT v2
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except AttributeError:
        # Paho-MQTT v1
        mqtt_client = mqtt.Client()

    try:
        mqtt_client.connect(args.mqtt_host, args.mqtt_port, 60)
        mqtt_client.loop_start()
        print("MQTT client connected and loop started.")
    except Exception as e:
        print(f"Failed to connect to MQTT broker: {e}. Running in offline mode.")
        mqtt_client = None

    # Load YOLOv8 Model
    print(f"Loading YOLOv8 model: {args.model}...")
    model = YOLO(args.model)
    print("Model loaded successfully.")

    # Load ROIs
    rois = {}
    if os.path.exists(args.roi):
        try:
            with open(args.roi, 'r') as f:
                rois = json.load(f)
            print(f"Loaded {len(rois)} seat ROIs from {args.roi}")
        except Exception as e:
            print(f"Error reading ROI file {args.roi}: {e}")
    else:
        print(f"Warning: ROI file {args.roi} not found. Please run roi_selector.py first to configure seat boundaries.")

    # Prepare Metrics CSV
    metrics_file_exists = os.path.exists(args.metrics)
    try:
        metrics_file = open(args.metrics, mode='a', newline='')
        metrics_writer = csv.writer(metrics_file)
        if not metrics_file_exists:
            metrics_writer.writerow(['timestamp', 'fps', 'inference_time_ms', 'seat_id', 'detected_state', 'person_conf', 'luggage_conf'])
    except Exception as e:
        print(f"Error opening metrics file: {e}")
        metrics_writer = None

    # Source setup
    source_is_num = args.source.isdigit()
    is_image = False
    if not source_is_num:
        ext = os.path.splitext(args.source)[1].lower()
        is_image = ext in ['.jpg', '.jpeg', '.png', '.bmp']

    if is_image:
        static_frame = cv2.imread(args.source)
        if static_frame is None:
            print(f"Error: Could not open image source {args.source}")
            return
        cap = None
    else:
        cap_source = int(args.source) if source_is_num else args.source
        cap = cv2.VideoCapture(cap_source)
        if not cap.isOpened():
            print(f"Error: Could not open video source {args.source}")
            return

    # Trackers for debouncing state (USING / AWAY)
    seat_states = {seat_id: "UNKNOWN" for seat_id in rois.keys()}
    state_counters = {seat_id: {"candidate": "UNKNOWN", "count": 0} for seat_id in rois.keys()}

    prev_time = time.time()
    consecutive_failures = 0
    
    print("\nStarting detection loop. Press 'q' in the window to quit.\n")

    while True:
        loop_start = time.time()
        if is_image:
            frame = static_frame.copy()
        else:
            ret, frame = cap.read()
            if not ret:
                # If it's a video file, loop it
                if not source_is_num:
                    print("End of video stream. Restarting...")
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    consecutive_failures += 1
                    print(f"[Warning] Failed to grab frame from camera ({consecutive_failures}/10). Retrying...")
                    time.sleep(0.1)
                    if consecutive_failures >= 10:
                        print("Error: Lost camera connection consecutively for 10 frames. Exiting.")
                        break
                    continue
            consecutive_failures = 0

        # Inference
        t_inf_start = time.time()
        results = model(frame, verbose=False)
        t_inf_end = time.time()
        inference_time_ms = (t_inf_end - t_inf_start) * 1000

        # Parse detections
        detections = results[0].boxes
        # Store objects as: (class_id, confidence, box_bottom_center_pt, xyxy)
        detected_objects = []
        for box in detections:
            cls_id = int(box.cls[0].item())
            conf = float(box.conf[0].item())
            xyxy = box.xyxy[0].tolist() # [xmin, ymin, xmax, ymax]
            # bottom center point of bounding box
            bottom_center = (int((xyxy[0] + xyxy[2]) / 2), int(xyxy[3]))
            detected_objects.append((cls_id, conf, bottom_center, xyxy))

        # Evaluate each Seat ROI
        current_frame_states = {} # {seat_id: (state, person_conf, luggage_conf)}
        for seat_id, pts in rois.items():
            pts_np = np.array(pts, dtype=np.int32)
            
            # Find objects inside this ROI
            persons_in_roi = []
            luggage_in_roi = []
            
            for cls_id, conf, pt, xyxy in detected_objects:
                # Check if bottom center is in polygon
                dist = cv2.pointPolygonTest(pts_np, pt, False)
                if dist >= 0: # inside or on the line
                    if cls_id == PERSON_CLASS:
                        persons_in_roi.append(conf)
                    elif cls_id in LUGGAGE_CLASSES:
                        luggage_in_roi.append(conf)

            # Determine seat state candidates
            p_conf = max(persons_in_roi) if persons_in_roi else 0.0
            l_conf = max(luggage_in_roi) if luggage_in_roi else 0.0

            # State Logic:
            # USING: Person OR Luggage detected (Seat is occupied/active)
            # AWAY: Neither Person nor Luggage detected (Seat is completely empty)
            if p_conf > 0.0 or l_conf > 0.0:
                frame_state = "USING"
            else:
                frame_state = "AWAY"

            current_frame_states[seat_id] = (frame_state, p_conf, l_conf)

            # Debouncing logic
            if seat_id not in seat_states:
                seat_states[seat_id] = "UNKNOWN"
                state_counters[seat_id] = {"candidate": "UNKNOWN", "count": 0}

            curr_candidate = state_counters[seat_id]["candidate"]
            if frame_state == curr_candidate:
                state_counters[seat_id]["count"] += 1
            else:
                state_counters[seat_id]["candidate"] = frame_state
                state_counters[seat_id]["count"] = 1

            # If state is stable for N frames, change official state
            if state_counters[seat_id]["count"] >= args.debounce_frames:
                old_state = seat_states[seat_id]
                new_state = frame_state
                
                # Check if status has changed
                if old_state != new_state:
                    seat_states[seat_id] = new_state
                    print(f"[*] Seat {seat_id} state changed: {old_state} -> {new_state}")
                    
                    # Send MQTT Event
                    if old_state == "UNKNOWN" or old_state != new_state:
                        payload = {"seatId": str(seat_id), "eventType": new_state}
                        payload_str = json.dumps(payload)
                        if mqtt_client:
                            mqtt_client.publish(args.mqtt_topic, payload_str)
                            print(f"[MQTT] Published event to {args.mqtt_topic}: {payload_str}")
                        else:
                            print(f"[MQTT Offline] Event would be sent: {payload_str}")

        # Calculate FPS
        current_time = time.time()
        fps = 1.0 / (current_time - prev_time)
        prev_time = current_time

        # Draw ROIs and labels on display frame
        display_frame = frame.copy()
        for seat_id, pts in rois.items():
            pts_np = np.array(pts, dtype=np.int32)
            state = seat_states.get(seat_id, "UNKNOWN")
            
            # Map colors: Green for USING (occupied), Red for AWAY (empty)
            if state == "USING":
                color = (0, 255, 0)
            elif state == "AWAY":
                color = (0, 0, 255)
            else:
                color = (128, 128, 128)

            cv2.polylines(display_frame, [pts_np], isClosed=True, color=color, thickness=2)
            
            # Draw seat text
            M = cv2.moments(pts_np)
            cX = int(M["m10"] / M["m00"]) if M["m00"] != 0 else pts[0][0]
            cY = int(M["m01"] / M["m00"]) if M["m00"] != 0 else pts[0][1]
            cv2.putText(display_frame, f"Seat {seat_id}: {state}", (cX - 40, cY), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Draw overall stats
        cv2.putText(display_frame, f"FPS: {fps:.1f} | Inf Time: {inference_time_ms:.1f}ms", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.imshow("SmartSeat AI Detector", display_frame)

        # Logging Metrics to CSV
        if metrics_writer:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            for seat_id, (frame_state, p_conf, l_conf) in current_frame_states.items():
                metrics_writer.writerow([timestamp, f"{fps:.2f}", f"{inference_time_ms:.2f}", seat_id, frame_state, f"{p_conf:.2f}", f"{l_conf:.2f}"])
            metrics_file.flush()

        # Exit check
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        # Dynamic FPS Limiting
        elapsed = time.time() - loop_start
        sleep_time = max(0, (1.0 / args.fps_limit) - elapsed)
        if sleep_time > 0:
            time.sleep(sleep_time)

    # Clean up
    if metrics_writer:
        metrics_file.close()
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    if cap:
        cap.release()
    cv2.destroyAllWindows()
    print("AI detector terminated clean.")

if __name__ == "__main__":
    main()
