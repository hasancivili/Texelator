import maya.cmds as cmds
import maya.OpenMaya as om

def get_uv_at_point(mesh_shape, world_point_mvector):
    """
    Finds the closest UV coordinate on the mesh for a given world space point.

    Args:
        mesh_shape (str): Name of the mesh shape node.
        world_point_mvector (om.MVector): Point in world space.

    Returns:
        tuple (float, float) or None: (u, v) UV coordinates or None if not found.
    """
    if not cmds.objExists(mesh_shape):
        cmds.warning(f"Mesh shape '{mesh_shape}' not found.")
        return None

    cpos_node = None # Define here so it can be deleted in case of error
    try:
        # Create closestPointOnMesh node
        cpos_node = cmds.createNode("closestPointOnMesh")
        
        # Get mesh transform node
        mesh_transform = cmds.listRelatives(mesh_shape, parent=True, fullPath=True)[0]
        
        # Connect worldMatrix of mesh transform to node
        cmds.connectAttr(f"{mesh_transform}.worldMatrix[0]", f"{cpos_node}.inputMatrix")
        
        # Mesh connection
        mesh_attr_to_connect = ""
        if cmds.attributeQuery("worldMesh", node=mesh_shape, exists=True):
            mesh_attr_to_connect = f"{mesh_shape}.worldMesh[0]"
        elif cmds.attributeQuery("outMesh", node=mesh_shape, exists=True):
            mesh_attr_to_connect = f"{mesh_shape}.outMesh"
        else:
            cmds.warning(f"Could not find appropriate mesh output attribute on mesh shape '{mesh_shape}' (worldMesh[0] or outMesh).")
            if cpos_node and cmds.objExists(cpos_node): cmds.delete(cpos_node)
            return None
            
        cmds.connectAttr(mesh_attr_to_connect, f"{cpos_node}.inMesh")
        
        # Set input position (world space)
        cmds.setAttr(f"{cpos_node}.inPositionX", world_point_mvector.x)
        cmds.setAttr(f"{cpos_node}.inPositionY", world_point_mvector.y)
        cmds.setAttr(f"{cpos_node}.inPositionZ", world_point_mvector.z)
        
        # Get UV coordinates
        u_val = cmds.getAttr(f"{cpos_node}.result.parameterU")
        v_val = cmds.getAttr(f"{cpos_node}.result.parameterV")
        
        if u_val is not None and v_val is not None:
            print(f"Found UV coordinates ({u_val}, {v_val}) for point ({world_point_mvector.x}, {world_point_mvector.y}, {world_point_mvector.z})")
            return float(u_val), float(v_val)
        else:
            cmds.warning(f"Could not get UV coordinates using closestPointOnMesh node.")
            return None

    except Exception as e:
        cmds.warning(f"Error getting UV from world point: {e}")
        return None
    finally:
        if cpos_node and cmds.objExists(cpos_node):
            cmds.delete(cpos_node)

