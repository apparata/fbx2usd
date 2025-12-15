/**
 * fbxaxisconvert - Convert FBX axis system
 *
 * Takes an FBX file as input and converts it to the specified coordinate system
 * using DeepConvertScene (or ConvertScene with --shallow).
 *
 * Usage:
 *   fbxaxisconvert <input.fbx> <output.fbx> [--target <system>] [--shallow]
 *
 * Build:
 *   make
 */

#include "fbxsdk_fix.h"
#include <cstdio>
#include <cstring>

// Axis system definitions with descriptions
struct AxisSystemInfo {
    const char* name;
    const char* description;
    FbxAxisSystem axisSystem;
};

// Get axis directions based on the FBX SDK header comments:
// MayaZUp:      UpVector = +Z, FrontVector = -Y, CoordSystem = +X (RightHanded)
// MayaYUp:      UpVector = +Y, FrontVector = +Z, CoordSystem = +X (RightHanded)
// Max:          UpVector = +Z, FrontVector = -Y, CoordSystem = +X (RightHanded)
// Motionbuilder: UpVector = +Y, FrontVector = +Z, CoordSystem = +X (RightHanded)
// OpenGL:       UpVector = +Y, FrontVector = +Z, CoordSystem = +X (RightHanded)
// DirectX:      UpVector = +Y, FrontVector = +Z, CoordSystem = -X (LeftHanded)
// Lightwave:    UpVector = +Y, FrontVector = +Z, CoordSystem = -X (LeftHanded)
//
// The "CoordSystem" value IS the right vector direction.
void GetAxisDirections(const FbxAxisSystem& axisSystem, char* upStr, char* rightStr, char* forwardStr) {
    int upSign = 0;
    FbxAxisSystem::EUpVector upVector = axisSystem.GetUpVector(upSign);

    int frontSign = 0;
    FbxAxisSystem::EFrontVector frontVector = axisSystem.GetFrontVector(frontSign);

    FbxAxisSystem::ECoordSystem coordSystem = axisSystem.GetCoorSystem();

    // Determine up axis
    char upAxis = '?';
    switch (upVector) {
        case FbxAxisSystem::eXAxis: upAxis = 'x'; break;
        case FbxAxisSystem::eYAxis: upAxis = 'y'; break;
        case FbxAxisSystem::eZAxis: upAxis = 'z'; break;
    }

    // Determine front (forward) axis based on parity
    // From the SDK docs: if up=Y, ParityEven=Z, ParityOdd=X
    // But looking at the predefined systems:
    //   MayaYUp has FrontVector=ParityOdd and forward=+Z
    //   MayaZUp has FrontVector=-ParityOdd and forward=-Y
    // So for up=Y: ParityOdd gives Z axis, ParityEven gives X axis
    // For up=Z: ParityOdd gives Y axis, ParityEven gives X axis
    char frontAxis = '?';
    if (upVector == FbxAxisSystem::eXAxis) {
        frontAxis = (frontVector == FbxAxisSystem::eParityEven) ? 'y' : 'z';
    } else if (upVector == FbxAxisSystem::eYAxis) {
        // ParityOdd = Z, ParityEven = X (based on MayaYUp using ParityOdd for +Z)
        frontAxis = (frontVector == FbxAxisSystem::eParityOdd) ? 'z' : 'x';
    } else if (upVector == FbxAxisSystem::eZAxis) {
        // ParityOdd = Y, ParityEven = X (based on MayaZUp using -ParityOdd for -Y)
        frontAxis = (frontVector == FbxAxisSystem::eParityOdd) ? 'y' : 'x';
    }

    // Determine right axis (the remaining axis)
    char rightAxis = '?';
    if ((upAxis == 'x' || frontAxis == 'x') && (upAxis == 'y' || frontAxis == 'y')) {
        rightAxis = 'z';
    } else if ((upAxis == 'x' || frontAxis == 'x') && (upAxis == 'z' || frontAxis == 'z')) {
        rightAxis = 'y';
    } else {
        rightAxis = 'x';
    }

    // Determine right axis sign
    // From SDK comments, CoordSystem describes the right vector:
    // RightHanded = +X for MayaYUp/MayaZUp, LeftHanded = -X for DirectX/Lightwave
    int rightSign = (coordSystem == FbxAxisSystem::eRightHanded) ? 1 : -1;

    // FBX "FrontVector" points toward camera (out of screen)
    // "Forward" conventionally points into the screen, so we negate the sign
    int forwardSign = -frontSign;

    sprintf(upStr, "%c%c", upSign >= 0 ? '+' : '-', upAxis);
    sprintf(rightStr, "%c%c", rightSign >= 0 ? '+' : '-', rightAxis);
    sprintf(forwardStr, "%c%c", forwardSign >= 0 ? '+' : '-', frontAxis);
}

