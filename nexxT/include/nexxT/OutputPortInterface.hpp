/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

/**
    \file OutputPortInterface.hpp
    The interface corresponding to \verbatim embed:rst :py:mod:`nexxT.interface.Ports` \endverbatim
*/

#ifndef NEXXT_OUTPUT_PORT_INTERFACE_HPP
#define NEXXT_OUTPUT_PORT_INTERFACE_HPP

#include <QtCore/QObject>
#include <QtCore/QSemaphore>
#include "nexxT/NexxTLinkage.hpp"
#include "nexxT/SharedPointerTypes.hpp"
#include "nexxT/Ports.hpp"

namespace nexxT
{
    class BaseFilterEnvironment;
 
    /*!
        This class is the C++ variant of \verbatim embed:rst:inline :py:class:`nexxT.interface.Ports.OutputPortInterface`
        \endverbatim.

        In contrast to the python version, this class is not abstract but directly implements the functionality.
    */
    class DLLEXPORT OutputPortInterface : public Port
    {
        Q_OBJECT
        
    signals:
        /*!
            QT signal for transmitting a sample over threads. Note that this signal is not intended to be used directly.
            Use the transmit method instead.

            See \verbatim embed:rst:inline :py:attr:`nexxT.interface.Ports.OutputPortInterface.transmitSample`
            \endverbatim.
        */
        void transmitSample(const QSharedPointer<const nexxT::DataSample> &sample);

    public:
        /*!
            Constructor.

            See \verbatim embed:rst:inline :py:func:`nexxT.interface.Ports.OutputPort`
            \endverbatim.
        */
        OutputPortInterface(bool dynamic, const QString &name, BaseFilterEnvironment *env);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.OutputPortInterface.transmit`
            \endverbatim.
        */
        void transmit(const SharedDataSamplePtr &sample);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Ports.OutputPortInterface.clone`
            \endverbatim.
        */
        virtual SharedPortPtr clone(BaseFilterEnvironment *) const;

        /*!
            Called by the nexxT framework, not intended to be used directly.
        */
        static void setupDirectConnection(const SharedPortPtr &, const SharedPortPtr &);
        /*!
            Called by the nexxT framework, not intended to be used directly.
        */
        static QObject *setupInterThreadConnection(const SharedPortPtr &, const SharedPortPtr &, QThread &, int width);
    };

};

#endif
