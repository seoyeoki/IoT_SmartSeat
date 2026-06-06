# 스마트 열람실 좌석 관리 시스템 (SmartSeat)

본 프로젝트는 IoT 기반의 **스마트 열람실 좌석 관리 시스템**입니다. 좌석 예약/반납을 위한 웹 프론트엔드, 스케줄러와 데이터베이스를 담당하는 백엔드 API 서버, 그리고 실시간으로 자리에 사람/짐 유무를 체크하는 AI 카메라 감지 모듈로 구성되어 있습니다.

---

## 📂 프로젝트 폴더 구조
* **[`/frontend`](file:///Users/seoyeon/Desktop/영남대학교%20컴퓨터공학과/4학년%201학기/IoT/과제/SmartSeat/frontend)**: 사용자용 좌석 상태 조회 및 예약/반납/시간 연장 웹 UI
* **[`/backend`](file:///Users/seoyeon/Desktop/영남대학교%20컴퓨터공학과/4학년%201학기/IoT/과제/SmartSeat/backend)**: Flask 기반 REST API 및 실시간 자리 비움 감시 스케줄러 (JSON DB)
* **[`/ai`](file:///Users/seoyeon/Desktop/영남대학교%20컴퓨터공학과/4학년%201학기/IoT/과제/SmartSeat/ai)**: YOLOv8을 활용한 좌석 점유 및 짐 검출 감지기 (MQTT 이벤트 발행)

---

## 🚀 빠른 시작 및 실행 방법

통합 데모 시연 시 3개의 터미널을 열고 순서대로 구동합니다.

### 1단계. Backend 실행 (포트: 5001)
```bash
cd backend
source venv/bin/activate  # (윈도우: .\venv\Scripts\activate)
pip install -r requirements.txt
python app.py
```

### 2단계. Frontend 실행
```bash
cd frontend
# (프론트엔드 구동용 로컬 웹 서버 실행 명령어 실행)
```

### 3단계. AI 카메라 모듈 실행 (MQTT 연동)
YOLOv8 모델을 가동하여 실시간으로 의자 영역 내 사람/짐 유무를 판단해 백엔드 브로커로 상태를 전송합니다.
```bash
cd ai
source venv/bin/activate
pip install -r requirements.txt

# 1. 비디오/카메라에서 좌석 영역(ROI) 쪼개기 및 매핑 (직사각형/마름모 자동 생성)
python auto_roi_generator.py --source video2.mp4 --shape rect

# 2. 실시간 상태 감지기 구동 (상태 변화 시 MQTT 전송)
python seat_detector.py --source video2.mp4 --roi seats_roi.json
```
* **구독 토픽**: `internal/seats/event`
* AI 모듈에 관한 더 자세한 수동 마우스 지정 툴, 지표 분석 요약 툴(`analyze_metrics.py`) 실행 방법은 **[`/ai/README.md`](file:///Users/seoyeon/Desktop/영남대학교%20컴퓨터공학과/4학년%201학기/IoT/과제/SmartSeat/ai/README.md)** 파일을 참고해 주세요.
