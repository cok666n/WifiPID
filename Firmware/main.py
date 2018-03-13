import ubinascii as binascii
from umqtt.robust import MQTTClient
import config
import time
import machine
from machine import Pin
from machine import Timer
import onewire, ds18x20
import network
from PID import PID
import urandom

#define a couple constants
machine_id = binascii.hexlify(machine.unique_id())
client_id= machine_id + str(urandom.getrandbits(24))
print(b"Machine ID: {}".format(machine_id))
print(b"Client ID: {}".format(client_id))

#set wemos D1 pin numbers for easier handling
D0 = Pin(16, Pin.OUT)
D0.value(0)
D1 = Pin(5, Pin.OUT)
D1.value(0)
D2 = Pin(4, Pin.OUT)
D2.value(0)
D3 = Pin(0, Pin.OUT)
D3.value(0)
D4 = Pin(2, Pin.OUT)
D4.value(0)
D5 = Pin(14, Pin.OUT)
D5.value(0)
D6 = Pin(12, Pin.OUT)
D6.value(0)
D7 = Pin(13, Pin.OUT)
D7.value(0)
D8 = Pin(15, Pin.OUT)
D8.value(0)

RELAY_COOL = D0
RELAY_HEAT = D1 # Heat relay is on D1 (PIN5)
LED = D4 # Onboard led is on D4 (PIN2)
TIMER_INTERVAL=1000 #1000msec interval to count seconds.
PUBLISH_INTERVAL=30


#defaults
PID_RUNNING = False
PID_CYCLE_S = 10
PID_SECONDSCOUNTER = 0
SECONDSCOUNTER = 0


def setRelayHeat(valueonoff):
    if RELAY_HEAT.value() != valueonoff :
        RELAY_HEAT.value(valueonoff)
        publish_relay()

def setRelayCool(valueonoff):
    if RELAY_COOL.value() != valueonoff :
        RELAY_COOL.value(valueonoff)
        publish_relay()


#function de controle de la led onboard du wemos, logique inverse.
def setLed(valueonoff):
    if(valueonoff==1):
        LED.value(0)
    else:
        LED.value(1)
    publish_led()

# lit la temperature de tous les capteurs trouv�s mais retourne juste la derniere recue.
def readTemp():
    # the device is on GPIO4/D2
    dat = D2

    # create the onewire object
    ds = ds18x20.DS18X20(onewire.OneWire(dat))

    # scan for devices on the bus
    roms = ds.scan()
    #print('found devices:', roms)

    # loop and print all temperatures
    #print('temperatures:', end=' ')
    ds.convert_temp()
    time.sleep_ms(750)
    for rom in roms:
        retval = ds.read_temp(rom)
    #print("Current temp : { }",retval)
    return retval
		
# MQTT Callback
def callback(topic, msg):
    global PUBLISH_INTERVAL,pid
    target = topic.decode().split('/')[-1]
    message = msg.decode()
    print("Received MQTT Message for topic {} : {}".format(target,msg)) 

    try:       
        if target == "RelayHeat":
            value = 1 if int(msg) > 0 else 0
            setRelayHeat(value)
        if target == "RelayCool":
            value = 1 if int(msg) > 0 else 0
            setRelayCool(value)
        elif target == "Led":
            value = 1 if int(msg) > 0 else 0
            setLed(value)
        elif target == "Publish_interval":
            if int(message) > 0 :
                PUBLISH_INTERVAL=int(msg)
        elif target == "Read_temp":
            if int(message) > 0 :
                publish_temp()
        elif target == "get_ip":
            if int(message) > 0 :
                publish_ip()
        elif target == "get_sts":
            if int(message) > 0 :
                publish_sts()
                publish_pid()
        elif target == "SetPoint":
            if float(message) > 0 :
                pid.set_point = float(message)
                publish_pid()
        elif target == "P":
            if float(message) > 0 :
                pid.Kp = float(message)
                publish_pid()
        elif target == "I":
            if float(message) > 0 :
                pid.Ki = float(message)
                publish_pid()
        elif target == "D":
            if float(message) > 0 :
                pid.Kd= float(message)
                publish_pid()
        elif target == "PID_Running":
            value = 1 if int(message) > 0 else 0
            if value == 1 :
                startPID()
            else:
                stopPID()
        else:
            print("Unable to process MQTT request")
    except Exception as e:
        print("Exception processing MQTT", str(e))

# command and status, custom MQTT broker.
def connect_and_subscribe():
    global client
    print('Connecting to {}:{} as user {} with password {}'.format(config.broker, config.port, config.user, config.password))
    client = MQTTClient(client_id, config.broker, port=config.port, user=config.user, password=config.password)
    client.set_callback(callback)
    if not client.connect(clean_session=False):
        print("Created new session to {}".format(config.broker))
        topic = b"/" + machine_id + b"/cmd/+"
        client.subscribe(topic)
        print("Subscribed to {}".format(topic))

