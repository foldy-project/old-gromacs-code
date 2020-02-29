FROM gromacs/gromacs:latest

RUN apt-get update \
    && apt-get install -y \
        python3 \
        curl \
        gettext-base \
    && apt-get clean

RUN curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
    && python3 get-pip.py

RUN pip install awscli \
    boto3 \
    absl-py \
    biopython

WORKDIR /app
COPY minim-modified.mdp.tpl .
COPY ions.mdp .
COPY run-simulation.sh .
COPY simulate.py .
COPY upload.sh .
COPY trjconv.sh .