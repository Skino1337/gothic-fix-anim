import os
import mathutils
from mathutils import Matrix, Quaternion, Vector
import math
from math import pi
import json
from pathlib import Path

# ---

import bpy

from bpy.types import Operator, AddonPreferences
from bpy.props import StringProperty, IntProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import FCurve, Camera, TimelineMarker, Object


animation_data_dict = {}
node_dict = {}

asc_armature = None
ROTATION_EULER = True


class Impp:
    def __init__(self):
        pass


def load_anim_data(path):
    global animation_data_dict

    animation_data_dict = Path(path).read_text(encoding='utf-8')
    animation_data_dict = json.loads(animation_data_dict)

    assert 'skeleton_data' in animation_data_dict
    assert 'root_translation' in animation_data_dict['skeleton_data']
    assert 'bbox' in animation_data_dict['skeleton_data']
    assert 'min' in animation_data_dict['skeleton_data']['bbox']
    assert 'max' in animation_data_dict['skeleton_data']['bbox']

    assert 'animation_data' in animation_data_dict
    assert 'frame_count' in animation_data_dict['animation_data']
    assert 'fps' in animation_data_dict['animation_data']
    assert 'frames' in animation_data_dict['animation_data']


def get_bone_data(bone_name, frame):
    return_list = [[], []]

    for node_name, node_data in animation_data_dict['animation_data']['frames'].items():
        if node_name.upper() == bone_name.upper():
            if 'translation' in node_data and len(node_data['translation']) > frame:
                return_list[0] = node_data['translation'][frame]
            if 'rotation' in node_data and len(node_data['rotation']) > frame:
                return_list[1] = node_data['rotation'][frame]

    return return_list


def set_animation(armature, bone_name, frame):
    pos, rot = get_bone_data(bone_name, frame)
    have_pos = False
    have_rot = False

    if len(pos) == 3:
        have_pos = True
    if len(rot) == 4:
        have_rot = True

    bone_name_original = bone_name
    bone_name = bone_name.upper()

    if have_pos:
        if bone_name in node_dict and node_dict[bone_name]:
            pos = Vector([f / 100.0 for f in pos])

            node_matrix_translation = Matrix.Translation(node_dict[bone_name]['translation']).to_4x4()
            node_matrix_rotation = node_dict[bone_name]['rotation'].to_matrix().to_4x4()
            node_matrix = node_matrix_translation @ node_matrix_rotation

            frame_matrix_translation = Matrix.Translation(pos).to_4x4()
            frame_matrix_rotation = Quaternion(rot).to_matrix().to_4x4()
            frame_matrix = frame_matrix_translation @ frame_matrix_rotation

            # convert global coordinate to local
            m1 = node_matrix.inverted() @ frame_matrix
            pos = m1.to_translation()
            pos = Vector([-pos.z, pos.x, pos.y])

        # print(f'rot in pos calc: {get_euler_string(m1)}')

    rot_quat = Quaternion()
    if have_rot:
        rot_quat = Quaternion(rot)

        if bone_name in node_dict and node_dict[bone_name] and 'rotation' in node_dict[bone_name]:
            rot_quat = rot_quat @ node_dict[bone_name]['rotation']

        rot_quat = Quaternion(Vector([rot_quat.w, -rot_quat.z, rot_quat.x, rot_quat.y]))

    animation_data = armature.animation_data

    if ROTATION_EULER:
        curve_path_pos = f'pose.bones["{bone_name_original}"].location'
        curve_path_rot = f'pose.bones["{bone_name_original}"].rotation_euler'

        curve_pos = [None, None, None]
        curve_rot = [None, None, None]

        for fc in animation_data.action.fcurves:
            if fc.data_path == curve_path_pos:
                curve_pos[fc.array_index] = fc
            elif fc.data_path == curve_path_rot:
                curve_rot[fc.array_index] = fc

        if have_pos:
            for i in range(len(curve_pos)):
                if not curve_pos[i]:
                    curve_pos[i] = animation_data.action.fcurves.new(curve_path_pos, index=i, action_group=bone_name_original)
                curve_pos[i].keyframe_points.insert(frame, pos[i])

        if have_rot:
            rot_euler = rot_quat.to_euler()

            for i in range(len(curve_rot)):
                if curve_rot[i] is None:
                    curve_rot[i] = animation_data.action.fcurves.new(curve_path_rot, index=i, action_group=bone_name_original)
                curve_rot[i].keyframe_points.insert(frame, rot_euler[i])
    else:
        curve_path_pos = f'pose.bones["{bone_name_original}"].location'
        curve_path_rot = f'pose.bones["{bone_name_original}"].rotation_quaternion'

        curve_pos = [None, None, None]
        curve_rot = [None, None, None, None]

        for fc in animation_data.action.fcurves:
            if fc.data_path == curve_path_pos:
                curve_pos[fc.array_index] = fc
            elif fc.data_path == curve_path_rot:
                curve_rot[fc.array_index] = fc

        if have_pos:
            for i in range(len(curve_pos)):
                if not curve_pos[i]:
                    curve_pos[i] = animation_data.action.fcurves.new(curve_path_pos, index=i, action_group=bone_name_original)
                curve_pos[i].keyframe_points.insert(frame, pos[i])

        if have_rot:
            for i in range(len(curve_rot)):
                if curve_rot[i] is None:
                    curve_rot[i] = animation_data.action.fcurves.new(curve_path_rot, index=i, action_group=bone_name_original)
                curve_rot[i].keyframe_points.insert(frame, rot_quat[i])


