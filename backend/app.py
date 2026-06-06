from flask import Flask, jsonify, request
from flask_cors import CORS
import json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import paho.mqtt.client as mqtt

app = Flask(__name__)
CORS(app)

MOCK_USER = {
    "userId": "smartSeat",
    "userName": "김00"
}

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "internal/seats/event"

def load_seats():
    with open('seats.json', 'r') as f:
        return json.load(f)

def save_seats(data):
    with open('seats.json', 'w') as f:
        json.dump(data, f, indent=2)

# 1. 현재 자리 조회 기능 (GET /api/seats)
@app.route('/api/seats', methods=['GET'])
def get_seats():
    seats = load_seats()
    return jsonify(seats)

# 2. 자리 대여 기능 (POST /api/me/seats/<seatId>/rentals)
@app.route('/api/me/seats/<seatId>/rentals', methods=['POST'])
def rent_seat(seatId):
    seats = load_seats()
    if seatId not in seats:
        return jsonify({"message": "존재하지 않는 좌석입니다."}), 404
    if seats[seatId]["status"] != "AVAILABLE":
        return jsonify({"message": "이미 사용 중인 좌석입니다."}), 400

    seats[seatId]["status"] = "OCCUPIED"
    seats[seatId]["userId"] = MOCK_USER["userId"]
    seats[seatId]["awayChangedAt"] = None
    seats[seatId]["alertSentAt"] = None # 알람 발송 시간 초기화
    save_seats(seats)
    return jsonify({"message": f"{seatId}번 좌석 대여가 완료되었습니다.", "seat": seats[seatId]}), 200

# 3. 사용자가 알람창이나 화면에서 직접 [반납]을 누르는 통로 (PATCH)
@app.route('/api/me/seats/<seatId>/rentals/return', methods=['PATCH'])
def return_seat(seatId):
    seats = load_seats()
    if seatId not in seats:
        return jsonify({"message": "존재하지 않는 좌석입니다."}), 404
    if seats[seatId]["status"] == "AVAILABLE":
        return jsonify({"message": "이미 반납되었거나 사용 중이지 않은 좌석입니다."}), 400

    seats[seatId]["status"] = "AVAILABLE"
    seats[seatId]["userId"] = None
    seats[seatId]["awayChangedAt"] = None
    seats[seatId]["alertSentAt"] = None
    save_seats(seats)
    return jsonify({"message": f"{seatId}번 좌석 반납이 완료되었습니다.", "seat": seats[seatId]}), 200

# 4. 사용자가 알람창에서 [계속 사용]을 선택했을 때 호출할 통로 (PATCH 추가)
@app.route('/api/me/seats/<seatId>/rentals/keep', methods=['PATCH'])
def keep_seat(seatId):
    seats = load_seats()
    if seatId not in seats:
        return jsonify({"message": "존재하지 않는 좌석입니다."}), 404
    
    # 알람이 간 상태에서만 '계속 사용' 수락 가능
    if seats[seatId]["status"] != "AWAY_ALERTED":
        return jsonify({"message": "알람 응답 대상 좌석이 아닙니다."}), 400

    # 상태를 다시 일반 AWAY로 돌려놓고, 알람 발송 시간만 리셋 (최초 비워진 시간 awayChangedAt은 그대로 유지)
    seats[seatId]["status"] = "AWAY"
    seats[seatId]["alertSentAt"] = None
    save_seats(seats)
    return jsonify({"message": f"{seatId}번 좌석 계속 사용이 선택되었습니다. (최대 1시간 30분 감시 유지)", "seat": seats[seatId]}), 200

# 5. 시간 연장 기능 (PATCH)
@app.route('/api/me/seats/<seatId>/rentals/extend', methods=['PATCH'])
def extend_seat(seatId):
    seats = load_seats()
    if seatId not in seats:
        return jsonify({"message": "존재하지 않는 좌석입니다."}), 404
    if seats[seatId]["status"] not in ["OCCUPIED", "AWAY"]:
        return jsonify({"message": "연장할 수 없는 상태의 좌석입니다."}), 400

    current_minutes = seats[seatId].get("remainingMinutes", 180)
    extended_minutes = current_minutes + 30
    seats[seatId]["remainingMinutes"] = extended_minutes
    save_seats(seats)
    return jsonify({"message": f"{seatId}번 좌석 시간이 30분 연장되었습니다.", "remainingMinutes": extended_minutes}), 200


