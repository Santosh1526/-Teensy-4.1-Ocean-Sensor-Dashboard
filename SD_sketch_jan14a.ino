/***
▗▖ ▗▖▗▖  ▗▖▗▄▄▄ ▗▄▄▄▖▗▄▄▖ ▗▖ ▗▖ ▗▄▖▗▄▄▄▖▗▄▄▄▖▗▄▄▖      ▗▄▄▖▗▄▄▄▖▗▖  ▗▖ ▗▄▄▖ ▗▄▖ ▗▄▄▖      ▗▄▄▖▗▖  ▗▖▗▄▄▖▗▄▄▄▖▗▄▄▄▖▗▖  ▗▖
▐▌ ▐▌▐▛▚▖▐▌▐▌  █▐▌   ▐▌ ▐▌▐▌ ▐▌▐▌ ▐▌ █  ▐▌   ▐▌ ▐▌    ▐▌   ▐▌   ▐▛▚▖▐▌▐▌   ▐▌ ▐▌▐▌ ▐▌    ▐▌    ▝▚▞▘▐▌     █  ▐▌   ▐▛▚▞▜▌
▐▌ ▐▌▐▌ ▝▜▌▐▌  █▐▛▀▀▘▐▛▀▚▖▐▌ ▐▌▐▛▀▜▌ █  ▐▛▀▀▘▐▛▀▚▖     ▝▀▚▖▐▛▀▀▘▐▌ ▝▜▌ ▝▀▚▖▐▌ ▐▌▐▛▀▚▖     ▝▀▚▖  ▐▌  ▝▀▚▖  █  ▐▛▀▀▘▐▌  ▐▌
▝▚▄▞▘▐▌  ▐▌▐▙▄▄▀▐▙▄▄▖▐▌ ▐▌▐▙█▟▌▐▌ ▐▌ █  ▐▙▄▄▖▐▌ ▐▌    ▗▄▄▞▘▐▙▄▄▖▐▌  ▐▌▗▄▄▞▘▝▚▄▞▘▐▌ ▐▌    ▗▄▄▞▘  ▐▌ ▗▄▄▞▘  █  ▐▙▄▄▖▐▌  ▐▌

Teensy 4.1 - GUI Synchronized Version with Remote SD Download
pH | DO | Temp | SD | Sleep | Pressure
VERSION: GUI Sync - 30 Min Intervals - Serial Always Active - Remote SD Download                                                                                                                                                                                                                                                                                                                                    
*/

#include <Arduino.h>
#include <Wire.h>
#include <SD.h>
#include <TimeLib.h>
#include "TSYS01.h"
#include "MS5837.h"

// ==================== CONFIGURATION ====================
#define USB_BAUD_RATE 115200
#define CHIP_SELECT BUILTIN_SDCARD
#define SLEEP_INTERVAL_MINUTES 30

// Pin definitions
#define PH_PIN A0
#define DO_PIN A1

// pH sensor settings
#define PH_OFFSET 0.19
#define PH_SAMPLING_INTERVAL 20
#define PH_ARRAY_LENGTH 40
#define VOLTAGE_REFERENCE 3.3

// DO sensor settings
#define VREF_DO 3300
#define ADC_RES 1024
#define TWO_POINT_CALIBRATION 1
#define CAL1_V 1274
#define CAL1_T 28
#define CAL2_V 1262
#define CAL2_T 21

// ==================== GLOBAL OBJECTS ====================
MS5837 pressure_sensor;
TSYS01 temp_sensor;

// Sensor availability flags
bool temp_sensor_ok = false;
bool pressure_sensor_ok = false;
bool sd_available = false;

// Reading counter
uint32_t reading_counter = 0;

// pH sampling array
int pH_array[PH_ARRAY_LENGTH];

// Next wake time (unix timestamp)
time_t nextWakeTime;

// System start time
time_t systemStartTime;

// Current sensor values (for GUI updates during sleep)
float current_pH = 0.0;
float current_DO = 0.0;
float current_temp = 0.0;
float current_pressure = 0.0;

// ==================== DO TABLE ====================
const uint16_t DO_Table[41] = {
  14460, 14220, 13820, 13440, 13090, 12740, 12420, 12110, 11810, 11530,
  11260, 11010, 10770, 10530, 10300, 10080, 9860, 9660, 9460, 9270,
  9080, 8900, 8730, 8570, 8410, 8250, 8110, 7960, 7820, 7690,
  7560, 7430, 7300, 7180, 7070, 6950, 6840, 6730, 6630, 6530, 6410
};

