import maya.cmds as cmds
import os
from . import step3_logic

def create_texture_uv_setup(prefix, follicle_transform, slide_ctrl):
    """
    Creates the UV reference setup for the given prefix.
    
    Args:
        prefix (str): The prefix for naming nodes
        follicle_transform (str): The follicle transform node
        slide_ctrl (str): The slide control node
        
    Returns:
        dict: Dictionary containing the created nodes
    """
    # Create the UV reference group and controls
    uv_ref = cmds.group(empty=True, name=f'{prefix}_UV_Ref')
    
    # Create the texture rotate group
    tex_rotate = cmds.group(empty=True, name=f'{prefix}_Texture_Rotate')
    cmds.parent(tex_rotate, uv_ref)
    cmds.setAttr(f'{tex_rotate}.translateX', 0.5)
    cmds.setAttr(f'{tex_rotate}.translateY', 0.5)
    cmds.makeIdentity(tex_rotate, apply=True, translate=True)
    
    # Create the texture reference group
    tex_ref = cmds.group(empty=True, name=f'{prefix}_Texture_Ref')
    cmds.parent(tex_ref, tex_rotate)
    cmds.setAttr(f'{tex_ref}.translateX', -0.5)
    cmds.setAttr(f'{tex_ref}.translateY', -0.5)
    
    # Create the texture control group
    tex_ctrl = cmds.group(empty=True, name=f'{prefix}_Texture_Control')
    cmds.parent(tex_ctrl, uv_ref)
    
    # Create constraints
    parent_constraint = cmds.parentConstraint(tex_ctrl, tex_ref, maintainOffset=True, name=f'{prefix}_ParentConstraint')[0]
    scale_constraint = cmds.scaleConstraint(tex_ctrl, tex_ref, maintainOffset=True, name=f'{prefix}_ScaleConstraint')[0]
    orient_constraint = cmds.orientConstraint(tex_ctrl, tex_rotate, maintainOffset=True, name=f'{prefix}_OrientConstraint')[0]
    
    # Group constraints
    constraints_grp = cmds.group(empty=True, name=f'{prefix}_Constraints')
    cmds.parent([parent_constraint, scale_constraint, orient_constraint], constraints_grp)
    cmds.parent(constraints_grp, uv_ref)
    
    # Add custom attributes
    custom_attrs = [
        'TranslateU', 'TranslateV',
        'ScaleU', 'ScaleV',
        'RotateFrame'
    ]
    
    for attr in custom_attrs:
        if not cmds.objExists(f'{tex_ref}.{attr}'):
            cmds.addAttr(tex_ref, longName=attr, attributeType='double', keyable=True)
    
    # Connect attributes
    cmds.connectAttr(f'{tex_ref}.translateX', f'{tex_ref}.TranslateU', force=True)
    cmds.connectAttr(f'{tex_ref}.translateY', f'{tex_ref}.TranslateV', force=True)
    cmds.connectAttr(f'{tex_ref}.scaleX', f'{tex_ref}.ScaleU', force=True)
    cmds.connectAttr(f'{tex_ref}.scaleY', f'{tex_ref}.ScaleV', force=True)
    
    # Create reverse rotation connection
    md_node = cmds.createNode('multiplyDivide', name=f'{prefix}_ReverseRotate_md')
    cmds.setAttr(f'{md_node}.input2X', -1)
    cmds.connectAttr(f'{tex_rotate}.rotateZ', f'{md_node}.input1X', force=True)
    cmds.connectAttr(f'{md_node}.outputX', f'{tex_ref}.RotateFrame', force=True)
    
    # Hide original transform attributes
    for attr in ['translateX', 'translateY', 'translateZ',
                 'rotateX', 'rotateY', 'rotateZ',
                 'scaleX', 'scaleY', 'scaleZ']:
        cmds.setAttr(f'{tex_ref}.{attr}', keyable=False, channelBox=False)
    
    # Connect follicle UV parameters to texture control
    follicle_shapes = cmds.listRelatives(follicle_transform, shapes=True, type="follicle") or []
    if follicle_shapes:
        follicle_shape = follicle_shapes[0]
        cmds.connectAttr(f'{follicle_shape}.parameterU', f'{tex_ctrl}.translateX', force=True)
        cmds.connectAttr(f'{follicle_shape}.parameterV', f'{tex_ctrl}.translateY', force=True)
    
    # Connect slide control to texture control
    scale_md = None
    if cmds.objExists(slide_ctrl):
        # Connect rotation directly
        cmds.connectAttr(f'{slide_ctrl}.rotateZ', f'{tex_ctrl}.rotateZ', force=True)
        
        # Connect scale through multiply node
        scale_md = cmds.createNode('multiplyDivide', name=f'{prefix}_ScaleFactor_md')
        cmds.setAttr(f'{scale_md}.input2X', 0.1)
        cmds.setAttr(f'{scale_md}.input2Y', 0.1)
        cmds.setAttr(f'{scale_md}.input2Z', 0.1)
        
        cmds.connectAttr(f'{slide_ctrl}.scale', f'{scale_md}.input1', force=True)
        cmds.connectAttr(f'{scale_md}.output', f'{tex_ctrl}.scale', force=True)
    
    return {
        'uv_ref': uv_ref,
        'tex_rotate': tex_rotate,
        'tex_ref': tex_ref,
        'tex_ctrl': tex_ctrl,
        'constraints_grp': constraints_grp,
        'reverse_rotation_node': md_node,
        'scale_factor_node': scale_md
    }

