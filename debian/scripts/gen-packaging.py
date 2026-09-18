#!/usr/bin/env python3
"""Generate debian/control and debian/*.install for MRPT 3.x.

MRPT 3.x is a colcon workspace of independent modules (see ../mrpt/modules/*).
This script reads each module's package.xml (the upstream source of truth for
dependencies) and emits:

  * debian/control      (binary package stanzas + Build-Depends)
  * debian/<pkg>.install (file lists, assuming a merged colcon install under
                          debian/tmp/usr with -DCMAKE_INSTALL_LIBDIR=lib/<triplet>
                          and python in /usr/lib/python3/dist-packages)

Re-run after upstream module/dependency changes:
    python3 debian/scripts/gen-packaging.py /path/to/mrpt/sources

The MRPT source tree is needed only to read the package.xml files.
"""
import os
import re
import sys
import glob

SOVER = "3.1"  # SOVERSION = MAJOR.MINOR

HERE = os.path.dirname(os.path.abspath(__file__))
DEBIAN = os.path.normpath(os.path.join(HERE, ".."))

# --- locate MRPT sources ---------------------------------------------------
MRPT_SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/code/mrpt")

# --- module classification (from the installed colcon tree) ----------------
# Modules that build a shared library libmrpt_<m>.so -> libmrpt-<m>3.1 + -dev
LIB_MODULES = [
    "bayes", "comms", "config", "containers", "core", "expr", "graphs",
    "graphslam", "gui", "hwdrivers", "img", "imgui", "io", "kinematics",
    "libapps_cli", "libapps_gui", "maps", "math", "nav", "obs", "opengl",
    "poses", "random", "rtti", "serialization", "slam", "system", "tfest",
    "topography", "viz",
]
# Header/cmake-only modules -> only a -dev package
HEADER_ONLY = ["common", "typemeta"]
# Modules that build a pybind11 module -> python3-mrpt-<m>
PYTHON_MODULES = [
    "bayes", "comms", "config", "containers", "core", "expr", "graphs", "gui",
    "img", "io", "kinematics", "maps", "math", "nav", "obs", "opengl", "poses",
    "random", "rtti", "serialization", "slam", "system", "tfest", "topography",
    "viz",
]

# include/mrpt/<ns> directory name when it differs from the short module name
NS_OVERRIDE = {"libapps_cli": "apps_cli", "libapps_gui": "apps_gui"}

# Extra runtime libs produced by a module's colcon package, besides its own:
EXTRA_LIBS = {"gui": ["nanogui"]}  # mrpt_gui also builds libmrpt_nanogui.so

# rosdep/raw key in package.xml -> Debian -dev package(s) for public <depend>s
EXT_DEV = {
    "eigen": ["libeigen3-dev"],
    "libglfw3-dev": ["libglfw3-dev"],
    "opengl": ["libgl-dev", "libglu1-mesa-dev"],
    "assimp-dev": ["libassimp-dev"],
    "cli11": ["libcli11-dev"],
    "libzstd-dev": ["libzstd-dev"],
    "libxrandr": ["libxrandr-dev"],
    "libxxf86vm": ["libxxf86vm-dev"],
    "wxwidgets": ["libwxgtk3.2-dev"],
    "wx-common": ["wx-common"],
    "qtbase5-dev": ["qtbase5-dev"],
    "libqt5-opengl-dev": ["libqt5opengl5-dev"],
}


def module_dir(short):
    """Return the source dir for a short module name."""
    return os.path.join(MRPT_SRC, "modules", "mrpt_" + short)


def parse_package_xml(short):
    """Return (mrpt_deps, ext_deps) from <depend> tags (public deps only)."""
    path = os.path.join(module_dir(short), "package.xml")
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    deps = re.findall(r"<depend>([^<]+)</depend>", txt)
    mrpt = [d.strip()[5:] for d in deps if d.strip().startswith("mrpt_")]
    ext = [d.strip() for d in deps if not d.strip().startswith("mrpt_")]
    return mrpt, ext


def debname(short):
    return "libmrpt-" + short.replace("_", "-")


def wrap_depends(items):
    """Format a Depends-style list, one per line, indented."""
    uniq = []
    for it in items:
        if it and it not in uniq:
            uniq.append(it)
    return ",\n         ".join(uniq)


# ---------------------------------------------------------------------------
# Build dependency graph
# ---------------------------------------------------------------------------
ALL_MODULES = LIB_MODULES + HEADER_ONLY
mrpt_deps = {}
ext_deps = {}
for m in ALL_MODULES:
    md, ed = parse_package_xml(m)
    mrpt_deps[m] = md
    ext_deps[m] = ed

