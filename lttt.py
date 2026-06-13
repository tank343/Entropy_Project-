import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import collections
import numpy as np

PORT = 'COM3' # SỬA CỔNG COM CỦA BẠN
data_buffers = [collections.deque([0.0]*50, maxlen=50) for _ in range(6)]
ser = serial.Serial(PORT, 115200, timeout=0.01)

fig, axs = plt.subplots(3, 2, figsize=(12, 10))
axs = axs.flatten()
titles = ['Entropy (bits)', 'SNR (dB)', 'Compression Ratio (8/H)', 
          'RSSI (dBm)', 'Inter-arrival Time (us)', 'Packet Loss (%)']
colors = ['#2ecc71', '#e74c3c', '#3498db', '#1abc9c', '#9b59b6', '#f1c40f']

lines = []
for i in range(6):
    line, = axs[i].plot(np.arange(50), data_buffers[i], color=colors[i], lw=2)
    lines.append(line)
    axs[i].set_title(titles[i], fontweight='bold')
    axs[i].grid(True, alpha=0.3)

def update(frame):
    if ser.in_waiting > 200: ser.reset_input_buffer()
    while ser.in_waiting > 0:
        try:
            line_str = ser.readline().decode('utf-8').strip()
            parts = line_str.split(',')
            if len(parts) == 6:
                for i in range(6): data_buffers[i].append(float(parts[i]))
        except: continue
    for i in range(6):
        lines[i].set_ydata(data_buffers[i])
        axs[i].relim()
        axs[i].autoscale_view()
        if i == 0: axs[i].set_ylim(0, 8.5)
        if i == 1: axs[i].set_ylim(-15, 45)
        if i == 2: axs[i].set_ylim(0, 30) # CỐ ĐỊNH TRỤC CR TỪ 0 ĐẾN 30x
        if i == 3: axs[i].set_ylim(-100, 0)
    return lines

ani = FuncAnimation(fig, update, interval=20, blit=False)
plt.tight_layout()
plt.show()