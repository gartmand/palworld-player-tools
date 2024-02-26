# gartmand/palworld-player-tools

Were you playing PalWorld with your pals (or alone), only to connect to your server
one day and be prompted to create a new character?

If so, did you make the sound decision to exit before creating the character?

Do you have no backups of the Level.sav, but are okay with losing inventory,
construction, etc. as long as you can keep your hard-earned character recipes,
stat points, etc.? 

If you answered yes, then read on! This tool is for you:
## add_players_to_level.py

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
   inventories or PalBoxes, and constructions will disappear. I am looking into a fix to re-link these,
   but it appears whatever causes the player data to go missing from the Level.sav cascades to containers, etc.
   So it may not be possible.
8. If there are stragglers who didn't create seed characters, you can repeat the process.
   Shut down the server, have stragglers create a character. Make note of the filenames
   of their saves. Run the tool again, adding -f SAV_FILE_NAME for each straggler's save.
   Make sure not to run it without -f, as it will process all the saves again.
9. Start the server again.

**WARNING**: The files in the destination savegame directory WILL BE MODIFIED. USE AT YOUR OWN RISK.
   
Good luck!   

The mapping file (JSON) is passed in to specify the levels of the players.
See the mapping.json in the repository for an example.
If this is left off, the players\' levels will all be set to whatever level the seed character is
(probably 1).