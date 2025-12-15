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
- **Bounding Box**: Computes axis-aligned bounding box for the entire scene
- **Prim Hierarchy**: ASCII tree visualization of the scene graph
- **Skeleton Hierarchy**: Displays bone/joint hierarchy for skeletal models
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

## Skeleton Hierarchy (50 joints)

**Path:** `/Character/Root/Skeleton`

Hips
├── Spine
│   ├── Spine1
│   │   └── Spine2
│   │       ├── Neck
│   │       │   └── Head
│   │       ├── LeftShoulder
│   │       │   └── LeftArm
│   │       │       └── LeftForeArm
│   │       │           └── LeftHand
│   │       └── RightShoulder
│   │           └── RightArm
│   │               └── RightForeArm
│   │                   └── RightHand
├── LeftUpLeg
│   └── LeftLeg
│       └── LeftFoot
│           └── LeftToeBase
└── RightUpLeg
    └── RightLeg
        └── RightFoot
            └── RightToeBase

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

# fbxinspect

A Python command-line tool for inspecting FBX files and displaying scene hierarchy, skeleton structure, animation takes, mesh information, and materials in Markdown format.

## Features

- **Scene Information**: Displays FPS, up axis, coordinate system, and unit scale
- **Node Summary**: Counts meshes, skeleton bones, materials, and textures
- **Bounding Box**: Computes axis-aligned bounding box for the entire scene
- **Node Hierarchy**: ASCII tree visualization of the scene graph with node types
- **Skeleton Hierarchy**: Displays bone/joint hierarchy for skeletal models
- **Mesh Details**: Shows vertex count, polygon count, UV sets, skinning, and blend shapes
- **Animation Takes**: Lists all animation stacks with duration, frame count, and FPS
- **Material Info**: Shows shading models and texture assignments (verbose mode)
- **Markdown Output**: Formatted output with aligned tables
- **Marked 2 Integration**: Option to open output directly in Marked 2 for preview

## Requirements

- Python 3.x
- Autodesk FBX SDK Python bindings

## Usage

### Basic Usage

Inspect an FBX file:

```bash
python3 fbxinspect model.fbx
```

### Options

```
fbxinspect <input_file> [options]

Options:
  -v, --verbose     Show detailed information (materials, etc.)
  -m, --marked      Copy output to pasteboard and open in Marked 2
```

### Examples

Inspect an FBX file:
```bash
python3 fbxinspect Character.fbx
```

Show verbose output with material details:
```bash
python3 fbxinspect Character.fbx -v
```

Open the output in Marked 2 for preview:
```bash
python3 fbxinspect Character.fbx -m
```

## Output Example

```markdown
# Character.fbx

## Scene Info

| Property          | Value               |
|-------------------|---------------------|
| FPS               | 30.0                |
| Up Axis           | Y                   |
| Coordinate System | Right-Handed        |
| Unit Scale        | 1.0 (cm)            |

## Node Summary

| Type           | Count |
|----------------|-------|
| Total nodes    | 55    |
| Meshes         | 1     |
| Skeleton bones | 50    |
| Materials      | 2     |
| Textures       | 4     |

## Node Hierarchy

Armature (Null)
└── Hips (Skeleton)
    ├── Spine (Skeleton)
    │   └── ...
    └── ...
Character_Mesh (Mesh)

## Skeleton Hierarchy (50 joints)

**Root:** `Hips`

Hips
├── Spine
│   └── Spine1
│       └── Spine2
│           ├── Neck
│           │   └── Head
│           ├── LeftShoulder
│           │   └── LeftArm
│           └── RightShoulder
│               └── RightArm
├── LeftUpLeg
│   └── LeftLeg
└── RightUpLeg
    └── RightLeg

## Meshes

| Name           | Vertices | Polygons | UV Sets | Skinned | Blend Shapes |
|----------------|----------|----------|---------|---------|--------------|
| Character_Mesh | 5432     | 10234    | 1       | Yes     | -            |

## Animation Takes

| Name  | Duration | Frames | FPS  | Layers |
|-------|----------|--------|------|--------|
| Idle  | 2.00s    | 60     | 30.0 | 1      |
| Walk  | 1.00s    | 30     | 30.0 | 1      |
| Run   | 0.67s    | 20     | 30.0 | 1      |
```

