#include <esp_now.h>
#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// 1. MAC BOARD THU (RX) - 88:F1:55:32:05:B8
uint8_t broadcastAddress[] = {0x88, 0xF1, 0x55, 0x32, 0x05, 0xB8}; 

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

typedef struct struct_message {
    float entropy; float snr; float cr;
    uint32_t seq; uint32_t timestamp; 
} struct_message;
struct_message myData;

const int MIC_PIN = 36; 
const int FRAME_SIZE = 256; 
byte samples[FRAME_SIZE];
uint32_t packetCount = 0;
float noisePower = 39.0; 

// Hàm tính công suất (Variance) cho 1 khung dữ liệu
float getFramePower() {
    float sum = 0;
    for (int i = 0; i < FRAME_SIZE; i++) {
        int raw = analogRead(MIC_PIN);
        samples[i] = (raw >> 4); // Chuyển 12-bit sang 8-bit
        sum += samples[i];
        delayMicroseconds(50);
    }
    float mean = sum / FRAME_SIZE;
    float p = 0;
    for (int i = 0; i < FRAME_SIZE; i++) {
        float diff = (float)samples[i] - mean;
        p += diff * diff;
    }
    return (p / FRAME_SIZE) + 0.001; 
}

// HÀM HIỆU CHUẨN TRONG ĐÚNG 2 GIÂY
void runCalibration() {
    Serial.println("\n--- BAT DAU HIEU CHUAN NHIEU NEN (2 GIAY) ---");
    unsigned long startTime = millis();
    float totalP = 0; int frameCount = 0;

    while (millis() - startTime < 2000) {
        display.clearDisplay();
        display.setTextColor(WHITE);
        display.setCursor(10, 10); display.print("CALIBRATING...");
        display.drawRect(10, 30, 108, 10, WHITE);
        display.fillRect(12, 32, map(millis()-startTime,0,2000,0,104), 6, WHITE);
        display.setCursor(10, 50); display.print("Keep Silent!");
        display.display();
        
        totalP += getFramePower();
        frameCount++;
    }
    noisePower = totalP / frameCount;
    if (noisePower < 1.0) noisePower = 1.0;

    Serial.print("KET QUA HIEU CHUAN (Noise Power): ");
    Serial.println(noisePower);
    
    display.clearDisplay();
    display.setCursor(10, 25); display.print("DONE! NP: "); display.print(noisePower, 1);
    display.display();
    delay(1000);
}

float calculateEntropy() {
    float ent = 0; int counts[256] = {0};
    for (int i = 0; i < FRAME_SIZE; i++) counts[samples[i]]++;
    for (int i = 0; i < 256; i++) {
        if (counts[i] > 0) {
            float p = (float)counts[i] / FRAME_SIZE;
            ent -= p * (log(p) / log(2.0));
        }
    }
    return ent;
}

void setup() {
    Serial.begin(115200);
    Wire.begin(25, 26); // SDA=25, SCL=26
    WiFi.mode(WIFI_STA);
    if (esp_now_init() != ESP_OK) return;

    esp_now_peer_info_t peerInfo = {};
    memcpy(peerInfo.peer_addr, broadcastAddress, 6);
    peerInfo.ifidx = WIFI_IF_STA; 
    peerInfo.encrypt = false;
    esp_now_add_peer(&peerInfo);

    display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
    runCalibration();
}

void loop() {
    float currentPower = getFramePower();
    myData.entropy = calculateEntropy();

    // SNR chuẩn công suất (10*log10)
    myData.snr = 10 * log10(currentPower / noisePower);

    // CR chuẩn Shannon: 8/H (Hệ số nén)
    myData.cr = 8.0 / max(myData.entropy, 0.1f);

    myData.seq = packetCount++;
    myData.timestamp = micros();

    esp_now_send(broadcastAddress, (uint8_t *) &myData, sizeof(myData));

    // --- GIAO DIỆN OLED GIỮ NGUYÊN BỐ CỤC ĐẸP ---
    display.clearDisplay();
    
    // Header Nền trắng chữ đen
    display.fillRect(0, 0, 128, 12, WHITE);
    display.setTextColor(BLACK); 
    display.setTextSize(1);
    display.setCursor(2, 2); display.print("ENTROPY NODE");
    display.setCursor(88, 2); display.print("P:"); display.print(myData.seq % 1000); 

    // Nội dung chữ Trắng
    display.setTextColor(WHITE);
    display.setCursor(0, 20); display.print("H:");
    display.setTextSize(2); display.setCursor(30, 18); display.print(myData.entropy, 2);
    display.setTextSize(1); display.print(" bits");

    display.drawLine(0, 36, 128, 36, WHITE); 
    display.setCursor(0, 42);
    display.print("SNR: "); display.print(myData.snr, 1); display.print("dB");
    display.setCursor(72, 42);
    display.print("CR: "); display.print(myData.cr, 1); display.print("x");

    // Thanh Gauge đáy
    display.drawRect(0, 54, 128, 10, WHITE);
    int barLen = (int)(myData.entropy * 124.0 / 8.0);
    display.fillRect(2, 56, (barLen > 124 ? 124 : barLen), 6, WHITE);

    display.display();
    delay(50); 
}