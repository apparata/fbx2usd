#!/usr/bin/env python3
"""
FBX to USD converter matching the exact structure of working BusinessMan.usda
- Animation prim is a CHILD of Skeleton prim
- Uses metersPerUnit = 0.01
- Has defaultPrim set
- Bind transforms != Rest transforms
"""

import sys
import os
import argparse
import shutil
from fbx import *
from pxr import Usd, UsdGeom, UsdSkel, UsdShade, Sdf, Gf


def make_valid_identifier(name):
    """Convert to valid USD name"""
    name = name.split(":")[-1].replace(" ", "_")
    valid = ""
    for c in name:
        if c.isalnum() or c == '_':
            valid += c
        else:
            valid += '_'
    if valid and valid[0].isdigit():
        valid = '_' + valid
    return valid if valid else "prim"


def collect_texture_paths(mesh_nodes):
    """Collect all texture file paths from materials in the mesh nodes"""
    texture_paths = set()

    for mesh_node in mesh_nodes:
        fbx_mesh = mesh_node.GetMesh()
        material_elem = fbx_mesh.GetElementMaterial()
        if material_elem and mesh_node.GetMaterialCount() > 0:
            fbx_material = mesh_node.GetMaterial(0)
            if fbx_material:
                # Check all texture properties
                texture_props = [
                    FbxSurfaceMaterial.sDiffuse,
                    FbxSurfaceMaterial.sNormalMap,
                    FbxSurfaceMaterial.sBump,
                    "ShininessExponent",
                    "Roughness",
                    "Metallic",
                ]

                for prop_name in texture_props:
                    prop = fbx_material.FindProperty(prop_name)
                    if prop.IsValid():
                        texture_count = prop.GetSrcObjectCount()
                        if texture_count > 0:
                            fbx_texture = prop.GetSrcObject(0)
                            if isinstance(fbx_texture, FbxFileTexture):
                                texture_path = fbx_texture.GetFileName()
                                if texture_path and os.path.exists(texture_path):
                                    texture_paths.add(texture_path)

    return texture_paths


def copy_textures_to_output(texture_paths, output_dir):
    """Copy texture files to the output directory"""
    copied = []
    for texture_path in texture_paths:
        texture_name = os.path.basename(texture_path)
        dest_path = os.path.join(output_dir, texture_name)

        # Don't copy if source and dest are the same
        if os.path.abspath(texture_path) == os.path.abspath(dest_path):
            continue

        try:
            shutil.copy2(texture_path, dest_path)
            copied.append(texture_name)
        except Exception as e:
            print(f"Warning: Could not copy texture {texture_name}: {e}")

    return copied


def gf_matrix_from_fbx(m):
    """Convert FbxAMatrix to Gf.Matrix4d"""
    return Gf.Matrix4d(
        m[0][0], m[0][1], m[0][2], m[0][3],
        m[1][0], m[1][1], m[1][2], m[1][3],
        m[2][0], m[2][1], m[2][2], m[2][3],
        m[3][0], m[3][1], m[3][2], m[3][3]
    )


def create_materialx_material(stage, mat_path, fbx_material, textures_subdir=None):
    """Create a MaterialX material for a single FBX material.
    If textures_subdir is provided, texture references will be prefixed with that subdirectory."""
    usd_material = UsdShade.Material.Define(stage, mat_path)

    # Create PBR surface shader
    pbr_path = f"{mat_path}/PBRSurface"
    pbr_shader = UsdShade.Shader.Define(stage, pbr_path)
    pbr_shader.CreateIdAttr("ND_realitykit_pbr_surfaceshader")

    # Create outputs
    pbr_output = pbr_shader.CreateOutput("out", Sdf.ValueTypeNames.Token)

    # Connect material to PBR shader
    mtlx_output = usd_material.CreateOutput("mtlx:surface", Sdf.ValueTypeNames.Token)
    mtlx_output.ConnectToSource(pbr_output)

    # Also create realitykit:vertex output (empty, but RCP expects it)
    usd_material.CreateOutput("realitykit:vertex", Sdf.ValueTypeNames.Token)

    # Diffuse/Base Color
    diffuse_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sDiffuse)
    if diffuse_prop.IsValid():
        texture_count = diffuse_prop.GetSrcObjectCount()
        if texture_count > 0:
            fbx_texture = diffuse_prop.GetSrcObject(0)
            if isinstance(fbx_texture, FbxFileTexture):
                texture_path = fbx_texture.GetFileName()
                texture_name = os.path.basename(texture_path)
                texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                tex_path = f"{mat_path}/DiffuseTexture"
                tex_shader = UsdShade.Shader.Define(stage, tex_path)
                tex_shader.CreateIdAttr("ND_RealityKitTexture2D_color3")
                tex_shader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                tex_shader.CreateInput("no_flip_v", Sdf.ValueTypeNames.Bool).Set(True)
                tex_output = tex_shader.CreateOutput("out", Sdf.ValueTypeNames.Color3f)

                base_color_input = pbr_shader.CreateInput("baseColor", Sdf.ValueTypeNames.Color3f)
                base_color_input.ConnectToSource(tex_output)
        else:
            if isinstance(fbx_material, FbxSurfaceLambert):
                diffuse_color = fbx_material.Diffuse.Get()
                pbr_shader.CreateInput("baseColor", Sdf.ValueTypeNames.Color3f).Set(
                    Gf.Vec3f(diffuse_color[0], diffuse_color[1], diffuse_color[2])
                )

    # Normal map (requires decode node)
    normal_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sNormalMap)
    if normal_prop.IsValid():
        texture_count = normal_prop.GetSrcObjectCount()
        if texture_count > 0:
            fbx_texture = normal_prop.GetSrcObject(0)
            if isinstance(fbx_texture, FbxFileTexture):
                texture_path = fbx_texture.GetFileName()
                texture_name = os.path.basename(texture_path)
                texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                # Create normal texture node
                normal_tex_path = f"{mat_path}/NormalTexture"
                normal_tex = UsdShade.Shader.Define(stage, normal_tex_path)
                normal_tex.CreateIdAttr("ND_RealityKitTexture2D_color3")
                normal_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                normal_tex.CreateInput("no_flip_v", Sdf.ValueTypeNames.Bool).Set(True)
                normal_tex_output = normal_tex.CreateOutput("out", Sdf.ValueTypeNames.Color3f)

                # Create normal map decode node
                decode_path = f"{mat_path}/NormalMapDecode"
                decode_shader = UsdShade.Shader.Define(stage, decode_path)
                decode_shader.CreateIdAttr("ND_normal_map_decode")
                decode_input = decode_shader.CreateInput("in", Sdf.ValueTypeNames.Float3)
                decode_input.ConnectToSource(normal_tex_output)
                decode_output = decode_shader.CreateOutput("out", Sdf.ValueTypeNames.Float3)

                # Connect to PBR shader
                normal_input = pbr_shader.CreateInput("normal", Sdf.ValueTypeNames.Float3)
                normal_input.ConnectToSource(decode_output)

    # Roughness
    roughness_set = False
    roughness_prop = fbx_material.FindProperty("ShininessExponent")
    if not roughness_prop.IsValid():
        roughness_prop = fbx_material.FindProperty("Roughness")

    if roughness_prop.IsValid():
        texture_count = roughness_prop.GetSrcObjectCount()
        if texture_count > 0:
            fbx_texture = roughness_prop.GetSrcObject(0)
            if isinstance(fbx_texture, FbxFileTexture):
                texture_path = fbx_texture.GetFileName()
                texture_name = os.path.basename(texture_path)
                texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                roughness_tex_path = f"{mat_path}/RoughnessTexture"
                roughness_tex = UsdShade.Shader.Define(stage, roughness_tex_path)
                roughness_tex.CreateIdAttr("ND_RealityKitTexture2D_float")
                roughness_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                roughness_tex.CreateInput("no_flip_v", Sdf.ValueTypeNames.Bool).Set(True)
                roughness_tex_output = roughness_tex.CreateOutput("out", Sdf.ValueTypeNames.Float)

                roughness_input = pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float)
                roughness_input.ConnectToSource(roughness_tex_output)
                roughness_set = True

    if not roughness_set and isinstance(fbx_material, FbxSurfacePhong):
        try:
            shininess = fbx_material.Shininess.Get()
            roughness = 1.0 - min(shininess / 100.0, 1.0)
            pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(max(0.0, min(1.0, roughness)))
            roughness_set = True
        except:
            pass

    if not roughness_set:
        pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)

    # Metallic
    metallic_prop = fbx_material.FindProperty("Metallic")
    if metallic_prop.IsValid():
        texture_count = metallic_prop.GetSrcObjectCount()
        if texture_count > 0:
            fbx_texture = metallic_prop.GetSrcObject(0)
            if isinstance(fbx_texture, FbxFileTexture):
                texture_path = fbx_texture.GetFileName()
                texture_name = os.path.basename(texture_path)
                texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                metallic_tex_path = f"{mat_path}/MetallicTexture"
                metallic_tex = UsdShade.Shader.Define(stage, metallic_tex_path)
                metallic_tex.CreateIdAttr("ND_RealityKitTexture2D_float")
                metallic_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                metallic_tex.CreateInput("no_flip_v", Sdf.ValueTypeNames.Bool).Set(True)
                metallic_tex_output = metallic_tex.CreateOutput("out", Sdf.ValueTypeNames.Float)

                metallic_input = pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float)
                metallic_input.ConnectToSource(metallic_tex_output)
        else:
            pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    else:
        pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

    # Emissive
    emissive_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sEmissive)
    if emissive_prop.IsValid():
        texture_count = emissive_prop.GetSrcObjectCount()
        if texture_count > 0:
            fbx_texture = emissive_prop.GetSrcObject(0)
            if isinstance(fbx_texture, FbxFileTexture):
                texture_path = fbx_texture.GetFileName()
                texture_name = os.path.basename(texture_path)
                texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                emissive_tex_path = f"{mat_path}/EmissiveTexture"
                emissive_tex = UsdShade.Shader.Define(stage, emissive_tex_path)
                emissive_tex.CreateIdAttr("ND_RealityKitTexture2D_color3")
                emissive_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                emissive_tex.CreateInput("no_flip_v", Sdf.ValueTypeNames.Bool).Set(True)
                emissive_tex_output = emissive_tex.CreateOutput("out", Sdf.ValueTypeNames.Color3f)

                emissive_input = pbr_shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f)
                emissive_input.ConnectToSource(emissive_tex_output)

    # Ambient Occlusion
    ao_prop = fbx_material.FindProperty("AmbientOcclusion")
    if ao_prop.IsValid():
        texture_count = ao_prop.GetSrcObjectCount()
        if texture_count > 0:
            fbx_texture = ao_prop.GetSrcObject(0)
            if isinstance(fbx_texture, FbxFileTexture):
                texture_path = fbx_texture.GetFileName()
                texture_name = os.path.basename(texture_path)
                texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                ao_tex_path = f"{mat_path}/OcclusionTexture"
                ao_tex = UsdShade.Shader.Define(stage, ao_tex_path)
                ao_tex.CreateIdAttr("ND_RealityKitTexture2D_float")
                ao_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                ao_tex.CreateInput("no_flip_v", Sdf.ValueTypeNames.Bool).Set(True)
                ao_tex_output = ao_tex.CreateOutput("out", Sdf.ValueTypeNames.Float)

                ao_input = pbr_shader.CreateInput("ambientOcclusion", Sdf.ValueTypeNames.Float)
                ao_input.ConnectToSource(ao_tex_output)

    return usd_material


