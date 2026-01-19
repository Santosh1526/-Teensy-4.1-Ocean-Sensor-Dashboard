## 🌊 Teensy 4.1 Ocean Sensor Dashboard

A comprehensive Python-based monitoring system for ocean environmental sensors using Teensy 4.1 microcontroller. Features real-time data visualization, SD card logging, remote data download, and interactive graphing capabilities.

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-green.svg)
![Serial](https://img.shields.io/badge/Communication-Serial-orange.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

---

## 📋 Table of Contents

- [Features](#-features)
- [System Architecture](#-system-architecture)
- [Hardware Requirements](#-hardware-requirements)
- [Software Requirements](#-software-requirements)
- [Installation](#-installation)
- [Usage](#-usage)
- [Data Protocol](#-data-protocol)
- [Screenshots](#-screenshots)
- [File Structure](#-file-structure)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

---

## ✨ Features

### 🔬 **Sensor Monitoring**
- **pH Sensor** - Water acidity/alkalinity measurement
- **Dissolved Oxygen (DO)** - Oxygen concentration in mg/L
- **Temperature** - Water temperature in °C
- **Pressure** - Atmospheric/water pressure in mbar

### 📊 **Data Management**
- ⏰ **30-minute interval readings** - Optimized for long-term deployment
- 💾 **Dual storage system** - SD card (Teensy) + CSV file (GUI)
- 📥 **Remote SD card download** - Retrieve all data via serial connection
- 🔄 **Continuous monitoring** - Real-time display updates even during sleep cycles
- 📈 **~4,320 readings** over 90-day deployment

### 🖥️ **GUI Features**
- 🎨 **Modern dark-themed interface** with color-coded sensor displays
- 💓 **Live heartbeat monitoring** - Continuous display updates
- 📊 **Real-time graphing** - 4-panel matplotlib visualization
- 📈 **Historical data analysis** - Load and plot SD card data
- 💾 **Export capabilities** - PNG, PDF, and CSV formats
- 🔔 **Status notifications** - Visual feedback for all operations

### 🛠️ **Technical Features**
- 🔌 **Auto-detection** - Automatic Teensy port detection
- 🧵 **Multi-threaded** - Non-blocking serial communication
- 🔒 **Thread-safe** - Proper GUI update synchronization
- ⚡ **High-speed serial** - 115200 baud communication
- 🛡️ **Error handling** - Robust exception management

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   TEENSY 4.1 HARDWARE                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ pH       │  │ DO       │  │ Temp     │  │ Pressure │   │
│  │ Sensor   │  │ Sensor   │  │ Sensor   │  │ Sensor   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │              │             │          │
│       └─────────────┴──────────────┴─────────────┘          │
│                         │                                    │
│                    ┌────▼────┐                              │
│                    │ Teensy  │                              │
│                    │  4.1    │                              │
│                    └────┬────┘                              │
│                         │                                    │
│                    ┌────▼────┐                              │
│                    │ SD Card │ (30-min intervals)           │
│                    └─────────┘                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                  USB Serial
                  115200 baud
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              PYTHON GUI APPLICATION                         │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Real-time Display  │  CSV Logging  │  Graphs       │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Serial Thread (Background)                         │   │
│  │  - Continuous reading                               │   │
│  │  - Protocol parsing                                 │   │
│  │  - Thread-safe updates                              │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                       │
              ┌────────┴────────┐
              │                 │
         ┌────▼────┐      ┌────▼────┐
         │  CSV    │      │ Graphs  │
         │  Export │      │ Export  │
         └─────────┘      └─────────┘
```

---

## 🔧 Hardware Requirements

- **Teensy 4.1** microcontroller
- **SD Card** (for onboard logging)
- **Sensors:**
  - pH sensor (analog output)
  - Dissolved Oxygen sensor (analog output)
  - Temperature sensor (digital/analog)
  - Pressure sensor (I2C/analog)
- **USB Cable** (for serial communication)
- **Power Supply** (appropriate for deployment environment)

---

## 💻 Software Requirements

### Python Dependencies

```bash
Python >= 3.7
tkinter (usually included with Python)
pyserial >= 3.5
Pillow >= 8.0
matplotlib >= 3.3.0
```

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/yourusername/teensy-ocean-sensor-dashboard.git
cd teensy-ocean-sensor-dashboard
```

2. **Install required packages:**
```bash
pip install pyserial pillow matplotlib
```

3. **Run the application:**
```bash
python ocean_sensor_dashboard.py
```

---

## 🚀 Usage

### Getting Started

1. **Connect Hardware:**
   - Connect Teensy 4.1 to your computer via USB
   - Ensure SD card is inserted in Teensy
   - Verify all sensors are connected

2. **Launch Application:**
   ```bash
   python ocean_sensor_dashboard.py
   ```

3. **Connect to Teensy:**
   - Click **"🔌 Connect to Teensy"**
   - Port auto-detection will attempt to find Teensy
   - Manual port entry available if auto-detection fails

4. **Monitor Data:**
   - Live sensor values update continuously
   - Scheduled readings (every 30 min) saved to SD + CSV
   - Console displays all system messages

### Key Operations

#### 📥 Download SD Card Data
```
1. Click "📥 Download SD Card"
2. Select save location
3. Wait for download completion
4. Data saved as text file with all readings
```

#### 📊 View Live Graphs
```
1. Click "📊 Live Graph"
2. 4-panel graph window opens
3. Auto-refreshes every 10 seconds
4. Export as PNG/PDF/CSV available
```

#### 📈 Analyze SD Card Data
```
1. Click "📥 SD Graph"
2. Select downloaded SD card file
3. Visualize historical data
4. Export graphs and data
```

#### 💾 Export CSV Data
```
1. Click "💾 Download CSV"
2. Choose save location
3. All GUI readings exported
```

---

## 📡 Data Protocol

### Teensy → GUI Communication

**Primary Format:**
```
$Params,<pH*100>,<DO*10>,<Temp*50>,<Pressure*1000>,<FLAG>
```

**Example:**
```
$Params,742,85,1120,1013000,SAVED
```

**Decoding:**
- pH = 742 / 100 = **7.42**
- DO = 85 / 10 = **8.5 mg/L**
- Temp = 1120 / 50 = **22.4°C**
- Pressure = 1013000 / 1000 = **1013.0 mbar**
- FLAG = **SAVED** (indicates 30-min scheduled reading)

### SD Card Download Protocol

**Request:**
```
DOWNLOAD_SD\n
```

**Response:**
```
SD_DOWNLOAD_START
<data lines...>
SD_DOWNLOAD_PROGRESS: X lines sent
<more data...>
SD_DOWNLOAD_END
```

**Error Handling:**
```
SD_DOWNLOAD_ERROR: <error message>
```

---

## 📸 Screenshots

### Main Dashboard
![Dashboard Screenshot](screenshots/dashboard.png)
*Real-time sensor monitoring with color-coded displays*

### Live Graphs
![Live Graphs Screenshot](screenshots/live_graphs.png)
*4-panel real-time data visualization*

### SD Card Download
![SD Download Screenshot](screenshots/sd_download.png)
*Remote SD card data retrieval interface*

---

## 📁 File Structure

```
teensy-ocean-sensor-dashboard/
│
├── ocean_sensor_dashboard.py      # Main Python application
├── teensy_firmware/                # Teensy 4.1 firmware (if included)
│   └── sensor_logger.ino
│
├── flowchart/                      # Engineering documentation
│   └── teensy_flowchart.html      # Interactive system flowchart
│
├── screenshots/                    # Application screenshots
│   ├── dashboard.png
│   ├── live_graphs.png
│   └── sd_download.png
│
├── data/                          # Sample data (optional)
│   ├── sample_readings.csv
│   └── sample_sd_data.txt
│
├── requirements.txt               # Python dependencies
├── README.md                      # This file
└── LICENSE                        # License information
```

---

## 🔧 Configuration

### Serial Settings
```python
BAUD = 115200              # Serial baud rate
SERIAL_TIMEOUT = 1.0       # Serial timeout in seconds
```

### Data Management
```python
MAX_BUFFER_SIZE = 10000    # Maximum readings in memory
READING_INTERVAL = 30      # Minutes between readings (Teensy)
```

### CSV Output
- **Continuous CSV:** Auto-created on connection
- **Format:** `teensy_30min_readings_YYYYMMDD_HHMMSS.csv`
- **Fields:** timestamp, pH, DO, Temperature, Pressure

---

## 🐛 Troubleshooting

### Connection Issues

**Problem:** Cannot find Teensy port
```
Solution:
1. Check USB cable connection
2. Verify Teensy is powered on
3. Try manual port entry (COM3, /dev/ttyACM0, etc.)
4. Install Teensy USB drivers if needed
```

**Problem:** Serial connection drops
```
Solution:
1. Check USB cable quality
2. Verify stable power supply
3. Reduce serial timeout if needed
4. Check for electromagnetic interference
```

### Data Issues

**Problem:** No data appearing
```
Solution:
1. Verify Teensy firmware is running
2. Check sensor connections
3. Monitor serial console for errors
4. Verify $Params protocol format
```

**Problem:** SD download fails
```
Solution:
1. Ensure SD card is properly inserted
2. Check SD card has data
3. Verify sufficient disk space for download
4. Try downloading to different location
```

### Graph Issues

**Problem:** Graphs not displaying
```
Solution:
1. Verify matplotlib is installed: pip install matplotlib
2. Check that sensor_data_list has entries
3. Ensure valid timestamp format
4. Update matplotlib: pip install --upgrade matplotlib
```

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Guidelines

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/AmazingFeature`)
3. **Commit changes** (`git commit -m 'Add AmazingFeature'`)
4. **Push to branch** (`git push origin feature/AmazingFeature`)
5. **Open a Pull Request**

### Areas for Contribution

- 🔌 Additional sensor support
- 📊 New visualization options
- 🌐 Web-based dashboard
- 📱 Mobile app integration
- 🔔 Alert/notification system
- 🗄️ Database integration
- 🧪 Unit tests

---

## 📊 Project Status

- ✅ Core functionality complete
- ✅ Real-time monitoring
- ✅ SD card download
- ✅   Graph visualization
- ✅  CSV export
- ✅ Web dashboard (planned)
- ✅ Database integration (planned)


---

## 📄 License


```
MIT License

Copyright (c) 2025 [Santosh Ambule]

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 👥 Authors

- **Santosh Ambule** - *Initial work* - https://github.com/Santosh1526

---

## 🙏 Acknowledgments

- Teensy 4.1 by [PJRC](https://www.pjrc.com/)
- Python Serial library by [pySerial](https://github.com/pyserial/pyserial)
- Matplotlib for visualization
- Ocean sensor research community

---

## 📞 Contact

**Project Link:** 

**Email:** santoshambule15@gmail.com

---

## 🌟 Star History

If you find this project useful, please consider giving it a ⭐!

---

## 📈 Deployment Example

### 90-Day Ocean Monitoring Deployment

```
Total Readings Expected: ~4,320
Reading Interval: 30 minutes
Storage Required: ~2-5 MB (SD card)
Power Consumption: ~500mW average
Battery Life: ~90 days (with 5000mAh battery)
```

### Typical Use Cases

- 🌊 **Aquaculture monitoring**
- 🔬 **Marine research**
- 🏊 **Pool/water quality monitoring**
- 🌡️ **Environmental studies**
- 📊 **Long-term data collection**

---

**Made with ❤️ for ocean environmental monitoring
