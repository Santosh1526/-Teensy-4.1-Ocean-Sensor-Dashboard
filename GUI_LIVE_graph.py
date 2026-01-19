import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from PIL import Image, ImageTk, ImageEnhance
import serial
import threading
import time
import csv
import serial.tools.list_ports
from datetime import datetime, timedelta
import sys
import re
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates

# -------------------- CONFIG --------------------
BAUD = 115200
SERIAL_TIMEOUT = 1.0

# -------------------- Global Variables --------------------
ser = None
sensor_data_list = []
csv_file_path = None
csv_writer = None
csv_file = None
continuous_csv_file = None
continuous_csv_writer = None

# runtime flags / thread handles
is_reading = False
read_thread = None
read_thread_stop = threading.Event()

# Current sensor values
current_ph = 0.0
current_do = 0.0
current_temp = 0.0
current_pressure = 0.0

# Last saved reading timestamp
last_saved_reading_time = None

# SD download variables
sd_download_active = False
sd_download_buffer = []
sd_download_file = None

# Graph window reference
graph_window = None

# -------------------- Find Teensy Port --------------------
def find_teensy_port():
    """Automatically detect Teensy port"""
    ports = serial.tools.list_ports.comports()
    print("\n🔍 Scanning for Teensy...")
    for port in ports:
        print(f"  📍 {port.device} - {port.description}")
        desc = (port.description or "").lower()
        dev = (port.device or "").lower()
        if "teensy" in desc or "teensy" in dev:
            print(f"  ✅ Found Teensy!")
            return port.device
        if "usbmodem" in dev or "ttyacm" in dev or "usbserial" in dev:
            print(f"  ✅ Found USB Serial Device!")
            return port.device
        if getattr(port, "vid", None) == 0x16C0:
            print(f"  ✅ Found Teensy by VID!")
            return port.device
    print("  ❌ No Teensy found")
    return None

# -------------------- Serial Reading Thread --------------------
def read_serial_data():
    """Continuously read data from Teensy and update display"""
    global ser, is_reading, read_thread_stop
    print("📡 Serial reading thread started")
    try:
        while not read_thread_stop.is_set() and is_reading:
            if ser is None or not getattr(ser, "is_open", False):
                time.sleep(0.1)
                continue

            try:
                if getattr(ser, "in_waiting", 0) > 0:
                    raw = ser.readline()
                    if not raw:
                        continue
                    try:
                        line = raw.decode("utf-8", errors="ignore").strip()
                    except Exception:
                        line = raw.decode("latin-1", errors="ignore").strip()
                    if line:
                        print(f"📥 RECEIVED: {line}")
                        root.after(0, lambda l=line: update_display(l))
                else:
                    time.sleep(0.02)
            except (serial.SerialException, OSError) as e:
                print(f"❌ Serial Exception in read loop: {e}")
                try:
                    text_box.insert(tk.END, f"[SERIAL ERROR] {e}\n", "red")
                    text_box.see(tk.END)
                except:
                    pass
                is_reading = False
                read_thread_stop.set()
                try:
                    if ser:
                        ser.close()
                except:
                    pass
                ser = None
                break
            except Exception as e:
                print(f"❌ Unexpected read error: {e}")
                try:
                    text_box.insert(tk.END, f"[READ ERROR] {e}\n", "red")
                    text_box.see(tk.END)
                except:
                    pass
                time.sleep(0.2)
    finally:
        print("📴 Serial reading thread exiting")