// ==================== FORWARD DECLARATIONS ====================
time_t getCompileTime();
int16_t readDO(uint32_t voltage_mv, uint8_t temperature_c);
double averageArray(int* arr, int number);
void loadReadingCounter();
void saveReadingCounter();
void createDatalogHeader();
void initPeripherals();
void printRuntimeStats();
void sendToGUI(float pH, float DO_mgL, float temp, float press_mbar, bool isSavedReading);
void downloadSDCard();
void performReading();
void setNextWakeTime();
bool isTimeToRead();
void lowPowerSleep();

// ==================== FUNCTIONS ====================

/**
 * Get compile time as Unix timestamp
 */
time_t getCompileTime() {
  const char *date = __DATE__;
  const char *time = __TIME__;
  
  char month_str[4];
  int day, year, hour, min, sec;
  
  sscanf(date, "%s %d %d", month_str, &day, &year);
  sscanf(time, "%d:%d:%d", &hour, &min, &sec);
  
  int month = 1;
  const char *months[] = {"Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"};
  for (int i = 0; i < 12; i++) {
    if (strcmp(month_str, months[i]) == 0) {
      month = i + 1;
      break;
    }
  }
  
  tmElements_t tm;
  tm.Year = year - 1970;
  tm.Month = month;
  tm.Day = day;
  tm.Hour = hour;
  tm.Minute = min;
  tm.Second = sec;
  
  return makeTime(tm);
}

/**
 * Calculate dissolved oxygen concentration
 */
int16_t readDO(uint32_t voltage_mv, uint8_t temperature_c) {
  if (temperature_c > 40) temperature_c = 40;
  
  #if TWO_POINT_CALIBRATION == 0
    uint16_t V_saturation = CAL1_V + 35 * (temperature_c - CAL1_T);
    return (voltage_mv * DO_Table[temperature_c]) / V_saturation;
  #else
    uint16_t V_saturation = ((int16_t)(temperature_c - CAL2_T)) *
                            (CAL1_V - CAL2_V) /
                            (CAL1_T - CAL2_T) + CAL2_V;
    return (voltage_mv * DO_Table[temperature_c]) / V_saturation;
  #endif
}

/**
 * Calculate average of array, excluding min/max values
 */
double averageArray(int* arr, int number) {
  if (number <= 0) return 0;
  
  if (number < 5) {
    long total = 0;
    for (int i = 0; i < number; i++) {
      total += arr[i];
    }
    return (double)total / number;
  }
  
  int minVal = arr[0], maxVal = arr[0];
  long total = 0;
  
  for (int i = 0; i < number; i++) {
    if (arr[i] < minVal) minVal = arr[i];
    if (arr[i] > maxVal) maxVal = arr[i];
    total += arr[i];
  }
  
  total = total - minVal - maxVal;
  return (double)total / (number - 2);
}

/**
 * Load reading counter from SD card
 */
void loadReadingCounter() {
  if (!sd_available) {
    reading_counter = 0;
    return;
  }
  
  if (SD.exists("counter.txt")) {
    File f = SD.open("counter.txt", FILE_READ);
    if (f) {
      String line = f.readStringUntil('\n');
      reading_counter = line.toInt();
      f.close();
      Serial.print("[Counter] Loaded from SD: ");
      Serial.println(reading_counter);
    }
  } else {
    reading_counter = 0;
    Serial.println("[Counter] Starting fresh from 0");
  }
}

/**
 * Save reading counter to SD card
 */
void saveReadingCounter() {
  if (!sd_available) return;
  
  if (SD.exists("counter.txt")) {
    SD.remove("counter.txt");
  }
  
  File f = SD.open("counter.txt", FILE_WRITE);
  if (f) {
    f.println(reading_counter);
    f.close();
  }
}

/**
 * Create Datalog.txt header if it doesn't exist
 */
