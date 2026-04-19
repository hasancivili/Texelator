import maya.cmds as cmds
import os

def select_image_file():
    """
    Displays a file dialog to select an image file for texturing.
    
    Returns:
        str: Selected file path or None if cancelled
    """
    image_file = cmds.fileDialog2(
        fileMode=1,  # Single existing file
        caption="Select Texture Image",
        fileFilter="Image Files (*.jpg *.jpeg *.png *.tif *.tiff *.exr);;All Files (*.*)",
        dialogStyle=2  # Maya style dialog
    )
    
    if image_file and len(image_file) > 0:
        return image_file[0]
    return None

def select_alpha_image_file():
    """
    Displays a file dialog to select an alpha image file for texturing.
    
    Returns:
        str: Selected file path or None if cancelled
    """
    image_file = cmds.fileDialog2(
        fileMode=1,  # Single existing file
        caption="Select Alpha Texture Image",
        fileFilter="Image Files (*.jpg *.jpeg *.png *.tif *.tiff *.exr);;All Files (*.*)",
        dialogStyle=2  # Maya style dialog
    )
    
    if image_file and len(image_file) > 0:
        return image_file[0]
    return None

def find_next_available_layer(layered_texture_node):
    """
    Finds the next available input layer on a layeredTexture node.
    
    Args:
        layered_texture_node (str): The layeredTexture node name
        
    Returns:
        int: The next available input index (0, 1, 2, etc.)
    """
    index = 0
    while True:
        # Check if this input layer is already connected
        connections = cmds.listConnections(f"{layered_texture_node}.inputs[{index}].color", source=True, destination=False)
        if not connections:
            return index
        index += 1

def get_max_layer_index(layered_texture_node):
    """
    Finds the highest used layer index in a layeredTexture node.
    
    Args:
        layered_texture_node (str): The layeredTexture node name
        
    Returns:
        int: The highest used layer index, or -1 if no layers are used
    """
    max_found = -1
    
    # Get all connected indices efficiently via listAttr
    connected_attrs = cmds.listConnections(layered_texture_node, connections=True, plugs=True, source=True, destination=False) or []
    
    for i in range(0, len(connected_attrs), 2):
        attr = connected_attrs[i]
        # Match pattern like "layeredTexture.inputs[N].color"
        if ".inputs[" in attr and "].color" in attr:
            try:
                idx = int(attr.split(".inputs[")[1].split("]")[0])
                if idx > max_found:
                    max_found = idx
            except (ValueError, IndexError):
                continue
    
    return max_found

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
            print(f"Moved color connection from input[{i}] to input[{i+1}]")
        
        # Handle alpha connections
        alpha_connections = cmds.listConnections(f"{layered_texture_node}.inputs[{i}].alpha", source=True, destination=False, plugs=True)
        if alpha_connections:
            # Disconnect from current index
            cmds.disconnectAttr(alpha_connections[0], f"{layered_texture_node}.inputs[{i}].alpha")
            
            # Reconnect to new index (i+1)
            cmds.connectAttr(alpha_connections[0], f"{layered_texture_node}.inputs[{i+1}].alpha", force=True)
            print(f"Moved alpha connection from input[{i}] to input[{i+1}]")

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
        print(f"Found existing material(s) on mesh '{mesh_transform}': {assigned_materials}")
        material = assigned_materials[0]
    else:
        print(f"No existing materials found on mesh '{mesh_transform}'. Attempting to use or create a default material.")
        
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
                print(f"Mesh '{mesh_transform}' is part of initialShadingGroup. Using its material: '{material}'.")
        
        if not material:
            print(f"Creating a new Lambert material and assigning it to '{mesh_transform}'.")
            mesh_base_name = mesh_transform.split('|')[-1].split(':')[-1]
            new_material_node = None
            new_sg_node = None
            try:
                new_material_node = cmds.shadingNode('lambert', asShader=True, name=f"{mesh_base_name}_autoMat#")
                new_sg_node = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{new_material_node}SG#")
                
                cmds.connectAttr(f"{new_material_node}.outColor", f"{new_sg_node}.surfaceShader", force=True)
                cmds.sets(mesh_transform, edit=True, forceElement=new_sg_node)
                material = new_material_node
                print(f"Successfully created and assigned material '{material}' with SG '{new_sg_node}' to '{mesh_transform}'.")
            except RuntimeError as e:
                print(f"Error creating/assigning new material for '{mesh_transform}': {e}")
                if new_sg_node and cmds.objExists(new_sg_node): cmds.delete(new_sg_node)
                if new_material_node and cmds.objExists(new_material_node): cmds.delete(new_material_node)
                material = None

    return material

