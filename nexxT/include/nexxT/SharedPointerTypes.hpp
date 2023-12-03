#ifndef NEXXT_SHARED_POINTER_TYPES_HPP
#define NEXXT_SHARED_POINTER_TYPES_HPP

#include <QtCore/QSharedPointer>

class QObject;

namespace nexxT
{
    class Port;
    class InputPortInterface;
    class OutputPortInterface;
    class DataSample;

    /*!
        A typedef for a Datasample handled by a shared pointer.
    */
    typedef QSharedPointer<const DataSample> SharedDataSamplePtr;

    /*!
        A typedef for a Port instance handled by a shared pointer.
    */
    typedef QSharedPointer<Port> SharedPortPtr;

    /*!
        A typedef for a Port instance handled by a shared pointer.
    */
    typedef QSharedPointer<InputPortInterface> SharedInputPortPtr;

    /*!
        A typedef for a Port instance handled by a shared pointer.
    */
    typedef QSharedPointer<OutputPortInterface> SharedOutputPortPtr;

    /*!
        A typedef for a list of ports.
    */
    typedef QList<QSharedPointer<Port> > PortList;

    /*!
        A typedef for a QObject handled by a shared pointer.

        In principle it is not really necessary to use a shared pointer to handle QObjects, because of the parent/child
        ownership principle. However for consistency, the design decision has been made to also wrap the services in a
        smart pointer just like datasamples, filters and ports.
    */
    typedef QSharedPointer<QObject> SharedQObjectPtr;
}

#endif