# Adafruit mqtt client for datalogging purposes
def connect_and_subscribe_adafruit():
    global clientAda
    print('Connecting to Adafruit')
    clientAda = MQTTClient(machine_id, "io.adafruit.com", user="joey_teknome", password="f513cbf5a4d643a09114c959980f1d67")  
    clientAda.connect()
    print("Connected to Adafruit IO")
	
def publish_sts():
    print("publish_sts")
    publish_ip()
    publish_led()
    publish_relay()
    publish_temp()
    publish_pid()
    
def publish_temp():
    topic = b"/" + machine_id + b"/sts/Temp"
    ctemp = readTemp()
    client.publish(topic,str(ctemp))
    clientAda.publish(b"joey_teknome/feeds/wemos-temperature",str(ctemp))
    clientAda.publish(b"joey_teknome/feeds/set-point",str(pid.set_point))
    print("PUB Temp: {} PUB SetPoint: {}".format(str(ctemp),str(pid.set_point)))

def publish_relay():
    topic = b"/" + machine_id + b"/sts/RelayHeat"
    client.publish(topic, str(RELAY_HEAT.value()))
    print("PUB Relay Heat: {}".format(str(RELAY_HEAT.value())))
    topic = b"/" + machine_id + b"/sts/RelayCool"
    client.publish(topic, str(RELAY_COOL.value()))
    print("PUB Relay Cool: {}".format(str(RELAY_COOL.value())))

def publish_led():
    topic = b"/" + machine_id + b"/sts/Led"
    if LED.value()==1 :
        client.publish(topic, "0")
    else:
        client.publish(topic, "1")
        
    print("PUB Led: {}".format(str(LED.value())))

def publish_ip():
    sta_if = network.WLAN(network.STA_IF)        
    topic = b"/" + machine_id + b"/sts/IP"
    client.publish(topic, sta_if.ifconfig()[0])
    print("PUB IP: {}".format(sta_if.ifconfig()[0]))

def publish_pid():
    global pid
    topic = b"/" + machine_id + b"/sts/P"
    client.publish(topic,str(pid.Kp))
    topic = b"/" + machine_id + b"/sts/I"
    client.publish(topic, str(pid.Ki))
    topic = b"/" + machine_id + b"/sts/D"
    client.publish(topic, str(pid.Kd))
    topic = b"/" + machine_id + b"/sts/PID_Output"
    client.publish(topic, str(pid.output))
    clientAda.publish(b"joey_teknome/feeds/pwm-output",str(pid.output))
    topic = b"/" + machine_id + b"/sts/SetPoint"
    client.publish(topic, str(pid.set_point))
    topic = b"/" + machine_id + b"/sts/PID_Running"
    client.publish(topic, str(PID_RUNNING))

    print("PUB P:{} I:{} D:{} O:{}".format(str(pid.Kp),str(pid.Ki),str(pid.Kd),str(pid.output)))

def initTimer(iPeriod):
    tim.init(period=iPeriod, mode=Timer.PERIODIC, callback=lambda t:timer_tick())

def timer_tick():
    global SECONDSCOUNTER,PID_SECONDSCOUNTER
    SECONDSCOUNTER += 1
        
    if (SECONDSCOUNTER >= PUBLISH_INTERVAL):
        publish_temp()
        SECONDSCOUNTER=0
    if(PID_RUNNING==True):
        if(PID_SECONDSCOUNTER >= PID_CYCLE_S):
            PID_SECONDSCOUNTER=0

        if(PID_SECONDSCOUNTER == 0):
            pid.update()
            publish_pid()
        
        pwm_check(PID_SECONDSCOUNTER)
        PID_SECONDSCOUNTER+=1

pwm_t_on = 0
pwm_t_off = 0

def pwm_setRate(irate):
    global pwm_t_on,pwm_t_off
    #PWM over a long cycle, min 1 sec activation
    pwm_t_on = int (PID_CYCLE_S * irate)
    pwm_t_off = PID_CYCLE_S - pwm_t_on

def pwm_check(iSeconds):
    if (pwm_t_on >= 0):
        if iSeconds < pwm_t_on:
            setRelayHeat(1)
        else:
            setRelayHeat(0)
    else:
        if(Relay.value == 1):
            setRelayHeat(0)

def startPID():
    global PID_RUNNING,pwm_t_on,pwm_t_off
    if PID_RUNNING == False:
        pwm_t_on = 0
        pwm_t_off = 0
        PID_RUNNING = True

def stopPID():
    global PID_RUNNING,pwm_t_on,pwm_t_off
    if PID_RUNNING == True:
        pwm_t_on = 0
        pwm_t_off = 0
        PID_RUNNING = False   
        setRelayHeat(0)
        publish_pid()


connect_and_subscribe()
connect_and_subscribe_adafruit()

pid = PID(readTemp,pwm_setRate,P=54.0,I=60.0,D=15.0)

publish_sts()


global tim
tim = Timer(-1)
initTimer(TIMER_INTERVAL)

while 1:
    client.wait_msg()


client.disconnect()
clientAda.disconnect()
