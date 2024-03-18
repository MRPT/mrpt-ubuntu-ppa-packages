#!/bin/bash

set -x
set -e

cd  ~/code && \
sudo docker run -v /home/jlblanco/code/mrpt-salsa:/tmp/mrpt-salsa -it --rm debian:mrpt.exp \
    /bin/bash -c "apt update && apt upgrade -y && apt dist-upgrade -y && cd /tmp && mkdir build && cp -r mrpt-salsa build/ && cd build/mrpt-salsa && rm .vscode/ -fr && gbp buildpackage"



