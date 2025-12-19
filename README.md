# MRPT PPA Publisher - Docker Deployment

Automated Docker-based system for building and publishing MRPT packages to Ubuntu PPA (Launchpad).

## Overview

This Docker container runs scheduled cron jobs to:
- Monitor MRPT repository for new commits (develop and master branches)
- Build Debian packages for Ubuntu 20.04, 22.04, and 24.04
- Sign packages with GPG
- Upload to Launchpad PPA

## Prerequisites

### On the Server

1. **Docker and Docker Compose**
   ```bash
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   
   # Install Docker Compose
   sudo apt-get update
   sudo apt-get install docker-compose-plugin
   
   # Add your user to docker group (optional)
   sudo usermod -aG docker $USER
   newgrp docker
   ```

2. **GPG Keys for Package Signing**
   - Existing GPG keys from `/home/mrptppa/.gnupg`
   - Must have valid Launchpad PPA signing key

3. **Launchpad/dput Configuration**
   - File: `~/.dput.cf` with PPA credentials

## Directory Structure

```
mrpt-ubuntu-ppa-packages/
├── docker-deployment/           # New branch
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── entrypoint.sh
│   ├── crontab
│   ├── scripts/
│   │   ├── run_mrpt-develop.sh
│   │   └── run_mrpt-master.sh
│   ├── README.md
│   └── .env.example
```

## Initial Setup

### 1. Create Docker Deployment Branch

```bash
cd /path/to/mrpt-ubuntu-ppa-packages
git checkout -b docker-deployment
```

### 2. Prepare Configuration Files

Create an `.env` file for local configuration:

```bash
cat > .env <<EOF
# Host directories
HOST_GPG_DIR=/home/mrptppa/.gnupg
HOST_DPUT_CONFIG=/home/mrptppa/.dput.cf
HOST_SSH_DIR=/home/mrptppa/.ssh

# Email for notifications
MAILTO=jlblanco@ual.es

# Timezone
TZ=Europe/Madrid
EOF
```

### 3. Backup Existing GPG Keys (IMPORTANT!)

Before proceeding, backup your GPG keys:

```bash
# As the mrptppa user
sudo -u mrptppa bash <<'BACKUP'
cd ~
mkdir -p ~/backup-$(date +%Y%m%d)
cp -r .gnupg ~/backup-$(date +%Y%m%d)/
cp .dput.cf ~/backup-$(date +%Y%m%d)/
gpg --export-secret-keys > ~/backup-$(date +%Y%m%d)/secret-keys.gpg
gpg --export-ownertrust > ~/backup-$(date +%Y%m%d)/ownertrust.txt
BACKUP
```

### 4. Verify GPG Keys

Test that GPG keys are accessible and valid:

```bash
sudo -u mrptppa gpg --list-secret-keys
```

You should see your Launchpad PPA signing key listed.

## Building the Docker Image

### Option 1: Using docker-compose (Recommended)

```bash
cd /path/to/mrpt-ubuntu-ppa-packages/docker-deployment

# Build the image
docker-compose build

# Or build with no cache
docker-compose build --no-cache
```

### Option 2: Using docker directly

```bash
cd /path/to/mrpt-ubuntu-ppa-packages/docker-deployment

docker build -t mrpt-ppa-publisher:latest .
```

## Running the Container

### Starting the Service

```bash
cd /path/to/mrpt-ubuntu-ppa-packages/docker-deployment

# Start in detached mode
docker-compose up -d

# View startup logs
docker-compose logs -f
```

### Verify Container is Running

```bash
# Check container status
docker-compose ps

# View logs
docker-compose logs --tail=50

# View cron logs
docker exec mrpt-ppa-publisher tail -f /var/log/mrpt-ppa/develop.log
docker exec mrpt-ppa-publisher tail -f /var/log/mrpt-ppa/master.log
```

## Testing Before Production

### 1. Test Build Manually

Run a test build without waiting for cron:

```bash
# Test develop branch build
docker exec -it mrpt-ppa-publisher /scripts/run_mrpt-develop.sh

# Test master branch build
docker exec -it mrpt-ppa-publisher /scripts/run_mrpt-master.sh
```

