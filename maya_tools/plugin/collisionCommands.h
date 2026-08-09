#pragma once
#include <maya/MArgList.h>
#include <maya/MStatus.h>

class CreateCollisionCommand : public MPxCommand
{
public:
    static void* creator();
    MStatus doIt(const MArgList& args) override;
};

class DefineColliderCommand : public MPxCommand
{
public:
    static void* creator();
    MStatus doIt(const MArgList& args) override;
};
