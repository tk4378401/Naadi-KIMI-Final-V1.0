# File: Nadi_DSP.py
# Ayurvedic Nadi Pariksha - Digital Signal Processing Engine
# नाड़ी परीक्षण डिजिटल सिग्नल प्रोसेसिंग इंजन
# Pure Math ONLY - No FFT, No BPM (Strictly Ayurvedic Time-Domain Analysis)

import numpy as np
from scipy import signal

# Sample Rate - 1000 Hz (1ms intervals)
# नमूना दर - 1000 हर्ट्ज
FS = 1000.0
DT = 1.0 / FS

# DSP Filter Configuration
# DSP फिल्टर कॉन्फिगरेशन

# 1st-order Butterworth High-Pass 0.1Hz for Raw Clean
# प्रथम-कोटि बटरवर्थ हाई-पास 0.1 हर्ट्ज
sos_hp_raw = signal.butter(1, 0.1, btype='high', output='sos', fs=FS)
zi_hp_raw_init = signal.sosfilt_zi(sos_hp_raw)

# 1st-order Butterworth High-Pass 0.05Hz for Integrator Anchor (Differentiator Illusion Fix)
# समाकलक एंकर के लिए प्रथम-कोटि बटरवर्थ हाई-पास 0.05 हर्ट्ज
sos_hp_anchor = signal.butter(1, 0.05, btype='high', output='sos', fs=FS)
zi_hp_anchor_init = signal.sosfilt_zi(sos_hp_anchor)

# Leaky Integrator Coefficients (0.999 for distinct Raw/Velocity appearance)
# लीकी इंटीग्रेटर गुणांक (0.999)
LEAKY_B = [DT]  # Numerator
LEAKY_A = [1.0, -0.999]  # Denominator with 0.999 leak factor


def process_batch(raw_batch, state):
    """
    Process a batch of 50 raw acceleration samples through the VPK chain.
    कच्चे त्वरण नमूनों के बैच को VPK श्रृंखला के माध्यम से प्रोसेस करें।
    
    Pipeline: Raw Clean -> Velocity -> Displacement
    Vata (Flow), Pitta (Heat/Metabolism), Kapha (Structure/Volume)
    वात (प्रवाह), पित्त (गर्मी/चयापचय), कफ (संरचना/आयतन)
    
    Args:
        raw_batch: 50 samples of raw acceleration (float64)
        state: Dictionary containing filter states
    
    Returns:
        Tuple of (raw_clean, velocity, displacement, updated_state)
    """
    # Extract or initialize filter states
    zi_hp_raw = state.get('zi_hp_raw', zi_hp_raw_init.copy())
    zi_vel_leaky = state.get('zi_vel_leaky', np.zeros(1))
    zi_vel_anchor = state.get('zi_vel_anchor', zi_hp_anchor_init.copy())
    zi_disp_leaky = state.get('zi_disp_leaky', np.zeros(1))
    zi_disp_anchor = state.get('zi_disp_anchor', zi_hp_anchor_init.copy())
    
    # Flatline/Spike Fix: Scale first HP filter state with first sample
    # फ्लैटलाइन/स्पाइक फिक्स: पहले नमूने के साथ पहले HP फिल्टर स्थिति को स्केल करें
    if len(raw_batch) > 0:
        zi_hp_raw = zi_hp_raw_init * raw_batch[0]
    
    # Stage 1: Raw Clean - High-Pass to remove DC drift
    # चरण 1: कच्चा साफ - DC ड्रिफ्ट हटाने के लिए हाई-पास
    raw_clean, zi_hp_raw = signal.sosfilt(sos_hp_raw, raw_batch, zi=zi_hp_raw)
    
    # Stage 2: Velocity - Leaky Integrator -> Anchor HPF
    # चरण 2: वेग - लीकी इंटीग्रेटर -> एंकर HPF
    # Leaky integration of raw (acceleration -> velocity)
    vel_leaky, zi_vel_leaky = signal.lfilter(LEAKY_B, LEAKY_A, raw_clean, zi=zi_vel_leaky)
    # Anchor to prevent drift
    velocity, zi_vel_anchor = signal.sosfilt(sos_hp_anchor, vel_leaky, zi=zi_vel_anchor)
    
    # Stage 3: Displacement - Leaky Integrator -> Anchor HPF -> Invert
    # चरण 3: विस्थापन - लीकी इंटीग्रेटर -> एंकर HPF -> इनवर्ट
    # Leaky integration of velocity (velocity -> displacement)
    disp_leaky, zi_disp_leaky = signal.lfilter(LEAKY_B, LEAKY_A, velocity, zi=zi_disp_leaky)
    # Anchor to prevent drift
    displacement, zi_disp_anchor = signal.sosfilt(sos_hp_anchor, disp_leaky, zi=zi_disp_anchor)
    # Invert displacement for proper VPK morphology visualization
    displacement = -displacement
    
    # Update state dictionary
    new_state = {
        'zi_hp_raw': zi_hp_raw,
        'zi_vel_leaky': zi_vel_leaky,
        'zi_vel_anchor': zi_vel_anchor,
        'zi_disp_leaky': zi_disp_leaky,
        'zi_disp_anchor': zi_disp_anchor
    }
    
    return raw_clean, velocity, displacement, new_state


def create_initial_state():
    """
    Create initial DSP state with proper initialization.
    उचित प्रारंभीकरण के साथ प्रारंभिक DSP स्थिति बनाएं।
    """
    return {
        'zi_hp_raw': zi_hp_raw_init.copy(),
        'zi_vel_leaky': np.zeros(1),
        'zi_vel_anchor': zi_hp_anchor_init.copy(),
        'zi_disp_leaky': np.zeros(1),
        'zi_disp_anchor': zi_hp_anchor_init.copy()
    }