def convert_fbx_to_usd(fbx_path, usd_path, use_materialx=False, use_directory_structure=False):
    """Main conversion function"""

    # Parse output path for directory structure
    base_name = os.path.splitext(os.path.basename(usd_path))[0]

    if use_directory_structure:
        # Create organized directory structure
        parent_dir = os.path.dirname(usd_path) or '.'
        output_dir = os.path.join(parent_dir, base_name)
        textures_dir = os.path.join(output_dir, "Textures")
        textures_subdir = "Textures"
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(textures_dir, exist_ok=True)
        # Update usd_path to be inside the new directory
        usd_path = os.path.join(output_dir, os.path.basename(usd_path))
    else:
        # Flat structure (original behavior)
        output_dir = os.path.dirname(usd_path)
        textures_dir = output_dir
        textures_subdir = None
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

    # Load FBX
    manager = FbxManager.Create()
    io_settings = FbxIOSettings.Create(manager, IOSROOT)
    manager.SetIOSettings(io_settings)

    scene = FbxScene.Create(manager, "scene")
    importer = FbxImporter.Create(manager, "")

    if not importer.Initialize(fbx_path, -1, manager.GetIOSettings()):
        raise Exception(f"Failed to load FBX: {importer.GetStatus().GetErrorString()}")

    if not importer.Import(scene):
        raise Exception("Failed to import FBX")

    importer.Destroy()
    FbxAxisSystem.OpenGL.ConvertScene(scene)

    # Get FBX scene unit and calculate scale factor
    scene_unit = scene.GetGlobalSettings().GetSystemUnit()
    fbx_scale = scene_unit.GetScaleFactor()  # Scale factor relative to centimeters
    print(f"FBX scale factor: {fbx_scale} (relative to cm)")

    # USD will use metersPerUnit = 0.01 (1 unit = 1 cm)
    # If FBX is in cm (scale=1.0), no conversion needed
    # If FBX is in meters (scale=100.0), we need to scale geometry by 100
    # If FBX is in inches (scale=2.54), we need to scale by 2.54
    geometry_scale = fbx_scale

    # Apply unit conversion to scene
    if fbx_scale != 1.0:
        unit_converter = FbxSystemUnit(1.0)  # Convert to centimeters
        unit_converter.ConvertScene(scene)
        print(f"Converted FBX scene units to centimeters")

    # Create USD stage
    stage = Usd.Stage.CreateNew(usd_path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    # Use metersPerUnit = 1.0 so RealityKit interprets the centimeter values as meters
    # This prevents the model from appearing 100x smaller
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    # Get model name
    model_name = make_valid_identifier(os.path.splitext(os.path.basename(fbx_path))[0])

    # Set default prim
    stage.SetDefaultPrim(stage.DefinePrim(f"/{model_name}", "Xform"))

    # Get all animation stacks
    time_mode = FbxTime.GetGlobalTimeMode()
    fps = FbxTime.GetFrameRate(time_mode)

    anim_stacks = []
    count = scene.GetSrcObjectCount(FbxCriteria.ObjectType(FbxAnimStack.ClassId))
    for i in range(count):
        anim_stacks.append(scene.GetSrcObject(FbxCriteria.ObjectType(FbxAnimStack.ClassId), i))

    print(f"Found {len(anim_stacks)} animation takes")
    for stack in anim_stacks:
        print(f"  - {stack.GetName()}")

    # Calculate total timeline for concatenated animation
    clips_info = []  # Store clip name, start_frame, end_frame for RealityKit
    current_frame = 0

    for stack in anim_stacks:
        scene.SetCurrentAnimationStack(stack)
        time_span = stack.GetLocalTimeSpan()
        start_time = time_span.GetStart().GetSecondDouble()
        stop_time = time_span.GetStop().GetSecondDouble()

        frames_count = int((stop_time - start_time) * fps + 0.5) + 1

        clips_info.append({
            'name': stack.GetName(),
            'start_frame': current_frame,
            'end_frame': current_frame + frames_count - 1,
            'stack': stack
        })

        current_frame += frames_count

    # Set stage time range to total
    if clips_info:
        stage.SetStartTimeCode(0)
        stage.SetEndTimeCode(current_frame - 1)
        stage.SetTimeCodesPerSecond(fps)

    # Find skeleton root
    def find_skeleton_root(node):
        attr = node.GetNodeAttribute()
        if isinstance(attr, FbxSkeleton):
            parent = node.GetParent()
            parent_attr = parent.GetNodeAttribute() if parent else None
            if not isinstance(parent_attr, FbxSkeleton):
                return node
        for i in range(node.GetChildCount()):
            result = find_skeleton_root(node.GetChild(i))
            if result:
                return result
        return None

    skel_root_joint = find_skeleton_root(scene.GetRootNode())

    if not skel_root_joint:
        # No skeleton found - delegate to non-skeletal code path
        print("No skeleton found - using non-skeletal export path")
        manager.Destroy()
        return convert_fbx_to_usd_no_skeleton(fbx_path, usd_path, use_materialx, use_directory_structure)

    # Collect joints
    joints = []
    joint_paths = {}

    def collect_joints(joint, path=""):
        joints.append(joint)
        name = make_valid_identifier(joint.GetName())
        joint_path = path + name
        joint_paths[id(joint)] = joint_path

        for i in range(joint.GetChildCount()):
            child = joint.GetChild(i)
            if isinstance(child.GetNodeAttribute(), FbxSkeleton):
                collect_joints(child, joint_path + "/")

    collect_joints(skel_root_joint)

    print(f"Found {len(joints)} joints")

    # Create hierarchy
    root_xform = UsdGeom.Xform.Define(stage, f"/{model_name}")

    # Create SkelRoot INSIDE model
    skel_root_path = f"/{model_name}/Root"
    UsdSkel.Root.Define(stage, skel_root_path)

    # Create Skeleton
    skel_path = f"{skel_root_path}/Skeleton"
    skel = UsdSkel.Skeleton.Define(stage, skel_path)

    # Set joints
    joint_names = [joint_paths[id(j)] for j in joints]
    skel.CreateJointsAttr().Set(joint_names)

    # Get rest transforms (local bind pose)
    rest_transforms = []
    for joint in joints:
        local_mat = gf_matrix_from_fbx(joint.EvaluateLocalTransform())
        rest_transforms.append(local_mat)

    skel.CreateRestTransformsAttr().Set(rest_transforms)

    # Bind transforms - extract from skin clusters (critical!)
    # Need to find a mesh with skinning to get the bind pose
    bind_transforms = None

    def find_mesh_with_skin(node):
        if isinstance(node.GetNodeAttribute(), FbxMesh):
            mesh = node.GetMesh()
            skin = mesh.GetDeformer(0, FbxDeformer.EDeformerType.eSkin)
            if skin:
                return skin
        for i in range(node.GetChildCount()):
            result = find_mesh_with_skin(node.GetChild(i))
            if result:
                return result
        return None

    skin = find_mesh_with_skin(scene.GetRootNode())

    if skin:
        # Build bind transforms from skin cluster data
        bind_transforms = []
        for joint in joints:
            # Find cluster for this joint
            found = False
            for c in range(skin.GetClusterCount()):
                cluster = skin.GetCluster(c)
                if id(cluster.GetLink()) == id(joint):
                    # Use TransformLinkMatrix directly (joint world transform at bind time)
                    transform_link = FbxAMatrix()
                    cluster.GetTransformLinkMatrix(transform_link)
                    bind_transforms.append(gf_matrix_from_fbx(transform_link))
                    found = True
                    break

            if not found:
                # Fallback: use rest transform inverse
                bind_transforms.append(rest_transforms[len(bind_transforms)].GetInverse())
    else:
        # No skin found, use rest inverse as fallback
        bind_transforms = [rest.GetInverse() for rest in rest_transforms]

    skel.CreateBindTransformsAttr().Set(bind_transforms)

    # Create Animation INSIDE Skeleton - concatenate all takes
    if clips_info:
        anim_path = f"{skel_path}/Animation"
        anim = UsdSkel.Animation.Define(stage, anim_path)
        anim.CreateJointsAttr().Set(joint_names)

        translations_attr = anim.CreateTranslationsAttr()
        rotations_attr = anim.CreateRotationsAttr()
        scales_attr = anim.CreateScalesAttr()

        anim_evaluator = scene.GetAnimationEvaluator()

        # Export all clips concatenated
        for clip_info in clips_info:
            scene.SetCurrentAnimationStack(clip_info['stack'])
            time_span = clip_info['stack'].GetLocalTimeSpan()
            start_time = time_span.GetStart().GetSecondDouble()
            stop_time = time_span.GetStop().GetSecondDouble()

            local_frames = clip_info['end_frame'] - clip_info['start_frame'] + 1

            for local_frame in range(local_frames):
                time = local_frame / fps + start_time
                fbx_time = FbxTime()
                fbx_time.SetSecondDouble(time)

                trans_list = []
                rot_list = []
                scale_list = []

                for joint in joints:
                    fbx_matrix = anim_evaluator.GetNodeLocalTransform(joint, fbx_time)

                    translation = fbx_matrix.GetT()
                    trans_list.append(Gf.Vec3f(translation[0], translation[1], translation[2]))

                    q = fbx_matrix.GetQ()
                    rot_list.append(Gf.Quatf(float(q[3]), float(q[0]), float(q[1]), float(q[2])))

                    scale = fbx_matrix.GetS()
                    scale_list.append(Gf.Vec3h(scale[0], scale[1], scale[2]))

                # Write at global frame offset
                global_frame = clip_info['start_frame'] + local_frame
                translations_attr.Set(trans_list, Usd.TimeCode(global_frame))
                rotations_attr.Set(rot_list, Usd.TimeCode(global_frame))
                scales_attr.Set(scale_list, Usd.TimeCode(global_frame))

        # Bind animation to Skeleton
        binding = UsdSkel.BindingAPI.Apply(skel.GetPrim())
        binding.CreateAnimationSourceRel().AddTarget(Sdf.Path(anim_path))

        # Bind SkelRoot to Skeleton and Animation
        skel_root_prim = stage.GetPrimAtPath(skel_root_path)
        skel_root_binding = UsdSkel.BindingAPI.Apply(skel_root_prim)
        skel_root_binding.CreateSkeletonRel().AddTarget(Sdf.Path(skel_path))
        skel_root_binding.CreateAnimationSourceRel().AddTarget(Sdf.Path(anim_path))

        total_frames = clips_info[-1]['end_frame'] + 1
        print(f"Exported {total_frames} frames of animation ({len(clips_info)} clips)")

    # Find and export meshes
    meshes = []
    def find_meshes(node):
        if isinstance(node.GetNodeAttribute(), FbxMesh):
            meshes.append(node)
        for i in range(node.GetChildCount()):
            find_meshes(node.GetChild(i))

    find_meshes(scene.GetRootNode())

    if meshes:
        # Create Geom under SkelRoot
        geom_path = f"{skel_root_path}/Geom"
        UsdGeom.Scope.Define(stage, geom_path)

        for mesh_node in meshes:
            fbx_mesh = mesh_node.GetMesh()
            mesh_name = make_valid_identifier(mesh_node.GetName())
            mesh_path = f"{geom_path}/{mesh_name}"
            usd_mesh = UsdGeom.Mesh.Define(stage, mesh_path)

            # Disable subdivision - keep as polygonal mesh
            usd_mesh.CreateSubdivisionSchemeAttr().Set("none")

            # Vertices
            verts = []
            for i in range(fbx_mesh.GetControlPointsCount()):
                pt = fbx_mesh.GetControlPoints()[i]
                verts.append(Gf.Vec3f(pt[0], pt[1], pt[2]))
            usd_mesh.CreatePointsAttr().Set(verts)

            # Faces
            counts = []
            indices = []
            for p in range(fbx_mesh.GetPolygonCount()):
                size = fbx_mesh.GetPolygonSize(p)
                counts.append(size)
                for v in range(size):
                    indices.append(fbx_mesh.GetPolygonVertex(p, v))

            usd_mesh.CreateFaceVertexCountsAttr().Set(counts)
            usd_mesh.CreateFaceVertexIndicesAttr().Set(indices)

            # Normals
            normal_elem = fbx_mesh.GetElementNormal()
            if normal_elem:
                normals = []
                for p in range(fbx_mesh.GetPolygonCount()):
                    for v in range(fbx_mesh.GetPolygonSize(p)):
                        idx = p * fbx_mesh.GetPolygonSize(p) + v
                        if normal_elem.GetReferenceMode() == FbxLayerElement.EReferenceMode.eDirect:
                            n = normal_elem.GetDirectArray().GetAt(idx)
                        else:
                            i = normal_elem.GetIndexArray().GetAt(idx)
                            n = normal_elem.GetDirectArray().GetAt(i)
                        normals.append(Gf.Vec3f(n[0], n[1], n[2]))

                if normals:
                    usd_mesh.CreateNormalsAttr().Set(normals)
                    usd_mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)

            # UVs - Export all UV sets
            uv_set_count = fbx_mesh.GetElementUVCount()
            primvar_api = UsdGeom.PrimvarsAPI(usd_mesh.GetPrim())

            for uv_index in range(uv_set_count):
                uv_elem = fbx_mesh.GetElementUV(uv_index)
                if uv_elem:
                    uvs = []
                    mapping_mode = uv_elem.GetMappingMode()
                    reference_mode = uv_elem.GetReferenceMode()

                    # Track polygon vertex index for proper UV indexing
                    polygon_vertex_index = 0

                    for p in range(fbx_mesh.GetPolygonCount()):
                        for v in range(fbx_mesh.GetPolygonSize(p)):
                            uv_index_to_use = 0

                            # Determine the correct index based on mapping mode
                            if mapping_mode == FbxLayerElement.EMappingMode.eByControlPoint:
                                # UV mapped per control point (vertex)
                                uv_index_to_use = fbx_mesh.GetPolygonVertex(p, v)
                            elif mapping_mode == FbxLayerElement.EMappingMode.eByPolygonVertex:
                                # UV mapped per polygon vertex (most common for meshes)
                                uv_index_to_use = polygon_vertex_index
                            elif mapping_mode == FbxLayerElement.EMappingMode.eByPolygon:
                                # UV mapped per polygon
                                uv_index_to_use = p
                            else:
                                # Default fallback
                                uv_index_to_use = polygon_vertex_index

                            # Get UV value based on reference mode
                            if reference_mode == FbxLayerElement.EReferenceMode.eDirect:
                                uv = uv_elem.GetDirectArray().GetAt(uv_index_to_use)
                            else:  # eIndexToDirect
                                uv_ref_index = uv_elem.GetIndexArray().GetAt(uv_index_to_use)
                                uv = uv_elem.GetDirectArray().GetAt(uv_ref_index)

                            uvs.append(Gf.Vec2f(uv[0], uv[1]))
                            polygon_vertex_index += 1

                    if uvs:
                        # First UV set gets the standard "st" name, others get "st1", "st2", etc.
                        uv_set_name = uv_elem.GetName()
                        if uv_index == 0:
                            primvar_name = "st"
                        elif uv_set_name:
                            # Use the FBX UV set name if available
                            primvar_name = f"st_{make_valid_identifier(uv_set_name)}"
                        else:
                            # Otherwise use index
                            primvar_name = f"st{uv_index}"

                        st_primvar = primvar_api.CreatePrimvar(primvar_name, Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
                        st_primvar.Set(uvs)
                        print(f"  UV set {uv_index}: {primvar_name} ({len(uvs)} coords)")

            # Materials
            material_elem = fbx_mesh.GetElementMaterial()
            if material_elem and mesh_node.GetMaterialCount() > 0:
                # Get the first material (most common case)
                fbx_material = mesh_node.GetMaterial(0)
                if fbx_material:
                    mat_name = make_valid_identifier(fbx_material.GetName())
                    mat_path = f"/{model_name}/Materials/{mat_name}"

                    # Create material scope if it doesn't exist
                    materials_scope_path = f"/{model_name}/Materials"
                    if not stage.GetPrimAtPath(materials_scope_path):
                        UsdGeom.Scope.Define(stage, materials_scope_path)

                    # Skip if material already created
                    if stage.GetPrimAtPath(mat_path):
                        usd_material = UsdShade.Material.Get(stage, mat_path)
                        UsdShade.MaterialBindingAPI(usd_mesh.GetPrim()).Bind(usd_material)
                        continue

                    if use_materialx:
                        # Use MaterialX shaders for Reality Composer Pro
                        usd_material = create_materialx_material(stage, mat_path, fbx_material, textures_subdir=textures_subdir)
                        UsdShade.MaterialBindingAPI(usd_mesh.GetPrim()).Bind(usd_material)
                    else:
                        # Use UsdPreviewSurface (default)
                        usd_material = UsdShade.Material.Define(stage, mat_path)

                        # Create USD Preview Surface shader
                        shader_path = f"{mat_path}/PreviewSurface"
                        shader = UsdShade.Shader.Define(stage, shader_path)
                        shader.CreateIdAttr("UsdPreviewSurface")

                        # Create primvar reader for st coordinates (shared by all textures)
                        primvar_reader_path = f"{mat_path}/PrimvarReader"
                        primvar_reader = UsdShade.Shader.Define(stage, primvar_reader_path)
                        primvar_reader.CreateIdAttr("UsdPrimvarReader_float2")
                        primvar_reader.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")
                        st_output = primvar_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

                        # Get diffuse color/texture
                        diffuse_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sDiffuse)
                        if diffuse_prop.IsValid():
                            # Check for texture
                            texture_count = diffuse_prop.GetSrcObjectCount()
                            if texture_count > 0:
                                fbx_texture = diffuse_prop.GetSrcObject(0)
                                if isinstance(fbx_texture, FbxFileTexture):
                                    # Get texture file path
                                    texture_path = fbx_texture.GetFileName()
                                    texture_name = os.path.basename(texture_path)
                                    texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                                    # Create texture reader shader
                                    tex_reader_path = f"{mat_path}/DiffuseTexture"
                                    tex_reader = UsdShade.Shader.Define(stage, tex_reader_path)
                                    tex_reader.CreateIdAttr("UsdUVTexture")
                                    tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                                    tex_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)

                                    # Connect texture to diffuse color
                                    diffuse_output = tex_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                                    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(diffuse_output)
                            else:
                                # Use solid color
                                if isinstance(fbx_material, FbxSurfaceLambert):
                                    diffuse_color = fbx_material.Diffuse.Get()
                                    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
                                        Gf.Vec3f(diffuse_color[0], diffuse_color[1], diffuse_color[2])
                                    )

                        # Get normal map
                        normal_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sNormalMap)
                        if normal_prop.IsValid():
                            texture_count = normal_prop.GetSrcObjectCount()
                            if texture_count > 0:
                                fbx_texture = normal_prop.GetSrcObject(0)
                                if isinstance(fbx_texture, FbxFileTexture):
                                    texture_path = fbx_texture.GetFileName()
                                    texture_name = os.path.basename(texture_path)
                                    texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                                    # Create normal texture reader
                                    normal_reader_path = f"{mat_path}/NormalTexture"
                                    normal_reader = UsdShade.Shader.Define(stage, normal_reader_path)
                                    normal_reader.CreateIdAttr("UsdUVTexture")
                                    normal_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                                    normal_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                                    # For normal maps, we need to specify it's a normal map
                                    normal_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                                    # Connect to normal input
                                    normal_output = normal_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                                    shader.CreateInput("normal", Sdf.ValueTypeNames.Normal3f).ConnectToSource(normal_output)

                        # Get bump/height map (alternative to normal map)
                        bump_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sBump)
                        if bump_prop.IsValid() and not normal_prop.IsValid():
                            texture_count = bump_prop.GetSrcObjectCount()
                            if texture_count > 0:
                                fbx_texture = bump_prop.GetSrcObject(0)
                                if isinstance(fbx_texture, FbxFileTexture):
                                    texture_path = fbx_texture.GetFileName()
                                    texture_name = os.path.basename(texture_path)
                                    texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                                    # Create bump texture reader
                                    bump_reader_path = f"{mat_path}/BumpTexture"
                                    bump_reader = UsdShade.Shader.Define(stage, bump_reader_path)
                                    bump_reader.CreateIdAttr("UsdUVTexture")
                                    bump_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                                    bump_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                                    bump_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                                    # Connect to normal input (bump maps can be used as normal maps)
                                    bump_output = bump_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                                    shader.CreateInput("normal", Sdf.ValueTypeNames.Normal3f).ConnectToSource(bump_output)

                        # Get roughness map or use shininess
                        roughness_set = False
                        roughness_prop = fbx_material.FindProperty("ShininessExponent")
                        if not roughness_prop.IsValid():
                            roughness_prop = fbx_material.FindProperty("Roughness")

                        if roughness_prop.IsValid():
                            texture_count = roughness_prop.GetSrcObjectCount()
                            if texture_count > 0:
                                fbx_texture = roughness_prop.GetSrcObject(0)
                                if isinstance(fbx_texture, FbxFileTexture):
                                    texture_path = fbx_texture.GetFileName()
                                    texture_name = os.path.basename(texture_path)
                                    texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                                    # Create roughness texture reader
                                    roughness_reader_path = f"{mat_path}/RoughnessTexture"
                                    roughness_reader = UsdShade.Shader.Define(stage, roughness_reader_path)
                                    roughness_reader.CreateIdAttr("UsdUVTexture")
                                    roughness_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                                    roughness_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                                    roughness_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                                    # Use red channel for roughness
                                    roughness_output = roughness_reader.CreateOutput("r", Sdf.ValueTypeNames.Float)
                                    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).ConnectToSource(roughness_output)
                                    roughness_set = True

                        # Try to use shininess from Phong material if roughness not set
                        if not roughness_set and isinstance(fbx_material, FbxSurfacePhong):
                            try:
                                shininess = fbx_material.Shininess.Get()
                                # Convert shininess (0-100) to roughness (0-1)
                                # Higher shininess = lower roughness
                                roughness = 1.0 - min(shininess / 100.0, 1.0)
                                shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(max(0.0, min(1.0, roughness)))
                                roughness_set = True
                            except:
                                pass

                        # Default roughness if nothing else worked
                        if not roughness_set:
                            # Use 0.5 as a reasonable default for diffuse materials
                            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)

                        # Get metallic map
                        metallic_prop = fbx_material.FindProperty("Metallic")
                        if metallic_prop.IsValid():
                            texture_count = metallic_prop.GetSrcObjectCount()
                            if texture_count > 0:
                                fbx_texture = metallic_prop.GetSrcObject(0)
                                if isinstance(fbx_texture, FbxFileTexture):
                                    texture_path = fbx_texture.GetFileName()
                                    texture_name = os.path.basename(texture_path)
                                    texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                                    # Create metallic texture reader
                                    metallic_reader_path = f"{mat_path}/MetallicTexture"
                                    metallic_reader = UsdShade.Shader.Define(stage, metallic_reader_path)
                                    metallic_reader.CreateIdAttr("UsdUVTexture")
                                    metallic_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                                    metallic_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                                    metallic_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                                    # Use red channel for metallic
                                    metallic_output = metallic_reader.CreateOutput("r", Sdf.ValueTypeNames.Float)
                                    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).ConnectToSource(metallic_output)
                            else:
                                # Default to 0
                                shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
                        else:
                            shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

                        # Get emissive map
                        emissive_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sEmissive)
                        if emissive_prop.IsValid():
                            texture_count = emissive_prop.GetSrcObjectCount()
                            if texture_count > 0:
                                fbx_texture = emissive_prop.GetSrcObject(0)
                                if isinstance(fbx_texture, FbxFileTexture):
                                    texture_path = fbx_texture.GetFileName()
                                    texture_name = os.path.basename(texture_path)
                                    texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                                    # Create emissive texture reader
                                    emissive_reader_path = f"{mat_path}/EmissiveTexture"
                                    emissive_reader = UsdShade.Shader.Define(stage, emissive_reader_path)
                                    emissive_reader.CreateIdAttr("UsdUVTexture")
                                    emissive_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                                    emissive_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)

                                    # Connect to emissive color
                                    emissive_output = emissive_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                                    shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(emissive_output)

                        # Get occlusion/AO map
                        ao_prop = fbx_material.FindProperty("AmbientOcclusion")
                        if ao_prop.IsValid():
                            texture_count = ao_prop.GetSrcObjectCount()
                            if texture_count > 0:
                                fbx_texture = ao_prop.GetSrcObject(0)
                                if isinstance(fbx_texture, FbxFileTexture):
                                    texture_path = fbx_texture.GetFileName()
                                    texture_name = os.path.basename(texture_path)
                                    texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                                    # Create AO texture reader
                                    ao_reader_path = f"{mat_path}/OcclusionTexture"
                                    ao_reader = UsdShade.Shader.Define(stage, ao_reader_path)
                                    ao_reader.CreateIdAttr("UsdUVTexture")
                                    ao_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                                    ao_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                                    ao_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                                    # Connect to occlusion
                                    ao_output = ao_reader.CreateOutput("r", Sdf.ValueTypeNames.Float)
                                    shader.CreateInput("occlusion", Sdf.ValueTypeNames.Float).ConnectToSource(ao_output)

                        # Connect shader to material
                        shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
                        usd_material.CreateSurfaceOutput().ConnectToSource(shader.GetOutput("surface"))

                        # Bind material to mesh
                        UsdShade.MaterialBindingAPI(usd_mesh.GetPrim()).Bind(usd_material)

            # Skinning
            skin = fbx_mesh.GetDeformer(0, FbxDeformer.EDeformerType.eSkin)
            if skin:
                num_verts = fbx_mesh.GetControlPointsCount()
                vert_weights = [[] for _ in range(num_verts)]

                for c in range(skin.GetClusterCount()):
                    cluster = skin.GetCluster(c)
                    link = cluster.GetLink()

                    joint_idx = -1
                    for j_idx, j in enumerate(joints):
                        if id(j) == id(link):
                            joint_idx = j_idx
                            break

                    if joint_idx == -1:
                        continue

                    indices_arr = cluster.GetControlPointIndices()
                    weights_arr = cluster.GetControlPointWeights()

                    for i in range(cluster.GetControlPointIndicesCount()):
                        v_idx = indices_arr[i]
                        weight = weights_arr[i]
                        if v_idx < num_verts and weight > 0:
                            vert_weights[v_idx].append((joint_idx, weight))

                # Convert to USD format
                max_influences = 4
                flat_indices = []
                flat_weights = []

                for weights_list in vert_weights:
                    weights_list.sort(key=lambda x: x[1], reverse=True)
                    weights_list = weights_list[:max_influences]

                    total = sum(w for _, w in weights_list)
                    if total > 0:
                        weights_list = [(j, w/total) for j, w in weights_list]

                    while len(weights_list) < max_influences:
                        weights_list.append((0, 0.0))

                    for j, w in weights_list:
                        flat_indices.append(j)
                        flat_weights.append(w)

                # Apply skinning
                binding_api = UsdSkel.BindingAPI.Apply(usd_mesh.GetPrim())
                binding_api.CreateSkeletonRel().AddTarget(Sdf.Path(skel_path))
                binding_api.CreateGeomBindTransformAttr().Set(Gf.Matrix4d(1.0))

                indices_pv = UsdGeom.Primvar(usd_mesh.GetPrim().CreateAttribute(
                    "primvars:skel:jointIndices", Sdf.ValueTypeNames.IntArray, False
                ))
                indices_pv.SetInterpolation(UsdGeom.Tokens.vertex)
                indices_pv.Set(flat_indices)
                indices_pv.SetElementSize(max_influences)

                weights_pv = UsdGeom.Primvar(usd_mesh.GetPrim().CreateAttribute(
                    "primvars:skel:jointWeights", Sdf.ValueTypeNames.FloatArray, False
                ))
                weights_pv.SetInterpolation(UsdGeom.Tokens.vertex)
                weights_pv.Set(flat_weights)
                weights_pv.SetElementSize(max_influences)

        print(f"Exported {len(meshes)} mesh(es)")

    # Create RealityKit AnimationLibrary component inside SkelRoot
    # This matches Reality Composer Pro's pattern
    if clips_info:
        anim_lib_path = f"{skel_root_path}/AnimationLibrary"
        anim_lib_prim = stage.DefinePrim(anim_lib_path, "RealityKitComponent")

        # Set info:id attribute
        info_id_attr = anim_lib_prim.CreateAttribute(
            "info:id", Sdf.ValueTypeNames.Token, custom=True
        )
        info_id_attr.Set("RealityKit.AnimationLibrary")

        # Prepare clip data
        clip_names = [clip['name'] for clip in clips_info]
        start_times = [float(clip['start_frame']) / float(fps) for clip in clips_info]

        # Create ClipDefinition
        clip_def_path = f"{anim_lib_path}/Clip_Animation"
        clip_def_prim = stage.DefinePrim(clip_def_path, "RealityKitClipDefinition")

        clip_names_attr = clip_def_prim.CreateAttribute(
            "clipNames", Sdf.ValueTypeNames.StringArray
        )
        clip_names_attr.Set(clip_names)

        src_anim_attr = clip_def_prim.CreateAttribute(
            "sourceAnimationName", Sdf.ValueTypeNames.String
        )
        src_anim_attr.Set("default subtree animation")

        start_times_attr = clip_def_prim.CreateAttribute(
            "startTimes", Sdf.ValueTypeNames.DoubleArray
        )
        start_times_attr.Set(start_times)

        print(f"Created AnimationLibrary with {len(clips_info)} clips")

    # Save
    stage.GetRootLayer().Save()
    print(f"✓ Saved: {usd_path}")

    # Copy textures to output directory
    if textures_dir:
        texture_paths = collect_texture_paths(meshes)
        if texture_paths:
            copied_textures = copy_textures_to_output(texture_paths, textures_dir)
            if copied_textures:
                print(f"✓ Copied {len(copied_textures)} texture(s)")

    manager.Destroy()


