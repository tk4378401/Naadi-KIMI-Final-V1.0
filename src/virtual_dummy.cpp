// File: src/virtual_dummy.cpp
// Ayurvedic Nadi Pariksha - ESP32 Virtual/Dummy Emulator
// नाड़ी परीक्षण - ESP32 वर्चुअल/डमी एमुलेटर
// TCP Client sending synthetic pulse data to Monitor
// मॉनिटर को सिंथेटिक पल्स डेटा भेजने वाला TCP क्लाइंट

#include <WiFi.h>
#include <math.h>

// WiFi Configuration - Update these with your network credentials
// WiFi कॉन्फिगरेशन - इन्हें अपने नेटवर्क क्रेडेंशियल्स के साथ अपडेट करें
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Monitor Configuration
// मॉनिटर कॉन्फिगरेशन
const char* monitor_ip = "192.168.1.100";  // Update with your Monitor PC IP
const uint16_t monitor_port = 5555;

// Sampling Configuration
// सैंपलिंग कॉन्फिगरेशन
const double FS = 1000.0;           // 1000 Hz sampling rate
const double DT = 1.0 / FS;         // 1ms interval
const int SAMPLES_PER_BATCH = 50;   // 50 samples per packet
const int BATCH_DELAY_MS = 50;        // 50ms delay between batches

// Dosha Waveform Parameters (matching Python Generator)
// दोष तरंगform पैरामीटर (पायथन जनरेटर से मिलान)
struct DoshaParams {
    double base_freq;
    double amplitude;
    double pulse_width;
};

const DoshaParams DOSHA_BALANCED = {1.08, 1.3, 0.18};   // ⚖ संतुलित
const DoshaParams DOSHA_VATA = {1.17, 1.0, 0.15};     // 🌬 वात
const DoshaParams DOSHA_PITTA = {1.25, 1.5, 0.12};    // 🔥 पित्त
const DoshaParams DOSHA_KAPHA = {0.92, 2.0, 0.25};    // 💧 कफ

// Global state
WiFiClient client;

// Continuous Time: Absolute phase tracked across all batches
// निरंतर समय: सभी बैचों में निरपेक्ष फेज़ ट्रैक किया गया
double global_phase = 0.0;

// Current dosha selection (can be changed via Serial commands)
// वर्तमान दोष चयन (सीरियल कमांड के माध्यम से बदला जा सकता है)
int current_dosha = 0;  // 0=balanced, 1=vata, 2=pitta, 3=kapha

/**
 * Generate Gaussian pulse
 * गॉसियन पल्स जनरेट करें
 */
double gaussian_pulse(double t, double center, double width, double amplitude) {
    double diff = t - center;
    return amplitude * exp(-(diff * diff) / (2.0 * width * width));
}

/**
 * Generate waveform sample using continuous phase
 * निरंतर फेज़ का उपयोग करके तरंगform नमूना जनरेट करें
 * 
 * CRITICAL: Uses fmod(phase, 1.0) ONLY for calculation, never resets phase
 * महत्वपूर्ण: केवल गणना के लिए fmod(phase, 1.0) का उपयोग करें, फेज़ कभी रीसेट न करें
 */
double generate_sample(double phase, const DoshaParams& params) {
    // beat_phase is ONLY used for calculation within the beat
    // beat_phase का उपयोग केवल बीट के भीतर गणना के लिए किया जाता है
    double beat_phase = fmod(phase, 1.0);
    
    // Primary pulse
    double waveform = gaussian_pulse(beat_phase, 0.5, params.pulse_width, params.amplitude);
    
    // Add harmonic for character (2nd harmonic)
    double harmonic_phase = fmod(beat_phase * 2.0, 1.0);
    waveform += gaussian_pulse(harmonic_phase, 0.5, params.pulse_width * 0.5, 
                                params.amplitude * 0.3);
    
    // Add small noise for realism
    waveform += (random(-100, 100) / 1000.0) * 0.05;
    
    return waveform;
}

/**
 * Get current dosha parameters
 * वर्तमान दोष पैरामीटर प्राप्त करें
 */
