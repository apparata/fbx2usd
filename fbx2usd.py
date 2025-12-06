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


def gf_matrix_from_fbx(m):
    """Convert FbxAMatrix to Gf.Matrix4d"""
    return Gf.Matrix4d(
        m[0][0], m[0][1], m[0][2], m[0][3],
        m[1][0], m[1][1], m[1][2], m[1][3],
        m[2][0], m[2][1], m[2][2], m[2][3],
        m[3][0], m[3][1], m[3][2], m[3][3]
    )


def convert_fbx_to_usd(fbx_path, usd_path):
    """Main conversion function"""

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
        print("No skeleton found")
        return

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

                    # Create or get material
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

                                # Create texture reader shader
                                tex_reader_path = f"{mat_path}/DiffuseTexture"
                                tex_reader = UsdShade.Shader.Define(stage, tex_reader_path)
                                tex_reader.CreateIdAttr("UsdUVTexture")
                                tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_name)
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

                                # Create normal texture reader
                                normal_reader_path = f"{mat_path}/NormalTexture"
                                normal_reader = UsdShade.Shader.Define(stage, normal_reader_path)
                                normal_reader.CreateIdAttr("UsdUVTexture")
                                normal_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_name)
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

                                # Create bump texture reader
                                bump_reader_path = f"{mat_path}/BumpTexture"
                                bump_reader = UsdShade.Shader.Define(stage, bump_reader_path)
                                bump_reader.CreateIdAttr("UsdUVTexture")
                                bump_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_name)
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

                                # Create roughness texture reader
                                roughness_reader_path = f"{mat_path}/RoughnessTexture"
                                roughness_reader = UsdShade.Shader.Define(stage, roughness_reader_path)
                                roughness_reader.CreateIdAttr("UsdUVTexture")
                                roughness_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_name)
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

                                # Create metallic texture reader
                                metallic_reader_path = f"{mat_path}/MetallicTexture"
                                metallic_reader = UsdShade.Shader.Define(stage, metallic_reader_path)
                                metallic_reader.CreateIdAttr("UsdUVTexture")
                                metallic_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_name)
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

                                # Create emissive texture reader
                                emissive_reader_path = f"{mat_path}/EmissiveTexture"
                                emissive_reader = UsdShade.Shader.Define(stage, emissive_reader_path)
                                emissive_reader.CreateIdAttr("UsdUVTexture")
                                emissive_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_name)
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

                                # Create AO texture reader
                                ao_reader_path = f"{mat_path}/OcclusionTexture"
                                ao_reader = UsdShade.Shader.Define(stage, ao_reader_path)
                                ao_reader.CreateIdAttr("UsdUVTexture")
                                ao_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_name)
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

    manager.Destroy()


def main():
    if len(sys.argv) < 3:
        print("Usage: fbx2usd_final.py <input.fbx> <output.usd[a|c]>")
        print("\nMatches the exact structure of working BusinessMan.usda:")
        print("- Animation is CHILD of Skeleton")
        print("- metersPerUnit = 0.01")
        print("- Bind transforms != Rest transforms")
        sys.exit(1)

    fbx_path = sys.argv[1]
    usd_path = sys.argv[2]

    if not os.path.exists(fbx_path):
        print(f"Error: File not found: {fbx_path}")
        sys.exit(1)

    try:
        convert_fbx_to_usd(fbx_path, usd_path)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
