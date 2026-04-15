# File: Nadi_Generator.py
# Ayurvedic Nadi Pariksha - Python Virtual Sensor / TCP Client
# नाड़ी परीक्षण - पायथन वर्चुअल सेंसर / TCP क्लाइंट
# PyQt6 GUI with Dosha Buttons - NO CLI

import sys
import socket
import struct
import threading
import time
import numpy as np
from PyQt6 import QtWidgets, QtCore

# TCP Configuration
MONITOR_IP = "127.0.0.1"  # Default to localhost
MONITOR_PORT = 5555

# Sampling Configuration
FS = 1000.0  # 1000 Hz sampling rate
DT = 1.0 / FS
SAMPLES_PER_BATCH = 50
BATCH_INTERVAL_MS = 50  # 50ms = 50 samples at 1000Hz

# Dosha Waveform Parameters
# दोष तरंगform पैरामीटर
DOSHA_PARAMS = {
    'vata': {      # 🌬 वात - Irregular, light, quick (60-80 BPM)
        'base_freq': 1.17,  # ~70 BPM
        'amplitude': 1.0,
        'variability': 0.3,  # High variability
        'pulse_width': 0.15,
        'harmonics': [0.3, 0.1]
    },
    'pitta': {     # 🔥 पित्त - Sharp, strong, bounding (70-80 BPM)
        'base_freq': 1.25,  # ~75 BPM
        'amplitude': 1.5,
        'variability': 0.1,
        'pulse_width': 0.12,
        'harmonics': [0.4, 0.2, 0.1]
    },
    'kapha': {     # 💧 कफ - Slow, steady, broad (50-60 BPM)
        'base_freq': 0.92,  # ~55 BPM
        'amplitude': 2.0,
        'variability': 0.05,
        'pulse_width': 0.25,
        'harmonics': [0.5, 0.3]
    },
    'balanced': {  # ⚖ संतुलित - Harmonious blend
        'base_freq': 1.08,  # ~65 BPM
        'amplitude': 1.3,
        'variability': 0.08,
        'pulse_width': 0.18,
        'harmonics': [0.35, 0.15, 0.05]
    }
}


def generate_gaussian_pulse(t, center, width, amplitude):
    """
    Generate a Gaussian pulse for waveform synthesis.
    तरंग संश्लेषण के लिए गॉसियन पल्स जनरेट करें।
    """
    return amplitude * np.exp(-((t - center) ** 2) / (2 * width ** 2))


def generate_waveform(phase, dosha_type='balanced'):
    """
    Generate multi-Gaussian Ayurvedic pulse waveform.
    मल्टी-गॉसियन आयुर्वेदिक पल्स तरंगform जनरेट करें।
    
    Continuous Time (Sawtooth Bug Fix):
    - Uses phase continuously without resetting
    - beat_phase = phase % 1.0 for single-cycle calculation
    """
    params = DOSHA_PARAMS[dosha_type]
    
    # Continuous time - beat_phase is ONLY used for calculation, not stored
    # निरंतर समय - केवल गणना के लिए beat_phase का उपयोग करें
    beat_phase = phase % 1.0  # Normalize to 0-1 within single beat
    
    # Base pulse (primary wave)
    waveform = generate_gaussian_pulse(
        beat_phase, 
        0.5, 
        params['pulse_width'], 
        params['amplitude']
    )
    
    # Add harmonics for dosha character
    # दोष चरित्र के लिए हार्मोनिक्स जोड़ें
    for i, harmonic_amp in enumerate(params['harmonics']):
        harmonic_phase = (beat_phase * (i + 2)) % 1.0
        waveform += generate_gaussian_pulse(
            harmonic_phase,
            0.5,
            params['pulse_width'] * 0.5,
            params['amplitude'] * harmonic_amp
        )
    
    # Add variability for vata-like irregularity
    if params['variability'] > 0:
        noise = np.random.normal(0, params['variability'] * 0.1)
        waveform += noise
    
    return waveform


class StatusSignal(QtCore.QObject):
    """Thread-safe signal for updating GUI status."""
    status_update = QtCore.pyqtSignal(str)


