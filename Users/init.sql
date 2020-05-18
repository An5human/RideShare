CREATE DATABASE rideshare;
\c rideshare
CREATE TABLE users (userid varchar(255) PRIMARY KEY, password char(40) NOT NULL);
