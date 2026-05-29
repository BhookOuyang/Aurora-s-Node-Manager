"""Node type mappings for cross-version and cross-tree-type compatibility."""
from typing import Dict, Optional, Tuple


# Cross-version node renames (old_name -> new_name or version mapping)
NODE_RENAME_MAP = {
    # 3.x -> 4.x renames
    "ShaderNodeSeparateRGB": "ShaderNodeSeparateColor",
    "ShaderNodeCombineRGB": "ShaderNodeCombineColor",
    "ShaderNodeHueSaturation": "ShaderNodeHueSaturation",  # Same name, properties changed
    "ShaderNodeTexImage": "ShaderNodeTexImage",  # Same, but projection method changed

    # Geometry nodes renamed/removed
    "GeometryNodeTransferAttribute": "GeometryNodeSampleIndex",  # Replaced in 4.0
    "GeometryNodeAttributeStatistic": "GeometryNodeAttributeStatistic",  # Same name, reworked
    "GeometryNodePointsToVolume": "GeometryNodePointsToVolume",  # Same
    "GeometryNodeDistributePointsOnFaces": "GeometryNodeDistributePointsOnFaces",  # Same

    # Compositor nodes
    "CompositorNodeColorBalance": "CompositorNodeColorBalance",  # Same, method changed
    "CompositorNodeHueSat": "CompositorNodeHueSat",  # Same
}


