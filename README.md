# python project - gpt, cursor assisted

***
requires libraries: matplotlib, pygame, and pandas; 
pygame will likely not run on 3.14 python, but has been verified to run on 3.12, and will likely run on 3.13
***

this is a project I had gpt generate to learn sql
start with game.py, which references telemetry.py to collect data, then use sqlite3 to explore the db generated data, and modify visualize.py to see different data, using sql script

download of sql database is unnecessary, it will be generated with the running of game.py, which runs telemetry.py, which generates game_telemetry.db, which can be visualized with visualize.py

EDIT 1-20-26:
I have started using Cursor to add additional features to the game, in collaboration with LP, A, J, and others

EDIT 2:
I have begun to use the game to develop into a sort of bullet hell game, using cursor. The game is intentionally simple, and is meant to be fun, (even if it was generated using AI, I wouldn't have been able to make the game otherwise)

I'm focusing on mechanics of the games, rather than the nitty gritty of the programming itself

EDIT 1-30-26: 
There's been a lot of progress made in the last 10 days, huzzah! The project's been refactored heavily, and there have been features added.