def convert_fbx_to_usd_no_skeleton(fbx_path, usd_path, use_materialx=False, use_directory_structure=False):
    """Convert FBX without skeleton to USD with concatenated animations.

    This is a separate code path for models without skeletons.
    Animations are exported as time-sampled transforms on mesh Xforms.
    """
    # Parse output path for directory structure
    base_name = os.path.splitext(os.path.basename(usd_path))[0]

    if use_directory_structure:
        # Create organized directory structure
        parent_dir = os.path.dirname(usd_path) or '.'
        output_dir = os.path.join(parent_dir, base_name)
        textures_dir = os.path.join(output_dir, "Textures")
        textures_subdir = "Textures"
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(textures_dir, exist_ok=True)
        # Update usd_path to be inside the new directory
        usd_path = os.path.join(output_dir, os.path.basename(usd_path))
    else:
        # Flat structure (original behavior)
        output_dir = os.path.dirname(usd_path)
        textures_dir = output_dir
        textures_subdir = None
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

    # Load FBX
    manager = FbxManager.Create()
    io_settings = FbxIOSettings.Create(manager, IOSROOT)
    manager.SetIOSettings(io_settings)

    scene = FbxScene.Create(manager, "scene")
    importer = FbxImporter.Create(manager, "")

    if not importer.Initialize(fbx_path, -1, manager.GetIOSettings()):
        raise Exception(f"Failed to load FBX: {importer.GetStatus().GetErrorString()}")

    if not importer.Import(scene):
        raise Exception("Failed to import FBX")

    importer.Destroy()
    FbxAxisSystem.OpenGL.ConvertScene(scene)

    # Get FBX scene unit and apply conversion
    scene_unit = scene.GetGlobalSettings().GetSystemUnit()
    fbx_scale = scene_unit.GetScaleFactor()
    print(f"FBX scale factor: {fbx_scale} (relative to cm)")

    if fbx_scale != 1.0:
        unit_converter = FbxSystemUnit(1.0)
        unit_converter.ConvertScene(scene)
        print(f"Converted FBX scene units to centimeters")

    # Create USD stage
    stage = Usd.Stage.CreateNew(usd_path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    # Get model name
    model_name = make_valid_identifier(os.path.splitext(os.path.basename(fbx_path))[0])

    # Set default prim
    stage.SetDefaultPrim(stage.DefinePrim(f"/{model_name}", "Xform"))

    # Get all animation stacks
    time_mode = FbxTime.GetGlobalTimeMode()
    fps = FbxTime.GetFrameRate(time_mode)

    anim_stacks = []
    count = scene.GetSrcObjectCount(FbxCriteria.ObjectType(FbxAnimStack.ClassId))
    for i in range(count):
        anim_stacks.append(scene.GetSrcObject(FbxCriteria.ObjectType(FbxAnimStack.ClassId), i))

    print(f"Found {len(anim_stacks)} animation takes")
    for stack in anim_stacks:
        print(f"  - {stack.GetName()}")

    # Calculate total timeline for concatenated animation
    clips_info = []
    current_frame = 0

    for stack in anim_stacks:
        scene.SetCurrentAnimationStack(stack)
        time_span = stack.GetLocalTimeSpan()
        start_time = time_span.GetStart().GetSecondDouble()
        stop_time = time_span.GetStop().GetSecondDouble()

        frames_count = int((stop_time - start_time) * fps + 0.5) + 1

        clips_info.append({
            'name': stack.GetName(),
            'start_frame': current_frame,
            'end_frame': current_frame + frames_count - 1,
            'stack': stack
        })

        current_frame += frames_count

    # Set stage time range if there are animations
    if clips_info:
        stage.SetStartTimeCode(0)
        stage.SetEndTimeCode(current_frame - 1)
        stage.SetTimeCodesPerSecond(fps)

    # Find meshes
    meshes = []
    def find_meshes(node):
        if isinstance(node.GetNodeAttribute(), FbxMesh):
            meshes.append(node)
        for i in range(node.GetChildCount()):
            find_meshes(node.GetChild(i))

    find_meshes(scene.GetRootNode())

    if meshes:
        # Create Geom scope directly under model (no SkelRoot needed)
        geom_path = f"/{model_name}/Geom"
        export_meshes_no_skeleton(stage, geom_path, model_name, scene, meshes, include_materials=True, textures_subdir=textures_subdir)

        # Export transform animations for each mesh
        if clips_info:
            for mesh_node in meshes:
                mesh_name = make_valid_identifier(mesh_node.GetName())
                mesh_path = f"{geom_path}/{mesh_name}"
                export_transform_animation(stage, mesh_path, scene, mesh_node, clips_info, fps)

            total_frames = clips_info[-1]['end_frame'] + 1
            print(f"Exported {total_frames} frames of transform animation ({len(clips_info)} clips)")

        print(f"Exported {len(meshes)} mesh(es)")

    # Create RealityKit AnimationLibrary component if there are animations
    if clips_info:
        anim_lib_path = f"/{model_name}/AnimationLibrary"
        anim_lib_prim = stage.DefinePrim(anim_lib_path, "RealityKitComponent")

        # Set info:id attribute
        info_id_attr = anim_lib_prim.CreateAttribute(
            "info:id", Sdf.ValueTypeNames.Token, custom=True
        )
        info_id_attr.Set("RealityKit.AnimationLibrary")

        # Prepare clip data
        clip_names = [clip['name'] for clip in clips_info]
        start_times = [float(clip['start_frame']) / float(fps) for clip in clips_info]

        # Create ClipDefinition
        clip_def_path = f"{anim_lib_path}/Clip_Animation"
        clip_def_prim = stage.DefinePrim(clip_def_path, "RealityKitClipDefinition")

        clip_names_attr = clip_def_prim.CreateAttribute(
            "clipNames", Sdf.ValueTypeNames.StringArray
        )
        clip_names_attr.Set(clip_names)

        src_anim_attr = clip_def_prim.CreateAttribute(
            "sourceAnimationName", Sdf.ValueTypeNames.String
        )
        src_anim_attr.Set("default subtree animation")

        start_times_attr = clip_def_prim.CreateAttribute(
            "startTimes", Sdf.ValueTypeNames.DoubleArray
        )
        start_times_attr.Set(start_times)

        print(f"Created AnimationLibrary with {len(clips_info)} clips")

    # Save
    stage.GetRootLayer().Save()
    print(f"✓ Saved: {usd_path}")

    # Copy textures to output directory
    if textures_dir:
        texture_paths = collect_texture_paths(meshes)
        if texture_paths:
            copied_textures = copy_textures_to_output(texture_paths, textures_dir)
            if copied_textures:
                print(f"✓ Copied {len(copied_textures)} texture(s)")

    manager.Destroy()


def load_fbx_scene(fbx_path):
    """Load and prepare an FBX scene, returns (manager, scene)"""
    manager = FbxManager.Create()
    io_settings = FbxIOSettings.Create(manager, IOSROOT)
    manager.SetIOSettings(io_settings)

    scene = FbxScene.Create(manager, "scene")
    importer = FbxImporter.Create(manager, "")

    if not importer.Initialize(fbx_path, -1, manager.GetIOSettings()):
        raise Exception(f"Failed to load FBX: {importer.GetStatus().GetErrorString()}")

    if not importer.Import(scene):
        raise Exception("Failed to import FBX")

    importer.Destroy()
    FbxAxisSystem.OpenGL.ConvertScene(scene)

    # Get FBX scene unit and calculate scale factor
    scene_unit = scene.GetGlobalSettings().GetSystemUnit()
    fbx_scale = scene_unit.GetScaleFactor()

    # Apply unit conversion to scene
    if fbx_scale != 1.0:
        unit_converter = FbxSystemUnit(1.0)
        unit_converter.ConvertScene(scene)

    return manager, scene


def find_skeleton_root_node(scene):
    """Find the root skeleton node in the scene"""
    def find_skeleton_root(node):
        attr = node.GetNodeAttribute()
        if isinstance(attr, FbxSkeleton):
            parent = node.GetParent()
            parent_attr = parent.GetNodeAttribute() if parent else None
            if not isinstance(parent_attr, FbxSkeleton):
                return node
        for i in range(node.GetChildCount()):
            result = find_skeleton_root(node.GetChild(i))
            if result:
                return result
        return None

    return find_skeleton_root(scene.GetRootNode())


def collect_joints(skel_root_joint):
    """Collect all joints and their paths from a skeleton root"""
    joints = []
    joint_paths = {}

    def collect_joints_recursive(joint, path=""):
        joints.append(joint)
        name = make_valid_identifier(joint.GetName())
        joint_path = path + name
        joint_paths[id(joint)] = joint_path

        for i in range(joint.GetChildCount()):
            child = joint.GetChild(i)
            if isinstance(child.GetNodeAttribute(), FbxSkeleton):
                collect_joints_recursive(child, joint_path + "/")

    collect_joints_recursive(skel_root_joint)
    return joints, joint_paths


def get_bind_transforms(scene, joints, rest_transforms):
    """Extract bind transforms from skin clusters"""
    def find_mesh_with_skin(node):
        if isinstance(node.GetNodeAttribute(), FbxMesh):
            mesh = node.GetMesh()
            skin = mesh.GetDeformer(0, FbxDeformer.EDeformerType.eSkin)
            if skin:
                return skin
        for i in range(node.GetChildCount()):
            result = find_mesh_with_skin(node.GetChild(i))
            if result:
                return result
        return None

    skin = find_mesh_with_skin(scene.GetRootNode())

    if skin:
        bind_transforms = []
        for joint in joints:
            found = False
            for c in range(skin.GetClusterCount()):
                cluster = skin.GetCluster(c)
                if id(cluster.GetLink()) == id(joint):
                    transform_link = FbxAMatrix()
                    cluster.GetTransformLinkMatrix(transform_link)
                    bind_transforms.append(gf_matrix_from_fbx(transform_link))
                    found = True
                    break

            if not found:
                bind_transforms.append(rest_transforms[len(bind_transforms)].GetInverse())
    else:
        bind_transforms = [rest.GetInverse() for rest in rest_transforms]

    return bind_transforms


def find_mesh_nodes(scene):
    """Find all mesh nodes in the scene"""
    meshes = []

    def find_meshes(node):
        if isinstance(node.GetNodeAttribute(), FbxMesh):
            meshes.append(node)
        for i in range(node.GetChildCount()):
            find_meshes(node.GetChild(i))

    find_meshes(scene.GetRootNode())
    return meshes


def export_skeleton(stage, skel_path, joints, joint_paths, bind_transforms):
    """Create skeleton prim with joints, rest and bind transforms"""
    skel = UsdSkel.Skeleton.Define(stage, skel_path)

    joint_names = [joint_paths[id(j)] for j in joints]
    skel.CreateJointsAttr().Set(joint_names)

    rest_transforms = []
    for joint in joints:
        local_mat = gf_matrix_from_fbx(joint.EvaluateLocalTransform())
        rest_transforms.append(local_mat)

    skel.CreateRestTransformsAttr().Set(rest_transforms)
    skel.CreateBindTransformsAttr().Set(bind_transforms)

    return skel, joint_names, rest_transforms


def export_animation(stage, anim_path, skel_path, skel_root_path, scene, joints, joint_names, clip_info, fps):
    """Export a single animation clip to the stage"""
    anim = UsdSkel.Animation.Define(stage, anim_path)
    anim.CreateJointsAttr().Set(joint_names)

    translations_attr = anim.CreateTranslationsAttr()
    rotations_attr = anim.CreateRotationsAttr()
    scales_attr = anim.CreateScalesAttr()

    anim_evaluator = scene.GetAnimationEvaluator()

    scene.SetCurrentAnimationStack(clip_info['stack'])
    time_span = clip_info['stack'].GetLocalTimeSpan()
    start_time = time_span.GetStart().GetSecondDouble()

    local_frames = clip_info['end_frame'] - clip_info['start_frame'] + 1

    for local_frame in range(local_frames):
        time = local_frame / fps + start_time
        fbx_time = FbxTime()
        fbx_time.SetSecondDouble(time)

        trans_list = []
        rot_list = []
        scale_list = []

        for joint in joints:
            fbx_matrix = anim_evaluator.GetNodeLocalTransform(joint, fbx_time)

            translation = fbx_matrix.GetT()
            trans_list.append(Gf.Vec3f(translation[0], translation[1], translation[2]))

            q = fbx_matrix.GetQ()
            rot_list.append(Gf.Quatf(float(q[3]), float(q[0]), float(q[1]), float(q[2])))

            scale = fbx_matrix.GetS()
            scale_list.append(Gf.Vec3h(scale[0], scale[1], scale[2]))

        # Write at global frame offset
        global_frame = clip_info['start_frame'] + local_frame
        translations_attr.Set(trans_list, Usd.TimeCode(global_frame))
        rotations_attr.Set(rot_list, Usd.TimeCode(global_frame))
        scales_attr.Set(scale_list, Usd.TimeCode(global_frame))

    # Bind animation to Skeleton
    skel_prim = stage.GetPrimAtPath(skel_path)
    binding = UsdSkel.BindingAPI.Apply(skel_prim)
    binding.CreateAnimationSourceRel().AddTarget(Sdf.Path(anim_path))

    # Bind SkelRoot to Skeleton and Animation
    skel_root_prim = stage.GetPrimAtPath(skel_root_path)
    skel_root_binding = UsdSkel.BindingAPI.Apply(skel_root_prim)
    skel_root_binding.CreateSkeletonRel().AddTarget(Sdf.Path(skel_path))
    skel_root_binding.CreateAnimationSourceRel().AddTarget(Sdf.Path(anim_path))


def export_meshes(stage, geom_path, skel_path, model_name, scene, mesh_nodes, joints, include_materials=True):
    """Export all meshes to the stage. Set include_materials=False to skip materials."""
    UsdGeom.Scope.Define(stage, geom_path)

    for mesh_node in mesh_nodes:
        fbx_mesh = mesh_node.GetMesh()
        mesh_name = make_valid_identifier(mesh_node.GetName())
        mesh_path = f"{geom_path}/{mesh_name}"
        usd_mesh = UsdGeom.Mesh.Define(stage, mesh_path)

        # Disable subdivision - keep as polygonal mesh
        usd_mesh.CreateSubdivisionSchemeAttr().Set("none")

        # Vertices
        verts = []
        for i in range(fbx_mesh.GetControlPointsCount()):
            pt = fbx_mesh.GetControlPoints()[i]
            verts.append(Gf.Vec3f(pt[0], pt[1], pt[2]))
        usd_mesh.CreatePointsAttr().Set(verts)

        # Faces
        counts = []
        indices = []
        for p in range(fbx_mesh.GetPolygonCount()):
            size = fbx_mesh.GetPolygonSize(p)
            counts.append(size)
            for v in range(size):
                indices.append(fbx_mesh.GetPolygonVertex(p, v))

        usd_mesh.CreateFaceVertexCountsAttr().Set(counts)
        usd_mesh.CreateFaceVertexIndicesAttr().Set(indices)

        # Normals
        normal_elem = fbx_mesh.GetElementNormal()
        if normal_elem:
            normals = []
            for p in range(fbx_mesh.GetPolygonCount()):
                for v in range(fbx_mesh.GetPolygonSize(p)):
                    idx = p * fbx_mesh.GetPolygonSize(p) + v
                    if normal_elem.GetReferenceMode() == FbxLayerElement.EReferenceMode.eDirect:
                        n = normal_elem.GetDirectArray().GetAt(idx)
                    else:
                        i = normal_elem.GetIndexArray().GetAt(idx)
                        n = normal_elem.GetDirectArray().GetAt(i)
                    normals.append(Gf.Vec3f(n[0], n[1], n[2]))

            if normals:
                usd_mesh.CreateNormalsAttr().Set(normals)
                usd_mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)

        # UVs
        uv_set_count = fbx_mesh.GetElementUVCount()
        primvar_api = UsdGeom.PrimvarsAPI(usd_mesh.GetPrim())

        for uv_index in range(uv_set_count):
            uv_elem = fbx_mesh.GetElementUV(uv_index)
            if uv_elem:
                uvs = []
                mapping_mode = uv_elem.GetMappingMode()
                reference_mode = uv_elem.GetReferenceMode()

                polygon_vertex_index = 0

                for p in range(fbx_mesh.GetPolygonCount()):
                    for v in range(fbx_mesh.GetPolygonSize(p)):
                        uv_index_to_use = 0

                        if mapping_mode == FbxLayerElement.EMappingMode.eByControlPoint:
                            uv_index_to_use = fbx_mesh.GetPolygonVertex(p, v)
                        elif mapping_mode == FbxLayerElement.EMappingMode.eByPolygonVertex:
                            uv_index_to_use = polygon_vertex_index
                        elif mapping_mode == FbxLayerElement.EMappingMode.eByPolygon:
                            uv_index_to_use = p
                        else:
                            uv_index_to_use = polygon_vertex_index

                        if reference_mode == FbxLayerElement.EReferenceMode.eDirect:
                            uv = uv_elem.GetDirectArray().GetAt(uv_index_to_use)
                        else:
                            uv_ref_index = uv_elem.GetIndexArray().GetAt(uv_index_to_use)
                            uv = uv_elem.GetDirectArray().GetAt(uv_ref_index)

                        uvs.append(Gf.Vec2f(uv[0], uv[1]))
                        polygon_vertex_index += 1

                if uvs:
                    uv_set_name = uv_elem.GetName()
                    if uv_index == 0:
                        primvar_name = "st"
                    elif uv_set_name:
                        primvar_name = f"st_{make_valid_identifier(uv_set_name)}"
                    else:
                        primvar_name = f"st{uv_index}"

                    st_primvar = primvar_api.CreatePrimvar(primvar_name, Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
                    st_primvar.Set(uvs)

        # Materials
        material_elem = fbx_mesh.GetElementMaterial()
        if include_materials and material_elem and mesh_node.GetMaterialCount() > 0:
            fbx_material = mesh_node.GetMaterial(0)
            if fbx_material:
                mat_name = make_valid_identifier(fbx_material.GetName())
                mat_path = f"/{model_name}/Materials/{mat_name}"

                materials_scope_path = f"/{model_name}/Materials"
                if not stage.GetPrimAtPath(materials_scope_path):
                    UsdGeom.Scope.Define(stage, materials_scope_path)

                usd_material = UsdShade.Material.Define(stage, mat_path)

                shader_path = f"{mat_path}/PreviewSurface"
                shader = UsdShade.Shader.Define(stage, shader_path)
                shader.CreateIdAttr("UsdPreviewSurface")

                primvar_reader_path = f"{mat_path}/PrimvarReader"
                primvar_reader = UsdShade.Shader.Define(stage, primvar_reader_path)
                primvar_reader.CreateIdAttr("UsdPrimvarReader_float2")
                primvar_reader.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")
                st_output = primvar_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

                diffuse_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sDiffuse)
                if diffuse_prop.IsValid():
                    texture_count = diffuse_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = diffuse_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            tex_reader_path = f"{mat_path}/DiffuseTexture"
                            tex_reader = UsdShade.Shader.Define(stage, tex_reader_path)
                            tex_reader.CreateIdAttr("UsdUVTexture")
                            tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            tex_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)

                            diffuse_output = tex_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(diffuse_output)
                    else:
                        if isinstance(fbx_material, FbxSurfaceLambert):
                            diffuse_color = fbx_material.Diffuse.Get()
                            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
                                Gf.Vec3f(diffuse_color[0], diffuse_color[1], diffuse_color[2])
                            )

                # Normal map
                normal_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sNormalMap)
                if normal_prop.IsValid():
                    texture_count = normal_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = normal_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            normal_reader_path = f"{mat_path}/NormalTexture"
                            normal_reader = UsdShade.Shader.Define(stage, normal_reader_path)
                            normal_reader.CreateIdAttr("UsdUVTexture")
                            normal_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            normal_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                            normal_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                            normal_output = normal_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                            shader.CreateInput("normal", Sdf.ValueTypeNames.Normal3f).ConnectToSource(normal_output)

                # Bump map fallback
                bump_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sBump)
                if bump_prop.IsValid() and not normal_prop.IsValid():
                    texture_count = bump_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = bump_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            bump_reader_path = f"{mat_path}/BumpTexture"
                            bump_reader = UsdShade.Shader.Define(stage, bump_reader_path)
                            bump_reader.CreateIdAttr("UsdUVTexture")
                            bump_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            bump_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                            bump_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                            bump_output = bump_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                            shader.CreateInput("normal", Sdf.ValueTypeNames.Normal3f).ConnectToSource(bump_output)

                # Roughness
                roughness_set = False
                roughness_prop = fbx_material.FindProperty("ShininessExponent")
                if not roughness_prop.IsValid():
                    roughness_prop = fbx_material.FindProperty("Roughness")

                if roughness_prop.IsValid():
                    texture_count = roughness_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = roughness_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            roughness_reader_path = f"{mat_path}/RoughnessTexture"
                            roughness_reader = UsdShade.Shader.Define(stage, roughness_reader_path)
                            roughness_reader.CreateIdAttr("UsdUVTexture")
                            roughness_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            roughness_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                            roughness_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                            roughness_output = roughness_reader.CreateOutput("r", Sdf.ValueTypeNames.Float)
                            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).ConnectToSource(roughness_output)
                            roughness_set = True

                if not roughness_set and isinstance(fbx_material, FbxSurfacePhong):
                    try:
                        shininess = fbx_material.Shininess.Get()
                        roughness = 1.0 - min(shininess / 100.0, 1.0)
                        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(max(0.0, min(1.0, roughness)))
                        roughness_set = True
                    except:
                        pass

                if not roughness_set:
                    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)

                # Metallic
                metallic_prop = fbx_material.FindProperty("Metallic")
                if metallic_prop.IsValid():
                    texture_count = metallic_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = metallic_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            metallic_reader_path = f"{mat_path}/MetallicTexture"
                            metallic_reader = UsdShade.Shader.Define(stage, metallic_reader_path)
                            metallic_reader.CreateIdAttr("UsdUVTexture")
                            metallic_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            metallic_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                            metallic_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                            metallic_output = metallic_reader.CreateOutput("r", Sdf.ValueTypeNames.Float)
                            shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).ConnectToSource(metallic_output)
                    else:
                        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
                else:
                    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

                # Emissive
                emissive_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sEmissive)
                if emissive_prop.IsValid():
                    texture_count = emissive_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = emissive_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            emissive_reader_path = f"{mat_path}/EmissiveTexture"
                            emissive_reader = UsdShade.Shader.Define(stage, emissive_reader_path)
                            emissive_reader.CreateIdAttr("UsdUVTexture")
                            emissive_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            emissive_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)

                            emissive_output = emissive_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                            shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(emissive_output)

                # Occlusion/AO
                ao_prop = fbx_material.FindProperty("AmbientOcclusion")
                if ao_prop.IsValid():
                    texture_count = ao_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = ao_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            ao_reader_path = f"{mat_path}/OcclusionTexture"
                            ao_reader = UsdShade.Shader.Define(stage, ao_reader_path)
                            ao_reader.CreateIdAttr("UsdUVTexture")
                            ao_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            ao_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                            ao_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                            ao_output = ao_reader.CreateOutput("r", Sdf.ValueTypeNames.Float)
                            shader.CreateInput("occlusion", Sdf.ValueTypeNames.Float).ConnectToSource(ao_output)

                shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
                usd_material.CreateSurfaceOutput().ConnectToSource(shader.GetOutput("surface"))

                UsdShade.MaterialBindingAPI(usd_mesh.GetPrim()).Bind(usd_material)

        # Skinning
        skin = fbx_mesh.GetDeformer(0, FbxDeformer.EDeformerType.eSkin)
        if skin:
            num_verts = fbx_mesh.GetControlPointsCount()
            vert_weights = [[] for _ in range(num_verts)]

            for c in range(skin.GetClusterCount()):
                cluster = skin.GetCluster(c)
                link = cluster.GetLink()

                joint_idx = -1
                for j_idx, j in enumerate(joints):
                    if id(j) == id(link):
                        joint_idx = j_idx
                        break

                if joint_idx == -1:
                    continue

                indices_arr = cluster.GetControlPointIndices()
                weights_arr = cluster.GetControlPointWeights()

                for i in range(cluster.GetControlPointIndicesCount()):
                    v_idx = indices_arr[i]
                    weight = weights_arr[i]
                    if v_idx < num_verts and weight > 0:
                        vert_weights[v_idx].append((joint_idx, weight))

            max_influences = 4
            flat_indices = []
            flat_weights = []

            for weights_list in vert_weights:
                weights_list.sort(key=lambda x: x[1], reverse=True)
                weights_list = weights_list[:max_influences]

                total = sum(w for _, w in weights_list)
                if total > 0:
                    weights_list = [(j, w/total) for j, w in weights_list]

                while len(weights_list) < max_influences:
                    weights_list.append((0, 0.0))

                for j, w in weights_list:
                    flat_indices.append(j)
                    flat_weights.append(w)

            binding_api = UsdSkel.BindingAPI.Apply(usd_mesh.GetPrim())
            binding_api.CreateSkeletonRel().AddTarget(Sdf.Path(skel_path))
            binding_api.CreateGeomBindTransformAttr().Set(Gf.Matrix4d(1.0))

            indices_pv = UsdGeom.Primvar(usd_mesh.GetPrim().CreateAttribute(
                "primvars:skel:jointIndices", Sdf.ValueTypeNames.IntArray, False
            ))
            indices_pv.SetInterpolation(UsdGeom.Tokens.vertex)
            indices_pv.Set(flat_indices)
            indices_pv.SetElementSize(max_influences)

            weights_pv = UsdGeom.Primvar(usd_mesh.GetPrim().CreateAttribute(
                "primvars:skel:jointWeights", Sdf.ValueTypeNames.FloatArray, False
            ))
            weights_pv.SetInterpolation(UsdGeom.Tokens.vertex)
            weights_pv.Set(flat_weights)
            weights_pv.SetElementSize(max_influences)


