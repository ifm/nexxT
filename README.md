# nexxT

*nexxT* is a hybrid python/c++ framework targeted mainly at computer vision algorithm developers. Developers can build a graph of plugins interacting via data-driven ports. 

## Design Principles

- Reliable, synchronized data transport across threads. Plugins usually have a thread they run in and do not need to care about locking and data consistency issues. The framework guarantees that all callback methods are called in the thread of the plugin unless explicitely otherwise stated.
- A state machine guarantees consistent behaviour in initialization, active and shutdown phases across plugins and threads.
- Non-intrusive design. Unlike other frameworks, nexxT tries its best to leave the developers the freedom they need. No directory structures are predefined, no build tools are required, the data formats are not predefined.
- Rapid prototyping of algorithms using python, both online (i.e. using an active sensor) and offline (i.e. using data from disk).
- Visualization can be done using python visualization toolkits supporting QT5.
- Efficient pipelines can be built without interacting with the python interpreter by using only C++ plugins.
- The open source license gives freedom to adapt code if necessary.
- Cross platform compatibility for windows and linux.

We used Enterprise Architect for the initial design, and most of the design decisions are still somewhat valid, especially the part about data transport. The design can be found here: https://github.com/ifm/nexxT/blob/master/design/NeXT.eap

## Documentation

The documentation is hosted on [readthedocs](https://nexxt.readthedocs.io).

## Installation

It is highly recommended to use the binary packages from pypi in a virtual environment.

### Linux

Assuming that you have a python3.7+ interpreter in your path, the installation can be done with

    python3 -m venv venv_nexxT
    source venv_nexxT/bin/activate
    python3 -m pip install pip -U
    pip install nexxT
    
### Windows

Assuming that you have a python3.7+ interpreter in your path, the installation is very similar

    python -m venv venv_nexxT
    .\venv_nexxT\Scripts\activate
    python -m pip install pip -U
    pip install nexxT

## Building from source

Building from source requires a QT5 installation suited to the PySide2 version used for the build. It is ok to use 5.14.0 to build against all versions 5.14.x of PySide2 because of QT's binary compatibility. You have to set the environment variable QTDIR to the installation directory of QT. Note that this installation is only used during build time, at runtime, nexxT always uses the QT version shipped with PySide2.

On linux, you will also need llvm and clang installed (because of the shiboken2 dependency). You might need to set the environment variable LLVM_INSTALL_DIR.

The following commands build nexxT from source using the non-recommended pip package of shiboken2-generator.

    git clone https://github.com/ifm/nexxT.git
    cd nexxT/workspace
    python3 -m venv venv
    source venv/bin/activate
    python3 -m pip install pip -U
    pip install -r requirements.txt --find-links https://download.qt.io/official_releases/QtForPython/shiboken2-generator/
    export QTDIR=<path>/<to>/<qt>
    export LLVM_INSTALL_DIR=<path>/<to>/<llvm>
    scons ..
    
When using setup.py to install nexxT, the above requirements shall be also fulfilled and scons is called implicitely from setup.py. Installation from source without using the wheel package is not supported.

## History

Originally we started with a commercial product from the automotive industry in our development, due to the requirements of a project at that time. That product had become more and more outdated and the management was not very keen on paying maintainance costs for updates. After very long discussions about the way forward, we finally got the go for developing an own framework. We have decided to apply an open-source license to it such that it might be useful to other people having the same pain than us as well. During the discussion phase we discussed also other alternatives, and here especially the use of *ROS2*, which claimed to fulfill many of our requirements. We decided against it because of the following reasons:
- The windows support was not production-ready when we tested it. Many *ROS2* components seem to run only on linux, even core *ROS2* components didn't work well on windows. I also experienced hardcoded paths to C:\python37 without the chance to use virtual environments.
- The *ROS2* design is very intrusive. You can't deviate from existing directory structure, build system conventions and operating system versions (some ROS tutorials even suggest to use a VM dedicated for a specific *ROS* version). Side-by-side installations of different ROS versions therefore are difficult.
- The data transport layer of *ROS2* seemed not to fulfill our requirements. We have often use cases where we record data to disk and develop algorithms using that data. Because *ROS2* is mainly designed as a system where algorithms run online, its assumptions about the data transport is low latency in prior of reliability. If in question, *ROS2* decides to throw away messages, and this is very bad for the offline/testing usage when you have not such a big focus on algorithm runtime but maybe more on algorithm quality performance. In this use-case it is a reasonable model that slow algorithms shall be able to slow down the computation, but at the time of evaluation this was not easily possible in *ROS2*. A discussion about this topic can be found here: https://answers.ros.org/question/336930/ros2-fast-publisher-slow-subscriber-is-it-possible-to-slow-down-the-publisher/
- It's not easily possible to start two *ROS2* applications side by side.

## Current Status

The current status is still in an early phase. We use the framework in newer projects, but there is still the chance for API-breaking changes. Some aspects like error handling are still a little rough.