### 2. Verify GPG Signing

```bash
# Check GPG keys inside container
docker exec -it mrpt-ppa-publisher gpg --list-secret-keys

# Test GPG signing
docker exec -it mrpt-ppa-publisher bash -c 'echo "test" | gpg --clearsign'
```

### 3. Check Cron Schedule

```bash
# View cron jobs
docker exec mrpt-ppa-publisher crontab -l

# Check cron is running
docker exec mrpt-ppa-publisher service cron status
```

## Migration from Existing System

### Step 1: Run Parallel (Safe Migration)

Keep existing cron jobs running while testing Docker:

```bash
# Existing cron jobs continue to run
# Docker container runs with different lock files (automatically configured)

# Monitor both systems for 24-48 hours
```

### Step 2: Disable Old Cron Jobs

Once Docker system is verified:

```bash
# As mrptppa user, comment out cron jobs
sudo -u mrptppa crontab -e

# Comment out these lines:
# 00 */12 * * * /home/mrptppa/cron/run_mrpt-develop.sh
# 50 */12 * * * /home/mrptppa/cron/run_mrpt-master.sh
```

### Step 3: Clean Up Old Files (Optional)

After successful migration (wait at least 1 week):

```bash
# Archive old working directories
sudo -u mrptppa bash <<'ARCHIVE'
cd ~
tar -czf old-mrpt-system-$(date +%Y%m%d).tar.gz \
    mrpt_debian mrpt_release mrpt_ubuntu .mrptppa.lock .mrptppa.sha
rm -rf mrpt_debian mrpt_release mrpt_ubuntu .mrptppa.lock .mrptppa.sha
ARCHIVE
```

## Monitoring and Maintenance

### View Logs

```bash
# Real-time logs
docker-compose logs -f

# Specific script logs
docker exec mrpt-ppa-publisher tail -f /var/log/mrpt-ppa/develop.log
docker exec mrpt-ppa-publisher tail -f /var/log/mrpt-ppa/master.log

# Last 100 lines
docker-compose logs --tail=100
```

### Check Build Status

```bash
# Check last commits processed
docker exec mrpt-ppa-publisher cat /var/cache/mrpt-ppa/mrptppa-develop.sha
docker exec mrpt-ppa-publisher cat /var/cache/mrpt-ppa/mrptppa-master.sha

# Check for lock files (should be empty between runs)
docker exec mrpt-ppa-publisher ls -la /var/cache/mrpt-ppa/*.lock
```

### Manual Triggers

```bash
# Manually trigger develop build
docker exec mrpt-ppa-publisher /scripts/run_mrpt-develop.sh

# Manually trigger master build  
docker exec mrpt-ppa-publisher /scripts/run_mrpt-master.sh
```

## Container Management

### Stopping the Container

```bash
# Graceful stop
docker-compose stop

# Stop and remove
docker-compose down
```

### Restarting the Container

```bash
# Restart after configuration changes
docker-compose restart

# Full rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Updating the Container

```bash
# Pull latest code
git pull origin docker-deployment

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

## Auto-start on Server Boot

Enable automatic container restart:

```bash
# Using docker-compose (already configured with restart: unless-stopped)
# No additional configuration needed

# Verify restart policy
docker inspect mrpt-ppa-publisher | grep -A 5 RestartPolicy
```

### Alternative: Systemd Service

Create `/etc/systemd/system/mrpt-ppa-publisher.service`:

```ini
[Unit]
Description=MRPT PPA Publisher Docker Container
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/mrptppa/mrpt-ubuntu-ppa-packages/docker-deployment
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
User=mrptppa

[Install]
WantedBy=multi-user.target
```

Enable the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable mrpt-ppa-publisher.service
sudo systemctl start mrpt-ppa-publisher.service
```

## Troubleshooting

### GPG Issues

```bash
# Check GPG keys
docker exec -it mrpt-ppa-publisher gpg --list-secret-keys

# Test signing
docker exec -it mrpt-ppa-publisher bash
echo "test" | gpg --clearsign