def connect_texture_to_mesh(mesh_transform, image_file_path, name_prefix="textureRigger", bind_joint=None):
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
    
    print(f"Using material '{material}' for texture connection")
    
    # Get material name for layered texture naming
    material_name = material.split('|')[-1].split(':')[-1]
    material_prefix = material_name.split('_')[0] if '_' in material_name else material_name
    layered_texture_name = f"{material_prefix}_layeredTexture"
    
    # Check if material already has a texture connected to its baseColor or color
    material_color_attr = None
    if cmds.attributeQuery('baseColor', node=material, exists=True):
        material_color_attr = f"{material}.baseColor"
    elif cmds.attributeQuery('color', node=material, exists=True):
        material_color_attr = f"{material}.color"
    elif cmds.attributeQuery('diffuseColor', node=material, exists=True):
        material_color_attr = f"{material}.diffuseColor"
    
    if not material_color_attr:
        cmds.warning(f"Cannot find color attribute on material '{material}'.")
        return None, None, None, None, None, None
    
    # Check if anything is connected to the color attribute
    material_color_connections = cmds.listConnections(material_color_attr, source=True, destination=False, plugs=True)
    
    # Initialize variables before they are used
    existing_connection_to_layer = False
    layered_texture_node = None
    
    # Check if what's connected is a layeredTexture (from previous runs of this tool)
    if material_color_connections:
        connected_node = material_color_connections[0].split('.')[0]
        if cmds.objectType(connected_node) == 'layeredTexture':
            layered_texture_node = connected_node
            existing_connection_to_layer = True
            print(f"Found existing layeredTexture node '{layered_texture_node}' connected to material")
    
    # Create a file texture node
    file_node = cmds.shadingNode('file', asTexture=True, name=f"{name_prefix}_texture")
    # Set the file path
    cmds.setAttr(f"{file_node}.fileTextureName", image_file_path, type="string")
    
    # Create a place2dTexture node for the file
    place2d_node = cmds.shadingNode('place2dTexture', asUtility=True, name=f"{name_prefix}_place2d")
    
    # Connect place2dTexture to file node
    place2d_attrs = [
        "coverage", "translateFrame", "rotateFrame", "mirrorU", "mirrorV", 
        "stagger", "wrapU", "wrapV", "repeatUV", "offset", "rotateUV", 
        "noiseUV", "vertexUvOne", "vertexUvTwo", "vertexUvThree", 
        "vertexCameraOne", "outUV", "outUvFilterSize"
    ]
    
    for attr in place2d_attrs:
        if cmds.attributeQuery(attr, node=place2d_node, exists=True) and \
           cmds.attributeQuery(attr, node=file_node, exists=True):
            try:
                cmds.connectAttr(f"{place2d_node}.{attr}", f"{file_node}.{attr}", force=True)
            except Exception:
                print(f"Failed to connect {attr}")
    
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
    
    # Handle connection to material based on whether there's an existing texture
    if material_color_connections and not existing_connection_to_layer:
        # There's an existing texture but not a layeredTexture, so create one
        layered_texture_node = cmds.shadingNode('layeredTexture', asTexture=True, name=layered_texture_name)
        
        # Connect the existing texture to layer 1 (index 1)
        existing_texture_out = material_color_connections[0]
        
        # Disconnect existing texture from material
        cmds.disconnectAttr(existing_texture_out, material_color_attr)
        
        # Connect existing texture to layer 1 (not layer 0)
        cmds.connectAttr(existing_texture_out, f"{layered_texture_node}.inputs[1].color", force=True)
        
        # Connect new projection to layer 0 (top layer)
        cmds.connectAttr(f"{projection_node}.outColor", f"{layered_texture_node}.inputs[0].color", force=True)
        
        # Connect projection's outAlpha to layer 0's alpha
        cmds.connectAttr(f"{projection_node}.outAlpha", f"{layered_texture_node}.inputs[0].alpha", force=True)
        
        # Connect layeredTexture to material
        cmds.connectAttr(f"{layered_texture_node}.outColor", material_color_attr, force=True)
        
        print(f"Created layeredTexture with existing texture at layer 1 and new projection at layer 0 (top)")
        print(f"Connected {projection_node}.outAlpha to {layered_texture_node}.inputs[0].alpha")
        
    elif existing_connection_to_layer:
        # Already have a layeredTexture, shift all existing layers down and put new one at index 0
        max_layer_index = get_max_layer_index(layered_texture_node)
        if max_layer_index >= 0:
            # Shift layers down
            shift_layers_down(layered_texture_node, max_layer_index)
            
            # Connect new projection to top layer (index 0)
            cmds.connectAttr(f"{projection_node}.outColor", f"{layered_texture_node}.inputs[0].color", force=True)
            
            # Connect projection's outAlpha to layer 0's alpha
            cmds.connectAttr(f"{projection_node}.outAlpha", f"{layered_texture_node}.inputs[0].alpha", force=True)
            
            print(f"Shifted all layers down and connected new projection to top layer (layer 0)")
            print(f"Connected {projection_node}.outAlpha to {layered_texture_node}.inputs[0].alpha")
        else:
            # If no layers found, just connect to layer 0
            cmds.connectAttr(f"{projection_node}.outColor", f"{layered_texture_node}.inputs[0].color", force=True)
            
            # Connect projection's outAlpha to layer 0's alpha
            cmds.connectAttr(f"{projection_node}.outAlpha", f"{layered_texture_node}.inputs[0].alpha", force=True)
            
            print(f"Connected new projection to layer 0 of empty layeredTexture")
            print(f"Connected {projection_node}.outAlpha to {layered_texture_node}.inputs[0].alpha")
        
    else:
        # No existing texture, create layered texture for future expansion
        layered_texture_node = cmds.shadingNode('layeredTexture', asTexture=True, name=layered_texture_name)
        
        # Connect projection to layer 0
        cmds.connectAttr(f"{projection_node}.outColor", f"{layered_texture_node}.inputs[0].color", force=True)
        
        # Connect projection's outAlpha to layer 0's alpha
        cmds.connectAttr(f"{projection_node}.outAlpha", f"{layered_texture_node}.inputs[0].alpha", force=True)
        
        # Connect layeredTexture to material
        try:
            cmds.connectAttr(f"{layered_texture_node}.outColor", material_color_attr, force=True)
            print(f"Created new layeredTexture with projection at layer 0")
            print(f"Connected {projection_node}.outAlpha to {layered_texture_node}.inputs[0].alpha")
        except Exception as e:
            cmds.warning(f"Failed to connect layered texture to material: {e}")
            # Clean up nodes if connection failed
            cmds.delete(file_node, place2d_node, place3d_node, projection_node, layered_texture_node)
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
            print(f"Created parent constraint '{parent_constraint}' from '{bind_joint}' to '{place3d_node}'")
            
            # Create scale constraint
            scale_constraint = cmds.scaleConstraint(bind_joint, place3d_node, maintainOffset=True)[0]
            print(f"Created scale constraint '{scale_constraint}' from '{bind_joint}' to '{place3d_node}'")
            
        except Exception as e:
            cmds.warning(f"Failed to constrain place3dTexture to bind joint: {e}")
    
    print(f"Connected texture '{os.path.basename(image_file_path)}' to material '{material}' using projection")
    return file_node, projection_node, place2d_node, place3d_node, layered_texture_node, material

