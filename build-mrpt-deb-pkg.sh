#!/bin/bash
#
# 1) Exports the given MRPT git repo tag/branch to an orig tar ball.
# 2) Creates a temporary branch and merges there this "main" branch with the
#    "debian" directory.
# 3) Updates "d/changelog" with a new snapshot release entry.
# 4) Builds a source .deb package.
#
# JLBC, 2021

set -e  # exit on error
set -x

APPEND_SNAPSHOT_NUM=0
APPEND_LINUX_DISTRO=""
GIT_TAG=""
SHOW_HELP=0

while getopts "hg:sd:" OPTION
do
	case $OPTION in
		s)
			APPEND_SNAPSHOT_NUM=1
			;;
		d)
			APPEND_LINUX_DISTRO=$OPTARG
			;;
		g)
			GIT_TAG=$OPTARG
			;;
		h)
			SHOW_HELP=1
			;;
		?)
			echo "Unknown command line argument!"
			exit 1
			;;
	esac
done

if [ "$GIT_TAG" == "" ] || [ "$SHOW_HELP" == "1" ];
then
	echo "Usage: $0 -g <GIT_TAG|GIT_BRANCH> [-d <DISTRIBUTION>] [-s]"
	echo " With:"
	echo "   - s: Appends a snapshot postfix to the tarball name."
	echo
	exit 0
fi

echo "Creating an MRPT Debian package for git tag: ${GIT_TAG}"

# ==============================================================================
# 1) Exports the given MRPT git repo tag/branch to an orig tar ball.
# ==============================================================================

# Add upstream remote, if not already:
git remote get-url upstream > /dev/null 2>&1 || GIT_MUST_ADD_UPSTREAM=1
echo "GIT_MUST_ADD_UPSTREAM: $GIT_MUST_ADD_UPSTREAM"
if [ "$GIT_MUST_ADD_UPSTREAM" == "1" ];
then
	git remote add upstream git@github.com:MRPT/mrpt.git
fi

git fetch --all
git checkout upstream/${GIT_TAG}
git submodule update --init --recursive

if [ $APPEND_SNAPSHOT_NUM == "1" ];
then
	MAKE_RELEASE_FLAG1=" -s"
fi

if [ ! $APPEND_LINUX_DISTRO == "" ];
then
	MAKE_RELEASE_FLAG2=" -d ${APPEND_LINUX_DISTRO}"
fi

bash packaging/make_release.sh ${MAKE_RELEASE_FLAG1} ${MAKE_RELEASE_FLAG2}

# ==============================================================================
# Restore
# ==============================================================================
git checkout main
git clean -fdx . || true
rm -fr 3rdparty  || true

# ==============================================================================
# 2) Creates a temporary branch and merges there this "main" branch with the
#    "debian" directory.
# ==============================================================================
MRPT_RELEASE_NAME=$(basename $HOME/mrpt_release/mrpt-*.tar.gz .tar.gz)
MRPT_FULL_VERSION=${MRPT_RELEASE_NAME#mrpt-}  # remove prefix

OUT_DIR=$HOME/mrpt_release/$MRPT_RELEASE_NAME

# Create the orig tarball:
(cd $HOME/mrpt_release && ln -s $MRPT_RELEASE_NAME.tar.gz mrpt_$MRPT_FULL_VERSION.orig.tar.gz)

# Extract:
(cd $HOME/mrpt_release && tar -xf $MRPT_RELEASE_NAME.tar.gz)

git archive --format=tar main debian | tar -x -C "${OUT_DIR}"

EMAIL4DEB="Jose Luis Blanco Claraco <joseluisblancoc@gmail.com>"
DEBCHANGE_CMD="--newversion 1:${MRPT_FULL_VERSION}-1"
echo "Changing to a new Debian version: ${DEBCHANGE_CMD}"
echo "Adding a new entry to debian/changelog for distribution ${APPEND_LINUX_DISTRO}"
(cd ${OUT_DIR} && DEBEMAIL=${EMAIL4DEB} debchange $DEBCHANGE_CMD -b --distribution ${APPEND_LINUX_DISTRO} --force-distribution New version of upstream sources.)
(cd ${OUT_DIR} && debuild -S -sa -d)
