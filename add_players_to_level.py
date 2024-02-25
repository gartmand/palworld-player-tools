import copy
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

    new_players_sav_dir = os.path.join(new_server_savegame_dir, 'Players')
    level_sav_file = os.path.join(new_server_savegame_dir, 'Level.sav')

    if (not os.path.isdir(new_server_savegame_dir)
            or not os.path.isdir(new_players_sav_dir)
            or not os.path.isfile(level_sav_file)):
        print('Please specify a new_server_savegame_dir that contains a Players directory and a Level.sav')
        error(_USAGE_)
    
    level_gvas = None
    character_save_parameter_map_values = {}
    level_mapping_data = {}

    # We can't restore certain data about players that is stored only on the Level.sav if that was lost.
    # Instead, we need a manual mapping to be supplied. At the moment, only the Player Level and Stat Points (related)
    # are known to fall in this category.
    if level_mapping_file:
        level_gvas = sav_to_gvas(level_sav_file)
        with open(level_mapping_file) as json_file:
            level_mapping_data = json.load(json_file)
        character_save_parameter_map_values = (
            level_gvas.properties)['worldSaveData']['value']['CharacterSaveParameterMap']['value']

    # Since the seed player sav file (new save) has all the right Containers and the right Instance ID,
    # we just need to copy over these properties from the old player sav into the seed sav.
    player_save_data_copy_properties = [
        'PlayerCharacterMakeData',
        'TechnologyPoint',
        'bossTechnologyPoint',
        'UnlockedRecipeTechnologyNames',
        'RecordData'
    ]

    for filename in player_filenames:

        new_sav_file = os.path.join(new_server_savegame_dir, 'Players', filename)

        old_sav_file = os.path.join(old_player_saves_dir, filename)
        guid_raw, guid_formatted = get_guid_data(filename)

        print('Processing player .sav file: {}'.format(filename))

        if not os.path.exists(new_sav_file):
            warn('Could not find matching save in new server for player with UID {} - SKIPPING'.format(guid_raw))
            continue

        if level_mapping_data and level_mapping_data['values']:
            # The matching lists should only be length one, but this is done to keep it idiomatic
            matching_level_players = list(filter(
                lambda x: x['key']['PlayerUId']['value'] == guid_formatted,
                character_save_parameter_map_values))

            matching_mapping_players = list(filter(
                lambda y: y['PlayerUId'] == guid_formatted,
                level_mapping_data['values']))

            if len(matching_level_players) == 0:
                warn('SKIPPING Player with UID "{}" because they were not found in Level.sav. '
                     'Please be sure the player logged onto the new server to seed their data.'.format(guid_raw))
                continue

            if len(matching_mapping_players) == 0:
                warn('Player with UID "{}" not found in mapping. Their level and attribute points will remain'
                     'the same as those of the seed character.'.format(guid_raw))

            for p in matching_level_players:
                for v in matching_mapping_players:
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

        player_old_gvas = sav_to_gvas(old_sav_file)
        player_new_gvas = sav_to_gvas(new_sav_file)

        for copy_property in player_save_data_copy_properties:
            copy_property_val = player_old_gvas.properties['SaveData']['value'].get(copy_property)

            if copy_property_val:
                player_new_gvas.properties['SaveData']['value'][copy_property] = copy.deepcopy(copy_property_val)

        gvas_to_sav(player_new_gvas, new_sav_file)
    gvas_to_sav(level_gvas, level_sav_file)


if __name__ == '__main__':
    main()
