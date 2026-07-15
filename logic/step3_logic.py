import maya.cmds as cmds
import json
import os
import re


PLACE2D_ATTRIBUTES = (
    'coverage', 'translateFrame', 'rotateFrame', 'mirrorU', 'mirrorV',
    'stagger', 'wrapU', 'wrapV', 'repeatUV', 'offset', 'rotateUV',
    'noiseUV', 'vertexUvOne', 'vertexUvTwo', 'vertexUvThree',
    'vertexCameraOne', 'outUV', 'outUvFilterSize')


def create_file_texture_network(
        image_file_path, name_prefix, black_default=False):
    """Create a file/place2d pair used by both projection and UV setups."""
    file_node = cmds.shadingNode('file', asTexture=True, name=f'{name_prefix}_texture')
    cmds.setAttr(f'{file_node}.fileTextureName', image_file_path, type='string')
    if black_default:
        cmds.setAttr(f'{file_node}.defaultColor', 0, 0, 0, type='double3')
    place2d = cmds.shadingNode(
        'place2dTexture', asUtility=True, name=f'{name_prefix}_place2d')
    for attribute in PLACE2D_ATTRIBUTES:
        if (cmds.attributeQuery(attribute, node=place2d, exists=True) and
                cmds.attributeQuery(attribute, node=file_node, exists=True)):
            try:
                cmds.connectAttr(
                    f'{place2d}.{attribute}', f'{file_node}.{attribute}', force=True)
            except RuntimeError:
                pass
    return file_node, place2d


def reorder_managed_layer_sources(layered_texture, ordered_sources):
    """Reconnect the managed leading slots in explicit top-to-bottom order."""
    if not layered_texture or not cmds.objExists(layered_texture):
        return False
    for index, source in enumerate(ordered_sources):
        for channel in ('color', 'alpha'):
            destination = f'{layered_texture}.inputs[{index}].{channel}'
            for current in cmds.listConnections(
                    destination, source=True, destination=False,
                    plugs=True) or []:
                cmds.disconnectAttr(current, destination)
            cmds.connectAttr(source[channel], destination, force=True)
    return True


def get_max_layer_index(layered_texture_node):
    """Return the highest instantiated layeredTexture input index."""
    if not layered_texture_node or not cmds.objExists(layered_texture_node):
        return -1
    indices = cmds.getAttr(
        f'{layered_texture_node}.inputs', multiIndices=True) or []
    return max(indices) if indices else -1

def shift_layers_down(layered_texture_node, max_index):
    """
    Shifts all layers down by one (index 0 to 1, 1 to 2, etc.) to make room for a new layer at index 0.
    Shifts both color and alpha connections.
    
    Args:
        layered_texture_node (str): The layeredTexture node name
        max_index (int): The highest currently used layer index
    """
    # We need to work from bottom to top to avoid overwriting connections
    for i in range(max_index, -1, -1):
        # Handle color connections
        color_connections = cmds.listConnections(f"{layered_texture_node}.inputs[{i}].color", source=True, destination=False, plugs=True)
        if color_connections:
            # Disconnect from current index
            cmds.disconnectAttr(color_connections[0], f"{layered_texture_node}.inputs[{i}].color")
            
            # Reconnect to new index (i+1)
            cmds.connectAttr(color_connections[0], f"{layered_texture_node}.inputs[{i+1}].color", force=True)
        
        # Handle alpha connections
        alpha_connections = cmds.listConnections(f"{layered_texture_node}.inputs[{i}].alpha", source=True, destination=False, plugs=True)
        if alpha_connections:
            # Disconnect from current index
            cmds.disconnectAttr(alpha_connections[0], f"{layered_texture_node}.inputs[{i}].alpha")
            
            # Reconnect to new index (i+1)
            cmds.connectAttr(alpha_connections[0], f"{layered_texture_node}.inputs[{i+1}].alpha", force=True)