def connect_texture_using_uvs(mesh_transform, image_file_path, name_prefix, follicle_transform=None):
    """
    Connects texture using UV-based method instead of projection.
    
    Args:
        mesh_transform (str): The transform node of the mesh
        image_file_path (str): Full path to the image file
        name_prefix (str): Prefix for naming created nodes
        follicle_transform (str): Name of the follicle transform node
        
    Returns:
        tuple: (file_node, place2d_node, tex_ref_setup, layered_texture, material_node, uv_ref_group)
    """
    if not mesh_transform or not cmds.objExists(mesh_transform):
        cmds.warning(f"Mesh '{mesh_transform}' not found.")
        return None, None, None, None, None, None
    
    if not image_file_path or not os.path.exists(image_file_path):
        cmds.warning(f"Image file '{image_file_path}' not found.")
        return None, None, None, None, None, None
    
    # Find or create material for the mesh
    material = step3_logic.find_or_create_material(mesh_transform)
    
    if not material:
        cmds.warning(f"Failed to find, create, or assign a suitable material for mesh '{mesh_transform}'. Cannot connect texture.")
        return None, None, None, None, None, None
    
    file_node, place2d_node = step3_logic.create_file_texture_network(
        image_file_path, name_prefix, black_default=True)
    
    # Find the slide_ctrl
    slide_ctrl = None
    if follicle_transform and cmds.objExists(follicle_transform):
        all_descendants = cmds.listRelatives(follicle_transform, allDescendents=True, type="transform") or []
        for desc in all_descendants:
            if "_Slide_ctrl" in desc:
                slide_ctrl = desc
                break
    
    # Create UV reference setup
    tex_ref_setup = None
    if slide_ctrl:
        tex_ref_setup = create_texture_uv_setup(name_prefix, follicle_transform, slide_ctrl)
        
        # Connect the tex_ref attributes to the place2d node
        tex_ref = tex_ref_setup['tex_ref']
        
        # Connect the RotateFrame attribute
        cmds.connectAttr(f"{tex_ref}.RotateFrame", f"{place2d_node}.rotateFrame", force=True)
        
        # Connect the ScaleU to CoverageU and ScaleV to CoverageV
        cmds.connectAttr(f"{tex_ref}.ScaleU", f"{place2d_node}.coverageU", force=True)
        cmds.connectAttr(f"{tex_ref}.ScaleV", f"{place2d_node}.coverageV", force=True)
        
        # Connect TranslateU to translateFrameU and TranslateV to translateFrameV
        cmds.connectAttr(f"{tex_ref}.TranslateU", f"{place2d_node}.translateFrameU", force=True)
        cmds.connectAttr(f"{tex_ref}.TranslateV", f"{place2d_node}.translateFrameV", force=True)
    else:
        cmds.warning(f"No slide control found for '{name_prefix}'; UV setup was skipped.")

    layered_texture_node = step3_logic.connect_source_to_material_layer(
        material, f'{file_node}.outColor', f'{file_node}.outAlpha')
    if not layered_texture_node:
        cmds.delete(file_node, place2d_node)
        if tex_ref_setup and cmds.objExists(tex_ref_setup.get('uv_ref')):
            cmds.delete(tex_ref_setup['uv_ref'])
        return None, None, None, None, None, None
    
    # Return tuple for the run_step3_logic function to use
    uv_ref_group = tex_ref_setup['uv_ref'] if tex_ref_setup else None
    return file_node, place2d_node, tex_ref_setup, layered_texture_node, material, uv_ref_group

