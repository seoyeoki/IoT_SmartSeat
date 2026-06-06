import cv2
import json
import os
import argparse
import numpy as np
from ultralytics import YOLO

def main():
    parser = argparse.ArgumentParser(description="Auto Seat ROI Generator based on Chair Detection")
    parser.add_argument("--source", type=str, default="0", help="Webcam index or path to video/image")
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="YOLOv8 model weights path")
    parser.add_argument("--output", type=str, default="seats_roi.json", help="Output JSON path")
    parser.add_argument("--shape", type=str, choices=["rect", "rhombus"], default="rect", help="ROI shape: rect or rhombus")
    parser.add_argument("--scale-w", type=float, default=1.8, help="Horizontal scale factor relative to chair width")
    parser.add_argument("--scale-h", type=float, default=2.2, help="Vertical scale factor relative to chair height")
    args = parser.parse_args()

    # Load YOLO
    print(f"Loading YOLOv8 model: {args.model}...")
    model = YOLO(args.model)
    
    # Load Frame
    cap = None
    if args.source.isdigit():
        cap = cv2.VideoCapture(int(args.source))
        ret, frame = cap.read()
        cap.release()
    else:
        if os.path.exists(args.source):
            ext = os.path.splitext(args.source)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.bmp']:
                frame = cv2.imread(args.source)
            else:
                cap = cv2.VideoCapture(args.source)
                ret, frame = cap.read()
                cap.release()
        else:
            frame = None

    if frame is None:
        print("Error: Could not load source image or camera. Auto ROI generation requires a valid frame.")
        return

    h_img, w_img = frame.shape[:2]

    # Detect Chairs (Class ID 56)
    print("Detecting chairs to define seed points...")
    results = model(frame, verbose=False)
    detections = results[0].boxes

    chairs = []
    for box in detections:
        cls_id = int(box.cls[0].item())
        conf = float(box.conf[0].item())
        if cls_id == 56 and conf > 0.3: # Chair class
            xyxy = box.xyxy[0].tolist()
            w_box = xyxy[2] - xyxy[0]
            h_box = xyxy[3] - xyxy[1]
            cx = int((xyxy[0] + xyxy[2]) / 2)
            cy = int((xyxy[1] + xyxy[3]) / 2)
            chairs.append({
                'cx': cx,
                'cy': cy,
                'w': w_box,
                'h': h_box,
                'xyxy': xyxy
            })

    print(f"Detected {len(chairs)} chairs.")
    if len(chairs) == 0:
        print("No chairs detected. Try another source or check lighting.")
        return

    # Sort chairs from top-left to bottom-right to assign seat IDs sequentially
    chairs.sort(key=lambda item: (item['cy'], item['cx']))

    rois = {}
    
    # Generate ROI for each chair using spatial partitioning logic
    for i, ch in enumerate(chairs):
        seat_id = str(i + 1)
        cx, cy = ch['cx'], ch['cy']
        w, h = ch['w'], ch['h']

        # Find closest neighbor in x and y to dynamically scale ROI (spatial partitioning)
        min_dist_x = w * args.scale_w
        min_dist_y = h * args.scale_h

        for j, other in enumerate(chairs):
            if i == j:
                continue
            dx = abs(cx - other['cx'])
            dy = abs(cy - other['cy'])
            dist = np.sqrt(dx**2 + dy**2)
            
            # Neighborhood check: If neighbor is within 4x size
            if dist < max(w, h) * 4:
                # We limit our bounding box size to 45% of the distance to the neighbor (sharing space 50-50)
                if dx > 10:
                    min_dist_x = min(min_dist_x, dx * 0.9)
                if dy > 10:
                    min_dist_y = min(min_dist_y, dy * 0.9)

        # Desk heuristic: Shift ROI slightly upward (assuming camera captures from front/top)
        # where the desk surface is located relative to the chair backrest.
        shift_y = -int(h * 0.5)
        target_cy = max(0, cy + shift_y)

        half_w = int(min_dist_x / 2)
        half_h = int(min_dist_y / 2)

        if args.shape == "rect":
            # Rectangle vertices
            x1 = max(0, cx - half_w)
            y1 = max(0, target_cy - half_h)
            x2 = min(w_img - 1, cx + half_w)
            y2 = min(h_img - 1, target_cy + half_h)
            pts = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
        elif args.shape == "rhombus":
            # Rhombus vertices (Top, Right, Bottom, Left)
            p_top = [cx, max(0, target_cy - half_h)]
            p_right = [min(w_img - 1, cx + half_w), target_cy]
            p_bottom = [cx, min(h_img - 1, target_cy + half_h)]
            p_left = [max(0, cx - half_w), target_cy]
            pts = [p_top, p_right, p_bottom, p_left]

        rois[seat_id] = pts

    # Save ROIs to json
    with open(args.output, 'w') as f:
        json.dump(rois, f, indent=4)
    print(f"Successfully generated and saved {len(rois)} ROIs to {args.output}")

    # Visualize generated ROIs on the frame and save as a preview image
    preview_frame = frame.copy()
    for seat_id, pts in rois.items():
        pts_np = np.array(pts, dtype=np.int32)
        cv2.polylines(preview_frame, [pts_np], isClosed=True, color=(0, 255, 255), thickness=2)
        # Centroid text
        M = cv2.moments(pts_np)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
        else:
            cX, cY = pts[0][0], pts[0][1]
        cv2.putText(preview_frame, f"Seat {seat_id}", (cX - 20, cY), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    preview_path = "auto_roi_preview.jpg"
    cv2.imwrite(preview_path, preview_frame)
    print(f"Preview image saved to {preview_path}. Please inspect it to verify.")

if __name__ == "__main__":
    main()
