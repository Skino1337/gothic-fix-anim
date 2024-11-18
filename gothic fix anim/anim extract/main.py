from collections import defaultdict
import json
from pathlib import Path
import itertools
from decimal import Decimal
import copy

from difflib import SequenceMatcher

import shutil


# pip install zenkit
# Luis Michaelis

from zenkit import Vfs, VfsOverwriteBehavior, ModelAnimation, ModelHierarchy, ModelMesh


from scipy.interpolate import CubicSpline

from mathutils import Matrix, Quaternion, Vector


PATH_TO_FILE = 'C:/GAMES/Archolos GOG RUS/Data/Anims.vdf'


model_hierarchy_data = {}
model_animation_data = {}

asc_data = {}


vfs = Vfs()
vfs.mount_disk(PATH_TO_FILE, clobber=VfsOverwriteBehavior.OLDER)


g_move_tr = []
v1_test = []
v2_test = []
bone_diff_quat_dict = {}


def split_animation_name(animation_name):
    parts = animation_name.split('-')
    if len(parts) == 0:
        assert False, 'wrong animation name'
    if len(parts) == 2:
        return parts[0], parts[1]
    else:
        assert False, 'wrong animation name'


def parse_model_hierarchy(model_hierarchy):
    # model_hierarchy_data[model_hierarchy.checksum]['skeleton_name'] = node.name
    if model_hierarchy.checksum not in model_hierarchy_data:
        model_hierarchy_data[model_hierarchy.checksum] = {}

    skeleton_name = model_hierarchy.source_path.split('\\')[-1].split('.')[0]
    if skeleton_name not in model_hierarchy_data[model_hierarchy.checksum]:
        model_hierarchy_data[model_hierarchy.checksum][skeleton_name] = {}

    # print(f'{skeleton_name=}')
    # print(f'{model_hierarchy.checksum=}')
    # print(f'{model_hierarchy.source_date=}')
    # print(f'{model_hierarchy.source_path=}')
    # print(f'{model_hierarchy.bbox.min=}')
    # print(f'{model_hierarchy.bbox.max=}')
    # print(f'{model_hierarchy.collision_bbox.min.x=}')
    # print(f'{model_hierarchy.collision_bbox.max=}')
    # print(f'{model_hierarchy.root_translation=}')

    root_translation = [model_hierarchy.root_translation.x, model_hierarchy.root_translation.y, model_hierarchy.root_translation.z]

    bbox_min = [model_hierarchy.bbox.min.x, model_hierarchy.bbox.min.y, model_hierarchy.bbox.min.z]
    bbox_max = [model_hierarchy.bbox.max.x, model_hierarchy.bbox.max.y, model_hierarchy.bbox.max.z]

    collision_bbox_min = [model_hierarchy.collision_bbox.min.x, model_hierarchy.collision_bbox.min.y, model_hierarchy.collision_bbox.min.z]
    collision_bbox_max = [model_hierarchy.collision_bbox.max.x, model_hierarchy.collision_bbox.max.y, model_hierarchy.collision_bbox.max.z]

    skeleton_data = {'source_path': model_hierarchy.source_path,
                     'root_translation': root_translation,
                     'bbox': {'min': bbox_min, 'max': bbox_max},
                     'collision_bbox': {'min': collision_bbox_min, 'max': collision_bbox_max},
                     'nodes': []}

    for i, model_node in enumerate(model_hierarchy.nodes):
        column_0 = model_node.transform.columns[0]
        column_1 = model_node.transform.columns[1]
        column_2 = model_node.transform.columns[2]
        column_3 = model_node.transform.columns[3]

        transform_mat = Matrix.Identity(4)
        transform_mat.col[0] = [column_0.x, column_0.y, column_0.z, column_0.w]
        transform_mat.col[1] = [column_1.x, column_1.y, column_1.z, column_1.w]
        transform_mat.col[2] = [column_2.x, column_2.y, column_2.z, column_2.w]
        transform_mat.col[3] = [column_3.x, column_3.y, column_3.z, column_3.w]

        translation, rotation, scale = transform_mat.decompose()
        # pos = [round(f, 4) for f in pos]
        # rot = [round(f, 4) for f in rot]

        # for j in range(len(pos)):
        #     pos[j] = pos[j] / 100.0

        for j in range(len(scale)):
            if 0.99998 < scale[j] < 1.0001:
                scale[j] = 1.0

        # print(f'[{i}] node_name={model_node.name}')
        # print(f'[{i}] {translation=}')
        # print(f'[{i}] {rotation=}')
        # print(f'[{i}] {scale=}')

        # model_hierarchy_data[model_hierarchy.checksum]['nodes'][i] = {'node_name': model_node.name,
        node = {'name': model_node.name, 'parent_index': model_node.parent, 'parent_name': '',
                'translation': [translation[0], translation[1], translation[2]],
                'rotation': [rotation[0], rotation[1], rotation[2], rotation[3]],
                'scale': [scale[0], scale[1], scale[2]]}

        skeleton_data['nodes'].append(node)

    for index, _ in enumerate(list(skeleton_data['nodes'])):
        parent_index = skeleton_data['nodes'][index]['parent_index']
        parent_name = ''
        if parent_index >= 0:
            parent_name = skeleton_data['nodes'][parent_index]['name']
        skeleton_data['nodes'][index]['parent_name'] = parent_name

    model_hierarchy_data[model_hierarchy.checksum][skeleton_name] = skeleton_data