def create_follicle_at_uv(mesh_shape_name, u_coord, v_coord, name_prefix="textureRigger"):
    """
    Creates a follicle and a null group inside it on the specified mesh at the given UV coordinates.
    
    Args:
        mesh_shape_name (str): Name of the mesh shape node.
        u_coord (float): U coordinate.
        v_coord (float): V coordinate.
        name_prefix (str, optional): Name prefix for the follicle. Defaults to "textureRigger".
    
    Returns:
        tuple: (follicle_transform_name, parent_group_name) or (None, None)
    """
    if not cmds.objExists(mesh_shape_name):
        cmds.warning(f"Mesh shape '{mesh_shape_name}' not found for creating follicle.")
        return None, None

    # Clean and use the name prefix
    clean_prefix = name_prefix if name_prefix else "textureRigger"
    follicle_name = f"{clean_prefix}_follicle#"

    # Create follicle shape and transform
    follicle_transform_name = cmds.createNode("transform", name=follicle_name)
    follicle_shape_name = cmds.createNode("follicle", name=f"{follicle_transform_name}Shape", parent=follicle_transform_name)

    # Mesh connections
    # Connect mesh's worldMesh or outMesh attribute to follicle's inputMesh
    if cmds.attributeQuery("worldMesh", node=mesh_shape_name, exists=True):
        cmds.connectAttr(f"{mesh_shape_name}.worldMesh[0]", f"{follicle_shape_name}.inputMesh")
    elif cmds.attributeQuery("outMesh", node=mesh_shape_name, exists=True):
        cmds.connectAttr(f"{mesh_shape_name}.outMesh", f"{follicle_shape_name}.inputMesh")
    else:
        cmds.warning(f"Could not find appropriate output attribute on mesh '{mesh_shape_name}' for follicle.")
        cmds.delete(follicle_transform_name)
        return None, None

    # Connect mesh's worldMatrix to follicle's inputWorldMatrix
    mesh_transform_name = cmds.listRelatives(mesh_shape_name, parent=True, fullPath=True)[0]
    cmds.connectAttr(f"{mesh_transform_name}.worldMatrix[0]", f"{follicle_shape_name}.inputWorldMatrix")

    # Connect follicle's outTranslate and outRotate to transform node
    cmds.connectAttr(f"{follicle_shape_name}.outTranslate", f"{follicle_transform_name}.translate")
    cmds.connectAttr(f"{follicle_shape_name}.outRotate", f"{follicle_transform_name}.rotate")

    # Set UV values
    cmds.setAttr(f"{follicle_shape_name}.parameterU", u_coord)
    cmds.setAttr(f"{follicle_shape_name}.parameterV", v_coord)

    # Create an empty "parent_grp" group (null group) inside the follicle
    parent_grp_name = cmds.group(empty=True, name=f"{clean_prefix}_parent_grp#")
    cmds.parent(parent_grp_name, follicle_transform_name)
    # Reset the group (relative to follicle)
    cmds.setAttr(f"{parent_grp_name}.translate", 0, 0, 0)
    cmds.setAttr(f"{parent_grp_name}.rotate", 0, 0, 0)
    cmds.setAttr(f"{parent_grp_name}.scale", 1, 1, 1)

    print(f"Follicle '{follicle_transform_name}' and parent group '{parent_grp_name}' created at UV ({u_coord}, {v_coord}).")
    return follicle_transform_name, parent_grp_name

