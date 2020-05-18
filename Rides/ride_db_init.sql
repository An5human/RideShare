CREATE DATABASE rideshare;
\c rideshare
CREATE TABLE IF NOT EXISTS rides(
	rideid SERIAL PRIMARY KEY,
	created_by VARCHAR(50),
	timestamp VARCHAR(30) NOT NULL,
	source VARCHAR(30) NOT NULL,
	destination VARCHAR(30) NOT NULL
);
CREATE TABLE IF NOT EXISTS user_rides(
	ride_id SERIAL REFERENCES rides(rideid) ON DELETE CASCADE,
	userid VARCHAR(50)
);
