#!/usr/bin/python3
import paho.mqtt.client as mqtt
from influxdb import InfluxDBClient
from influxdb import SeriesHelper

# InfluxDB connections settings
host = 'localhost'
port = 8086
user = ''
password = ''
dbname = 'mydb'

myclient = InfluxDBClient(host, port, user, password, dbname)

# Uncomment the following code if the database is not yet created
# myclient.create_database(dbname)
# myclient.create_retention_policy('awesome_policy', '3d', 3, default=True)


class MySeriesHelper(SeriesHelper):
    """Instantiate SeriesHelper to write points to the backend."""

    class Meta:
        """Meta class stores time series helper configuration."""

        # The client should be an instance of InfluxDBClient.
        client = myclient

        # The series name must be a string. Add dependent fields/tags
        # in curly brackets.
        series_name = 'Temperature'

        # Defines all the fields in this time series.
        fields = ['Value']

        # Defines all the tags for the series.
        tags = ['DeviceID','SensorID']

        # Defines the number of data points to store prior to writing
        # on the wire.
        bulk_size = 1 

        # autocommit must be set to True when using bulk_size
        autocommit = True


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata,flags, rc):
	print("Connected with result code "+str(rc))
	# Subscribing in on_connect() means that if we lose the connection and
	# reconnect then subscriptions will be renewed.
	client.subscribe("/+/sts/Temp/#")

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
	print("Topic: "+ msg.topic+"\nMessage: "+str(msg.payload))
	tokens=msg.topic.split("/")
	MySeriesHelper(DeviceID=tokens[1], SensorID=tokens[4], Value=msg.payload)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set("user", password="password")

client.connect("m13.cloudmqtt.com", 18910, 60)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()
