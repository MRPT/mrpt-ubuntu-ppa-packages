Repository with script to create PPA or custom Debian snapshot packages of the
MRPT project.

The `debian` directory is maintained in a separate git branch for each i
target distribution.


Usage example:

    MRPT_PKG_EXPORTED_SUBMODULES=nanoflann ./build-mrpt-deb-pkg.sh  -s -g develop -d bionic
