/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

/**
    \file Filters.hpp
    The interface corresponding to \verbatim embed:rst :py:mod:`nexxT.interface.Filters` \endverbatim
*/

#ifndef NEXXT_FILTERS_HPP
#define NEXXT_FILTERS_HPP

#include <cstdint>
#include <QtCore/QString>
#include <QtCore/QObject>
#include <QtCore/QList>

#include "NexxTLinkage.hpp"
#include "Ports.hpp"

namespace nexxT
{

    /*!
        This struct is the C++ variant of \verbatim embed:rst:inline :py:class:`nexxT.interface.Filters.FilterState`
        \endverbatim
    */
    struct DLLEXPORT FilterState
    {
        static const int CONSTRUCTING = 0;      //!< During constructor
        static const int CONSTRUCTED = 1;       //!< After constructor before calling onInit
        static const int INITIALIZING = 2;      //!< During onInit
        static const int INITIALIZED = 3;       //!< After onInit before onOpen
        static const int OPENING = 4;           //!< During onOpen
        static const int OPENED = 5;            //!< After onOpen before onStart
        static const int STARTING = 6;          //!< During onStart
        static const int ACTIVE = 7;            //!< After onStart before onStop
        static const int STOPPING = 8;          //!< During onStop
        static const int CLOSING = 9;           //!< During onClose
        static const int DEINITIALIZING = 10;   //!< During onDeinit
        static const int DESTRUCTING = 11;      //!< During destructor
        static const int DESTRUCTED = 12;       //!< After destructor

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.FilterState.state2str` \endverbatim
        */
        static QString state2str(int state);
    };

    class Filter;
    struct FilterD;
    class BaseFilterEnvironment;
    class PropertyCollection;

    /*!
        A typedef for a Filter instance handled by a shared pointer.
    */
    typedef QSharedPointer<Filter> SharedFilterPtr;

    /*!
        This class is the C++ variant of \verbatim embed:rst:inline :py:class:`nexxT.interface.Filters.Filter`
        \endverbatim
    */
    class DLLEXPORT Filter : public QObject
    {
        Q_OBJECT 

        FilterD *const d;
    protected:
        /*!
            Constructor, see \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.__init__`
            \endverbatim
        */
        Filter(bool dynInPortsSupported, bool dynOutPortsSupported, BaseFilterEnvironment *env);

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.propertyCollection` \endverbatim
        */
        PropertyCollection *propertyCollection();
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.guiState` \endverbatim
        */
        PropertyCollection *guiState();

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.addStaticPort` \endverbatim
        */
        void addStaticPort(const SharedPortPtr &port);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.addStaticOutputPort` \endverbatim
        */
        SharedPortPtr addStaticOutputPort(const QString &name);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.addStaticInputPort` \endverbatim
        */
        SharedPortPtr addStaticInputPort(const QString &name, int queueSizeSamples = 1, double queueSizeSeconds = -1);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.removeStaticPort` \endverbatim
        */
        void removeStaticPort(const SharedPortPtr &port);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.getDynamicInputPorts` \endverbatim
        */
        PortList getDynamicInputPorts();
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.getDynamicOutputPorts` \endverbatim
        */
        PortList getDynamicOutputPorts();

    public:
        /*!
            Destructor
        */
        virtual ~Filter();
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.onInit` \endverbatim
        */
        virtual void onInit();
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.onOpen` \endverbatim
        */
        virtual void onOpen();
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.onStart` \endverbatim
        */
        virtual void onStart();
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.onPortDataChanged` \endverbatim
        */
        virtual void onPortDataChanged(const InputPortInterface &inputPort);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.onStop` \endverbatim
        */
        virtual void onStop();
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.onClose` \endverbatim
        */
        virtual void onClose();
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.onDeinit` \endverbatim
        */
        virtual void onDeinit();
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.onSuggestDynamicPorts` \endverbatim
        */
        virtual QList<QList<QString> > onSuggestDynamicPorts();

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Filters.Filter.environment` \endverbatim
        */
        BaseFilterEnvironment *environment() const;

        /*!
            Return a shared pointer referencing the given instance. The ownership of the pointer is transferred to the
            shared pointer.
        */
        static SharedFilterPtr make_shared(Filter *filter);
    };
};

#endif
