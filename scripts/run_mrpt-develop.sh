#!/bin/bash
set -e

echo "======================================"
echo "MRPT Develop PPA Build Script"
echo "Started: $(date)"
echo "======================================"

# to fix gpg ioctl error msg
export GPG_TTY=$(tty)

# Use environment variables or defaults
LOCKFILE=${LOCKFILE:-/var/cache/mrpt-ppa/mrptppa-develop.lock}
SHA_CACHE_FILE=${SHA_CACHE_FILE:-/var/cache/mrpt-ppa/mrptppa-develop.sha}
PPA_URL=${PPA_URL:-ppa:joseluisblancoc/mrpt}

DO_REMOVE_LOCK=1

# Make sure we cleanup lockfile on exit:
function cleanup
{
	if [ "$DO_REMOVE_LOCK" == "1" ]; then
		rm -f $LOCKFILE
	fi
}
trap cleanup EXIT

# Check for another active session:
if [ -f $LOCKFILE ]; then
	# There is a lock file. Honor it and exit... unless it's really old,
	# which might indicate a dangling script (?).
	if [ "$(( $(date +"%s") - $(stat -c "%Y" $LOCKFILE) ))" -gt "7200" ]; then
		# too old: reset lock file
		rm -f $LOCKFILE
		echo "Removing dangling lockfile."
	else
		DO_REMOVE_LOCK=0
		echo "Exiting: there is another instance running? (lockfile exists)"
		exit 0;
	fi
fi
# Create lock file:
touch $LOCKFILE

if [ ! -f $SHA_CACHE_FILE ]; then
    echo " " > $SHA_CACHE_FILE
fi

# Get latest MRPT script:
cd /home/mrpt

echo "Updating MRPT repository..."
git clean -d -x -f > /dev/null
git checkout . > /dev/null 2>&1
git pull > /dev/null 2>&1
git submodule update --init --recursive > /dev/null

# Check if there are new commit(s)?
CURSHA=`git rev-parse HEAD`
LASTSHA=`cat $SHA_CACHE_FILE`

if [ "$CURSHA" != "$LASTSHA" ]; then
    echo "New commits detected: $CURSHA"
    echo "Previous SHA was: $LASTSHA"
    set -x

    # Build PPA and uploads:
    GITBRANCH=develop
    TMPDIR=/tmp/mrpt-$GITBRANCH
    
    rm -fr $TMPDIR
    mkdir -p $TMPDIR
    cd $TMPDIR

    git clone https://github.com/MRPT/mrpt-ubuntu-ppa-packages.git
    cd mrpt-ubuntu-ppa-packages

    # Create release directory if it doesn't exist
    mkdir -p /root/mrpt_release

    # u20.04 focal:
    echo "Building for Ubuntu 20.04 (focal)..."
    MRPT_PKG_EXPORTED_SUBMODULES="nanoflann" ./build-mrpt-deb-pkg.sh -s -g $GITBRANCH -d focal
    (cd /root/mrpt_release && dput $PPA_URL *.changes)

    # u22.04 jammy
    echo "Building for Ubuntu 22.04 (jammy)..."
    ./build-mrpt-deb-pkg.sh -s -g $GITBRANCH -d jammy
    (cd /root/mrpt_release && dput $PPA_URL *.changes)

    # u24.04 noble
    echo "Building for Ubuntu 24.04 (noble)..."
    ./build-mrpt-deb-pkg.sh -s -g $GITBRANCH -d noble
    (cd /root/mrpt_release && dput $PPA_URL *.changes)

    # Save new commit sha:
    echo $CURSHA > $SHA_CACHE_FILE
    echo "Build completed successfully!"
else
    echo "No new commits since last run ($CURSHA)"
fi

# Clean up
echo "Cleaning up temporary files..."
rm -fr /root/mrpt_debian
rm -fr /root/mrpt_release
rm -fr /root/mrpt_ubuntu
cd /home/mrpt
git clean -d -x -f > /dev/null

echo "======================================"
echo "MRPT Develop build script completed"
echo "Finished: $(date)"
echo "======================================"