def export_meshes_no_skeleton(stage, geom_path, model_name, scene, mesh_nodes, include_materials=True, textures_subdir=None):
    """Export all meshes to the stage without skeleton/skinning data.

    This is a separate code path for models without skeletons.
    If textures_subdir is provided, texture references will be prefixed with that subdirectory.
    """
    UsdGeom.Scope.Define(stage, geom_path)

    for mesh_node in mesh_nodes:
        fbx_mesh = mesh_node.GetMesh()
        mesh_name = make_valid_identifier(mesh_node.GetName())
        mesh_path = f"{geom_path}/{mesh_name}"
        usd_mesh = UsdGeom.Mesh.Define(stage, mesh_path)

        # Disable subdivision - keep as polygonal mesh
        usd_mesh.CreateSubdivisionSchemeAttr().Set("none")

        # Vertices
        verts = []
        for i in range(fbx_mesh.GetControlPointsCount()):
            pt = fbx_mesh.GetControlPoints()[i]
            verts.append(Gf.Vec3f(pt[0], pt[1], pt[2]))
        usd_mesh.CreatePointsAttr().Set(verts)

        # Faces
        counts = []
        indices = []
        for p in range(fbx_mesh.GetPolygonCount()):
            size = fbx_mesh.GetPolygonSize(p)
            counts.append(size)
            for v in range(size):
                indices.append(fbx_mesh.GetPolygonVertex(p, v))

        usd_mesh.CreateFaceVertexCountsAttr().Set(counts)
        usd_mesh.CreateFaceVertexIndicesAttr().Set(indices)

        # Normals
        normal_elem = fbx_mesh.GetElementNormal()
        if normal_elem:
            normals = []
            for p in range(fbx_mesh.GetPolygonCount()):
                for v in range(fbx_mesh.GetPolygonSize(p)):
                    idx = p * fbx_mesh.GetPolygonSize(p) + v
                    if normal_elem.GetReferenceMode() == FbxLayerElement.EReferenceMode.eDirect:
                        n = normal_elem.GetDirectArray().GetAt(idx)
                    else:
                        i = normal_elem.GetIndexArray().GetAt(idx)
                        n = normal_elem.GetDirectArray().GetAt(i)
                    normals.append(Gf.Vec3f(n[0], n[1], n[2]))

            if normals:
                usd_mesh.CreateNormalsAttr().Set(normals)
                usd_mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)

        # UVs
        uv_set_count = fbx_mesh.GetElementUVCount()
        primvar_api = UsdGeom.PrimvarsAPI(usd_mesh.GetPrim())

        for uv_index in range(uv_set_count):
            uv_elem = fbx_mesh.GetElementUV(uv_index)
            if uv_elem:
                uvs = []
                mapping_mode = uv_elem.GetMappingMode()
                reference_mode = uv_elem.GetReferenceMode()

                polygon_vertex_index = 0

                for p in range(fbx_mesh.GetPolygonCount()):
                    for v in range(fbx_mesh.GetPolygonSize(p)):
                        uv_index_to_use = 0

                        if mapping_mode == FbxLayerElement.EMappingMode.eByControlPoint:
                            uv_index_to_use = fbx_mesh.GetPolygonVertex(p, v)
                        elif mapping_mode == FbxLayerElement.EMappingMode.eByPolygonVertex:
                            uv_index_to_use = polygon_vertex_index
                        elif mapping_mode == FbxLayerElement.EMappingMode.eByPolygon:
                            uv_index_to_use = p
                        else:
                            uv_index_to_use = polygon_vertex_index

                        if reference_mode == FbxLayerElement.EReferenceMode.eDirect:
                            uv = uv_elem.GetDirectArray().GetAt(uv_index_to_use)
                        else:
                            uv_ref_index = uv_elem.GetIndexArray().GetAt(uv_index_to_use)
                            uv = uv_elem.GetDirectArray().GetAt(uv_ref_index)

                        uvs.append(Gf.Vec2f(uv[0], uv[1]))
                        polygon_vertex_index += 1

                if uvs:
                    uv_set_name = uv_elem.GetName()
                    if uv_index == 0:
                        primvar_name = "st"
                    elif uv_set_name:
                        primvar_name = f"st_{make_valid_identifier(uv_set_name)}"
                    else:
                        primvar_name = f"st{uv_index}"

                    st_primvar = primvar_api.CreatePrimvar(primvar_name, Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.faceVarying)
                    st_primvar.Set(uvs)

        # Materials
        material_elem = fbx_mesh.GetElementMaterial()
        if include_materials and material_elem and mesh_node.GetMaterialCount() > 0:
            fbx_material = mesh_node.GetMaterial(0)
            if fbx_material:
                mat_name = make_valid_identifier(fbx_material.GetName())
                mat_path = f"/{model_name}/Materials/{mat_name}"

                materials_scope_path = f"/{model_name}/Materials"
                if not stage.GetPrimAtPath(materials_scope_path):
                    UsdGeom.Scope.Define(stage, materials_scope_path)

                usd_material = UsdShade.Material.Define(stage, mat_path)

                shader_path = f"{mat_path}/PreviewSurface"
                shader = UsdShade.Shader.Define(stage, shader_path)
                shader.CreateIdAttr("UsdPreviewSurface")

                primvar_reader_path = f"{mat_path}/PrimvarReader"
                primvar_reader = UsdShade.Shader.Define(stage, primvar_reader_path)
                primvar_reader.CreateIdAttr("UsdPrimvarReader_float2")
                primvar_reader.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")
                st_output = primvar_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

                diffuse_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sDiffuse)
                if diffuse_prop.IsValid():
                    texture_count = diffuse_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = diffuse_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            tex_reader_path = f"{mat_path}/DiffuseTexture"
                            tex_reader = UsdShade.Shader.Define(stage, tex_reader_path)
                            tex_reader.CreateIdAttr("UsdUVTexture")
                            tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            tex_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)

                            diffuse_output = tex_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(diffuse_output)
                    else:
                        if isinstance(fbx_material, FbxSurfaceLambert):
                            diffuse_color = fbx_material.Diffuse.Get()
                            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
                                Gf.Vec3f(diffuse_color[0], diffuse_color[1], diffuse_color[2])
                            )

                # Normal map
                normal_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sNormalMap)
                if normal_prop.IsValid():
                    texture_count = normal_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = normal_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            normal_reader_path = f"{mat_path}/NormalTexture"
                            normal_reader = UsdShade.Shader.Define(stage, normal_reader_path)
                            normal_reader.CreateIdAttr("UsdUVTexture")
                            normal_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            normal_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                            normal_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                            normal_output = normal_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                            shader.CreateInput("normal", Sdf.ValueTypeNames.Normal3f).ConnectToSource(normal_output)

                # Bump map fallback
                bump_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sBump)
                if bump_prop.IsValid() and not normal_prop.IsValid():
                    texture_count = bump_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = bump_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            bump_reader_path = f"{mat_path}/BumpTexture"
                            bump_reader = UsdShade.Shader.Define(stage, bump_reader_path)
                            bump_reader.CreateIdAttr("UsdUVTexture")
                            bump_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            bump_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                            bump_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                            bump_output = bump_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                            shader.CreateInput("normal", Sdf.ValueTypeNames.Normal3f).ConnectToSource(bump_output)

                # Roughness
                roughness_set = False
                roughness_prop = fbx_material.FindProperty("ShininessExponent")
                if not roughness_prop.IsValid():
                    roughness_prop = fbx_material.FindProperty("Roughness")

                if roughness_prop.IsValid():
                    texture_count = roughness_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = roughness_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            roughness_reader_path = f"{mat_path}/RoughnessTexture"
                            roughness_reader = UsdShade.Shader.Define(stage, roughness_reader_path)
                            roughness_reader.CreateIdAttr("UsdUVTexture")
                            roughness_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            roughness_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                            roughness_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                            roughness_output = roughness_reader.CreateOutput("r", Sdf.ValueTypeNames.Float)
                            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).ConnectToSource(roughness_output)
                            roughness_set = True

                if not roughness_set and isinstance(fbx_material, FbxSurfacePhong):
                    try:
                        shininess = fbx_material.Shininess.Get()
                        roughness = 1.0 - min(shininess / 100.0, 1.0)
                        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(max(0.0, min(1.0, roughness)))
                        roughness_set = True
                    except:
                        pass

                if not roughness_set:
                    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)

                # Metallic
                metallic_prop = fbx_material.FindProperty("Metallic")
                if metallic_prop.IsValid():
                    texture_count = metallic_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = metallic_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            metallic_reader_path = f"{mat_path}/MetallicTexture"
                            metallic_reader = UsdShade.Shader.Define(stage, metallic_reader_path)
                            metallic_reader.CreateIdAttr("UsdUVTexture")
                            metallic_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            metallic_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                            metallic_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                            metallic_output = metallic_reader.CreateOutput("r", Sdf.ValueTypeNames.Float)
                            shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).ConnectToSource(metallic_output)
                    else:
                        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
                else:
                    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

                # Emissive
                emissive_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sEmissive)
                if emissive_prop.IsValid():
                    texture_count = emissive_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = emissive_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            emissive_reader_path = f"{mat_path}/EmissiveTexture"
                            emissive_reader = UsdShade.Shader.Define(stage, emissive_reader_path)
                            emissive_reader.CreateIdAttr("UsdUVTexture")
                            emissive_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            emissive_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)

                            emissive_output = emissive_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                            shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(emissive_output)

                # Occlusion/AO
                ao_prop = fbx_material.FindProperty("AmbientOcclusion")
                if ao_prop.IsValid():
                    texture_count = ao_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = ao_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            ao_reader_path = f"{mat_path}/OcclusionTexture"
                            ao_reader = UsdShade.Shader.Define(stage, ao_reader_path)
                            ao_reader.CreateIdAttr("UsdUVTexture")
                            ao_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            ao_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                            ao_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                            ao_output = ao_reader.CreateOutput("r", Sdf.ValueTypeNames.Float)
                            shader.CreateInput("occlusion", Sdf.ValueTypeNames.Float).ConnectToSource(ao_output)

                shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
                usd_material.CreateSurfaceOutput().ConnectToSource(shader.GetOutput("surface"))

                UsdShade.MaterialBindingAPI(usd_mesh.GetPrim()).Bind(usd_material)

        # No skinning for non-skeletal meshes