def create_skeleton():
    global asc_armature

    def get_parent_node_data(node_name):
        for n_name, n_data in node_dict.items():
            if node_name == n_name:
                if n_data['parent_name'] and n_data['parent_name'] in node_dict:
                    return node_dict[n_data['parent_name']]

        return None

    def get_child_node_data(node_name, tag=None):
        for n_name, n_data in node_dict.items():
            if node_name == n_data['parent_name']:
                if tag:
                    if tag in n_name:
                        return n_data
                else:
                    return n_data

        return None

    def bound_tail(head, tail, limit):
        is_raise = head > tail
        if is_raise:
            if limit >= head:
                return tail
            return max(tail, limit)
        else:
            if limit <= head:
                return tail
            return min(tail, limit)

    for obj in bpy.context.scene.objects:
        if obj.type == 'ARMATURE' and obj.name == 'Armature':
            for bone in obj.data.bones:
                if bone.name.upper().startswith('BIP01'):
                    asc_armature = obj
                    break

    if not asc_armature:
        armature = bpy.data.armatures.new('Armature_temp')
        # armature.display_type = 'STICK'
        rig = bpy.data.objects.new(armature.name, armature)

        bpy.context.collection.objects.link(rig)
        bpy.context.view_layer.objects.active = rig

        armature = None
        for obj in bpy.context.scene.objects:
            if obj.type == 'ARMATURE' and obj.name == 'Armature_temp':
                armature = obj
                break

        assert armature is not None, 'armature not found'

        # ---

        bpy.data.armatures[armature.name].show_names = True
        bpy.data.armatures[armature.name].show_axes = True

        # ---

        # bone edits only in edit mode
        armature.select_set(True)
        bpy.context.view_layer.objects.active = armature
        bpy.ops.object.mode_set(mode='EDIT', toggle=False)

    for index, node in enumerate(animation_data_dict['skeleton_data']['nodes']):
        # print(f'create matrix: {node["name"]}')
        name = node['name']
        translation = node['translation']
        translation = Vector([f / 100.0 for f in translation])
        rotation = Quaternion(node['rotation'])
        parent_name = node['parent_name']

        if index == 0:
            root_translation = animation_data_dict['skeleton_data']['root_translation']
            root_translation = Vector([f / 100.0 for f in root_translation])
            translation = translation + root_translation

        parent_transform_translation = Vector()
        parent_transform_rotation = Quaternion()
        parent_transform_matrix = Matrix()

        if parent_name and parent_name in node_dict:
            if 'transform_translation' in node_dict[parent_name]:
                parent_transform_translation = node_dict[parent_name]['transform_translation']
            if 'transform_rotation' in node_dict[parent_name]:
                parent_transform_rotation = node_dict[parent_name]['transform_rotation']
            if 'transform_matrix' in node_dict[parent_name]:
                parent_transform_matrix = node_dict[parent_name]['transform_matrix']

        transform_translation = parent_transform_rotation @ translation
        transform_translation = parent_transform_translation + transform_translation
        transform_rotation = parent_transform_rotation @ rotation

        transform_matrix = Matrix.Translation(translation) @ rotation.to_matrix().to_4x4()
        transform_matrix = parent_transform_matrix @ transform_matrix

        node_dict[name] = {'parent_name': parent_name, 'translation': translation, 'rotation': rotation,
                           'transform_translation': transform_translation, 'transform_rotation': transform_rotation,
                           'transform_matrix': transform_matrix}
    #
    #     min_pos_y = min(transform_pos.y, min_pos_y)
    #
    # print(f'{min_pos_y=}')

    # create bones for skeleton
    if not asc_armature:
        for node_name, node_data in node_dict.items():
            # if 'BIP01' not in node_name.upper():
            #     continue

            # print(f'create bone: {node_name}')

            bone = armature.data.edit_bones.new(node_name)
            bone.head = [0, 0, 0]
            length = 0.1
            child_node_data = get_child_node_data(node_name)
            if child_node_data:
                length = (node_data['transform_translation'] - child_node_data['transform_translation']).length
            bone.tail = [length, 0, 0]

            # bound without this don't work
            bone.transform(node_data['transform_rotation'].to_matrix())
            bone.translate(node_data['transform_translation'])

            if child_node_data:
                x_bound = bound_tail(bone.head.x, bone.tail.x, child_node_data['transform_translation'].x)
                y_bound = bound_tail(bone.head.y, bone.tail.y, child_node_data['transform_translation'].y)
                z_bound = bound_tail(bone.head.z, bone.tail.z, child_node_data['transform_translation'].z)

                bone.length = abs((node_data['transform_translation'] - Vector([x_bound, y_bound, z_bound])).length)
            else:
                bbox_min = animation_data_dict['skeleton_data']['bbox']['min']
                bbox_min = Vector([f / 100.0 for f in bbox_min])
                bbox_max = animation_data_dict['skeleton_data']['bbox']['max']
                bbox_max = Vector([f / 100.0 for f in bbox_max])
                # bbox have very little values...
                parent_node_data = get_parent_node_data(node_name)
                if parent_node_data and 'bone' in parent_node_data and parent_node_data['bone']:
                    bone.length = parent_node_data['bone'].length / 2

            node_dict[node_name]['bone'] = bone
            if 'parent_name' in node_dict[node_name] and node_dict[node_name]['parent_name']:
                parent_name = node_dict[node_name]['parent_name']
                if 'bone' in node_dict[parent_name]:
                    bone.parent = node_dict[parent_name]['bone']

    for node_name, node_data in node_dict.items():
        # if 'BIP01' not in node_name:
        #     continue

        # asc style bone (main rotation axis)
        # translation_matrix = Matrix.Translation(node_data['transform_pos']).to_4x4()
        # rotation_matrix = node_data['transform_rot'].to_matrix().to_4x4()
        # transform_matrix = translation_matrix @ rotation_matrix
        transform_matrix = node_data['transform_matrix']

        default_bone_matrix = Matrix.Rotation(math.radians(-90.0), 4, 'Z').to_4x4()

        bone_matrix = transform_matrix @ default_bone_matrix

        # asc style bone (roll)
        bone_matrix = bone_matrix @ Matrix.Rotation(math.radians(90.0), 4, 'Y').to_4x4()

        # stay on foot
        bone_matrix = Matrix.Rotation(math.radians(90), 4, 'X').to_4x4() @ bone_matrix

        if 'bone' in node_dict[node_name] and node_dict[node_name]['bone']:
            bone = node_dict[node_name]['bone']
            bone.matrix = bone_matrix

            # mirror bug? fix
            bone.head = [-bone.head.x, bone.head.y, bone.head.z]
            bone.tail = [-bone.tail.x, bone.tail.y, bone.tail.z]
            bone.roll = (bone.roll * -1.0) + math.radians(180.0)

        node_dict[node_name]['bone_matrix'] = bone_matrix

    # print(f'---')
    # print(f'---')
    # print(f'---')

    if not asc_armature:
        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)


