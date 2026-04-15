// File: src/hardware_main.cpp
// Ayurvedic Nadi Pariksha - ESP32 Real Hardware Implementation
// नाड़ी परीक्षण - ESP32 वास्तविक हार्डवेयर कार्यान्वयन
// Reads from piezo sensor via ADC, sends to Monitor via TCP
// पाइज़ो सेंसर से ADC के माध्यम से पढ़ता है, TCP के माध्यम से मॉनिटर को भेजता है

#include <WiFi.h>
#include <esp_timer.h>

// WiFi Configuration - Update with your network credentials
// WiFi कॉन्फिगरेशन - अपने नेटवर्क क्रेडेंशियल्स के साथ अपडेट करें
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Monitor Configuration - Update with your Monitor PC IP
// मॉनिटर कॉन्फिगरेशन - अपने मॉनिटर PC IP के साथ अपडेट करें
const char* monitor_ip = "192.168.1.100";
const uint16_t monitor_port = 5555;

// Hardware Configuration
// हार्डवेयर कॉन्फिगरेशन
const int ADC_PIN = 34;  // GPIO34 (ADC1_CH6) - piezo sensor input
const int ADC_ATTEN = ADC_ATTEN_DB_11;  // 0-3.3V range

// Sampling Configuration
// सैंपलिंग कॉन्फिगरेशन
const int SAMPLES_PER_BATCH = 50;   // 50 samples per TCP packet
const int FS = 1000;                 // 1000 Hz sampling rate
const int SAMPLE_INTERVAL_US = 1000; // 1000 microseconds = 1ms = 1000Hz

// Global objects
WiFiClient client;
esp_timer_handle_t sample_timer;

// Double-buffered sample storage
// डबल-बफर्ड नमूना स्टोरेज
volatile double sample_buffer_a[SAMPLES_PER_BATCH];
volatile double sample_buffer_b[SAMPLES_PER_BATCH];
volatile double* write_buffer = sample_buffer_a;  // Buffer being filled by ISR
volatile double* send_buffer = nullptr;              // Buffer ready to send
volatile int sample_index = 0;
volatile bool buffer_ready = false;

portMUX_TYPE timer_mux = portMUX_INITIALIZER_UNLOCKED;

/**
 * Timer ISR - Called exactly every 1000 microseconds (1000Hz)
 * टाइमर ISR - ठीक हर 1000 माइक्रोसेकंड (1000Hz) पर कहा जाता है
 * 
 * Reads ADC and stores in current buffer
 * ADC पढ़ता है और वर्तमान बफर में स्टोर करता है
 */
void IRAM_ATTR on_sample_timer(void* arg) {
    portENTER_CRITICAL_ISR(&timer_mux);
    
    if (sample_index < SAMPLES_PER_BATCH) {
        // Read ADC (12-bit ADC, 0-4095)
        int raw_adc = analogRead(ADC_PIN);
        
        // Convert to double and normalize (center around 0)
        // डबल में कनवर्ट करें और सामान्यीकृत करें (0 के चारों ओर केंद्र)
        write_buffer[sample_index] = (raw_adc - 2048.0) / 2048.0;
        
        sample_index++;
        
        // Check if buffer is full
        if (sample_index >= SAMPLES_PER_BATCH) {
            // Swap buffers
            send_buffer = write_buffer;
            write_buffer = (write_buffer == sample_buffer_a) ? sample_buffer_b : sample_buffer_a;
            sample_index = 0;
            buffer_ready = true;
        }
    }
    
    portEXIT_CRITICAL_ISR(&timer_mux);
}

/**
 * Setup the high-precision sampling timer
 * उच्च-सटीकता सैंपलिंग टाइमर सेटअप करें
 */
void setup_sampling_timer() {
    const esp_timer_create_args_t timer_args = {
        .callback = &on_sample_timer,
        .arg = nullptr,
        .dispatch_method = ESP_TIMER_TASK,
        .name = "nadi_sampler",
        .skip_unhandled_events = false
    };
    
    ESP_ERROR_CHECK(esp_timer_create(&timer_args, &sample_timer));
    
    // Start timer with 1000us (1ms) period = 1000Hz
    ESP_ERROR_CHECK(esp_timer_start_periodic(sample_timer, SAMPLE_INTERVAL_US));
    
    Serial.println("⏱️ सैंपलिंग टाइमर शुरू / Sampling timer started: 1000Hz");
}

