FROM python:3.13.9-alpine3.22

LABEL Maintainer="serega404"
LABEL org.opencontainers.image.source=https://github.com/serega404/VodokanalStat
LABEL org.opencontainers.image.licenses=MIT

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

# Setting up crontab
COPY crontab /tmp/crontab
RUN cat /tmp/crontab > /etc/crontabs/root

COPY main.py main.py

# run crond as main process of container
CMD ["crond", "-f", "-l", "2"]