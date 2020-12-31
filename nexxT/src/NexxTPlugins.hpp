/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

/**
    \file NexxTPlugins.hpp

    Macros for announcing filters in the c++ world.
*/

#ifndef NEXXT_PLUGINS_HPP
#define NEXXT_PLUGINS_HPP

#include "Filters.hpp"
#include <QtCore/QLibrary>

/*!
    This macro must be present in the Filter's class declaration.

    \param classname the name of the Filter class
*/
#define NEXXT_PLUGIN_DECLARE_FILTER(classname)                                          \
    static nexxT::Filter *nexxt_plugin_create(nexxT::BaseFilterEnvironment *env)        \
    {                                                                                   \
        nexxT::Filter *res = new classname(env);                                        \
        return res;                                                                     \
    }

/*!
    Start to define the plugin introspection code section. To define the introspection
    code section, one of the .cpp files must call these macros once:

    \verbatim embed:rst
        .. code-block:: c

            NEXXT_PLUGIN_DEFINE_START()
            NEXXT_PLUGIN_ADD_FILTER(...)
            NEXXT_PLUGIN_ADD_FILTER(...)
            NEXXT_PLUGIN_ADD_FILTER(...)
            NEXXT_PLUGIN_DEFINE_FINISH()
    \endverbatim
*/
#define NEXXT_PLUGIN_DEFINE_START()                                                     \
    struct {                                                                            \
        QString name;                                                                   \
        nexxT::PluginCreateFunc func;                                                   \
    } nexxt_plugin_functions[] = { {"", 0}

/*!
    Add the given filtertype to the plugin

    \param filtertype the name of the Filter class
*/
#define NEXXT_PLUGIN_ADD_FILTER(filtertype)                                             \
    , {#filtertype, &filtertype::nexxt_plugin_create}

/*!
    Finish the plugin introspection code section
*/
#define NEXXT_PLUGIN_DEFINE_FINISH()                                                    \
    };                                                                                  \
                                                                                        \
    extern "C" FORCE_DLLEXPORT void nexxT_pluginDefinition(QMap<QString, nexxT::PluginCreateFunc> &res)  \
    {                                                                                   \
        res.clear();                                                                    \
        for(uint32_t i = 1;                                                             \
            i < sizeof(nexxt_plugin_functions)/sizeof(nexxt_plugin_functions[0]);       \
            i++)                                                                        \
        {                                                                               \
            res[nexxt_plugin_functions[i].name] = nexxt_plugin_functions[i].func;       \
        }                                                                               \
    }

//! @cond Doxygen_Suppress
namespace nexxT
{
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
};
//! @endcond

#endif