def export_transform_animation(stage, mesh_path, scene, mesh_node, clips_info, fps):
    """Export transform animation for a mesh node (translation, rotation, scale).

    This samples the mesh node's local transform at each frame and writes
    time-sampled USD xform operations.
    """
    mesh_prim = stage.GetPrimAtPath(mesh_path)
    if not mesh_prim:
        return

    xform = UsdGeom.Xform(mesh_prim)
    anim_evaluator = scene.GetAnimationEvaluator()

    # Clear any existing xform ops and set up new ones
    xform.ClearXformOpOrder()
    translate_op = xform.AddTranslateOp()
    orient_op = xform.AddOrientOp()
    scale_op = xform.AddScaleOp()

    # Export all clips concatenated
    for clip_info in clips_info:
        scene.SetCurrentAnimationStack(clip_info['stack'])
        time_span = clip_info['stack'].GetLocalTimeSpan()
        start_time = time_span.GetStart().GetSecondDouble()

        local_frames = clip_info['end_frame'] - clip_info['start_frame'] + 1

        for local_frame in range(local_frames):
            time = local_frame / fps + start_time
            fbx_time = FbxTime()
            fbx_time.SetSecondDouble(time)

            # Get the local transform at this time
            fbx_matrix = anim_evaluator.GetNodeLocalTransform(mesh_node, fbx_time)

            # Extract translation
            translation = fbx_matrix.GetT()
            trans_vec = Gf.Vec3d(translation[0], translation[1], translation[2])

            # Extract rotation as quaternion
            q = fbx_matrix.GetQ()
            quat = Gf.Quatf(float(q[3]), float(q[0]), float(q[1]), float(q[2]))

            # Extract scale
            scale = fbx_matrix.GetS()
            scale_vec = Gf.Vec3f(scale[0], scale[1], scale[2])

            # Write at global frame offset
            global_frame = clip_info['start_frame'] + local_frame
            translate_op.Set(trans_vec, Usd.TimeCode(global_frame))
            orient_op.Set(quat, Usd.TimeCode(global_frame))
            scale_op.Set(scale_vec, Usd.TimeCode(global_frame))


