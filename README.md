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

## History

Originally we started with a commercial product from the automotive industry in our development, due to the requirements of a project at that time. That product had become more and more outdated and the management was not very keen on paying maintainance costs for updates. After very long discussions about the way forward, we finally got the go for developing an own framework. We have decided to apply an open-source license to it such that it might be useful to other people having the same pain than us as well. During the discussion phase we discussed also other alternatives, and here especially the use of *ROS2*, which claimed to fulfill many of our requirements. We decided against it because of the following reasons:
- The windows support was not production-ready when we tested it. Many *ROS2* components seem to run only on linux, even core *ROS2* components didn't work well on windows. I also experienced hardcoded paths to C:\python37 without the chance to use virtual environments.
- The *ROS2* design is very intrusive. You can't deviate from existing directory structure, build system conventions and operating system versions (some ROS tutorials even suggest to use a VM dedicated for a specific *ROS* version). Side-by-side installations of different ROS versions therefore are difficult.
- The data transport layer of *ROS2* seemed not to fulfill our requirements. We have often use cases where we record data to disk and develop algorithms using that data. Because *ROS2* is mainly designed as a system where algorithms run online, its assumptions about the data transport is low latency in prior of reliability. If in question, *ROS2* decides to throw away messages, and this is very bad for the offline/testing usage when you have not such a big focus on algorithm runtime but maybe more on algorithm quality performance. In this use-case it is a reasonable model that slow algorithms shall be able to slow down the computation, but at the time of evaluation this was not easily possible in *ROS2*. A discussion about this topic can be found here: https://answers.ros.org/question/336930/ros2-fast-publisher-slow-subscriber-is-it-possible-to-slow-down-the-publisher/
- It's not easily possible to start two *ROS2* applications side by side.

## Current Status

The current status is still in an early phase. We use the framework in newer projects, but there is still the chance for API-breaking changes. Documentation is pretty poor at the moment. It is planned to come up with some example use cases.