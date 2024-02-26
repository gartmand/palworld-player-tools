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
This tool was created to address the problem of restoring players to the same server when they had a character but are 
prompted with Character Creation. In other words - their data is missing from Level.sav. Restoring them to a different
server isn't fully supported and you might have to figure that out yourself for now. If the server is on a different 
architecture, or you are restoring from single player to dedicated or vice versa, 
you may need to apply a GUID replacement (not yet implemented here) to the .sav files after gathering info on what
the players' new GUIDs will be. Suggested reading: https://github.com/xNul/palworld-host-save-fix
No inventory, PalBox, etc. will be copied over, unfortunately.

Suggested use:
1. MAKE SURE YOUR PLAYERS DO NOT FINISH CHARACTER CREATION BEFORE YOU MAKE A COPY OF THE SAVE.
   If they do, their save will be overwritten and lost. In that case, it's probably best to use a full-fledged
   save editor like Paver: https://github.com/adefee/paver-palworld-save-editor
2. Ensure the server is stopped. Otherwise, it's going to overwrite your fixes, and your players might
   create characters and overwrite their individual .sav files inadvertently.
3. Create a backup of the Level's save folder. That is - the one containing Level.sav and Players/. Make sure it's
   the one in use by the server. Otherwise, you will lose the Player saves forever further in this process.
4. Ask your players what level they were. Record their levels (and the total exp required to get there PLUS ONE)
   in a mapping.json file. For now, the Exp value is a manual entry. I hope to implement a similar lookup to the one
   that Paver does here: https://github.com/adefee/paver-palworld-save-editor/blob/main/src/data/experiencePerLevel.json
   The XP tuning might be in flux, thus such a lookup table might change frequently. 
5. Start the server, then have your players all log in.
6. Stop the server, then run the tool. Point the --old-player-saves-dir (-s) at the Players/ directory inside
   your backup copy, the --new-server-savegame-dir (-d) at the in-use Level save folder 
   containing Players/ and Level.sav, and the --level-mapping-file (-m) at the mapping you created in 4.
7. Start the server, and verify your players are restored. Note that at this time, this tool cannot restore
   inventories or PalBoxes, and constructions will disappear.
8. If there are stragglers who didn't create seed characters, you can repeat the process.
   Shut down the server, have stragglers create a character. Make note of the filenames
   of their saves. Run the tool again, adding -f SAV_FILE_NAME for each straggler's save.
   Make sure not to run it without -f, as it will process all the saves again.
9. Start the server again.

WARNING: The files in the destination savegame directory WILL BE MODIFIED. USE AT YOUR OWN RISK.
   
Good luck!   

The mapping file (JSON) is passed in to specify the levels of the players.
See the mapping.json in the repository for an example.
If this is left off, the players\' levels will all be set to whatever level the seed character is
(probably 1).
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
                        help='The path to a JSON file containing a mapping of Player GUIds to their desired level. '
                             'If the path contains spaces, surround it with quotes. Double any backslashes.')

    parser.add_argument('--old-player-saves-dir', '-s',
                        required=True,
                        help='The path to a directory containing player save '
                             'data to copy over (Usually called "Players"). '
                             'If the path contains spaces, surround it with quotes. Double any backslashes.')

    parser.add_argument('--player-save-file', '-f',
                        action='append',
                        help='The name of a specific player save file whose data should be transferred. '
                             'If none specified, all save files in old-player-saves-dir will be used. '
                             'Supports entering multiple files, e.g. -f filename1.sav -f filename2.sav.')

    parser.add_argument('--new-server-savegame-dir', '-d',
                        required=True,
                        help='The path to the destination directory containing Players/ and Level.sav.'
                             'If the path contains spaces, surround it with quotes. Double any backslashes.')

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

    # Since the seed player sav file (new save) has all the right new (but empty) Containers and the right Instance ID,
    # we just need to copy over these properties from the old player sav into the seed sav.
    #
    # TODO: It might be good to replace the Container IDs in the seed sav with those from the
    #       old one, if those containers survived whatever corruption occurred. In other words, we'd need to
    #       filter for references to the Container IDs in the Level.sav. If one is present, do the replacement.
    #       It might also be nice to look for occurrences of the old Player Instance ID and replace with
    #       the new one, like xNul/palworld-host-save-fix does for the guild fix, or vice versa.
    #       This is probably a pipe dream though. Whatever corruption causes the characters to be deleted from the
    #       Level.sav seems like it cascades the delete to the Player's containers.
    #
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
                    p['value']['RawData']['value']['object']['SaveParameter']['value']['Exp'] = {
                        'id': None,
                        'value': v['Exp'],
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
