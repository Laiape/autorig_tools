#include "collisionCommands.h"
#include <maya/MFnPlugin.h>
#include <maya/MGlobal.h>
#include <maya/MObject.h>


MStatus initializePlugin(MObject obj)
{

    const char* pluginVendor = ("Laia Peris");
    const char* pluginVersion = "0.1";
    const char* pluginApiVersion = "Any";
    

    /*ASI ES COMO SE DEBE DECLARAR UN PLUG-IN
    MFnPlugin(MObject& object, const char* vendor, const char* version, const char* apiVersion, MStatus* status); 
    Para ello se necesitan declarar los "atributos" previamente*/
    MFnPlugin fnPlugin(obj, pluginVendor, pluginVersion);
    MStatus status = fnPlugin.registerCommand(kPluginName);

    if(!status) {status.perror("registerCommand createCollision"); return status}
    return status;
    
}

MStatus uninitializePlugin(MObject obj)
{

    MFnPlugin fnPlugin(obj);
    MStatus status = fnPlugin.deregisterCommand(kPluginName);

    if(!status)
    {
        status.perror("El plugin no se ha podido desregistrar");
    }

    return status;

}