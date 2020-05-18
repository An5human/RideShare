import pika
import json
import sys
import os
import psycopg2
import uuid
from kazoo.client import KazooClient
from kazoo.client import KazooState

#print('[*] Worker Starting...')

### Checking for type of worker ###
if len(sys.argv) == 3:
	worker_type = str(sys.argv[1])
	update = str(sys.argv[2])
else:
	worker_type = 'slave'
	update = '0'
###-----------------------------####

#print("[INFO] Worker-Type: ",worker_type)

####     Zookeeper Part      ####

##############################################################
# The Zookeeper of the slave workers watches over the master # 
# The slaves are watched over by the orchestrator.           #
##############################################################

###-Connection-###
zk = KazooClient(hosts='zoo:2181')
zk.start()

### - choosing the slave to become the master - ###

def choose_leader():
	print('[INFO] Becomes the master..')
	#if worker_type == 'slave':
	#	worker_type = 'master'
	##-- Won't work the queues need to be changed. --##
	## reruning the code but as master works.
	os.execv(sys.executable,[sys.executable,__file__,'master','0'])	

	

def choosemaster(event):
	'''When master crashes, slave that wins becomes master.'''
	print('[INFO] Master Crashed. Starting Election for next master.')
	if zk.exists("/master/node1"):
		zk.delete("/master/node1")
		election = zk.Election("/master", worker_type)
		election.run(choose_leader)
		election.cancel()
	if not zk.exists("/master/node1"):
		election = zk.Election("/master", worker_type)
		election.run(choose_leader)
		# won't effect the winner but cancel for others 
		election.cancel()


if worker_type == 'slave':
	print('[INFO] ZK Creating slave node')
	zk.ensure_path("/slave")
	i = 1
	## Finding an unused node to assocaited with this file which exits with program.
	while zk.exists("/slave/node"+str(i)):
		i=i+1
	zk.create("/slave/node"+str(i),ephemeral=True)
	
	print('[INFO] ZK Watching the master node')
	zk.ensure_path("/master")
	### slaves watching the master.
	### Waiting for master node to be created. Time for master to start.
	while True:
		try:
			y = zk.get_children("/master")
			if len(y) == 1:
				break
		except:
			continue

	children = zk.get_children("/master", watch=choosemaster)

## creating a master node in zookeeper.
if worker_type == 'master':
	print('[INFO] Zk Creating a master node')
	zk.ensure_path("/master")
	### ephemeral node deletes at the end of the session.
	zk.create("/master/node1", ephemeral=True)

#####-----------------------######



### RabbitMQ Connection ###
connection = pika.BlockingConnection(pika.ConnectionParameters(host='rmq',heartbeat=0))
channel = connection.channel()
###---------------------###

### If a new slave has started with out the current data ###
#if update == 1:
	### get the data

if worker_type == 'master':
	#print('[INFO] RMQ Queue Declaration.')
	channel.queue_declare(queue='writeQ',durable=True)
	channel.exchange_declare(exchange='sync', exchange_type='fanout')
	channel.queue_declare(queue='updateQ',durable=True)
	channel.queue_declare(queue='update_sendQ',durable=True)
	clr = channel.queue_declare(queue='',durable=True)
	clear_queue_name = clr.method.queue
	channel.exchange_declare(exchange='clear', exchange_type='fanout')
	channel.queue_bind(exchange='clear', queue=clear_queue_name)


if worker_type == 'slave':
	#print('[INFO] RMQ Queue Declaration.')
	channel.queue_declare(queue='responseQ', durable=True)
	channel.queue_declare(queue='readQ', durable=True)
	result = channel.queue_declare(queue='',durable=True)
	queue_name = result.method.queue
	channel.exchange_declare(exchange='sync', exchange_type='fanout')
	channel.queue_bind(exchange='sync', queue=queue_name)
	channel.queue_declare(queue='updateQ',durable=True)
	channel.queue_declare(queue='update_sendQ',durable=True)
	clr = channel.queue_declare(queue='',durable=True)
	clear_queue_name = clr.method.queue
	channel.exchange_declare(exchange='clear', exchange_type='fanout')
	channel.queue_bind(exchange='clear', queue=clear_queue_name)

#### ------------------------------------------- #####

#### Read Queue Callback #####
def clear(channel,method,props,body):
	#print('[INFO] Clearing the database...')
	connection = psycopg2.connect(user = "postgres",password = "password",host = "localhost",port = "5432",database = "rideshare")
	cursor = connection.cursor()
	query = "DELETE FROM user_rides;DELETE FROM rides;DELETE FROM users;"
	cursor.execute(query)
	connection.commit()
	#print('[INFO] Database cleared.')

