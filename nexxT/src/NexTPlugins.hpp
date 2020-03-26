/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef NEXT_PLUGINS_HPP
#define NEXT_PLUGINS_HPP

#include "Filters.hpp"
#include "NexTConfig.hpp"
#include <QtCore/QLibrary>

#define NEXT_PLUGIN_DECLARE_FILTER(classname)                                           \
    static nexxT::Filter *next_plugin_create(nexxT::BaseFilterEnvironment *env)           \
    {                                                                                   \
        nexxT::Filter *res = new classname(env);                                         \
        return res;                                                                     \
    }

#define NEXT_PLUGIN_DEFINE_START()                                                      \
    struct {                                                                            \
        QString name;                                                                   \
        nexxT::PluginCreateFunc func;                                                    \
    } next_plugin_functions[] = { {"", 0}

#define NEXT_PLUGIN_ADD_FILTER(filtertype)                                              \
    , {#filtertype, &filtertype::next_plugin_create}

#define NEXT_PLUGIN_DEFINE_FINISH()                                                     \
    };                                                                                  \
                                                                                        \
    extern "C" FORCE_DLLEXPORT void nexT_pluginDefinition(QMap<QString, nexxT::PluginCreateFunc> &res)  \
    {                                                                                   \
        res.clear();                                                                    \
        for(int i = 1;                                                                  \
            i < sizeof(next_plugin_functions)/sizeof(next_plugin_functions[0]);         \
            i++)                                                                        \
        {                                                                               \
            res[next_plugin_functions[i].name] = next_plugin_functions[i].func;         \
        }                                                                               \
    }

START_NAMESPACE
    typedef nexxT::Filter *(*PluginCreateFunc)(nexxT::BaseFilterEnvironment *env);
    typedef void (*PluginDefinitionFunc)(QMap<QString, nexxT::PluginCreateFunc> &res);
    
    struct PluginInterfaceD;

    class DLLEXPORT PluginInterface
    {
        PluginInterfaceD *d;
        static PluginInterface *_singleton;

        void loadLib(const QString &lib);
        PluginInterface();
    public:
        static PluginInterface* singleton();

        virtual ~PluginInterface();

        Filter *create(const QString &lib, const QString &function, BaseFilterEnvironment *env);
        QStringList availableFilters(const QString &lib);
        void unloadAll();
    };
STOP_NAMESPACE

#endif
