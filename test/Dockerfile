FROM golang:latest
RUN apt-get update && \
    apt-get install -y \
        curl \
        tar \
        gzip
RUN go get github.com/stretchr/testify/require
WORKDIR /app
COPY entrypoint.sh .
COPY suite_test.go .
ENTRYPOINT [ "./entrypoint.sh" ]
