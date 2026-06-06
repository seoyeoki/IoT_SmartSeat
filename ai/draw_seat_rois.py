import cv2
import json
import os
import numpy as np

# Ground-truth manually mapped ROIs for 1.jpg, 2.jpg, 3.jpg, 4.jpg
# Maps exact chair-desk pair boundaries for each seat
MANUAL_ROIS = {
    "1.jpg": {
        "1": [[590, 220], [1080, 220], [1080, 940], [590, 940]],  # Right partitioned seat
        "2": [[65, 220], [560, 220], [560, 940], [65, 940]]       # Left partitioned seat
    },
    "2.jpg": {
        "8": [[2, 100], [95, 100], [95, 166], [2, 166]],
        "7": [[120, 90], [175, 90], [175, 140], [120, 140]],
        "3": [[165, 65], [215, 65], [215, 115], [165, 115]],
        "6": [[185, 80], [240, 80], [240, 135], [185, 135]],
        "5": [[220, 70], [270, 70], [270, 120], [220, 120]],
        "4": [[235, 75], [285, 75], [285, 125], [235, 125]],
        "2": [[255, 65], [298, 65], [298, 105], [255, 105]],
        "1": [[265, 70], [298, 70], [298, 100], [265, 100]]
    },
    "3.jpg": {
        "10": [[290, 260], [420, 260], [420, 595], [290, 595]], # Large center seat
        "9": [[230, 250], [335, 250], [335, 545], [230, 545]],  # Seat left to 10
        "11": [[400, 280], [500, 280], [500, 595], [400, 595]], # Seat right to 10
        "8": [[200, 215], [255, 215], [255, 450], [200, 450]],
        "7": [[145, 210], [215, 210], [215, 450], [145, 450]],
        "6": [[180, 215], [250, 215], [250, 450], [180, 450]],
        "5": [[245, 225], [305, 225], [305, 470], [245, 470]],
        "4": [[305, 230], [365, 230], [365, 480], [305, 480]],
        "3": [[80, 180], [135, 180], [135, 345], [80, 345]],
        "2": [[25, 175], [80, 175], [80, 335], [25, 335]],
        "1": [[310, 140], [355, 140], [355, 290], [310, 290]]
    },
    "4.jpg": {
        "12": [[40, 265], [105, 265], [105, 395], [40, 395]],
        "10": [[0, 250], [45, 250], [45, 360], [0, 360]],
        "8": [[95, 210], [180, 210], [180, 360], [95, 360]],
        "9": [[175, 210], [250, 210], [250, 390], [175, 390]],
        "11": [[250, 200], [350, 200], [350, 395], [250, 395]],
        "5": [[345, 190], [410, 190], [410, 340], [345, 340]],
        "7": [[295, 195], [355, 195], [355, 345], [295, 345]],
        "1": [[400, 195], [455, 195], [455, 330], [400, 330]]
    }
}

def draw_semi_transparent_poly(img, pts, color, alpha=0.3):
    overlay = img.copy()
    cv2.fillPoly(overlay, [pts], color)
    return cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0)

def main():
    print("Starting visual seat ROI mapper (Chair-Desk boundaries)...")
    
    for filename, rois in MANUAL_ROIS.items():
        if not os.path.exists(filename):
            print(f"Skipping {filename} (File not found).")
            continue
            
        print(f"Drawing seat zones on {filename}...")
        img = cv2.imread(filename)
        display_img = img.copy()
        
        for seat_id, pts in rois.items():
            pts_np = np.array(pts, dtype=np.int32)
            
            # 1. Draw a semi-transparent colored polygon overlay (Cyan/Teal hue)
            display_img = draw_semi_transparent_poly(display_img, pts_np, (255, 200, 0), alpha=0.25)
            
            # 2. Draw thick solid border
            cv2.polylines(display_img, [pts_np], isClosed=True, color=(0, 255, 0), thickness=2)
            
            # 3. Put label at the center of the polygon
            M = cv2.moments(pts_np)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
            else:
                cX, cY = pts[0][0], pts[0][1]
                
            # Draw label box
            label_text = f"Seat {seat_id}"
            (w, h), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            cv2.rectangle(display_img, (cX - int(w/2) - 4, cY - int(h/2) - 6), (cX + int(w/2) + 4, cY + int(h/2) + 6), (0, 0, 0), -1)
            cv2.putText(display_img, label_text, (cX - int(w/2), cY + int(h/2) - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            
        # Save labeled image
        out_img_name = filename.replace(".jpg", "_roi.jpg")
        cv2.imwrite(out_img_name, display_img)
        print(f"-> Saved labeled image to: {out_img_name}")
        
        # Save corresponding JSON config file
        out_json_name = filename.replace(".jpg", "_roi.json")
        with open(out_json_name, "w") as f:
            json.dump(rois, f, indent=4)
        print(f"-> Saved seat configuration to: {out_json_name}")
        
    print("\nVisual Seat ROI mapping completed. Check *_roi.jpg and *_roi.json in 'ai/' directory.")

if __name__ == "__main__":
    main()
