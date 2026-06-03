from flask import Flask, jsonify, request
import json

app = Flask(__name__)

# 로그인 상태를 가정할 사용자 데이터
MOCK_USER = {
    "userId": "22311894",
    "userName": "김서연"
}

# seats.json 파일을 읽어오는 함수
def load_seats():
    with open('seats.json', 'r') as f:
        return json.load(f)

# seats.json 파일에 데이터를 저장하는 함수
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
    
    # 만약 요청한 좌석 번호가 파일에 없으면 에러 반환
    if seatId not in seats:
        return jsonify({"message": "존재하지 않는 좌석입니다."}), 404
        
    # 이미 대여 중인 자리라면 에러 반환
    if seats[seatId]["status"] != "AVAILABLE":
        return jsonify({"message": "이미 사용 중인 좌석입니다."}), 400

    # [대여 성공 처리] 좌석 상태를 변경
    seats[seatId]["status"] = "OCCUPIED"
    seats[seatId]["userId"] = MOCK_USER["userId"] # 가정한 사용자 학번 주입
    
    # 바뀐 데이터를 다시 파일에 저장
    save_seats(seats)
    
    return jsonify({
        "message": f"{seatId}번 좌석 대여가 완료되었습니다.",
        "seat": seats[seatId]
    }), 200

# 3. 자리 반납 기능 (PATCH /api/me/seats/<seatId>/rentals/return)
@app.route('/api/me/seats/<seatId>/rentals/return', methods=['PATCH'])
def return_seat(seatId):
    seats = load_seats()
    
    # 존재하지 않는 좌석 예외 처리
    if seatId not in seats:
        return jsonify({"message": "존재하지 않는 좌석입니다."}), 404
        
    # 이미 비어 있는 자리라면 반납할 필요 없음
    if seats[seatId]["status"] == "AVAILABLE":
        return jsonify({"message": "이미 반납되었거나 사용 중이지 않은 좌석입니다."}), 400

    # 반납 성공 처리 - 좌석 정보를 초기 상태로 리셋
    seats[seatId]["status"] = "AVAILABLE"
    seats[seatId]["userId"] = None
    seats[seatId]["awayChangedAt"] = None
    
    # 변경된 데이터를 파일에 저장
    save_seats(seats)
    
    return jsonify({
        "message": f"{seatId}번 좌석 반납이 완료되었습니다.",
        "seat": seats[seatId]
    }), 200

# 4. 자리 연장 기능 (PATCH /api/me/seats/<seatId>/rentals/extend)
@app.route('/api/me/seats/<seatId>/rentals/extend', methods=['PATCH'])
def extend_seat(seatId):
    seats = load_seats()
    
    # 존재하지 않는 좌석 예외 처리
    if seatId not in seats:
        return jsonify({"message": "존재하지 않는 좌석입니다."}), 404
        
    # 대여 중인 자리가 아니면 연장할 수 없음
    if seats[seatId]["status"] != "OCCUPIED":
        return jsonify({"message": "대여 중인 좌석이 아니라서 연장할 수 없습니다."}), 400

    # 테스트를 위해 기존 남은 시간에 30분을 더해주는 임시 로직
    # 만약 기존에 값이 없었다면 기본 180분(3시간)에서 시작
    current_minutes = seats[seatId].get("remainingMinutes", 180)
    extended_minutes = current_minutes + 30
    
    # 변경된 데이터를 파일에 저장
    seats[seatId]["remainingMinutes"] = extended_minutes
    save_seats(seats)
    
    return jsonify({
        "message": f"{seatId}번 좌석 시간이 30분 연장되었습니다.",
        "remainingMinutes": extended_minutes,
        "seat": seats[seatId]
    }), 200

if __name__ == '__main__':
    # 5001번으로 고정
    app.run(debug=True, host='0.0.0.0', port=5001)