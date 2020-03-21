/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "PropertyCollection.hpp"

#include <cstdio>

USE_NAMESPACE

PropertyCollection::PropertyCollection()
{
}

PropertyCollection::~PropertyCollection()
{
}

void PropertyCollection::defineProperty(const QString &name, const QVariant &defaultVal, const QString &helpstr)
{
    throw std::runtime_error("not implemented.");
}

QVariant PropertyCollection::getProperty(const QString &name) const
{
    throw std::runtime_error("not implemented.");
}

void PropertyCollection::setProperty(const QString &name, const QVariant &variant)
{
    throw std::runtime_error("not implemented.");
}

QString PropertyCollection::evalpath(const QString &path) const
{
    throw std::runtime_error("not implemented.");
}

