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


# add private credentials
ARG SSH_PRIVATE_KEY
RUN mkdir /root/.ssh/
RUN echo "${SSH_PRIVATE_KEY}" > /root/.ssh/id_rsa
RUN chmod 400 ~/.ssh/id_rsa
RUN touch /root/.ssh/known_hosts
RUN ssh-keyscan github.com >> /root/.ssh/known_hosts

WORKDIR /go/src/github.com/thavlik
RUN git clone git@github.com:thavlik/foldy-operator.git

WORKDIR /app
COPY entrypoint.sh .
COPY suite_test.go .

WORKDIR /go/src/github.com/thavlik/foldy-operator/proteinnet
RUN git pull

# remove private credentials
RUN rm /root/.ssh/id_rsa

WORKDIR /app
ENTRYPOINT [ "./entrypoint.sh" ]
