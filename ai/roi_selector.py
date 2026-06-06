import cv2
import json
import os
import argparse
import numpy as np

# global variables
points = []
rois = {}  # {seat_id: [[x1, y1], [x2, y2], ...]}

def mouse_callback(event, x, y, flags, param):
    global points
    if event == cv2.EVENT_LBUTTONDOWN:
        points.append([x, y])
        print(f"Point added: ({x}, {y})")

def main():
    global points, rois
    parser = argparse.ArgumentParser(description="Seat ROI Selector")
    parser.add_argument("--source", type=str, default="0", help="Webcam index or path to video file/image")
    parser.add_argument("--output", type=str, default="seats_roi.json", help="Output JSON path")
    args = parser.parse_args()

    # Try to load existing ROIs
    if os.path.exists(args.output):
        try:
            with open(args.output, 'r') as f:
                rois = json.load(f)
            print(f"Loaded existing ROIs from {args.output}")
        except Exception as e:
            print(f"Error loading {args.output}: {e}")

    # Load source
    frame = None
    if args.source.isdigit():
        cap = cv2.VideoCapture(int(args.source))
        ret, frame = cap.read()
        cap.release()
    elif os.path.exists(args.source):
        # check if it is image or video
        ext = os.path.splitext(args.source)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.bmp']:
            frame = cv2.imread(args.source)
        else:
            cap = cv2.VideoCapture(args.source)
            ret, frame = cap.read()
            cap.release()
    
    if frame is None:
        print("Warning: Source not found or could not be opened. Generating a dummy 800x600 image for ROI configuration.")
        frame = np.zeros((600, 800, 3), dtype=np.uint8)
        # draw a grid for helper
        for i in range(1, 4):
            cv2.line(frame, (i * 200, 0), (i * 200, 600), (50, 50, 50), 1)
            cv2.line(frame, (0, i * 150), (800, i * 150), (50, 50, 50), 1)
        cv2.putText(frame, "DUMMY FRAME (Grid)", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    cv2.namedWindow("ROI Selector")
    cv2.setMouseCallback("ROI Selector", mouse_callback)

    print("\n=== ROI Selector Instructions ===")
    print("1. Left Click to add polygon points for a seat.")
    print("2. Press 'Enter' or 'c' to complete the current polygon.")
    print("   -> Then enter the Seat ID in the terminal.")
    print("3. Press 'r' to reset the current drawing points.")
    print("4. Press 'd' to delete all defined ROIs.")
    print("5. Press 's' to save all ROIs to JSON and exit.")
    print("6. Press 'q' to quit without saving.")
    print("=================================\n")

    while True:
        display_frame = frame.copy()

        # Draw already saved ROIs
        for seat_id, pts in rois.items():
            pts_np = np.array(pts, dtype=np.int32)
            cv2.polylines(display_frame, [pts_np], isClosed=True, color=(0, 255, 0), thickness=2)
            # Find centroid to put text
            M = cv2.moments(pts_np)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
            else:
                cX, cY = pts[0][0], pts[0][1]
            cv2.putText(display_frame, f"Seat {seat_id}", (cX - 20, cY), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # Draw current drawing points
        if len(points) > 0:
            for pt in points:
                cv2.circle(display_frame, tuple(pt), 4, (0, 0, 255), -1)
            if len(points) > 1:
                cv2.polylines(display_frame, [np.array(points, dtype=np.int32)], isClosed=False, color=(255, 0, 0), thickness=1)

        cv2.imshow("ROI Selector", display_frame)
        key = cv2.waitKey(30) & 0xFF

        if key == ord('q'):
            print("Quitting without saving.")
            break
        elif key == ord('r'):
            points = []
            print("Current points reset.")
        elif key == ord('d'):
            rois = {}
            print("All ROIs cleared.")
        elif key in [13, ord('c')]:  # Enter key or 'c'
            if len(points) < 3:
                print("A polygon must have at least 3 points.")
                continue
            
            # Request seat ID in terminal
            print("\n--- Seat Registration ---")
            seat_id = input("Enter Seat ID for the drawn region: ").strip()
            if seat_id:
                rois[seat_id] = points
                print(f"Seat {seat_id} registered with {len(points)} points.")
            else:
                print("Registration cancelled (empty ID).")
            points = []
        elif key == ord('s'):
            with open(args.output, 'w') as f:
                json.dump(rois, f, indent=4)
            print(f"Successfully saved {len(rois)} ROIs to {args.output}.")
            break

    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
