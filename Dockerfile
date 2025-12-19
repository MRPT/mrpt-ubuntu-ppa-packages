FROM ubuntu:24.04

# Prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive
ENV GPG_TTY=/dev/console

# Install required packages
RUN apt-get update && apt-get install -y \
    # Build tools
    build-essential \
    cmake \
    debhelper \
    devscripts \
    dh-cmake \
    lintian \
    # Version control
    git \
    git-lfs \
    # GPG and signing
    gnupg \
    gpg-agent \
    pinentry-curses \
    # PPA upload tools
    dput \
    python3 \
    python3-launchpadlib \
    # Scheduling
    cron \
    # Utilities
    ca-certificates \
    curl \
    wget \
    vim \
    less \
    # Mail support for cron
    msmtp \
    msmtp-mta \
    mailutils \
    && rm -rf /var/lib/apt/lists/*

# Create working directories
RUN mkdir -p /home/mrpt \
    && mkdir -p /scripts \
    && mkdir -p /var/cache/mrpt-ppa \
    && mkdir -p /var/log/mrpt-ppa

# Set working directory
WORKDIR /root

# Copy cron scripts
COPY scripts/ /scripts/
RUN chmod +x /scripts/*.sh

# Copy crontab configuration
COPY crontab /etc/cron.d/mrpt-ppa
RUN chmod 0644 /etc/cron.d/mrpt-ppa \
    && crontab /etc/cron.d/mrpt-ppa

# Copy and set up entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Environment variables with defaults
ENV MAILTO="jlblanco@ual.es"
ENV PPA_URL="ppa:joseluisblancoc/mrpt"
ENV HOME=/root

# Expose volumes for persistence
VOLUME ["/root/.gnupg", "/var/cache/mrpt-ppa", "/root/.ssh"]

ENTRYPOINT ["/entrypoint.sh"]
CMD ["cron", "-f"]