class GeneratorThread(threading.Thread):
    """
    Background thread for continuous waveform generation and TCP transmission.
    निरंतर तरंगform जनरेशन और TCP ट्रांसमिशन के लिए पृष्ठभूमि थ्रेड।
    """
    def __init__(self, status_signal, get_dosha_func, get_running_func):
        super().__init__(daemon=True)
        self.status_signal = status_signal
        self.get_dosha = get_dosha_func
        self.get_running = get_running_func
        self.sock = None
        
        # Continuous Time: Track absolute phase across batches
        # निरंतर समय: बैचों में निरपेक्ष फेज़ ट्रैक करें
        self.phase = 0.0
        
    def run(self):
        """Main generator loop with auto-reconnect."""
        while self.get_running():
            try:
                # Attempt connection
                self.status_signal.status_update.emit(
                    f"🟡 {MONITOR_IP}:{MONITOR_PORT} से कनेक्ट कर रहा है... / Connecting..."
                )
                
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(5)
                self.sock.connect((MONITOR_IP, MONITOR_PORT))
                self.sock.settimeout(None)
                
                self.status_signal.status_update.emit(
                    "🟢 मॉनिटर से कनेक्टेड / Connected to Monitor - भेजना शुरू / Sending..."
                )
                
                # Get current dosha parameters
                dosha_type = self.get_dosha()
                params = DOSHA_PARAMS[dosha_type]
                
                while self.get_running():
                    # Generate 50 samples at 1000Hz
                    # 1000Hz पर 50 नमूने जनरेट करें
                    batch = np.zeros(SAMPLES_PER_BATCH, dtype=np.float64)
                    
                    for i in range(SAMPLES_PER_BATCH):
                        # CRITICAL: Continuous time - increment phase, NEVER reset
                        # महत्वपूर्ण: निरंतर समय - फेज़ बढ़ाएं, कभी रीसेट न करें
                        self.phase += params['base_freq'] * DT
                        
                        batch[i] = generate_waveform(self.phase, dosha_type)
                    
                    # TCP Data Format: 4-byte length + 400-byte payload
                    # TCP डेटा प्रारूप: 4-बाइट लंबाई + 400-बाइट पेलोड
                    payload = struct.pack('<50d', *batch)
                    header = struct.pack('<I', len(payload))
                    
                    self.sock.sendall(header + payload)
                    
                    # 50ms delay for 50 samples at 1000Hz
                    time.sleep(BATCH_INTERVAL_MS / 1000.0)
                    
                    # Check if dosha changed
                    new_dosha = self.get_dosha()
                    if new_dosha != dosha_type:
                        dosha_type = new_dosha
                        params = DOSHA_PARAMS[dosha_type]
                        self.status_signal.status_update.emit(
                            f"🔄 दोष बदला: {dosha_type.upper()} / Dosha changed: {dosha_type.upper()}"
                        )
                        
            except ConnectionRefusedError:
                self.status_signal.status_update.emit(
                    "🔴 मॉनिटर ऑफलाइन - पुनः प्रयास... / Monitor offline - Retrying..."
                )
            except ConnectionResetError:
                self.status_signal.status_update.emit(
                    "🔴 कनेक्शन रीसेट - पुनः कनेक्टिंग... / Connection reset - Reconnecting..."
                )
            except Exception as e:
                self.status_signal.status_update.emit(f"❌ त्रुटि: {str(e)} / Error: {str(e)}")
            finally:
                if self.sock:
                    try:
                        self.sock.close()
                    except:
                        pass
                    self.sock = None
            
            # Robust TCP: Auto-reconnect delay
            # मजबूत TCP: ऑटो-रीकनेक्ट विलंब
            if self.get_running():
                time.sleep(2)