def find_or_create_material(mesh_transform):
    """
    Finds or creates a material for the given mesh transform.
    
    Args:
        mesh_transform (str): The transform node of the mesh
        
    Returns:
        str or None: The material node name, or None if failed
    """
    material = None
    assigned_materials = []

    if cmds.objExists(mesh_transform):
        shading_groups_from_sets = cmds.listSets(type=1, object=mesh_transform) or []
        for sg in shading_groups_from_sets:
            if cmds.attributeQuery('surfaceShader', node=sg, exists=True):
                mat_conns = cmds.listConnections(f"{sg}.surfaceShader", source=True, destination=False, plugs=False)
                if mat_conns:
                    for mat_node in mat_conns:
                        if cmds.ls(mat_node, materials=True) and mat_node not in assigned_materials:
                            assigned_materials.append(mat_node)

        if not assigned_materials:
            shapes = cmds.listRelatives(mesh_transform, shapes=True, noIntermediate=True, fullPath=True) or []
            for shape in shapes:
                sgs_from_shape = cmds.listConnections(shape, type='shadingEngine')
                if sgs_from_shape:
                    for sg_shape in list(set(sgs_from_shape)):
                        if cmds.attributeQuery('surfaceShader', node=sg_shape, exists=True):
                            mat_conns = cmds.listConnections(f"{sg_shape}.surfaceShader", source=True, destination=False, plugs=False)
                            if mat_conns:
                                for mat_node in mat_conns:
                                    if cmds.ls(mat_node, materials=True) and mat_node not in assigned_materials:
                                        assigned_materials.append(mat_node)

    if assigned_materials:
        material = assigned_materials[0]
    else:
        lambert1_as_fallback = None
        initial_sg_list = cmds.ls("initialShadingGroup", type="shadingEngine")
        if initial_sg_list:
            initial_sg = initial_sg_list[0]
            members = cmds.sets(initial_sg, query=True) or []
            is_member = False
            if mesh_transform in members:
                is_member = True
            else:
                shapes = cmds.listRelatives(mesh_transform, shapes=True, noIntermediate=True, fullPath=True) or []
                for shape_node in shapes:
                    if shape_node in members:
                        is_member = True
                        break
            
            mat_conns_initial_sg = cmds.listConnections(f"{initial_sg}.surfaceShader", source=True, destination=False)
            if mat_conns_initial_sg and cmds.ls(mat_conns_initial_sg[0], materials=True):
                lambert1_as_fallback = mat_conns_initial_sg[0]

            if is_member and lambert1_as_fallback:
                material = lambert1_as_fallback
        
        if not material:
            mesh_base_name = mesh_transform.split('|')[-1].split(':')[-1]
            new_material_node = None
            new_sg_node = None
            try:
                new_material_node = cmds.shadingNode('lambert', asShader=True, name=f"{mesh_base_name}_autoMat#")
                new_sg_node = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{new_material_node}SG#")
                
                cmds.connectAttr(f"{new_material_node}.outColor", f"{new_sg_node}.surfaceShader", force=True)
                cmds.sets(mesh_transform, edit=True, forceElement=new_sg_node)
                material = new_material_node
            except RuntimeError as e:
                cmds.warning(f"Could not assign a material to '{mesh_transform}': {e}")
                if new_sg_node and cmds.objExists(new_sg_node): cmds.delete(new_sg_node)
                if new_material_node and cmds.objExists(new_material_node): cmds.delete(new_material_node)
                material = None

    return material


def get_material_color_attr(material):
    """Return the color input supported by the assigned Maya/render material."""
    for attribute in ('baseColor', 'color', 'diffuseColor', 'diffuse_color'):
        if cmds.attributeQuery(attribute, node=material, exists=True):
            return f'{material}.{attribute}'
    return None


def connect_source_to_material_layer(material, source_color, source_alpha):
    """Insert one texture source at input 0 of the material layeredTexture."""
    material_color_attr = get_material_color_attr(material)
    if not material_color_attr:
        cmds.warning(f"Cannot find color attribute on material '{material}'.")
        return None

    existing = cmds.listConnections(
        material_color_attr, source=True, destination=False, plugs=True) or []
    layered_texture = None
    if existing and cmds.objectType(existing[0].split('.')[0]) == 'layeredTexture':
        layered_texture = existing[0].split('.')[0]

    if not layered_texture:
        material_short = material.split('|')[-1].split(':')[-1]
        material_prefix = material_short.split('_')[0] if '_' in material_short else material_short
        layered_texture = cmds.shadingNode(
            'layeredTexture', asTexture=True, name=f'{material_prefix}_layeredTexture')
        if existing:
            cmds.disconnectAttr(existing[0], material_color_attr)
            cmds.connectAttr(existing[0], f'{layered_texture}.inputs[1].color', force=True)
        cmds.connectAttr(f'{layered_texture}.outColor', material_color_attr, force=True)
    else:
        max_index = get_max_layer_index(layered_texture)
        if max_index >= 0:
            shift_layers_down(layered_texture, max_index)

    cmds.connectAttr(source_color, f'{layered_texture}.inputs[0].color', force=True)
    cmds.connectAttr(source_alpha, f'{layered_texture}.inputs[0].alpha', force=True)
    return layered_texture


def capture_material_state(mesh_transform):
    """Capture the material input and existing layeredTexture before Step 3."""
    material = find_or_create_material(mesh_transform)
    color_attr = get_material_color_attr(material) if material else None
    if not color_attr:
        return None
    sources = cmds.listConnections(
        color_attr, source=True, destination=False, plugs=True) or []
    source = sources[0] if sources else None
    layered = source.split('.')[0] if source and cmds.objectType(source.split('.')[0]) == 'layeredTexture' else None
    layers = []
    if layered:
        for index in cmds.getAttr(f'{layered}.inputs', multiIndices=True) or []:
            entry = {'index': index}
            for child in ('color', 'alpha'):
                plug = f'{layered}.inputs[{index}].{child}'
                connections = cmds.listConnections(
                    plug, source=True, destination=False, plugs=True) or []
                entry[f'{child}_source'] = connections[0] if connections else None
                if not connections:
                    try:
                        entry[f'{child}_value'] = cmds.getAttr(plug)
                    except RuntimeError:
                        entry[f'{child}_value'] = None
            for child in ('blendMode', 'isVisible'):
                try:
                    entry[child] = cmds.getAttr(f'{layered}.inputs[{index}].{child}')
                except RuntimeError:
                    entry[child] = None
            layers.append(entry)
    return {
        'material': material, 'color_attr': color_attr, 'source': source,
        'layered_texture': layered, 'layers': layers
    }