# -------------------- Update Display with Synchronized Output --------------------
def update_display(line):
    """Parse incoming data and update GUI labels with sensor values"""
    global current_ph, current_do, current_temp, current_pressure, last_saved_reading_time
    global sd_download_active, sd_download_buffer, sd_download_file

    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updated = False
        is_saved_reading = False

        # ========== SD DOWNLOAD PROTOCOL ==========
        if sd_download_active:
            if line == "SD_DOWNLOAD_END":
                # Download complete
                if sd_download_file:
                    sd_download_file.write("\n".join(sd_download_buffer))
                    sd_download_file.close()
                    sd_download_file = None
                    
                text_box.insert(tk.END, f"\n{'='*70}\n", "green")
                text_box.insert(tk.END, f"✅ SD CARD DOWNLOAD COMPLETE!\n", "green")
                text_box.insert(tk.END, f"📊 Total lines received: {len(sd_download_buffer)}\n", "cyan")
                text_box.insert(tk.END, f"{'='*70}\n\n", "green")
                text_box.see(tk.END)
                
                messagebox.showinfo("Download Complete", 
                    f"✅ SD Card data downloaded successfully!\n\n"
                    f"📊 Total lines: {len(sd_download_buffer)}\n"
                    f"💾 File saved")
                
                sd_download_active = False
                sd_download_buffer = []
                download_sd_button.config(state="normal", text="📥 Download SD Card")
                status_label.config(text="📊 Status: Connected - Monitoring", fg="#00BFFF")
                return
            
            elif line.startswith("SD_DOWNLOAD_ERROR"):
                # Download error
                if sd_download_file:
                    sd_download_file.close()
                    sd_download_file = None
                
                text_box.insert(tk.END, f"\n❌ SD DOWNLOAD ERROR: {line}\n\n", "red")
                text_box.see(tk.END)
                
                messagebox.showerror("Download Error", 
                    f"❌ SD Card download failed:\n\n{line}")
                
                sd_download_active = False
                sd_download_buffer = []
                download_sd_button.config(state="normal", text="📥 Download SD Card")
                status_label.config(text="📊 Status: Connected - Monitoring", fg="#00BFFF")
                return
            
            elif line.startswith("SD_DOWNLOAD_PROGRESS"):
                # Progress update
                parts = line.split(":")
                if len(parts) > 1:
                    text_box.insert(tk.END, f"📥 {parts[1]}\n", "cyan")
                    text_box.see(tk.END)
                return
            
            else:
                # Regular SD data line
                sd_download_buffer.append(line)
                
                # Update progress every 50 lines
                if len(sd_download_buffer) % 50 == 0:
                    text_box.insert(tk.END, f"📥 Received {len(sd_download_buffer)} lines...\n", "cyan")
                    text_box.see(tk.END)
                return

        # ========== PRIMARY FORMAT: $Params,pH*100,DO*10,Temp*50,Pressure*1000,FLAG ==========
        if "$Params" in line or "$params" in line:
            parts = line.split(',')
            if len(parts) >= 5:
                try:
                    current_ph = float(parts[1]) / 100.0
                    current_do = float(parts[2]) / 10.0
                    current_temp = float(parts[3]) / 50.0
                    current_pressure = float(parts[4]) / 1000.0
                    
                    if len(parts) >= 6 and "SAVED" in parts[5].upper():
                        is_saved_reading = True
                        last_saved_reading_time = datetime.now()
                    
                    ph_label.config(text=f"🌊 pH: {current_ph:.2f}")
                    do_label.config(text=f"💧 DO: {current_do:.2f} mg/L")
                    temp_label.config(text=f"🔥 Temperature: {current_temp:.2f}°C")
                    pressure_label.config(text=f"🌡️ Pressure: {current_pressure:.2f} mbar")
                    
                    if is_saved_reading:
                        save_sensor_data(current_time, current_ph, current_do, current_temp, current_pressure)
                        text_box.insert(tk.END, f"\n{'='*70}\n", "white")
                        text_box.insert(tk.END, f"[{current_time}] ✅ SD CARD READING SAVED:\n", "green")
                        text_box.insert(tk.END, f"{'='*70}\n", "white")
                        text_box.insert(tk.END, f"  🌊 pH: {current_ph:.2f}\n", "blue")
                        text_box.insert(tk.END, f"  💧 DO: {current_do:.2f} mg/L\n", "green")
                        text_box.insert(tk.END, f"  🔥 Temp: {current_temp:.2f}°C\n", "red")
                        text_box.insert(tk.END, f"  🌡️ Pressure: {current_pressure:.2f} mbar\n", "goldenrod")
                        text_box.insert(tk.END, f"  💾 Saved to: SD Card + CSV File\n", "cyan")
                        text_box.insert(tk.END, f"{'='*70}\n\n", "white")
                        
                        status_label.config(text="📊 Status: Reading Saved to SD + CSV", fg="#00FF00")
                        root.after(3000, lambda: status_label.config(text="📊 Status: Connected - Monitoring", fg="#00BFFF"))
                    else:
                        text_box.insert(tk.END, f"[{current_time}] 💓 Heartbeat - Display Updated\n", "cyan")
                        status_label.config(text="📊 Status: Live Display Update", fg="#00BFFF")
                    
                    text_box.see(tk.END)
                    updated = True
                    
                except ValueError as e:
                    text_box.insert(tk.END, f"[PARSE ERR] {e}\n", "red")
                    text_box.see(tk.END)

        # ========== Show system messages ==========
        if not updated:
            if any(keyword in line for keyword in ["READING #", "Time:", "Sleeping", "WAKING UP", 
                                                    "SD card", "Counter", "Runtime", "Temperature sensor",
                                                    "Pressure sensor", "Duration"]):
                if "READING #" in line:
                    text_box.insert(tk.END, f"\n{'='*70}\n", "yellow")
                    text_box.insert(tk.END, f"{line}\n", "yellow")
                    text_box.insert(tk.END, f"{'='*70}\n", "yellow")
                elif "Sleeping" in line:
                    text_box.insert(tk.END, f"\n😴 {line}\n", "cyan")
                    text_box.insert(tk.END, "⏰ Next reading in 30 minutes...\n", "yellow")
                    text_box.insert(tk.END, "💓 Display will remain updated with heartbeat data\n\n", "cyan")
                    status_label.config(text="😴 Status: Sleeping (Next reading in 30 min)", fg="#FFA500")
                elif "WAKING UP" in line:
                    text_box.insert(tk.END, f"\n⏰ {line}\n", "green")
                    text_box.insert(tk.END, "📊 Taking scheduled reading...\n\n", "green")
                    status_label.config(text="⏰ Status: Taking Reading", fg="#00FF00")
                elif "✓" in line or "✗" in line:
                    color = "green" if "✓" in line else "red"
                    text_box.insert(tk.END, f"{line}\n", color)
                else:
                    text_box.insert(tk.END, f"{line}\n", "white")
                text_box.see(tk.END)

    except Exception as e:
        text_box.insert(tk.END, f"ERROR in update_display: {e}\n", "red")
        text_box.see(tk.END)

