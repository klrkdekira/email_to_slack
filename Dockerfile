FROM python:3.8.3-slim-buster

RUN apt update && \
    apt install -y tzdata && \
    rm -rf /var/lib/apt/lists

COPY main.py /usr/local/bin

VOLUME ["/data/"]

WORKDIR /data

ENV TZ=Asia/Kuala_Lumpur

ENV POP3_SERVER ""
ENV POP3_PORT ""
ENV POP3_ACCOUNT ""
ENV POP3_PASSWORD ""
ENV SLACK_WEBHOOK ""

CMD [ "main.py" ]