DoshaParams get_current_params() {
    switch(current_dosha) {
        case 1: return DOSHA_VATA;
        case 2: return DOSHA_PITTA;
        case 3: return DOSHA_KAPHA;
        default: return DOSHA_BALANCED;
    }
}

/**
 * Connect to WiFi
 * WiFi से कनेक्ट करें
 */
void connect_wifi() {
    Serial.println("WiFi से कनेक्ट कर रहा है... / Connecting to WiFi...");
    WiFi.begin(ssid, password);
    
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    
    Serial.println();
    Serial.print("✅ WiFi कनेक्टेड! IP: / WiFi Connected! IP: ");
    Serial.println(WiFi.localIP());
}

/**
 * Connect to Monitor with auto-retry
 * ऑटो-रीट्राई के साथ मॉनिटर से कनेक्ट करें
 */
bool connect_monitor() {
    Serial.print("📡 मॉनिटर से कनेक्ट कर रहा है / Connecting to Monitor: ");
    Serial.print(monitor_ip);
    Serial.print(":");
    Serial.println(monitor_port);
    
    if (!client.connect(monitor_ip, monitor_port)) {
        Serial.println("❌ कनेक्शन विफल / Connection failed - पुनः प्रयास / Retrying...");
        return false;
    }
    
    Serial.println("🟢 मॉनिटर से कनेक्टेड! / Connected to Monitor!");
    return true;
}

/**
 * Send batch of samples to monitor
 * मॉनिटर को नमूनों का बैच भेजें
 */
void send_batch() {
    double samples[SAMPLES_PER_BATCH];
    DoshaParams params = get_current_params();
    
    // Generate 50 samples
    // 50 नमूने जनरेट करें
    for (int i = 0; i < SAMPLES_PER_BATCH; i++) {
        // CRITICAL: Continuous time - increment phase, NEVER reset
        // महत्वपूर्ण: निरंतर समय - फेज़ बढ़ाएं, कभी रीसेट न करें
        global_phase += params.base_freq * DT;
        
        samples[i] = generate_sample(global_phase, params);
    }
    
    // TCP Protocol: 4-byte length header + 400-byte payload
    // TCP प्रोटोकॉल: 4-बाइट लंबाई हेडर + 400-बाइट पेलोड
    uint32_t payload_size = SAMPLES_PER_BATCH * sizeof(double);  // 400 bytes
    
    // Send length header (little-endian)
    client.write((uint8_t*)&payload_size, 4);
    
    // Send payload (400 bytes of double array)
    client.write((uint8_t*)samples, payload_size);
}

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println("========================================");
    Serial.println("🩺 आयुर्वेदिक नाड़ी परीक्षण - ESP32 वर्चुअल एमुलेटर");
    Serial.println("   Ayurvedic Nadi Pariksha - ESP32 Virtual Emulator");
    Serial.println("========================================");
    
    randomSeed(analogRead(0));
    
    connect_wifi();
    
    Serial.println("📝 सीरियल कमांड / Serial Commands:");
    Serial.println("   0 = संतुलित / Balanced");
    Serial.println("   1 = वात / Vata");
    Serial.println("   2 = पित्त / Pitta");
    Serial.println("   3 = कफ / Kapha");
}

void loop() {
    // Check for dosha change commands via Serial
    if (Serial.available()) {
        char cmd = Serial.read();
        if (cmd >= '0' && cmd <= '3') {
            current_dosha = cmd - '0';
            const char* names[] = {"संतुलित/Balanced", "वात/Vata", "पित्त/Pitta", "कफ/Kapha"};
            Serial.print("🔄 दोष बदला: / Dosha changed: ");
            Serial.println(names[current_dosha]);
        }
    }
    
    // Robust TCP: Auto-reconnect loop
    // मजबूत TCP: ऑटो-रीकनेक्ट लूप
    if (!client.connected()) {
        Serial.println("🔴 मॉनिटर से डिस्कनेक्टेड / Disconnected from Monitor");
        client.stop();
        
        // Retry connection with delay
        while (!connect_monitor()) {
            delay(2000);  // 2 second retry interval
        }
    }
    
    // Send batch of samples
    send_batch();
    
    // 50ms delay for 1000Hz / 50 samples
    delay(BATCH_DELAY_MS);
}