# 6-1. MQTT 연결 및 수신
def on_connect(client, userdata, flags, rc):
    print(f"[MQTT] 브로커 연결 성공 (코드: {rc})")
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode('utf-8')
        data = json.loads(payload)
        
        seatId = str(data.get("seatId"))
        event_type = data.get("eventType")
        detected_at = data.get("detectedAt")
        
        seats = load_seats()
        if seatId not in seats: return

        if event_type == "AWAY":
            # 이미 비어있는 상태거나 알람 간 상태면 최초 인지 시간 유지
            if seats[seatId]["status"] not in ["AWAY", "AWAY_ALERTED"]:
                seats[seatId]["status"] = "AWAY"
                seats[seatId]["awayChangedAt"] = detected_at if detected_at else datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        elif event_type == "USING":
            # 돌아오면 모든 상태 완전 초기화 (정상 이용 중)
            seats[seatId]["status"] = "OCCUPIED"
            seats[seatId]["awayChangedAt"] = None
            seats[seatId]["alertSentAt"] = None
            
        save_seats(seats)
        print(f"[MQTT 반영 완료] 좌석 {seatId}번 -> {event_type}")
    except Exception as e:
        print(f"[MQTT 에러]: {e}")


# 6-2. 3단계 자동 순찰 감시 알고리즘 (핵심 로직)
def check_away_seats():
    with app.app_context():
        seats = load_seats()
        now = datetime.now()
        updated = False
        
        print(f"🔍 [{now.strftime('%H:%M:%S')}] 정기 순찰 돌리는 중...")
        
        for seatId, info in seats.items():
            status = info["status"]
            away_str = info.get("awayChangedAt")
            alert_str = info.get("alertSentAt")
            
            if not away_str: continue
            
            # 시간 파싱 예외 처리
            away_time = datetime.strptime(away_str.replace('T', ' ')[:19], "%Y-%m-%d %H:%M:%S")
            alert_time = datetime.strptime(alert_str.replace('T', ' ')[:19], "%Y-%m-%d %H:%M:%S") if alert_str else None


            # [규칙 1] 자리를 비운 지 1시간이 지났을 때 -> 알람 발송 및 상태 변경
            # 시연 테스트용: 10초 (실제 운영: timedelta(minutes=60))
            if status == "AWAY" and not alert_time:
                if now - away_time > timedelta(seconds=10): 
                    print(f"[알람 발송] {seatId}번 사용자에게 스마트폰 알람을 보냅니다: '자리를 계속 사용하시겠습니까?'")
                    info["status"] = "AWAY_ALERTED"
                    info["alertSentAt"] = now.strftime("%Y-%m-%dT%H:%M:%S")
                    updated = True


            # [규칙 2] 알람을 보냈는데 10분 동안 묵묵부답일 때 -> 즉시 강제 반납
            # 시연 테스트용: 20초 (실제 운영: timedelta(minutes=10))
            elif status == "AWAY_ALERTED" and alert_time:
                if now - alert_time > timedelta(seconds=20):
                    print(f"[강제 반납 - 미응답] {seatId}번 사용자 10분 동안 응답 없음! 자리를 강제 반납시킵니다.")
                    info["status"] = "AVAILABLE"
                    info["userId"] = None
                    info["awayChangedAt"] = None
                    info["alertSentAt"] = None
                    updated = True


            # [규칙 3]계속 사용한다 해놓고 총 비워둔 지 1시간 반이 넘었을 때 -> 최종 강제 반납
            # 시연 테스트용: 40초 (실제 운영: timedelta(minutes=90))
            if status == "AWAY" and alert_str is None: # 알람을 한 번 거쳤다가 계속 사용을 눌러 리셋된 상태
                if now - away_time > timedelta(seconds=40):
                    print(f"[강제 반납 - 시간 초과] {seatId}번 자리 비운 지 1시간 30분 초과! 무조건 강제 반납 처리합니다.")
                    info["status"] = "AVAILABLE"
                    info["userId"] = None
                    info["awayChangedAt"] = None
                    info["alertSentAt"] = None
                    updated = True
                    
        if updated:
            save_seats(seats)

# 스케줄러 및 MQTT 기동
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_away_seats, trigger="interval", seconds=10) # 10초마다 순찰 돌기
scheduler.start()

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)