def restore_material_state(state, current_layered_nodes=()):
    """Restore the material graph captured before Step 3."""
    if not state or not cmds.objExists(state.get('material')):
        return
    color_attr = state['color_attr']
    for source in cmds.listConnections(
            color_attr, source=True, destination=False, plugs=True) or []:
        cmds.disconnectAttr(source, color_attr)

    layered = state.get('layered_texture')
    if layered and cmds.objExists(layered):
        for index in cmds.getAttr(f'{layered}.inputs', multiIndices=True) or []:
            try:
                cmds.removeMultiInstance(f'{layered}.inputs[{index}]', b=True)
            except RuntimeError:
                pass
        for entry in state.get('layers', []):
            index = entry['index']
            for child in ('color', 'alpha'):
                plug = f'{layered}.inputs[{index}].{child}'
                source = entry.get(f'{child}_source')
                value = entry.get(f'{child}_value')
                if source and cmds.objExists(source.split('.')[0]):
                    cmds.connectAttr(source, plug, force=True)
                elif value is not None:
                    if child == 'color':
                        rgb = value[0] if isinstance(value, (list, tuple)) and len(value) == 1 else value
                        cmds.setAttr(plug, *rgb, type='double3')
                    else:
                        cmds.setAttr(plug, value)
            for child in ('blendMode', 'isVisible'):
                if entry.get(child) is not None:
                    cmds.setAttr(f'{layered}.inputs[{index}].{child}', entry[child])

    original_source = state.get('source')
    if original_source and cmds.objExists(original_source.split('.')[0]):
        cmds.connectAttr(original_source, color_attr, force=True)

    for node in set(current_layered_nodes):
        if node and node != layered and cmds.objExists(node):
            cmds.delete(node)

def connect_texture_to_mesh(mesh_transform, image_file_path, name_prefix="texelator", bind_joint=None):
    """
    Connects the specified texture to the mesh's material using a projection node.
    If the material already has a texture, uses a layeredTexture node to layer them.
    
    Args:
        mesh_transform (str): The transform node of the mesh
        image_file_path (str): Full path to the image file
        name_prefix (str): Prefix for naming created nodes
        bind_joint (str): Name of the bind joint to connect to the place3dTexture
        
    Returns:
        tuple: (file_node, projection_node, place2d_node, place3d_node, layered_texture, material_node) or (None, None, None, None, None, None)
    """
    if not mesh_transform or not cmds.objExists(mesh_transform):
        cmds.warning(f"Mesh '{mesh_transform}' not found.")
        return None, None, None, None, None, None
        
    if not image_file_path or not os.path.exists(image_file_path):
        cmds.warning(f"Image file '{image_file_path}' not found.")
        return None, None, None, None, None, None
        
    # Find or create material for the mesh
    material = find_or_create_material(mesh_transform)
    
    if not material:
        cmds.warning(f"Failed to find, create, or assign a suitable material for mesh '{mesh_transform}'. Cannot connect texture.")
        return None, None, None, None, None, None
    
    file_node, place2d_node = create_file_texture_network(image_file_path, name_prefix)
    
    # Create a place3dTexture node for the projection
    place3d_node = cmds.shadingNode('place3dTexture', asUtility=True, name=f"{name_prefix}_place3d")
    
    # Set the scale of place3dTexture to 1
    cmds.setAttr(f"{place3d_node}.scale", 3, 3, 3, type="double3")
    
    # Create a projection node
    projection_node = cmds.shadingNode('projection', asUtility=True, name=f"{name_prefix}_projection")
    
    # Set projection type to "planar" (1)
    cmds.setAttr(f"{projection_node}.projType", 1)
    
    # Set Wrap to off
    if cmds.attributeQuery('wrap', node=projection_node, exists=True):
        cmds.setAttr(f"{projection_node}.wrap", 0)  # 0 = off
    
    # Set defaultColor to [0, 0, 0]
    cmds.setAttr(f"{projection_node}.defaultColor", 0, 0, 0, type="double3")
    
    # Connect file node to projection node
    cmds.connectAttr(f"{file_node}.outColor", f"{projection_node}.image", force=True)
    
    # Connect place3dTexture to projection node
    cmds.connectAttr(f"{place3d_node}.worldInverseMatrix[0]", f"{projection_node}.placementMatrix", force=True)

    # New alpha handling logic starts here
    # 1. Create a new layeredTexture node for alpha
    alpha_layered_texture_node = cmds.shadingNode('layeredTexture', asTexture=True, name=f"{name_prefix}_alpha_layeredTexture")
    
    # 2. Connect main image's alpha to the new layeredTexture's inputs[0].alpha
    cmds.connectAttr(f"{file_node}.outAlpha", f"{alpha_layered_texture_node}.inputs[0].alpha", force=True)
    
    # 3. Set inputs[0].color of the new layeredTexture to white
    cmds.setAttr(f"{alpha_layered_texture_node}.inputs[0].color", 1, 1, 1, type="double3")
    
    # 4. Create a new projection node for alpha
    alpha_projection_node = cmds.shadingNode('projection', asUtility=True, name=f"{name_prefix}_alpha_projection")
    
    # Set alpha_projection_node type to "planar" (1) and wrap off, default color black
    cmds.setAttr(f"{alpha_projection_node}.projType", 1)
    if cmds.attributeQuery('wrap', node=alpha_projection_node, exists=True):
        cmds.setAttr(f"{alpha_projection_node}.wrap", 0)
    cmds.setAttr(f"{alpha_projection_node}.defaultColor", 0, 0, 0, type="double3")

    # 5. Connect the new layeredTexture to the new alpha projection node's image
    cmds.connectAttr(f"{alpha_layered_texture_node}.outColor", f"{alpha_projection_node}.image", force=True)
    
    # 6. Connect the existing place3dTexture to the new alpha projection node's placementMatrix
    cmds.connectAttr(f"{place3d_node}.worldInverseMatrix[0]", f"{alpha_projection_node}.placementMatrix", force=True)
    
    # 7. Connect the new alpha projection node's outColorR to the main projection_node's alphaOffset
    cmds.connectAttr(f"{alpha_projection_node}.outColorR", f"{projection_node}.alphaOffset", force=True)
    # End of new alpha handling logic
    
    layered_texture_node = connect_source_to_material_layer(
        material, f'{projection_node}.outColor', f'{projection_node}.outAlpha')
    if not layered_texture_node:
        cmds.delete(file_node, place2d_node, place3d_node, projection_node,
                    alpha_layered_texture_node, alpha_projection_node)
        return None, None, None, None, None, None
    
    # If bind_joint is provided, set up constraints
    if bind_joint and cmds.objExists(bind_joint):
        try:
            # Match place3dTexture's position and rotation to the bind_joint
            translation = cmds.xform(bind_joint, query=True, worldSpace=True, translation=True)
            rotation = cmds.xform(bind_joint, query=True, worldSpace=True, rotation=True)
            
            # Set the place3dTexture's position and rotation
            cmds.xform(place3d_node, worldSpace=True, translation=translation)
            cmds.xform(place3d_node, worldSpace=True, rotation=rotation)
            
            # Create parent constraint
            parent_constraint = cmds.parentConstraint(bind_joint, place3d_node, maintainOffset=True)[0]
            
            # Create scale constraint
            scale_constraint = cmds.scaleConstraint(bind_joint, place3d_node, maintainOffset=True)[0]
            
        except Exception as e:
            cmds.warning(f"Failed to constrain place3dTexture to bind joint: {e}")
    
    return file_node, projection_node, place2d_node, place3d_node, layered_texture_node, material