def setup_follicle_connections(follicle_transform, follicle_shape, node_prefix):
    """
    Creates advanced connections and controller for the follicle.
    
    Args:
        follicle_transform (str): Name of the follicle transform node.
        follicle_shape (str): Name of the follicle shape node.
        node_prefix (str): Name prefix to be used for nodes created inside.
    
    Returns:
        tuple: (slide_ctrl_name, bind_joint_name) if successful, otherwise (None, None)
    """
    try:
        # Organize node names
        # base_name = follicle_transform.split('|')[-1].split(':')[-1]  # Name without namespace and full path
        # if not base_name: 
        #     base_name = "follicleSetup"
        #     print(f"Valid name not found, using default name: {base_name}")
        base_name = node_prefix # Use the incoming prefix directly

        compose_matrix_node = cmds.createNode("composeMatrix", name=f"{base_name}_compMat")
        mult_matrix_node = cmds.createNode("multMatrix", name=f"{base_name}_multMat")
        decompose_matrix_node = cmds.createNode("decomposeMatrix", name=f"{base_name}_decomMat")

        cmds.connectAttr(f"{follicle_shape}.outRotate", f"{compose_matrix_node}.inputRotate", force=True)
        cmds.connectAttr(f"{follicle_shape}.outTranslate", f"{compose_matrix_node}.inputTranslate", force=True)
        cmds.connectAttr(f"{compose_matrix_node}.outputMatrix", f"{mult_matrix_node}.matrixIn[0]", force=True)
        cmds.connectAttr(f"{follicle_transform}.parentInverseMatrix[0]", f"{mult_matrix_node}.matrixIn[1]", force=True)
        cmds.connectAttr(f"{mult_matrix_node}.matrixSum", f"{decompose_matrix_node}.inputMatrix", force=True)

        # Unlock translate and rotate locks
        for attr_comp in ["translate", "rotate"]:
            for axis in ["X", "Y", "Z"]:
                attr_full_name = f"{follicle_transform}.{attr_comp}{axis}"
                if cmds.getAttr(attr_full_name, lock=True):
                    cmds.setAttr(attr_full_name, lock=False)

        # Remove existing connections
        if cmds.isConnected(f"{follicle_shape}.outTranslate", f"{follicle_transform}.translate"):
            cmds.disconnectAttr(f"{follicle_shape}.outTranslate", f"{follicle_transform}.translate")
        if cmds.isConnected(f"{follicle_shape}.outRotate", f"{follicle_transform}.rotate"):
            cmds.disconnectAttr(f"{follicle_shape}.outRotate", f"{follicle_transform}.rotate")

        cmds.connectAttr(f"{decompose_matrix_node}.outputTranslate", f"{follicle_transform}.translate", force=True)
        cmds.connectAttr(f"{decompose_matrix_node}.outputRotate", f"{follicle_transform}.rotate", force=True)

        position_grp = cmds.group(empty=True, name=f"{base_name}_position_grp", parent=follicle_transform)
        invert_grp = cmds.group(empty=True, name=f"{base_name}_Invert_grp", parent=position_grp)
        slide_ctrl_result = cmds.circle(name=f"{base_name}_Slide_ctrl", normal=(0, 1, 0), radius=1)
        
        if not slide_ctrl_result:
            cmds.warning("Failed to create Slide_ctrl.")
            return None, None
            
        slide_ctrl = slide_ctrl_result[0]
        cmds.parent(slide_ctrl, invert_grp)

        cmds.addAttr(slide_ctrl, longName="Precision", attributeType="float", defaultValue=0.8)
        cmds.setAttr(f"{slide_ctrl}.Precision", keyable=True)

        translate_invert_node = cmds.createNode("multiplyDivide", name=f"{base_name}_Translate_Invert")
        cmds.setAttr(f"{translate_invert_node}.input2X", -1)
        cmds.setAttr(f"{translate_invert_node}.input2Y", -1)
        cmds.setAttr(f"{translate_invert_node}.input2Z", -1)
        cmds.connectAttr(f"{slide_ctrl}.translate", f"{translate_invert_node}.input1", force=True)
        cmds.connectAttr(f"{translate_invert_node}.output", f"{invert_grp}.translate", force=True)

        invert_u_node = cmds.createNode("multDoubleLinear", name=f"{base_name}_Invert_U")
        invert_v_node = cmds.createNode("multDoubleLinear", name=f"{base_name}_Invert_V")
        cmds.connectAttr(f"{slide_ctrl}.translateX", f"{invert_u_node}.input1", force=True)
        cmds.connectAttr(f"{slide_ctrl}.translateY", f"{invert_v_node}.input1", force=True)
        cmds.setAttr(f"{invert_u_node}.input2", 1)
        cmds.setAttr(f"{invert_v_node}.input2", 1)

        precision_u_node = cmds.createNode("multDoubleLinear", name=f"{base_name}_Precision_U")
        precision_v_node = cmds.createNode("multDoubleLinear", name=f"{base_name}_Precision_V")
        cmds.connectAttr(f"{invert_u_node}.output", f"{precision_u_node}.input1", force=True)
        cmds.connectAttr(f"{invert_v_node}.output", f"{precision_v_node}.input1", force=True)
        cmds.connectAttr(f"{slide_ctrl}.Precision", f"{precision_u_node}.input2", force=True)
        cmds.connectAttr(f"{slide_ctrl}.Precision", f"{precision_v_node}.input2", force=True)

        pos_u_node = cmds.createNode("addDoubleLinear", name=f"{base_name}_pos_U_driver")
        pos_v_node = cmds.createNode("addDoubleLinear", name=f"{base_name}_pos_V_driver")
        cmds.connectAttr(f"{precision_u_node}.output", f"{pos_u_node}.input1", force=True)
        cmds.connectAttr(f"{precision_v_node}.output", f"{pos_v_node}.input1", force=True)

        # Get current UV values of the follicle shape
        param_u = cmds.getAttr(f"{follicle_shape}.parameterU")
        param_v = cmds.getAttr(f"{follicle_shape}.parameterV")

        # Set AddDoubleLinear input2 values (current UV positions)
        cmds.setAttr(f"{pos_u_node}.input2", param_u)
        cmds.setAttr(f"{pos_v_node}.input2", param_v)

        clamp_node = cmds.createNode("clamp", name=f"{base_name}_clamp")
        cmds.connectAttr(f"{pos_u_node}.output", f"{clamp_node}.inputR", force=True)  # inputR for U
        cmds.connectAttr(f"{pos_v_node}.output", f"{clamp_node}.inputG", force=True)  # inputG for V
        cmds.setAttr(f"{clamp_node}.minR", 0)
        cmds.setAttr(f"{clamp_node}.minG", 0)
        cmds.setAttr(f"{clamp_node}.minB", 0)
        cmds.setAttr(f"{clamp_node}.maxR", 1)
        cmds.setAttr(f"{clamp_node}.maxG", 1)
        cmds.setAttr(f"{clamp_node}.maxB", 1)
        cmds.connectAttr(f"{clamp_node}.outputR", f"{follicle_shape}.parameterU", force=True)
        cmds.connectAttr(f"{clamp_node}.outputG", f"{follicle_shape}.parameterV", force=True)

        cmds.setAttr(f"{slide_ctrl}.translate", 0, 0, 0, type="double3")
        cmds.setAttr(f"{slide_ctrl}.rotate", 0, 0, 0, type="double3")
        cmds.makeIdentity(slide_ctrl, apply=True, translate=True, rotate=True, scale=False)

        cmds.setAttr(f"{position_grp}.rotateZ", 180)
        cmds.setAttr(f"{position_grp}.translateZ", 0)
        cmds.setAttr(f"{position_grp}.scale", 1, 1, 1, type="double3")

        bind_joint_result = cmds.joint(name=f"{base_name}_bind")
        if not bind_joint_result:
            cmds.warning("Failed to create bind joint.")
            bind_joint = None
        else:
            bind_joint = bind_joint_result
            if isinstance(bind_joint_result, list):
                bind_joint = bind_joint_result[0]
                
            cmds.setAttr(f"{bind_joint}.drawStyle", 2)
            cmds.parent(bind_joint, slide_ctrl)
            cmds.setAttr(f"{bind_joint}.translate", 0, 0, 0, type="double3")
            cmds.setAttr(f"{bind_joint}.rotate", 0, 0, 0, type="double3")
            cmds.setAttr(f"{bind_joint}.jointOrient", 0, 0, 0, type="double3")

        curve_obj_shape_list = cmds.listRelatives(slide_ctrl, shapes=True, type="nurbsCurve", fullPath=True)
        if not curve_obj_shape_list:
            print(f"No NURBS curve shape found under Slide_ctrl '{slide_ctrl}'. Skipping CV manipulation.")
        else:
            curve_obj_shape = curve_obj_shape_list[0]
            cv_list = cmds.ls(f"{curve_obj_shape}.cv[*]", flatten=True)
            
            # Find curve center
            try:
                curve_transform = cmds.listRelatives(curve_obj_shape, parent=True, fullPath=True)[0]
                curve_center = cmds.objectCenter(curve_transform, gl=True)
            except Exception:
                # Manual calculation if objectCenter fails
                bb = cmds.exactWorldBoundingBox(slide_ctrl)
                curve_center = [(bb[0]+bb[3])/2, (bb[1]+bb[4])/2, (bb[2]+bb[5])/2]

            # Scale up CVs for better visibility
            for cv in cv_list:
                cv_pos = cmds.pointPosition(cv, world=True)
                new_pos = [
                    (cv_pos[0] - curve_center[0]) * 3 + curve_center[0],
                    (cv_pos[1] - curve_center[1]) * 3 + curve_center[1],
                    (cv_pos[2] - curve_center[2]) * 3 + curve_center[2]
                ]
                cmds.xform(cv, worldSpace=True, translation=new_pos)
            
            # Rotate CVs
            cmds.rotate(90, 0, 0, f"{curve_obj_shape}.cv[*]", relative=True, objectSpace=True)
            cmds.move(0, 0, 0.02, f"{curve_obj_shape}.cv[*]", relative=True, objectSpace=True, worldSpaceDistance=True)
            print("Curve CV manipulation successfully applied.")

        print(f"Advanced follicle setup applied for '{follicle_transform}'.")
        return slide_ctrl, bind_joint
        
    except Exception as e:
        cmds.warning(f"Error creating advanced follicle connections: {e}")
        return None, None

