import gc
import webrepl
import time

def do_connect():
    import network
    from config import ssid, psk, ssid2, psk2
    from machine import Pin

    sta_if = network.WLAN(network.STA_IF)
    ap_if = network.WLAN(network.AP_IF)

    # Active le mode AP pour commencer...
    ap_if.active(True)

    # Tente de rejoindre le reeau configure
    if not sta_if.isconnected():
        print('connecting to network {} ...'.format(ssid))
        sta_if.active(True)
        sta_if.connect(ssid, psk)
        ctr = 0
        while not sta_if.isconnected() and ctr < 20:
           ctr += 1
           time.sleep_ms(250)

    if sta_if.isconnected():
        print('STA network config:', sta_if.ifconfig())
        D4 = Pin(2, Pin.OUT)
        D4.value(0)
        # ap_if.active(False)
    else:
        print('first network failed, connecting to network {} ...'.format(ssid2))
        sta_if.active(True)
        sta_if.connect(ssid2, psk2)
        ctr = 0
        while not sta_if.isconnected() and ctr < 20:
           ctr += 1
           time.sleep_ms(250)
           
        if sta_if.isconnected():
            # ap_if.active(False)
            D4 = Pin(2, Pin.OUT)
            D4.value(0)
            print('STA network config:', sta_if.ifconfig())
        else:
            print('AP network config:', ap_if.ifconfig())

import esp
esp.osdebug(None)

do_connect()
webrepl.start()
gc.collect()
