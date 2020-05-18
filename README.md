# RideShare

Rideshare is a backend cloud application hosted on AWS servers, which can potentially be used to pool rides. It provides various microservices APIs to create, delete and manage users, rides etc. It runs on top of highly reliant, fault tolerant database as a service application, which handles any database read or write requests. The DBaaS application runs on separate server. It uses RabbitMQ as AMPQ messaging broker to handle internal data transfer and Apache Zookeeper which handles any internal crash, making the application fault tolerance. The DBaaS also support scaling the application to handle too many requests and at same time makes sure that resource do go unutilized. 

DBaaS has workers which handle data read and write. There are two types of workers, master and slave. Master performs all database write operation, whereas Slave performs all the read operation. The Orchestrator which is the head/face of the DBaaS intercepts all requests made to DBaaS and sends the data to the appropriated worker. The workers have their own databases. Data Consistency between the database of the workers is taken care of by the communication of the workers within themselves.


## Getting Started

The project can be set up locally or on remote system. It is preferred to be set up on a Linux system.   

### Prerequisites

To run the project you will need ** Docker ** . You will also need to install python along with Flask library. We will be using rabbitmq and zookeeper docker images for this project, so no need to install them separately. We use docker-compose to build docker images of slave and master. To install docker on Linux system run the following command

To install docker,
```
$ sudo apt update
$ sudo apt install -y docker.io docker-compose
```

If you are using windows OS, refer [here](https://docs.docker.com/docker-for-windows/install/).

### Installing

In order to run the project, we need to preform following instruction,

#### Local-System

If you are running it on a local system. Make sure to change to the port number of Flask in Rides and Users application to any number above 2000. By default, Flask runs on port 5000. Since there are three flask application and all cannot run on the same port.

Running Ride application
```
$ cd /Rides
$ sudo docker-compose up --build
```

Running User application.
```
$ cd /Users
$ $ sudo docker-compose up --build
```

Running DBaaS application
```
$ cd /DB
$ $ sudo docker-compose up --build
```

#### AWS instances

Create three different instances for rides, users and database, use Linux as operation system (preferably). Make sure to expose port 80 of to all the instances.

You can also use a Load Balancer to distribute the load on User and Rides Instance.
If you do create two target groups one for users and others for rides. Set a user and rides instance accordingly. Add a rule to filter the request based on the path of the URL. Use /api/v1/users to user instance and /api/v1/rides to rides instance. 

Move the respective file to the respective instance.
And repeat for each instance
```
$ sudo apt update
$ sudo apt install -y docker.io docker-compose

$ sudo docker-compose up --build
```

## Running the tests

To test the project, perform URL request to rides and users instance using various tools like [Postman](https://www.postman.com/), [curl](https://curl.haxx.se/) etc,

## Deployment

Even though Ride and User application may not suit for all application, but the DBaaS is separate application of its own. It can be ported accordingly for various applications.

## Built With

* [Docker](https://www.docker.com/)
* [Flask](https://flask.palletsprojects.com/en/1.1.x/)
* [RabbitMQ](https://www.rabbitmq.com/)
* [Zookeeper](http://zookeeper.apache.org/)
* [PostgreSQL](https://www.postgresql.org/)

## Contributing

If you wish to contribute to this project. Please contact us at [Anshuman](anshumanpandey30799@gamil.com).

## Authors

* **Anshuman Pandey** - [an5human](https://github.com/An5human)
* **Anuj** - [anuj](https://github.com/)
* **Anirudh Maiya** - [maiya](https://github.com/)

See also the list of [contributors](https://github.com/An5human/RideShare/contributors) who participated in this project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

## Acknowledgments

I would like to thank PES Unviersity Computer Science Deptartment to present me with the opportunity to work on this project. This was a great learning experince.