# Cross-tree-type mappings
# Format: (source_tree_type, target_tree_type) -> {source_node: target_node}
CROSS_TYPE_MAP = {
    # Shader -> Geometry
    ("ShaderNodeTree", "GeometryNodeTree"): {
        "ShaderNodeTexNoise": "GeometryNodeTexNoise",
        "ShaderNodeTexVoronoi": "GeometryNodeTexVoronoi",
        "ShaderNodeTexWave": "GeometryNodeTexWave",
        "ShaderNodeTexMagic": "GeometryNodeTexMagic",
        "ShaderNodeTexBrick": "GeometryNodeTexBrick",
        "ShaderNodeTexChecker": "GeometryNodeTexChecker",
        "ShaderNodeTexGradient": "GeometryNodeTexGradient",
        "ShaderNodeTexMusgrave": "GeometryNodeTexMusgrave",
        "ShaderNodeTexWhiteNoise": "GeometryNodeTexWhiteNoise",
        "ShaderNodeTexImage": "GeometryNodeImageTexture",
        "ShaderNodeValToRGB": "GeometryNodeColorRamp",
        "ShaderNodeRGBCurve": "GeometryNodeRGBCurve",
        "ShaderNodeCurveFloat": "GeometryNodeFloatCurve",
        "ShaderNodeMath": "GeometryNodeMath",
        "ShaderNodeVectorMath": "GeometryNodeVectorMath",
        "ShaderNodeMix": "GeometryNodeMix",
        "ShaderNodeSeparateColor": "GeometryNodeSeparateColor",
        "ShaderNodeCombineColor": "GeometryNodeCombineColor",
        "ShaderNodeSeparateXYZ": "GeometryNodeSeparateXYZ",
        "ShaderNodeCombineXYZ": "GeometryNodeCombineXYZ",
        "ShaderNodeMapping": "GeometryNodeMapping",
        "ShaderNodeNormal": "GeometryNodeNormal",
        "ShaderNodeClamp": "GeometryNodeClamp",
        "ShaderNodeMapRange": "GeometryNodeMapRange",
        "ShaderNodeFloatCurve": "GeometryNodeFloatCurve",
        "ShaderNodeRGB": "GeometryNodeRGB",
        "ShaderNodeValue": "GeometryNodeValue",
        "ShaderNodeBlackbody": "GeometryNodeBlackbody",
        "ShaderNodeVolumeAbsorption": None,  # No geometry equivalent
        "ShaderNodeVolumeScatter": None,
        "ShaderNodeBsdfPrincipled": None,
        "ShaderNodeBsdfDiffuse": None,
        "ShaderNodeBsdfGlossy": None,
        "ShaderNodeBsdfTransparent": None,
        "ShaderNodeBsdfGlass": None,
        "ShaderNodeBsdfRefraction": None,
        "ShaderNodeBsdfAnisotropic": None,
        "ShaderNodeBsdfVelvet": None,
        "ShaderNodeBsdfToon": None,
        "ShaderNodeSubsurfaceScattering": None,
        "ShaderNodeEmission": None,
        "ShaderNodeAmbientOcclusion": None,
        "ShaderNodeHoldout": None,
        "ShaderNodeLayerWeight": None,
        "ShaderNodeFresnel": None,
        "ShaderNodeNewGeometry": None,
        "ShaderNodeLightPath": None,
        "ShaderNodeObjectInfo": "GeometryNodeObjectInfo",
        "ShaderNodeHairInfo": None,
        "ShaderNodeParticleInfo": None,
        "ShaderNodeCameraData": None,
        "ShaderNodeUVMap": None,
        "ShaderNodeTangent": None,
        "ShaderNodeNormalMap": None,
    },

    # Geometry -> Shader
    ("GeometryNodeTree", "ShaderNodeTree"): {
        "GeometryNodeTexNoise": "ShaderNodeTexNoise",
        "GeometryNodeTexVoronoi": "ShaderNodeTexVoronoi",
        "GeometryNodeTexWave": "ShaderNodeTexWave",
        "GeometryNodeTexMagic": "ShaderNodeTexMagic",
        "GeometryNodeTexBrick": "ShaderNodeTexBrick",
        "GeometryNodeTexChecker": "ShaderNodeTexChecker",
        "GeometryNodeTexGradient": "ShaderNodeTexGradient",
        "GeometryNodeTexMusgrave": "ShaderNodeTexMusgrave",
        "GeometryNodeTexWhiteNoise": "ShaderNodeTexWhiteNoise",
        "GeometryNodeImageTexture": "ShaderNodeTexImage",
        "GeometryNodeColorRamp": "ShaderNodeValToRGB",
        "GeometryNodeRGBCurve": "ShaderNodeRGBCurve",
        "GeometryNodeFloatCurve": "ShaderNodeCurveFloat",
        "GeometryNodeMath": "ShaderNodeMath",
        "GeometryNodeVectorMath": "ShaderNodeVectorMath",
        "GeometryNodeMix": "ShaderNodeMix",
        "GeometryNodeSeparateColor": "ShaderNodeSeparateColor",
        "GeometryNodeCombineColor": "ShaderNodeCombineColor",
        "GeometryNodeSeparateXYZ": "ShaderNodeSeparateXYZ",
        "GeometryNodeCombineXYZ": "ShaderNodeCombineXYZ",
        "GeometryNodeMapping": "ShaderNodeMapping",
        "GeometryNodeNormal": "ShaderNodeNormal",
        "GeometryNodeClamp": "ShaderNodeClamp",
        "GeometryNodeMapRange": "ShaderNodeMapRange",
        "GeometryNodeRGB": "ShaderNodeRGB",
        "GeometryNodeValue": "ShaderNodeValue",
        "GeometryNodeBlackbody": "ShaderNodeBlackbody",
        "GeometryNodeObjectInfo": "ShaderNodeObjectInfo",
        # Geometry-only nodes (no shader equivalent)
        "GeometryNodeInputPosition": None,
        "GeometryNodeInputNormal": None,
        "GeometryNodeInputIndex": None,
        "GeometryNodeInputID": None,
        "GeometryNodeInputMaterialIndex": None,
        "GeometryNodeInputRadius": None,
        "GeometryNodeInputShadeSmooth": None,
        "GeometryNodeInputNamedAttribute": None,
        "GeometryNodeSetPosition": None,
        "GeometryNodeSetNormal": None,
        "GeometryNodeSetMaterial": None,
        "GeometryNodeJoinGeometry": None,
        "GeometryNodeSeparateGeometry": None,
        "GeometryNodeDeleteGeometry": None,
        "GeometryNodeDuplicateElements": None,
        "GeometryNodeInstanceOnPoints": None,
        "GeometryNodeRealizeInstances": None,
        "GeometryNodePoints": None,
        "GeometryNodeMeshLine": None,
        "GeometryNodeMeshCircle": None,
        "GeometryNodeMeshCube": None,
        "GeometryNodeMeshUVSphere": None,
        "GeometryNodeMeshIcoSphere": None,
        "GeometryNodeMeshCylinder": None,
        "GeometryNodeMeshCone": None,
        "GeometryNodeMeshGrid": None,
        "GeometryNodeCurveCircle": None,
        "GeometryNodeCurveLine": None,
        "GeometryNodeCurveArc": None,
        "GeometryNodeCurveSpiral": None,
        "GeometryNodeCurveQuadraticBezier": None,
        "GeometryNodeCurveCubicBezier": None,
        "GeometryNodeCurveBezierSegment": None,
        "GeometryNodeCurveSplineType": None,
        "GeometryNodeCurveSetHandles": None,
        "GeometryNodeCurveToMesh": None,
        "GeometryNodeCurveToPoints": None,
        "GeometryNodeMeshToCurve": None,
        "GeometryNodeMeshToPoints": None,
        "GeometryNodePointsToVertices": None,
        "GeometryNodePointsToVolume": None,
        "GeometryNodeVolumeToMesh": None,
        "GeometryNodeDistributePointsOnFaces": None,
        "GeometryNodeDistributePointsInVolume": None,
        "GeometryNodeDistributePointsInGrid": None,
        "GeometryNodeStringJoin": None,
        "GeometryNodeStringToCurves": None,
        "GeometryNodeStringLength": None,
        "GeometryNodeReplaceString": None,
        "GeometryNodeSliceString": None,
        "GeometryNodeSpecialStringCharacters": None,
        "GeometryNodeValueToString": None,
        "GeometryNodeRandomValue": None,
        "GeometryNodeAccumulateField": None,
        "GeometryNodeFieldAtIndex": None,
        "GeometryNodeFieldOnDomain": None,
        "GeometryNodeSwitch": None,
        "GeometryNodeCompare": None,
        "GeometryNodeBooleanMath": None,
        "GeometryNodeFloatToInt": None,
        "GeometryNodeInterpolateDomain": None,
        "GeometryNodeTransferAttribute": None,  # Removed in 4.0
        "GeometryNodeSampleIndex": None,
        "GeometryNodeSampleNearest": None,
        "GeometryNodeAttributeStatistic": None,
        "GeometryNodeDomainSize": None,
        "GeometryNodeBlurAttribute": None,
        "GeometryNodeCaptureAttribute": None,
        "GeometryNodeRemoveNamedAttribute": None,
        "GeometryNodeStoreNamedAttribute": None,
        "GeometryNodeViewer": None,
        "GeometryNodeTool3DCursor": None,
        "GeometryNodeToolFaceSet": None,
        "GeometryNodeToolMousePosition": None,
        "GeometryNodeToolSelection": None,
        "GeometryNodeToolSetFaceSet": None,
        "GeometryNodeToolSetSelection": None,
        "GeometryNodeSimulationZone": None,
        "GeometryNodeRepeatZone": None,
        "GeometryNodeBake": None,
    },

    # Shader -> Compositor
    ("ShaderNodeTree", "CompositorNodeTree"): {
        "ShaderNodeTexNoise": "CompositorNodeTexNoise",
        "ShaderNodeTexVoronoi": None,
        "ShaderNodeTexWave": None,
        "ShaderNodeTexMagic": None,
        "ShaderNodeTexBrick": None,
        "ShaderNodeTexChecker": None,
        "ShaderNodeTexGradient": None,
        "ShaderNodeTexMusgrave": None,
        "ShaderNodeTexWhiteNoise": None,
        "ShaderNodeTexImage": "CompositorNodeImage",
        "ShaderNodeValToRGB": "CompositorNodeValToRGB",
        "ShaderNodeRGBCurve": "CompositorNodeHueCorrect",  # Approximate
        "ShaderNodeMath": "CompositorNodeMath",
        "ShaderNodeVectorMath": None,
        "ShaderNodeMix": None,
        "ShaderNodeSeparateColor": "CompositorNodeSepRGBA",
        "ShaderNodeCombineColor": "CompositorNodeCombRGBA",
        "ShaderNodeSeparateXYZ": None,
        "ShaderNodeCombineXYZ": None,
        "ShaderNodeMapping": None,
        "ShaderNodeNormal": None,
        "ShaderNodeClamp": None,
        "ShaderNodeMapRange": None,
        "ShaderNodeRGB": "CompositorNodeRGB",
        "ShaderNodeValue": "CompositorNodeValue",
        "ShaderNodeBlackbody": None,
        "ShaderNodeObjectInfo": None,
    },

    # Compositor -> Shader
    ("CompositorNodeTree", "ShaderNodeTree"): {
        "CompositorNodeTexNoise": "ShaderNodeTexNoise",
        "CompositorNodeImage": "ShaderNodeTexImage",
        "CompositorNodeValToRGB": "ShaderNodeValToRGB",
        "CompositorNodeMath": "ShaderNodeMath",
        "CompositorNodeSepRGBA": "ShaderNodeSeparateColor",
        "CompositorNodeCombRGBA": "ShaderNodeCombineColor",
        "CompositorNodeRGB": "ShaderNodeRGB",
        "CompositorNodeValue": "ShaderNodeValue",
        # Compositor-only nodes
        "CompositorNodeRLayers": None,
        "CompositorNodeComposite": None,
        "CompositorNodeViewer": None,
        "CompositorNodeSplit": None,
        "CompositorNodeSwitch": None,
        "CompositorNodeMixRGB": None,
        "CompositorNodeAlphaOver": None,
        "CompositorNodeZcombine": None,
        "CompositorNodeColorBalance": None,
        "CompositorNodeHueSat": None,
        "CompositorNodeBrightContrast": None,
        "CompositorNodeGamma": None,
        "CompositorNodeInvert": None,
        "CompositorNodeCurveRGB": None,
        "CompositorNodeHueCorrect": None,
        "CompositorNodeTonemap": None,
        "CompositorNodePremulKey": None,
        "CompositorNodeLensdist": None,
        "CompositorNodeGlare": None,
        "CompositorNodeSunBeams": None,
        "CompositorNodeBokehBlur": None,
        "CompositorNodeBokehImage": None,
        "CompositorNodeDefocus": None,
        "CompositorNodeDilateErode": None,
        "CompositorNodeInpaint": None,
        "CompositorNodeDespeckle": None,
        "CompositorNodeFilter": None,
        "CompositorNodeBlur": None,
        "CompositorNodeBilateralBlur": None,
        "CompositorNodeVecBlur": None,
        "CompositorNodeDBlur": None,
        "CompositorNodePixelate": None,
        "CompositorNodeMask": None,
        "CompositorNodeKeying": None,
        "CompositorNodeKeyingScreen": None,
        "CompositorNodeChannelMatte": None,
        "CompositorNodeColorMatte": None,
        "CompositorNodeDifferenceMatte": None,
        "CompositorNodeDistanceMatte": None,
        "CompositorNodeLumaMatte": None,
        "CompositorNodeTranslate": None,
        "CompositorNodeRotate": None,
        "CompositorNodeScale": None,
        "CompositorNodeFlip": None,
        "CompositorNodeCrop": None,
        "CompositorNodeDisplace": None,
        "CompositorNodeMapUV": None,
        "CompositorNodePlaneTrackDeform": None,
        "CompositorNodeCornerPin": None,
        "CompositorNodeStabilize2D": None,
        "CompositorNodeMovieClip": None,
        "CompositorNodeMovieDistortion": None,
        "CompositorNodeNormal": None,
        "CompositorNodeNormalize": None,
        "CompositorNodeCryptomatte": None,
        "CompositorNodeCryptomatteV2": None,
        "CompositorNodeAntiAliasing": None,
        "CompositorNodeDenoise": None,
        "CompositorNodeOutputFile": None,
        "CompositorNodeLevels": None,
        "CompositorNodeColorSpill": None,
        "CompositorNodeDoubleEdgeMask": None,
        "CompositorNodeEdgeDetect": None,
        "CompositorNodeEllipseMask": None,
        "CompositorNodeIDMask": None,
        "CompositorNodeBoxMask": None,
        "CompositorNodeTrackPos": None,
        "CompositorNodeTransform": None,
        "CompositorNodeCombineColor": None,
        "CompositorNodeSeparateColor": None,
        "CompositorNodeCombineXYZ": None,
        "CompositorNodeSeparateXYZ": None,
        "CompositorNodeSetAlpha": None,
        "CompositorNodeBokehImage": None,
        "CompositorNodeTime": None,
    },
}