def create_anim():
    frame_count = animation_data_dict['animation_data']['frame_count']
    assert frame_count >= 1

    # print(f'{frame_count=}')

    scene = bpy.context.scene
    scene.render.fps = int(animation_data_dict['animation_data']['fps'])
    scene.frame_start = 0
    scene.frame_end = frame_count - 1
    scene.frame_set(0)

    for obj in bpy.context.scene.objects:
        if obj.type != 'ARMATURE':
            continue

        if asc_armature:
            obj = asc_armature

        animation_data = obj.animation_data
        if animation_data is None:
            animation_data = obj.animation_data_create()

        if animation_data.action:
            bpy.data.actions.remove(animation_data.action, do_unlink=True)

        animation_data.action = bpy.data.actions.new(f'{obj.name}Action')

        for frame in range(frame_count):
            # print(f'{frame=}')
            for pose_bone in obj.pose.bones:
                bone_name = pose_bone.name
                # print(f'{pose_bone=}')
                if ROTATION_EULER:
                    pose_bone.rotation_mode = 'XYZ'
                else:
                    pose_bone.rotation_mode = 'QUATERNION'
                set_animation(obj, bone_name, frame)


def reset_scene():
    """Reset the current scene"""

    scene = bpy.context.scene

    for child_collection in scene.collection.children:
        scene.collection.children.unlink(child_collection)

    for child_object in scene.collection.objects:
        scene.collection.objects.unlink(child_object)

    bpy.ops.outliner.orphans_purge(do_recursive=True)


