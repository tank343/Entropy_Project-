#include <esp_now.h>
#include <WiFi.h>

typedef struct struct_message {
    float entropy; float snr; float cr;
    uint32_t seq; uint32_t timestamp;
} struct_message;
struct_message incoming;

uint32_t lastSeq = 0;
uint32_t totalExpected = 0;
uint32_t lostCount = 0;
uint32_t lastRecvTime = 0;
bool first = true;

void OnDataRecv(const esp_now_recv_info * info, const uint8_t *data, int len) {
    uint32_t now = micros();
    memcpy(&incoming, data, sizeof(incoming));
    
    if (first) { 
        lastSeq = incoming.seq; 
        first = false; 
        return; 
    }
    
    // --- LOGIC PHÁT HIỆN MẤT GÓI MỚI ---
    if (incoming.seq > lastSeq + 1) {
        // Mất gói do nhiễu/khoảng cách (Số nhảy cóc)
        lostCount += (incoming.seq - lastSeq - 1);
    } 
    else if (incoming.seq < lastSeq) {
        // Mất gói do TX bị Reset (Số quay về 0)
        lostCount++; 
    }
    
    lastSeq = incoming.seq;
    totalExpected++;

    // Tỉ lệ mất gói (%)
    float plr = ((float)lostCount / (totalExpected + lostCount)) * 100.0;

    // Jitter
    uint32_t jitter = now - lastRecvTime;
    lastRecvTime = now;

    // Gửi lên Python: H, SNR, CR, RSSI, Jitter, PLR
    Serial.printf("%.2f,%.2f,%.2f,%d,%u,%.2f\n", 
                  incoming.entropy, incoming.snr, incoming.cr, 
                  info->rx_ctrl->rssi, jitter, plr);
}

void setup() {
    Serial.begin(115200);
    WiFi.mode(WIFI_STA);
    esp_now_init();
    esp_now_register_recv_cb(esp_now_recv_cb_t(OnDataRecv));
    Serial.println("RX_READY");
}
void loop() {}