def parse_model_animation(model_animation, animation_name):
    # print('--- START parse_model_animation')
    # print(str(model_animation.source_path))
    # print(str(node.name))

    # print(f'man_name={animation_name}')
    # print(f'{model_hierarchy_data=}')

    # print(f'{model_animation.frame_count=}')
    # print(f'{model_animation.fps_source=}')
    # print(f'{model_animation.fps=}')
    # print(f'{model_animation.layer=}')
    # print(f'{model_animation.node_count=}')
    # print(f'{model_animation.node_indices=}')
    # print(f'{model_animation.checksum=}')
    # print(f'{len(model_animation.samples)=}')

    # print(f'source_path={str(model_animation.source_path)}')

    # for i, sample in enumerate(model_animation.samples):
    #     if i % model_animation.frame_count == 0:
    #         print(f'[{i}] {sample.position.y=}')

    asc_name = str(model_animation.source_path).split('\\')[-1]
    # print(f'{asc_name=}')

    # if animation_name == 'BARBQ_SCAV-T_S0_2_S1':
    #     exit()

    if model_animation.checksum not in model_hierarchy_data:
        return

    if len(model_hierarchy_data[model_animation.checksum]) <= 0:
        return

    skeleton_name = list(model_hierarchy_data[model_animation.checksum].keys())[0]

    # print(f'animation {animation_name} assigned to skeleton: {model_hierarchy_data[model_animation.checksum][skeleton_name]}')
    # print(f'animation {animation_name} assigned to skeleton: {skeleton_name}')

    model_hierarchy_nodes = model_hierarchy_data[model_animation.checksum][skeleton_name]['nodes']

    # nodes_dict = {}
    # for key in list(model_hierarchy_nodes.keys()):
    #     nn = model_hierarchy_data[model_animation.checksum]['nodes'][key]['node_name']
    #     parent_name = model_hierarchy_data[model_animation.checksum]['nodes'][key]['parent_name']
    #     pos = model_hierarchy_data[model_animation.checksum]['nodes'][key]['pos']
    #     rot = model_hierarchy_data[model_animation.checksum]['nodes'][key]['rot']
    #     nodes_dict[nn] = {'parent': parent_name, 'translation': pos, 'rotation': rot}
    # model_animation_data_nodes[node_name] = nodes_dict

    # model_animation_data_fps[animation_name] = model_animation.fps

    animation_data = {'name': animation_name, 'frame_count': model_animation.frame_count, 'fps': model_animation.fps,
                      'fps_source': model_animation.fps_source, 'layer': model_animation.layer,
                      'source_script': {}, 'frames': {}}

    source_script_data = parse_source_script(model_animation.source_script)
    if source_script_data and 'asc_name' in source_script_data:
        animation_data['source_script'] = source_script_data

        folder, animation_name_clear = split_animation_name(animation_name)
        if folder not in asc_data:
            asc_data[folder] = {}
        # asc_name = source_script_data['asc_name']
        # asc_name = folder

        if asc_name not in asc_data[folder]:
            asc_data[folder][asc_name] = []

        asc_data[folder][asc_name].append(animation_data)

    if animation_name not in model_animation_data:
        model_animation_data[animation_name] = {
            'skeleton_data': model_hierarchy_data[model_animation.checksum][skeleton_name],
            'animation_data': animation_data}

    bone_offset = 0
    frame_offset = 0
    for sample_index, sample in enumerate(model_animation.samples):
        if bone_offset >= len(model_animation.node_indices):
            bone_offset = 0
            frame_offset = frame_offset + 1

        bone_index = model_animation.node_indices[bone_offset]

        bone_name = model_hierarchy_nodes[bone_index]['name']
        if bone_name not in model_animation_data[animation_name]['animation_data']['frames']:
            model_animation_data[animation_name]['animation_data']['frames'][bone_name] = {}

        # bone_index_parent = model_hierarchy_nodes[bone_index]['parent_index']
        # bone_name_parent = ''
        # model_animation_data[animation_name][bone_name]['parent'] = [bone_name_parent]
        # if bone_index_parent >= 0:
        #     bone_name_parent = model_hierarchy_nodes[bone_index_parent]['node_name']
        #     model_animation_data[animation_name][bone_name]['parent'] = [bone_name_parent]

        # model_animation_data[animation_name][bone_name]['bone_pos'] = [model_hierarchy_nodes[bone_index]['translation']]
        # model_animation_data[animation_name][bone_name]['bone_rot'] = [model_hierarchy_nodes[bone_index]['rotation']]

        translation = [sample.position.x, sample.position.y, sample.position.z]
        rotation = [sample.rotation.w, sample.rotation.x, sample.rotation.y, sample.rotation.z]

        if 'translation' not in model_animation_data[animation_name]['animation_data']['frames'][bone_name]:
            model_animation_data[animation_name]['animation_data']['frames'][bone_name]['translation'] = []
        model_animation_data[animation_name]['animation_data']['frames'][bone_name]['translation'].append(translation)

        if 'rotation' not in model_animation_data[animation_name]['animation_data']['frames'][bone_name]:
            model_animation_data[animation_name]['animation_data']['frames'][bone_name]['rotation'] = []
        model_animation_data[animation_name]['animation_data']['frames'][bone_name]['rotation'].append(rotation)

        bone_offset = bone_offset + 1