---

# fbxunit

A Python command-line tool for converting an FBX file from one unit system to another, with options to scale geometry or only change metadata.

## Purpose

Convert FBX files between different unit systems (e.g., centimeters to meters). By default, the tool uses the FBX SDK's built-in unit conversion which properly scales:
- Vertex positions
- Node transforms (translations)
- Animation curves (translation keyframes)
- Camera and light properties
- Other distance-based properties

Alternatively, use `--no-scale` to only change the unit metadata without modifying any geometry values.

## Requirements

- Python 3.x
- Autodesk FBX SDK Python bindings

## Usage

```bash
python3 fbxunit <input.fbx> <output.fbx> <unit> [--no-scale]
```

### Supported Units

| Unit | Aliases |
|------|---------|
| Meters | m, meters |
| Centimeters | cm, centimeters |
| Millimeters | mm, millimeters |
| Inches | in, inches |
| Feet | ft, feet |

### Options

| Option | Description |
|--------|-------------|
| `--no-scale` | Only change unit metadata without scaling geometry |

### Examples

Convert from centimeters to meters (scales geometry):
```bash
python3 fbxunit model.fbx model_meters.fbx m
```

Change unit metadata only (no scaling):
```bash
python3 fbxunit model.fbx model_meters.fbx m --no-scale
```

### Output

With scaling (default):
```
Loading: model.fbx
Current unit: cm (scale factor: 1.0)
Target unit: meters
Converting scene...
Conversion factor: 0.01
New unit: m (scale factor: 100.0)
Saving: model_meters.fbx
Done!
```

With `--no-scale`:
```
Loading: model.fbx
Current unit: cm (scale factor: 1.0)
Target unit: meters
Converting scene...
Changing unit metadata only (no geometry scaling)
New unit: m (scale factor: 100.0)
Saving: model_meters.fbx
Done!
```

## When to Use Each Mode

- **Default (with scaling)**: Use when you want to convert the actual size of the model. For example, a 180cm character becomes 1.8m.
- **`--no-scale`**: Use when the geometry values are already correct but the unit metadata is wrong. For example, a model authored in meters but incorrectly tagged as centimeters.

---

# fbxscale

A Python command-line tool for scaling FBX geometry without changing the unit metadata. Useful for fixing models that are the wrong size but have the correct unit setting.

## Purpose

Scale all geometry, transforms, and animations in an FBX file by a given factor while preserving the original unit metadata. This is the opposite of `fbxunit --no-scale` - it changes the geometry but keeps the unit.

## Requirements

- Python 3.x
- Autodesk FBX SDK Python bindings

## Usage

```bash
python3 fbxscale <input.fbx> <output.fbx> <scale_factor>
```

### Common Scale Factors

| Factor | Effect |
|--------|--------|
| 0.01 | Make 100x smaller |
| 0.1 | Make 10x smaller |
| 10 | Make 10x larger |
| 100 | Make 100x larger |

### Examples

Fix a model that's 100x too large:
```bash
python3 fbxscale model.fbx model_fixed.fbx 0.01
```

Make a model 10x larger:
```bash
python3 fbxscale tiny_model.fbx bigger_model.fbx 10
```

### Output

```
Loading: model.fbx
Unit: cm (scale factor: 1.0)
Scaling by factor: 0.01
Scaling scene...
Unit after scaling: cm (scale factor: 1.0)
Saving: model_fixed.fbx
Done!
```

## How It Works

The tool uses a clever trick with the FBX SDK:
1. Temporarily converts to a different unit scale (which scales all geometry)
2. Restores the original unit metadata without scaling

This achieves the effect of scaling geometry while preserving the unit setting.

## When to Use

Use `fbxscale` when:
- A model has the correct unit (e.g., meters) but is 100x too large
- You need to resize a model without changing its unit metadata
- You're preparing models from different sources to be the same scale

---

# append-fbx-skeletal-animation