# Check GPG agent
docker exec mrpt-ppa-publisher ps aux | grep gpg-agent
```

### Permission Issues

```bash
# Check file permissions in container
docker exec mrpt-ppa-publisher ls -la /root/.gnupg
docker exec mrpt-ppa-publisher ls -la /var/cache/mrpt-ppa

# Fix permissions (if needed)
docker exec mrpt-ppa-publisher chmod 700 /root/.gnupg
docker exec mrpt-ppa-publisher chmod 600 /root/.gnupg/*
```

### Cron Not Running

```bash
# Check cron service
docker exec mrpt-ppa-publisher service cron status

# Restart cron
docker exec mrpt-ppa-publisher service cron restart

# Check cron logs
docker exec mrpt-ppa-publisher tail -f /var/log/cron.log
```

### Build Failures

```bash
# Check full logs
docker exec mrpt-ppa-publisher cat /var/log/mrpt-ppa/develop.log

# Check disk space
docker exec mrpt-ppa-publisher df -h

# Clean old build files
docker exec mrpt-ppa-publisher bash -c 'cd /home/mrpt && git clean -fdx'
```

### Container Won't Start

```bash
# Check container logs
docker-compose logs

# Check for port conflicts
docker ps -a

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

## Security Considerations

### GPG Key Protection

- **Mounted as read-only**: GPG keys are mounted read-only by default in docker-compose.yml
- **Permissions**: Ensure host GPG directory has proper permissions (700)
- **Backup**: Always maintain secure backups of GPG keys

### Network Security

- Container only needs outbound HTTPS access
- No inbound ports exposed
- Consider using Docker network policies for additional isolation

### Secrets Management

For production, consider using Docker secrets:

```bash
# Create secrets
echo "your-gpg-passphrase" | docker secret create gpg_passphrase -

# Update docker-compose.yml to use secrets
```

## Performance Tuning

### Resource Limits

Adjust in `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'      # Increase for faster builds
      memory: 8G       # Increase if builds run out of memory
```

### Build Parallelization

Edit build scripts to enable parallel builds:

```bash
# In build-mrpt-deb-pkg.sh, add:
export DEB_BUILD_OPTIONS="parallel=4"
```

## Rollback Procedure

If issues occur:

1. **Stop Docker container**:
   ```bash
   docker-compose down
   ```

2. **Re-enable old cron jobs**:
   ```bash
   sudo -u mrptppa crontab -e
   # Uncomment the cron jobs
   ```

3. **Verify old system works**:
   ```bash
   sudo -u mrptppa /home/mrptppa/cron/run_mrpt-develop.sh
   ```

## Backup Strategy

### Regular Backups

```bash
# Backup persistent volumes
docker run --rm -v mrpt-ppa-cache:/data -v $(pwd):/backup \
    alpine tar czf /backup/mrpt-ppa-cache-$(date +%Y%m%d).tar.gz /data

# Backup GPG keys (on host)
sudo tar czf /backup/mrpt-gpg-$(date +%Y%m%d).tar.gz /home/mrptppa/.gnupg
```

### Automated Backup Script

Create `/home/mrptppa/backup-mrpt-docker.sh`:

```bash
#!/bin/bash
BACKUP_DIR=/backup/mrpt-ppa
mkdir -p $BACKUP_DIR

DATE=$(date +%Y%m%d)

# Backup volumes
docker run --rm \
    -v mrpt-ppa-cache:/data \
    -v $BACKUP_DIR:/backup \
    alpine tar czf /backup/cache-$DATE.tar.gz /data

# Backup GPG keys
tar czf $BACKUP_DIR/gpg-$DATE.tar.gz /home/mrptppa/.gnupg

# Keep only last 7 days
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

Add to crontab:
```bash
0 2 * * * /home/mrptppa/backup-mrpt-docker.sh
```

## Support and Contact

For issues or questions:
- Email: jlblanco@ual.es
- GitHub: https://github.com/MRPT/mrpt-ubuntu-ppa-packages/issues

## License

Same as MRPT project