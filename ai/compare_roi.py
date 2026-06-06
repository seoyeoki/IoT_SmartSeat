import cv2
import json
import os
import argparse
import numpy as np
from ultralytics import YOLO

def detect_chairs(model, frame, conf_threshold=0.3):
    results = model(frame, verbose=False)
    detections = results[0].boxes
    chairs = []
    for box in detections:
        cls_id = int(box.cls[0].item())
        conf = float(box.conf[0].item())
        if cls_id == 56 and conf >= conf_threshold: # Chair class
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
    # Sort chairs from top-left to bottom-right
    chairs.sort(key=lambda item: (item['cy'], item['cx']))
    return chairs

def calculate_method_a(chairs, img_shape, scale_w=1.6, scale_h=2.0):
    """Method A: Fixed Ratio Extension. Simply expands the chair box regardless of neighbors."""
    h_img, w_img = img_shape[:2]
    rois = {}
    for i, ch in enumerate(chairs):
        seat_id = str(i + 1)
        cx, cy = ch['cx'], ch['cy']
        w, h = ch['w'], ch['h']
        
        shift_y = -int(h * 0.5)
        target_cy = max(0, cy + shift_y)

        half_w = int((w * scale_w) / 2)
        half_h = int((h * scale_h) / 2)

        x1 = max(0, cx - half_w)
        y1 = max(0, target_cy - half_h)
        x2 = min(w_img - 1, cx + half_w)
        y2 = min(h_img - 1, target_cy + half_h)
        rois[seat_id] = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    return rois

def calculate_method_b(chairs, img_shape, scale_w=1.6, scale_h=2.0):
    """Method B: Spatial Partitioning (Equal Partition). Scales box, but caps size by half distance to closest neighbor."""
    h_img, w_img = img_shape[:2]
    rois = {}
    for i, ch in enumerate(chairs):
        seat_id = str(i + 1)
        cx, cy = ch['cx'], ch['cy']
        w, h = ch['w'], ch['h']

        # Start with default expansion
        min_dist_x = w * scale_w
        min_dist_y = h * scale_h

        # Find closest neighbor to divide space 50-50
        for j, other in enumerate(chairs):
            if i == j:
                continue
            dx = abs(cx - other['cx'])
            dy = abs(cy - other['cy'])
            dist = np.sqrt(dx**2 + dy**2)
            
            if dist < max(w, h) * 4: # Near neighbors
                if dx > 10:
                    min_dist_x = min(min_dist_x, dx * 0.9) # 90% of distance -> 45% radius for each
                if dy > 10:
                    min_dist_y = min(min_dist_y, dy * 0.9)

        shift_y = -int(h * 0.5)
        target_cy = max(0, cy + shift_y)

        half_w = int(min_dist_x / 2)
        half_h = int(min_dist_y / 2)

        x1 = max(0, cx - half_w)
        y1 = max(0, target_cy - half_h)
        x2 = min(w_img - 1, cx + half_w)
        y2 = min(h_img - 1, target_cy + half_h)
        rois[seat_id] = [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]
    return rois

