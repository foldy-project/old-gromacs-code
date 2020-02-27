FROM golang:latest AS builder
ENV GO111MODULE=on
WORKDIR /go/src/github.com/thavlik/foldy-operator
COPY go.mod .
COPY go.sum .
RUN go mod download
COPY . .
RUN GOOS=linux GOARCH=amd64 CGO_ENABLED=0 go build -o foldy-operator

FROM alpine:latest
COPY --from=builder /go/src/github.com/thavlik/foldy-operator/foldy-operator .
ENTRYPOINT [ "./foldy-operator" ]

