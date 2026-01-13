bomberman
4 players, spawn 1 in each corner, p1 in top left, p2 in bottom right, p3 in top right, p4 in bottom left.

to run game: python grid_game.py

controls:
P1: arrow keys to move, spacebar to place/throw bombs
P2: WASD keys to move, E to place/throw bombs

debug keybinds:
R: restart game
H: show hitboxes
I: become invincible
T: walk through walls
G: give yourself the glove powerup.
0: to activate sudden death

todo:
multiplayer
add bosses as playable characters?
fix the glove
make players trip when a bomb is thrown at their feet
implement the skull powerdown
make a proper powerup spawn table
proper ui
menus
possibly other maps

known issues:
if 1 player fies, and then the other player dies, the first player will come to life
thrown bombs do not act correctly
player 2 cant kick bombs
when the match resets players will keep the effects of the speed and fire powerups