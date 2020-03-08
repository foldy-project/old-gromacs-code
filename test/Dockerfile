FROM golang:latest

RUN apt-get update && \
    apt-get install -y \
        curl \
        tar \
        gzip

RUN go get github.com/stretchr/testify/require \
    github.com/stretchr/testify/assert \
    github.com/Jeffail/tunny \
    github.com/fogleman/fauxgl \
    github.com/nfnt/resize \
    github.com/fogleman/ease

WORKDIR /go/src/github.com/fogleman
RUN git clone https://github.com/thavlik/ribbon.git

WORKDIR /app
COPY entrypoint.sh .
COPY suite_test.go .
ENTRYPOINT [ "./entrypoint.sh" ]
