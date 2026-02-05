FROM python:3.13.9-alpine3.22

LABEL Maintainer="serega404"
LABEL org.opencontainers.image.source=https://github.com/serega404/VodokanalStat
LABEL org.opencontainers.image.licenses=MIT

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY report.py report.py
COPY main.py main.py

# Ensure Python prints are unbuffered so Docker captures logs
ENV PYTHONUNBUFFERED=1

# run python daemon (use -u to make sure no buffering at interpreter level)
CMD ["python3", "-u", "main.py", "--monthly"]