A Python command-line tool for merging animation takes from one FBX file into another. Useful for combining animations from different sources (e.g., Mixamo) into a single FBX file before converting to USD.

## Features

- **Animation Merging**: Copies animation stacks (takes) from a source FBX into a destination FBX
- **Skeleton Matching**: Automatically maps bones between files with identical or similar skeleton hierarchies
- **Coordinate System Handling**: Detects and compensates for Z-up vs Y-up differences between files
- **Scale Adjustment**: Optional scale factor for animations (useful when source animations are in different units)
- **Auto-Scale Detection**: Can automatically calculate scale factor based on skeleton size differences
- **PreRotation Baking**: Handles bone PreRotation differences by baking them into animation curves
- **Duplicate Handling**: Automatically renames animation stacks to avoid name conflicts

## Requirements

- Python 3.x
- Autodesk FBX SDK Python bindings

## Usage

### Basic Usage

Merge animations from one FBX file into another:

```bash
python3 append-fbx-skeletal-animation model.fbx animations.fbx output.fbx
```

### With Scale Factor

If the animation source uses different units (e.g., Mixamo animations are often 100x larger):

```bash
python3 append-fbx-skeletal-animation model.fbx mixamo_anims.fbx output.fbx --scale 0.01
```

### Auto-Scale Detection

Let the tool automatically detect the scale difference based on skeleton size:

```bash
python3 append-fbx-skeletal-animation model.fbx animations.fbx output.fbx --scale auto
```

### Options

```
append-fbx-skeletal-animation <model.fbx> <animations.fbx> <output.fbx> [options]

Arguments:
  model.fbx       FBX file with rigged model and base animations
  animations.fbx  FBX file with additional animations to merge
  output.fbx      Output FBX file path

Options:
  --scale FACTOR  Scale factor for animation translations (default: 1.0)
                  Use "auto" to auto-detect from skeleton size
                  Use 0.01 if animations are 100x too big
                  Use 100 if animations are 100x too small
```

## Workflow Example

Combining a character model with Mixamo animations:

1. Export your rigged character from Blender/Maya as `character.fbx`
2. Download animations from Mixamo for the same skeleton
3. Merge the animations:
   ```bash
   python3 append-fbx-skeletal-animation character.fbx mixamo_walk.fbx character_with_walk.fbx --scale 0.01
   python3 append-fbx-skeletal-animation character_with_walk.fbx mixamo_run.fbx character_final.fbx --scale 0.01
   ```
4. Convert to USD:
   ```bash
   python3 fbx2usd -s character_final.fbx output/Character.usda
   ```

## How It Works

1. Loads both FBX files using the Autodesk FBX SDK
2. Analyzes skeleton hierarchies to build bone name mappings
3. Detects coordinate system differences (Z-up vs Y-up) and calculates rotation offsets
4. For each animation stack in the source file:
   - Creates a new animation stack in the destination
   - Copies all animation layers with their properties
   - Transfers keyframe data for translation, rotation, and scale
   - Applies coordinate system transformations and scale adjustments
   - Bakes PreRotation differences into animation curves
5. Saves the merged result to a new FBX file

## Notes

- Both FBX files should have compatible skeleton hierarchies (same bone names)
- The tool preserves cubic interpolation and tangent data when copying keyframes
- Animation stacks with duplicate names are automatically renamed with a numeric suffix

---

# retarget-mixamo

A Python command-line tool for retargeting Mixamo animations onto custom rigs. Transfers animation data from Mixamo-style skeletons to your own character rig using bone mapping.

## Features

- **Local Rotation Delta Method**: Works even when source and target skeletons have different global orientations at rest (e.g., different T-pose arm angles)
- **Bone Mapping**: Uses a JSON or text mapping file to match source bones to target bones
- **Root Motion Support**: Derives root motion from Mixamo Hips when target has a Root bone that Mixamo lacks
- **Axis/Unit Conversion**: Automatically converts source axis system and units to match target
- **Scale Compensation**: Computes scale from hip heights to handle skeletons with different world scales
- **Flexible Input**: Supports JSON mapping files or simple text files with `->`, `→`, or `=` syntax