def organize_scene_hierarchy(mesh_transform, follicle_transform, place3d_node, name_prefix, master_group_name=None):
    """
    Organizes the scene hierarchy according to specified requirements:
    1. Creates or finds a master group for the Texelator setup
    2. Places mesh under GEO group
    3. Creates RIG group with prefix_Texture_ctrl_grp for follicle
    4. Places place3dTexture under UTIL group (if provided)
    5. Sets follicle shape node visibility to off
    6. Sets UTIL group visibility to off
    
    Args:
        mesh_transform (str): The mesh transform node
        follicle_transform (str): The follicle transform node
        place3d_node (str): The place3dTexture node (can be None for UV-based method)
        name_prefix (str): User-provided prefix for naming
        master_group_name (str, optional): Name for the master group. Auto-generated if None.
    Returns:
        str: The (potentially updated) full path of the mesh transform.
    """
    if not follicle_transform:
        cmds.warning("Missing follicle node for scene organization.")
        return cmds.ls(mesh_transform, long=True)[0] if cmds.objExists(mesh_transform) else mesh_transform

    # This will be the path of the mesh after this function.
    final_mesh_path = mesh_transform

    # --- Per-mesh Texelator group ---
    if not master_group_name:
        mesh_short_name = mesh_transform.split('|')[-1].split(':')[-1]
        master_group_name = f"Texelator_{mesh_short_name}"
    
    master_group_long_name = ""
    if not cmds.objExists(master_group_name):
        master_group_long_name = cmds.group(empty=True, name=master_group_name, world=True)
    else:
        master_group_long_name = cmds.ls(master_group_name, long=True)[0]
    if not cmds.attributeQuery("isTexelatorSetup", node=master_group_long_name, exists=True):
        cmds.addAttr(master_group_long_name, longName="isTexelatorSetup", attributeType="bool", defaultValue=True)
        cmds.setAttr(f"{master_group_long_name}.isTexelatorSetup", lock=True)
    if not cmds.attributeQuery("texelatorVersion", node=master_group_long_name, exists=True):
        cmds.addAttr(master_group_long_name, longName="texelatorVersion", dataType="string")
        cmds.setAttr(f"{master_group_long_name}.texelatorVersion", "0.1.4", type="string", lock=True)

    # Mesh stays where it is (no GEO group)
    if cmds.objExists(mesh_transform):
        final_mesh_path = cmds.ls(mesh_transform, long=True)[0]
    else:
        cmds.warning(f"Mesh '{mesh_transform}' not found at the start of scene organization.")
    
    rig_group_name = "RIG"
    rig_group_long_name = ""
    # Look for RIG under master group
    rig_candidates = cmds.listRelatives(master_group_long_name, children=True, type="transform", fullPath=True) or []
    for c in rig_candidates:
        if c.split('|')[-1] == rig_group_name:
            rig_group_long_name = c
            break
    if not rig_group_long_name:
        rig_group_long_name = cmds.group(empty=True, name=rig_group_name, parent=master_group_long_name)
    
    texture_ctrl_grp_name = f"{name_prefix}_Texture_ctrl_grp"
    texture_ctrl_grp_long_name = next(
        (child for child in cmds.listRelatives(
            rig_group_long_name, children=True, type='transform', fullPath=True) or []
         if child.split('|')[-1] == texture_ctrl_grp_name),
        None)
    if not texture_ctrl_grp_long_name:
        texture_ctrl_grp_long_name = cmds.group(
            empty=True, name=texture_ctrl_grp_name, parent=rig_group_long_name)

    if cmds.objExists(follicle_transform):
        current_follicle_parent_list = cmds.listRelatives(follicle_transform, parent=True, fullPath=True)
        current_follicle_parent_full_path = current_follicle_parent_list[0] if current_follicle_parent_list else None
        if current_follicle_parent_full_path != texture_ctrl_grp_long_name:
            cmds.parent(follicle_transform, texture_ctrl_grp_long_name)
    else:
        cmds.warning(f"Follicle '{follicle_transform}' not found for parenting under '{texture_ctrl_grp_name}'.")

    follicle_shapes = cmds.listRelatives(follicle_transform, shapes=True, type="follicle", fullPath=True)
    if follicle_shapes:
        for shape in follicle_shapes:
            cmds.setAttr(f"{shape}.visibility", 0)
    
    # Handle place3d_node (if provided) - Modified to handle None case
    util_group_name = "UTIL"
    util_group_long_name = ""
    # Look for UTIL under master group
    util_candidates = cmds.listRelatives(master_group_long_name, children=True, type="transform", fullPath=True) or []
    for c in util_candidates:
        if c.split('|')[-1] == util_group_name:
            util_group_long_name = c
            break
    if not util_group_long_name:
        util_group_long_name = cmds.group(empty=True, name=util_group_name, parent=master_group_long_name)

    if place3d_node and cmds.objExists(place3d_node):
        current_p3d_parent_list = cmds.listRelatives(place3d_node, parent=True, fullPath=True)
        current_p3d_parent_full_path = current_p3d_parent_list[0] if current_p3d_parent_list else None
        if current_p3d_parent_full_path != util_group_long_name:
            cmds.parent(place3d_node, util_group_long_name)
    elif place3d_node:  # place3d_node was provided but doesn't exist
        cmds.warning(f"place3dTexture node '{place3d_node}' not found for parenting under '{util_group_name}'.")
        
    try:
        cmds.setAttr(f"{util_group_long_name}.visibility", 0)
    except Exception as e:
        cmds.warning(f"Could not set UTIL group visibility: {e}")
        
    return final_mesh_path

