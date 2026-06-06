import csv
import os
import argparse
from collections import defaultdict
import matplotlib.pyplot as plt

def main():
    parser = argparse.ArgumentParser(description="SmartSeat AI Metrics Analyzer")
    parser.add_argument("--csv", type=str, default="metrics.csv", help="Path to metrics.csv file")
    parser.add_argument("--out-img", type=str, default="metrics_analysis.png", help="Path to save output chart")
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        print(f"Error: {args.csv} does not exist. Run seat_detector.py first to collect metrics.")
        return

    print(f"Reading metrics from {args.csv}...")

    # Data containers
    timestamps = []
    fps_values = []
    inf_times = []
    
    # seat_occupancy = {seat_id: {state: count}}
    seat_occupancy = defaultdict(lambda: defaultdict(int))
    total_frames_per_seat = defaultdict(int)

    try:
        with open(args.csv, mode='r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader) # Skip header
            
            # Expected columns: ['timestamp', 'fps', 'inference_time_ms', 'seat_id', 'detected_state', 'person_conf', 'luggage_conf']
            for row in reader:
                if not row or len(row) < 7:
                    continue
                
                ts = row[0]
                fps = float(row[1])
                inf_time = float(row[2])
                seat_id = row[3]
                state = row[4]
                
                # We store unique timestamps for overall telemetry trends
                timestamps.append(ts)
                fps_values.append(fps)
                inf_times.append(inf_time)
                
                seat_occupancy[seat_id][state] += 1
                total_frames_per_seat[seat_id] += 1
                
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    if not fps_values:
        print("CSV file is empty or lacks valid rows.")
        return

    # 1. Calculate Summary Statistics
    # Since multiple seats log per timestamp, we average overall telemetry per frame
    # Unique metrics calculation based on timestamps
    total_records = len(fps_values)
    avg_fps = sum(fps_values) / total_records
    avg_inf_time = sum(inf_times) / total_records
    max_inf_time = max(inf_times)
    min_inf_time = min(inf_times)

    print("\n==================================================")
    print("                AI 성능 지표 요약 리포트")
    print("==================================================")
    print(f" 총 기록 프레임 수  : {total_records} records")
    print(f" 평균 처리 속도 (FPS): {avg_fps:.2f} frames/sec")
    print(f" 평균 딥러닝 추론 시간: {avg_inf_time:.2f} ms")
    print(f" 최대/최소 추론 시간  : {max_inf_time:.2f} ms / {min_inf_time:.2f} ms")
    print("--------------------------------------------------")
    print(" [좌석별 사용 점유율 통계]")
    
    sorted_seats = sorted(seat_occupancy.keys(), key=lambda x: int(x) if x.isdigit() else x)
    
    seat_ids_chart = []
    using_ratios = []

    for seat_id in sorted_seats:
        total = total_frames_per_seat[seat_id]
        using_count = seat_occupancy[seat_id]["USING"]
        away_count = seat_occupancy[seat_id]["AWAY"]
        empty_count = seat_occupancy[seat_id]["EMPTY"] # for legacy compatibility if any
        
        using_ratio = (using_count / total) * 100 if total > 0 else 0
        away_ratio = ((away_count + empty_count) / total) * 100 if total > 0 else 0
        
        seat_ids_chart.append(f"Seat {seat_id}")
        using_ratios.append(using_ratio)
        
        print(f" * 좌석 {seat_id:2s} -> USING (사용 중/짐 있음): {using_ratio:6.2f}% ({using_count}/{total} frames)")
        print(f"           -> AWAY  (빈자리/부재중) : {away_ratio:6.2f}% ({away_count + empty_count}/{total} frames)")
    print("==================================================\n")

    # 2. Generate and Save Plot
    print(f"Generating charts and saving to {args.out_img}...")
    
    # We downsample timestamps to avoid crowded x-axis
    step = max(1, len(inf_times) // 20)
    indices = range(0, len(inf_times), step)
    sampled_times = [inf_times[i] for i in indices]
    sampled_labels = [timestamps[i].split(" ")[1] for i in indices] # Only take time part (HH:MM:SS)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Left: Inference Time Trend
    ax1.plot(sampled_times, marker='o', color='#00e5ff', linestyle='-', linewidth=2)
    ax1.set_title("Inference Latency Trend (YOLOv8n)", fontsize=12, fontweight='bold', color='#333333')
    ax1.set_xlabel("Time (HH:MM:SS)", fontsize=10)
    ax1.set_ylabel("Inference Time (ms)", fontsize=10)
    ax1.set_xticks(range(len(sampled_labels)))
    ax1.set_xticklabels(sampled_labels, rotation=45, ha='right')
    ax1.grid(True, linestyle='--', alpha=0.6)

    # Right: Seat Occupancy Bar Chart
    colors = ['#00e575' if ratio > 50 else '#ff9100' for ratio in using_ratios]
    bars = ax2.bar(seat_ids_chart, using_ratios, color=colors, edgecolor='#555555', width=0.6)
    ax2.set_title("Seat Occupancy Rate (%)", fontsize=12, fontweight='bold', color='#333333')
    ax2.set_ylabel("Percentage (%)", fontsize=10)
    ax2.set_ylim(0, 100)
    ax2.grid(True, axis='y', linestyle='--', alpha=0.6)

    # Add values on top of bars
    for bar in bars:
        height = bar.get_height()
        ax2.annotate(f'{height:.1f}%',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),  # 3 points vertical offset
                    textcoords="offset points",
                    ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    plt.savefig(args.out_img, dpi=300)
    print("Metrics analysis completed successfully.")

if __name__ == "__main__":
    main()