def resolve_node_type(bl_idname: str, target_version: Tuple[int, ...]) -> str:
    """Resolve node type for target Blender version.

    Args:
        bl_idname: Original node type identifier
        target_version: Target Blender version tuple (major, minor, patch)

    Returns:
        Resolved node type string
    """
    # Direct rename mapping
    if bl_idname in NODE_RENAME_MAP:
        return NODE_RENAME_MAP[bl_idname]

    return bl_idname


def get_cross_type_mapping(bl_idname: str, source_tree_type: str, 
                           target_tree_type: str) -> Optional[str]:
    """Get mapped node type for cross-tree-type loading.

    Args:
        bl_idname: Original node type
        source_tree_type: Source tree type (e.g., "ShaderNodeTree")
        target_tree_type: Target tree type (e.g., "GeometryNodeTree")

    Returns:
        Mapped node type or None if no mapping exists
    """
    key = (source_tree_type, target_tree_type)
    if key not in CROSS_TYPE_MAP:
        return None

    mapping = CROSS_TYPE_MAP[key]
    return mapping.get(bl_idname)


def get_available_cross_type_nodes(source_tree_type: str, target_tree_type: str) -> Dict[str, str]:
    """Get all available cross-type mappings.

    Returns:
        Dictionary of {source_node: target_node} for valid mappings only
    """
    key = (source_tree_type, target_tree_type)
    if key not in CROSS_TYPE_MAP:
        return {}

    return {k: v for k, v in CROSS_TYPE_MAP[key].items() if v is not None}
