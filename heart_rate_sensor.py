import time, network
from machine import Pin, ADC, I2C
import ssd1306
import utime
import json
import mip
from umqtt.simple import MQTTClient

ssid = ""
pw = ""
broker = ""
client_id = ""
topic = ""
sub = "#"
button = Pin(12, Pin.IN, Pin.PULL_UP)
led = Pin(21, Pin.OUT)
pulse = ADC(26)
#conversion_factor = 3.3 / (65535)
# Other button pins 7, 8, 9

sda=machine.Pin(14) 
scl=machine.Pin(15) # Sda and scl pins are for the lcd screen 
i2c=machine.I2C(1, sda=sda, scl=scl, freq=400000)
display = ssd1306.SSD1306_I2C(128, 64, i2c)

patient_name = ""
max_samples = 300
samples = []
avg = 0
countBeat = True # Used to check if measurement can be taken
cut_off_counter = 0
cut_off_limit = 30 # Max number of taken measurements

measured_values = [] # Used to calculate bpm average after terminating the program

beats = []
beat_time = 0
min_treshold = 32000
max_treshold = 40000

cTime = time.localtime()

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
    

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, pw)
# mip.install('umqtt.simple')
max_wait = 10
while max_wait > 0:
    if wlan.status() < 0 or wlan.status() >= 3:
        break
    max_wait -= 1
    print("Waiting for connection..")
    time.sleep(1)

if wlan.status() != 3:
    raise RuntimeError("network connection failed")
else:
    print("Connected")
    status = wlan.ifconfig()
    print(f"ip = {status[0]}")
    
try:
    client = mqtt_connect()
except OSError as e:
    mqtt_reconnect()

# client.set_callback(mqtt_cb)

# Publish json data
def publish_json_data(href):
    client.publish(topic, href)

# Create json object
def create_json_data(bpm_loc):
    cTime = time.localtime() # Get current time
    d = '{:02d}:{:02d}:{:02d}'.format(cTime[2], cTime[1], cTime[0]) # Format date
    t = '{:02d}:{:02d}:{:02d}'.format(cTime[3], cTime[4], cTime[5]) # Format time
    
    # Create json object
    href = json.dumps({"pName": patient_name, "mDate": d, "mTime": t, "bpm": bpm_loc})
    # print(href)
    publish_json_data(href) # Call publish_json_data
    

# Display text
display.text("Push the button", 0, 0, 1)
display.text("to start", 0, 10, 1)
display.text("measuring.", 0, 20, 1)
display.show()

while True:
    if button.value() == 0: # If button is pressed.
        break

display.fill(0) # Clear display
display.text("Please wait...", 0, 0, 1)
display.show()

while cut_off_counter is not cut_off_limit:
    led.off()
    reading = pulse.read_u16()
    
    # If reading is less than the minimum treshold allow to detect next beat
    if reading < min_treshold:
        countBeat = True
        # pass
    
    # If reading is more than minimum treshold and less than maximum treshold
    # append value to samples list
    if reading > min_treshold and reading < max_treshold:
        samples.append(reading)
    
    # If samples list is full calculate average.
    if len(samples) is max_samples:
        avg = (sum(samples) / len(samples))
        samples.pop()

        # If current reading is above average and countBeat is True
        # time is appended to the beats list.
        # When beats list has more than 30 values, an accurate measurement
        # can be achieved.
        if reading > avg and countBeat:
            countBeat = False # Prevent counting beats.
            beats.append(time.time()) # Append time.
            # print(beats)
            beats = beats[-30:] # Get the last 30 items from beats list.
            beat_time = beats[-1] - beats[0] # Check if value is more than one.
            if beat_time:
                bpm = (len(beats) / (beat_time)) * 60
                bpm = float("{:.2f}".format(bpm)) # Limit decimals to two.
                if bpm > 50 and bpm < 200:
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
    
# Clear display and show average bpm.
display.fill(0)
display.text("Measuring done.", 0, 0, 1)
display.text("Average BPM: %d " % (sum(measured_values) / len(measured_values)), 0, 10, 1)
display.show()
