#ifndef NEXXT_SHARED_POINTER_TYPES_HPP
#define NEXXT_SHARED_POINTER_TYPES_HPP

#include <QtCore/QSharedPointer>

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
}

#endif
