/* 
 * SPDX-License-Identifier: Apache-2.0
 * Copyright (C) 2020 ifm electronic gmbh
 *
 * THE PROGRAM IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
 */

#include "PropertyCollection.hpp"

#include <cstdio>

using namespace nexxT;

PropertyHandler::PropertyHandler()
{
}

PropertyHandler::~PropertyHandler()
{
}

QVariantMap PropertyHandler::options()
{
    throw std::runtime_error("not implemented.");
}

QVariant PropertyHandler::fromConfig(const QVariant &value)
{
    throw std::runtime_error("not implemented.");
}

QVariant PropertyHandler::toConfig(const QVariant &value)
{
    throw std::runtime_error("not implemented.");
}

QVariant PropertyHandler::toViewValue(const QVariant &value)
{
    throw std::runtime_error("not implemented.");
}

QWidget *PropertyHandler::createEditor(QWidget *parent)
{
    throw std::runtime_error("not implemented.");
}

void PropertyHandler::setEditorData(QWidget *editor, const QVariant &value)
{
    throw std::runtime_error("not implemented.");
}

QVariant PropertyHandler::getEditorData(QWidget *editor)
{
    throw std::runtime_error("not implemented.");
}


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

void PropertyCollection::defineProperty(const QString &name, const QVariant &defaultVal, const QString &helpstr, const QVariantMap &options)
{
    throw std::runtime_error("not implemented.");
}

void PropertyCollection::defineProperty(const QString &name, const QVariant &defaultVal, const QString &helpstr, const PropertyHandler *handler)
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

