# 스마트 열람실 좌석 관리 시스템 (백엔드)

본 저장소는 IoT 프로젝트의 **스마트 열람실 시스템 백엔드 API 서버**입니다.  
Flask를 활용하여 실시간 좌석 상태 조회, 대여, 반납, 연장 기능을 제공하며, AI 카메라 연동을 통한 자동 자리 비움 감시 스케줄러가 포함되어 있습니다.

---

## 1. 개발 환경 및 기술 스택
* **Language:** Python 3.11+
* **Framework:** Flask 3.0.2 (Flask-CORS 포함)
* **Scheduler:** APScheduler 3.10.4
* **Protocol:** MQTT (Message Queuing Telemetry Transport)
* **Database:** 파일 기반 JSON 데이터베이스 (`seats.json`)

---

## 2. 초기 환경 세팅 및 실행 방법 (모듈 실행법)

### Mac / Linux 환경
```bash
# 1. 가상환경 활성화
source venv/bin/activate

# 2. 필수 라이브러리 한방에 설치
pip install -r requirements.txt

# 3. 로컬 서버 실행 (기본 포트: 5001)
python app.py
```

### Windows 환경
```bash
# 1. 가상환경 활성화
.\venv\Scripts\activate

# 2. 필수 라이브러리 한방에 설치
pip install -r requirements.txt

# 3. 로컬 서버 실행 (기본 포트: 5001)
python app.py
```

> **서버 접속 주소:** `http://127.0.0.1:5001` (CORS 허용 처리가 완료되어 프론트엔드 모듈과 즉시 다이렉트 통신이 가능합니다.)

---

## 3. 전체 통합 테스트 방법 (Frontend / Backend / AI)

본 프로젝트는 3개의 프로세스가 동시에 구동되어야 정상적인 시연이 가능합니다. 테스트 시 아래 순서대로 실행해 주세요.

1. **Backend 켜기:** 위의 실행 방법을 참고하여 터미널 1에서 `python app.py`를 실행합니다.
2. **Frontend 켜기:** 터미널 2에서 UI 구동 명령어를 실행하여 웹 화면을 띄웁니다.
3. **AI 켜기:** 터미널 3에서 카메라 감지 모듈 코드를 실행합니다.

> **시연 및 테스트 편의를 위한 안내 (현재 활성화 상태)**
> * 원래 설계안의 자동 반납 주기는 1시간(미응답 제한 10분, 최대 이탈 1시간 반)이지만, 빠른 통합 테스트 및 시연 확인을 위해 현재 분 단위 가속 스케줄러(알람 10초, 미응답 20초, 최대 이탈 40초)로 조정해 두었습니다.
> * 실제 운영용 시간으로 변경하려면 app.py 내부의 check_away_seats 함수 내 timedelta 설정을 수정하시면 됩니다.

---

## 4. UI 담당자용 API 명세서 (좌석 총 10개 세팅 완료)

### ① 전체 좌석 상태 조회
* **URL:** `GET /api/seats`
* **Response (JSON):**
  ```json
  {
    "1": { "status": "AVAILABLE", "userId": null, "awayChangedAt": null, "remainingMinutes": 180 },
    "2": { "status": "OCCUPIED", "userId": "22311894", "awayChangedAt": null, "remainingMinutes": 150 }
  }
  ```

### ② 좌석 대여하기
* **URL:** `POST /api/me/seats/<seatId>/rentals (예: /api/me/seats/1/rentals)`

* **설명:** 좌석 상태가 OCCUPIED로 변경되며 테스트용 고정 학번(22311894)이 주입됩니다.

### ③ 좌석 반납하기
* **URL:** `PATCH /api/me/seats/<seatId>/rentals/return`

* **설명:** 좌석 상태가 AVAILABLE로 리셋되며 userId 및 자리비움 시간이 초기화됩니다.

### ④ 시간 연장하기
* **URL:** `PATCH /api/me/seats/<seatId>/rentals/extend`

* **설명:** 기존 남은 시간에 기본 30분이 누적 연장됩니다.

### ⑤ 알람 확인 시 자리 유지하기
* **URL:** `PATCH /api/me/seats/<seatId>/rentals/keep`

* **설명:** 스마트폰 알람창에서 사용자가 [계속 사용] 버튼을 눌렀을 때 호출합니다. 좌석 상태가 AWAY로 유지되며 최대 제한 시간 타이머가 이어서 작동합니다.

---

## 5. AI 담당자용 이벤트 연동 명세서 (MQTT)

본 시스템은 실시간성 향상을 위해 기존 HTTP POST 방식을 폐기하고 MQTT 프로토콜 기반의 토픽 구독 방식으로 동작합니다.  
카메라 모듈은 이벤트 발생 시 아래 규격으로 메시지를 발행(Publish)해 주세요.

* **MQTT 브로커 주소:** `broker.hivemq.com`
* **구독 토픽 (Topic)** `internal/seats/event`

* **발행 메시지 규격 (JSON Body):**
  * 사용자 자리 비움 감지 시:<br>
    ```json
    {"seatId": "1", "eventType": "AWAY"}
    ```

  * 사용자 자리 복귀 감지 시:<br>
    ```json
    {"seatId": "1", "eventType": "USING"}
    ```