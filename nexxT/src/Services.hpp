/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef NEXXT_SERVICES_HPP
#define NEXXT_SERVICES_HPP

#include <QtCore/QObject>
#include <QtCore/QSharedPointer>

#include "NexxTLinkage.hpp"

namespace nexxT
{
    struct ServicesD;

    typedef QSharedPointer<QObject> SharedQObjectPtr;

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
        Services();
        virtual ~Services();

        static SharedQObjectPtr getService(const QString &name);
        static void addService(const QString &name, QObject *service);
        static void removeService(const QString &name);
        static void removeAll();
    };
};

#endif