def read(channel,method,props,body):
	content = body.decode('utf-8')
	data = ""
	for i in content:
		if i == '\'':
			data = data + "\""
			continue
		data = data + i
	
	content = json.loads(data)
	table = content["table"]
	#print("[INFO] Data:",content)
	#print("[INFO] Reading Values From Database...")
	value = readdb("rideshare",table,content)
	#print("[INFO] Sending the value to orchestrator...")
	channel.basic_publish(exchange='',
                     routing_key=props.reply_to,
                     properties=pika.BasicProperties(correlation_id = \
                                                         props.correlation_id),
                     body=str(value))
	channel.basic_ack(delivery_tag=method.delivery_tag)
	#print("[INFO] Value Sent")
####----------------------####

#### WriteQ callback function ### 
def write(channel,method,properties,body):
	content = body.decode('utf-8')
	data = ""
	for i in content:
		if i == '\'':
			data = data + "\""
			continue
		data = data + i
	content = json.loads(data)
	table = content["table"]
	operation = content["operation"]
	print("[INFO] Data:",content)
	print("[INFO] Writing the data to database...")
	if worker_type == 'slave':
		print("[INFO] Updating Slaves")
	try:
		value = writedb("rideshare",table,operation,content)
	except:
		pass
	#print("[INFO] Written")
	if worker_type == 'master':
		print("[INFO] Sending Update to slaves...")
		channel.basic_publish(exchange='sync',routing_key='',body=body)
###------------------------------###



#####################################
###     Writing to database       ###
#####################################
def writedb(database,table,operation,data):
	"""Writing to the database"""
	connection = psycopg2.connect(user = "postgres",password = "password",host = "localhost",port = "5432",database = database)
	cursor = connection.cursor()
	if(operation == "insert"):
		if(table == "users"):
			query = "INSERT INTO users(userid,password) VALUES('" +data["username"]+ "','"+data["password"]+"');"
		if(table == "ride"):
			query = "INSERT INTO rides(created_by,timestamp,source,destination) VALUES('" +data["username"]+ "','" +data["timestamp"]+ "','" +data["source"]+ "','" +data["destination"]+ "');"
		if(table == "user_ride"):
			query = "INSERT INTO user_rides(ride_id, userid) VALUES(" + data["rideid"] + ",'" + data["username"]+ "');"   
	if(operation == "delete"):
		if(table == "user"):
			query = "DELETE FROM users where userid = '" +data["username"]+ "';"
		if(table == "ride"):
			query = "DELETE FROM rides where rideid  = " +data["rideid"]+ ";"
		if(table == "both"):
			query = "DELETE FROM rides where created_by = '"+data["username"]+"';" + "DELETE FROM user_rides where userid = '"+data["username"]+"';"

	cursor.execute(query)
	connection.commit()
	return
#####--------------------------#####

#####################################
###     Reading from database     ###
#####################################
def readdb(database,table,data):
	"""Reading from the database"""
	connection = psycopg2.connect(user = "postgres",password = "password",host = "localhost",port = "5432",database = database)
	cursor = connection.cursor()
	output = {}
	if(table == "users"):
		try:
			kw = data["username"]
			query = "SELECT * FROM users WHERE userid = '" +kw+ "';"
		except KeyError:
			query = "SELECT userid FROM users;"
		output["username"] = []
		cursor.execute(query)
		result = cursor.fetchall()
		for i in range(len(result)):
			output["username"].append(result[i][0])
	if(table == "ride_sd"):
		query = "SELECT * FROM rides WHERE source = '" +data["source"]+ "' AND destination  = '" +data["destination"]+ "';"
		cursor.execute(query)
		result = cursor.fetchall()
		output["rideid"] = []
		output["created_by"] = []
		output["timestamp"] = []
		for i in range(len(result)):
			output["rideid"].append(result[i][0])
			output["created_by"].append(result[i][1])
			output["timestamp"].append(result[i][2])
	if(table == "ride"):
		query = "SELECT * FROM rides WHERE rideid = " +data["rideid"]+ ";"
		cursor.execute(query)
		result = cursor.fetchall()
		output["rideid"] = []
		output["created_by"] = []
		output["timestamp"] = []
		output["source"] = []
		output["destination"] = []
		for i in range(len(result)):
			output["rideid"].append(result[i][0])
			output["created_by"].append(result[i][1])
			output["timestamp"].append(result[i][2])
			output["source"].append(result[i][3])
			output["destination"].append(result[i][4])
	if(table == "user_ride"):
		query = "SELECT * FROM user_rides WHERE ride_id = " + data["rideid"] + ";"
		cursor.execute(query)
		result = cursor.fetchall()
		output["username"] = []
		for i in range(len(result)):
			output["username"].append(result[i][0])

	if (data["table"] == "count_rides"):
		query = "SELECT COUNT(*) FROM rides;"
		cursor.execute(query)
		(number_of_rows,)=cursor.fetchone()
		return json.dumps([number_of_rows])
	return output

