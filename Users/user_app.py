from flask import Flask, render_template,jsonify,request,abort,url_for,Response
import re
import psycopg2
import requests
import json
import datetime
from waitress import serve

api_count = 0

#Database IP
db_ip = "http://18.234.4.35:80"

#Ride  IP
ride_ip = "http://3.230.14.110:80"

locations = {}

f = open("api_count.txt","r") 
api_count = int(f.read())
f.close()


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

@app.route('/')
def health():
	return Response('{}', status=200)

@app.route('/api/v1/users', methods=['GET','PUT',"POST","DELETE"])
def adduser():
	print("Method requested:", request.method, flush=True)
	global api_count
	api_count +=1
	if request.method == 'PUT':
		data = request.json
		print("data:", data)
		pattern = re.compile(r'\b[0-9a-f]{40}\b')
		prepost = str(data)
		match = re.match(pattern, data['password'])
		print("Add user method evoked")
		r = requests.post(db_ip + "/api/v1/db/read",json={"table":"users","username":data["username"]})
		r = r.json()
		l = len(r['username'])
		if(match != None)  and (l == 0):
			r = requests.post(db_ip + "/api/v1/db/write",json={"table":"users","operation":"insert","username":data["username"],"password":data["password"]})
			return Response("{}",status=201)
		return 	Response("{}",status=400)
	elif request.method == "GET":
		try:
			data = request.json
			r = requests.post(db_ip + "/api/v1/db/read",json={"table":"users"})
			r = r.json()
			l = r["username"]
			length = len(l)
			if length == 0:
				return Response("{}", status = 204)
			return Response(json.dumps(l),status = 200)
		except:
			return Response("{}",status=400)

	else:
		return Response("{done:yes}", status=405)

@app.route('/api/v1/users/<username>',  methods=['GET','PUT',"POST","DELETE"])
def removeuser(username):
	global api_count
	api_count +=1
	if request.method == 'DELETE':
		r = requests.post(db_ip + "/api/v1/db/read",json={"table":"users","username":username})
		r = r.json()
		l = len(r["username"])
		if(l != 0):
			r = requests.post(db_ip + "/api/v1/db/write",json = {"table":"users","operation":"delete","username":username})
			r2 = requests.post(db_ip + "/api/v1/db/write", json = {"table":"both","operation":"delete","username":username})
			return Response('{}',status = 200)
		return Response("{}",status=400)
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



@app.route('/api/v1/_count', methods=["GET"])
def request_count():
	global api_count
	return Response(json.dumps([api_count]),status="200")

@app.route('/api/v1/_count',methods=["DELETE"])
def reset_count():
	global api_count
	api_count = 0
	return Response("{}", status="200")


if __name__ == '__main__':
	try:
		serve(app, host = "0.0.0.0", port = 80)
		#app.run(host="0.0.0.0",port=80)
	except:
		f = open("api_count.txt","w") 
		f.write(str(api_count))
		f.close()