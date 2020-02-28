FROM golang:latest

RUN apt-get update && \
    apt-get install -y \
        curl \
        tar \
        gzip

RUN go get github.com/stretchr/testify/require \
    github.com/stretchr/testify/assert \
    github.com/Jeffail/tunny

WORKDIR /app
COPY entrypoint.sh .
COPY suite_test.go .
ENTRYPOINT [ "./entrypoint.sh" ]