SYN = "${source:Synopsis}"
EXT = "${source:Extended-Description}"


def desc(summary, body):
    """Return a full 'Description:' control field.

    Uses the ${source:Synopsis}/${source:Extended-Description} substvars, which
    dpkg-gencontrol derives from the Description field of the Source paragraph.
    """
    lines = ["Description: %s - %s" % (SYN, summary), " %s" % EXT, " ."]
    for b in body:
        lines.append(" " + b)
    return "\n".join(lines)


stanzas = []
install_files = {}  # pkgname -> list of install lines


def lib_pkg(short):
    p = debname(short) + SOVER
    stanzas.append("\n".join([
        "Package: %s" % p,
        "Section: libs",
        "Architecture: any",
        "Multi-Arch: same",
        "Depends: ${shlibs:Depends}, ${misc:Depends}",
        desc("%s library" % short,
                                ["Runtime shared library of the MRPT %s module." % short]),
    ]))
    install_files[p] = ["usr/lib/*/libmrpt_%s.so.*" % short]


def dev_pkg(short, arch="any", multiarch="same", header_only=False):
    p = debname(short) + "-dev"
    deps = ["${misc:Depends}"]
    if not header_only:
        deps.append("%s%s (= ${binary:Version})" % (debname(short), SOVER))
    for d in mrpt_deps[short]:
        deps.append(debname(d) + "-dev")
    for e in ext_deps[short]:
        # Known non-Debian rosdep keys map via EXT_DEV; Debian-style names
        # (lib*-dev) pass through unchanged.
        deps += EXT_DEV.get(e, [e])
    fields = [
        "Package: %s" % p,
        "Section: libdevel",
        "Architecture: %s" % arch,
        "Multi-Arch: %s" % multiarch,
        "Depends: " + wrap_depends(deps),
        desc("%s development files" % short,
                                ["Headers, CMake config and the development symlink "
                                 "for the MRPT %s module." % short]),
    ]
    stanzas.append("\n".join(fields))

    lines = []
    if not header_only:
        lines.append("usr/lib/*/libmrpt_%s.so" % short)
    ns = NS_OVERRIDE.get(short, short)
    lines.append("usr/include/mrpt/%s/" % ns)
    # umbrella header mrpt/<ns>.h if it exists in the source tree
    if os.path.exists(os.path.join(module_dir(short), "include", "mrpt", ns + ".h")):
        lines.append("usr/include/mrpt/%s.h" % ns)
    lines.append("usr/lib/*/mrpt_%s/cmake/" % short)
    install_files[p] = lines


# Library modules: lib + dev
for m in LIB_MODULES:
    lib_pkg(m)
    dev_pkg(m)

# Stray top-level core headers not under a module namespace dir:
install_files[debname("core") + "-dev"] += [
    "usr/include/mrpt/3rdparty/",
    "usr/include/mrpt/registerAllClasses.h",
    "usr/include/mrpt/version.h",
]

# Extra libs (nanogui from gui)
for parent, extras in EXTRA_LIBS.items():
    for ex in extras:
        p = debname(ex) + SOVER
        builtusing = ""
        extra_desc = ["Runtime shared library (vendored %s fork used by MRPT GUI classes)." % ex]
        fields = [
            "Package: %s" % p,
            "Section: libs",
            "Architecture: any",
            "Multi-Arch: same",
            "Depends: ${shlibs:Depends}, ${misc:Depends}",
        ]
        if ex == "nanogui":
            fields.append("Built-Using: fonts-roboto-fontface (= ${fonts-roboto-fontface:version})")
        fields.append(desc("%s library" % ex, extra_desc))
        stanzas.append("\n".join(fields))
        install_files[p] = ["usr/lib/*/libmrpt_%s.so.*" % ex]
        # dev for the extra lib
        pdev = debname(ex) + "-dev"
        ddeps = ["${misc:Depends}", "%s%s (= ${binary:Version})" % (debname(ex), SOVER)]
        if ex == "nanogui":
            ddeps += ["libmrpt-gui-dev", "libglfw3-dev"]
        stanzas.append("\n".join([
            "Package: %s" % pdev,
            "Section: libdevel",
            "Architecture: any",
            "Multi-Arch: same",
            "Depends: " + wrap_depends(ddeps),
            desc("%s development files" % ex,
                                    ["Development files for the vendored %s fork." % ex]),
        ]))
        install_files[pdev] = [
            "usr/lib/*/libmrpt_%s.so" % ex,
            "usr/include/mrpt/%s/" % ex,
            "usr/include/%s/" % ex,   # vendored public headers (top-level)
            "usr/lib/*/mrpt_%s/cmake/" % ex,
        ]

