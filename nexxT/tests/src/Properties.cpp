#include "Properties.hpp"
#include "nexxT/Logger.hpp"
#include "nexxT/PropertyCollection.hpp"

using namespace nexxT;

PropertyReceiver::PropertyReceiver(BaseFilterEnvironment *env) :
    Filter(false, false, env)
    {}

PropertyReceiver::~PropertyReceiver()
{}

void PropertyReceiver::onInit()
{
    propertyCollection()->defineProperty("int", 1, "an integer property", {{"min", 0}, {"max", 10}});
    propertyCollection()->defineProperty("float", 10.0, "a float property", {{"min", -1.0}, {"max", 100.0}});
    propertyCollection()->defineProperty("str", "Hello", "a string property");
    propertyCollection()->defineProperty("bool", false, "a bool property");
    propertyCollection()->defineProperty("enum", "v1", "an enum property", {{"enum", QStringList{"v1", "v2", "v3"}}});

    if(!(bool)
    connect(propertyCollection(), SIGNAL(propertyChanged(nexxT::PropertyCollection *, const QString &)),
            this, SLOT(propertyChanged(nexxT::PropertyCollection *, const QString &)))
    )  {
        NEXXT_LOG_ERROR("connect failed!");
    } else {
    }
}

void PropertyReceiver::propertyChanged(nexxT::PropertyCollection *propcoll, const QString &name)
{
    QVariant v = propcoll->getProperty(name);
    NEXXT_LOG_INFO(QString("propertyChanged %1 is %2").arg(name, v.toString()));
}

void PropertyReceiver::onOpen()
{
}

void PropertyReceiver::onStart()
{
}

void PropertyReceiver::onStop()
{
}

void PropertyReceiver::onClose()
{
}

void PropertyReceiver::onDeinit()
{
    if( !disconnect(propertyCollection(), SIGNAL(propertyChanged(nexxT::PropertyCollection *, const QString &)),
            this, SLOT(propertyChanged(nexxT::PropertyCollection *, const QString &))) )
    {
        NEXXT_LOG_ERROR("disconnect failed!");
    }
}
