/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "Services.hpp"
#include "Logger.hpp"
#include <QtCore/QMutex>
#include <QtCore/QMap>

using namespace nexxT;

Services *Services::_singleton = 0;

typedef QSharedPointer<QMutex> SharedMutexPtr;

namespace nexxT
{
    struct ServicesD
    {
        SharedMutexPtr mutex;
        QMap<QString, SharedQObjectPtr > map;
    };
};

Services::Services()
    : d(new ServicesD{SharedMutexPtr(new QMutex(QMutex::Recursive))})
{
}

Services::~Services()
{
    delete d;
}

SharedQObjectPtr Services::_getService(const QString &name)
{
    QMutexLocker locker(d->mutex.get());
    auto it = d->map.find(name);
    if(it == d->map.end())
    {
        if( name != "Logging" )
        {
            NEXXT_LOG_WARN(QString("Service %1 not found. Returning NULL.").arg(name));
        }
        return SharedQObjectPtr();
    } else
    {
        return it.value();
    }
}

void Services::_addService(const QString &name, const SharedQObjectPtr &service)
{
    QMutexLocker locker(d->mutex.get());
    if( (d->map.find(name) != d->map.end() ) )
    {
        NEXXT_LOG_WARN(QString("Service %1 already existing; automatically removing it.").arg(name));
        removeService(name);
    }
    NEXXT_LOG_INFO(QString("adding service %1").arg(name));
    d->map[name] = service;
}

void Services::_removeService(const QString &name)
{
    QMutexLocker locker(d->mutex.get());
    if( (d->map.find(name) == d->map.end() ) )
    {
        NEXXT_LOG_WARN(QString("Service %1 doesn't exist. Not removing.").arg(name));
    }
    NEXXT_LOG_INFO(QString("removing service %1").arg(name));
    d->map.remove(name);
}

void Services::_removeAll()
{
    QMutexLocker locker(d->mutex.get());
    QStringList keys = d->map.keys();
    for(QString key : keys)
    {
        _removeService(key);
    }
}

Services *Services::singleton()
{
    if( !_singleton )
    {
        _singleton = new Services();
    }
    return _singleton;
}

SharedQObjectPtr Services::getService(const QString &name)
{
    return singleton()->_getService(name);
}

void Services::addService(const QString &name, QObject *service)
{
    SharedQObjectPtr srv = SharedQObjectPtr(service);
    singleton()->_addService(name, srv);
}

void Services::removeService(const QString &name)
{
    singleton()->_removeService(name);
}

void Services::removeAll()
{
    singleton()->_removeAll();
}