# Header-only modules
# common: ships cmake helpers + common headers under share/mrpt_common (arch all)
stanzas.append("\n".join([
    "Package: libmrpt-common-dev",
    "Section: libdevel",
    "Architecture: all",
    "Multi-Arch: foreign",
    "Depends: ${misc:Depends}, cmake",
    desc("common development files",
                            ["CMake helper scripts and common headers shared by all MRPT modules."]),
]))
install_files["libmrpt-common-dev"] = [
    "usr/share/mrpt_common/cmake/",
    "usr/share/mrpt_common/common_headers/",
    "usr/share/mrpt_common/common_sources/",
]

# typemeta: header-only but uses the generic cmake export under lib/<triplet>
dev_pkg("typemeta", arch="any", multiarch="same", header_only=True)

# data: cmake stub (arch-indep path lib/cmake/mrpt_data); data files go to mrpt-common
stanzas.append("\n".join([
    "Package: libmrpt-data-dev",
    "Section: libdevel",
    "Architecture: all",
    "Multi-Arch: foreign",
    "Depends: ${misc:Depends}",
    desc("data CMake config",
                            ["CMake config exposing the path to MRPT example datasets and config files."]),
]))
install_files["libmrpt-data-dev"] = ["usr/lib/cmake/mrpt_data/"]

# python packages
for m in PYTHON_MODULES:
    p = "python3-mrpt-" + m.replace("_", "-")
    deps = ["${python3:Depends}", "${shlibs:Depends}", "${misc:Depends}"]
    if m != "core":
        deps.append("python3-mrpt-core (= ${binary:Version})")
    # mirror C++ module deps that also have python bindings
    for d in mrpt_deps.get(m, []):
        if d in PYTHON_MODULES and d != m and d != "core":
            deps.append("python3-mrpt-" + d.replace("_", "-"))
    stanzas.append("\n".join([
        "Package: %s" % p,
        "Section: python",
        "Architecture: any",
        "Multi-Arch: allowed",
        "Depends: " + wrap_depends(deps),
        desc("Python 3 bindings for mrpt %s" % m,
                                ["Python 3 wrapper for the MRPT %s module." % m]),
    ]))
    # 'mrpt' is an implicit PEP 420 namespace package (no root __init__.py),
    # so each module independently ships only its own subpackage dir.
    install_files[p] = ["usr/lib/python3/dist-packages/mrpt/%s/" % m]

# python metapackage
py_all = ["python3-mrpt-" + m.replace("_", "-") + " (= ${binary:Version})" for m in PYTHON_MODULES]
stanzas.append("\n".join([
    "Package: python3-mrpt",
    "Section: python",
    "Architecture: any",
    "Multi-Arch: allowed",
    "Depends: ${misc:Depends}, " + wrap_depends(py_all),
    desc("Python 3 bindings (metapackage)",
                            ["This metapackage installs the Python 3 bindings for all MRPT modules."]),
]))

# apps
stanzas.append("\n".join([
    "Package: mrpt-apps",
    "Architecture: any",
    "Depends: ${shlibs:Depends}, ${misc:Depends}",
    "Recommends: mrpt-common (= ${source:Version})",
    desc("console and GUI applications",
                            ["A set of console and GUI robotics applications built on MRPT",
                             "(rawlog-grabber, RawLogViewer, SceneViewer3D, icp-slam, pf-localization,",
                             "camera-calib, navlog-viewer, and many more)."]),
]))
install_files["mrpt-apps"] = [
    "usr/bin/*",
    "usr/share/man/man1/*",
    "share/applications/*.desktop usr/share/applications",
    "share/pixmaps/* usr/share/pixmaps",
    "share/mime/packages/* usr/share/mime/packages",
    "share/metainfo/* usr/share/metainfo",
]

# datasets/config files (former mrpt-common content)
stanzas.append("\n".join([
    "Package: mrpt-common",
    "Architecture: all",
    "Multi-Arch: foreign",
    "Depends: ${misc:Depends}",
    desc("example datasets and config files",
                            ["Example datasets and configuration files used by several MRPT applications."]),
]))
install_files["mrpt-common"] = [
    "usr/share/mrpt_data/config_files/",
    "usr/share/mrpt_data/datasets/",
]

