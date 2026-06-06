import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const BASE_URL = 'http://192.168.45.116:5001'; 
const MY_USER_ID = 'smartSeat'; 

function App() {
  const [seats, setSeats] = useState({}); 
  const [selectedSeatId, setSelectedSeatId] = useState(null); 
  const [showAwayModal, setShowAwayModal] = useState(false); 
  const hasAlertedAway = useRef(false);

  // ① 전체 좌석 상태 조회 (GET /api/seats)

  const fetchSeats = async () => {
    try {
      const response = await fetch(`${BASE_URL}/api/seats`);
      if (response.ok) {
        const data = await response.json();
        setSeats(data);

        const mySeatKey = Object.keys(data).find(key => data[key]?.userId === MY_USER_ID);
        
        if (mySeatKey && data[mySeatKey]?.status === 'AWAY_ALERTED') {
          if (!hasAlertedAway.current) {
            setShowAwayModal(true);
            hasAlertedAway.current = true; 
          }
        } else {
          hasAlertedAway.current = false;
        }
      }
    } catch (error) {
      console.error('백엔드 서버 연결 실패:', error);
    }
  };

  useEffect(() => {
    fetchSeats(); 
    const interval = setInterval(fetchSeats, 2000); 
    return () => clearInterval(interval);
  }, []);

  const mySeatId = seats ? Object.keys(seats).find(key => seats[key]?.userId === MY_USER_ID) : null;
  const mySeatInfo = mySeatId ? seats[mySeatId] : null;

  
   // ② 좌석 대여하기 (기존 좌석이 있으면 자동 반납 후 새 좌석 대여)
  const handleRentSeat = async (seatId) => {
    try {

      // 이미 사용 중인 자리가 있다면 기존 자리 반납 API를 먼저 호출
      if (mySeatId) {
        const returnResponse = await fetch(`${BASE_URL}/api/me/seats/${mySeatId}/rentals/return`, {
          method: 'PATCH',
        });
        if (!returnResponse.ok) {
          alert('기존 좌석 반납에 실패하여 새 좌석을 대여할 수 없습니다.');
          return;
        }
      }

      // 새 좌석 대여 API 호출
      const response = await fetch(`${BASE_URL}/api/me/seats/${seatId}/rentals`, {
        method: 'POST',
      });

      if (response.ok) {
        if (mySeatId) {
          alert(`${mySeatId}번 좌석이 자동 반납되고, ${seatId}번 좌석으로 이동되었습니다.`);
        } else {
          alert(`${seatId}번 좌석 대여가 완료되었습니다.`);
        }
        setSelectedSeatId(null);
        fetchSeats();
      } else {
        const errData = await response.json();
        alert(errData.message || '대여에 실패했습니다.');
      }
    } catch (error) {
      console.error('대여/이동 에러:', error);
    }
  };

   // ③ 좌석 반납하기
  const handleReturnSeat = async (seatId) => {
    if (!seatId) return;
    try {
      const response = await fetch(`${BASE_URL}/api/me/seats/${seatId}/rentals/return`, {
        method: 'PATCH',
      });
      if (response.ok) {
        alert('자리가 정상적으로 반납되었습니다.');
        setShowAwayModal(false);
        fetchSeats();
      }
    } catch (error) {
      console.error('반납 에러:', error);
    }
  };

  // ④ 시간 연장하기
  const handleExtendSeat = async (seatId) => {
    if (!seatId) return;

    const currentMinutes = mySeatInfo ? Number(mySeatInfo.remainingMinutes || 180) : 180;
    
    // 현재 시간에 30분을 더한 예측값 계산
    const expectedMinutes = currentMinutes + 30;

    // 예측값이 180분을 넘어가면 백엔드 요청을 보내지 않고 즉시 차단
    if (expectedMinutes > 180) {
      alert(`최대 이용 시간 초과`);
      return;
    }

    try {
      const response = await fetch(`${BASE_URL}/api/me/seats/${seatId}/rentals/extend`, {
        method: 'PATCH',
      });
      if (response.ok) {
        alert('이용 시간이 30분 연장되었습니다.');
        fetchSeats();
      } else {
        const errData = await response.json();
        alert(errData.message || '연장할 수 없는 상태입니다.');
      }
    } catch (error) {
      console.error('연장 에러:', error);
    }
  };

  // ⑤ 알람 확인 시 자리 유지하기
  const handleKeepSeat = async (seatId) => {
    if (!seatId) return;
    try {
      const response = await fetch(`${BASE_URL}/api/me/seats/${seatId}/rentals/keep`, {
        method: 'PATCH',
      });
      if (response.ok) {
        alert('자리 유지가 접수되었습니다.');
        setShowAwayModal(false);
        fetchSeats();
      } else {
        const errData = await response.json();
        alert(errData.message || '처리 오류가 발생했습니다.');
      }
    } catch (error) {
      console.error('자리 유지 에러:', error);
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>스마트 좌석 관리 시스템</h1>
        <p className="location-tag">IT관 라운지 3층</p>
      </header>

      <main className="app-content">
        <section className="my-status-section">
          <h2>내 대여 정보 <span className="user-id-badge">사용자 계정: {MY_USER_ID}</span></h2>
          {mySeatInfo ? (
            /* 🌟 borderTop과 border를 none으로 밀어버려 CSS에 선언된 붉은 라인을 강제 차단했습니다. */
            <div 
              className={`status-card active ${mySeatInfo.status.includes('AWAY') ? 'status-away' : ''}`}
              style={{ borderTop: 'none', border: 'none', boxShadow: '0 4px 15px rgba(0,0,0,0.05)' }}
            >
              <p className="status-title">
                {mySeatInfo.status === 'AWAY_ALERTED' ? '⚠️ 자리비움 경고 알람 발생!' : 
                 mySeatInfo.status === 'AWAY' ? '🟡 현재 자리 비움 상태' : '🔴 현재 좌석 이용 중'}
                <br />
                <span className="highlight">{mySeatId}번 좌석</span>
              </p>
              <p>남은 이용 시간: <span className="time-highlight">{mySeatInfo.remainingMinutes || 180}분</span></p>
              <div className="btn-group">
                <button className="btn extend-btn" onClick={() => handleExtendSeat(mySeatId)}>시간 연장 (30분)</button>
                <button className="btn return-btn" onClick={() => handleReturnSeat(mySeatId)}>자리 반납하기</button>
              </div>
            </div>
          ) : (
            <div className="status-card empty">
              <p>대여한 자리가 없습니다. 아래 배치도에서 이용할 좌석을 선택하세요.</p>
            </div>
          )}
        </section>

        <section className="lounge-section">
          <h2>좌석 배치도</h2>
          <div className="seat-grid">
            {seats && Object.keys(seats).length > 0 ? (
              Object.keys(seats)
                .sort((a, b) => Number(a) - Number(b)) 
                .map((seatId) => {
                  const seat = seats[seatId];
                  if (!seat) return null; 

                  const isMine = seat.userId === MY_USER_ID;
                  const isAvailable = seat.status === 'AVAILABLE';

                  let statusClass = 'available';
                  if (seat.status === 'OCCUPIED') statusClass = 'occupied';
                  if (seat.status === 'AWAY' || seat.status === 'AWAY_ALERTED') statusClass = 'away';

                  return (
                    <button
                      key={seatId}
                      className={`seat-box ${statusClass} ${isMine ? 'my-seat' : ''}`}
                      disabled={!isAvailable && !isMine}
                      onClick={() => {
                        if (isAvailable) {
                          setSelectedSeatId(seatId);
                        }
                      }}
                    >
                      <div className="seat-number">{seatId}번</div>
                      <div className="seat-status-text">
                        {isAvailable && '대여 가능'}
                        {!isAvailable && (isMine ? '내 자리' : '이용 중')}
                        {(seat.status === 'AWAY' || seat.status === 'AWAY_ALERTED') && ' (부재)'}
                      </div>
                      {seat.remainingMinutes > 0 && !isAvailable && (
                        <div className="seat-time-text">{seat.remainingMinutes}분 남음</div>
                      )}
                    </button>
                  );
                })
            ) : (
              <div className="loading-text" style={{ padding: '20px', textAlign: 'center', color: '#888' }}>
                좌석 정보를 불러오는 중입니다...
              </div>
            )}
          </div>
        </section>
      </main>

      {selectedSeatId && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h3>자리 대여하기</h3>
            {mySeatId ? (
              <p className="modal-msg">
                이전 <span className="highlight" style={{color: '#d9534f'}}>{mySeatId}번 좌석을 반납</span>하고<br />
                <span className="highlight">{selectedSeatId}번 좌석</span>으로 이동하시겠습니까?
              </p>
            ) : (
              <p className="modal-msg"><span className="highlight">{selectedSeatId}번 좌석</span>을 대여하시겠습니까?</p>
            )}
            <p className="sub-text">(기본 이용 시간: 3시간)</p>
            <div className="modal-btn-group">
              <button className="btn confirm-btn" onClick={() => handleRentSeat(selectedSeatId)}>예</button>
              <button className="btn cancel-btn" onClick={() => setSelectedSeatId(null)}>아니오</button>
            </div>
          </div>
        </div>
      )}

      {showAwayModal && (
        <div className="modal-overlay">
          <div className="modal-content alert-modal">
            <h3 className="alert-title">⚠️ 자리가 비어 있어요!</h3>
            <p className="modal-msg">AI 카메라가 사용자의 이탈을 감지했습니다.<br />반납을 잊으셨나요?</p>
            <p className="sub-text danger-text">※ 미응답 상태가 지속되면 자동 강제 반납 처리됩니다.</p>
            <div className="modal-btn-group vertical">
              <button className="btn keep-btn large" onClick={() => handleKeepSeat(mySeatId)}>계속 사용하기</button>
              <button className="btn return-btn large" onClick={() => handleReturnSeat(mySeatId)}>지금 반납하기</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;