#####--------------------------#####


#####################################
###     Updating from database     ###
#####################################
def update_send(ch, method, props, body):
	print('[INFO] Getting the updated database...')
	connection = psycopg2.connect(user = "postgres",password = "password",host = "localhost",port = "5432",database = "rideshare")
	cursor = connection.cursor()
	output={"users":[],"rides":[],"user_rides":[]}
	query = "SELECT * FROM users;"
	cursor.execute(query)
	result = cursor.fetchall()
	output["users"] = result
	query = "SELECT * FROM rides;"
	cursor.execute(query)
	result = cursor.fetchall()
	output["rides"] = result
	query = "SELECT * FROM user_rides;"
	cursor.execute(query)
	result = cursor.fetchall()
	output["user_rides"] = result
	#print('[INFO] Sending the Database.')
	out = json.dumps(output)
	ch.basic_publish(exchange='',routing_key=props.reply_to,properties=pika.BasicProperties(correlation_id =props.correlation_id),body=out)
	ch.basic_ack(delivery_tag=method.delivery_tag)
	#print('[INFO] Database sent.')
	
def update_data(data):
	#print('[INFO] Updating the database ...')
	connection = psycopg2.connect(user = "postgres",password = "password",host = "localhost",port = "5432",database = "rideshare")
	cursor = connection.cursor()
	users = data["users"]
	for user in users:
		query = "INSERT INTO users(userid,password) VALUES('" +user[0]+ "','"+user[1]+"');"
		cursor.execute(query)
		connection.commit()
	rides = data["rides"]
	for ride in rides:
		query = "INSERT INTO rides(rideid, created_by,timestamp,source,destination) VALUES(" +str(ride[0])+ ",'" +ride[1]+ "','" +ride[2]+ "','" +ride[3]+ "','" +ride[4]+ "');"
		cursor.execute(query)
		connection.commit()
	user_rides = data["user_rides"]
	for user_ride in user_rides:
		query = "INSERT INTO user_rides(ride_id, userid) VALUES(" + str(user_ride[0]) + ",'" + user_ride[1]+ "');" 
		cursor.execute(query)
		connection.commit()
	#print('[INFO] Database updated.')

class Update_RPC(object):
	def __init__(self):
		self.connection = pika.BlockingConnection(
			pika.ConnectionParameters(host='rmq',heartbeat=0))

		self.channel = self.connection.channel()

		result = self.channel.queue_declare(queue='update_sendQ', durable=True)
		self.callback_queue = result.method.queue

		self.channel.basic_consume(
			queue=self.callback_queue,
			on_message_callback=self.on_response,
			auto_ack=True)

	def on_response(self, ch, method, props, body):
		if self.corr_id == props.correlation_id:
			self.response = body

	def call(self):
		self.response = None
		self.corr_id = str(uuid.uuid4())
		self.channel.basic_publish(
			exchange='',
			routing_key='updateQ',
			properties=pika.BasicProperties(
				reply_to=self.callback_queue,
				correlation_id=self.corr_id,
			),
			body="")
		while self.response is None:
			self.connection.process_data_events()
		return self.response.decode('utf-8')


if update == '1':
	if worker_type == 'slave':
		print('[INFO] Update RPC Call...')
		upd = Update_RPC()
		out = upd.call()
		# data = ""
		# for i in out:
		# 	if i == '\'':
		# 		data = data + "\""
		# 		continue
		# 	data = data + i
		print(out)
		data = json.loads(out)
		update_data(data)
		print(data)
		
#####--------------------------#####

###--- RabbitMQ Consumption Section --###
print('[INFO] RMQ Queue Consuming..')
channel.basic_qos(prefetch_count=1)

channel.basic_consume(queue=clear_queue_name,on_message_callback=clear,auto_ack=True)

if worker_type == 'slave':
	channel.basic_consume(queue='readQ', on_message_callback=read)
	channel.basic_consume(queue=queue_name,on_message_callback=write,auto_ack=True)

if worker_type == 'master':
	channel.basic_consume(queue='writeQ', on_message_callback=write,auto_ack=True)
	channel.basic_consume(queue='updateQ',on_message_callback=update_send)

####----------------------------------####

#### Let the consumption begin ####
if __name__ == '__main__':
	try:
		channel.start_consuming()
	except KeyboardInterrupt:
		##-  Time to say bye -##
		print("[INFO] Closing Worker...")
		channel.stop_consuming()
		connection.close()
		print("[INFO] Worker Closed.")