/**
 * Connect to WiFi
 * WiFi से कनेक्ट करें
 */
void connect_wifi() {
    Serial.println("WiFi से कनेक्ट कर रहा है... / Connecting to WiFi...");
    WiFi.begin(ssid, password);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("\n❌ WiFi कनेक्शन विफल / WiFi connection failed - रीबूट / Rebooting...");
        ESP.restart();
    }
    
    Serial.println();
    Serial.print("✅ WiFi कनेक्टेड! IP: / WiFi Connected! IP: ");
    Serial.println(WiFi.localIP());
}

/**
 * Connect to Monitor TCP Server with auto-retry
 * ऑटो-रीट्राई के साथ मॉनिटर TCP सर्वर से कनेक्ट करें
 */
bool connect_monitor() {
    Serial.print("📡 मॉनिटर से कनेक्ट कर रहा है / Connecting to Monitor: ");
    Serial.print(monitor_ip);
    Serial.print(":");
    Serial.println(monitor_port);
    
    if (!client.connect(monitor_ip, monitor_port)) {
        Serial.println("❌ कनेक्शन विफल / Connection failed");
        return false;
    }
    
    Serial.println("🟢 मॉनिटर से कनेक्टेड! / Connected to Monitor!");
    return true;
}

/**
 * Send buffer to monitor via TCP
 * TCP के माध्यम से मॉनिटर को बफर भेजें
 * 
 * Protocol: 4-byte little-endian length + 400-byte payload
 * प्रोटोकॉल: 4-बाइट लिटिल-एंडियन लंबाई + 400-बाइट पेलोड
 */
void send_buffer_to_monitor() {
    if (send_buffer == nullptr) return;
    
    // Copy from volatile buffer
    double samples[SAMPLES_PER_BATCH];
    for (int i = 0; i < SAMPLES_PER_BATCH; i++) {
        samples[i] = send_buffer[i];
    }
    
    uint32_t payload_size = SAMPLES_PER_BATCH * sizeof(double);  // 400 bytes
    
    // Send length header (little-endian)
    client.write((uint8_t*)&payload_size, 4);
    
    // Send payload
    client.write((uint8_t*)samples, payload_size);
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println("========================================");
    Serial.println("🩺 आयुर्वेदिक नाड़ी परीक्षण - ESP32 हार्डवेयर");
    Serial.println("   Ayurvedic Nadi Pariksha - ESP32 Hardware");
    Serial.println("========================================");
    
    // Setup ADC
    // ADC सेटअप करें
    analogSetAttenuation(ADC_ATTEN);
    analogReadResolution(12);  // 12-bit resolution (0-4095)
    pinMode(ADC_PIN, INPUT);
    
    Serial.print("📊 ADC पिन / ADC Pin: GPIO");
    Serial.println(ADC_PIN);
    Serial.println("   तयार / Ready...");
    
    // Connect to WiFi
    connect_wifi();
    
    // Setup high-precision timer
    setup_sampling_timer();
    
    Serial.println("========================================");
    Serial.println("🟢 सिस्टम सक्रिय / System Active");
    Serial.println("   नाड़ी सेंसर से डेटा प्राप्त कर रहा है...");
    Serial.println("   Receiving data from Nadi sensor...");
    Serial.println("========================================");
}

void loop() {
    // Robust TCP: Check connection and auto-reconnect
    // मजबूत TCP: कनेक्शन जांचें और ऑटो-रीकनेक्ट करें
    if (!client.connected()) {
        Serial.println("🔴 मॉनिटर से डिस्कनेक्टेड / Disconnected from Monitor");
        client.stop();
        
        // Retry with delay
        while (!connect_monitor()) {
            delay(2000);  // 2 second retry
        }
    }
    
    // Check if buffer is ready to send
    // जांचें कि क्या बफर भेजने के लिए तैयार है
    if (buffer_ready) {
        portENTER_CRITICAL(&timer_mux);
        buffer_ready = false;
        portEXIT_CRITICAL(&timer_mux);
        
        send_buffer_to_monitor();
    }
    
    // Small delay to prevent watchdog issues
    delay(1);
}
