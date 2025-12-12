# fbx2usd

A Python command-line tool for converting FBX files to USD (Universal Scene Description) format, optimized for Apple's RealityKit framework. Supports both skeletal and non-skeletal models with animations.

## Features

- **Skeletal Animation Support**: Preserves complete skeletal hierarchies and bind poses
- **Non-Skeletal Animation Support**: Exports transform-based animations for models without skeletons
- **Multiple Animation Takes**: Concatenates into single timeline, or exports as separate files
- **Separate Animation Export**: Export each animation take as a separate USD file with RealityKit AnimationLibrary
- **Directory Structure**: Optional organized output with `Textures/` and `Animations/` subdirectories
- **RealityKit Compatible**: Creates animation libraries with clip definitions for both skeletal and non-skeletal models
- **PBR Materials**: Converts materials with support for:
  - Diffuse/Albedo textures
  - Normal maps
  - Roughness maps
  - Metallic maps
  - Emissive maps
  - Ambient Occlusion maps
- **MaterialX Support**: Optional MaterialX shader export for Reality Composer Pro ShaderGraph compatibility
- **Mesh Export**: Exports geometry with normals and multiple UV sets
- **Skinning Weights**: Preserves skinning data (up to 4 influences per vertex) for skeletal models
- **Static Model Support**: Exports models without animations as simple static geometry
- **Flexible Output**: Supports binary USDC and human-readable ascii USDA formats
- **Unit Conversion**: Handles unit conversion (defaults to centimeters with metersPerUnit = 0.01)

## Requirements

### Python Dependencies

- macOS 26 or higher
- Python 3.10 or higher
- Pixar USD library (`usd-core`)
- Autodesk FBX SDK Python bindings

### Installing Dependencies

**Install USD library** (via pip):
   ```bash
   pip install usd-core
   ```