void createDatalogHeader() {
  if (!sd_available) return;
  
  if (!SD.exists("Datalog.txt")) {
    File f = SD.open("Datalog.txt", FILE_WRITE);
    if (f) {
      f.println("================================================================================");
      f.println("                    TEENSY 4.1 WATER QUALITY DATA LOG");
      f.println("                   CONTINUOUS 3 MONTH MONITORING SYSTEM");
      f.println("                          30 MINUTE INTERVALS");
      f.println("================================================================================");
      f.println();
      f.print("System Started: ");
      f.printf("%02d/%02d/%04d at %02d:%02d:%02d\n",
               day(systemStartTime), month(systemStartTime), year(systemStartTime),
               hour(systemStartTime), minute(systemStartTime), second(systemStartTime));
      f.println();
      f.println("Expected Total Readings: ~4,320 (30 min intervals for 90 days)");
      f.println();
      f.println("================================================================================");
      f.println();
      f.close();
      Serial.println("[FILE] Datalog.txt header created");
    }
  }
}

/**
 * Initialize all peripherals
 */
void initPeripherals() {
  Wire.begin();
  delay(100);
  
  analogReadResolution(10);
  
  // Initialize temperature sensor
  temp_sensor_ok = false;
  for (int i = 0; i < 3; i++) {
    if (temp_sensor.init()) {
      temp_sensor_ok = true;
      break;
    }
    delay(200);
  }
  
  // Initialize pressure sensor
  pressure_sensor.setModel(MS5837::MS5837_30BA);
  pressure_sensor.setFluidDensity(997);
  pressure_sensor_ok = false;
  for (int i = 0; i < 3; i++) {
    if (pressure_sensor.init()) {
      pressure_sensor_ok = true;
      break;
    }
    delay(200);
  }
}

/**
 * Calculate runtime statistics
 */
void printRuntimeStats() {
  time_t currentTime = now();
  unsigned long runtimeSeconds = currentTime - systemStartTime;
  unsigned long days = runtimeSeconds / 86400;
  unsigned long hours = (runtimeSeconds % 86400) / 3600;
  unsigned long minutes = (runtimeSeconds % 3600) / 60;
  
  Serial.println("\n╔════════════════════════════════════════╗");
  Serial.println("║         RUNTIME STATISTICS             ║");
  Serial.println("╚════════════════════════════════════════╝");
  Serial.printf("Total Runtime: %lu days, %lu hours, %lu minutes\n", days, hours, minutes);
  Serial.printf("Total Readings: %lu\n", reading_counter);
  Serial.printf("Expected Readings: %lu\n", (runtimeSeconds / 1800) + 1);
  Serial.printf("Remaining Days: ~%lu days until 90 days\n", 90 - days);
  Serial.println();
}

/**
 * Send data to GUI in standardized format
 */
void sendToGUI(float pH, float DO_mgL, float temp, float press_mbar, bool isSavedReading) {
  // Send in $Params format (scaled integers for transmission)
  // pH*100, DO*10, Temp*50, Pressure*1000
  Serial.print("$Params,");
  Serial.print((int)(pH * 100));
  Serial.print(",");
  Serial.print((int)(DO_mgL * 10));
  Serial.print(",");
  Serial.print((int)(temp * 50));
  Serial.print(",");
  Serial.print((int)(press_mbar * 1000));
  
  // Add flag to indicate if this was saved to SD
  if (isSavedReading) {
    Serial.println(",SAVED");
  } else {
    Serial.println(",LIVE");
  }
}

/**
 * Download SD card data via serial
 */
void downloadSDCard() {
  if (!sd_available) {
    Serial.println("SD_DOWNLOAD_ERROR: SD card not available");
    return;
  }
  
  if (!SD.exists("Datalog.txt")) {
    Serial.println("SD_DOWNLOAD_ERROR: Datalog.txt does not exist");
    return;
  }
  
  Serial.println("SD_DOWNLOAD_PROGRESS: Starting SD card download...");
  delay(100);
  
  File dataFile = SD.open("Datalog.txt", FILE_READ);
  if (!dataFile) {
    Serial.println("SD_DOWNLOAD_ERROR: Failed to open Datalog.txt");
    return;
  }
  
  unsigned long fileSize = dataFile.size();
  unsigned long bytesSent = 0;
  int lineCount = 0;
  
  Serial.print("SD_DOWNLOAD_PROGRESS: File size = ");
  Serial.print(fileSize);
  Serial.println(" bytes");
  delay(100);
  
  // Read and send file line by line
  while (dataFile.available()) {
    String line = dataFile.readStringUntil('\n');
    Serial.println(line);
    
    bytesSent += line.length() + 1;
    lineCount++;
    
    // Send progress update every 100 lines
    if (lineCount % 100 == 0) {
      Serial.print("SD_DOWNLOAD_PROGRESS: Sent ");
      Serial.print(lineCount);
      Serial.print(" lines (");
      Serial.print((bytesSent * 100) / fileSize);
      Serial.println("%)");
      delay(50);
    }
    
    delay(5);
  }
  
  dataFile.close();
  
  Serial.print("SD_DOWNLOAD_PROGRESS: Transfer complete - ");
  Serial.print(lineCount);
  Serial.println(" lines sent");
  delay(100);
  
  Serial.println("SD_DOWNLOAD_END");
  Serial.flush();
}

