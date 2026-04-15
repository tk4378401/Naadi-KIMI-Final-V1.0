# 🩺 आयुर्वेदिक नाड़ी परीक्षण प्रणाली / Ayurvedic Nadi Pariksha System

## English | हिंदी

---

## 📖 System Architecture / प्रणाली वास्तुकला

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AYURVEDIC NADI PARIKSHA ECOSYSTEM                      │
│                      आयुर्वेदिक नाड़ी परीक्षण पारिस्थितिकी तंत्र               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐      TCP Port 5555       ┌──────────────────┐        │
│   │  Data Sources   │  ═══════════════════►  │  Nadi Monitor    │        │
│   │   डेटा स्रोत     │    400-byte packets    │  नाड़ी मॉनिटर      │        │
│   └─────────────────┘                        │  (PyQt6 GUI)     │        │
│          │                                   └──────────────────┘        │
│          │                                          │                     │
│    ┌─────┴─────┬─────────────┬─────────────┐        │                     │
│    │           │             │             │        ▼                     │
│    ▼           ▼             ▼             ▼   ┌─────────┐              │
│ ┌──────┐  ┌────────┐    ┌──────────┐  ┌────────┐ │  Raw    │ Yellow     │
│ │Python│  │ ESP32  │    │  ESP32   │  │  ESP32 │ │Velocity │ Cyan       │
│ │Virtual│  │Virtual │    │ Hardware │  │Hardware│ │Displacement│ Green   │
│ │Generator│ Dummy  │    │ Sensor   │  │Sensor  │ │   VPK    │          │
│ │जनरेटर │  │डमी    │    │  सेंसर   │  │ सेंसर  │ └─────────┘          │
│ └──┬───┘  └──┬────┘    └────┬─────┘  └───┬────┘                           │
│    │         │              │            │                                 │
│    └─────────┴──────────────┴────────────┘                                 │
│                    TCP Client Connections                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔬 Calculus Pipeline Explanation / कैलकुलस पाइपलाइन व्याख्या

The system implements a **Double Integration** DSP chain for Ayurvedic pulse analysis:

**त्वरण → वेग → विस्थापन / Acceleration → Velocity → Displacement**

```
Raw Piezo Signal (Piezoelectric Acceleration)
        │
        ▼
┌─────────────────────────────────────┐
│  Stage 1: Raw Clean                 │
│  High-Pass Filter (0.1 Hz)          │
│  DC drift removal                    │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  Stage 2: Velocity (∫ Raw dt)        │
│  Leaky Integrator (α=0.999)         │
│  + Anchor HPF (0.05 Hz)             │
│  पित्त (Pitta) - Metabolic Flow     │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  Stage 3: Displacement (∬ Raw dt²)   │
│  Leaky Integrator (α=0.999)         │
│  + Anchor HPF (0.05 Hz)             │
│  + Invert (-displacement)           │
│  कफ (Kapha) - Structural Volume   │
└─────────────────────────────────────┘
        │
        ▼
   VPK Morphology Display
   वात-पित्त-कफ आकृति प्रदर्शन
```

### दोष (Dosha) Characteristics / विशेषताएं:

| Dosha | Color | Quality | Frequency | Waveform |
|-------|-------|---------|-----------|----------|
| 🌬 **वात (Vata)** | Yellow/Gold | Light, Irregular, Quick | 60-80 BPM | High variability |
| 🔥 **पित्त (Pitta)** | Cyan | Sharp, Strong, Bounding | 70-80 BPM | High amplitude, sharp |
| 💧 **कफ (Kapha)** | Green | Slow, Steady, Broad | 50-60 BPM | Low frequency, broad |
| ⚖ **संतुलित (Balanced)** | White | Harmonious blend | ~65 BPM | Balanced waveform |

---

## ⚠️ STRICT AYURVEDIC PRINCIPLE: NO FFT, NO BPM

**This system follows traditional Ayurvedic pulse examination methodology:**

- ✅ **Time-Domain Analysis Only** - केवल समय-डोमेन विश्लेषण
- ✅ **VPK Morphology** - वात-पित्त-कफ आकृति का अध्ययन
- ✅ **Gati (Movement Quality)** - गति (गति की गुणवत्ता)
- ✅ **Flow Dynamics** - प्रवाह गतिकी
- ❌ **NO FFT** - No frequency domain analysis
- ❌ **NO BPM** - No Beats Per Minute calculation
- ❌ **NO Western Cardiology** - No allopathic heart metrics

> "The wise physician does not count the pulse, but feels its character."
> 
> *- Charaka Samhita, Sutra Sthana*

---

## 📁 Files / फाइलें

| # | File | Purpose | Description |
|---|------|---------|-------------|
| 1 | `Nadi_DSP.py` | Shared DSP Engine | Pure math signal processing - no UI, no I/O |
| 2 | `Nadi_Monitor.py` | TCP Server + GUI | Medical visualizer with 3 VPK plots |
| 3 | `Nadi_Generator.py` | TCP Client + GUI | Virtual sensor with Dosha buttons |
| 4 | `src/virtual_dummy.cpp` | ESP32 Firmware | Virtual emulator for testing |
| 5 | `src/hardware_main.cpp` | ESP32 Firmware | Real piezo sensor reader |
| 6 | `platformio.ini` | Build Config | Two environments: `[env:virtual]` and `[env:hardware]` |
| 7 | `requirements.txt` | Python Deps | numpy, scipy, PyQt6, pyqtgraph, pyinstaller |
| 8 | `README.md` | Documentation | This file |
| 9 | `.github/workflows/build.yml` | CI/CD | Automated EXE and firmware builds |

---

## 🚀 Quick Start / त्वरित शुरुआत

### Python Components