def run_step3_uv_logic(mesh_transform, image_file_path=None, name_prefix="texelator",
                       follicle_transform=None, is_sequence=False, master_group_name=None):
    """
    Main logic for Step 3 UV-based texture connection: Connects texture using UVs and organizes scene.
    
    Args:
        mesh_transform (str): Mesh transform node name
        image_file_path (str, optional): Path to image file
        name_prefix (str, optional): Prefix for node names
        follicle_transform (str, optional): Follicle transform node name
        is_sequence (bool, optional): Whether the texture is a sequence
        
    Returns the UV nodes, material, mesh path and tracked UV setup nodes.
    """
    if not image_file_path:
        cmds.warning("No image file path provided for texture connection.")
        return None, None, None, None, None, None, mesh_transform, {}
    
    file_node, place2d_node, tex_ref_setup, layered_texture, material, uv_ref_group = connect_texture_using_uvs(
        mesh_transform, 
        image_file_path, 
        name_prefix,
        follicle_transform=follicle_transform
    )

    updated_mesh_path_after_organization = mesh_transform 

    if not file_node: 
        cmds.warning(f"Texture connection failed for prefix '{name_prefix}'.")
        return None, None, None, None, None, None, mesh_transform, {}

    # Find slide_ctrl for the follicle
    slide_ctrl = None
    if follicle_transform and cmds.objExists(follicle_transform):
        all_descendants = cmds.listRelatives(follicle_transform, allDescendents=True, type="transform") or []
        for desc in all_descendants:
            if "_Slide_ctrl" in desc:
                slide_ctrl = desc
                break
    
    # Setup sequence texture if needed
    if is_sequence and slide_ctrl and file_node:
        step3_logic.setup_sequence_texture(file_node, slide_ctrl, is_sequence)

    # Hide slide_ctrl attributes if needed
    if slide_ctrl:
        step3_logic.hide_slide_ctrl_attributes(slide_ctrl)
    
    # Use the same organizing function but with None for place3d_node
    if follicle_transform: 
        place3d_node_substitute = None  # No place3dTexture for UV-based method
        updated_mesh_path_after_organization = step3_logic.organize_scene_hierarchy(
            mesh_transform, follicle_transform, place3d_node_substitute,
            name_prefix, master_group_name=master_group_name)
        
    else:
        cmds.warning(f"Skipping scene organization for prefix '{name_prefix}' due to missing follicle node.")
            
    # Return None for projection_node and place3d_node since we're not using them in the UV-based method
    details = {'uv_setup': tex_ref_setup}
    return (file_node, None, place2d_node, None, layered_texture, material,
            updated_mesh_path_after_organization, details)
