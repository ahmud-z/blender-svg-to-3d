from cmath import log
import os
import bpy
import sys
import typing
import inspect
import pkgutil
import importlib
from pathlib import Path
import math
from mathutils import Vector

class SvgTo3d(bpy.types.Operator):
    """My SVG To 3D Script"""
    bl_idname = "object.svg_to_3d"
    bl_label = "Svg to 3d"
    bl_options = {'REGISTER', 'UNDO'}

    def getGeometryCenter(self, obj):
        sumWCoord = [0,0,0]
        numbVert = 0
        if obj.type == 'MESH':
            for vert in obj.data.vertices:
                wmtx = obj.matrix_world
                worldCoord = vert.co * wmtx
                sumWCoord[0] += worldCoord[0]
                sumWCoord[1] += worldCoord[1]
                sumWCoord[2] += worldCoord[2]
                numbVert += 1
            sumWCoord[0] = sumWCoord[0]/numbVert
            sumWCoord[1] = sumWCoord[1]/numbVert
            sumWCoord[2] = sumWCoord[2]/numbVert

        return sumWCoord
    
    def center_origin(self):
        bpy.ops.transform.translate(value=(0, 0, 1), orient_type='GLOBAL')
        
        bpy.context.scene.cursor.location = Vector((0.0, 0.0, 0.0))
        bpy.context.scene.cursor.rotation_euler = Vector((0.0, 0.0, 0.0))
        

    def execute(self, context):
        scene = context.scene
        cursor = scene.cursor.location

        bpy.ops.object.join()
        
        obj = bpy.context.active_object

        obj.scale.x = 20
        obj.scale.y = 20
        obj.scale.z = 20
        obj.rotation_euler[0] = math.radians(90)
        
        self.center_origin()

        bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')

        obj.location.x = 0
        obj.location.y = 0
        obj.location.z = 0

        obj.data.extrude = 0.01
        obj.data.bevel_depth = 0.0005

        bpy.ops.object.convert(target='MESH')

        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='FACE')
        bpy.ops.mesh.select_all(action='SELECT')
        
        bpy.ops.mesh.dissolve_faces()

        bpy.ops.mesh.dissolve_limited()
        
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, type='VERT')
        bpy.ops.mesh.remove_doubles()

        return {'FINISHED'}


__all__ = (
    "init",
    "register",
    "unregister",
)

blender_version = bpy.app.version

modules = None
ordered_classes = [SvgTo3d]

def menu_func(self, context):
    self.layout.operator(SvgTo3d.bl_idname)

def init():
    global modules
    global ordered_classes

    modules = get_all_submodules(Path(__file__).parent)
    ordered_classes = get_ordered_classes_to_register(modules)

def register():
    for cls in ordered_classes:
        bpy.utils.register_class(cls)

    bpy.types.VIEW3D_MT_object.append(menu_func)

    for module in modules:
        if module.__name__ == __name__:
            continue
        if hasattr(module, "register"):
            module.register()

def unregister():
    for cls in reversed(ordered_classes):
        bpy.utils.unregister_class(cls)

    bpy.types.VIEW3D_MT_object.remove(menu_func)

    for module in modules:
        if module.__name__ == __name__:
            continue
        if hasattr(module, "unregister"):
            module.unregister()


# Import modules
#################################################

def get_all_submodules(directory):
    return list(iter_submodules(directory, directory.name))

def iter_submodules(path, package_name):
    for name in sorted(iter_submodule_names(path)):
        yield importlib.import_module("." + name, package_name)

def iter_submodule_names(path, root=""):
    for _, module_name, is_package in pkgutil.iter_modules([str(path)]):
        if is_package:
            sub_path = path / module_name
            sub_root = root + module_name + "."
            yield from iter_submodule_names(sub_path, sub_root)
        else:
            yield root + module_name


# Find classes to register
#################################################

def get_ordered_classes_to_register(modules):
    return toposort(get_register_deps_dict(modules))

def get_register_deps_dict(modules):
    my_classes = set(iter_my_classes(modules))
    my_classes_by_idname = {cls.bl_idname : cls for cls in my_classes if hasattr(cls, "bl_idname")}

    deps_dict = {}
    for cls in my_classes:
        deps_dict[cls] = set(iter_my_register_deps(cls, my_classes, my_classes_by_idname))
    return deps_dict

def iter_my_register_deps(cls, my_classes, my_classes_by_idname):
    yield from iter_my_deps_from_annotations(cls, my_classes)
    yield from iter_my_deps_from_parent_id(cls, my_classes_by_idname)

def iter_my_deps_from_annotations(cls, my_classes):
    for value in typing.get_type_hints(cls, {}, {}).values():
        dependency = get_dependency_from_annotation(value)
        if dependency is not None:
            if dependency in my_classes:
                yield dependency

def get_dependency_from_annotation(value):
    if blender_version >= (2, 93):
        if isinstance(value, bpy.props._PropertyDeferred):
            return value.keywords.get("type")
    else:
        if isinstance(value, tuple) and len(value) == 2:
            if value[0] in (bpy.props.PointerProperty, bpy.props.CollectionProperty):
                return value[1]["type"]
    return None

def iter_my_deps_from_parent_id(cls, my_classes_by_idname):
    if bpy.types.Panel in cls.__bases__:
        parent_idname = getattr(cls, "bl_parent_id", None)
        if parent_idname is not None:
            parent_cls = my_classes_by_idname.get(parent_idname)
            if parent_cls is not None:
                yield parent_cls

def iter_my_classes(modules):
    base_types = get_register_base_types()
    for cls in get_classes_in_modules(modules):
        if any(base in base_types for base in cls.__bases__):
            if not getattr(cls, "is_registered", False):
                yield cls

def get_classes_in_modules(modules):
    classes = set()
    for module in modules:
        for cls in iter_classes_in_module(module):
            classes.add(cls)
    return classes

def iter_classes_in_module(module):
    for value in module.__dict__.values():
        if inspect.isclass(value):
            yield value

def get_register_base_types():
    return set(getattr(bpy.types, name) for name in [
        "Panel", "Operator", "PropertyGroup",
        "AddonPreferences", "Header", "Menu",
        "Node", "NodeSocket", "NodeTree",
        "UIList", "RenderEngine",
        "Gizmo", "GizmoGroup",
    ])


# Find order to register to solve dependencies
#################################################

def toposort(deps_dict):
    sorted_list = []
    sorted_values = set()
    while len(deps_dict) > 0:
        unsorted = []
        for value, deps in deps_dict.items():
            if len(deps) == 0:
                sorted_list.append(value)
                sorted_values.add(value)
            else:
                unsorted.append(value)
        deps_dict = {value : deps_dict[value] - sorted_values for value in unsorted}
    return sorted_list
