#!/bin/bash

docker build -t debian:mrpt -f Dockerfile.sid .
docker build -t debian:mrpt.exp -f Dockerfile.exp .