def find_bind_joint_from_follicle(follicle_transform):
    """
    Finds the _bind joint related to the follicle created in step 2.
    
    Args:
        follicle_transform (str): The transform node of the follicle
        
    Returns:
        str: Name of the bind joint or None if not found
    """
    if not follicle_transform or not cmds.objExists(follicle_transform):
        return None
    
    # Try to find the bind joint based on naming convention
    base_name = follicle_transform.split('|')[-1].split(':')[-1]
    possible_bind_joint = f"{base_name}_bind"
    
    if cmds.objExists(possible_bind_joint):
        return possible_bind_joint
    
    # If not found by name, search for a joint under the slide_ctrl
    slide_ctrl_candidates = cmds.listRelatives(follicle_transform, allDescendents=True, type="transform") or []
    
    for ctrl in slide_ctrl_candidates:
        if "_Slide_ctrl" in ctrl:
            # Check for joints under this control
            joints = cmds.listRelatives(ctrl, allDescendents=True, type="joint") or []
            joints += cmds.listRelatives(ctrl, children=True, type="joint") or []
            
            for joint in joints:
                if "_bind" in joint:
                    return joint
    
    return None

def detect_image_sequence_range(image_path):
    """Return the real frame range for the selected image sequence.

    The last numeric block before the extension is treated as the frame number,
    so both ``name.1001.exr`` and ``name_0001.png`` are supported. Files must
    share the same text before/after that number and the same extension.
    """
    if not image_path:
        return None
    image_path = os.path.abspath(os.path.expandvars(os.path.expanduser(image_path)))
    directory, filename = os.path.split(image_path)
    stem, extension = os.path.splitext(filename)
    match = re.search(r'(\d+)(?!.*\d)', stem)
    if not match or not os.path.isdir(directory):
        return None
    prefix = stem[:match.start()]
    suffix = stem[match.end():]
    pattern = re.compile(
        r'^{}(\d+){}{}$'.format(
            re.escape(prefix), re.escape(suffix), re.escape(extension)),
        re.IGNORECASE)
    frames = []
    try:
        for entry in os.scandir(directory):
            if not entry.is_file():
                continue
            candidate = pattern.match(entry.name)
            if candidate:
                frames.append(int(candidate.group(1)))
    except OSError:
        return None
    if not frames:
        return None
    return min(frames), max(frames), len(set(frames))


def _file_sequence_range(file_node):
    if not file_node or not cmds.objExists(file_node):
        return None
    try:
        return detect_image_sequence_range(
            cmds.getAttr(f'{file_node}.fileTextureName'))
    except (RuntimeError, TypeError):
        return None