// Get a human-readable name for the axis system
const char* GetAxisSystemName(const FbxAxisSystem& axisSystem) {
    if (axisSystem == FbxAxisSystem::MayaZUp) return "MayaZUp";
    if (axisSystem == FbxAxisSystem::MayaYUp) return "MayaYUp";
    if (axisSystem == FbxAxisSystem::Max) return "Max";
    if (axisSystem == FbxAxisSystem::Motionbuilder) return "Motionbuilder";
    if (axisSystem == FbxAxisSystem::OpenGL) return "OpenGL";
    if (axisSystem == FbxAxisSystem::DirectX) return "DirectX";
    if (axisSystem == FbxAxisSystem::Lightwave) return "Lightwave";
    return "Custom";
}

// Get axis system description string
void GetAxisSystemDescription(const FbxAxisSystem& axisSystem, char* buffer, size_t bufferSize) {
    char up[4], right[4], forward[4];
    GetAxisDirections(axisSystem, up, right, forward);

    FbxAxisSystem::ECoordSystem coordSystem = axisSystem.GetCoorSystem();
    const char* handedness = (coordSystem == FbxAxisSystem::eRightHanded) ? "right-handed" : "left-handed";

    snprintf(buffer, bufferSize, "up: %s, right: %s, forward: %s, %s", up, right, forward, handedness);
}

// Print axis system details
void PrintAxisSystemDetails(const FbxAxisSystem& axisSystem) {
    char desc[128];
    GetAxisSystemDescription(axisSystem, desc, sizeof(desc));
    fprintf(stderr, "  (%s)\n", desc);
}

// Available target axis systems
static const AxisSystemInfo g_axisSystems[] = {
    { "realitykit",    "RealityKit",     FbxAxisSystem::MayaYUp },
    { "maya-y-up",     "Maya Y-Up",      FbxAxisSystem::MayaYUp },
    { "maya-z-up",     "Maya Z-Up",      FbxAxisSystem::MayaZUp },
    { "max",           "3ds Max",        FbxAxisSystem::Max },
    { "opengl",        "OpenGL",         FbxAxisSystem::OpenGL },
    { "directx",       "DirectX",        FbxAxisSystem::DirectX },
};
static const int g_axisSystemCount = sizeof(g_axisSystems) / sizeof(g_axisSystems[0]);

void PrintUsage(const char* programName) {
    fprintf(stderr, "Usage: %s <input.fbx> <output.fbx> [options]\n", programName);
    fprintf(stderr, "\n");
    fprintf(stderr, "Converts FBX axis system to specified coordinate system.\n");
    fprintf(stderr, "\n");
    fprintf(stderr, "Options:\n");
    fprintf(stderr, "  -t, --target <system>  Target coordinate system (default: maya-y-up)\n");
    fprintf(stderr, "  --shallow              Use ConvertScene instead of DeepConvertScene\n");
    fprintf(stderr, "  -h, --help             Show this help message\n");
    fprintf(stderr, "\n");
    fprintf(stderr, "Target coordinate systems:\n");

    for (int i = 0; i < g_axisSystemCount; i++) {
        char desc[128];
        GetAxisSystemDescription(g_axisSystems[i].axisSystem, desc, sizeof(desc));
        fprintf(stderr, "  %-14s %s\n", g_axisSystems[i].name, g_axisSystems[i].description);
        fprintf(stderr, "                 (%s)\n", desc);
    }

    fprintf(stderr, "\n");
    fprintf(stderr, "DeepConvertScene (default) converts the scene and all animations.\n");
    fprintf(stderr, "ConvertScene (--shallow) only converts node transforms.\n");
}

const FbxAxisSystem* FindAxisSystem(const char* name) {
    for (int i = 0; i < g_axisSystemCount; i++) {
        if (strcmp(name, g_axisSystems[i].name) == 0) {
            return &g_axisSystems[i].axisSystem;
        }
    }
    return nullptr;
}

