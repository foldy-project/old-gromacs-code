FROM golang:latest

RUN apt-get update \
    && apt-get install -y \
        curl \
        tar \
        gzip \
        python3 \
    && apt-get clean

RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
    && python3 get-pip.py \
    && pip install awscli

RUN go get github.com/stretchr/testify/require \
    github.com/stretchr/testify/assert \
    github.com/Jeffail/tunny

WORKDIR /app
COPY entrypoint.sh .
COPY good_test.go .
ENTRYPOINT [ "./entrypoint.sh" ]