def draw_rois(frame, rois, title):
    canvas = frame.copy()
    # Semi-transparent overlay for text box background
    cv2.rectangle(canvas, (0, 0), (canvas.shape[1], 40), (0, 0, 0), -1)
    cv2.putText(canvas, title, (15, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    for seat_id, pts in rois.items():
        pts_np = np.array(pts, dtype=np.int32)
        # Draw bounding lines
        cv2.polylines(canvas, [pts_np], isClosed=True, color=(0, 255, 255), thickness=2)
        
        # Calculate label position
        M = cv2.moments(pts_np)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
        else:
            cX, cY = pts[0][0], pts[0][1]
        
        # Draw seat label
        cv2.putText(canvas, f"Seat {seat_id}", (cX - 25, cY), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
    return canvas

def main():
    parser = argparse.ArgumentParser(description="AI Seat ROI Algorithm Comparison Simulator (A vs B)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--images", nargs="+", help="Space-separated list of image file paths")
    group.add_argument("--dir", type=str, help="Directory containing images to process")
    
    parser.add_argument("--model", type=str, default="yolov8n.pt", help="YOLOv8 model weights path")
    parser.add_argument("--out-dir", type=str, default="comparison_results", help="Directory to save comparison results")
    args = parser.parse_args()

    # Load Model
    print(f"Loading YOLOv8: {args.model}...")
    model = YOLO(args.model)

    # Collect Images
    image_paths = []
    if args.images:
        image_paths = args.images
    elif args.dir:
        if os.path.exists(args.dir):
            valid_exts = ('.jpg', '.jpeg', '.png', '.bmp')
            image_paths = [os.path.join(args.dir, f) for f in os.listdir(args.dir) if f.lower().endswith(valid_exts)]
        else:
            print(f"Directory {args.dir} not found.")
            return

    if not image_paths:
        print("No valid images found to compare.")
        return

    os.makedirs(args.out_dir, exist_ok=True)
    print(f"Processing {len(image_paths)} images. Outputs will be saved to '{args.out_dir}'...")

    for idx, img_path in enumerate(image_paths):
        filename = os.path.basename(img_path)
        print(f"[{idx+1}/{len(image_paths)}] Processing: {filename}")
        
        frame = cv2.imread(img_path)
        if frame is None:
            print(f"Error loading image: {img_path}")
            continue

        # Detect Chairs
        chairs = detect_chairs(model, frame)
        if not chairs:
            print(f"No chairs detected in {filename}. Skipping comparison.")
            continue

        # Calculate ROIs
        rois_a = calculate_method_a(chairs, frame.shape)
        rois_b = calculate_method_b(chairs, frame.shape)

        # Draw results
        canvas_a = draw_rois(frame, rois_a, "Method A: Fixed Ratio Extension")
        canvas_b = draw_rois(frame, rois_b, "Method B: Equal Space Partitioning")

        # Combine side-by-side
        comparison_view = np.hstack((canvas_a, canvas_b))

        # Save result
        out_path = os.path.join(args.out_dir, f"compare_{filename}")
        cv2.imwrite(out_path, comparison_view)
        print(f"-> Saved comparison to {out_path}")

        # Show in OpenCV Window (with exception handling for headless systems)
        try:
            cv2.imshow("ROI Comparison: Method A vs Method B", comparison_view)
            print("Press any key in the window to load the next image. Press 'q' to quit.")
            key = cv2.waitKey(0) & 0xFF
            if key == ord('q'):
                print("Simulation aborted by user.")
                break
        except Exception:
            # Headless server or GUI connection issues
            pass

    cv2.destroyAllWindows()
    
    # Generate index.html report to easily view results in browsers
    html_path = os.path.join(args.out_dir, "index.html")
    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Seat ROI Algorithm Comparison (Method A vs B)</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #121212;
            color: #e0e0e0;
            margin: 0;
            padding: 20px;
        }}
        h1 {{
            text-align: center;
            color: #00e5ff;
            margin-top: 10px;
        }}
        p.subtitle {{
            text-align: center;
            color: #aaa;
            margin-bottom: 30px;
            font-size: 1.1em;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(600px, 1fr));
            gap: 25px;
            max-width: 1600px;
            margin: 0 auto;
        }}
        .card {{
            background-color: #1e1e1e;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
            border: 1px solid #333;
        }}
        .card-header {{
            padding: 12px 20px;
            background-color: #252525;
            font-weight: bold;
            font-size: 1.1em;
            border-bottom: 1px solid #333;
            color: #00e5ff;
        }}
        .img-container {{
            width: 100%;
            text-align: center;
        }}
        .img-container img {{
            width: 100%;
            height: auto;
            display: block;
        }}
    </style>
</head>
<body>
    <h1>AI Seat ROI Algorithm Comparison</h1>
    <p class="subtitle">Method A: Fixed Ratio Extension (Left) vs Method B: Equal Space Partitioning (Right)</p>
    <div class="grid">
"""
    # Add image cards
    for img_path in image_paths:
        filename = os.path.basename(img_path)
        compare_filename = f"compare_{filename}"
        compare_img_path = os.path.join(args.out_dir, compare_filename)
        if os.path.exists(compare_img_path):
            html_content += f"""        <div class="card">
            <div class="card-header">{filename}</div>
            <div class="img-container">
                <img src="{compare_filename}" alt="Comparison for {filename}">
            </div>
        </div>
"""
            
    html_content += """    </div>
</body>
</html>
"""
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"\nGenerated HTML report at: {html_path}")
        print("To view results, you can open this file in any web browser.")
    except Exception as e:
        print(f"Failed to generate HTML report: {e}")

    print("\nComparison finished. All results saved successfully.")

if __name__ == "__main__":
    main()