def _connected_sequence_range(frame_attr, additional_file_node=None):
    """Combine ranges of all file nodes driven by one controller attribute."""
    file_nodes = []
    try:
        destinations = cmds.listConnections(
            frame_attr, source=False, destination=True,
            plugs=True, connections=False) or []
    except RuntimeError:
        destinations = []
    for destination in destinations:
        if destination.endswith('.frameExtension'):
            node = destination.rsplit('.', 1)[0]
            if node not in file_nodes:
                file_nodes.append(node)
    if additional_file_node and additional_file_node not in file_nodes:
        file_nodes.append(additional_file_node)
    ranges = [value for value in map(_file_sequence_range, file_nodes) if value]
    if not ranges:
        return 0, 9999, 0
    return (
        min(value[0] for value in ranges),
        max(value[1] for value in ranges),
        sum(value[2] for value in ranges))


def _set_integer_attribute_range(frame_attr, minimum, maximum):
    """Safely replace an existing numeric attribute's hard limits."""
    current = cmds.getAttr(frame_attr)
    # Keep the current value valid while first changing the limits, then clamp
    # it and apply the exact detected range.
    cmds.addAttr(
        frame_attr, edit=True,
        minValue=min(minimum, current), maxValue=max(maximum, current))
    clamped = max(minimum, min(maximum, current))
    if clamped != current:
        cmds.setAttr(frame_attr, clamped)
    cmds.addAttr(
        frame_attr, edit=True, minValue=minimum, maxValue=maximum)


def setup_sequence_texture(file_node, slide_ctrl, is_sequence=False,
                           attribute_name="Frame"):
    """
    Sets up a texture file node for sequence playback and connects it to a slide ctrl.
    
    Args:
        file_node (str): The file texture node name
        slide_ctrl (str): The slide control that will drive the frame
        is_sequence (bool): Whether to enable sequence mode
        attribute_name (str): Controller attribute driving frameExtension
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not cmds.objExists(file_node) or not cmds.objExists(slide_ctrl):
        cmds.warning(f"File node '{file_node}' or slide ctrl '{slide_ctrl}' does not exist.")
        return False
    
    try:
        # Set useFrameExtension based on is_sequence flag
        cmds.setAttr(f"{file_node}.useFrameExtension", 1 if is_sequence else 0)
        
        frame_attr = f"{slide_ctrl}.{attribute_name}"
        
        # If sequence mode is enabled, create or update the Frame attribute
        if is_sequence:
            attribute_exists = cmds.attributeQuery(
                attribute_name, node=slide_ctrl, exists=True)
            if attribute_exists:
                minimum, maximum, _count = _connected_sequence_range(
                    frame_attr, additional_file_node=file_node)
            else:
                detected = _file_sequence_range(file_node)
                minimum, maximum, _count = detected or (0, 9999, 0)
            if not attribute_exists:
                cmds.addAttr(slide_ctrl, longName=attribute_name,
                           attributeType="long", defaultValue=minimum,
                           minValue=minimum, maxValue=maximum, keyable=True)
            else:
                _set_integer_attribute_range(
                    frame_attr, minimum, maximum)
            
            # Connect Frame attribute to frameExtension
            if not cmds.isConnected(frame_attr, f"{file_node}.frameExtension"):
                cmds.connectAttr(frame_attr, f"{file_node}.frameExtension", force=True)
        else:
            # Disconnect if exists and sequence mode is disabled
            if cmds.attributeQuery(
                    attribute_name, node=slide_ctrl, exists=True):
                if cmds.isConnected(frame_attr, f"{file_node}.frameExtension"):
                    cmds.disconnectAttr(frame_attr, f"{file_node}.frameExtension")
                    minimum, maximum, _count = _connected_sequence_range(
                        frame_attr)
                    _set_integer_attribute_range(
                        frame_attr, minimum, maximum)
                
                # Optionally, we could also remove the attribute
                # cmds.deleteAttr(slide_ctrl, attribute="Frame")
        
        return True
    except Exception as e:
        cmds.warning(f"Error setting up sequence texture: {e}")
        return False

def hide_slide_ctrl_attributes(slide_ctrl):
    """
    Makes specified attributes of slide_ctrl non-keyable, hidden, and locked.
    
    Args:
        slide_ctrl (str): The slide control node name
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not slide_ctrl or not cmds.objExists(slide_ctrl):
        return False
    
    try:
        # List of attributes to hide and lock
        attrs_to_hide = ["translateZ", "rotateX", "rotateY", "scaleZ"]
        
        for attr in attrs_to_hide:
            if cmds.attributeQuery(attr, node=slide_ctrl, exists=True):
                # First unlock the attribute if it's already locked
                cmds.setAttr(f"{slide_ctrl}.{attr}", lock=False)
                
                # Make attribute non-keyable and hide it
                cmds.setAttr(f"{slide_ctrl}.{attr}", keyable=False, channelBox=False)
                
                # Lock the attribute
                cmds.setAttr(f"{slide_ctrl}.{attr}", lock=True)
        
        return True
    except Exception as e:
        cmds.warning(f"Error hiding/locking attributes on {slide_ctrl}: {e}")
        return False