/**
 * Take readings and save to Datalog.txt
 */
void performReading() {
  unsigned long reading_start = millis();
  
  time_t currentTime = now();
  reading_counter++;
  
  Serial.println("\n════════════════════════════════════════");
  Serial.print("READING #");
  Serial.println(reading_counter);
  Serial.printf("Time: %02d/%02d/%04d %02d:%02d:%02d\n",
    day(currentTime), month(currentTime), year(currentTime),
    hour(currentTime), minute(currentTime), second(currentTime));
  Serial.println("════════════════════════════════════════\n");
  
  // ===== pH READING =====
  Serial.print("[pH] Sampling... ");
  for (int i = 0; i < PH_ARRAY_LENGTH; i++) {
    pH_array[i] = analogRead(PH_PIN);
    delay(PH_SAMPLING_INTERVAL);
  }
  
  float pH_voltage = averageArray(pH_array, PH_ARRAY_LENGTH) * VOLTAGE_REFERENCE / 1024.0;
  current_pH = 3.5 * pH_voltage + PH_OFFSET;
  Serial.print(current_pH, 2);
  Serial.println(" pH");
  
  // ===== TEMPERATURE READING =====
  current_temp = 25.0;
  if (temp_sensor_ok) {
    temp_sensor.read();
    current_temp = temp_sensor.temperature();
    Serial.print("[Temp] ");
    Serial.print(current_temp, 2);
    Serial.println(" °C");
  } else {
    Serial.println("[Temp] Using default 25°C");
  }
  
  // ===== PRESSURE READING =====
  current_pressure = 0.0;
  if (pressure_sensor_ok) {
    pressure_sensor.read();
    current_pressure = pressure_sensor.pressure();
    Serial.print("[Pressure] ");
    Serial.print(current_pressure, 2);
    Serial.println(" mbar");
  } else {
    Serial.println("[Pressure] Unavailable");
  }
  
  // ===== DO READING =====
  uint8_t temp_for_do = (uint8_t)constrain(current_temp, 0, 40);
  uint16_t do_adc_raw = analogRead(DO_PIN);
  uint32_t do_voltage_mv = (uint32_t(VREF_DO) * do_adc_raw) / ADC_RES;
  int16_t do_value_ugL = readDO(do_voltage_mv, temp_for_do);
  current_DO = do_value_ugL / 1000.0;
  
  Serial.print("[DO] ");
  Serial.print(do_value_ugL);
  Serial.print(" ug/L (");
  Serial.print(current_DO, 2);
  Serial.println(" mg/L)");
  
  unsigned long reading_duration = millis() - reading_start;
  Serial.print("[Duration] ");
  Serial.print(reading_duration);
  Serial.println(" ms\n");
  
  sendToGUI(current_pH, current_DO, current_temp, current_pressure, true);
  
  // ===== SAVE TO SD CARD =====
  if (sd_available) {
    Serial.println("Saving to Datalog.txt...");
    
    File dataFile = SD.open("Datalog.txt", FILE_WRITE);
    if (dataFile) {
      dataFile.println("--------------------------------------------------------------------------------");
      dataFile.print("Reading ID: ");
      dataFile.println(reading_counter);
      dataFile.printf("Date & Time: %02d/%02d/%04d at %02d:%02d:%02d\n",
                      day(currentTime), month(currentTime), year(currentTime),
                      hour(currentTime), minute(currentTime), second(currentTime));
      
      unsigned long runtimeSeconds = currentTime - systemStartTime;
      unsigned long days = runtimeSeconds / 86400;
      unsigned long hours = (runtimeSeconds % 86400) / 3600;
      dataFile.printf("Runtime: %lu days, %lu hours\n", days, hours);
      dataFile.println();
      
      dataFile.print("pH Voltage: ");
      dataFile.print(pH_voltage, 3);
      dataFile.println(" V");
      dataFile.print("pH Value: ");
      dataFile.println(current_pH, 2);
      dataFile.print("Temperature: ");
      dataFile.print(current_temp, 2);
      dataFile.print(" °C [Sensor: ");
      dataFile.print(temp_sensor_ok ? "OK" : "FAIL");
      dataFile.println("]");
      dataFile.print("Pressure: ");
      dataFile.print(current_pressure, 2);
      dataFile.print(" mbar [Sensor: ");
      dataFile.print(pressure_sensor_ok ? "OK" : "FAIL");
      dataFile.println("]");
      dataFile.print("DO Voltage: ");
      dataFile.print(do_voltage_mv);
      dataFile.println(" mV");
      dataFile.print("DO Concentration: ");
      dataFile.print(do_value_ugL);
      dataFile.print(" ug/L (");
      dataFile.print(current_DO, 2);
      dataFile.println(" mg/L)");
      dataFile.print("Reading Duration: ");
      dataFile.print(reading_duration);
      dataFile.println(" ms");
      dataFile.println();
      
      dataFile.close();
      
      Serial.println("✓ Data saved to Datalog.txt");
      Serial.println("✓ Data sent to GUI");
    } else {
      Serial.println("✗ FAILED to open Datalog.txt");
    }
    
    saveReadingCounter();
    Serial.println("✓ Counter saved");
    
  } else {
    Serial.println("✗ SD CARD NOT AVAILABLE - DATA NOT SAVED!");
  }
  
  if (reading_counter % 48 == 0) {
    printRuntimeStats();
  }
  
  Serial.println("════════════════════════════════════════\n");
}

