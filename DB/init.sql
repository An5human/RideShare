create database rideshare;

\c rideshare

create table if not exists users(
	userid VARCHAR(50) PRIMARY KEY,
	password VARCHAR(40)
);

create table if not exists rides(
	rideid SERIAL PRIMARY KEY,
	created_by VARCHAR(50) REFERENCES users(userid),
	timestamp VARCHAR(30) NOT NULL,
	source VARCHAR(30) NOT NULL,
	destination VARCHAR(30) NOT NULL
);

create table if not exists user_rides(
	ride_id SERIAL REFERENCES rides(rideid),
	userid VARCHAR(50) REFERENCES users(userid)
);