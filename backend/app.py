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

if __name__ == '__main__':
    # 맥북 5000번 포트 충돌 피하기 위해 5001번으로 고정
    app.run(debug=True, host='0.0.0.0', port=5001)