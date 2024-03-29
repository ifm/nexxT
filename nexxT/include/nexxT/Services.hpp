/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

/**
    \file Services.hpp
    The interface corresponding to \verbatim embed:rst :py:mod:`nexxT.interface.Services \endverbatim
*/

#ifndef NEXXT_SERVICES_HPP
#define NEXXT_SERVICES_HPP

#include <QtCore/QObject>
#include <QtCore/QSharedPointer>

#include "nexxT/NexxTLinkage.hpp"
#include "nexxT/SharedPointerTypes.hpp"

namespace nexxT
{
    struct ServicesD;

    /*!
        This class is the C++ variant of \verbatim embed:rst:inline :py:class:`nexxT.interface.Services.Services`
        \endverbatim
    */
    class DLLEXPORT Services
    {
        ServicesD *d;
        static Services *_singleton;

        SharedQObjectPtr _getService(const QString &name);
        void _addService(const QString &name, const SharedQObjectPtr &service);
        void _removeService(const QString &name);
        void _removeAll();

        static Services *singleton();

    public:
        /*!
            Constructor (intended to be used by the nexxT framework only)
        */
        Services();
        /*!
            Destructor
        */
        virtual ~Services();

        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Services.Services.getService` \endverbatim
        */
        static SharedQObjectPtr getService(const QString &name);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Services.Services.addService` \endverbatim
        */
        static void addService(const QString &name, QObject *service);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Services.Services.removeService` \endverbatim
        */
        static void removeService(const QString &name);
        /*!
            See \verbatim embed:rst:inline :py:meth:`nexxT.interface.Services.Services.removeAll` \endverbatim
        */
        static void removeAll();
    };
};

#endif
