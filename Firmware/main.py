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

#define a couple constants
machine_id = binascii.hexlify(machine.unique_id())
print(b"Machine ID: {}".format(machine_id))

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

RELAY = D1 # relay du board sur IO1 (donc PIN5 selon doc wemos)
LED = D4 # led du wemos sur IO4 (donc PIN2 selon doc wemos)
TIMER_INTERVAL=1000 #on compte les secondes
Publish_interval=30


#defaults
P_value=54.
I_value=60.
D_value=15.
PID_setPoint=20.0
PID_running = False
PID_cycle_s=10
PIDSecondsCounter =0;
SecondsCounter=0;


def setRelay(valueonoff):   
    RELAY.value(valueonoff)
    publish_relay()
    

#function de controle de la led onboard du wemos, logique inverse.
def setLed(valueonoff):
    if(valueonoff==1):
        LED.value(0)
    else:
        LED.value(1)
    publish_led()

# lit la temperature de tous les capteurs trouvés mais retourne juste la derniere recue.
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
    global Publish_interval,PID_setPoint,P_value,I_value,D_value
    target = topic.decode().split('/')[-1]
    print("Received MQTT Message for topic {} : {}".format(target,msg)) 

    if target == "Relay":
        value = 1 if int(msg) > 0 else 0
        setRelay(value)
    elif target == "Led":
        value = 1 if int(msg) > 0 else 0
        setLed(value)
    elif target == "Publish_interval":
        if int(msg) > 0 :
            Publish_interval=int(msg)
    elif target == "Read_temp":
        if int(msg) > 0 :
            publish_temp()
    elif target == "SetPoint":
        if float(str(msg)) > 0 :
            PID_setPoint = float(str(msg))
    elif target == "P":
        if float(str(msg)) > 0 :
            P_value = float(str(msg))
    elif target == "I":
        if float(str(msg)) > 0 :
            I_value = float(str(msg))
    elif target == "D":
        if float(str(msg)) > 0 :
            D_value = float(str(msg))
    elif target == "PID_Running":
        value = 1 if int(msg) > 0 else 0
        if(value == 1):
            startPID()
        else:
            stopPID()
    else:
        print("Unable to process MQTT request")

# command and status, custom MQTT broker.
def connect_and_subscribe():
    global client
    print('Connecting to {} as user {} with password {}'.format(config.broker, config.user, config.password))
    client = MQTTClient(machine_id, config.broker, user=config.user, password=config.password)
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
    clientAda.publish(b"joey_teknome/feeds/set-point",str(PID_setPoint))
    print("PUB Temp: {} PUB SetPoint: {}".format(str(ctemp),str(PID_setPoint)))

def publish_relay():
    topic = b"/" + machine_id + b"/sts/Relay"
    client.publish(topic, str(RELAY.value()))
    print("PUB Relay: {}".format(str(RELAY.value())))

def publish_led():
    topic = b"/" + machine_id + b"/sts/Led"
    if(LED.value()==1):
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
    client.publish(topic,str(pid.P_value))
    topic = b"/" + machine_id + b"/sts/I"
    client.publish(topic, str(pid.I_value))
    topic = b"/" + machine_id + b"/sts/D"
    client.publish(topic, str(pid.D_value))
    topic = b"/" + machine_id + b"/sts/PID_Output"
    client.publish(topic, str(pid.output))

    print("PUB P:{} I:{} D:{} O:{}".format(str(pid.P_value),str(pid.I_value),str(pid.D_value),str(pid.output)))

def initTimer(iPeriod):
    tim.init(period=iPeriod, mode=Timer.PERIODIC, callback=lambda t:timer_tick())

def timer_tick():
    global SecondsCounter,PIDSecondsCounter
    SecondsCounter += 1
        
    if (SecondsCounter >= Publish_interval):
        publish_temp()
        SecondsCounter=0
    if(PID_running==True):
        if(PIDSecondsCounter >= PID_cycle_s):
            PIDSecondsCounter=0

        if(PIDSecondsCounter == 0):
            pid.set_point = PID_setPoint
            pid.update()
            publish_pid()
        
        pwm_check(PIDSecondsCounter)
        PIDSecondsCounter+=1

pwm_t_on = 0
pwm_t_off = 0

def pwm_setRate(irate):
    #PWM over a long cycle, min 1 sec activation
    pwm_t_on = int (PID_cycle_s * irate)
    pwm_t_off = PID_cycle_s - pwm_t_on

def pwm_check(iSeconds):
    if (pwm_t_on >= 0):
        if iSeconds < pwm_t_on:
            setRelay(1)
        else:
            setRelay(0)
    else:
        if(Relay.value == 1):
            setRelay(0)

def startPID():
    if PID_running == False:
        pwm_t_on = 0
        pwm_t_off = 0
        PID_running = True;

def stopPID():
    if PID_running == True:
        pwm_t_on = 0
        pwm_t_off = 0
        PID_running = False;   


connect_and_subscribe()
connect_and_subscribe_adafruit()

pid = PID(readTemp,pwm_setRate,P=P_value,I=I_value,D=D_value)

publish_sts()


global tim
tim = Timer(-1)  
initTimer(TIMER_INTERVAL)



while 1:
    client.wait_msg()
    
client.disconnect()
clientAda.disconnect()
