/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#ifndef NEXT_PROPERTY_COLLECTION_HPP
#define NEXT_PROPERTY_COLLECTION_HPP

#include <QtCore/QObject>
#include <QtCore/QVariant>
#include "NexTLinkage.hpp"
#include "NexTConfig.hpp"

START_NAMESPACE
    class DLLEXPORT PropertyCollection : public QObject
    {
        Q_OBJECT

    public:
        PropertyCollection();
        virtual ~PropertyCollection();

        virtual void defineProperty(const QString &name, const QVariant &defaultVal, const QString &helpstr);
        virtual QVariant getProperty(const QString &name) const;

    public slots:
        virtual void setProperty(const QString &name, const QVariant &variant);
        virtual QString evalpath(const QString &path) const;

    signals:
        void propertyChanged(const PropertyCollection &sender, const QString &name);
    };
STOP_NAMESPACE

#endif