# Removed connect_texture_with_alpha function as it's no longer needed.

def organize_scene_hierarchy(mesh_transform, follicle_transform, place3d_node, name_prefix):
    """
    Organizes the scene hierarchy according to specified requirements:
    1. Places mesh under GEO group
    2. Creates RIG group with prefix_Texture_ctrl_grp for follicle
    3. Places place3dTexture under UTIL group (if provided)
    4. Sets follicle shape node visibility to off
    5. Sets UTIL group visibility to off
    
    Args:
        mesh_transform (str): The mesh transform node
        follicle_transform (str): The follicle transform node
        place3d_node (str): The place3dTexture node (can be None for UV-based method)
        name_prefix (str): User-provided prefix for naming
    Returns:
        str: The (potentially updated) full path of the mesh transform.
    """
    if not follicle_transform:
        cmds.warning("Missing follicle node for scene organization.")
        # Return original mesh_transform as we can't be sure of its state if other critical nodes are missing
        return cmds.ls(mesh_transform, long=True)[0] if cmds.objExists(mesh_transform) else mesh_transform

    # This will be the path of the mesh after this function.
    final_mesh_path = mesh_transform # Initialize with the input path

    # 1. GEO group for mesh
    geo_group_name = "GEO"
    geo_group_long_name = ""
    if not cmds.objExists(geo_group_name):
        geo_group_long_name = cmds.group(empty=True, name=geo_group_name, world=True)
    else:
        geo_group_long_name = cmds.ls(geo_group_name, long=True)[0]
    
    if cmds.objExists(mesh_transform):
        # Get current full path of the mesh, in case mesh_transform was a short name
        current_mesh_full_path = cmds.ls(mesh_transform, long=True)[0]
        
        parent_list = cmds.listRelatives(current_mesh_full_path, parent=True, fullPath=True)
        current_parent_full_path = parent_list[0] if parent_list else None

        if current_parent_full_path != geo_group_long_name:
            # cmds.parent returns a list of new full paths of moved objects
            moved_objects = cmds.parent(current_mesh_full_path, geo_group_long_name)
            if moved_objects:
                final_mesh_path = moved_objects[0]
            else:
                cmds.warning(f"Failed to parent '{current_mesh_full_path}' under '{geo_group_long_name}'.")
                final_mesh_path = current_mesh_full_path
        else:
            # Already under the correct GEO group, ensure final_mesh_path is the full path.
            final_mesh_path = current_mesh_full_path
    else:
        cmds.warning(f"Mesh '{mesh_transform}' not found at the start of scene organization.")
        # final_mesh_path remains the original, potentially invalid, mesh_transform
    
    # ... existing code for RIG group ...
    rig_group_name = "RIG"
    rig_group_long_name = ""
    if not cmds.objExists(rig_group_name):
        rig_group_long_name = cmds.group(empty=True, name=rig_group_name, world=True)
    else:
        rig_group_long_name = cmds.ls(rig_group_name, long=True)[0]
    
    texture_ctrl_grp_name = f"{name_prefix}_Texture_ctrl_grp"
    texture_ctrl_grp_long_name = ""
    if not cmds.objExists(texture_ctrl_grp_name):
        texture_ctrl_grp_long_name = cmds.group(empty=True, name=texture_ctrl_grp_name, parent=rig_group_long_name)
    else:
        # Ensure it's parented under RIG if it exists but is not parented correctly
        existing_grp_full_path = cmds.ls(texture_ctrl_grp_name, long=True)[0]
        grp_parent_list = cmds.listRelatives(existing_grp_full_path, parent=True, fullPath=True)
        grp_parent_full_path = grp_parent_list[0] if grp_parent_list else None
        if grp_parent_full_path != rig_group_long_name:
            cmds.parent(existing_grp_full_path, rig_group_long_name)
        texture_ctrl_grp_long_name = cmds.ls(texture_ctrl_grp_name, long=True)[0] # Get full path

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
    if not cmds.objExists(util_group_name):
        util_group_long_name = cmds.group(empty=True, name=util_group_name, world=True)
    else:
        util_group_long_name = cmds.ls(util_group_name, long=True)[0]

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