int main(int argc, char** argv) {
    // Parse arguments
    const char* inputPath = nullptr;
    const char* outputPath = nullptr;
    const char* targetName = "maya-y-up";
    bool useShallow = false;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--shallow") == 0) {
            useShallow = true;
        } else if (strcmp(argv[i], "-t") == 0 || strcmp(argv[i], "--target") == 0) {
            if (i + 1 < argc) {
                targetName = argv[++i];
            } else {
                fprintf(stderr, "Error: --target requires an argument\n");
                return 1;
            }
        } else if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) {
            PrintUsage(argv[0]);
            return 0;
        } else if (argv[i][0] == '-') {
            fprintf(stderr, "Error: Unknown option: %s\n", argv[i]);
            PrintUsage(argv[0]);
            return 1;
        } else if (!inputPath) {
            inputPath = argv[i];
        } else if (!outputPath) {
            outputPath = argv[i];
        }
    }

    if (!inputPath || !outputPath) {
        PrintUsage(argv[0]);
        return 1;
    }

    // Find target axis system
    const FbxAxisSystem* targetAxisSystem = FindAxisSystem(targetName);
    if (!targetAxisSystem) {
        fprintf(stderr, "Error: Unknown target coordinate system: %s\n", targetName);
        fprintf(stderr, "Use --help to see available systems.\n");
        return 1;
    }

    // Initialize the FBX SDK
    FbxManager* manager = FbxManager::Create();
    if (!manager) {
        fprintf(stderr, "Error: Failed to create FBX Manager\n");
        return 1;
    }

    // Create IO settings
    FbxIOSettings* ios = FbxIOSettings::Create(manager, IOSROOT);
    manager->SetIOSettings(ios);

    // Create importer
    FbxImporter* importer = FbxImporter::Create(manager, "");

    fprintf(stderr, "Loading: %s\n", inputPath);

    if (!importer->Initialize(inputPath, -1, manager->GetIOSettings())) {
        fprintf(stderr, "Error: Failed to initialize importer: %s\n",
                importer->GetStatus().GetErrorString());
        manager->Destroy();
        return 1;
    }

    // Create scene and import
    FbxScene* scene = FbxScene::Create(manager, "");

    if (!importer->Import(scene)) {
        fprintf(stderr, "Error: Failed to import scene: %s\n",
                importer->GetStatus().GetErrorString());
        importer->Destroy();
        manager->Destroy();
        return 1;
    }

    importer->Destroy();

    // Get current axis system
    FbxAxisSystem currentAxisSystem = scene->GetGlobalSettings().GetAxisSystem();

    fprintf(stderr, "Current axis system: %s\n", GetAxisSystemName(currentAxisSystem));
    PrintAxisSystemDetails(currentAxisSystem);

    // Check if conversion is needed
    if (currentAxisSystem == *targetAxisSystem) {
        fprintf(stderr, "Axis system is already %s, no conversion needed.\n", targetName);
    } else {
        fprintf(stderr, "Target axis system: %s\n", GetAxisSystemName(*targetAxisSystem));
        PrintAxisSystemDetails(*targetAxisSystem);

        if (useShallow) {
            fprintf(stderr, "Converting with ConvertScene (shallow)...\n");
            targetAxisSystem->ConvertScene(scene);
        } else {
            fprintf(stderr, "Converting with DeepConvertScene...\n");
            targetAxisSystem->DeepConvertScene(scene);
        }

        // Verify conversion
        FbxAxisSystem newAxisSystem = scene->GetGlobalSettings().GetAxisSystem();
        fprintf(stderr, "New axis system: %s\n", GetAxisSystemName(newAxisSystem));
        PrintAxisSystemDetails(newAxisSystem);
    }

    // Create exporter
    FbxExporter* exporter = FbxExporter::Create(manager, "");

    // Find binary FBX format
    int fileFormat = -1;
    int formatCount = manager->GetIOPluginRegistry()->GetWriterFormatCount();

    for (int i = 0; i < formatCount; i++) {
        if (manager->GetIOPluginRegistry()->WriterIsFBX(i)) {
            FbxString desc = manager->GetIOPluginRegistry()->GetWriterFormatDescription(i);
            if (desc.Find("binary") >= 0) {
                fileFormat = i;
                break;
            }
        }
    }

    if (fileFormat < 0) {
        fileFormat = manager->GetIOPluginRegistry()->GetNativeWriterFormat();
    }

    fprintf(stderr, "Saving: %s\n", outputPath);

    if (!exporter->Initialize(outputPath, fileFormat, manager->GetIOSettings())) {
        fprintf(stderr, "Error: Failed to initialize exporter: %s\n",
                exporter->GetStatus().GetErrorString());
        exporter->Destroy();
        manager->Destroy();
        return 1;
    }

    if (!exporter->Export(scene)) {
        fprintf(stderr, "Error: Failed to export scene: %s\n",
                exporter->GetStatus().GetErrorString());
        exporter->Destroy();
        manager->Destroy();
        return 1;
    }

    exporter->Destroy();
    manager->Destroy();

    fprintf(stderr, "Done!\n");
    return 0;
}
