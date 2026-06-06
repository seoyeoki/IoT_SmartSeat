# 스마트 열람실 AI 좌석 감지 모듈

본 저장소는 IoT 스마트 열람실 좌석 관리 시스템의 **AI 카메라 감지 및 좌석 상태 모니터링 모듈**입니다. YOLOv8 객체 탐지 모델을 활용하여 각 좌석의 사람 및 소지품 유무를 실시간으로 판별하고, 백엔드 서버에 MQTT 프로토콜로 이벤트를 발행합니다.

---

## 1. 개발 환경 및 필수 라이브러리
* **Language:** Python 3.11+
* **Deep Learning Framework:** Ultralytics YOLOv8 (nano)
* **Computer Vision:** OpenCV Python
* **Protocol:** Paho-MQTT (HiveMQ Broker 연동)

---

## 2. 초기 세팅 및 가상환경 설치
```bash
# 1. ai 디렉토리로 이동
cd ai

# 2. 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 3. 필수 라이브러리 설치
pip install -r requirements.txt
```

---

## 3. 주요 모듈 및 실행 방법

### ① [자동] 좌석 ROI(관심 영역) 자동 생성기
화면 내 의자(`chair`)를 탐지하여 이웃 간 거리를 기준으로 공간을 50-50으로 균등하게 사각형/마름모꼴로 분할해 `seats_roi.json` 설정 파일을 자동으로 빌드합니다.
```bash
python auto_roi_generator.py --source video1.mp4 --shape rect
```

### ② [수동] 좌석 ROI 정밀 드로잉 툴
화면에 직접 마우스 클릭으로 다각형 꼭짓점을 찍어 구역을 정밀하게 그리고 좌석 번호(`seatId`)를 직접 연결하여 `seats_roi.json`을 저장합니다.
```bash
python roi_selector.py --source video1.mp4
```
* **단축키**: `Enter`/`c` (다각형 완료 및 좌석 번호 입력), `r` (현재 그림 리셋), `s` (json 저장 및 종료), `q` (취소)

### ③ [수동] 정밀 매핑 예제 렌더러
1~4.jpg 이미지에 매핑된 정확한 의자-책상 영역을 시각적으로 렌더링하고, 바로 디텍터에 사용할 수 있는 JSON 파일들을 복제 출력해줍니다.
```bash
python draw_seat_rois.py
# 예시: 1.jpg 칸막이형 구조 구성을 디텍터 감지 데이터로 적용
cp 1_roi.json seats_roi.json
```

### ④ [실시간] 메인 좌석 감지기 (MQTT 연동)
설정된 `seats_roi.json` 영역 내에 사람 또는 짐(책, 가방, 노트북 등)이 존재하는지 확인하여 `USING` 또는 `AWAY`로 판별하고, 상태 변화 발생 시 백엔드 MQTT 브로커로 즉각 전송합니다.
```bash
python seat_detector.py --source video1.mp4 --roi seats_roi.json
```
* **MQTT 브로커**: `broker.hivemq.com` (포트 1883)
* **발행 토픽**: `internal/seats/event`
* **JSON 페이로드**: `{"seatId": "1", "eventType": "USING" | "AWAY"}`

### ⑤ [분석] 성능 및 점유 통계 요약 분석기
수집된 `metrics.csv`를 로드하여 평균 FPS, 딥러닝 추론 지연, 좌석별 실시간 점유율을 계산하고 시각화 분석 이미지(`metrics_analysis.png`)를 렌더링해 줍니다.
```bash
python analyze_metrics.py
```

### ⑥ [비교] 영역 쪼개기 알고리즘 비교기
기법 A(단순 박스 확장)와 기법 B(이웃 간 거리 균등 분할)의 결과를 한눈에 비교하고 `index.html` 리포트를 작성해 줍니다.
```bash
python compare_roi.py --images 1.jpg 2.jpg
open comparison_results/index.html
```

---

## 4. Git 커밋 권장 가이드 (.gitignore 설정 완료)
가상환경(`venv/`) 폴더와 대용량 YOLO 모델 가중치 파일(`yolov8n.pt`)은 깃에 절대 커밋하지 않도록 사전에 `.gitignore`에 등록되어 있습니다.
*(주의: `video1.mp4`나 `video2.mp4` 등 대용량 비디오 파일은 GitHub의 단일 파일 100MB 푸시 용량 제한에 걸리므로, 로컬에서만 사용하거나 Git LFS 설정을 적용하여 업로드하시기 바랍니다.)*
