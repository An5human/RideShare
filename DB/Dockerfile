FROM ubuntu:18.04

RUN mkdir -p /code
COPY ./requirements.txt /code/requirements.txt
COPY . /code

RUN apt update && apt -y install wget gnupg gnupg2 gnupg1

RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 7FCC7D46ACCC4CF8

RUN echo "deb http://apt.postgresql.org/pub/repos/apt/ precise-pgdg main" > /etc/apt/sources.list.d/pgdg.list

RUN apt-get update && apt-get install -y  postgresql-9.3 postgresql-client-9.3 postgresql-contrib-9.3

USER postgres

RUN    /etc/init.d/postgresql start &&\
    psql --command "ALTER USER postgres WITH PASSWORD 'password';" &&\
    psql -U postgres -f /code/init.sql

RUN echo "host all  all    0.0.0.0/0  md5" >> /etc/postgresql/9.3/main/pg_hba.conf

RUN echo "listen_addresses='*'" >> /etc/postgresql/9.3/main/postgresql.conf

USER root
EXPOSE 5432

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1

VOLUME  ["/etc/postgresql", "/var/log/postgresql", "/var/lib/postgresql"]

CMD ["/usr/lib/postgresql/9.3/bin/postgres", "-D", "/var/lib/postgresql/9.3/main", "-c", "config_file=/etc/postgresql/9.3/main/postgresql.conf"]

RUN apt-get update && apt-get install -y python3 python3-pip gcc python3-dev musl-dev

RUN pip3 install -r /code/requirements.txt

RUN chmod 777 /code/worker.py

WORKDIR /code
