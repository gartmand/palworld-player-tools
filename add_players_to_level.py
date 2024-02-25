import json
import os
import sys

from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import compress_gvas_to_sav, decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

_USAGE_ = '''\
add_players_to_level.py <old_player_saves_dir> <new_server_savegame_dir> [<level_mapping_file>]'
    old_player_saves_dir => Path to Players/ directory where the .sav of players you want to insert into the level are
    new_server_savegame_dir => Path to directory containing both Level.sav of the new server, 
        AND a Players/ directory containing pre-seeded .sav files for the players to be copied.
'''


def add_player_to_level(old_user_json, new_user_json, level_json):
    pass


def add_players_to_level(user_guids, level_json):
    pass


def merge_player_json(old_json, new_json):
    pass


def format_guid(guid_or_filename):
    return '{}-{}-{}-{}-{}'.format(
        guid_or_filename[:8],
        guid_or_filename[8:12],
        guid_or_filename[12:16],
        guid_or_filename[16:20],
        guid_or_filename[20:32]
    ).lower()


def get_guid_data(file_or_dir_name):
    guid_raw = os.path.splitext(file_or_dir_name)[0]
    guid_formatted = format_guid(guid_raw)
    return guid_raw, guid_formatted


def error(msg, exitcode=1):
    print('ERROR: {}'.format(msg))
    exit(exitcode)


def warn(msg):
    print('WARNING: {}'.format(msg))


def sav_to_gvas(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
        raw_gvas, _ = decompress_sav_to_gvas(data)
    return GvasFile.read(
        raw_gvas, PALWORLD_TYPE_HINTS, PALWORLD_CUSTOM_PROPERTIES, allow_nan=True
    )


def gvas_to_sav(gvas_file, output_filepath):
    if ('Pal.PalWorldSaveGame' in gvas_file.header.save_game_class_name
            or 'Pal.PalLocalWorldSaveGame' in gvas_file.header.save_game_class_name):
        save_type = 0x32
    else:
        save_type = 0x31
    sav_file = compress_gvas_to_sav(
        gvas_file.write(PALWORLD_CUSTOM_PROPERTIES), save_type
    )
    with open(output_filepath, 'wb') as f:
        f.write(sav_file)


def main():
    if len(sys.argv) < 3:
        error(_USAGE_)

    old_player_saves_dir = sys.argv[1].replace(os.sep, '/')
    new_server_savegame_dir = sys.argv[2].replace(os.sep, '/')
    level_mapping_file = sys.argv[3].replace(os.sep, '/') if len(sys.argv) >= 4 and sys.argv[3] else ''

    if not level_mapping_file:
        warn('No level_mapping_file specified. The levels of the seed characters, along with their stat '
             'points, will be used. This probably means you\'ll have level one characters with bugged unlocks!')

    # Get the filenames of all the player saves. These can be used for GUIDs (and opening).
    # player_filename_paths = glob.glob(old_player_saves_dir + '/*.sav', recursive=False)
    player_filenames = list(filter(lambda x: x.endswith('.sav'), os.listdir(old_player_saves_dir)))

    if len(player_filenames) == 0:
        error('No .sav files found in old_player_saves_dir {}')

    player_guids_raw = []
    player_guids_formatted = []

    # Collect raw (uppercase) and formatted (dashed lower) GUIDs.
    for path in player_filenames:
        guid_raw, guid_formatted = get_guid_data(path)

        player_guids_raw.append(guid_raw)
        player_guids_formatted.append(guid_formatted)

    # # Alternatively:
    # player_guids_raw, player_guids_formatted = \
    #     (x for x in zip(*map(get_guid_data, player_filename_paths)))

    print(', '.join(player_filenames))
    print(', '.join(player_guids_raw))
    print(', '.join(player_guids_formatted))

    level_sav_path = new_server_savegame_dir + '/Level.sav'

    save_folder_contents = os.listdir(new_server_savegame_dir)
    if 'Players' not in save_folder_contents or 'Level.sav' not in save_folder_contents:
        print('Please specify a new_server_savegame_dir that contains a Players directory and a Level.sav')
        error(_USAGE_)

    # Convert level files to JSON
    level_gvas = sav_to_gvas(level_sav_path)

    character_save_parameter_map_values = (
        level_gvas.properties)['worldSaveData']['value']['CharacterSaveParameterMap']['value']

    for filename in player_filenames:
        old_sav_path = os.path.join(old_player_saves_dir, filename)
        new_sav_path = os.path.join(new_server_savegame_dir, 'Players', filename)
        guid_raw, guid_formatted = get_guid_data(old_sav_path)

        player_old_gvas = sav_to_gvas(old_sav_path)
        player_new_gvas = sav_to_gvas(new_sav_path)





    # Data about players that is stored only on the Level.sav, not on the Player.sav
    level_players = list(filter(
        lambda x: x['value']['RawData']['value']['object']['SaveParameter']['value']['IsPlayer']['value'],
        character_save_parameter_map_values))
    if level_mapping_file:
        level_mapping_data = {}
        with open(level_mapping_file) as json_file:
            level_mapping_data = json.load(json_file)
        for p in level_players:
            for v in filter(lambda y: y['PlayerUId'] == p['key']['PlayerUId']['value'], level_mapping_data['values']):
                p['value']['RawData']['value']['object']['SaveParameter']['value']['Level'] = {
                    'id': None,
                    'value': v['Level'],
                    'type': 'IntProperty'
                }
                p['value']['RawData']['value']['object']['SaveParameter']['value']['UnusedStatusPoint'] = {
                    'id': None,
                    'value': v['Level'] - 1,
                    'type': 'IntProperty'
                }


if __name__ == '__main__':
    main()