def run_step2_logic(mesh_shape_name, locator_name, name_prefix="textureRigger"):
    """
    Runs the main logic of Step 2: Get UV from locator position, create follicle
    and apply advanced follicle connections.
    
    Args:
        mesh_shape_name (str): Name of the mesh shape node.
        locator_name (str): Name of the locator transform node.
        name_prefix (str, optional): Name prefix for objects to be created. Defaults to "textureRigger".
    
    Returns:
        tuple: (follicle_transform_name, slide_ctrl_name) or (None, None)
    """
    if not mesh_shape_name or not cmds.objExists(mesh_shape_name):
        cmds.warning("No valid mesh shape name provided for Step 2 or mesh not found.")
        return None, None
    if not locator_name or not cmds.objExists(locator_name):
        cmds.warning("No valid locator name provided for Step 2 or locator not found.")
        return None, None

    # Get the world space position of the locator
    locator_pos_list = cmds.xform(locator_name, query=True, translation=True, worldSpace=True)
    if not locator_pos_list or len(locator_pos_list) != 3:
        cmds.warning(f"Could not get position of locator '{locator_name}'.")
        return None, None
    
    locator_world_point = om.MVector(locator_pos_list[0], locator_pos_list[1], locator_pos_list[2])

    # Find the corresponding UV on the mesh for this world position
    uv_coords = get_uv_at_point(mesh_shape_name, locator_world_point)

    actual_prefix = name_prefix if name_prefix else "uv"

    if uv_coords:
        u, v = uv_coords
        print(f"UV corresponding to locator position: ({u}, {v})")
        
        # 1. Create follicle and parent_grp
        follicle_transform, initial_parent_group = create_follicle_at_uv(mesh_shape_name, u, v, name_prefix) # Pass original name_prefix for follicle creation
        if follicle_transform and initial_parent_group:
            follicle_shape_list = cmds.listRelatives(follicle_transform, shapes=True, type="follicle", fullPath=True)
            if not follicle_shape_list:
                cmds.warning(f"Could not find follicle shape for follicle transform '{follicle_transform}'.")
                # Clean up created objects
                if cmds.objExists(follicle_transform): cmds.delete(follicle_transform)
                return None, None
            
            follicle_shape = follicle_shape_list[0]
            
            # 2. Apply advanced follicle connections
            slide_ctrl, bind_joint = setup_follicle_connections(follicle_transform, follicle_shape, actual_prefix) # Pass actual_prefix for internal nodes
            
            if slide_ctrl:
                # Delete parent_grp if it's no longer used
                if initial_parent_group and cmds.objExists(initial_parent_group):
                    cmds.delete(initial_parent_group)
                    print(f"Initial parent_grp '{initial_parent_group}' deleted.")
                
                # Select the slide control object
                cmds.select(slide_ctrl, replace=True)
                return follicle_transform, slide_ctrl
            else:
                # If advanced setup fails, continue with basic follicle and parent_grp
                cmds.select(follicle_transform, replace=True)
                return follicle_transform, initial_parent_group
        else:
            cmds.warning("Could not create follicle and parent group.")
            return None, None
    else:
        cmds.warning(f"Could not find UV coordinate on mesh '{mesh_shape_name}' for locator position.")
        return None, None