def parse_mdh(node):
    if node.is_dir():
        for node_children in node.children:
            parse_mdh(node_children)
    if node.is_file():
        if node.name.endswith('.MDH'):
            name = node.name.split('.')[0]
            print(f'{node.name=}')
            # if name not in ['BLOODFLY']:  # , 'DRAGON', 'DEMON', 'CRAWLER', 'HUMANS', 'BLOODFLY'
            #     return

            print(f'{node.name=}')
            model_hierarchy = ModelHierarchy.load(vfs.find(node.name))
            parse_model_hierarchy(model_hierarchy)


def calc_frames_scaled_v2(frame_list, fps_source, fps):
    fps = fps
    frame_count = len(frame_list)

    fps_target = fps_source

    frame_count_target = int(fps_target / fps * frame_count)

    time_interval = 1 / fps
    duration = time_interval * (frame_count - 1)

    time_interval_target = duration / (frame_count_target - 1)

    result_frame_list = [None] * frame_count_target
    for i in range(len(frame_list[0])):
        y_list = [y[i] for y in frame_list]
        x_list = [x * time_interval for x in range(len(y_list))]
        spl = CubicSpline(x_list, y_list)

        x_target_list = [x * time_interval_target for x in range(frame_count_target)]
        y_target_list = list(spl(x_target_list))
        for j, y_target in enumerate(y_target_list):
            if result_frame_list[j] is None:
                result_frame_list[j] = []
            result_frame_list[j].append(y_target)

    return result_frame_list