bl_info = {
    'name': 'MAN and ASC animation file importer in .json format',
    'version': (0, 0, 1),
    'blender': (4, 0, 0),
    'category': 'Import-Export',
}


class Pref(AddonPreferences):
    bl_idname = __name__
    print(f'{bl_idname=}')

    boolean: BoolProperty(
        name='Use Euler instead Quaternion',
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        # layout.label(text="This is a preferences view for our add-on")
        layout.prop(self, 'boolean')


class Import_MANJSON_ASCJSON_Animation(Operator, ImportHelper):
    bl_idname = 'import.import_manjson_ascjson_animation'
    bl_label = '.MAN.json | .ASC.json'
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}
    filename_ext = '.json'
    filter_glob: StringProperty(
        default='*.json',
        options={'HIDDEN'},
    )

    def execute(self, context):
        global animation_data_dict, node_dict, asc_armature, ROTATION_EULER

        animation_data_dict = {}
        node_dict = {}
        asc_armature = None

        preferences = context.preferences
        addon_prefs = preferences.addons[__name__].preferences
        ROTATION_EULER = addon_prefs.boolean

        print(f'{ROTATION_EULER=}')

        # reset_scene()
        load_anim_data(self.filepath)
        create_skeleton()
        create_anim()

        return {'FINISHED'}


def menu_func_import(self, context):
    self.layout.operator(Import_MANJSON_ASCJSON_Animation.bl_idname, text='Gothic Animation (.MAN.json) (.ASC.json)')


def register():
    bpy.utils.register_class(Import_MANJSON_ASCJSON_Animation)
    bpy.utils.register_class(Pref)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.utils.unregister_class(Import_MANJSON_ASCJSON_Animation)
    bpy.utils.unregister_class(Pref)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()
