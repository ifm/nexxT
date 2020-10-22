/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "NexxTPlugins.hpp"
#include "Logger.hpp"
#include <QtCore/QMap>

using namespace nexxT;

namespace nexxT
{
    struct PluginInterfaceD
    {
        QMap<QString, QSharedPointer<QLibrary> > loadedLibs;
    };
}

PluginInterface *PluginInterface::_singleton;

void PluginInterface::loadLib(const QString &file)
{
    if( !d->loadedLibs.contains(file) )
    {
        NEXXT_LOG_DEBUG(QString("Loading plugin %1").arg(file));
        QSharedPointer<QLibrary> lib(new QLibrary(file));
        if(!lib->load())
        {
            throw std::runtime_error((QString("Cannot load lib %1 (%2).").arg(file).arg(lib->errorString())).toStdString());
        }
        d->loadedLibs.insert(file, lib);
    }
}

PluginInterface* PluginInterface::singleton()
{
    if( !_singleton )
    {
        _singleton = new PluginInterface();
    }
    return _singleton;
}

PluginInterface::PluginInterface() : d(new PluginInterfaceD())
{
    NEXXT_LOG_INTERNAL(QString("PluginInterface::PluginInterface %1").arg(uint64_t(this), 0, 16));
}

PluginInterface::~PluginInterface()
{
    NEXXT_LOG_INTERNAL(QString("PluginInterface::~PluginInterface %1").arg(uint64_t(this), 0, 16));
    unloadAll();
    delete d;
}

Filter *PluginInterface::create(const QString &lib, const QString &function, BaseFilterEnvironment *env)
{
    PluginDefinitionFunc f = PluginDefinitionFunc(d->loadedLibs[lib]->resolve("nexxT_pluginDefinition"));
    if(!f)
    {
        throw std::runtime_error((QString("Cannot resolve '%1' in %2 (%3).").arg(function).arg(lib).arg(d->loadedLibs[lib]->errorString())).toStdString());
    }
    QMap<QString, PluginCreateFunc> m;
    f(m);
    if(!m.contains(function))
    {
        throw std::runtime_error((QString("Cannot find function '%1' in function table of %a.").arg(function).arg(lib)).toStdString());
    }
    Filter *res = m[function](env);
    return res;
}

QStringList PluginInterface::availableFilters(const QString &lib)
{
    loadLib(lib);
    PluginDefinitionFunc f = PluginDefinitionFunc(d->loadedLibs[lib]->resolve("nexxT_pluginDefinition"));
    if(!f)
    {
        throw std::runtime_error((QString("Cannot resolve 'nexxT_pluginDefinition' in %1 (%2).").arg(lib).arg(d->loadedLibs[lib]->errorString())).toStdString());
    }
    QMap<QString, PluginCreateFunc> m;
    f(m);
    return m.keys();
}

void PluginInterface::unloadAll()
{
    foreach(QSharedPointer<QLibrary> lib, d->loadedLibs)
    {
        NEXXT_LOG_DEBUG(QString("Unloading plugin %1").arg(lib->fileName()));
        lib->unload();
    }
    d->loadedLibs.clear();
}
