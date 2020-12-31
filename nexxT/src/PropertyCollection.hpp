/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

/**
    \file PropertyCollection.hpp
    The interface corresponding to \verbatim embed:rst :py:mod:`nexxT.interface.PropertyCollections \endverbatim
*/

#ifndef NEXXT_PROPERTY_COLLECTION_HPP
#define NEXXT_PROPERTY_COLLECTION_HPP

#include <QtCore/QObject>
#include <QtCore/QVariant>
#include "NexxTLinkage.hpp"

namespace nexxT
{
    /*!
        This class is the C++ variant of \verbatim embed:rst:inline
        :py:class:`nexxT.interface.PropertyCollections.PropertyHandler`
        \endverbatim
    */
    class DLLEXPORT PropertyHandler
    {        
    public:
        /*!
            Constructor
        */
        PropertyHandler();
        /*!
            Destructor
        */
        virtual ~PropertyHandler();
        /*!
            See \verbatim embed:rst:inline
            :py:meth:`nexxT.interface.PropertyCollections.PropertyHandler.options` \endverbatim

            The python dict is translated to a QVariantMap in the C++ world.
        */
        virtual QVariantMap options();
        /*!
            See \verbatim embed:rst:inline
            :py:meth:`nexxT.interface.PropertyCollections.PropertyHandler.fromConfig` \endverbatim
        */
        virtual QVariant fromConfig(const QVariant &value);
        /*!
            See \verbatim embed:rst:inline
            :py:meth:`nexxT.interface.PropertyCollections.PropertyHandler.toConfig` \endverbatim
        */
        virtual QVariant toConfig(const QVariant &value);
        /*!
            See \verbatim embed:rst:inline
            :py:meth:`nexxT.interface.PropertyCollections.PropertyHandler.toViewValue` \endverbatim
        */
        virtual QVariant toViewValue(const QVariant &value);
        /*!
            See \verbatim embed:rst:inline
            :py:meth:`nexxT.interface.PropertyCollections.PropertyHandler.createEditor` \endverbatim
        */
        virtual QWidget *createEditor(QWidget *parent);
        /*!
            See \verbatim embed:rst:inline
            :py:meth:`nexxT.interface.PropertyCollections.PropertyHandler.setEditorData` \endverbatim
        */
        virtual void setEditorData(QWidget *editor, const QVariant &value);
        /*!
            See \verbatim embed:rst:inline
            :py:meth:`nexxT.interface.PropertyCollections.PropertyHandler.getEditorData` \endverbatim
        */
        virtual QVariant getEditorData(QWidget *editor);
    };

    /*!
        This class is the C++ variant of \verbatim embed:rst:inline
        :py:class:`nexxT.interface.PropertyCollections.PropertyCollection`
        \endverbatim
    */
    class DLLEXPORT PropertyCollection : public QObject
    {
        Q_OBJECT

    public:
        /*!
            Constructor
        */
        PropertyCollection();
        /*!
            Destructor
        */
        virtual ~PropertyCollection();

        /*!
            See \verbatim embed:rst:inline
            :py:meth:`nexxT.interface.PropertyCollections.PropertyCollection.defineProperty` \endverbatim

            Variant with no options and no handler.
        */
        virtual void defineProperty(const QString &name, const QVariant &defaultVal, const QString &helpstr);
        /*!
            See \verbatim embed:rst:inline
            :py:meth:`nexxT.interface.PropertyCollections.PropertyCollection.defineProperty` \endverbatim

            Variant with options. C++ example
            \verbatim embed:rst
                .. code-block:: c

                    defineProperty("intProp", 1, "a bound integer", {{"min", -4},{"max", 9}});
                    defineProperty("enumProp", "Hello", "an enum prop", {{"enum", QStringList{"Hello", "World"}}});
            \endverbatim
        */
        virtual void defineProperty(const QString &name, const QVariant &defaultVal, const QString &helpstr, const QVariantMap &options);
        /*!
            See \verbatim embed:rst:inline
            :py:meth:`nexxT.interface.PropertyCollections.PropertyCollection.defineProperty` \endverbatim

            Variant with a custom handler.
        */
        virtual void defineProperty(const QString &name, const QVariant &defaultVal, const QString &helpstr, const PropertyHandler *handler);
        /*!
            See \verbatim embed:rst:inline
            :py:meth:`nexxT.interface.PropertyCollections.PropertyCollection.getProperty` \endverbatim
        */
        virtual QVariant getProperty(const QString &name) const;

    public slots:
        /*!
            Called from the nexxT framework, not intended to be used publicly
        */
        virtual void setProperty(const QString &name, const QVariant &variant);

        /*!
            See \verbatim embed:rst:inline
            :py:meth:`nexxT.interface.PropertyCollections.PropertyCollection.evalpath` \endverbatim
        */
        virtual QString evalpath(const QString &path) const;

    signals:
        /*!
            See \verbatim embed:rst:inline
            :py:attr:`nexxT.interface.PropertyCollections.PropertyCollection.propertyChanged` \endverbatim
        */
        void propertyChanged(const PropertyCollection &sender, const QString &name);
    };
};

#endif