def export_transform_animation_single(stage, mesh_path, scene, mesh_node, clip_info, fps):
    """Export transform animation for a single clip (for separate animation files).

    Similar to export_transform_animation but for a single clip starting at frame 0.
    """
    mesh_prim = stage.GetPrimAtPath(mesh_path)
    if not mesh_prim:
        return

    xform = UsdGeom.Xform(mesh_prim)
    anim_evaluator = scene.GetAnimationEvaluator()

    # Clear any existing xform ops and set up new ones
    xform.ClearXformOpOrder()
    translate_op = xform.AddTranslateOp()
    orient_op = xform.AddOrientOp()
    scale_op = xform.AddScaleOp()

    scene.SetCurrentAnimationStack(clip_info['stack'])
    time_span = clip_info['stack'].GetLocalTimeSpan()
    start_time = time_span.GetStart().GetSecondDouble()

    local_frames = clip_info['end_frame'] - clip_info['start_frame'] + 1

    for local_frame in range(local_frames):
        time = local_frame / fps + start_time
        fbx_time = FbxTime()
        fbx_time.SetSecondDouble(time)

        # Get the local transform at this time
        fbx_matrix = anim_evaluator.GetNodeLocalTransform(mesh_node, fbx_time)

        # Extract translation
        translation = fbx_matrix.GetT()
        trans_vec = Gf.Vec3d(translation[0], translation[1], translation[2])

        # Extract rotation as quaternion
        q = fbx_matrix.GetQ()
        quat = Gf.Quatf(float(q[3]), float(q[0]), float(q[1]), float(q[2]))

        # Extract scale
        scale = fbx_matrix.GetS()
        scale_vec = Gf.Vec3f(scale[0], scale[1], scale[2])

        # Write at local frame (starting from 0)
        translate_op.Set(trans_vec, Usd.TimeCode(local_frame))
        orient_op.Set(quat, Usd.TimeCode(local_frame))
        scale_op.Set(scale_vec, Usd.TimeCode(local_frame))


def export_materials_only(stage, materials_scope_path, model_name, scene, mesh_nodes, textures_subdir=None):
    """Export only materials to a stage (for separate materials file).
    If textures_subdir is provided, texture references will be prefixed with that subdirectory."""
    for mesh_node in mesh_nodes:
        fbx_mesh = mesh_node.GetMesh()
        material_elem = fbx_mesh.GetElementMaterial()
        if material_elem and mesh_node.GetMaterialCount() > 0:
            fbx_material = mesh_node.GetMaterial(0)
            if fbx_material:
                mat_name = make_valid_identifier(fbx_material.GetName())
                mat_path = f"{materials_scope_path}/{mat_name}"

                # Skip if already created
                if stage.GetPrimAtPath(mat_path):
                    continue

                usd_material = UsdShade.Material.Define(stage, mat_path)

                shader_path = f"{mat_path}/PreviewSurface"
                shader = UsdShade.Shader.Define(stage, shader_path)
                shader.CreateIdAttr("UsdPreviewSurface")

                primvar_reader_path = f"{mat_path}/PrimvarReader"
                primvar_reader = UsdShade.Shader.Define(stage, primvar_reader_path)
                primvar_reader.CreateIdAttr("UsdPrimvarReader_float2")
                primvar_reader.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")
                st_output = primvar_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

                diffuse_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sDiffuse)
                if diffuse_prop.IsValid():
                    texture_count = diffuse_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = diffuse_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            tex_reader_path = f"{mat_path}/DiffuseTexture"
                            tex_reader = UsdShade.Shader.Define(stage, tex_reader_path)
                            tex_reader.CreateIdAttr("UsdUVTexture")
                            tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            tex_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)

                            diffuse_output = tex_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(diffuse_output)
                    else:
                        if isinstance(fbx_material, FbxSurfaceLambert):
                            diffuse_color = fbx_material.Diffuse.Get()
                            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(
                                Gf.Vec3f(diffuse_color[0], diffuse_color[1], diffuse_color[2])
                            )

                # Normal map
                normal_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sNormalMap)
                if normal_prop.IsValid():
                    texture_count = normal_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = normal_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            normal_reader_path = f"{mat_path}/NormalTexture"
                            normal_reader = UsdShade.Shader.Define(stage, normal_reader_path)
                            normal_reader.CreateIdAttr("UsdUVTexture")
                            normal_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            normal_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                            normal_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                            normal_output = normal_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                            shader.CreateInput("normal", Sdf.ValueTypeNames.Normal3f).ConnectToSource(normal_output)

                # Roughness
                roughness_set = False
                roughness_prop = fbx_material.FindProperty("ShininessExponent")
                if not roughness_prop.IsValid():
                    roughness_prop = fbx_material.FindProperty("Roughness")

                if roughness_prop.IsValid():
                    texture_count = roughness_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = roughness_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            roughness_reader_path = f"{mat_path}/RoughnessTexture"
                            roughness_reader = UsdShade.Shader.Define(stage, roughness_reader_path)
                            roughness_reader.CreateIdAttr("UsdUVTexture")
                            roughness_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            roughness_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                            roughness_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                            roughness_output = roughness_reader.CreateOutput("r", Sdf.ValueTypeNames.Float)
                            shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).ConnectToSource(roughness_output)
                            roughness_set = True

                if not roughness_set and isinstance(fbx_material, FbxSurfacePhong):
                    try:
                        shininess = fbx_material.Shininess.Get()
                        roughness = 1.0 - min(shininess / 100.0, 1.0)
                        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(max(0.0, min(1.0, roughness)))
                        roughness_set = True
                    except:
                        pass

                if not roughness_set:
                    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)

                # Metallic
                metallic_prop = fbx_material.FindProperty("Metallic")
                if metallic_prop.IsValid():
                    texture_count = metallic_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = metallic_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            metallic_reader_path = f"{mat_path}/MetallicTexture"
                            metallic_reader = UsdShade.Shader.Define(stage, metallic_reader_path)
                            metallic_reader.CreateIdAttr("UsdUVTexture")
                            metallic_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            metallic_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                            metallic_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                            metallic_output = metallic_reader.CreateOutput("r", Sdf.ValueTypeNames.Float)
                            shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).ConnectToSource(metallic_output)
                    else:
                        shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
                else:
                    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

                # Emissive
                emissive_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sEmissive)
                if emissive_prop.IsValid():
                    texture_count = emissive_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = emissive_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            emissive_reader_path = f"{mat_path}/EmissiveTexture"
                            emissive_reader = UsdShade.Shader.Define(stage, emissive_reader_path)
                            emissive_reader.CreateIdAttr("UsdUVTexture")
                            emissive_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            emissive_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)

                            emissive_output = emissive_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
                            shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(emissive_output)

                # Occlusion/AO
                ao_prop = fbx_material.FindProperty("AmbientOcclusion")
                if ao_prop.IsValid():
                    texture_count = ao_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = ao_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            ao_reader_path = f"{mat_path}/OcclusionTexture"
                            ao_reader = UsdShade.Shader.Define(stage, ao_reader_path)
                            ao_reader.CreateIdAttr("UsdUVTexture")
                            ao_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            ao_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_output)
                            ao_reader.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("raw")

                            ao_output = ao_reader.CreateOutput("r", Sdf.ValueTypeNames.Float)
                            shader.CreateInput("occlusion", Sdf.ValueTypeNames.Float).ConnectToSource(ao_output)

                shader.CreateOutput("surface", Sdf.ValueTypeNames.Token)
                usd_material.CreateSurfaceOutput().ConnectToSource(shader.GetOutput("surface"))


def export_materials_materialx(stage, materials_scope_path, model_name, scene, mesh_nodes, textures_subdir=None):
    """Export materials using MaterialX shaders for Reality Composer Pro.
    If textures_subdir is provided, texture references will be prefixed with that subdirectory."""
    for mesh_node in mesh_nodes:
        fbx_mesh = mesh_node.GetMesh()
        material_elem = fbx_mesh.GetElementMaterial()
        if material_elem and mesh_node.GetMaterialCount() > 0:
            fbx_material = mesh_node.GetMaterial(0)
            if fbx_material:
                mat_name = make_valid_identifier(fbx_material.GetName())
                mat_path = f"{materials_scope_path}/{mat_name}"

                # Skip if already created
                if stage.GetPrimAtPath(mat_path):
                    continue

                usd_material = UsdShade.Material.Define(stage, mat_path)

                # Create PBR surface shader
                pbr_path = f"{mat_path}/PBRSurface"
                pbr_shader = UsdShade.Shader.Define(stage, pbr_path)
                pbr_shader.CreateIdAttr("ND_realitykit_pbr_surfaceshader")

                # Create outputs
                pbr_output = pbr_shader.CreateOutput("out", Sdf.ValueTypeNames.Token)

                # Connect material to PBR shader
                mtlx_output = usd_material.CreateOutput("mtlx:surface", Sdf.ValueTypeNames.Token)
                mtlx_output.ConnectToSource(pbr_output)

                # Also create realitykit:vertex output (empty, but RCP expects it)
                usd_material.CreateOutput("realitykit:vertex", Sdf.ValueTypeNames.Token)

                # Diffuse/Base Color
                diffuse_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sDiffuse)
                if diffuse_prop.IsValid():
                    texture_count = diffuse_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = diffuse_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            tex_path = f"{mat_path}/DiffuseTexture"
                            tex_shader = UsdShade.Shader.Define(stage, tex_path)
                            tex_shader.CreateIdAttr("ND_RealityKitTexture2D_color3")
                            tex_shader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            tex_shader.CreateInput("no_flip_v", Sdf.ValueTypeNames.Bool).Set(True)
                            tex_output = tex_shader.CreateOutput("out", Sdf.ValueTypeNames.Color3f)

                            base_color_input = pbr_shader.CreateInput("baseColor", Sdf.ValueTypeNames.Color3f)
                            base_color_input.ConnectToSource(tex_output)
                    else:
                        if isinstance(fbx_material, FbxSurfaceLambert):
                            diffuse_color = fbx_material.Diffuse.Get()
                            pbr_shader.CreateInput("baseColor", Sdf.ValueTypeNames.Color3f).Set(
                                Gf.Vec3f(diffuse_color[0], diffuse_color[1], diffuse_color[2])
                            )

                # Normal map (requires decode node)
                normal_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sNormalMap)
                if normal_prop.IsValid():
                    texture_count = normal_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = normal_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            # Create normal texture node
                            normal_tex_path = f"{mat_path}/NormalTexture"
                            normal_tex = UsdShade.Shader.Define(stage, normal_tex_path)
                            normal_tex.CreateIdAttr("ND_RealityKitTexture2D_color3")
                            normal_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            normal_tex.CreateInput("no_flip_v", Sdf.ValueTypeNames.Bool).Set(True)
                            normal_tex_output = normal_tex.CreateOutput("out", Sdf.ValueTypeNames.Color3f)

                            # Create normal map decode node
                            decode_path = f"{mat_path}/NormalMapDecode"
                            decode_shader = UsdShade.Shader.Define(stage, decode_path)
                            decode_shader.CreateIdAttr("ND_normal_map_decode")
                            decode_input = decode_shader.CreateInput("in", Sdf.ValueTypeNames.Float3)
                            decode_input.ConnectToSource(normal_tex_output)
                            decode_output = decode_shader.CreateOutput("out", Sdf.ValueTypeNames.Float3)

                            # Connect to PBR shader
                            normal_input = pbr_shader.CreateInput("normal", Sdf.ValueTypeNames.Float3)
                            normal_input.ConnectToSource(decode_output)

                # Roughness
                roughness_set = False
                roughness_prop = fbx_material.FindProperty("ShininessExponent")
                if not roughness_prop.IsValid():
                    roughness_prop = fbx_material.FindProperty("Roughness")

                if roughness_prop.IsValid():
                    texture_count = roughness_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = roughness_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            roughness_tex_path = f"{mat_path}/RoughnessTexture"
                            roughness_tex = UsdShade.Shader.Define(stage, roughness_tex_path)
                            roughness_tex.CreateIdAttr("ND_RealityKitTexture2D_float")
                            roughness_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            roughness_tex.CreateInput("no_flip_v", Sdf.ValueTypeNames.Bool).Set(True)
                            roughness_tex_output = roughness_tex.CreateOutput("out", Sdf.ValueTypeNames.Float)

                            roughness_input = pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float)
                            roughness_input.ConnectToSource(roughness_tex_output)
                            roughness_set = True

                if not roughness_set and isinstance(fbx_material, FbxSurfacePhong):
                    try:
                        shininess = fbx_material.Shininess.Get()
                        roughness = 1.0 - min(shininess / 100.0, 1.0)
                        pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(max(0.0, min(1.0, roughness)))
                        roughness_set = True
                    except:
                        pass

                if not roughness_set:
                    pbr_shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.5)

                # Metallic
                metallic_prop = fbx_material.FindProperty("Metallic")
                if metallic_prop.IsValid():
                    texture_count = metallic_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = metallic_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            metallic_tex_path = f"{mat_path}/MetallicTexture"
                            metallic_tex = UsdShade.Shader.Define(stage, metallic_tex_path)
                            metallic_tex.CreateIdAttr("ND_RealityKitTexture2D_float")
                            metallic_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            metallic_tex.CreateInput("no_flip_v", Sdf.ValueTypeNames.Bool).Set(True)
                            metallic_tex_output = metallic_tex.CreateOutput("out", Sdf.ValueTypeNames.Float)

                            metallic_input = pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float)
                            metallic_input.ConnectToSource(metallic_tex_output)
                    else:
                        pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
                else:
                    pbr_shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)

                # Emissive
                emissive_prop = fbx_material.FindProperty(FbxSurfaceMaterial.sEmissive)
                if emissive_prop.IsValid():
                    texture_count = emissive_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = emissive_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            emissive_tex_path = f"{mat_path}/EmissiveTexture"
                            emissive_tex = UsdShade.Shader.Define(stage, emissive_tex_path)
                            emissive_tex.CreateIdAttr("ND_RealityKitTexture2D_color3")
                            emissive_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            emissive_tex.CreateInput("no_flip_v", Sdf.ValueTypeNames.Bool).Set(True)
                            emissive_tex_output = emissive_tex.CreateOutput("out", Sdf.ValueTypeNames.Color3f)

                            emissive_input = pbr_shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f)
                            emissive_input.ConnectToSource(emissive_tex_output)

                # Ambient Occlusion
                ao_prop = fbx_material.FindProperty("AmbientOcclusion")
                if ao_prop.IsValid():
                    texture_count = ao_prop.GetSrcObjectCount()
                    if texture_count > 0:
                        fbx_texture = ao_prop.GetSrcObject(0)
                        if isinstance(fbx_texture, FbxFileTexture):
                            texture_path = fbx_texture.GetFileName()
                            texture_name = os.path.basename(texture_path)
                            texture_ref = f"{textures_subdir}/{texture_name}" if textures_subdir else texture_name

                            ao_tex_path = f"{mat_path}/OcclusionTexture"
                            ao_tex = UsdShade.Shader.Define(stage, ao_tex_path)
                            ao_tex.CreateIdAttr("ND_RealityKitTexture2D_float")
                            ao_tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_ref)
                            ao_tex.CreateInput("no_flip_v", Sdf.ValueTypeNames.Bool).Set(True)
                            ao_tex_output = ao_tex.CreateOutput("out", Sdf.ValueTypeNames.Float)

                            ao_input = pbr_shader.CreateInput("ambientOcclusion", Sdf.ValueTypeNames.Float)
                            ao_input.ConnectToSource(ao_tex_output)


