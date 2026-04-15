# File: Nadi_Monitor.py
# Ayurvedic Nadi Pariksha - Medical Visualizer & TCP Server
# नाड़ी परीक्षण - मेडिकल विज़ुअलाइज़र और TCP सर्वर
# NO FFT, NO BPM - Strictly Time-Domain VPK Morphology Analysis
# केवल समय-डोमेन VPK आकृति विश्लेषण

import sys
import socket
import struct
import queue
import threading
import time

import numpy as np
from PyQt6 import QtWidgets, QtCore
import pyqtgraph as pg

from Nadi_DSP import process_batch, create_initial_state

# TCP Configuration
TCP_PORT = 5555
SAMPLES_PER_PACKET = 50
BYTES_PER_SAMPLE = 8  # float64
PAYLOAD_SIZE = SAMPLES_PER_PACKET * BYTES_PER_SAMPLE  # 400 bytes

# UI Update Timer Interval (40ms for stutter-free updates)
UI_TIMER_MS = 40


def recvall(sock, n):
    """
    TCP Data Corruption Fix: Receive exactly n bytes from socket.
    TCP डेटा भ्रष्टाचार फिक्स: सॉकेट से ठीक n बाइट प्राप्त करें।
    """
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return bytes(data)


class StatusSignal(QtCore.QObject):
    """
    UI Freeze Fix: Thread-safe signal for updating GUI status labels.
    UI फ्रीज फिक्स: GUI स्थिति लेबल अपडेट करने के लिए थ्रेड-सेफ सिग्नल।
    """
    status_update = QtCore.pyqtSignal(str)


class TCPServerThread(threading.Thread):
    """
    Background TCP server thread that receives pulse data.
    पल्स डेटा प्राप्त करने वाला पृष्ठभूमि TCP सर्वर थ्रेड।
    """
    def __init__(self, data_queue, status_signal):
        super().__init__(daemon=True)
        self.data_queue = data_queue
        self.status_signal = status_signal
        self.running = True
        self.server_socket = None
        
    def run(self):
        """Main server loop with auto-restart capability."""
        while self.running:
            try:
                self.status_signal.status_update.emit("🟡 सर्वर प्रारंभ हो रहा है... / Starting server...")
                
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind(('0.0.0.0', TCP_PORT))
                self.server_socket.listen(1)
                
                self.status_signal.status_update.emit(
                    f"🟢 पोर्ट {TCP_PORT} पर सुन रहा है / Listening on port {TCP_PORT}"
                )
                
                conn, addr = self.server_socket.accept()
                self.status_signal.status_update.emit(f"🔗 कनेक्टेड: {addr[0]} / Connected: {addr[0]}")
                
                with conn:
                    while self.running:
                        # Receive 4-byte length header (little-endian)
                        header = recvall(conn, 4)
                        if header is None:
                            break
                        
                        payload_len = struct.unpack('<I', header)[0]
                        
                        if payload_len != PAYLOAD_SIZE:
                            self.status_signal.status_update.emit(
                                f"⚠️ अमान्य पेलोड आकार: {payload_len} / Invalid payload size: {payload_len}"
                            )
                            continue
                        
                        # Receive exactly 400 bytes of payload
                        payload = recvall(conn, payload_len)
                        if payload is None:
                            break
                        
                        # Unpack 50 float64 samples
                        samples = struct.unpack('<50d', payload)
                        self.data_queue.put(np.array(samples, dtype=np.float64))
                        
            except ConnectionResetError:
                self.status_signal.status_update.emit("🔴 कनेक्शन रीसेट / Connection Reset - पुनः कनेक्टिंग...")
            except Exception as e:
                self.status_signal.status_update.emit(f"❌ त्रुटि: {str(e)} / Error: {str(e)}")
            
            # Robust TCP: Wait before retrying
            if self.running:
                time.sleep(2)
                
        if self.server_socket:
            self.server_socket.close()
            
    def stop(self):
        self.running = False


