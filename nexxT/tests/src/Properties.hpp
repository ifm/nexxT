#ifndef PROPERTY_RECEIVER_HPP
#define PROPERTY_RECEIVER_HPP

#include "nexxT/Filters.hpp"
#include "nexxT/NexxTPlugins.hpp"

class PropertyReceiver : public nexxT::Filter
{
    Q_OBJECT
public:
    NEXXT_PLUGIN_DECLARE_FILTER(PropertyReceiver)

    PropertyReceiver(nexxT::BaseFilterEnvironment *env);
    virtual ~PropertyReceiver();

    virtual void onInit();
    virtual void onOpen();
    virtual void onStart();
    virtual void onStop();
    virtual void onClose();
    virtual void onDeinit();

public slots:
    void propertyChanged(nexxT::PropertyCollection *sender, const QString &name);
};

#endif