## Requirements

- Python 3.x
- Autodesk FBX SDK Python bindings

## Usage

```bash
python3 retarget-mixamo --source <animation.fbx> --source-tpose <source_tpose.fbx> \
                        --target-tpose <target_tpose.fbx> --map <mapping.json> --out <output.fbx>
```

### Required Arguments

| Argument | Description |
|----------|-------------|
| `--source` | Mixamo animation FBX (source animation to retarget) |
| `--source-tpose` | Mixamo T-pose FBX (source skeleton reference pose) |
| `--target-tpose` | Custom rig T-pose FBX (target skeleton reference pose) |
| `--map` | Bone mapping file (JSON or text format) |
| `--out` | Output FBX path (target with retargeted animation) |

### Optional Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--fps` | 30 | Sampling FPS for baking animation |
| `--rest-frame` | 0 | Frame index used as rest reference |
| `--root-name` | Root | Target root bone name |
| `--hips-name` | Hips | Target hips bone name |
| `--source-hips-name` | mixamorig:Hips | Source hips bone name |
| `--take` | (first) | Source AnimStack name to use |
| `--out-take` | Retargeted | Name of new AnimStack in output |
| `--no-convert-space` | | Don't convert source axis/unit to match target |
| `--root-motion-axes` | XZ | Axes of target Root translation to drive from source hips |
| `--hips-translation-axes` | Y | Axes of target Hips translation to keep |
| `-v, --verbose` | | Verbose logging |
| `--list-bones` | | List all skeleton bones in source and target, then exit |
| `--debug-frame` | | Dump detailed debug info for a specific frame |

### Mapping File Format

**JSON format:**
```json
{
  "mixamorig:Hips": "Hips",
  "mixamorig:Spine": "Spine",
  "mixamorig:Spine1": "Spine1",
  "mixamorig:LeftArm": "LeftArm"
}
```

**Text format** (using `->`, `→`, or `=`):
```
mixamorig:Hips -> Hips
mixamorig:Spine -> Spine
mixamorig:LeftArm = LeftArm
```

### Examples

Basic retargeting:
```bash
python3 retarget-mixamo \
  --source mixamo_walk.fbx \
  --source-tpose mixamo_tpose.fbx \
  --target-tpose mycharacter_tpose.fbx \
  --map bone_mapping.json \
  --out mycharacter_walk.fbx
```

List bones to help create mapping file:
```bash
python3 retarget-mixamo \
  --source mixamo_walk.fbx \
  --source-tpose mixamo_tpose.fbx \
  --target-tpose mycharacter_tpose.fbx \
  --map empty.json \
  --out /dev/null \
  --list-bones
```

Retarget with custom root motion settings:
```bash
python3 retarget-mixamo \
  --source mixamo_run.fbx \
  --source-tpose mixamo_tpose.fbx \
  --target-tpose mycharacter_tpose.fbx \
  --map bone_mapping.json \
  --out mycharacter_run.fbx \
  --root-motion-axes ""
```

## How It Works

1. **Load Scenes**: Loads source animation, source T-pose, and target T-pose FBX files
2. **Build Bone Mapping**: Parses the mapping file to create source→target bone correspondence
3. **Compute Rest Poses**: Extracts local rest rotations for all mapped bones in both skeletons
4. **Calculate Scale**: Determines scale factor from hip height difference between skeletons
5. **For Each Frame**:
   - Computes local rotation delta: `Qdelta = Q_source_local * inverse(Q_source_rest)`
   - Applies delta to target rest pose: `Q_target = Qdelta * Q_target_rest`
   - Handles root motion by extracting XZ movement from source hips
6. **Write Animation**: Creates new AnimStack with baked rotation/translation curves

## Notes

- Works best when both skeletons are in similar T-poses
- Skips missing bone pairs with warnings
- Handles PreRotation/PostRotation by working in matrices and decomposing at the end
- Root motion is derived from Mixamo Hips movement when target has a Root bone

---

## Acknowledgments

- Built using Pixar's Universal Scene Description (USD)
- fbx2usd uses Autodesk's FBX SDK for FBX file parsing
