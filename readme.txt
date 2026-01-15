bomberman
4 players, spawn 1 in each corner, p1 in top left, p2 in bottom right, p3 in top right, p4 in bottom left.

to run game: python grid_game.py

controls:
P1: arrow keys to move, spacebar to place/throw bombs
P2: WASD keys to move, E to place/throw bombs
P3: IJKL keys to move, O to place/throw bombs 
P4: numpad 8456 to move, 9 to place/throw bombs

debug keybinds:
R: restart game
H: show hitboxes
I: become invincible
T: walk through walls
G: give yourself the glove powerup.
0: to activate sudden death

todo:
online multiplayer
add bosses as playable characters?
fix the glove
make players trip when a bomb is thrown at their feet
implement the skull powerdown
make a proper powerup spawn table
proper ui
menus
possibly other maps

known issues:
thrown bombs do not act correctly
G to give glove doesnt give to players 3 and 4, only 1 and 2

skull:
 The player moves extremely fast.
The player moves extremely slow.
 The player continuously sets bombs when possible.
The player's bombs explode at the minimum blast radius regardless of their current blast radius (1 tile from origin).
The player is unable to set bombs.