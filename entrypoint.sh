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

    # Kill any existing GPG agent from host that might be using old version
    gpgconf --kill gpg-agent 2>/dev/null || true

    # List available keys
    echo "Available GPG keys:"
    gpg --list-secret-keys || echo "Warning: No secret keys found!"
else
    echo "Warning: GPG directory not found at /root/.gnupg"
    echo "Make sure to mount your GPG keys directory"
fi

# Configure GPG agent
if [ ! -f /root/.gnupg/gpg-agent.conf ]; then
    # Try to create gpg-agent.conf, but don't fail if read-only
    cat > /root/.gnupg/gpg-agent.conf 2>/dev/null <<EOF || echo "Note: GPG directory is read-only, skipping gpg-agent.conf creation"
default-cache-ttl 34560000
max-cache-ttl 34560000
allow-preset-passphrase
EOF
else
    echo "gpg-agent.conf already exists"
fi

# Restart GPG agent with container's version
gpgconf --kill gpg-agent 2>/dev/null || true
gpg-agent --daemon --allow-preset-passphrase 2>/dev/null || true

# Check dput configuration
echo "Checking dput configuration..."
if [ -f "/root/.dput.cf" ]; then
    echo "dput configuration found"
elif [ -d "/root/.dput.cf" ]; then
    echo "Warning: /root/.dput.cf is a directory (Docker created it because source file didn't exist)"
    echo "Removing directory and creating dput configuration file..."
    rmdir /root/.dput.cf 2>/dev/null || rm -rf /root/.dput.cf
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
else
    echo "dput configuration not found, creating default configuration..."
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

# Ensure cron directory exists
mkdir -p /var/log

# Test cron is working
echo "Setting up cron..."
if ! service cron start; then
    echo "ERROR: Failed to start cron service"
    echo "Trying alternative cron startup..."
    /usr/sbin/cron || {
        echo "ERROR: Cannot start cron daemon"
        exit 1
    }
fi

# Create a log symlink for easier access
ln -sf /var/log/cron.log /var/log/mrpt-ppa/cron.log 2>/dev/null || true

# Verify cron is running
if pgrep cron > /dev/null; then
    echo "Cron daemon is running (PID: $(pgrep cron))"
else
    echo "WARNING: Cron daemon may not be running properly"
fi

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