def setup_sequence_texture(file_node, slide_ctrl, is_sequence=False):
    """
    Sets up a texture file node for sequence playback and connects it to a slide ctrl.
    
    Args:
        file_node (str): The file texture node name
        slide_ctrl (str): The slide control that will drive the frame
        is_sequence (bool): Whether to enable sequence mode
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not cmds.objExists(file_node) or not cmds.objExists(slide_ctrl):
        cmds.warning(f"File node '{file_node}' or slide ctrl '{slide_ctrl}' does not exist.")
        return False
    
    try:
        # Set useFrameExtension based on is_sequence flag
        cmds.setAttr(f"{file_node}.useFrameExtension", 1 if is_sequence else 0)
        
        # Handle Frame attribute on slide_ctrl
        frame_attr = f"{slide_ctrl}.Frame"
        
        # If sequence mode is enabled, create or update the Frame attribute
        if is_sequence:
            # Check if Frame attribute already exists
            if not cmds.attributeQuery("Frame", node=slide_ctrl, exists=True):
                # Create the Frame attribute if it doesn't exist
                cmds.addAttr(slide_ctrl, longName="Frame", attributeType="long", defaultValue=1, 
                           minValue=0, maxValue=9999, keyable=True)
                print(f"Added Frame attribute to {slide_ctrl}")
            
            # Connect Frame attribute to frameExtension
            if not cmds.isConnected(frame_attr, f"{file_node}.frameExtension"):
                cmds.connectAttr(frame_attr, f"{file_node}.frameExtension", force=True)
                print(f"Connected {frame_attr} to {file_node}.frameExtension")
        else:
            # Disconnect if exists and sequence mode is disabled
            if cmds.attributeQuery("Frame", node=slide_ctrl, exists=True):
                if cmds.isConnected(frame_attr, f"{file_node}.frameExtension"):
                    cmds.disconnectAttr(frame_attr, f"{file_node}.frameExtension")
                    print(f"Disconnected {frame_attr} from {file_node}.frameExtension")
                
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
        
        print(f"Successfully hidden and locked specified attributes on {slide_ctrl}")
        return True
    except Exception as e:
        cmds.warning(f"Error hiding/locking attributes on {slide_ctrl}: {e}")
        return False

def run_step3_logic(mesh_transform, image_file_path=None, name_prefix="textureRigger", follicle_transform=None, is_sequence=False):
    """
    Main logic for Step 3: Connects texture and organizes scene.
    
    Args:
        mesh_transform (str): Mesh transform node name
        image_file_path (str, optional): Path to image file
        name_prefix (str, optional): Prefix for node names
        follicle_transform (str, optional): Follicle transform node name
        is_sequence (bool, optional): Whether the texture is a sequence
        
    Returns:
        tuple: (file_node, projection_node, place2d_node, place3d_node, layered_texture, material_node, updated_mesh_transform)
        or (None, None, None, None, None, None, original_mesh_transform_if_failed)
    """
    if not image_file_path:
        cmds.warning("No image file path provided for texture connection.")
        return None, None, None, None, None, None, mesh_transform

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
        return None, None, None, None, None, None, mesh_transform

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
        updated_mesh_path_after_organization = organize_scene_hierarchy(mesh_transform, follicle_transform, place3d_node, name_prefix)
    else:
        cmds.warning(f"Skipping scene organization for prefix '{name_prefix}' due to missing follicle or place3dTexture node.")
            
    return file_node, projection_node, place2d_node, place3d_node, layered_texture, material, updated_mesh_path_after_organization