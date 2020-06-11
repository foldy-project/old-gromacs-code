FROM gromacs/gromacs:latest

ARG CONCURRENCY=4

RUN echo "deb http://ftp.de.debian.org/debian sid main" >> /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y \
        --allow-unauthenticated \
        curl \
        gettext-base \
        python3 \
        python3-distutils \
    && apt-get clean

RUN python3 --version

RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
    && python3 get-pip.py

RUN pip install awscli \
    boto3 \
    absl-py \
    biopython

RUN python get-pip.py \
    && python -m pip install numpy cloudpickle

WORKDIR /app
COPY charmming_parser charmming_parser
COPY minim-modified.mdp.tpl .
COPY ions.mdp .
COPY run-simulation.sh .
COPY normalize.sh .
COPY normalize.py .
COPY simulate.py .
COPY util.py .
COPY proteinnet.py .
COPY errors.py .
COPY upload.sh .
COPY trjconv.sh .
COPY fake-sim.sh .