def parse_source_script(source_script):
    line_parts = source_script.split()
    if len(line_parts) >= 11 and 'ANI' == line_parts[0]:
        pass
    else:
        return None
    line_parts[-1] = line_parts[-1].replace('"', '').replace('(', '').replace(')', '')
    name = line_parts[1].replace('"', '').replace('(', '').replace(')', '')
    layer = int(line_parts[2]) if line_parts[2].isdigit() else 1
    next_anim = line_parts[3].replace('"', '').replace('(', '').replace(')', '')
    blend_id = float(line_parts[4])
    blend_out = float(line_parts[5])
    flags = line_parts[6]
    asc_name = line_parts[7].replace('"', '').split('.')[0]
    direction = line_parts[8]
    start_frame = int(line_parts[9]) if line_parts[9].isdigit() else 0
    end_frame = int(line_parts[10]) if line_parts[10].isdigit() else 0
    fps = 25.0
    cvs = 0.0  # CollisionVolumeScale
    for part in line_parts[11:]:
        value = part.split(':')[-1]
        if 'FPS' in part:
            try:
                fps = float(value)  # can 12.5
            except:
                pass
        elif 'CVS' in part:
            try:
                cvs = float(value)
            except:
                pass

    return {'name': name, 'layer': layer, 'next_anim': next_anim, 'blend_id': blend_id,
            'blend_out': blend_out, 'flags': flags, 'asc_name': asc_name,
            'direction': direction, 'start_frame': start_frame, 'end_frame': end_frame, 'fps': fps, 'cvs': cvs}


def parse_man(node):
    if node.is_dir():
        for node_children in node.children:
            parse_man(node_children)
    if node.is_file():
        if node.name.endswith('.MAN'):
            name = node.name.split('.')[0]
            # if name not in ['HUMANS-S_BOWRUN']:  # HUMANS-S_BOWRUN, HUMANS-T_JUMPB, HUMANS-T_RUN_2_RUNL, HUMANS-S_RUNL, HUMANS-T_RUNL_2_RUN
            #     return

            model_animation = ModelAnimation.load(vfs.find(node.name))
            assert model_animation.node_count * model_animation.frame_count == len(model_animation.samples)
            assert model_animation.node_count == len(model_animation.node_indices)

            # print(f'{model_animation.fps_source}')
            # print(f'{model_animation.source_path}')
            # print(f'{model_animation.source_script}')

            # source_script_data = parse_source_script(model_animation.source_script)
            # if source_script_data:
            #     source_script_data = {**{'full_name': name}, **{'model_animation': model_animation}, **source_script_data}
            #     asc_name = source_script_data['asc_name']
            #     if asc_name not in asc_anim_dict:
            #         asc_anim_dict[asc_name] = []
            #     asc_anim_dict[asc_name].append(source_script_data)
            # print(f'{source_script_data=}')

            # node name can duplicate
            name_asc = model_animation.source_path.split('\\')[-1].split('.')[0]
            # if name_asc not in ['BARBQ_NW_MISC_SHEEP_01', ]:  # HUM_AMB_BOWRUN_M01, HUM_JUMPB_M01, HUM_RUNLOOP_M01
            #     return

            # node_data = parse_asc(name_asc)
            parse_model_animation(model_animation, name)


def save_man():
    print(f'START SAVE MAN')

    path_man_folder = Path('MAN')

    shutil.rmtree(path_man_folder, ignore_errors=True)
    path_man_folder.mkdir(exist_ok=True)

    for anim_name, data in model_animation_data.items():
        json_data = json.dumps(data, indent=4, ensure_ascii=False)

        skeleton_name = ''
        man_name = anim_name + '.MAN' + '.json'

        anim_name_parts = anim_name.split('-')
        if len(anim_name_parts) == 0:
            pass
        if len(anim_name_parts) == 2:
            skeleton_name = anim_name_parts[0]
            man_name = anim_name_parts[1] + '.MAN' + '.json'
        else:
            assert False

        path_man_skeleton_folder = path_man_folder
        if skeleton_name:
            path_man_skeleton_folder = path_man_folder / Path(skeleton_name)
            if not path_man_skeleton_folder.exists():
                path_man_skeleton_folder.mkdir(exist_ok=True)

        file = path_man_skeleton_folder / Path(man_name)
        if file.exists():
            # file.unlink()
            assert False
        file.write_text(json_data, encoding='utf-8')


