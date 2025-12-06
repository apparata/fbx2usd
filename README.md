# fbx2usd

A Python command-line tool for converting FBX files with skeletal animations to USD (Universal Scene Description) format, optimized for Apple's RealityKit framework.

## Features

- **Skeletal Animation Support**: Preserves complete skeletal hierarchies and bind poses
- **Multiple Animation Takes**: Concatenates multiple animation takes into a single timeline
- **RealityKit Compatible**: Creates animation libraries with clip definitions
- **PBR Materials**: Converts materials with support for:
  - Diffuse/Albedo textures
  - Normal maps
  - Roughness maps
  - Metallic maps
  - Emissive maps
  - Ambient Occlusion maps
- **Mesh Export**: Exports geometry with normals and multiple UV sets
- **Skinning Weights**: Preserves skinning data (up to 4 influences per vertex)
- **Flexible Output**: Supports USD, USDA (ASCII), and USDC (compressed) formats
- **Unit Conversion**: Handles unit conversion (defaults to centimeters with metersPerUnit = 0.01)

## Requirements

### Python Dependencies

- macOS 26 or higher
- Python 3.10 or higher
- Pixar USD library (`usd-core`)
- Autodesk FBX SDK Python bindings

### Installing Dependencies

1. **Install USD library** (via pip):
   ```bash
   pip install usd-core
   ```

2. **Install Autodesk FBX SDK** (manual installation required):

   The FBX SDK is not available via pip and must be downloaded from Autodesk:

   - Visit [Autodesk FBX SDK Download Page](https://www.autodesk.com/developer-network/platform-technologies/fbx-sdk-2020-2-1)
   - Download the FBX Python SDK for your platform (Windows, macOS, or Linux)
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

Convert an FBX file to USD:

```bash
python3 fbx2usd input.fbx output.usdc
```

### Output Formats

The tool automatically determines the output format based on the file extension:

- `.usda` - ASCII USD format (human-readable)
- `.usdc` - Binary USD format

```bash
python3 fbx2usd model.fbx model.usda  # ASCII output
python3 fbx2usd model.fbx model.usdc  # Compressed output
```

### Examples

Convert a character with animations:
```bash
python3 fbx2usd character_with_anims.fbx character.usdc
```

Convert to ASCII format for inspection:
```bash
python3 fbx2usd model.fbx model.usda
```

## How It Works

The converter performs the following operations:

1. **Scene Loading**:
   - Loads the FBX file using the Autodesk FBX SDK
2. **Skeleton Export**:
   - Extracts skeletal hierarchy
   - Preserves bind transforms and rest poses
   - Converts to OpenGL coordinate system
3. **Mesh Export**:
   - Exports geometry with proper vertex ordering
   - Includes normals and multiple UV sets
   - Preserves skinning weights and joint influences
4. **Material Conversion**:
   - Creates USD Preview Surface materials
   - Maps FBX material properties to PBR parameters
   - References texture files with proper paths
5. **Animation Export**:
   - Concatenates all animation takes into a single timeline
   - Samples skeletal transformations at 30 FPS
   - Creates RealityKit animation library with clip definitions
6. **USD Writing**:
   - Outputs the complete scene in USD format

## Limitations

- Supports skeletal animation only (no morph targets/blend shapes currently)
- Limited to 4 bone influences per vertex
- Assumes Y-up coordinate system
- Material conversion is optimized for PBR workflows
- Texture paths are preserved as-is (not embedded)

## Technical Details

### Coordinate System

The converter transforms from FBX's coordinate system to OpenGL convention (Y-up, right-handed) for compatibility with USD and RealityKit.

### Unit Handling

By default, the converter sets `metersPerUnit = 0.01` (centimeters). The FBX scene's unit scale is applied to ensure correct sizing.

### Animation Sampling

Animations are sampled at 30 FPS by default. All animation takes in the FBX file are concatenated sequentially into a single timeline.

## License

This project is licensed under the 0BSD License - see the [LICENSE](LICENSE) file for details.

## Dependencies and Licenses

- **Pixar USD**: Apache 2.0 License
- **Autodesk FBX SDK**: Proprietary license from Autodesk (users must agree to Autodesk's terms)

## Acknowledgments

- Built using Pixar's Universal Scene Description (USD)
- Uses Autodesk's FBX SDK for FBX file parsing