# -------------------- Save Sensor Data --------------------
def save_sensor_data(timestamp, ph, do, temp, pressure):
    """Store sensor readings and save to BOTH continuous and interval CSV files"""
    global csv_file, csv_writer, continuous_csv_file, continuous_csv_writer
    
    sensor_data_list.append({
        "timestamp": timestamp,
        "pH": f"{ph:.2f}",
        "DO": f"{do:.2f}",
        "Temperature": f"{temp:.2f}",
        "Pressure": f"{pressure:.2f}"
    })

    if len(sensor_data_list) > 10000:
        sensor_data_list.pop(0)

    try:
        if continuous_csv_file and continuous_csv_writer:
            continuous_csv_writer.writerow({
                "timestamp": timestamp,
                "pH": f"{ph:.2f}",
                "DO": f"{do:.2f}",
                "Temperature": f"{temp:.2f}",
                "Pressure": f"{pressure:.2f}"
            })
            continuous_csv_file.flush()
    except Exception as e:
        print(f"Error writing to continuous CSV: {e}")

    data_count_label.config(text=f"📊 Saved Readings: {len(sensor_data_list)}")

# -------------------- Download SD Card Data --------------------
def download_sd_card():
    """Request SD card data download from Teensy"""
    global ser, sd_download_active, sd_download_buffer, sd_download_file

    if not ser or not getattr(ser, "is_open", False):
        messagebox.showerror("Not Connected", "⚠️ Please connect to Teensy first!")
        return

    if sd_download_active:
        messagebox.showwarning("Download Active", "⚠️ SD download already in progress!")
        return

    # Ask user for save location
    file_path = filedialog.asksaveasfilename(
        defaultextension=".txt",
        filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
        initialfile=f"Datalog_Download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )

    if not file_path:
        return

    try:
        # Open file for writing
        sd_download_file = open(file_path, 'w')
        sd_download_buffer = []
        sd_download_active = True

        # Update UI
        download_sd_button.config(state="disabled", text="⏳ Downloading...")
        status_label.config(text="📥 Status: Downloading SD Card...", fg="#FFA500")

        text_box.insert(tk.END, f"\n{'='*70}\n", "cyan")
        text_box.insert(tk.END, f"📥 REQUESTING SD CARD DOWNLOAD\n", "cyan")
        text_box.insert(tk.END, f"{'='*70}\n", "cyan")
        text_box.insert(tk.END, f"💾 Save location: {file_path}\n", "yellow")
        text_box.insert(tk.END, f"⏳ Waiting for Teensy response...\n\n", "yellow")
        text_box.see(tk.END)

        # Send download command to Teensy
        ser.write(b"DOWNLOAD_SD\n")
        ser.flush()

        print("📥 SD download request sent to Teensy")

    except Exception as e:
        messagebox.showerror("Download Error", f"Failed to start download:\n\n{e}")
        sd_download_active = False
        sd_download_buffer = []
        if sd_download_file:
            sd_download_file.close()
            sd_download_file = None
        download_sd_button.config(state="normal", text="📥 Download SD Card")

# -------------------- Plot Graph Helper --------------------
def plot_sensor_graphs(timestamps, ph_values, do_values, temp_values, pressure_values, title_text, window):
    """Helper function to create and display graphs"""
    
    # Create figure with subplots
    fig = Figure(figsize=(12, 8), facecolor='#001F33')
    
    # Create 4 subplots (2x2 grid)
    ax1 = fig.add_subplot(2, 2, 1, facecolor='#0A1929')
    ax2 = fig.add_subplot(2, 2, 2, facecolor='#0A1929')
    ax3 = fig.add_subplot(2, 2, 3, facecolor='#0A1929')
    ax4 = fig.add_subplot(2, 2, 4, facecolor='#0A1929')
    
    # Plot 1: pH
    ax1.plot(timestamps, ph_values, color='#00E1FF', linewidth=2, marker='o', markersize=4)
    ax1.set_title('🌊 pH Level', color='white', fontsize=14, fontweight='bold')
    ax1.set_ylabel('pH', color='white', fontsize=12)
    ax1.tick_params(colors='white')
    ax1.grid(True, alpha=0.3, color='white')
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    
    # Plot 2: Dissolved Oxygen
    ax2.plot(timestamps, do_values, color='#00FF88', linewidth=2, marker='s', markersize=4)
    ax2.set_title('💧 Dissolved Oxygen', color='white', fontsize=14, fontweight='bold')
    ax2.set_ylabel('DO (mg/L)', color='white', fontsize=12)
    ax2.tick_params(colors='white')
    ax2.grid(True, alpha=0.3, color='white')
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    
    # Plot 3: Temperature
    ax3.plot(timestamps, temp_values, color='#FF6B6B', linewidth=2, marker='^', markersize=4)
    ax3.set_title('🔥 Temperature', color='white', fontsize=14, fontweight='bold')
    ax3.set_ylabel('Temperature (°C)', color='white', fontsize=12)
    ax3.set_xlabel('Time', color='white', fontsize=12)
    ax3.tick_params(colors='white')
    ax3.grid(True, alpha=0.3, color='white')
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    
    # Plot 4: Pressure
    ax4.plot(timestamps, pressure_values, color='#FFD700', linewidth=2, marker='d', markersize=4)
    ax4.set_title('🌡️ Pressure', color='white', fontsize=14, fontweight='bold')
    ax4.set_ylabel('Pressure (mbar)', color='white', fontsize=12)
    ax4.set_xlabel('Time', color='white', fontsize=12)
    ax4.tick_params(colors='white')
    ax4.grid(True, alpha=0.3, color='white')
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    
    # Rotate x-axis labels
    for ax in [ax1, ax2, ax3, ax4]:
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    fig.tight_layout(pad=3.0)
    
    return fig

# -------------------- Open Live Graph Window --------------------
def open_graph_window():
    """Open a new window with real-time graphs of sensor data from GUI"""
    global graph_window
    
    if not sensor_data_list:
        messagebox.showwarning("No Data", 
            "⚠️ No sensor data available to plot!\n\n"
            "Connect to Teensy and wait for readings to be saved.")
        return
    
    # Check if graph window already exists
    if graph_window is not None and graph_window.winfo_exists():
        graph_window.lift()
        graph_window.focus_force()
        return
    
    # Create new window
    graph_window = tk.Toplevel(root)
    graph_window.title("📊 Live Sensor Data Graphs")
    graph_window.geometry("1200x900")
    graph_window.configure(bg="#3B6D42")
    # Create new window
    graph_window = tk.Toplevel(root)
    graph_window.title("📊 Live Sensor Data Graphs")
    graph_window.geometry("1200x900")
    graph_window.configure(bg="#001F33")
    
    # Title
    title = tk.Label(graph_window, text="📊 Live Sensor Data Visualization (GUI Readings)",
                    font=("Times", 20, "bold"), fg="#00E1FF", bg="#001F33")
    title.pack(pady=10)
    
    # Info label
    info_label = tk.Label(graph_window, 
                         text=f"📈 Displaying {len(sensor_data_list)} live readings | Auto-refreshing every 10 seconds",
                         font=("Arial", 10), fg="white", bg="#001F33")
    info_label.pack(pady=5)
    
    # Extract data
    timestamps = []
    ph_values = []
    do_values = []
    temp_values = []
    pressure_values = []
    
    for data in sensor_data_list:
        try:
            timestamps.append(datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S"))
            ph_values.append(float(data["pH"]))
            do_values.append(float(data["DO"]))
            temp_values.append(float(data["Temperature"]))
            pressure_values.append(float(data["Pressure"]))
        except:
            continue
    
    if not timestamps:
        messagebox.showerror("Error", "Unable to parse sensor data for graphing!")
        graph_window.destroy()
        return
    
    # Create graphs
    fig = plot_sensor_graphs(timestamps, ph_values, do_values, temp_values, pressure_values, 
                             "Live Readings", graph_window)
    
    # Create canvas
    canvas_frame = tk.Frame(graph_window, bg="#001F33")
    canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.draw()
    canvas_widget = canvas.get_tk_widget()
    canvas_widget.pack(fill=tk.BOTH, expand=True)
    
    # Auto-refresh function
    auto_refresh_enabled = [True]  # Use list to allow modification in nested function
    
    def auto_refresh():
        if not auto_refresh_enabled[0] or not graph_window.winfo_exists():
            return
            
        try:
            # Clear and recreate
            timestamps.clear()
            ph_values.clear()
            do_values.clear()
            temp_values.clear()
            pressure_values.clear()
            
            for data in sensor_data_list:
                try:
                    timestamps.append(datetime.strptime(data["timestamp"], "%Y-%m-%d %H:%M:%S"))
                    ph_values.append(float(data["pH"]))
                    do_values.append(float(data["DO"]))
                    temp_values.append(float(data["Temperature"]))
                    pressure_values.append(float(data["Pressure"]))
                except:
                    continue
            
            if timestamps:
                # Recreate figure
                new_fig = plot_sensor_graphs(timestamps, ph_values, do_values, temp_values, 
                                            pressure_values, "Live Readings", graph_window)
                
                # Update canvas
                canvas.figure = new_fig
                canvas.draw()
                
                # Update info label
                info_label.config(text=f"📈 Displaying {len(sensor_data_list)} live readings | "
                                      f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
            
            # Schedule next refresh
            if graph_window.winfo_exists():
                graph_window.after(10000, auto_refresh)
        except:
            pass
    
    # Start auto-refresh
    graph_window.after(10000, auto_refresh)
    
    # Button frame
    button_frame = tk.Frame(graph_window, bg="#001F33")
    button_frame.pack(pady=10)
    
    # Manual refresh button
    def manual_refresh():
        auto_refresh()
    
    refresh_btn = tk.Button(button_frame, text="🔄 Refresh Now", command=manual_refresh,
                           font=("Times", 11, "bold"), bg="#007A99", fg="white",
                           relief="flat", width=15, height=2)
    refresh_btn.pack(side=tk.LEFT, padx=5)
    
    # Toggle auto-refresh
    def toggle_auto_refresh():
        auto_refresh_enabled[0] = not auto_refresh_enabled[0]
        if auto_refresh_enabled[0]:
            toggle_btn.config(text="⏸️ Pause Auto-Refresh", bg="#FFA500")
            auto_refresh()
        else:
            toggle_btn.config(text="▶️ Resume Auto-Refresh", bg="#00AA00")
    
    toggle_btn = tk.Button(button_frame, text="⏸️ Pause Auto-Refresh", command=toggle_auto_refresh,
                          font=("Times", 11, "bold"), bg="#FFA500", fg="white",
                          relief="flat", width=18, height=2)
    toggle_btn.pack(side=tk.LEFT, padx=5)
    
    # Export graph button
    def export_graph():
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg"), ("PDF", "*.pdf")],
            initialfile=f"live_sensor_graphs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        )
        if file_path:
            try:
                fig.savefig(file_path, dpi=300, facecolor='#001F33', edgecolor='none')
                messagebox.showinfo("Success", f"📊 Graph saved to:\n\n{file_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save graph:\n\n{e}")
    
    export_btn = tk.Button(button_frame, text="💾 Export Graph", command=export_graph,
                          font=("Times", 11, "bold"), bg="#00AA00", fg="white",
                          relief="flat", width=15, height=2)
    export_btn.pack(side=tk.LEFT, padx=5)
    
    # Close button
    def close_window():
        auto_refresh_enabled[0] = False
        graph_window.destroy()
    
    close_btn = tk.Button(button_frame, text="❌ Close", command=close_window,
                         font=("Times", 11, "bold"), bg="#CC0000", fg="black",
                         relief="flat", width=12, height=2)
    close_btn.pack(side=tk.LEFT, padx=5)

# -------------------- Open SD Card Graph Window --------------------
def open_sd_graph_window():
    """Open a new window to plot data from SD card file"""
    
    # Ask user to select SD card data file
    file_path = filedialog.askopenfilename(
        title="Select SD Card Data File",
        filetypes=[("Text Files", "*.txt"), ("CSV Files", "*.csv"), ("All Files", "*.*")]
    )
    
    if not file_path:
        return
    
    try:
        # Parse SD card file
        timestamps = []
        ph_values = []
        do_values = []
        temp_values = []
        pressure_values = []
        
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
        text_box.insert(tk.END, f"\n📂 Loading SD card file: {file_path}\n", "cyan")
        text_box.see(tk.END)
        
        # Parse lines looking for $Params format
        for line in lines:
            line = line.strip()
            if "$Params" in line or "$params" in line:
                try:
                    parts = line.split(',')
                    if len(parts) >= 5:
                        ph = float(parts[1]) / 100.0
                        do = float(parts[2]) / 10.0
                        temp = float(parts[3]) / 50.0
                        pressure = float(parts[4]) / 1000.0
                        
                        # Use current time as placeholder (SD card might not have timestamps)
                        # You can modify this to extract timestamps if they exist in your SD format
                        timestamps.append(datetime.now() + timedelta(minutes=len(timestamps)*30))
                        ph_values.append(ph)
                        do_values.append(do)
                        temp_values.append(temp)
                        pressure_values.append(pressure)
                except:
                    continue
        
        if not timestamps:
            messagebox.showerror("No Data", 
                f"⚠️ No valid sensor data found in file!\n\n"
                f"Make sure the file contains $Params format data.")
            text_box.insert(tk.END, f"❌ No valid data found in SD file\n", "red")
            text_box.see(tk.END)
            return
        
        text_box.insert(tk.END, f"✅ Loaded {len(timestamps)} readings from SD card\n", "green")
        text_box.see(tk.END)
        
        # Create graph window
        sd_graph_window = tk.Toplevel(root)
        sd_graph_window.title("📥 SD Card Data Graphs")
        sd_graph_window.geometry("1200x900")
        sd_graph_window.configure(bg="#001F33")
        
        # Title
        title = tk.Label(sd_graph_window, text="📥 SD Card Data Visualization",
                        font=("Times", 20, "bold"), fg="#00E1FF", bg="#001F33")
        title.pack(pady=10)
        
        # Info label
        info_label = tk.Label(sd_graph_window, 
                             text=f"📈 Displaying {len(timestamps)} readings from SD card | File: {file_path.split('/')[-1]}",
                             font=("Arial", 10), fg="white", bg="#001F33")
        info_label.pack(pady=5)
        
        # Create graphs
        fig = plot_sensor_graphs(timestamps, ph_values, do_values, temp_values, pressure_values,
                                "SD Card Data", sd_graph_window)
        
        # Create canvas
        canvas = FigureCanvasTkAgg(fig, master=sd_graph_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Button frame
        button_frame = tk.Frame(sd_graph_window, bg="#001F33")
        button_frame.pack(pady=10)
        
        # Export graph button
        def export_graph():
            export_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg"), ("PDF", "*.pdf")],
                initialfile=f"sd_card_graphs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )
            if export_path:
                try:
                    fig.savefig(export_path, dpi=300, facecolor='#001F33', edgecolor='none')
                    messagebox.showinfo("Success", f"📊 Graph saved to:\n\n{export_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save graph:\n\n{e}")
        
        export_btn = tk.Button(button_frame, text="💾 Export Graph", command=export_graph,
                              font=("Times", 11, "bold"), bg="#00AA00", fg="white",
                              relief="flat", width=15, height=2)
        export_btn.pack(side=tk.LEFT, padx=5)
        
        # Export CSV button
        def export_csv():
            csv_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV Files", "*.csv")],
                initialfile=f"sd_card_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            if csv_path:
                try:
                    with open(csv_path, 'w', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(["Timestamp", "pH", "DO (mg/L)", "Temperature (°C)", "Pressure (mbar)"])
                        for i in range(len(timestamps)):
                            writer.writerow([
                                timestamps[i].strftime("%Y-%m-%d %H:%M:%S"),
                                f"{ph_values[i]:.2f}",
                                f"{do_values[i]:.2f}",
                                f"{temp_values[i]:.2f}",
                                f"{pressure_values[i]:.2f}"
                            ])
                    messagebox.showinfo("Success", f"💾 CSV saved to:\n\n{csv_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save CSV:\n\n{e}")
        
        csv_btn = tk.Button(button_frame, text="📄 Export CSV", command=export_csv,
                           font=("Times", 11, "bold"), bg="#007A99", fg="white",
                           relief="flat", width=15, height=2)
        csv_btn.pack(side=tk.LEFT, padx=5)
        
        # Close button
        close_btn = tk.Button(button_frame, text="❌ Close", command=sd_graph_window.destroy,
                             font=("Times", 11, "bold"), bg="#CC0000", fg="white",
                             relief="flat", width=12, height=2)
        close_btn.pack(side=tk.LEFT, padx=5)
        
    except Exception as e:
        messagebox.showerror("Error Loading File", f"Failed to load SD card file:\n\n{e}")
        text_box.insert(tk.END, f"❌ Error loading SD file: {e}\n", "red")
        text_box.see(tk.END)

# -------------------- Connect to Teensy --------------------
def connect_teensy():
    """Connect to Teensy and start read thread"""
    global ser, is_reading, read_thread, read_thread_stop, continuous_csv_file, continuous_csv_writer

    if ser and getattr(ser, "is_open", False):
        messagebox.showinfo("Already Connected", "✅ Already connected to Teensy!")
        return

    port = find_teensy_port()

    if not port:
        response = messagebox.askyesno("Teensy Not Found",
            "⚠️ Could not find Teensy!\n\nTry manual port entry?")
        if response:
            port = simpledialog.askstring("Manual Port",
                "Enter port (e.g., COM3, /dev/ttyACM0):")
        if not port:
            text_box.insert(tk.END, "❌ No port provided. Connect aborted.\n", "red")
            text_box.see(tk.END)
            return

    try:
        try:
            continuous_csv_file_path = f"teensy_30min_readings_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            continuous_csv_file = open(continuous_csv_file_path, 'w', newline='')
            continuous_csv_writer = csv.DictWriter(continuous_csv_file, 
                                                   fieldnames=["timestamp", "pH", "DO", "Temperature", "Pressure"])
            continuous_csv_writer.writeheader()
            continuous_csv_file.flush()
            text_box.insert(tk.END, f"📝 CSV file created: {continuous_csv_file_path}\n", "cyan")
        except Exception as e:
            messagebox.showerror("File Error", f"Could not create CSV file:\n{e}")
            return

        text_box.insert(tk.END, f"🔌 Connecting to {port} at {BAUD} baud...\n", "white")
        text_box.see(tk.END)
        ser = serial.Serial(port, BAUD, timeout=SERIAL_TIMEOUT)
        time.sleep(0.2)
        try:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
        except Exception:
            pass

        is_reading = True
        read_thread_stop.clear()
        read_thread = threading.Thread(target=read_serial_data, daemon=True)
        read_thread.start()

        text_box.insert(tk.END, "\n" + "="*70 + "\n", "green")
        text_box.insert(tk.END, f"✅ CONNECTED to {port}\n", "green")
        text_box.insert(tk.END, "="*70 + "\n\n", "green")
        text_box.insert(tk.END, "📊 Mode: 30-Minute Interval Monitoring\n", "cyan")
        text_box.insert(tk.END, "💾 All scheduled readings saved to SD + CSV\n", "cyan")
        text_box.insert(tk.END, "💓 Display updates continuously (including during sleep)\n", "cyan")
        text_box.insert(tk.END, "⏰ Readings taken every 30 minutes\n", "cyan")
        text_box.insert(tk.END, "📁 CSV file: " + continuous_csv_file_path + "\n", "yellow")
        text_box.insert(tk.END, "📥 Use 'Download SD Card' to retrieve all SD data\n\n", "cyan")
        text_box.see(tk.END)
        
        connect_button.config(text="✅ Connected", bg="#00AA00", state="disabled")
        download_sd_button.config(state="normal")
        graph_button.config(state="normal")
        status_label.config(text="📊 Status: Connected - Monitoring", fg="#00BFFF")
        
        messagebox.showinfo("Connected", 
                          f"✅ Connected to {port}\n\n"
                          f"📊 30-Minute Interval Mode Active\n\n"
                          f"Readings saved to:\n{continuous_csv_file_path}\n\n"
                          f"You can now download SD card data!")
        
    except Exception as e:
        text_box.insert(tk.END, f"❌ Connection failed: {e}\n", "red")
        text_box.see(tk.END)
        messagebox.showerror("Connection Error", f"Failed to connect to {port}\n\n{e}")

# -------------------- Disconnect --------------------
def disconnect_teensy():
    """Disconnect from Teensy and stop reading thread safely"""
    global ser, is_reading, read_thread_stop, read_thread, continuous_csv_file, continuous_csv_writer

    is_reading = False
    read_thread_stop.set()
    if read_thread and read_thread.is_alive():
        read_thread.join(timeout=1.0)

    if continuous_csv_file:
        try:
            continuous_csv_file.close()
            text_box.insert(tk.END, "\n💾 CSV file saved and closed\n", "green")
            text_box.see(tk.END)
        except Exception as e:
            print(f"Error closing continuous CSV: {e}")
    
    continuous_csv_file = None
    continuous_csv_writer = None

    if ser and getattr(ser, "is_open", False):
        try:
            ser.close()
        except:
            pass
    ser = None

    text_box.insert(tk.END, "\n⚠️ DISCONNECTED\n\n", "red")
    text_box.see(tk.END)
    connect_button.config(text="🔌 Connect to Teensy", bg="#007A99", state="normal")
    download_sd_button.config(state="disabled")
    graph_button.config(state="normal")  # Keep enabled if data exists
    status_label.config(text="📊 Status: Disconnected", fg="#FF0000")
    messagebox.showinfo("Disconnected", "Serial connection closed.\nCSV file saved.")

# -------------------- Download Data --------------------
def download_data():
    """Download all sensor data to CSV"""
    global sensor_data_list

    if not sensor_data_list:
        messagebox.showwarning("No Data",
            "⚠️ No sensor data to download!\n\nConnect to Teensy and wait for scheduled readings.")
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".csv",
        filetypes=[("CSV Files", "*.csv")],
        initialfile=f"teensy_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    )

    if file_path:
        try:
            with open(file_path, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=["timestamp", "pH", "DO", "Temperature", "Pressure"])
                writer.writeheader()
                writer.writerows(sensor_data_list)

            messagebox.showinfo("Success",
                f"💾 Saved {len(sensor_data_list)} readings to:\n\n{file_path}")

            text_box.insert(tk.END, f"💾 Downloaded {len(sensor_data_list)} readings to {file_path}\n", "green")
            text_box.see(tk.END)
        except Exception as e:
            messagebox.showerror("Save Error", f"Error saving file:\n{e}")

# -------------------- GUI Setup --------------------
root = tk.Tk()
root.title("🌊 Ocean Sensor Dashboard.")
root.geometry("1000x800")
root.resizable(False, False)

def on_closing():
    global is_reading, ser, read_thread_stop, csv_file, continuous_csv_file
    is_reading = False
    read_thread_stop.set()
    
    if csv_file:
        try:
            csv_file.close()
        except:
            pass
    
    if continuous_csv_file:
        try:
            continuous_csv_file.close()
        except:
            pass
    
    try:
        if ser and getattr(ser, "is_open", False):
            ser.close()
    except:
        pass
    root.destroy()
    try:
        sys.exit(0)
    except:
        pass

root.protocol("WM_DELETE_WINDOW", on_closing)

canvas = tk.Canvas(root, width=1000, height=800, bg="#001F33", highlightthickness=0)
canvas.pack(fill="both", expand=True)

title_label = tk.Label(root, text="🌊 Teensy 4.1 - 30 Minute Interval Monitor 🌊",
                       font=("Times", 24, "bold"), fg="#00E1FF", bg="#0E0F0F")
title_label.place(x=150, y=15)

clock_label = tk.Label(root, font=("Consolas", 11, "bold"), bg="#0E0F0F", fg="white")
clock_label.place(x=850, y=20)

def update_clock():
    try:
        clock_label.config(text=time.strftime("⏰ %H:%M:%S"))
        root.after(1000, update_clock)
    except:
        pass

update_clock()

data_count_label = tk.Label(root, text="📊 Saved Readings: 0",
                           font=("Times", 14, "bold"), bg="#001F33", fg="#00FF00")
data_count_label.place(x=20, y=20)

status_label = tk.Label(root, text="📊 Status: Not Connected",
                       font=("Times", 12, "bold"), bg="#001F33", fg="#FF0000")
status_label.place(x=20, y=50)

# -------------------- Buttons --------------------
connect_button = tk.Button(root, text="🔌 Connect to Teensy", command=connect_teensy,
                           font=("Times", 12, "bold"), bg="#021519", fg="black",
                           relief="flat", width=18, height=2)
connect_button.place(x=50, y=90)

disconnect_button = tk.Button(root, text="⚠️ Disconnect", command=disconnect_teensy,
                              font=("Times", 12, "bold"), bg="#CC0000", fg="black",
                              relief="flat", width=14, height=2)
disconnect_button.place(x=290, y=90)

download_button = tk.Button(root, text="💾 Download CSV", command=download_data,
                            font=("Times", 12, "bold"), bg="#021519", fg="black",
                            relief="flat", width=15, height=2)
download_button.place(x=490, y=90)

download_sd_button = tk.Button(root, text="📥 Download SD", command=download_sd_card,
                               font=("Times", 11, "bold"), bg="#007A00", fg="black",
                               relief="flat", width=13, height=2, state="disabled")
download_sd_button.place(x=690, y=90)

graph_button = tk.Button(root, text="📊 Live Graph", command=open_graph_window,
                        font=("Times", 10, "bold"), bg="#FF8C00", fg="black",
                        relief="flat", width=12, height=1, state="disabled")
graph_button.place(x=850, y=90)

sd_graph_button = tk.Button(root, text="📥 SD Graph", command=open_sd_graph_window,
                           font=("Times", 10, "bold"), bg="#9370DB", fg="black",
                           relief="flat", width=12, height=1)
sd_graph_button.place(x=850, y=125)

panel = tk.Frame(root, bd=0, highlightbackground="#700606", highlightthickness=3, bg="#0D0D0D")
panel.place(x=50, y=160, width=900, height=600)

def create_sensor_label(parent, text, color, y):
    frame = tk.Frame(parent, bg=color, highlightthickness=0, bd=0)
    frame.place(x=80, y=y, width=740, height=65)
    label = tk.Label(frame, text=text, font=("Arial", 24, "bold"),
                     bg=color, fg="#000000", anchor="w", padx=20)
    label.pack(fill="both", expand=True)
    return label

ph_label = create_sensor_label(panel, "🌊 pH: --", "#B3F0FF", 30)
do_label = create_sensor_label(panel, "💧 DO: -- mg/L", "#FFF0B3", 110)
temp_label = create_sensor_label(panel, "🔥 Temperature: --°C", "#FFB3B3", 190)
pressure_label = create_sensor_label(panel, "🌡️ Pressure: -- mbar", "#B3FFCC", 270)

text_frame = tk.Frame(panel, bg="#001F33")
text_frame.place(x=50, y=360, width=800, height=220)

scrollbar = tk.Scrollbar(text_frame)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

text_box = tk.Text(text_frame, height=13, width=90, bg="#000B1A",
                   fg="#00FF00", font=("Consolas", 9),
                   yscrollcommand=scrollbar.set, relief="flat")
text_box.pack(side=tk.LEFT, fill="both", expand=True)
scrollbar.config(command=text_box.yview)

for color in ["blue", "green", "red", "goldenrod", "white", "cyan", "yellow"]:
    text_box.tag_config(color, foreground=color)

text_box.insert(tk.END, "🌊 TEENSY 4.1 - 30 MINUTE INTERVAL MONITOR\n", "cyan")
text_box.insert(tk.END, "=" * 80 + "\n\n", "white")
text_box.insert(tk.END, "📡 Click 'Connect to Teensy' to start monitoring\n\n", "white")
text_box.insert(tk.END, "⏰ OPERATING MODE:\n", "yellow")
text_box.insert(tk.END, "   • Teensy takes readings every 30 minutes\n", "white")
text_box.insert(tk.END, "   • Each reading is saved to SD card + GUI CSV file\n", "white")
text_box.insert(tk.END, "   • Display updates continuously (even during sleep)\n", "white")
text_box.insert(tk.END, "   • Expected ~4,320 readings over 90 days\n", "white")
text_box.insert(tk.END, "   • Serial connection remains active throughout\n\n", "white")
text_box.insert(tk.END, "💾 Click 'Download CSV' to save GUI readings\n", "white")
text_box.insert(tk.END, "📥 Click 'Download SD Card' to retrieve all SD data\n", "cyan")
text_box.insert(tk.END, "📊 Click 'View Graphs' to visualize sensor data\n\n", "yellow")
text_box.insert(tk.END, "✅ Ready to connect!\n", "green")

footer = tk.Label(root,
    text="Teensy 4.1 - 30 Min Intervals | Live Monitoring | SD + CSV Logging | Real-Time Graphs | Remote Download",
    font=("Arial", 10, "italic"), fg="#FFFFFF", bg="#001F33")
footer.place(x=90, y=770)

print("\n" + "="*70)
print("🌊 TEENSY 4.1 - 30 MINUTE INTERVAL DASHBOARD")
print("="*70)
print("Ready to connect to Teensy...")
print("\nFeatures:")
print("  • Receives data every 30 minutes from Teensy")
print("  • Displays live sensor values continuously")
print("  • Saves all scheduled readings to CSV")
print("  • Maintains connection during sleep periods")
print("  • Synchronized with Teensy SD card logging")
print("  • Download SD card data remotely via serial")
print("  • Real-time graphing and visualization")
print("="*70 + "\n")

root.mainloop()