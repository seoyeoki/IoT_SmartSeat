from flask import Flask, jsonify
import json

app = Flask(__name__)

# seats.json 파일을 읽어오는 함수
def load_seats():
    with open('seats.json', 'r') as f:
        return json.load(f)

# 현재 자리 조회 기능 (GET /api/seats)
@app.route('/api/seats', methods=['GET'])
def get_seats():
    seats = load_seats()
    return jsonify(seats)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)