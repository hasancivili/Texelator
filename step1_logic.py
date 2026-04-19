import maya.cmds as cmds
import maya.OpenMaya as om

# Module-level variables to store reference objects
_ref_follicle_transform = None
_ref_follicle_shape = None
_ref_null_group = None
_ref_mesh_transform = None
_ref_mesh_shape = None

def has_uv_map(mesh_shape):
    """
    Checks if the given mesh has UV coordinates.
    
    Args:
        mesh_shape (str): Name of the mesh shape node
        
    Returns:
        bool: True if the mesh has UV coordinates, False otherwise
    """
    if not cmds.objExists(mesh_shape):
        return False
        
    # Check if the mesh has UVs
    try:
        # Method 1: Check if polyEvaluate returns UV values
        uv_count = cmds.polyEvaluate(mesh_shape, uv=True)
        if isinstance(uv_count, (int, float)) and uv_count > 0:
            return True
            
        # Method 2: Try to get UV sets
        uv_sets = cmds.polyUVSet(mesh_shape, query=True, allUVSets=True)
        if uv_sets and len(uv_sets) > 0:
            # Check if any UV in the first set
            uv_count = cmds.polyEvaluate(mesh_shape, uvcoord=True)
            return isinstance(uv_count, (int, float)) and uv_count > 0
            
        return False
    except Exception as e:
        print(f"Error checking UV map for mesh '{mesh_shape}': {e}")
        return False

def create_reference_follicle(mesh_transform, mesh_shape):
    """
    Creates a reference follicle (PosRefFol) and a null group inside it at UV position 0.5, 0.5.
    
    Args:
        mesh_transform (str): Name of the mesh transform node
        mesh_shape (str): Name of the mesh shape node
        
    Returns:
        tuple: (follicle_transform, follicle_shape, null_group) or (None, None, None) if failed
    """
    global _ref_follicle_transform, _ref_follicle_shape, _ref_null_group
    
    # Check if mesh exists
    if not cmds.objExists(mesh_shape):
        cmds.warning(f"Mesh shape '{mesh_shape}' not found.")
        return None, None, None

    # Check if mesh has UVs
    if not has_uv_map(mesh_shape):
        cmds.warning(f"Mesh shape '{mesh_shape}' does not have UV coordinates.")
        return None, None, None

    try:
        # Create a follicle shape and its parent transform
        follicle_transform = cmds.createNode("transform", name="PosRefFol")
        follicle_shape = cmds.createNode("follicle", name="PosRefFolShape", parent=follicle_transform)
        
        # Connect mesh to follicle
        cmds.connectAttr(f"{mesh_shape}.worldMatrix[0]", f"{follicle_shape}.inputWorldMatrix")
        if cmds.attributeQuery("worldMesh", node=mesh_shape, exists=True):
            cmds.connectAttr(f"{mesh_shape}.worldMesh[0]", f"{follicle_shape}.inputMesh")
        else:
            cmds.connectAttr(f"{mesh_shape}.outMesh", f"{follicle_shape}.inputMesh")
        
        # Connect follicle's outputs to its transform
        cmds.connectAttr(f"{follicle_shape}.outTranslate", f"{follicle_transform}.translate")
        cmds.connectAttr(f"{follicle_shape}.outRotate", f"{follicle_transform}.rotate")
        
        # Set UV position to 0.5, 0.5
        cmds.setAttr(f"{follicle_shape}.parameterU", 0.5)
        cmds.setAttr(f"{follicle_shape}.parameterV", 0.5)
        
        # Create null group inside follicle
        null_group = cmds.group(empty=True, name="PosRefNull", parent=follicle_transform)
        
        print(f"Created reference follicle at UV (0.5, 0.5) on mesh '{mesh_transform}'")
        
        # Store the references globally
        _ref_follicle_transform = follicle_transform
        _ref_follicle_shape = follicle_shape
        _ref_null_group = null_group
        
        return follicle_transform, follicle_shape, null_group
        
    except Exception as e:
        cmds.warning(f"Error creating reference follicle: {e}")
        return None, None, None

