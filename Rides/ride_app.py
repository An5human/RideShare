from flask import Flask, render_template,jsonify,request,abort,url_for,Response
import re
import ast
import psycopg2
import requests
import json
import datetime
from waitress import serve

#DataBase IP
db_ip = "http://18.234.4.35:80"

api_count = 0


f = open("api_count.txt","r")
val = f.read()
print(val)
api_count = int(val)
f.close()

#Ride IP
head = {'origin': '3.230.14.110'}

#Load Balancer Address
user_ip = "http://RideShare-332653198.us-east-1.elb.amazonaws.com"
locations = {}

def testdate(timestamp):
	halves = timestamp.split(":")
	if len(halves)!=2:
		return False
	datepart = halves[0].split("-")
	if len(datepart)!=3:
		return False
	day = datepart[0]
	month = datepart[1]
	year = datepart[2]
	timepart = halves[1].split("-")
	if len(timepart)!=3:
		return False
	sec = timepart[0]
	mins = timepart[1]
	hr = timepart[2]
	try:
		datetime.datetime(int(year),int(month),int(day),int(hr),int(mins), int(sec))
	except:
		return False
	return True

def makedt(timestamp):
	halves = timestamp.split(":")
	datepart = halves[0].split("-")
	timepart = halves[1].split("-")
	day = int(datepart[0])
	month = int(datepart[1])
	year = int(datepart[2])
	sec = int(timepart[0])
	mins = int(timepart[1])
	hr = int(timepart[2])
	return datetime.datetime(year,month,day,hr,mins,sec)

with open("AreaNameEnum.csv") as f:
	lines = f.readlines()
	lines = lines[1:]
	for l in lines:
		line = l.split(",")
		locations[int(line[0])] = line[1].rstrip("\r").rstrip("\n")

app=Flask(__name__)
meths = ["GET", "POST", "PUT", "DELETE"]


@app.route('/')
def health():
	return Response('{}', status=200)

@app.route('/api/v1/rides', methods = meths)
def createride():
	global api_count
	api_count +=1
	if request.method == "POST":
		data = request.json
		if not testdate(data['timestamp']):
			print("Bad timestamp!", flush=True)
			return Response('{}',status=400)
		if int(data["source"]) not in locations.keys() and int(data["destination"]) not in locations.keys():
			print("Bad location", flush=True)
			return Response('{}',status=400)
		r = requests.get(user_ip + "/api/v1/users", headers=head)
		r= r.content.decode('utf-8')
		print(r,flush = True)
		r = ast.literal_eval(r)
		l = data["created_by"] in r 
		if(l):
			r = requests.post(db_ip + "/api/v1/db/write",json={"table":"ride","operation":"insert","username":data["created_by"],"timestamp":data["timestamp"],"source":str(data["source"]),"destination":str(data["destination"])})
			return Response('{}',status=201)
		return 	Response('{}',status=400)

	elif request.method == "GET":
		try:
			rs = request.args.get("source")
			rd = request.args.get("destination")
			r1 = requests.post(db_ip + "/api/v1/db/read",json={"table":"ride_sd","source":rs,"destination":rd})
			detail = r1.json()
			req_time = datetime.datetime.now()
			req_time = req_time.replace(microsecond=0)
			print("req_time:", req_time)
			if "rideid" not in detail or len(detail["rideid"])==0:
				return Response("{}", status=204)
			resp = []
			for i in range(len(detail["rideid"])):
				ride_time = makedt(detail["timestamp"][i])
				print("ride_time:", ride_time)
				if ride_time >= req_time:
					resp.append({"rideId":detail["rideid"][i],"username":detail["created_by"][i],"timestamp":detail["timestamp"][i]})
			return Response(json.dumps(resp), status=200)
		except:
			return 	Response("{}",status=400)
	else:
		return Response("{}", status=405)

@app.route('/api/v1/rides/count', methods = meths)
def num_rides():
	global api_count
	api_count +=1
	if request.method == "GET":
		r1 = requests.post(db_ip + "/api/v1/db/read",json={"table":"count_rides"})
		return Response(r1.text, status=200)
	else:
		return Response("{}", status=405)

@app.route('/api/v1/db/clear', methods=['GET','PUT',"POST","DELETE"])
def clear():
	if request.method == "POST":
		try:
			requests.post(db_ip+"/api/v1/db/clear")
			return Response("{}",status=200)
		except:
			return Response("{}",status=400)
	else:
		return Response("{}", status=405)


@app.route('/api/v1/rides/<rideId>', methods=meths)
def ridedetails(rideId):
	global api_count
	api_count +=1

	if request.method == "GET":
		r1 = requests.post(db_ip + "/api/v1/db/read",json={"table":"ride","rideid":rideId})
		detail = r1.json()
		r2 = requests.post(db_ip + "/api/v1/db/read",json={"table":"user_ride","rideid":rideId})
		detail2 = r2.json()
		resp = []
		if "rideid" not in detail:
			return Response("{}", status = 204)
		if(len(detail["rideid"])==0):
			return Response('{}',status=204)
		for i in range(len(detail["rideid"])):
			resp.append({"rideId":detail["rideid"][i],"created_by":detail["created_by"][i],"users":detail2["username"],"timestamp":detail["timestamp"][i],"source":locations[int(detail["source"][i])],"destination":locations[int(detail["destination"][i])]})
		return Response(json.dumps(resp[0]),status=200)

	elif request.method == "POST":
		data = request.json
		r1 = requests.post(db_ip + "/api/v1/db/read",json={"table":"ride","rideid":rideId})
		detail = r1.json()
		creator = detail["created_by"][0]
		r = requests.get(user_ip + "/api/v1/users", headers=head)
		r = r.content.decode('utf-8')
		rt = ast.literal_eval(r)
		l1 = data["username"] in rt
		r3 = requests.post(db_ip + "/api/v1/db/read",json={"table":"user_ride","rideid":rideId})
		r3js = r3.json()
		existing_users = r3js["username"]
		if (creator == data["username"]) or (data["username"] in existing_users):
			return Response("{}", status=400) # creator is trying to add himself as a user, or user is already in. dont allow
		if(len(detail["rideid"])!=0 and l1):
			r1 = requests.post(db_ip + "/api/v1/db/write",json={"table":"user_ride","operation":"insert","rideid":rideId,"username":data["username"]})
			return Response("{}",status=200)
		return  Response("{}",status=400)
	elif request.method == "DELETE":
		try:
			r1 = requests.post(db_ip + "/api/v1/db/read",json={"table":"ride","rideid":rideId})
			detail = r1.json()
			if(len(detail["rideid"])!=0):
				r = requests.post(db_ip + "/api/v1/db/write",json={'table':"ride","operation":"delete","rideid":rideId})
				return Response('{}',status=200)
			return Response('{}',status=400)
		except:
			return 	Response("{}",status=400)
	else:
		return Response("{}", status=405)

@app.route('/api/v1/_count',methods=["GET"])
def request_count():
	global api_count
	return Response(json.dumps([api_count]), status=200)

@app.route('/api/v1/_count',methods=["DELETE"])
def del_count():
	global api_count
	api_count = 0
	return Response("{}", status=200)

if __name__ == '__main__':
	try:
		serve(app, host = "0.0.0.0", port = 80)
		#app.run(host="0.0.0.0",port=80)
	except:
		f= open("api_count.txt","w") 
		f.write(str(api_count))
		f.close()