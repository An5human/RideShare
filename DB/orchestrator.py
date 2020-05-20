#!/usr/bin/env python
from flask import Flask, render_template,jsonify,request,abort,url_for,Response
import pika
import json
import uuid
import docker
import time
import logging
from kazoo.client import KazooClient
from kazoo.client import KazooState
from waitress import serve
import threading
####------------------######

####-- Activating Counter ---##
no_of_request = 0
running_slave_container = 1

slave_count = 1

first_request = 1


### Check the usage every 120 seconds ###
def usage_check():
	global no_of_request
	print("Usage:",no_of_request,"	Running Contianers:",running_slave_container)

	if running_slave_container < (no_of_request // 20) + 1:
		scale_up((no_of_request // 20)-running_slave_container+1)
	if running_slave_container > (no_of_request // 20) + 1:
		scale_down(running_slave_container - (no_of_request // 20)-1)
	
	timer = threading.Timer(118.0, usage_check)
	timer.start()
	no_of_request = 0

#################################

### Docker Scaling Section ###
client = docker.from_env()
#client = docker.DockerClient(base_url='unix:///var/run/docker.sock')

def scale_up(amt):
	global slave_count
	global running_slave_container
	print("[*] Scaling Up..",amt)
	for i in range(amt):
		running_slave_container = running_slave_container + 1
		slave_container = client.containers.run("ubuntu_slave","sh -c '/etc/init.d/postgresql start && sleep 10 && python3 worker.py slave 1'",name="slave_"+str(slave_count+1),network = "ubuntu_default",links={'zoo':'zoo','rmq':'rmq'},detach = True)
		#slave_container.start()
		slave_count = slave_count + 1
		print("[*] Container created",slave_container)
	## Wait for the node to be created
	## Else the zookeeper will get triggered. He is very sensitive about this.
	while True:
		y = zk.get_children("/slave")
		if len(y) == running_slave_container:
			break


def scale_down(amt):
	global slave_count
	global running_slave_container
	containers_list = client.containers.list()
	slaves = []
	for container in containers_list:
		slave = container
		pid = container.top()['Processes'][0][1]
		cmd  = 	container.top()['Processes'][0][7]
		if 'slave' in str(cmd):
			slaves.append((pid,slave))
	slaves.sort()
	print("[*] Scaling down..",amt,len(slaves))
	for i in range(amt):
		container = slaves[0][1]
		running_slave_container = running_slave_container - 1
		container.stop()
		slaves = slaves[1:]
#### ---------------------------------------- #####

##### RabbitMQ Section ######

#### Connection ####
connection = pika.BlockingConnection(pika.ConnectionParameters(host='rmq',heartbeat=0))
channel = connection.channel()

#### Queue Declare ####
channel.queue_declare(queue='readQ', durable=True)
channel.queue_declare(queue='writeQ', durable = True)
channel.exchange_declare(exchange='clear', exchange_type='fanout')
#####----------------------#######

##### -- Zookeeper Section -- ######

###-Connection-###
zk = KazooClient(hosts='zoo:2181')
zk.start()

def master_changed(event):
	
	#start another slave
	global slave_count
	children = zk.get_children('/slave')
	if(len(children) < running_slave_container):
		print("Creating a new node")
		slave_container = client.containers.run("ubuntu_slave","sh -c '/etc/init.d/postgresql start && python3 worker.py slave 1'",name="slave_"+str(slave_count+1),network = "ubuntu_default",links={'zoo':'zoo','rmq':'rmq'},detach = True)
		#slave_container.start()
		slave_count = slave_count + 1
		slave_container.attach(stdout=True)
		#slave_container = client.containers.run(image," ",detach = True)
		zk.get_children("/master",watch=master_changed)
		print("[*] New slave Container stared",slave_container,slave_container.name)
		print("Created a new node")
		while True:
			y = zk.get_children("/slave")
			if len(y) == running_slave_container:
				break
	else:
		zk.get_children("/master",watch=master_changed)

def create_new_slave(event):
	#finding the name of image
	#images = client.images.list()
	#for image in images:
	#	name = image.name
	#	if 'slave' in name:
	#		image = name
	#		break
	global slave_count
	global running_slave_container
	children = zk.get_children('/slave')
	#if the children has failed. We create more ...
	print("[INFO] checking nodes..",len(children),running_slave_container)
	if(len(children) < running_slave_container):
		print("Creating a new node")
		slave_container = client.containers.run("ubuntu_slave","sh -c '/etc/init.d/postgresql start && python3 worker.py slave 1'",name="slave_"+str(slave_count+1),network = "ubuntu_default",links={'zoo':'zoo','rmq':'rmq'},detach = True)
		#slave_container.start()
		slave_count = slave_count + 1 
		slave_container.attach(stdout=True)
		#slave_container = client.containers.run(image," ",detach = True)
		print("[INFO] New Slave Container stared",slave_container,slave_container.name)
		zk.get_children("/slave",watch=create_new_slave)
	else:
		zk.get_children("/slave",watch=create_new_slave)	
		

zk.ensure_path("/slave")
### slaves watching the master.
while True:
	try:
		y = zk.get_children("/slave")
		if len(y) > 0:
			break
	except:
		continue

children = zk.get_children("/slave", watch=create_new_slave)

zk.ensure_path("/master")
### slaves watching the master.
while True:
	try:
		y = zk.get_children("/master")
		if len(y) > 0:
			break
	except:
		continue

children = zk.get_children("/master", watch=master_changed)

####################################

####---- Orchestrator Reading RPC Class ----####
class Read(object):
	def __init__(self):
		self.connection = pika.BlockingConnection(
			pika.ConnectionParameters(host='rmq',heartbeat=0))

		self.channel = self.connection.channel()

		result = self.channel.queue_declare(queue='responseQ', durable=True)
		self.callback_queue = result.method.queue

		self.channel.basic_consume(
			queue=self.callback_queue,
			on_message_callback=self.on_response,
			auto_ack=True)

	def on_response(self, ch, method, props, body):
		if self.corr_id == props.correlation_id:
			self.response = body

	def call(self, data):
		self.response = None
		self.corr_id = str(uuid.uuid4())
		self.channel.basic_publish(
			exchange='',
			routing_key='readQ',
			properties=pika.BasicProperties(
				reply_to=self.callback_queue,
				correlation_id=self.corr_id,
			),
			body=str(data))
		while self.response is None:
			self.connection.process_data_events()
		return self.response.decode('utf-8')

read_call = Read()

##---- Orchestrator Reading Ends -----##


#########-- Flash API -- ###########

app=Flask(__name__)


####-- Read API Starts --####
@app.route('/api/v1/db/read', methods=["POST"])
def read():
	print('[ORC] Reading API')
	global no_of_request
	global first_request
	if first_request == 1:
		timer = threading.Timer(115.0, usage_check)
		timer.start()
		first_request = 0
	no_of_request = no_of_request + 1
	data = request.json
	data = str(data)
	out = read_call.call(data)
	data = ""
	for i in out:
		if i == '\'':
			data = data + "\""
			continue
		data = data + i
	return Response(data,status = 201)
####-- Read API Ends  --####

####-- Write API Starts  --####
@app.route('/api/v1/db/write', methods=["POST"])
def write():
	print('[ORC] Writing API')
	#global no_of_requst
	#no_of_request = no_of_request + 1	
	data = request.json
	data = str(data)
	channel.basic_publish(
	exchange='',
	routing_key='writeQ',
	body=str(data))
	return Response("",status = 201)
####-- Write API Ends  --####

####-- Clear API Starts  --####
@app.route('/api/v1/db/clear', methods=["POST"])
def clear():
	print('[ORC] Clear API')
	#global no_of_request
	#no_of_request = no_of_request + 1
	channel.basic_publish(
	exchange='clear',
	routing_key='',
	body="")
	return Response("",status = 201)
####-- Write API Ends  --####

@app.route('/api/v1/crash/master',methods=["POST"])
def crashmaster():
	print('[ORC] Crash Master')
	containers_list = client.containers.list()
	containers_name = []
	found = 0
	for container in containers_list:
		master = container
		cmd = master.top()['Processes'][0][7]
		if "master" in cmd:
			found = 1
			break
	if found == 1:
		pid = master.top()['Processes'][0][1]
		master.stop()
		# remome the contianer
		client.containers.prune()
		return Response(pid,status = 200)
	return Response("",status = 204)

@app.route('/api/v1/crash/slave',methods=["POST"])
def crashslave():
	print('[ORC] Crash Slave')
	containers_list = client.containers.list()
	slaves = []
	pid = 0
	for container in containers_list:
		cmd = container.top()['Processes'][0][7]
		if "slave" in cmd:
			slave = container
			pid  = 	container.top()['Processes'][0][1]
			slaves.append((pid,slave))
	if len(slaves) > 0:
		slaves.sort(reverse = True)
		pid = slaves[0][0]
		slaves[0][1].stop()
		# remome the contianer
		client.containers.prune()
	if pid == 0:
		return Response('{}',status = 204)
	return Response(pid,status = 200)

#####-   Contianer PiD list  ------######
@app.route('/api/v1/worker/list',methods=["GET"])
def list():
	print('[ORC] List Workers')
	containers_list = client.containers.list()
	containers_pid = []
	for container in containers_list:
		name = container.name
		# list of processes of the form ['UID','PID','PPID','C','STIME','TTY','TIME','CMD'] 
		if 'master' in name or 'slave' in name:
			process = container.top()['Processes']
			pid = str(process[0][1])
			containers_pid.append(pid)
	containers_pid.sort()
	return Response(json.dumps(containers_pid),status = 201)
######-----------------------######


###-- Main Part --##
if __name__ == '__main__':
	serve(app,host="0.0.0.0",port='80')

