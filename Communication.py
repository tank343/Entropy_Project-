import cv2
import numpy as np
import requests
import threading
import time
import winsound
from datetime import datetime

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG
# ==========================================
SOURCE = 0 # Thay bằng URL ESP32-CAM nếu cần: "http://192.168.1.XX/stream"

# Thông tin kết nối Blynk IoT
BLYNK_AUTH_TOKEN = "g9Hr0MuhXc1HigvnA57IW0ODmVa5Rzs1" 
BLYNK_BASE_URL = "https://sgp1.blynk.cloud/external/api"

# Cấu hình logic phát hiện
fire_counter = 0
CONFIRM_FRAMES = 15      # Cần 15 khung hình liên tiếp để xác nhận cháy
ALERT_INTERVAL = 30      # Gửi nhắc lại sau mỗi 30 giây nếu lửa vẫn cháy
last_alert_time = 0      
last_state = 0           

# ==========================================
# 2. HÀM TRUYỀN TIN VÀ ĐO ĐỘ TRỄ (COMMUNICATION)
# ==========================================

def trigger_alarm_process(frame, is_repeat=False):
    """Gửi cảnh báo, đo thời gian gói tin và thông báo lên điện thoại"""
    def task():
        global last_alert_time
        try:
            # Ghi lại mốc thời gian bắt đầu gửi gói tin
            start_time = time.perf_counter()
            time_now_full = datetime.now().strftime("%H:%M:%S.%f")[:-3] # Định dạng: Giờ:Phút:Giây.MiliGiây

            print(f"\n--- [LOG] BẮT ĐẦU GỬI GÓI TIN LÚC: {time_now_full} ---")
            
            # 1. Gửi Event (Thông báo đẩy Push Notification)
            event_url = f"{BLYNK_BASE_URL}/logEvent?token={BLYNK_AUTH_TOKEN}&code=fire_alert"
            requests.get(event_url, timeout=5)

            # 2. Cập nhật trạng thái V1 (Đèn đỏ) và V2 (Dòng chữ kèm mốc thời gian)
            status_msg = f"CHAY! Luc:{time_now_full}"
            requests.get(f"{BLYNK_BASE_URL}/update?token={BLYNK_AUTH_TOKEN}&v1=1", timeout=5)
            response = requests.get(f"{BLYNK_BASE_URL}/update?token={BLYNK_AUTH_TOKEN}&v2={status_msg}", timeout=5)
            
            # Tính toán độ trễ phản hồi từ Server Singapore
            latency = (time.perf_counter() - start_time) * 1000 # Chuyển sang miligiây
            
            if response.status_code == 200:
                print(f"[OK] Gói tin đã tới Server Singapore. Độ trễ (Latency): {latency:.2f} ms")
                print(f"[OK] Nội dung hiển thị trên điện thoại: {status_msg}")
            
            # 3. Lưu ảnh bằng chứng (Chỉ lưu ở lần báo động đầu tiên)
            if not is_repeat:
                filename = f"BANG_CHUNG_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                cv2.imwrite(filename, frame)
                print(f"[OK] Đã lưu bằng chứng tại máy trạm: {filename}")
            
            # 4. Hú còi báo động tại chỗ (Beep)
            for _ in range(3):
                winsound.Beep(2500, 800) 
                
        except Exception as e:
            print(f"[ERROR] Lỗi truyền tin: {e}")

    threading.Thread(target=task).start()

def reset_system_status():
    """Reset hệ thống về trạng thái an toàn"""
    def task():
        try:
            print("\n>>> [SYSTEM] Hết lửa. Đang đưa hệ thống về trạng thái AN TOÀN...")
            requests.get(f"{BLYNK_BASE_URL}/update?token={BLYNK_AUTH_TOKEN}&v1=0", timeout=5)
            requests.get(f"{BLYNK_BASE_URL}/update?token={BLYNK_AUTH_TOKEN}&v2=He thong on dinh", timeout=5)
        except:
            pass
    threading.Thread(target=task).start()