class NadiMonitor(QtWidgets.QMainWindow):
    """
    Main Monitor GUI window with 3 stacked plots for VPK analysis.
    VPK विश्लेषण के लिए 3 स्टैक्ड प्लॉट्स के साथ मुख्य मॉनिटर GUI विंडो।
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🩺 आयुर्वेदिक नाड़ी परीक्षण मॉनिटर / Ayurvedic Nadi Pariksha Monitor")
        self.setGeometry(100, 100, 1200, 800)
        
        # Data storage (5 seconds at 1000Hz = 5000 samples)
        self.max_samples = 5000
        self.raw_buffer = np.zeros(self.max_samples)
        self.vel_buffer = np.zeros(self.max_samples)
        self.disp_buffer = np.zeros(self.max_samples)
        
        # DSP state
        self.dsp_state = create_initial_state()
        
        # Data queue for thread-safe communication
        self.data_queue = queue.Queue()
        
        # Status signal for UI updates from thread
        self.status_signal = StatusSignal()
        self.status_signal.status_update.connect(self.update_status)
        
        # Setup UI
        self.setup_ui()
        
        # Start TCP server thread
        self.server_thread = TCPServerThread(self.data_queue, self.status_signal)
        self.server_thread.start()
        
        # UI timer for stutter-free updates (drains entire queue)
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.process_queue)
        self.update_timer.start(UI_TIMER_MS)
        
    def setup_ui(self):
        """Setup the dark-themed PyQt6 GUI with 3 stacked plots."""
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)
        
        # Status bar at top
        self.status_label = QtWidgets.QLabel("🟡 प्रारंभ हो रहा है... / Initializing...")
        self.status_label.setStyleSheet("color: #FFA500; font-size: 14px; padding: 5px;")
        layout.addWidget(self.status_label)
        
        # Info labels
        info_frame = QtWidgets.QFrame()
        info_layout = QtWidgets.QHBoxLayout(info_frame)
        
        # Dosha labels with colors
        vata_label = QtWidgets.QLabel("🌬 वात (Vata) - प्रवाह गति / Flow Dynamics")
        vata_label.setStyleSheet("color: #FFD700; font-weight: bold;")
        
        pitta_label = QtWidgets.QLabel("🔥 पित्त (Pitta) - रूपांतरण / Transformation")
        pitta_label.setStyleSheet("color: #00CED1; font-weight: bold;")
        
        kapha_label = QtWidgets.QLabel("💧 कफ (Kapha) - संरचना / Structure")
        kapha_label.setStyleSheet("color: #32CD32; font-weight: bold;")
        
        info_layout.addWidget(vata_label)
        info_layout.addWidget(pitta_label)
        info_layout.addWidget(kapha_label)
        info_layout.addStretch()
        
        # NO FFT/BPM warning label
        no_fft_label = QtWidgets.QLabel("⚠️ NO BPM/NO FFT - केवल VPK समय-डोमेन / Time-Domain VPK Only")
        no_fft_label.setStyleSheet("color: #FF6B6B; font-weight: bold; font-size: 12px;")
        info_layout.addWidget(no_fft_label)
        
        layout.addWidget(info_frame)
        
        # Configure pyqtgraph dark theme
        pg.setConfigOption('background', '#1a1a2e')
        pg.setConfigOption('foreground', '#ffffff')
        
        # Plot 1: Raw Acceleration (Yellow - Vata Flow)
        self.plot_raw = pg.PlotWidget(title="📊 कच्चा त्वरण (Raw Acceleration) - वात गति / Vata Flow")
        self.plot_raw.setLabel('left', 'Amplitude')
        self.plot_raw.setLabel('bottom', 'Time (samples)')
        self.plot_raw.showGrid(x=True, y=True, alpha=0.3)
        self.plot_raw.enableAutoRange('y', True)  # Hidden Wave Fix
        self.curve_raw = self.plot_raw.plot(pen=pg.mkPen(color='#FFD700', width=2))
        layout.addWidget(self.plot_raw)
        
        # Plot 2: Velocity (Cyan - Pitta Transformation)
        self.plot_vel = pg.PlotWidget(title="📈 वेग (Velocity) - पित्त रूपांतरण / Pitta Transformation")
        self.plot_vel.setLabel('left', 'Velocity')
        self.plot_vel.setLabel('bottom', 'Time (samples)')
        self.plot_vel.showGrid(x=True, y=True, alpha=0.3)
        self.plot_vel.enableAutoRange('y', True)  # Hidden Wave Fix
        self.curve_vel = self.plot_vel.plot(pen=pg.mkPen(color='#00CED1', width=2))
        layout.addWidget(self.plot_vel)
        
        # Plot 3: Displacement (Green - Kapha Structure)
        self.plot_disp = pg.PlotWidget(title="📉 विस्थापन (Displacement) - कफ संरचना / Kapha Structure (VPK Morphology)")
        self.plot_disp.setLabel('left', 'Displacement')
        self.plot_disp.setLabel('bottom', 'Time (samples)')
        self.plot_disp.showGrid(x=True, y=True, alpha=0.3)
        self.plot_disp.enableAutoRange('y', True)  # Hidden Wave Fix
        self.curve_disp = self.plot_disp.plot(pen=pg.mkPen(color='#32CD32', width=2))
        layout.addWidget(self.plot_disp)
        
        # Legend/Help text at bottom
        help_text = QtWidgets.QLabel(
            "🔹 पीला (Yellow) = त्वरण/Acceleration | 🔹 सियान (Cyan) = वेग/Velocity | 🔹 हरा (Green) = विस्थापन/Displacement | "
            "कैलकुलस: ∫∫ त्वरण → वेग → विस्थापन / Calculus: ∫∫ Acceleration → Velocity → Displacement"
        )
        help_text.setStyleSheet("color: #888888; font-size: 11px; padding: 5px;")
        layout.addWidget(help_text)
        
    def update_status(self, message):
        """Thread-safe status label update via pyqtSignal."""
        self.status_label.setText(message)
        
    def process_queue(self):
        """
        Stutter Fix: Drain entire queue in a while loop (40ms timer).
        स्टटर फिक्स: व्हाइल लूप में पूरी कतार खाली करें।
        """
        data_received = False
        
        while not self.data_queue.empty():
            try:
                batch = self.data_queue.get_nowait()
                
                # Process through DSP engine
                raw_clean, velocity, displacement, self.dsp_state = process_batch(
                    batch, self.dsp_state
                )
                
                # Roll buffers and append new data
                batch_size = len(batch)
                
                self.raw_buffer = np.roll(self.raw_buffer, -batch_size)
                self.raw_buffer[-batch_size:] = raw_clean
                
                self.vel_buffer = np.roll(self.vel_buffer, -batch_size)
                self.vel_buffer[-batch_size:] = velocity
                
                self.disp_buffer = np.roll(self.disp_buffer, -batch_size)
                self.disp_buffer[-batch_size:] = displacement
                
                data_received = True
            except queue.Empty:
                break
        
        # Update plots if data was received
        if data_received:
            self.curve_raw.setData(self.raw_buffer)
            self.curve_vel.setData(self.vel_buffer)
            self.curve_disp.setData(self.disp_buffer)
            
    def closeEvent(self, event):
        """Clean shutdown of TCP server thread."""
        self.server_thread.stop()
        self.server_thread.join(timeout=2)
        event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    
    # Dark theme application stylesheet
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
            border-radius: 5px;
        }
    """)
    
    window = NadiMonitor()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
