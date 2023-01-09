import time, network
from machine import Pin, ADC, I2C
import ssd1306
import utime
import json
import mip
from umqtt.simple import MQTTClient

# Insert own values here for MQTT connection.
ssid = ""
pw = ""
broker = ""
client_id = ""
topic = ""
sub = "#"

# Board related variables.
# Other button pins 7, 8, 9
button = Pin(12, Pin.IN, Pin.PULL_UP)
led = Pin(21, Pin.OUT)
pulse = ADC(26)
#conversion_factor = 3.3 / (65535) # Pull ADC values to zero.
sda=machine.Pin(14) 
scl=machine.Pin(15) # Sda and scl pins are for the lcd screen 
i2c=machine.I2C(1, sda=sda, scl=scl, freq=400000)
display = ssd1306.SSD1306_I2C(128, 64, i2c)

# Variables used to calculate heart beat.
patient_name = "Gavril"
max_samples = 300 # Max number of values in samples array at any given time.
samples = []
avg = 0
countBeat = True # Used to check if measurement can be taken
cut_off_counter = 0 # Counter used to count how many measurements have been taken.
cut_off_limit = 30 # Max number of measurements to be taken.

measured_values = [] # Used to calculate bpm average after terminating the program

beats = [] # Array for beat times.
beat_time = 0 # Time initialized to zero.
min_treshold = 32000 # Min value to detect a heart beat.
max_treshold = 40000 # Max value to detect a heart beat.

cTime = time.localtime()

# MQTT related methods.
def mqtt_connect():
    # connect mqtt
    client = MQTTClient(client_id, broker, port = 1883, keepalive=3600)
    client.connect()
    print("Connected to MQTT Broker at: " + (broker))
    return client

def mqtt_reconnect():
    # reconnect mqtt
    print("Failed to connect to MQTT Broker. Reconnect.")
    time.sleep(5)
    machine.reset()
    
def mqtt_cb(topic, msg):
    # define mqtt callback functionality
    print(topic + ":" + msg)
    
# Uncomment following lines for network connectivity.
# wlan = network.WLAN(network.STA_IF)
# wlan.active(True)
# wlan.connect(ssid, pw)
# # mip.install('umqtt.simple')
# max_wait = 10
# while max_wait > 0:
#     if wlan.status() < 0 or wlan.status() >= 3:
#         break
#     max_wait -= 1
#     print("Waiting for connection..")
#     time.sleep(1)

# if wlan.status() != 3:
#     raise RuntimeError("network connection failed")
# else:
#     print("Connected")
#     status = wlan.ifconfig()
#     print(f"ip = {status[0]}")
#     
# try:
#     client = mqtt_connect()
# except OSError as e:
#     mqtt_reconnect()

# client.set_callback(mqtt_cb)

# Publish json data
def publish_json_data(json_file):
    client.publish(topic, json_file)

# Create json object
def create_json_data(current_bpm):
    cTime = time.localtime() # Get current time
    d = '{:02d}:{:02d}:{:02d}'.format(cTime[2], cTime[1], cTime[0]) # Format date
    t = '{:02d}:{:02d}:{:02d}'.format(cTime[3], cTime[4], cTime[5]) # Format time
    
    # Create json object
    json_file = json.dumps({"pName": patient_name, "mDate": d, "mTime": t, "bpm": current_bpm})
    print(json_file)
    # publish_json_data(json_file) # Call publish_json_data

# Welcome screen
def welcome():
    # Display text
    display.text("Push the button", 0, 0, 1)
    display.text("to start", 0, 10, 1)
    display.text("measuring.", 0, 20, 1)
    display.show()
    while True:
        if button.value() == 0: # If button is pressed.
            break

# While less than max number of measurements has been taken.
def please_wait():
    display.fill(0) # Clear display
    display.text("Please wait...", 0, 0, 1)
    display.show()

# Variables used to calculate heart rate variability by using MSSD
# (Mean of the Squared Successive Differences)
# Using RMSSD would probably be better/right solution.
values_for_hrv = []
first_time_measured = False
time_one = 0
time_two = 0

# Calculates the difference between
# two consecutive times (time_one and time_two).
def calculate_consecutive_times():
    global first_time_measured
    global time_one
    global time_two
    
    # Get first measured time to time_one.
    # After that always use time_two.
    if not first_time_measured: 
        time_one = time.time()
        first_time_measured = True
    else:
        time_two = time.time()
        
    if time_one is not 0 and time_two is not 0:
        current = (time_one - time_two)
        current = current**2
        #print(current)
        values_for_hrv.append(current) # Append current time.
        time_one = time_two # Swap second value to first for second round.

def calculate_hrv():
    calculate_hrv = sum(values_for_hrv) / (2*len(values_for_hrv))
    # print(calculated_hrv)
    return calculate_hrv

# When measuring is done.
def measuring_done():
    # Clear display and show average bpm.
    display.fill(0)
    display.text("Measuring done.", 0, 0, 1)
    # Calculate average BPM from last 15 values to get rid of the higher values measured at the beginning.
    display.text("Average BPM: %d " % (sum(measured_values[-15:]) / len(measured_values[-15:])), 0, 10, 1)
    display.text("HRV: %.4f" % calculate_hrv(), 0, 20, 1)
    display.show()
    
# Start of program
welcome()
please_wait()

while cut_off_counter is not cut_off_limit:
    led.off() # Turn led of during every cycle.
    reading = pulse.read_u16()
    
    # If reading is less than the minimum treshold allow to detect next beat
    if reading < min_treshold:
        countBeat = True
    
    # If reading is more than minimum treshold and less than maximum treshold
    # append value to samples list
    if reading > min_treshold and reading < max_treshold:
        samples.append(reading)
    
    # If samples list is full calculate average and pop first value out.
    if len(samples) is max_samples:
        avg = (sum(samples) / len(samples))
        samples.pop(0)

        # If current reading is above average and countBeat is True
        # time is appended to the beats list.
        # When beats list has more than 30 values, an accurate measurement
        # can be achieved.
        if reading > avg and countBeat:
            countBeat = False # Prevent counting beats.
            beats.append(time.time()) # Append time.
            # print(beats)
            beats = beats[-30:] # Get the last 30 items from beats list.
            beat_time = beats[-1] - beats[0] # Check if value is positive.
            if beat_time:
                bpm = (len(beats) / (beat_time)) * 60
                bpm = float("{:.2f}".format(bpm)) # Limit decimals to two.
                if bpm > 50 and bpm < 200:
                    calculate_consecutive_times()
                    print(f"BPM: {bpm}")
                    display.fill(0) # Clear display and show text content
                    display.text("Patient name: ", 0, 0, 1)
                    display.text("%s " % patient_name, 0, 10, 2)
                    display.text("%d bpm" % bpm, 0, 20, 3)
                    display.show() # Show display
                    measured_values.append(bpm) # Append bpm for bpm average calculation
                    create_json_data(bpm) # Create json data
                    cut_off_counter += 1
                led.on()  
    utime.sleep(0.01)
    
measuring_done()