# ==========================================
# 3. VÒNG LẶP XỬ LÝ ẢNH (IMAGE PROCESSING)
# ==========================================

cap = cv2.VideoCapture(SOURCE)
# Thuật toán tách nền MOG2 để nhận diện chuyển động
fgbg = cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=50, detectShadows=True)

print("--------------------------------------------------")
print("HỆ THỐNG GIÁM SÁT CHÁY SIÊU THỊ ĐANG HOẠT ĐỘNG...")
print("--------------------------------------------------")

while True:
    ret, frame = cap.read()
    if not ret: break

    frame = cv2.resize(frame, (640, 480))
    display_frame = frame.copy()
    blurred = cv2.GaussianBlur(frame, (15, 15), 0)

    # BƯỚC 1: Tách vùng chuyển động
    fgmask = fgbg.apply(blurred)
    _, fgmask = cv2.threshold(fgmask, 200, 255, cv2.THRESH_BINARY)

    # BƯỚC 2: Tách màu lửa (Sử dụng cả HSV và YCrCb để loại bỏ màu da người)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # Lọc HSV: Chú trọng độ bão hòa S cao để bỏ qua màu da
    lower_fire = np.array([0, 130, 180]) 
    upper_fire = np.array([40, 255, 255])
    mask_hsv = cv2.inRange(hsv, lower_fire, upper_fire)

    # Lọc YCrCb: Chú trọng độ sáng Y và sắc đỏ Cr
    ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
    Y, Cr, Cb = cv2.split(ycrcb)
    mask_ycrcb = np.zeros(Y.shape, dtype=np.uint8)
    cond = (Y > 195) & (Cr > 160) & (Cb < 110) & (Cr > Cb)
    mask_ycrcb[cond] = 255

    # BƯỚC 3: Kết hợp Chuyển động AND Màu lửa
    fire_color_mask = cv2.bitwise_and(mask_hsv, mask_ycrcb)
    combined_mask = cv2.bitwise_and(fire_color_mask, fgmask)
    combined_mask = cv2.dilate(combined_mask, np.ones((5,5), np.uint8), iterations=2)

    # BƯỚC 4: Tìm Contour và xác định đám cháy
    contours, _ = cv2.findContours(combined_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    is_fire_detected = False
    for cnt in contours:
        if cv2.contourArea(cnt) > 1500: # Diện tích đủ lớn để loại bỏ nhiễu
            is_fire_detected = True
            x, y, w, h = cv2.boundingRect(cnt)
            cv2.rectangle(display_frame, (x, y), (x + w, y + h), (0, 0, 255), 3)
            cv2.putText(display_frame, "CANH BAO CHAY!", (x, y-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    # BƯỚC 5: LOGIC TRUYỀN TIN CẢNH BÁO
    if is_fire_detected:
        fire_counter += 1
    else:
        fire_counter = max(0, fire_counter - 1)

    now = time.time()
    # Trường hợp bắt đầu phát hiện cháy
    if fire_counter >= CONFIRM_FRAMES and last_state == 0:
        trigger_alarm_process(display_frame, is_repeat=False)
        last_alert_time = now
        last_state = 1
    
    # Trường hợp vẫn đang cháy (Nhắc lại sau ALERT_INTERVAL giây)
    elif last_state == 1 and (now - last_alert_time > ALERT_INTERVAL) and fire_counter >= CONFIRM_FRAMES:
        trigger_alarm_process(display_frame, is_repeat=True)
        last_alert_time = now

    # Trường hợp đã dập tắt lửa hoàn toàn
    elif fire_counter == 0 and last_state == 1:
        reset_system_status()
        last_state = 0

    # Hiển thị cửa sổ giám sát
    cv2.imshow("HE THONG GIAM SAT CHAY - NHOM 2", display_frame)
    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()