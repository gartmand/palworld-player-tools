import argparse
import copy
import glob
import json
import os
import sys

from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.palsav import compress_gvas_to_sav, decompress_sav_to_gvas
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

_PROGRAM_DESCRIPTION_ = '''\
Used to transfer players from specified Players directory (or specific files within it) to a destination 
savegame folder (Level.sav and Players/) when restoring from backup, after losing the original 
Level.sav. The players to be copied should first create characters on the destination. '
An optional mapping file (JSON) can be passed in to specify the levels of the players. '
If this is left off, the players\' levels will all be set to whatever level the seed character is '
(probably 1). No inventory, PalBox, etc. will be copied over.

Note that if the server is on a different architecture, you may need to apply a GUID fix (not yet implemented here).

WARNING: The files in the destination savegame directory WILL BE MODIFIED. USE AT YOUR OWN RISK.
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
    parser = argparse.ArgumentParser(description=_PROGRAM_DESCRIPTION_)

    parser.add_argument('--level-mapping-file', '-m',
                        required=False,
                        help='The path to a JSON file containing a mapping of Player GUIds to their desired level')

    parser.add_argument('--old-player-saves-dir', '-s',
                        required=True,
                        help='The path to a directory containing player save '
                             'data to copy over (Usually called "Players")')

    parser.add_argument('--player-save-file', '-f',
                        action='append',
                        help='The name of a specific player save file whose data should be transferred. '
                             'If none specified, all save files in old-player-saves-dir will be used. '
                             'Supports entering multiple files, e.g. -f filename1.sav -f filename2.sav.')

    parser.add_argument('--new-server-savegame-dir', '-d',
                        required=True,
                        help='The path to the destination directory containing Players/ and Level.sav')

    args = parser.parse_args()
    new_server_savegame_dir = args.new_server_savegame_dir
    level_mapping_file = args.level_mapping_file
    old_player_saves_dir = args.old_player_saves_dir
    player_save_files = args.player_save_file

    if not level_mapping_file:
        warn('No level_mapping_file specified. The levels of the seed characters, along with their stat '
             'points, will be used. This probably means you\'ll have level one characters with bugged unlocks!')

    player_filenames = []
    if player_save_files:
        player_filenames = [os.path.join(old_player_saves_dir, file) for file in player_save_files]
    else:
        # Get the filenames of all the player saves. These can be used for GUIDs (and opening).
        player_filenames = glob.glob(os.path.join(old_player_saves_dir, '*.sav'), recursive=False)
        # player_filenames = list(filter(lambda x: x.endswith('.sav'), os.listdir(old_player_saves_dir)))
        if len(player_filenames) == 0:
            error('No .sav files found in old_player_saves_dir {}')

    add_players_to_level(player_filenames, new_server_savegame_dir, level_mapping_file)


def add_players_to_level(player_filenames, new_server_savegame_dir, level_mapping_file):
    new_players_sav_dir = os.path.join(new_server_savegame_dir, 'Players')
    level_sav_file = os.path.join(new_server_savegame_dir, 'Level.sav')

    if (not os.path.isdir(new_server_savegame_dir)
            or not os.path.isdir(new_players_sav_dir)
            or not os.path.isfile(level_sav_file)):
        error('Please specify a new_server_savegame_dir that contains a Players directory and a Level.sav')

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

    for old_sav_file in player_filenames:
        filename = os.path.basename(old_sav_file)
        new_sav_file = os.path.join(new_server_savegame_dir, 'Players', filename)

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
                     'Please be sure the player has logged onto the new server to seed their data.'.format(guid_raw))
                continue

            if len(matching_mapping_players) == 0:
                warn('Player with UID "{}" not found in mapping. Their level and attribute points will remain '
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

    if level_mapping_file:
        gvas_to_sav(level_gvas, level_sav_file)


if __name__ == '__main__':
    main()