def save_asc():
    print(f'START SAVE ASC')

    folder_asc_path = Path('ASC')

    shutil.rmtree(folder_asc_path, ignore_errors=True)
    folder_asc_path.mkdir(exist_ok=True)

    # for asc_anim_name, asc_anim_list in asc_anim_dict.items():
    #     asc_anim_list = sorted(asc_anim_list, key=lambda item: item['start_frame'])

    # asc_data_to_save = {}

    # asc_data[folder][asc_name].append(animation_data)

    for folder_name, folder_data in asc_data.items():
        for asc_name, anim_data_list in folder_data.items():
            # print(f'{asc_name=}, anim len={len(anim_data_list)}')
            anim_data_list = sorted(anim_data_list, key=lambda item: item['source_script']['start_frame'])
            # print(f'{anim_data_list=}')

            # for anim_data in anim_data_list:
                # print(f'man name: {anim_data["name"]}')

            for i in range(len(anim_data_list)):
                assert anim_data_list[0]['fps_source'] == anim_data_list[i]['fps_source']
                # print(f"name={anim_data_list[i]['source_script']['name']}")

            # 1, 5-10, 10-30, 30-40, Bloodfly WTF??? don't need this check???
            missing_frames = []
            for i in range(len(anim_data_list)):
                if len(anim_data_list) > 0 and i + 1 < len(anim_data_list):
                    # assert anim_data_list[i]['source_script']['end_frame'] + 1 == anim_data_list[i + 1]['source_script']['start_frame']
                    end_frame = anim_data_list[i]['source_script']['end_frame']
                    start_frame = anim_data_list[i + 1]['source_script']['start_frame']
                    if end_frame + 1 != start_frame:
                        for frame in range(end_frame + 1, start_frame):
                            missing_frames.append(frame)

            # model_animation_data[animation_name]['animation_data']['frames'][bone_name]['rotation'].append(rotation)
            assert anim_data_list[0]['name'] in model_animation_data

            asc_data_to_save = {'skeleton_data': model_animation_data[anim_data_list[0]['name']]['skeleton_data'],
                                'animation_data': {'name': asc_name,
                                                   'frame_count': 0,
                                                   'fps': anim_data_list[0]['fps_source'],
                                                   'frames': {}}}

            frames = {}
            for anim_data in anim_data_list:
                for node_name, node_data in anim_data['frames'].items():
                    # print(f'{node_name=} {node_data=}')
                    if node_name not in frames:
                        frames[node_name] = {}
                    for key, value in node_data.items():
                        # print(f'{key=}, {value=}')
                        if key not in frames[node_name]:
                            frames[node_name][key] = []
                        frames[node_name][key].extend(value)
                        # print(f'frames after add: {len(frames[node_name][key])}')

            fps_source = anim_data_list[0]['fps_source']
            fps = anim_data_list[0]['fps']
            for node_name, node_data in frames.items():
                for key, value in node_data.items():
                    if fps_source != fps:
                        value_scaled = calc_frames_scaled_v2(value, fps_source, fps)
                        frames[node_name][key] = value_scaled
                        # print(f'frames after scale: {len(frames[node_name][key])}')

            asc_data_to_save['animation_data']['frames'] = frames
            if len(frames) > 0:
                first_node_data = list(frames.values())[0]
                # print(f'{first_node_data=}')
                first_key_data = list(first_node_data.values())[0]
                # print(f'{first_key_data=}')
                asc_data_to_save['animation_data']['frame_count'] = len(first_key_data)
            else:
                asc_data_to_save['animation_data']['frame_count'] = 0

            json_data = json.dumps(asc_data_to_save, indent=4, ensure_ascii=False)

            # bone_name = model_hierarchy_data[model_animation.checksum]['nodes'][bone_index]['node_name']

            # print(asc_anim_list[0]['model_animation'])
            # asc_name = asc_anim_list[0]['asc_name'] + '.ASC' + '.json'
            # asc_name = asc_name + '.ASC' + '.json'

            suffix = ''
            if missing_frames:
                suffix = '_ERROR'
                print(f"WARNING: Can't find .MAN file for {anim_data_list[0]['source_script']['asc_name']}.ASC, missing frames: {missing_frames}")

            asc_name = anim_data_list[0]['source_script']['asc_name'] + suffix + '.ASC' + '.json'

            # subfolder_name, _ = split_animation_name(anim_data_list[0]['name'])
            folder_subfolder_asc_path = folder_asc_path / Path(folder_name)
            if not folder_subfolder_asc_path.exists():
                folder_subfolder_asc_path.mkdir(exist_ok=True)

            # folder_subfolder_asc_path = folder_asc_path

            file = folder_subfolder_asc_path / Path(asc_name)
            if file.exists():
                # file.unlink()
                assert False
            file.write_text(json_data, encoding='utf-8')


parse_mdh(vfs.root)
parse_man(vfs.root)
save_man()
save_asc()