class NadiGenerator(QtWidgets.QMainWindow):
    """
    Main Generator GUI with Dosha selection buttons.
    दोष चयन बटनों के साथ मुख्य जनरेटर GUI।
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎛️ नाड़ी जनरेटर / Nadi Generator - वर्चुअल सेंसर / Virtual Sensor")
        self.setGeometry(150, 150, 600, 500)
        
        self.current_dosha = 'balanced'
        self.running = True
        
        # Status signal for thread-safe updates
        self.status_signal = StatusSignal()
        self.status_signal.status_update.connect(self.update_status)
        
        self.setup_ui()
        
        # Start generator thread
        self.gen_thread = GeneratorThread(
            self.status_signal,
            lambda: self.current_dosha,
            lambda: self.running
        )
        self.gen_thread.start()
        
    def setup_ui(self):
        """Setup the dark-themed GUI with large dosha buttons."""
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        
        # Title
        title = QtWidgets.QLabel("🩺 आयुर्वेदिक नाड़ी जनरेटर / Ayurvedic Nadi Generator")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFD700;")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Subtitle
        subtitle = QtWidgets.QLabel("वर्चुअल पल्स सेंसर - त्रिदोष विश्लेषण / Virtual Pulse Sensor - Tridosha Analysis")
        subtitle.setStyleSheet("font-size: 12px; color: #888888;")
        subtitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        
        # Status label
        self.status_label = QtWidgets.QLabel("🟡 प्रारंभ हो रहा है... / Initializing...")
        self.status_label.setStyleSheet("font-size: 14px; color: #FFA500; padding: 10px;")
        self.status_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Dosha selection buttons frame
        buttons_frame = QtWidgets.QFrame()
        buttons_layout = QtWidgets.QVBoxLayout(buttons_frame)
        buttons_layout.setSpacing(15)
        
        # Button style template
        button_style = """
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                padding: 20px;
                border-radius: 10px;
                min-height: 60px;
            }
        """
        
        # 🌬 वात (Vata) - Yellow/Gold
        self.btn_vata = QtWidgets.QPushButton("🌬 वात (Vata)")
        self.btn_vata.setStyleSheet(button_style + """
            QPushButton {
                background-color: #4a4a00;
                color: #FFD700;
                border: 3px solid #FFD700;
            }
            QPushButton:hover {
                background-color: #5a5a10;
            }
            QPushButton:pressed {
                background-color: #FFD700;
                color: #1a1a2e;
            }
        """)
        self.btn_vata.clicked.connect(lambda: self.set_dosha('vata'))
        buttons_layout.addWidget(self.btn_vata)
        
        # 🔥 पित्त (Pitta) - Cyan
        self.btn_pitta = QtWidgets.QPushButton("🔥 पित्त (Pitta)")
        self.btn_pitta.setStyleSheet(button_style + """
            QPushButton {
                background-color: #004a4a;
                color: #00CED1;
                border: 3px solid #00CED1;
            }
            QPushButton:hover {
                background-color: #105a5a;
            }
            QPushButton:pressed {
                background-color: #00CED1;
                color: #1a1a2e;
            }
        """)
        self.btn_pitta.clicked.connect(lambda: self.set_dosha('pitta'))
        buttons_layout.addWidget(self.btn_pitta)
        
        # 💧 कफ (Kapha) - Green
        self.btn_kapha = QtWidgets.QPushButton("💧 कफ (Kapha)")
        self.btn_kapha.setStyleSheet(button_style + """
            QPushButton {
                background-color: #004a00;
                color: #32CD32;
                border: 3px solid #32CD32;
            }
            QPushButton:hover {
                background-color: #105a10;
            }
            QPushButton:pressed {
                background-color: #32CD32;
                color: #1a1a2e;
            }
        """)
        self.btn_kapha.clicked.connect(lambda: self.set_dosha('kapha'))
        buttons_layout.addWidget(self.btn_kapha)
        
        # ⚖ संतुलित (Balanced) - White/Purple
        self.btn_balanced = QtWidgets.QPushButton("⚖ संतुलित (Balanced)")
        self.btn_balanced.setStyleSheet(button_style + """
            QPushButton {
                background-color: #4a004a;
                color: #E0E0E0;
                border: 3px solid #E0E0E0;
            }
            QPushButton:hover {
                background-color: #5a105a;
            }
            QPushButton:pressed {
                background-color: #E0E0E0;
                color: #1a1a2e;
            }
        """)
        self.btn_balanced.clicked.connect(lambda: self.set_dosha('balanced'))
        buttons_layout.addWidget(self.btn_balanced)
        
        layout.addWidget(buttons_frame)
        
        # Current selection indicator
        self.selection_label = QtWidgets.QLabel("✅ वर्तमान: संतुलित / Current: Balanced")
        self.selection_label.setStyleSheet("font-size: 16px; color: #32CD32; font-weight: bold;")
        self.selection_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.selection_label)
        
        # Dosha descriptions
        desc_text = QtWidgets.QLabel(
            "🌬 वात = तेज़, अनियमित / Fast, Irregular | "
            "🔥 पित्त = तेज़, मज़बूत / Fast, Strong | "
            "💧 कफ = धीमा, स्थिर / Slow, Steady | "
            "⚖ संतुलित = सामंजस्य / Harmonious"
        )
        desc_text.setStyleSheet("font-size: 11px; color: #888888;")
        desc_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        desc_text.setWordWrap(True)
        layout.addWidget(desc_text)
        
        # Info section
        info_frame = QtWidgets.QFrame()
        info_layout = QtWidgets.QVBoxLayout(info_frame)
        
        ip_label = QtWidgets.QLabel(f"📡 मॉनिटर IP: {MONITOR_IP} | पोर्ट: {MONITOR_PORT}")
        ip_label.setStyleSheet("color: #00CED1; font-size: 12px;")
        info_layout.addWidget(ip_label)
        
        rate_label = QtWidgets.QLabel(f"📊 सैंपल दर: {FS} Hz | बैच आकार: {SAMPLES_PER_BATCH} samples")
        rate_label.setStyleSheet("color: #00CED1; font-size: 12px;")
        info_layout.addWidget(rate_label)
        
        layout.addWidget(info_frame)
        layout.addStretch()
        
    def set_dosha(self, dosha_type):
        """Update the current dosha selection."""
        self.current_dosha = dosha_type
        
        dosha_names = {
            'vata': 'वात (Vata)',
            'pitta': 'पित्त (Pitta)',
            'kapha': 'कफ (Kapha)',
            'balanced': 'संतुलित (Balanced)'
        }
        
        self.selection_label.setText(f"✅ वर्तमान: {dosha_names[dosha_type]} / Current: {dosha_names[dosha_type]}")
        
    def update_status(self, message):
        """Thread-safe status update."""
        self.status_label.setText(message)
        
    def closeEvent(self, event):
        """Clean shutdown."""
        self.running = False
        self.gen_thread.join(timeout=2)
        event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    
    # Dark theme
    app.setStyleSheet("""
        QMainWindow {
            background-color: #1a1a2e;
        }
        QWidget {
            background-color: #16213e;
            color: #ffffff;
        }
        QFrame {
            background-color: #0f3460;
            border-radius: 8px;
        }
        QLabel {
            color: #ffffff;
        }
    """)
    
    window = NadiGenerator()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