**Install Autodesk FBX SDK** (manual installation required):

   The FBX SDK is not available via pip and must be downloaded from Autodesk:

   - Visit [Autodesk FBX SDK Download Page](https://www.autodesk.com/developer-network/platform-technologies/fbx-sdk-2020-2-1)
   - Download and install the FBX SDK (2020.3)
   - Download the FBX Python Bindings
   - Download the FBX Python SDK
   - Follow Autodesk's installation instructions for your operating system
   - Ensure the FBX Python bindings are in your Python path

   **Note**: You must agree to Autodesk's license terms to use the FBX SDK.

## Installation

### Option 1: Direct Usage

Simply download `fbx2usd` and run it directly:

```bash
python3 fbx2usd input.fbx output.usdc
```

### Option 2: Install as Package

Clone this repository and install using pip:

```bash
git clone https://github.com/yourusername/fbx2usd.git
cd fbx2usd
pip install -e .
```

This will make the `fbx2usd` command available system-wide:

```bash
fbx2usd input.fbx output.usdc
```

## Usage

### Basic Usage

Convert an FBX file to USD (concatenates all animations into single timeline):

```bash
python3 fbx2usd input.fbx output.usdc
```

### Separate Animation Export

Export each animation take as a separate USD file using the `-s` or `--separate-animations` flag:

```bash
python3 fbx2usd -s character.fbx output/Character.usda
```

This creates:
- `Character.usda` - **Main entry point** with model, skeleton/mesh, and AnimationLibrary
- `Character-Materials.usda` - Materials and shaders
- `Character-<animation>.usda` - Individual animation files (one per take)
- `README.md` - Usage instructions and Swift code example
- Texture files are automatically copied to the output directory

**In Reality Composer Pro**, add `Character.usda` to your project. All other files will be brought in automatically because they are referenced. `Character.usda` is the file you should drag into the scene.

The same output structure is used for both skeletal and non-skeletal models, making the workflow consistent regardless of animation type.

### Output Formats

The tool automatically determines the output format based on the file extension:

- `.usda` - ASCII USD format (human-readable)
- `.usdc` - Binary USD format

```bash
python3 fbx2usd model.fbx model.usda  # ASCII output
python3 fbx2usd model.fbx model.usdc  # Binary output
```

### Examples

Convert a character with animations (single file):
```bash
python3 fbx2usd character_with_anims.fbx character.usdc
```

Export separate animation files for RealityKit:
```bash
python3 fbx2usd -s character.fbx output/Character.usda
```

Convert to ASCII format for inspection:
```bash
python3 fbx2usd model.fbx model.usda
```

### MaterialX Export

Use the `-m` or `--materialx` flag to export materials using MaterialX shaders instead of UsdPreviewSurface. This creates materials that are editable in Reality Composer Pro's ShaderGraph editor:

```bash
python3 fbx2usd -m -s character.fbx output/Character.usda
```

MaterialX export uses RealityKit-specific shader nodes:
- `ND_realitykit_pbr_surfaceshader` - PBR surface shader
- `ND_RealityKitTexture2D_color3` - Color texture sampler
- `ND_RealityKitTexture2D_float` - Single-channel texture sampler
- `ND_normal_map_decode` - Normal map decoder

**Note**: MaterialX is primarily useful when you want to edit materials in Reality Composer Pro's visual ShaderGraph. For general use, the default UsdPreviewSurface materials are more widely compatible.

### Directory Structure Export

Use the `-d` or `--directory-structure` flag to create an organized directory hierarchy for output files:

```bash
python3 fbx2usd -d character.fbx output/Character.usda
```

This creates a root directory named after the output file, with textures organized in a `Textures/` subdirectory:

```
Character/
├── Character.usda
└── Textures/
    ├── diffuse.png
    └── normal.png
```

When combined with `-s` (separate animations), animations are also organized in an `Animations/` subdirectory:

```bash
python3 fbx2usd -s -d character.fbx output/Character.usda
```

Creates:
```
Character/
├── Character.usda               (main entry point with model and AnimationLibrary)
├── Character-Materials.usda     (materials and shaders)
├── Animations/
│   ├── Character-Walk.usda
│   └── Character-Run.usda
├── Textures/
│   ├── diffuse.png
│   └── normal.png
└── README.md
```

All USD references are automatically updated to point to the correct subdirectory locations.

## How It Works

The converter performs the following operations:

1. **Scene Loading**:
   - Loads the FBX file using the Autodesk FBX SDK
   - Converts to OpenGL coordinate system (Y-up)
2. **Model Type Detection**:
   - Automatically detects whether the model has a skeleton
   - Routes to appropriate export path (skeletal or non-skeletal)
3. **Skeleton Export** (for skeletal models):
   - Extracts skeletal hierarchy
   - Preserves bind transforms and rest poses
4. **Mesh Export**:
   - Exports geometry with proper vertex ordering
   - Includes normals and multiple UV sets
   - Preserves skinning weights and joint influences (skeletal models only)
5. **Material Conversion**:
   - Creates USD Preview Surface materials (default) or MaterialX shaders (`-m` flag)
   - Maps FBX material properties to PBR parameters
   - References texture files with proper paths
6. **Animation Export**:
   - Default mode: Concatenates all animation takes into a single timeline
   - Separate mode (`-s`): Creates individual files per animation with RealityKit AnimationLibrary
   - Skeletal models: Samples joint transformations
   - Non-skeletal models: Samples mesh transform operations (translate, rotate, scale)
   - Creates RealityKit animation library with clip definitions
7. **USD Writing**:
   - Outputs the complete scene in USD format

## Limitations

- No morph targets/blend shapes support currently
- Limited to 4 bone influences per vertex (skeletal models)
- Assumes Y-up coordinate system
- Material conversion is optimized for PBR workflows
- Texture paths are preserved as-is (not embedded)

## Technical Details

### Coordinate System

The converter transforms from FBX's coordinate system to OpenGL convention (Y-up, right-handed) for compatibility with USD and RealityKit.

### Unit Handling

By default, the converter sets `metersPerUnit = 0.01` (centimeters). The FBX scene's unit scale is applied to ensure correct sizing.

### Animation Sampling

Animations are sampled at the FBX file's frame rate (typically 30 FPS). All animation takes in the FBX file are concatenated sequentially into a single timeline, or exported as separate files with the `-s` flag.

### Model Types

The converter automatically detects and handles two types of models:

- **Skeletal models**: Models with a skeleton hierarchy. Animations are exported as `UsdSkel.Animation` with joint transforms.
- **Non-skeletal models**: Models without a skeleton. Animations are exported as time-sampled USD xform operations (`xformOp:translate`, `xformOp:orient`, `xformOp:scale`) on mesh transforms.

Both model types support:
- Multiple animation takes
- Concatenated or separate animation export
- RealityKit AnimationLibrary generation

## License

This project is licensed under the 0BSD License - see the [LICENSE](LICENSE) file for details.

## Dependencies and Licenses

- **Pixar USD**: Apache 2.0 License
- **Autodesk FBX SDK**: Proprietary license from Autodesk (users must agree to Autodesk's terms)

---

# usdinspect

A Python command-line tool for inspecting USD files (usda/usdc/usdz) and displaying RealityKit animation libraries, skeletal animations, and scene hierarchy information.

## Features

- **Stage Information**: Displays format, FPS, time range, up axis, and meters per unit
- **Prim Summary**: Counts meshes, materials, skeletons, and other prim types
- **Prim Hierarchy**: ASCII tree visualization of the scene graph
- **RealityKit Animation Libraries**: Lists animation names and source files
- **Skeletal Animations**: Shows duration, frame count, FPS, joint count, and animation channels
- **Reference Following**: Recursively inspects referenced USD files (enabled by default)
- **Markdown Output**: Formatted output with aligned tables
- **Marked 2 Integration**: Option to open output directly in Marked 2 for preview

## Usage

### Basic Usage

Inspect a USD file:

```bash
python3 usdinspect model.usda
```

### Options

```
usdinspect <input_file> [options]

Options:
  --no-recursive    Don't follow USD references (default: follows references)
  -v, --verbose     Show detailed information
  -m, --marked      Copy output to pasteboard and open in Marked 2
```

### Examples

Inspect a USD file with all referenced files:
```bash
python3 usdinspect Character.usdc
```

Inspect only the specified file (don't follow references):
```bash
python3 usdinspect Character.usda --no-recursive
```

Open the output in Marked 2 for preview:
```bash
python3 usdinspect Character.usdc -m
```

## Output Example

```markdown
# Character.usdc

## Stage Info

| Property        | Value         |
|-----------------|---------------|
| Format          | usdc (Binary) |
| FPS             | 24.0          |
| Time Range      | (not set)     |
| Up Axis         | Y             |
| Meters Per Unit | 1.0           |

## Prim Summary

| Type        | Count |
|-------------|-------|
| Total prims | 26    |
| Meshes      | 1     |
| Materials   | 1     |
| Skeletons   | 1     |

## Prim Hierarchy

Character (Xform)
├── Root (SkelRoot)
│   ├── Skeleton (Skeleton)
│   └── Geom (Scope)
│       └── Character (Mesh)
├── Materials (Scope)
│   └── Material (Material)
└── AnimationLibrary (RealityKitComponent)
    ├── Idle (RealityKitAnimationFile)
    └── Walk (RealityKitAnimationFile)

## RealityKit Animation Library

**Path:** `/Character/AnimationLibrary`

### Animations

| Name | File                  |
|------|-----------------------|
| Idle | `Character-Idle.usdc` |
| Walk | `Character-Walk.usdc` |

## Skeletal Animations

| Source                | Path                                 | Duration | Frames | FPS  | Joints | Channels                        |
|-----------------------|--------------------------------------|----------|--------|------|--------|---------------------------------|
| `Character-Idle.usdc` | `/Character/Root/Skeleton/Animation` | 1.77s    | 54     | 30.0 | 50     | translations, rotations, scales |
| `Character-Walk.usdc` | `/Character/Root/Skeleton/Animation` | 1.03s    | 32     | 30.0 | 50     | translations, rotations, scales |
```

## Requirements

- Python 3.10 or higher
- Pixar USD library (`usd-core`)

No FBX SDK required - this tool only reads USD files.

---

## Acknowledgments

- Built using Pixar's Universal Scene Description (USD)
- fbx2usd uses Autodesk's FBX SDK for FBX file parsing
