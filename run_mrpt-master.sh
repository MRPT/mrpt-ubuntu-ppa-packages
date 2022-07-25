#!/bin/bash
set -e


# to fix gpg ioctl error msg
export GPG_TTY=$(tty)

# Lock file preparation:
LOCKFILE=$HOME/.mrpt-master-ppa.lock
DO_REMOVE_LOCK=1
# Make sure we cleanup lockfile on exit:
function cleanup
{
	if [ "$DO_REMOVE_LOCK" == "1" ]; then
		rm $LOCKFILE
	fi
}
trap cleanup EXIT

# Check for another active session:
if [ -f $LOCKFILE ]; then
	# There is a lock file. Honor it and exit... unless it's really old,
	# which might indicate a dangling script (?).
	if [ "$(( $(date +"%s") - $(stat -c "%Y" $LOCKFILE) ))" -gt "7200" ]; then
		# too old: reset lock file
		rm $LOCKFILE
		echo "Removing dangling lockfile."
	else
		DO_REMOVE_LOCK=0
		echo "Exiting: there is another instance running? (lockfile exists)"
		exit;
	fi
fi
# Create lock file:
touch $LOCKFILE

SHA_CACHE_FILE="$HOME/.mrpt-master-ppa.sha"
if [ ! -f $SHA_CACHE_FILE ]; then
    echo " " > $SHA_CACHE_FILE
fi

# Get latest MRPT script:
cd $HOME/mrpt-master

git clean -d -x -f >/dev/null
git checkout . >/dev/null
git pull > /dev/null
git submodule update --init --recursive

# Check if there are new commit(s)?
CURSHA=`git rev-parse HEAD`
LASTSHA=`cat $SHA_CACHE_FILE`

if [ "$CURSHA" != "$LASTSHA" ]; then
    set -x

    # Build PPA and uploads:
    GITBRANCH=master
    TMPDIR=/tmp/mrpt-$GITBRANCH
    PPA_URL=ppa:joseluisblancoc/mrpt-stable

    rm -fr $TMPDIR
    mkdir $TMPDIR
    cd $TMPDIR

    git clone https://github.com/MRPT/mrpt-ubuntu-ppa-packages.git
    cd mrpt-ubuntu-ppa-packages

    # u18.04 bionic:
    MRPT_PKG_EXPORTED_SUBMODULES="nanoflann simpleini" ./build-mrpt-deb-pkg.sh  -s -g $GITBRANCH -d bionic
    (cd $HOME/mrpt_release && dput $PPA_URL *.changes)

    # u20.04 focal:
    MRPT_PKG_EXPORTED_SUBMODULES="nanoflann" ./build-mrpt-deb-pkg.sh  -s -g $GITBRANCH -d focal
    (cd $HOME/mrpt_release && dput $PPA_URL *.changes)

    # u22.04 jammy:
    ./build-mrpt-deb-pkg.sh  -s -g $GITBRANCH -d jammy
    (cd $HOME/mrpt_release && dput $PPA_URL *.changes)

    # Save new commit sha:
    echo $CURSHA > $SHA_CACHE_FILE
fi

# Clean up
rm -fr $HOME/mrpt_debian
rm -fr $HOME/mrpt_release
rm -fr $HOME/mrpt_ubuntu
cd $HOME/mrpt-master
git clean -d -x -f >/dev/null

# self update:
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
(cd $SCRIPT_DIR && git pull)
