#!/bin/bash
set -e

echo "=========================================="
echo "MRPT PPA Publisher Container Starting"
echo "=========================================="
echo "Time: $(date)"
echo "Timezone: ${TZ:-UTC}"
echo "MAILTO: ${MAILTO}"
echo "PPA_URL: ${PPA_URL}"
echo "=========================================="

# Set GPG_TTY for proper GPG operation
export GPG_TTY=$(tty)

# Ensure cache directory exists and has proper permissions
mkdir -p /var/cache/mrpt-ppa
mkdir -p /var/log/mrpt-ppa

# Update lock and SHA cache file paths to use persistent volume
export LOCKFILE=/var/cache/mrpt-ppa/mrptppa.lock
export SHA_CACHE_FILE=/var/cache/mrpt-ppa/mrptppa.sha

# Check GPG configuration
echo "Checking GPG keys..."
if [ -d "/root/.gnupg" ]; then
    # Set proper permissions for GPG directory (might be needed if mounted)
    chmod 700 /root/.gnupg || true
    chmod 600 /root/.gnupg/* 2>/dev/null || true
    
    # List available keys
    echo "Available GPG keys:"
    gpg --list-secret-keys || echo "Warning: No secret keys found!"
else
    echo "Warning: GPG directory not found at /root/.gnupg"
    echo "Make sure to mount your GPG keys directory"
fi

# Configure GPG agent
cat > /root/.gnupg/gpg-agent.conf <<EOF
default-cache-ttl 34560000
max-cache-ttl 34560000
allow-preset-passphrase
EOF

# Start GPG agent
gpg-agent --daemon --allow-preset-passphrase 2>/dev/null || true

# Check dput configuration
echo "Checking dput configuration..."
if [ -f "/root/.dput.cf" ]; then
    echo "dput configuration found"
else
    echo "Warning: dput configuration not found at /root/.dput.cf"
    echo "Creating basic dput configuration..."
    cat > /root/.dput.cf <<EOF
[DEFAULT]
method = ftp
hash = md5
allow_unsigned_uploads = 0
run_lintian = 0
run_dinstall = 0
check_version = 0
scp_compress = 0
post_upload_command =
pre_upload_command =
passive_ftp = 1
default_host_main =

[${PPA_URL}]
fqdn = ppa.launchpad.net
method = ftp
incoming = ~joseluisblancoc/ubuntu/mrpt/
login = anonymous
allow_unsigned_uploads = 0
EOF
fi

# Check SSH keys (if needed)
if [ -d "/root/.ssh" ]; then
    chmod 700 /root/.ssh || true
    chmod 600 /root/.ssh/* 2>/dev/null || true
    echo "SSH keys found"
fi

# Configure git
echo "Configuring git..."
git config --global user.email "${MAILTO}"
git config --global user.name "MRPT PPA Publisher"
git config --global --add safe.directory /home/mrpt

# Clone MRPT repository if it doesn't exist
if [ ! -d "/home/mrpt/.git" ]; then
    echo "Cloning MRPT repository..."
    cd /home
    git clone https://github.com/MRPT/mrpt.git
    cd mrpt
    git submodule update --init --recursive
else
    echo "MRPT repository already exists"
fi

# Create initial SHA cache file if it doesn't exist
if [ ! -f "${SHA_CACHE_FILE}" ]; then
    echo " " > "${SHA_CACHE_FILE}"
fi

# Remove any stale lock files on startup
if [ -f "${LOCKFILE}" ]; then
    echo "Removing stale lockfile from previous run"
    rm -f "${LOCKFILE}"
fi

# Test cron is working
echo "Setting up cron..."
service cron start || true

# Create a log symlink for easier access
ln -sf /var/log/cron.log /var/log/mrpt-ppa/cron.log 2>/dev/null || true

echo "=========================================="
echo "Container initialization complete!"
echo "Cron jobs scheduled:"
crontab -l
echo "=========================================="
echo ""
echo "Container is now running. Logs will appear below:"
echo ""

# Execute the CMD (cron -f) or any other command passed
exec "$@"