/**
 * Calculate next wake time
 */
void setNextWakeTime() {
  time_t currentTime = now();
  nextWakeTime = currentTime + (SLEEP_INTERVAL_MINUTES * 60);
  
  Serial.print("Next reading scheduled: ");
  Serial.printf("%02d/%02d/%04d %02d:%02d:%02d\n",
    day(nextWakeTime), month(nextWakeTime), year(nextWakeTime),
    hour(nextWakeTime), minute(nextWakeTime), second(nextWakeTime));
}

/**
 * Check if it's time to take a reading
 */
bool isTimeToRead() {
  return now() >= nextWakeTime;
}

/**
 * Low power sleep with periodic heartbeat
 */
void lowPowerSleep() {
  Serial.println("\n╔════════════════════════════════════════╗");
  Serial.println("║      ENTERING LOW POWER MODE           ║");
  Serial.println("╚════════════════════════════════════════╝");
  Serial.print("Sleep duration: ");
  Serial.print(SLEEP_INTERVAL_MINUTES);
  Serial.println(" minutes");
  
  setNextWakeTime();
  
  Serial.println("Sleeping... (GUI will remain connected)\n");
  Serial.flush();
  
  digitalWrite(LED_BUILTIN, LOW);
  
  unsigned long lastHeartbeat = millis();
  const unsigned long HEARTBEAT_INTERVAL = 30000;
  
  while (!isTimeToRead()) {
    if (Serial.available() > 0) {
      String command = Serial.readStringUntil('\n');
      command.trim();
      
      if (command == "DOWNLOAD_SD") {
        Serial.println("\n════════════════════════════════════════");
        Serial.println("   SD DOWNLOAD REQUEST (DURING SLEEP)");
        Serial.println("════════════════════════════════════════\n");
        
        downloadSDCard();
        
        Serial.println("\n════════════════════════════════════════");
        Serial.println("   SD DOWNLOAD COMPLETE");
        Serial.println("   Resuming sleep...");
        Serial.println("════════════════════════════════════════\n");
        
        while (Serial.available() > 0) {
          Serial.read();
        }
      }
    }
    
    delay(10000);
    
    if (millis() - lastHeartbeat >= HEARTBEAT_INTERVAL) {
      sendToGUI(current_pH, current_DO, current_temp, current_pressure, false);
      lastHeartbeat = millis();
    }
    
    digitalWrite(LED_BUILTIN, HIGH);
    delay(50);
    digitalWrite(LED_BUILTIN, LOW);
  }
  
  Serial.println("\n╔════════════════════════════════════════╗");
  Serial.println("║         WAKING UP - TIME TO READ       ║");
  Serial.println("╚════════════════════════════════════════╝\n");
  
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(100);
    digitalWrite(LED_BUILTIN, LOW);
    delay(100);
  }
}