def bind_materials_from_reference(stage, geom_path, materials_path, scene, mesh_nodes):
    """Bind materials to meshes when materials are referenced from another file"""
    for mesh_node in mesh_nodes:
        fbx_mesh = mesh_node.GetMesh()
        mesh_name = make_valid_identifier(mesh_node.GetName())
        mesh_path = f"{geom_path}/{mesh_name}"

        material_elem = fbx_mesh.GetElementMaterial()
        if material_elem and mesh_node.GetMaterialCount() > 0:
            fbx_material = mesh_node.GetMaterial(0)
            if fbx_material:
                mat_name = make_valid_identifier(fbx_material.GetName())
                mat_path = f"{materials_path}/{mat_name}"

                mesh_prim = stage.GetPrimAtPath(mesh_path)
                if mesh_prim:
                    usd_material = UsdShade.Material.Get(stage, mat_path)
                    if usd_material:
                        UsdShade.MaterialBindingAPI(mesh_prim).Bind(usd_material)


def convert_fbx_to_usd_separate(fbx_path, usd_path, use_materialx=False, use_directory_structure=False):
    """Export FBX as separate USD files: main model, per-animation files, and parent file"""

    # Parse output path
    base_name = os.path.splitext(os.path.basename(usd_path))[0]
    ext = os.path.splitext(usd_path)[1] or '.usda'

    if use_directory_structure:
        # Create organized directory structure
        parent_dir = os.path.dirname(usd_path) or '.'
        output_dir = os.path.join(parent_dir, base_name)
        animations_dir = os.path.join(output_dir, "Animations")
        textures_dir = os.path.join(output_dir, "Textures")
        textures_subdir = "Textures"
        animations_subdir = "Animations"
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(animations_dir, exist_ok=True)
        os.makedirs(textures_dir, exist_ok=True)
    else:
        # Flat structure (original behavior)
        output_dir = os.path.dirname(usd_path)
        animations_dir = output_dir
        textures_dir = output_dir
        textures_subdir = None
        animations_subdir = None
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

    # Load FBX scene
    manager, scene = load_fbx_scene(fbx_path)

    # Get model name from FBX
    model_name = make_valid_identifier(os.path.splitext(os.path.basename(fbx_path))[0])

    # Get FPS
    time_mode = FbxTime.GetGlobalTimeMode()
    fps = FbxTime.GetFrameRate(time_mode)

    # Get animation stacks
    anim_stacks = []
    count = scene.GetSrcObjectCount(FbxCriteria.ObjectType(FbxAnimStack.ClassId))
    for i in range(count):
        anim_stacks.append(scene.GetSrcObject(FbxCriteria.ObjectType(FbxAnimStack.ClassId), i))

    print(f"Found {len(anim_stacks)} animation takes")
    for stack in anim_stacks:
        print(f"  - {stack.GetName()}")

    # Find skeleton
    skel_root_joint = find_skeleton_root_node(scene)
    if not skel_root_joint:
        # No skeleton found - delegate to non-skeletal code path
        print("No skeleton found - using non-skeletal export path")
        manager.Destroy()
        return convert_fbx_to_usd_separate_no_skeleton(fbx_path, usd_path, use_materialx, use_directory_structure)

    # Collect joints
    joints, joint_paths = collect_joints(skel_root_joint)
    print(f"Found {len(joints)} joints")

    # Get rest transforms
    rest_transforms = []
    for joint in joints:
        local_mat = gf_matrix_from_fbx(joint.EvaluateLocalTransform())
        rest_transforms.append(local_mat)

    # Get bind transforms
    bind_transforms = get_bind_transforms(scene, joints, rest_transforms)

    # Find meshes
    mesh_nodes = find_mesh_nodes(scene)
    print(f"Found {len(mesh_nodes)} mesh(es)")

    # Calculate clip info for each animation
    clips_info = []
    for stack in anim_stacks:
        scene.SetCurrentAnimationStack(stack)
        time_span = stack.GetLocalTimeSpan()
        start_time = time_span.GetStart().GetSecondDouble()
        stop_time = time_span.GetStop().GetSecondDouble()
        frames_count = int((stop_time - start_time) * fps + 0.5) + 1

        clips_info.append({
            'name': make_valid_identifier(stack.GetName()),
            'original_name': stack.GetName(),
            'start_frame': 0,
            'end_frame': frames_count - 1,
            'stack': stack
        })

    # --- 0. Export Materials to separate file ---
    materials_usd_path = os.path.join(output_dir, f"{base_name}-Materials{ext}") if output_dir else f"{base_name}-Materials{ext}"
    materials_file_basename = os.path.basename(materials_usd_path)

    materials_stage = Usd.Stage.CreateNew(materials_usd_path)
    UsdGeom.SetStageUpAxis(materials_stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(materials_stage, 1.0)

    # Create Materials scope as default prim
    materials_scope = UsdGeom.Scope.Define(materials_stage, "/Materials")
    materials_stage.SetDefaultPrim(materials_scope.GetPrim())

    # Export materials to this stage
    if use_materialx:
        export_materials_materialx(materials_stage, "/Materials", model_name, scene, mesh_nodes, textures_subdir=textures_subdir)
    else:
        export_materials_only(materials_stage, "/Materials", model_name, scene, mesh_nodes, textures_subdir=textures_subdir)

    materials_stage.GetRootLayer().Save()
    print(f"✓ Saved materials: {materials_usd_path}")

    # --- 1. Export Main Model (no animation) ---
    main_usd_path = os.path.join(output_dir, f"{base_name}{ext}") if output_dir else f"{base_name}{ext}"

    main_stage = Usd.Stage.CreateNew(main_usd_path)
    UsdGeom.SetStageUpAxis(main_stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(main_stage, 1.0)

    # Create hierarchy
    root_xform = UsdGeom.Xform.Define(main_stage, f"/{model_name}")
    main_stage.SetDefaultPrim(root_xform.GetPrim())

    skel_root_path = f"/{model_name}/Root"
    UsdSkel.Root.Define(main_stage, skel_root_path)

    skel_path = f"{skel_root_path}/Skeleton"
    skel, joint_names, _ = export_skeleton(main_stage, skel_path, joints, joint_paths, bind_transforms)

    # Export meshes (without materials - they're in separate file)
    geom_path = f"{skel_root_path}/Geom"
    export_meshes(main_stage, geom_path, skel_path, model_name, scene, mesh_nodes, joints, include_materials=False)

    # Reference materials from separate file
    main_materials_path = f"/{model_name}/Materials"
    main_materials_prim = main_stage.DefinePrim(main_materials_path)
    main_materials_prim.GetReferences().AddReference(f"./{materials_file_basename}", "/Materials")

    # Bind materials to meshes
    bind_materials_from_reference(main_stage, geom_path, main_materials_path, scene, mesh_nodes)

    # Note: We save main_stage after adding AnimationLibrary (below)

    # --- 2. Export Each Animation Take ---
    anim_files = []
    for clip_info in clips_info:
        take_name = clip_info['name']
        anim_usd_path = os.path.join(animations_dir, f"{base_name}-{take_name}{ext}") if animations_dir else f"{base_name}-{take_name}{ext}"
        anim_files.append((take_name, os.path.basename(anim_usd_path)))

        anim_stage = Usd.Stage.CreateNew(anim_usd_path)
        UsdGeom.SetStageUpAxis(anim_stage, UsdGeom.Tokens.y)
        UsdGeom.SetStageMetersPerUnit(anim_stage, 1.0)

        # Set time range for this animation
        anim_stage.SetStartTimeCode(0)
        anim_stage.SetEndTimeCode(clip_info['end_frame'])
        anim_stage.SetTimeCodesPerSecond(fps)

        # Create hierarchy
        anim_root_xform = UsdGeom.Xform.Define(anim_stage, f"/{model_name}")
        anim_stage.SetDefaultPrim(anim_root_xform.GetPrim())

        anim_skel_root_path = f"/{model_name}/Root"
        UsdSkel.Root.Define(anim_stage, anim_skel_root_path)

        anim_skel_path = f"{anim_skel_root_path}/Skeleton"
        anim_skel, anim_joint_names, _ = export_skeleton(anim_stage, anim_skel_path, joints, joint_paths, bind_transforms)

        # Export animation
        anim_prim_path = f"{anim_skel_path}/Animation"
        export_animation(anim_stage, anim_prim_path, anim_skel_path, anim_skel_root_path, scene, joints, anim_joint_names, clip_info, fps)

        # Reference mesh from main file and materials from materials file
        main_file_basename = os.path.basename(main_usd_path)
        # Use ../ prefix if animation is in subdirectory
        ref_prefix = "../" if animations_subdir else "./"

        # Reference Geom (mesh)
        anim_geom_path = f"{anim_skel_root_path}/Geom"
        geom_prim = anim_stage.DefinePrim(anim_geom_path)
        geom_prim.GetReferences().AddReference(f"{ref_prefix}{main_file_basename}", f"/{model_name}/Root/Geom")

        # Reference Materials from materials file
        anim_materials_path = f"/{model_name}/Materials"
        materials_prim = anim_stage.DefinePrim(anim_materials_path)
        materials_prim.GetReferences().AddReference(f"{ref_prefix}{materials_file_basename}", "/Materials")

        # Override material bindings on the referenced mesh to use local materials path
        # This is needed because the main file's mesh binds to its own materials path,
        # but we need to rebind to this file's materials path
        for mesh_node in mesh_nodes:
            fbx_mesh = mesh_node.GetMesh()
            mesh_name = make_valid_identifier(mesh_node.GetName())
            mesh_path = f"{anim_geom_path}/{mesh_name}"

            material_elem = fbx_mesh.GetElementMaterial()
            if material_elem and mesh_node.GetMaterialCount() > 0:
                fbx_material = mesh_node.GetMaterial(0)
                if fbx_material:
                    mat_name = make_valid_identifier(fbx_material.GetName())
                    mat_path = f"{anim_materials_path}/{mat_name}"

                    mesh_prim = anim_stage.GetPrimAtPath(mesh_path)
                    if mesh_prim:
                        usd_material = UsdShade.Material.Get(anim_stage, mat_path)
                        if usd_material:
                            UsdShade.MaterialBindingAPI(mesh_prim).Bind(usd_material)

        anim_stage.GetRootLayer().Save()
        print(f"✓ Saved animation: {anim_usd_path}")

    # --- 3. Add AnimationLibrary to main model file and save ---
    if anim_files:
        anim_lib_path = f"/{model_name}/AnimationLibrary"
        anim_lib_prim = main_stage.DefinePrim(anim_lib_path, "RealityKitComponent")

        info_id_attr = anim_lib_prim.CreateAttribute(
            "info:id", Sdf.ValueTypeNames.Token, custom=True
        )
        info_id_attr.Set("RealityKit.AnimationLibrary")

        for take_name, anim_filename in anim_files:
            anim_file_prim_path = f"{anim_lib_path}/{take_name}"
            anim_file_prim = main_stage.DefinePrim(anim_file_prim_path, "RealityKitAnimationFile")

            file_attr = anim_file_prim.CreateAttribute("file", Sdf.ValueTypeNames.Asset, custom=True)
            # Use Animations/ subdirectory if directory structure is enabled
            anim_ref = f"./{animations_subdir}/{anim_filename}" if animations_subdir else f"./{anim_filename}"
            file_attr.Set(anim_ref)

            name_attr = anim_file_prim.CreateAttribute("name", Sdf.ValueTypeNames.String, custom=True)
            name_attr.Set(take_name)

    main_stage.GetRootLayer().Save()
    print(f"✓ Saved main model: {main_usd_path}")

    # Copy textures to output directory (use textures_dir for organized structure)
    texture_paths = collect_texture_paths(mesh_nodes)
    if texture_paths and textures_dir:
        copied_textures = copy_textures_to_output(texture_paths, textures_dir)
        if copied_textures:
            print(f"✓ Copied {len(copied_textures)} texture(s)")

    # Write README.md
    if output_dir:
        readme_path = os.path.join(output_dir, "README.md")
        main_filename = os.path.basename(main_usd_path)
        first_anim = anim_files[0][0] if anim_files else "Idle"
        readme_content = f"""# {model_name} USD Files

This directory contains USD files exported from an FBX file with separate animations.

## Usage in Reality Composer Pro

**Add `{main_filename}` to your Reality Composer Pro project.** All other files will be brought in automatically because they are referenced.

## File Structure

- `{main_filename}` - **Main entry point** with model, skeleton, mesh, and AnimationLibrary
- `{os.path.basename(materials_usd_path)}` - Materials and shaders
- `{base_name}-<animation>{ext}` - Individual animation files

## Animations

The following animations are available in the AnimationLibrary:

"""
        for take_name, _ in anim_files:
            readme_content += f"- {take_name}\n"

        readme_content += f"""
## Example Code

```swift
guard
    let modelRoot = scene.findEntity(named: "{model_name}"),
    let animationLibrary = modelRoot.components[AnimationLibraryComponent.self]
else {{
    return
}}

guard let animation = animationLibrary.animations["{first_anim}"] else {{
    return
}}

modelRoot.playAnimation(
    animation.repeat(),
    transitionDuration: 0,
    startsPaused: false
)
```
"""

        with open(readme_path, 'w') as f:
            f.write(readme_content)
        print(f"✓ Created README.md")

    manager.Destroy()

    print(f"\nGenerated {len(anim_files) + 2} USD files:")
    print(f"  - {materials_usd_path} (materials)")
    print(f"  - {main_usd_path} (main model with AnimationLibrary)")
    for take_name, anim_filename in anim_files:
        print(f"  - {os.path.join(animations_dir, anim_filename) if animations_dir else anim_filename} ({take_name} animation)")


def convert_fbx_to_usd_separate_no_skeleton(fbx_path, usd_path, use_materialx=False, use_directory_structure=False):
    """Export FBX without skeleton as separate USD files: main model, per-animation files, and parent file.

    This is a separate code path for models without skeletons.
    Animations are exported as time-sampled transforms on mesh Xforms.
    """
    # Parse output path
    base_name = os.path.splitext(os.path.basename(usd_path))[0]
    ext = os.path.splitext(usd_path)[1] or '.usda'

    if use_directory_structure:
        # Create organized directory structure
        parent_dir = os.path.dirname(usd_path) or '.'
        output_dir = os.path.join(parent_dir, base_name)
        animations_dir = os.path.join(output_dir, "Animations")
        textures_dir = os.path.join(output_dir, "Textures")
        textures_subdir = "Textures"
        animations_subdir = "Animations"
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(animations_dir, exist_ok=True)
        os.makedirs(textures_dir, exist_ok=True)
    else:
        # Flat structure (original behavior)
        output_dir = os.path.dirname(usd_path)
        animations_dir = output_dir
        textures_dir = output_dir
        textures_subdir = None
        animations_subdir = None
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

    # Load FBX scene
    manager, scene = load_fbx_scene(fbx_path)

    # Get model name from FBX
    model_name = make_valid_identifier(os.path.splitext(os.path.basename(fbx_path))[0])

    # Get FPS
    time_mode = FbxTime.GetGlobalTimeMode()
    fps = FbxTime.GetFrameRate(time_mode)

    # Get animation stacks
    anim_stacks = []
    count = scene.GetSrcObjectCount(FbxCriteria.ObjectType(FbxAnimStack.ClassId))
    for i in range(count):
        anim_stacks.append(scene.GetSrcObject(FbxCriteria.ObjectType(FbxAnimStack.ClassId), i))

    print(f"Found {len(anim_stacks)} animation takes")
    for stack in anim_stacks:
        print(f"  - {stack.GetName()}")

    # Find meshes
    mesh_nodes = find_mesh_nodes(scene)
    print(f"Found {len(mesh_nodes)} mesh(es)")

    # Calculate clip info for each animation
    clips_info = []
    for stack in anim_stacks:
        scene.SetCurrentAnimationStack(stack)
        time_span = stack.GetLocalTimeSpan()
        start_time = time_span.GetStart().GetSecondDouble()
        stop_time = time_span.GetStop().GetSecondDouble()
        frames_count = int((stop_time - start_time) * fps + 0.5) + 1

        clips_info.append({
            'name': make_valid_identifier(stack.GetName()),
            'original_name': stack.GetName(),
            'start_frame': 0,
            'end_frame': frames_count - 1,
            'stack': stack
        })

    # --- 0. Export Materials to separate file ---
    materials_usd_path = os.path.join(output_dir, f"{base_name}-Materials{ext}") if output_dir else f"{base_name}-Materials{ext}"
    materials_file_basename = os.path.basename(materials_usd_path)

    materials_stage = Usd.Stage.CreateNew(materials_usd_path)
    UsdGeom.SetStageUpAxis(materials_stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(materials_stage, 1.0)

    # Create Materials scope as default prim
    materials_scope = UsdGeom.Scope.Define(materials_stage, "/Materials")
    materials_stage.SetDefaultPrim(materials_scope.GetPrim())

    # Export materials to this stage
    if use_materialx:
        export_materials_materialx(materials_stage, "/Materials", model_name, scene, mesh_nodes, textures_subdir=textures_subdir)
    else:
        export_materials_only(materials_stage, "/Materials", model_name, scene, mesh_nodes, textures_subdir=textures_subdir)

    materials_stage.GetRootLayer().Save()
    print(f"✓ Saved materials: {materials_usd_path}")

    # --- 1. Export Main Model (no animation) ---
    main_usd_path = os.path.join(output_dir, f"{base_name}{ext}") if output_dir else f"{base_name}{ext}"

    main_stage = Usd.Stage.CreateNew(main_usd_path)
    UsdGeom.SetStageUpAxis(main_stage, UsdGeom.Tokens.y)
    UsdGeom.SetStageMetersPerUnit(main_stage, 1.0)

    # Create hierarchy - simpler than skeletal: just model root with Geom
    root_xform = UsdGeom.Xform.Define(main_stage, f"/{model_name}")
    main_stage.SetDefaultPrim(root_xform.GetPrim())

    # Export meshes without materials (they're in separate file) and without skinning
    geom_path = f"/{model_name}/Geom"
    export_meshes_no_skeleton(main_stage, geom_path, model_name, scene, mesh_nodes, include_materials=False)

    # Reference materials from separate file
    main_materials_path = f"/{model_name}/Materials"
    main_materials_prim = main_stage.DefinePrim(main_materials_path)
    main_materials_prim.GetReferences().AddReference(f"./{materials_file_basename}", "/Materials")

    # Bind materials to meshes
    bind_materials_from_reference(main_stage, geom_path, main_materials_path, scene, mesh_nodes)

    # Note: We save main_stage after adding AnimationLibrary (below)

    # --- 2. Export Each Animation Take ---
    anim_files = []
    # Reference prefix for animation files pointing back to parent directory
    ref_prefix = "../" if animations_subdir else "./"

    for clip_info in clips_info:
        take_name = clip_info['name']
        anim_usd_path = os.path.join(animations_dir, f"{base_name}-{take_name}{ext}") if animations_dir else f"{base_name}-{take_name}{ext}"
        anim_files.append((take_name, os.path.basename(anim_usd_path)))

        anim_stage = Usd.Stage.CreateNew(anim_usd_path)
        UsdGeom.SetStageUpAxis(anim_stage, UsdGeom.Tokens.y)
        UsdGeom.SetStageMetersPerUnit(anim_stage, 1.0)

        # Set time range for this animation
        anim_stage.SetStartTimeCode(0)
        anim_stage.SetEndTimeCode(clip_info['end_frame'])
        anim_stage.SetTimeCodesPerSecond(fps)

        # Create hierarchy
        anim_root_xform = UsdGeom.Xform.Define(anim_stage, f"/{model_name}")
        anim_stage.SetDefaultPrim(anim_root_xform.GetPrim())

        # Reference Geom (mesh) from main file
        main_file_basename = os.path.basename(main_usd_path)
        anim_geom_path = f"/{model_name}/Geom"
        geom_prim = anim_stage.DefinePrim(anim_geom_path)
        geom_prim.GetReferences().AddReference(f"{ref_prefix}{main_file_basename}", f"/{model_name}/Geom")

        # Reference Materials from materials file
        anim_materials_path = f"/{model_name}/Materials"
        materials_prim = anim_stage.DefinePrim(anim_materials_path)
        materials_prim.GetReferences().AddReference(f"{ref_prefix}{materials_file_basename}", "/Materials")

        # Export transform animations for each mesh
        for mesh_node in mesh_nodes:
            mesh_name = make_valid_identifier(mesh_node.GetName())
            mesh_path = f"{anim_geom_path}/{mesh_name}"

            # The mesh prim comes from the reference, but we can add xform ops to override
            mesh_prim = anim_stage.GetPrimAtPath(mesh_path)
            if mesh_prim:
                export_transform_animation_single(anim_stage, mesh_path, scene, mesh_node, clip_info, fps)

        # Override material bindings on the referenced mesh
        for mesh_node in mesh_nodes:
            fbx_mesh = mesh_node.GetMesh()
            mesh_name = make_valid_identifier(mesh_node.GetName())
            mesh_path = f"{anim_geom_path}/{mesh_name}"

            material_elem = fbx_mesh.GetElementMaterial()
            if material_elem and mesh_node.GetMaterialCount() > 0:
                fbx_material = mesh_node.GetMaterial(0)
                if fbx_material:
                    mat_name = make_valid_identifier(fbx_material.GetName())
                    mat_path = f"{anim_materials_path}/{mat_name}"

                    mesh_prim = anim_stage.GetPrimAtPath(mesh_path)
                    if mesh_prim:
                        usd_material = UsdShade.Material.Get(anim_stage, mat_path)
                        if usd_material:
                            UsdShade.MaterialBindingAPI(mesh_prim).Bind(usd_material)

        anim_stage.GetRootLayer().Save()
        print(f"✓ Saved animation: {anim_usd_path}")

    # --- 3. Add AnimationLibrary to main model file and save ---
    if anim_files:
        anim_lib_path = f"/{model_name}/AnimationLibrary"
        anim_lib_prim = main_stage.DefinePrim(anim_lib_path, "RealityKitComponent")

        info_id_attr = anim_lib_prim.CreateAttribute(
            "info:id", Sdf.ValueTypeNames.Token, custom=True
        )
        info_id_attr.Set("RealityKit.AnimationLibrary")

        for take_name, anim_filename in anim_files:
            anim_file_prim_path = f"{anim_lib_path}/{take_name}"
            anim_file_prim = main_stage.DefinePrim(anim_file_prim_path, "RealityKitAnimationFile")

            file_attr = anim_file_prim.CreateAttribute("file", Sdf.ValueTypeNames.Asset, custom=True)
            # Use Animations/ subdirectory if directory structure is enabled
            anim_ref = f"./{animations_subdir}/{anim_filename}" if animations_subdir else f"./{anim_filename}"
            file_attr.Set(anim_ref)

            name_attr = anim_file_prim.CreateAttribute("name", Sdf.ValueTypeNames.String, custom=True)
            name_attr.Set(take_name)

    main_stage.GetRootLayer().Save()
    print(f"✓ Saved main model: {main_usd_path}")

    # Copy textures to output directory (use textures_dir for organized structure)
    texture_paths = collect_texture_paths(mesh_nodes)
    if texture_paths and textures_dir:
        copied_textures = copy_textures_to_output(texture_paths, textures_dir)
        if copied_textures:
            print(f"✓ Copied {len(copied_textures)} texture(s)")

    # Write README.md
    if output_dir:
        readme_path = os.path.join(output_dir, "README.md")
        main_filename = os.path.basename(main_usd_path)
        first_anim = anim_files[0][0] if anim_files else "Idle"
        readme_content = f"""# {model_name} USD Files

This directory contains USD files exported from an FBX file with separate animations.
This model does not have a skeleton - animations are transform-based.

## Usage in Reality Composer Pro

**Add `{main_filename}` to your Reality Composer Pro project.** All other files will be brought in automatically because they are referenced.

## File Structure

- `{main_filename}` - **Main entry point** with model, mesh, and AnimationLibrary
- `{os.path.basename(materials_usd_path)}` - Materials and shaders
- `{base_name}-<animation>{ext}` - Individual animation files

## Animations

The following animations are available in the AnimationLibrary:

"""
        for take_name, _ in anim_files:
            readme_content += f"- {take_name}\n"

        readme_content += f"""
## Example Code

```swift
guard
    let modelRoot = scene.findEntity(named: "{model_name}"),
    let animationLibrary = modelRoot.components[AnimationLibraryComponent.self]
else {{
    return
}}

guard let animation = animationLibrary.animations["{first_anim}"] else {{
    return
}}

modelRoot.playAnimation(
    animation.repeat(),
    transitionDuration: 0,
    startsPaused: false
)
```
"""

        with open(readme_path, 'w') as f:
            f.write(readme_content)
        print(f"✓ Created README.md")

    manager.Destroy()

    file_count = len(anim_files) + 2 if anim_files else 2
    print(f"\nGenerated {file_count} USD files:")
    print(f"  - {materials_usd_path} (materials)")
    print(f"  - {main_usd_path} (main model with AnimationLibrary)")
    for take_name, anim_filename in anim_files:
        print(f"  - {os.path.join(animations_dir, anim_filename) if animations_dir else anim_filename} ({take_name} animation)")


def main():
    parser = argparse.ArgumentParser(
        description='Convert FBX files to USD format with RealityKit support.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  fbx2usd input.fbx output.usda
      Convert FBX to single USD with concatenated animations

  fbx2usd -s input.fbx output/Character.usda
      Export separate USD files for each animation take:
        - Character.usda (main model with AnimationLibrary)
        - Character-Materials.usda (materials and shaders)
        - Character-<take>.usda (individual animation files)
'''
    )
    parser.add_argument('input', help='Input FBX file path')
    parser.add_argument('output', help='Output USD file path')
    parser.add_argument('-s', '--separate-animations', action='store_true',
                        help='Export each animation as a separate USD file')
    parser.add_argument('-m', '--materialx', action='store_true',
                        help='Use MaterialX shaders instead of UsdPreviewSurface (for Reality Composer Pro)')
    parser.add_argument('-d', '--directory-structure', action='store_true',
                        help='Create organized directory structure with Textures/ subdirectory (and Animations/ when using -s)')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: File not found: {args.input}")
        sys.exit(1)

    try:
        if args.separate_animations:
            convert_fbx_to_usd_separate(args.input, args.output, use_materialx=args.materialx, use_directory_structure=args.directory_structure)
        else:
            convert_fbx_to_usd(args.input, args.output, use_materialx=args.materialx, use_directory_structure=args.directory_structure)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
