#define CONTROL_PIN 4  // GPIO10 사용 (원하는 핀으로 변경 가능)

// Shutter time 관련 변수들
unsigned long shutterOpenTime = 1000;  // 기본값: 1초 (밀리초 단위로 저장)
bool isShutterTimeRunning = false;
unsigned long shutterStartTime = 0;

void setup() {
  Serial.begin(115200);         // 시리얼 통신 시작
  pinMode(CONTROL_PIN, OUTPUT); // 핀을 출력으로 설정
  digitalWrite(CONTROL_PIN, LOW); // 초기 상태는 LOW (0 = close)
  Serial.println("Shutter Control Ready");
  Serial.println("Commands: 0=open, 1=close, t,time=shutter time (seconds)");
}

void loop() {
  // Shutter time 기능 처리
  if (isShutterTimeRunning) {
    if (millis() - shutterStartTime >= shutterOpenTime) {
      digitalWrite(CONTROL_PIN, LOW);  // 시간이 지나면 close (0)
      Serial.println("Shutter closed automatically");
      isShutterTimeRunning = false;
    }
  }

  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();  // 앞뒤 공백 제거
    
    if (input == "0") {
      digitalWrite(CONTROL_PIN, HIGH);   // HIGH 출력 (open)
      Serial.println("Output: HIGH (3.3V) - Shutter OPEN");
      isShutterTimeRunning = false;  // 수동 제어 시 자동 타이머 중지
    } else if (input == "1") {
      digitalWrite(CONTROL_PIN, LOW);  // LOW 출력 (close)
      Serial.println("Output: LOW (0V) - Shutter CLOSE");
      isShutterTimeRunning = false;  // 수동 제어 시 자동 타이머 중지
    } else if (input.startsWith("t,")) {
      // Shutter time 실행: t,시간 (초)
      if (!isShutterTimeRunning) {
        // 시간 값 추출 (초 단위)
        String timeStr = input.substring(2);  // "t," 이후 부분
        timeStr.trim();
        
        if (timeStr.length() > 0) {
          float timeInSeconds = timeStr.toFloat();
          shutterOpenTime = (unsigned long)(timeInSeconds * 1000);  // 초를 밀리초로 변환
          Serial.println("Shutter time set to: " + String(timeInSeconds) + " seconds (" + String(shutterOpenTime) + "ms)");
        }
        
        digitalWrite(CONTROL_PIN, HIGH);   // open (HIGH)
        Serial.println("Shutter opened, will close in " + String((float)shutterOpenTime/1000) + " seconds");
        shutterStartTime = millis();
        isShutterTimeRunning = true;
      } else {
        Serial.println("Shutter time already running");
      }
    } else {
      Serial.println("Unknown command. Use:");
      Serial.println("  0 = open shutter");
      Serial.println("  1 = close shutter");
      Serial.println("  t,time = shutter time (e.g., t,1.5 for 1.5 seconds)");
    }
  }
} 