// ==================== SETUP ====================
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  
  for (int i = 0; i < 5; i++) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(200);
    digitalWrite(LED_BUILTIN, LOW);
    delay(200);
  }
  
  Serial.begin(USB_BAUD_RATE);
  
  unsigned long start = millis();
  while (!Serial && (millis() - start < 3000)) {
    delay(10);
  }
  
  Serial.println("\n");
  Serial.println("════════════════════════════════════════════════════════════════");
  Serial.println("        TEENSY 4.1 WATER QUALITY MONITORING SYSTEM");
  Serial.println("           GUI SYNCHRONIZED VERSION");
  Serial.println("              30 MINUTE READING INTERVALS");
  Serial.println("════════════════════════════════════════════════════════════════");
  Serial.println();
  Serial.println("System Features:");
  Serial.println("  ✓ Automatic time setting from compile time");
  Serial.println("  ✓ 30-minute interval readings");
  Serial.println("  ✓ ~4,320 readings over 90 days");
  Serial.println("  ✓ Continuous GUI connection");
  Serial.println("  ✓ Serial heartbeat during sleep");
  Serial.println("  ✓ SD card data logging");
  Serial.println("  ✓ Remote SD card download via serial");
  Serial.println();
  Serial.println("════════════════════════════════════════════════════════════════\n");
  
  Wire.begin();
  
  Serial.println("[TIME] Setting system time from compile time...");
  systemStartTime = getCompileTime();
  setTime(systemStartTime);
  
  Serial.print("✓ System time set to: ");
  Serial.printf("%02d/%02d/%04d %02d:%02d:%02d\n",
    day(), month(), year(),
    hour(), minute(), second());
  Serial.println("✓ Time will continue running automatically");
  Serial.println();
  
  Serial.println("[INIT] SD card...");
  sd_available = false;
  
  for (int i = 0; i < 5; i++) {
    if (SD.begin(CHIP_SELECT)) {
      sd_available = true;
      Serial.println("✓ SD card ready");
      break;
    }
    delay(500);
  }
  
  if (!sd_available) {
    Serial.println("✗ SD CARD FAILED!");
    Serial.println("⚠ CRITICAL: Data will NOT be saved!");
    Serial.println("⚠ Please check SD card and restart system");
    Serial.println("Continuing anyway for testing...\n");
  } else {
    loadReadingCounter();
    createDatalogHeader();
  }
  
  Serial.println();
  Serial.println("[INIT] Initializing sensors...");
  initPeripherals();
  
  if (temp_sensor_ok) {
    Serial.println("✓ Temperature sensor: OK");
  } else {
    Serial.println("⚠ Temperature sensor: FAILED (will use 25°C default)");
  }
  
  if (pressure_sensor_ok) {
    Serial.println("✓ Pressure sensor: OK");
  } else {
    Serial.println("⚠ Pressure sensor: FAILED (readings will be 0)");
  }
  
  Serial.println();
  Serial.println("════════════════════════════════════════════════════════════════");
  Serial.println("                   INITIALIZATION COMPLETE");
  Serial.println("              STARTING 3 MONTH MEASUREMENT CYCLE");
  Serial.println("════════════════════════════════════════════════════════════════");
  Serial.println();
  Serial.println("Expected completion date: ~90 days from now");
  Serial.println("Total expected readings: ~4,320");
  Serial.println("GUI connection: ACTIVE");
  Serial.println("Remote SD download: ENABLED");
  Serial.println();
  
  delay(2000);
}

// ==================== LOOP ====================
void loop() {
  if (Serial.available() > 0) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command == "DOWNLOAD_SD") {
      Serial.println("\n════════════════════════════════════════");
      Serial.println("   SD CARD DOWNLOAD REQUEST RECEIVED");
      Serial.println("════════════════════════════════════════\n");
      
      downloadSDCard();
      
      Serial.println("\n════════════════════════════════════════");
      Serial.println("   SD DOWNLOAD COMPLETE");
      Serial.println("   Continuing with monitoring cycle...");
      Serial.println("════════════════════════════════════════\n");
      
      while (Serial.available() > 0) {
        Serial.read();
      }
    }
  }
  
  if (isTimeToRead()) {
    initPeripherals();
    performReading();
    lowPowerSleep();
  }
  
  delay(1000);
}
  