def create_locator_at_null_position(name_prefix):
    """
    Creates a locator with the given prefix at the world position of the reference null group.
    
    Args:
        name_prefix (str): Prefix for the locator name
        
    Returns:
        str: Name of the created locator or None if failed
    """
    global _ref_null_group
    
    if not _ref_null_group or not cmds.objExists(_ref_null_group):
        cmds.warning("Reference null group does not exist. Please select mesh first.")
        return None
    
    try:
        # Get world position of null group
        null_world_pos = cmds.xform(_ref_null_group, query=True, worldSpace=True, translation=True)
        
        # Create locator in world space (not parented to follicle)
        locator_name = f"{name_prefix}_locator"
        locator = cmds.spaceLocator(name=locator_name)[0]
        
        # Position locator at null's world position
        cmds.xform(locator, translation=null_world_pos, worldSpace=True)
        
        print(f"Created locator '{locator}' at position: {null_world_pos}")
        return locator
        
    except Exception as e:
        cmds.warning(f"Error creating locator: {e}")
        return None

def run_step1_logic(name_prefix, existing_mesh_transform=None, existing_mesh_shape=None):
    """
    Main function for Step 1 logic:
    - If mesh transform/shape provided, uses them
    - Otherwise uses currently selected mesh
    - Creates reference follicle if it doesn't exist
    - Creates locator with given prefix at the position of reference null
    
    Args:
        name_prefix (str): Prefix for locator name
        existing_mesh_transform (str, optional): Name of mesh transform to use
        existing_mesh_shape (str, optional): Name of mesh shape to use
        
    Returns:
        tuple: (mesh_transform, mesh_shape, locator_name) or (None, None, None) if failed
    """
    global _ref_follicle_transform, _ref_follicle_shape, _ref_null_group, _ref_mesh_transform, _ref_mesh_shape
    
    mesh_transform_to_use = existing_mesh_transform
    mesh_shape_to_use = existing_mesh_shape
    
    # If reference follicle already exists and mesh hasn't changed, skip to creating locator
    if _ref_follicle_transform and _ref_null_group and _ref_mesh_transform == mesh_transform_to_use:
        print(f"Using existing reference follicle on mesh '{_ref_mesh_transform}'")
        locator = create_locator_at_null_position(name_prefix)
        if locator:
            return _ref_mesh_transform, _ref_mesh_shape, locator
        return None, None, None
    
    # Otherwise, create new reference follicle
    follicle_transform, follicle_shape, null_group = create_reference_follicle(mesh_transform_to_use, mesh_shape_to_use)
    
    if follicle_transform and null_group:
        _ref_mesh_transform = mesh_transform_to_use
        _ref_mesh_shape = mesh_shape_to_use
        
        # Now create the locator
        locator = create_locator_at_null_position(name_prefix)
        if locator:
            return mesh_transform_to_use, mesh_shape_to_use, locator
    
    return None, None, None

def clear_reference_follicle():
    """
    Clears the stored references to the follicle and null group.
    This should be called when resetting the tool state.
    """
    global _ref_follicle_transform, _ref_follicle_shape, _ref_null_group, _ref_mesh_transform, _ref_mesh_shape
    
    if _ref_follicle_transform and cmds.objExists(_ref_follicle_transform):
        try:
            cmds.delete(_ref_follicle_transform)
            print(f"Deleted reference follicle '{_ref_follicle_transform}'")
        except Exception as e:
            print(f"Could not delete reference follicle: {e}")
    
    # Clear all references
    _ref_follicle_transform = None
    _ref_follicle_shape = None
    _ref_null_group = None 
    _ref_mesh_transform = None
    _ref_mesh_shape = None
    print("Cleared all reference follicle data")

