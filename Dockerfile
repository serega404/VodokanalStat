FROM python:3.13.9-alpine3.22

LABEL Maintainer="serega404"
LABEL org.opencontainers.image.source=https://github.com/serega404/VodokanalStat
LABEL org.opencontainers.image.licenses=MIT

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY report.py report.py
COPY main.py main.py

# run python daemon
CMD ["python3", "main.py", "--monthly"]