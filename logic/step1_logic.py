import maya.cmds as cmds
from .compat import create_compatible_math_node

# Module-level variables to store reference objects
_ref_follicle_transform = None
_ref_follicle_shape = None
_ref_null_group = None


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
        cmds.warning(f"Could not inspect UVs on '{mesh_shape}': {e}")
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

        # PosRefFol is an internal placement reference; it should never clutter the viewport.
        cmds.setAttr(f"{follicle_transform}.visibility", 0)
        
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
        
        return locator
        
    except Exception as e:
        cmds.warning(f"Error creating locator: {e}")
        return None

def clear_reference_follicle():
    """
    Clears the stored references to the follicle and null group.
    This should be called when resetting the tool state.
    """
    global _ref_follicle_transform, _ref_follicle_shape, _ref_null_group
    
    if _ref_follicle_transform and cmds.objExists(_ref_follicle_transform):
        try:
            cmds.delete(_ref_follicle_transform)
        except Exception as e:
            cmds.warning(f"Could not delete reference follicle: {e}")
    
    # Clear all references
    _ref_follicle_transform = None
    _ref_follicle_shape = None
    _ref_null_group = None 


def create_mirrored_locator(original_locator, mesh_transform, mirror_axis='X', mirror_prefix=''):
    """
    Creates a mirrored locator relative to the mesh's bounding box center.
    
    Args:
        original_locator (str): Name of the original locator
        mesh_transform (str): Name of the mesh transform node
        mirror_axis (str): Axis to mirror across ('X', 'Y', or 'Z')
        mirror_prefix (str): Full prefix for the mirrored locator (e.g. 'R_Eye')
        
    Returns:
        str: Name of the mirrored locator or None if failed
    """
    if not original_locator or not cmds.objExists(original_locator):
        cmds.warning(f"Original locator '{original_locator}' not found.")
        return None
    
    if not mesh_transform or not cmds.objExists(mesh_transform):
        cmds.warning(f"Mesh '{mesh_transform}' not found.")
        return None
    
    try:
        # Get mesh bounding box center
        bbox = cmds.exactWorldBoundingBox(mesh_transform)
        center = [(bbox[0]+bbox[3])/2.0, (bbox[1]+bbox[4])/2.0, (bbox[2]+bbox[5])/2.0]
        
        # Get original locator world position
        pos = cmds.xform(original_locator, query=True, worldSpace=True, translation=True)
        
        # Mirror position relative to mesh bbox center
        axis_map = {'X': 0, 'Y': 1, 'Z': 2}
        axis_idx = axis_map.get(mirror_axis.upper(), 0)
        
        mirrored_pos = list(pos)
        mirrored_pos[axis_idx] = 2.0 * center[axis_idx] - pos[axis_idx]
        
        # Create mirrored locator
        mirror_locator_name = f"{mirror_prefix}_locator"
        mirror_locator = cmds.spaceLocator(name=mirror_locator_name)[0]
        cmds.xform(mirror_locator, translation=mirrored_pos, worldSpace=True)
        
        return mirror_locator
        
    except Exception as e:
        cmds.warning(f"Error creating mirrored locator: {e}")
        return None


def connect_mirror_guide(original_locator, guide_locator, mesh_transform, mirror_axis='X', node_prefix='TexelatorMirror'):
    """Drive a guide locator as a live world-space mirror of an editable locator."""
    if not all(cmds.objExists(node) for node in (original_locator, guide_locator, mesh_transform)):
        cmds.warning("Cannot create mirror guide: original, guide, or mesh is missing.")
        return []
    axis_index = {'X': 0, 'Y': 1, 'Z': 2}.get(mirror_axis.upper(), 0)
    axis_names = ('X', 'Y', 'Z')
    bounding_box = cmds.exactWorldBoundingBox(mesh_transform)
    centre = [(bounding_box[i] + bounding_box[i + 3]) / 2.0 for i in range(3)]
    created_nodes = []
    try:
        for index, axis_name in enumerate(axis_names):
            destination = f"{guide_locator}.translate{axis_name}"
            cmds.setAttr(destination, lock=False)
            for source in cmds.listConnections(destination, source=True, destination=False, plugs=True) or []:
                cmds.disconnectAttr(source, destination)
            if index == axis_index:
                invert = cmds.createNode('multiplyDivide', name=f"{node_prefix}_mirror{axis_name}_invert#")
                offset = create_compatible_math_node('addDL', 'addDoubleLinear', f"{node_prefix}_mirror{axis_name}_offset#")
                cmds.setAttr(f"{invert}.input2X", -1)
                cmds.setAttr(f"{offset}.input2", 2.0 * centre[index])
                cmds.connectAttr(f"{original_locator}.translate{axis_name}", f"{invert}.input1X", force=True)
                cmds.connectAttr(f"{invert}.outputX", f"{offset}.input1", force=True)
                cmds.connectAttr(f"{offset}.output", destination, force=True)
                created_nodes.extend([invert, offset])
            else:
                cmds.connectAttr(f"{original_locator}.translate{axis_name}", destination, force=True)
            cmds.setAttr(destination, lock=True, keyable=False, channelBox=False)
        for shape in cmds.listRelatives(guide_locator, shapes=True, fullPath=True) or []:
            cmds.setAttr(f"{shape}.overrideEnabled", 1)
            cmds.setAttr(f"{shape}.overrideColor", 18)
        return created_nodes
    except Exception as error:
        cmds.warning(f"Could not connect mirror guide: {error}")
        for node in created_nodes:
            if cmds.objExists(node):
                cmds.delete(node)
        return []