def run_step3_logic(mesh_transform, image_file_path=None, name_prefix="texelator",
                    follicle_transform=None, is_sequence=False, master_group_name=None):
    """
    Main logic for Step 3: Connects texture and organizes scene.
    
    Args:
        mesh_transform (str): Mesh transform node name
        image_file_path (str, optional): Path to image file
        name_prefix (str, optional): Prefix for node names
        follicle_transform (str, optional): Follicle transform node name
        is_sequence (bool, optional): Whether the texture is a sequence
        
    Returns the projection nodes, material, mesh path and tracked support nodes.
    """
    if not image_file_path:
        cmds.warning("No image file path provided for texture connection.")
        return None, None, None, None, None, None, mesh_transform, {}

    bind_joint = find_bind_joint_from_follicle(follicle_transform) if follicle_transform else None

    file_node, projection_node, place2d_node, place3d_node, layered_texture, material = connect_texture_to_mesh(
        mesh_transform, 
        image_file_path, 
        name_prefix,
        bind_joint=bind_joint
    )

    updated_mesh_path_after_organization = mesh_transform 

    if not file_node: 
        cmds.warning(f"Texture connection failed for prefix '{name_prefix}'. Skipping organization.")
        return None, None, None, None, None, None, mesh_transform, {}

    # Find slide_ctrl for the follicle
    slide_ctrl = None
    if follicle_transform and cmds.objExists(follicle_transform):
        # Try to find Slide_ctrl from the follicle hierarchy
        all_descendants = cmds.listRelatives(follicle_transform, allDescendents=True, type="transform") or []
        for desc in all_descendants:
            if "_Slide_ctrl" in desc:
                slide_ctrl = desc
                break
        
        # If not found directly, try through the bind_joint's parent
        if not slide_ctrl and bind_joint:
            parent_transforms = cmds.listRelatives(bind_joint, parent=True, type="transform")
            if parent_transforms:
                potential_slide_ctrl = parent_transforms[0]
                if "_Slide_ctrl" in potential_slide_ctrl:
                    slide_ctrl = potential_slide_ctrl

    # Setup sequence texture if needed
    if is_sequence and slide_ctrl:
        setup_sequence_texture(file_node, slide_ctrl, is_sequence)

    # Hide specified attributes on slide_ctrl
    if slide_ctrl:
        hide_slide_ctrl_attributes(slide_ctrl)

    if follicle_transform and place3d_node: 
        updated_mesh_path_after_organization = organize_scene_hierarchy(
            mesh_transform, follicle_transform, place3d_node, name_prefix,
            master_group_name=master_group_name)
    else:
        cmds.warning(f"Skipping scene organization for prefix '{name_prefix}' due to missing follicle or place3dTexture node.")
            
    support_nodes = []
    for alpha_projection in cmds.listConnections(
            f'{projection_node}.alphaOffset', source=True, destination=False) or []:
        support_nodes.append(alpha_projection)
        support_nodes.extend(cmds.listConnections(
            f'{alpha_projection}.image', source=True, destination=False) or [])
    details = {'support_nodes': list(set(support_nodes))}
    return (file_node, projection_node, place2d_node, place3d_node,
            layered_texture, material, updated_mesh_path_after_organization, details)


# --- Layer Management ---

def get_layer_info(layered_texture_node):
    """
    Gets information about all connected layers in a layeredTexture node.
    
    Args:
        layered_texture_node (str): The layeredTexture node name
        
    Returns:
        list: List of dicts with 'index', 'color_source', 'alpha_source' keys, sorted by index
    """
    if not layered_texture_node or not cmds.objExists(layered_texture_node):
        return []
    
    layers = []
    connected_attrs = cmds.listConnections(layered_texture_node, connections=True, plugs=True, source=True, destination=False) or []
    
    found_indices = set()
    for i in range(0, len(connected_attrs), 2):
        attr = connected_attrs[i]
        source = connected_attrs[i + 1]
        if ".inputs[" in attr:
            try:
                idx = int(attr.split(".inputs[")[1].split("]")[0])
                found_indices.add(idx)
            except (ValueError, IndexError):
                continue
    
    for idx in sorted(found_indices):
        color_conns = cmds.listConnections(f"{layered_texture_node}.inputs[{idx}].color", source=True, destination=False, plugs=True) or []
        alpha_conns = cmds.listConnections(f"{layered_texture_node}.inputs[{idx}].alpha", source=True, destination=False, plugs=True) or []
        
        color_src = color_conns[0] if color_conns else None
        alpha_src = alpha_conns[0] if alpha_conns else None
        
        # Try to get a readable name from the color source
        display_name = ""
        if color_src:
            src_node = color_src.split('.')[0]
            display_name = src_node
        
        layers.append({
            'index': idx,
            'color_source': color_src,
            'alpha_source': alpha_src,
            'display_name': display_name
        })
    
    return layers