```bash
# 1. Install dependencies / निर्भरताएं स्थापित करें
pip install -r requirements.txt

# 2. Start the Monitor (Server) first / पहले मॉनिटर (सर्वर) शुरू करें
python Nadi_Monitor.py

# 3. Start the Generator (Client) / जनरेटर (क्लाइंट) शुरू करें
python Nadi_Generator.py
# OR: Connect ESP32 hardware / या: ESP32 हार्डवेयर कनेक्ट करें
```

### Building Standalone EXEs / स्टैंडअलोन EXE बनाना

```bash
# Build NadiMonitor.exe
pyinstaller --onefile --windowed --name NadiMonitor Nadi_Monitor.py

# Build NadiGenerator.exe
pyinstaller --onefile --windowed --name NadiGenerator Nadi_Generator.py
```

---

## 🔌 ESP32 Firmware Flashing / ESP32 फर्मवेयर फ्लैशिंग

### Prerequisites / पूर्वापेक्षाएं:
1. Install [PlatformIO Core](https://platformio.org/install/cli) or VS Code + PlatformIO extension
2. ESP32 development board (ESP32-DevKitC or similar)
3. USB cable

### Flashing Instructions / फ्लैशिंग निर्देश:

```bash
# 1. Clone/navigate to project directory
# परियोजना निर्देशिका में नेविगेट करें

# 2. Flash VIRTUAL firmware (simulated sensor)
# वर्चुअल फर्मवेयर फ्लैश करें (अनुकरण सेंसर)
pio run -e virtual --target upload

# OR: Flash HARDWARE firmware (real piezo sensor)
# या: हार्डवेयर फर्मवेयर फ्लैश करें (वास्तविक पाइज़ो सेंसर)
pio run -e hardware --target upload

# 3. Monitor serial output
# सीरियल आउटपुट मॉनिटर करें
pio device monitor --baud 115200
```

### Hardware Wiring (for hardware_main.cpp) / हार्डवेयर वायरिंग:

```
Piezo Sensor        ESP32
┌─────────┐        ┌──────────┐
│  RED    │───────►│ 3.3V     │
│  BLACK  │───────►│ GND      │
│  SIGNAL │───────►│ GPIO34   │ (ADC1_CH6)
└─────────┘        └──────────┘

Optional: 100kΩ resistor between SIGNAL and GND for stability
वैकल्पिक: स्थिरता के लिए SIGNAL और GND के बीच 100kΩ प्रतिरोधक
```

### WiFi Configuration / WiFi कॉन्फिगरेशन:

Update these lines in both `.cpp` files before flashing:

```cpp
const char* ssid = "YOUR_WIFI_SSID";         // आपका WiFi नाम
const char* password = "YOUR_WIFI_PASSWORD";  // आपका WiFi पासवर्ड
const char* monitor_ip = "192.168.1.100";     // मॉनिटर PC का IP
```

---

## 📊 Data Protocol / डेटा प्रोटोकॉल

All TCP clients use this exact packet structure:

```
┌─────────────────┬────────────────────────────────────────────────────────┐
│ 4 bytes Header  │ 400 bytes Payload                                      │
│ Little-Endian   │ 50 × float64 (8 bytes each)                           │
│ uint32 length   │ Raw acceleration samples at 1000Hz                    │
│ (value = 400)   │ 50 samples = 50ms of data                             │
└─────────────────┴────────────────────────────────────────────────────────┘
```

**Python struct format:** `'<I'` (header) + `'<50d'` (payload)
**C++ equivalent:** `uint32_t` header + `double samples[50]` payload

---

## 🔧 Troubleshooting / समस्या निवारण

| Problem / समस्या | Solution / समाधान |
|-----------------|-------------------|
| Connection refused | Ensure Monitor is running before Generator/ESP32 |
| कनेक्शन अस्वीकृत | Verify `monitor_ip` matches your PC's IP address |
| Flat line on plots | Check DSP state initialization in `Nadi_DSP.py` |
| प्लॉट पर सपाट रेखा | Verify TCP packet format (4-byte header + 400 bytes) |
| Stuttering display | Check UI timer is 40ms and drains queue fully |
| प्रदर्शन रुक-रुक कर | Verify `enableAutoRange('y', True)` on all plots |
| ESP32 upload fails | Hold BOOT button while clicking RESET, then upload |
| Sawtooth waveform | Ensure phase is NEVER reset in batch loop |
| आरी आकृति तरंग | Use `phase += freq * dt` continuously |

---

## 🏥 Medical Disclaimer / चिकित्सा अस्वीकरण

**This system is for educational and research purposes only.**

**यह प्रणाली केवल शैक्षिक और अनुसंधान उद्देश्यों के लिए है।**

- Not FDA approved / FDA द्वारा अनुमोदित नहीं
- Not a medical device / एक चिकित्सा उपकरण नहीं
- Consult qualified Ayurvedic practitioner / योग्य आयुर्वेदिक चिकित्सक से परामर्श करें
- Do not use for diagnosis / निदान के लिए उपयोग न करें

---

## 📜 License / लाइसेंस

MIT License - See individual files for details.

---

## 🙏 Acknowledgments / स्वीकृतियां

- **Charaka Samhita** - The foundational text of Ayurveda
- **Sushruta Samhita** - Surgical and diagnostic techniques
- **Ashtanga Hridayam** - Comprehensive Ayurvedic manual

**ॐ शांति: शांति: शांति:**

*Om Shanti Shanti Shanti - Peace to body, mind, and spirit.*

---

## 📞 Support / सहायता

For technical issues, please check:
1. GitHub Issues tab
2. ESP32 serial monitor output (`pio device monitor`)
3. Python console error messages

**वसुधैव कुटुम्बकम्** - *The world is one family.*
