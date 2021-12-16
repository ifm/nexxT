#include "Compatibility.hpp"

using namespace nexxT;

QMenu *Compatibility::getMenuFromAction(QAction *a)
{
    return a->menu();
}