# docs
stanzas.append("\n".join([
    "Package: mrpt-doc",
    "Section: doc",
    "Architecture: all",
    "Multi-Arch: foreign",
    "Depends: ${misc:Depends}, libjs-jquery",
    desc("documentation and examples",
                            ["HTML documentation and commented C++ examples for the MRPT libraries."]),
]))

# libmrpt-dev metapackage (all -dev)
all_dev = []
for m in LIB_MODULES:
    all_dev.append(debname(m) + "-dev (= ${binary:Version})")
all_dev.append("libmrpt-nanogui-dev (= ${binary:Version})")
all_dev.append("libmrpt-common-dev (= ${source:Version})")
all_dev.append("libmrpt-typemeta-dev (= ${binary:Version})")
all_dev.append("libmrpt-data-dev (= ${source:Version})")
stanzas.append("\n".join([
    "Package: libmrpt-dev",
    "Section: libdevel",
    "Architecture: all",
    "Multi-Arch: foreign",
    "Depends: ${misc:Depends},\n         " + wrap_depends(all_dev),
    desc("metapackage for all development files",
                            ["This metapackage installs all MRPT -dev packages."]),
]))

# ---------------------------------------------------------------------------
# Build-Depends (union of all package.xml build/test deps mapped to Debian)
# ---------------------------------------------------------------------------
BUILD_DEPENDS = """dpkg-dev (>= 1.22.5), debhelper-compat (= 13),
 dh-sequence-python3,
 cmake,
 chrpath,
 pkgconf,
 perl,
 colcon,
 python3-colcon-cmake,
 python3-colcon-defaults,
 python3-colcon-ros,
 python3-colcon-recursive-crawl,
 python3-colcon-package-information,
 python3-colcon-package-selection,
 python3-colcon-parallel-executor,
 python3-colcon-output,
 python3-colcon-library-path,
 python3-colcon-metadata,
 libeigen3-dev,
 libglfw3-dev,
 libgl-dev,
 libglu1-mesa-dev,
 libxrandr-dev,
 libxxf86vm-dev,
 libassimp-dev,
 libcli11-dev,
 libzstd-dev,
 libwxgtk3.2-dev,
 wx-common,
 qtbase5-dev,
 libqt5opengl5-dev,
 libsimpleini-dev,
 libicu-dev,
 libnanoflann-dev,
 libfyaml-dev,
 libtinyxml2-dev,
 liboctomap-dev,
 zlib1g-dev,
 libgtest-dev,
 libglew-dev,
 fonts-roboto-fontface,
 pybind11-dev,
 python3-all-dev,
 python3-numpy,
 python3-setuptools,
 libavcodec-dev,
 libavformat-dev,
 libavutil-dev,
 libswscale-dev,
 libdc1394-dev [linux-any],
 libopenni2-dev,
 libpcap-dev,
 libusb-1.0-0-dev [linux-any],
 libftdi1-dev"""

SOURCE = """Source: mrpt
Section: science
Priority: optional
Maintainer: Jose Luis Blanco Claraco <joseluisblancoc@gmail.com>
Build-Depends: %s
Standards-Version: 4.7.3
Homepage: https://www.mrpt.org/
Vcs-Git: https://salsa.debian.org/robotics-team/mrpt.git
Vcs-Browser: https://salsa.debian.org/robotics-team/mrpt
Rules-Requires-Root: no
Description: Mobile Robot Programming Toolkit
 The Mobile Robot Programming Toolkit (MRPT) is an extensive, cross-platform,
 and open source C++ library aimed to help robotics researchers to design and
 implement algorithms in the fields of Simultaneous Localization and Mapping
 (SLAM), computer vision, and motion planning (obstacle avoidance).

""" % BUILD_DEPENDS

# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------
control = SOURCE + "\n\n".join(stanzas) + "\n"
with open(os.path.join(DEBIAN, "control"), "w", encoding="utf-8") as f:
    f.write(control)

# remove stale .install files
for old in glob.glob(os.path.join(DEBIAN, "*.install")):
    os.remove(old)
for pkg, lines in install_files.items():
    with open(os.path.join(DEBIAN, pkg + ".install"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

print("Generated control with %d binary packages and %d .install files" %
      (control.count("\nPackage: ") + control.count("Package: ") - control.count("\nPackage: "),
       len(install_files)))
n_pkgs = len([s for s in stanzas if s.startswith("Package:")])
print("  binary package stanzas:", n_pkgs)
print("  .install files:", len(install_files))
