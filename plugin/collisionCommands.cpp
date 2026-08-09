#include "collisionCommands.h"
#include <maya/MPxCommand.h>
#include <maya/MArgList.h>
#include <maya/MStatus.h>
#include <maya/MGlobal.h>

void* CreateCollisionCommand::creator()
{
    return new CreateCollisionCommand();
}

MStatus CreateCollisionCommand:doIt()
{
    const MStatus status = MGlobal::executeCommand("polySphere"); //Esto nos va a crear una esfera, es de prueba
    if(!status)
    {
        MGlobal::displayError("Collision Setup no se ha completado" + status.errorString());
    }
    
    return status;

}

void* DefineColliderCommand::creator()
{
    return new DefineColliderCommand();
}

MStatus DefineColliderCommand::doIt()
{
    const MStatus status = MGlobal::executeCommand("polySphere"); //Esto nos va a crear una esfera, es de prueba
    if(!status)
    {
        MGlobal::displayError("No se ha encontrado el objeto colisionador completado" + status.errorString());
    }
    
    return status;

}