def swap_layers(layered_texture_node, index_a, index_b):
    """
    Swaps two layers in a layeredTexture node.
    
    Args:
        layered_texture_node (str): The layeredTexture node name
        index_a (int): First layer index
        index_b (int): Second layer index
        
    Returns:
        bool: True if successful
    """
    if not layered_texture_node or not cmds.objExists(layered_texture_node):
        return False
    
    # Get connections for both layers
    color_a = cmds.listConnections(f"{layered_texture_node}.inputs[{index_a}].color", source=True, destination=False, plugs=True)
    alpha_a = cmds.listConnections(f"{layered_texture_node}.inputs[{index_a}].alpha", source=True, destination=False, plugs=True)
    color_b = cmds.listConnections(f"{layered_texture_node}.inputs[{index_b}].color", source=True, destination=False, plugs=True)
    alpha_b = cmds.listConnections(f"{layered_texture_node}.inputs[{index_b}].alpha", source=True, destination=False, plugs=True)
    
    # Disconnect all
    if color_a:
        cmds.disconnectAttr(color_a[0], f"{layered_texture_node}.inputs[{index_a}].color")
    if alpha_a:
        cmds.disconnectAttr(alpha_a[0], f"{layered_texture_node}.inputs[{index_a}].alpha")
    if color_b:
        cmds.disconnectAttr(color_b[0], f"{layered_texture_node}.inputs[{index_b}].color")
    if alpha_b:
        cmds.disconnectAttr(alpha_b[0], f"{layered_texture_node}.inputs[{index_b}].alpha")
    
    # Reconnect swapped
    if color_b:
        cmds.connectAttr(color_b[0], f"{layered_texture_node}.inputs[{index_a}].color", force=True)
    if alpha_b:
        cmds.connectAttr(alpha_b[0], f"{layered_texture_node}.inputs[{index_a}].alpha", force=True)
    if color_a:
        cmds.connectAttr(color_a[0], f"{layered_texture_node}.inputs[{index_b}].color", force=True)
    if alpha_a:
        cmds.connectAttr(alpha_a[0], f"{layered_texture_node}.inputs[{index_b}].alpha", force=True)
    
    return True


# --- Existing Setup Scanning ---

def scan_existing_setups():
    """
    Scans the scene for Texelator master groups, including legacy TextureRigger setups.
    
    Returns:
        list: List of dicts with 'master_group', 'mesh', 'prefixes' keys
    """
    setups = []
    
    # Keep legacy scenes editable after the rebrand.
    all_transforms = cmds.ls(type="transform") or []
    for node in all_transforms:
        if (cmds.attributeQuery("isTexelatorSetup", node=node, exists=True) or
                cmds.attributeQuery("isTextureRiggerSetup", node=node, exists=True)):
            setup_info = {'master_group': node, 'mesh': None, 'prefixes': [], 'stage': 'final', 'setup_id': None}
            if cmds.attributeQuery('texelatorStage', node=node, exists=True):
                setup_info['stage'] = cmds.getAttr(f'{node}.texelatorStage') or 'selected_mesh'
            if cmds.attributeQuery('texelatorSetupId', node=node, exists=True):
                setup_info['setup_id'] = cmds.getAttr(f'{node}.texelatorSetupId')
            if cmds.attributeQuery('texelatorMesh', node=node, exists=True):
                stored_mesh = cmds.getAttr(f'{node}.texelatorMesh')
                if stored_mesh and cmds.objExists(stored_mesh):
                    setup_info['mesh'] = stored_mesh
            if cmds.attributeQuery('texelatorData', node=node, exists=True):
                try:
                    setup_info['metadata'] = json.loads(
                        cmds.getAttr(f'{node}.texelatorData') or '{}')
                except (TypeError, ValueError):
                    setup_info['metadata'] = {}
            main_prefixes = set()
            for part in setup_info.get('metadata', {}).get('parts', {}).values():
                if part.get('original_key'):
                    main_prefixes.add(part['original_key'])
                if part.get('guide_key'):
                    main_prefixes.add(part['guide_key'])
            
            node_children = cmds.listRelatives(node, children=True, type="transform", fullPath=True) or []
            
            # Try to find mesh from follicle connections in the RIG group
            for child in node_children:
                if child.split('|')[-1] == "RIG":
                    rig_children = cmds.listRelatives(child, children=True, type="transform") or []
                    for rc in rig_children:
                        rc_short = rc.split('|')[-1]
                        if rc_short.endswith("_Texture_ctrl_grp"):
                            prefix = rc_short.replace("_Texture_ctrl_grp", "")
                            if main_prefixes and prefix not in main_prefixes:
                                continue
                            setup_info['prefixes'].append(prefix)
                            
                            # Find mesh from follicle inputMesh connection
                            if not setup_info['mesh']:
                                follicles = cmds.listRelatives(rc, allDescendents=True, type="follicle") or []
                                for fol_shape in follicles:
                                    mesh_conns = cmds.listConnections(f"{fol_shape}.inputMesh", source=True, destination=False, shapes=True) or []
                                    for mc in mesh_conns:
                                        mesh_transforms = cmds.listRelatives(mc, parent=True, type="transform")
                                        if mesh_transforms:
                                            setup_info['mesh'] = mesh_transforms[0]
                                            break
                                    if setup_info['mesh']:
                                        break
                    break
            
            # Legacy support: also check for GEO group (old setups)
            if not setup_info['mesh']:
                for child in node_children:
                    if child.split('|')[-1] == "GEO":
                        geo_children = cmds.listRelatives(child, children=True, type="transform") or []
                        for geo_child in geo_children:
                            shapes = cmds.listRelatives(geo_child, shapes=True, type="mesh")
                            if shapes:
                                setup_info['mesh'] = geo_child
                                break
                        break

            # A paused guide-stage setup has locators directly under its group.
            if setup_info['stage'] == 'guides':
                guide_nodes = cmds.listRelatives(node, allDescendents=True, type='transform', fullPath=True) or []
                for guide in guide_nodes:
                    short_name = guide.split('|')[-1]
                    if short_name.endswith('_locator'):
                        prefix = short_name[:-len('_locator')]
                        if prefix not in setup_info['prefixes']:
                            setup_info['prefixes'].append(prefix)
            
            setups.append(setup_info)
    
    return setups
