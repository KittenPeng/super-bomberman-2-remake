import pygame
import sys
import math
import os
import random

# Initialize Pygame
pygame.init()

# Initialize mixer for music
pygame.mixer.init()

# Load sound effects
place_bomb_sound = None
bomb_explode_sound = None
item_get_sound = None
kick_voice_sound = None
kick_sound = None
try:
    place_bomb_sound = pygame.mixer.Sound("Place Bomb.wav")
except Exception as e:
    print(f"Warning: Could not load place bomb sound: {e}")

try:
    bomb_explode_sound = pygame.mixer.Sound("Bomb Explodes.wav")
except Exception as e:
    print(f"Warning: Could not load bomb explode sound: {e}")

try:
    item_get_sound = pygame.mixer.Sound("Item Get.wav")
except Exception as e:
    print(f"Warning: Could not load item get sound: {e}")

try:
    kick_voice_sound = pygame.mixer.Sound("kick voice.wav")
except Exception as e:
    print(f"Warning: Could not load kick voice sound: {e}")

try:
    kick_sound_raw = pygame.mixer.Sound("kick.wav")
    # Pitch down by 1 semitone (ratio = 2^(-1/12) ≈ 0.9439)
    # To pitch down, we need to resample at a slower rate
    try:
        import numpy as np
        # Get the sound array
        sound_array = pygame.sndarray.array(kick_sound_raw)
        # Calculate the pitch ratio (4 semitones down = 2^(-4/12))
        pitch_ratio = 2 ** (-4 / 12)  # ≈ 0.7937 (pitch down by 4 semitones)
        # Resample the audio to pitch it down
        if len(sound_array.shape) == 2:  # Stereo
            # Resample each channel
            original_length = sound_array.shape[0]
            new_length = int(original_length / pitch_ratio)
            resampled = np.zeros((new_length, sound_array.shape[1]), dtype=sound_array.dtype)
            for i in range(new_length):
                source_index = int(i * pitch_ratio)
                if source_index < original_length:
                    resampled[i] = sound_array[source_index]
            kick_sound = pygame.sndarray.make_sound(resampled)
        else:  # Mono
            original_length = sound_array.shape[0]
            new_length = int(original_length / pitch_ratio)
            resampled = np.zeros(new_length, dtype=sound_array.dtype)
            for i in range(new_length):
                source_index = int(i * pitch_ratio)
                if source_index < original_length:
                    resampled[i] = sound_array[source_index]
            kick_sound = pygame.sndarray.make_sound(resampled)
    except ImportError:
        # If numpy is not available, use the original sound
        kick_sound = kick_sound_raw
        print("Warning: numpy not available, using original kick sound pitch")
    except Exception as e:
        # If resampling fails, use the original sound
        kick_sound = kick_sound_raw
        print(f"Warning: Could not pitch shift kick sound: {e}, using original")
except Exception as e:
    kick_sound = None
    print(f"Warning: Could not load kick sound: {e}")

try:
    pause_jingle_sound = pygame.mixer.Sound("Pause Jingle.wav")
    # Set volume to be louder (1.0 is max, but we can go higher if needed)
    pause_jingle_sound.set_volume(1.0)
except Exception as e:
    pause_jingle_sound = None
    print(f"Warning: Could not load pause jingle sound: {e}")

# Constants
GRID_WIDTH = 15
GRID_HEIGHT = 13
CELL_SIZE = 40
WINDOW_WIDTH = GRID_WIDTH * CELL_SIZE
WINDOW_HEIGHT = GRID_HEIGHT * CELL_SIZE

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
DARK_GRAY = (80, 80, 80)
GREEN = (30, 120, 30)
BLUE = (50, 100, 200)
RED = (200, 50, 50)
BROWN = (139, 69, 19)  # Destructible walls
ORANGE = (255, 165, 0)  # Bomb
YELLOW = (255, 255, 0)  # Explosion
PURPLE = (128, 0, 128)  # Glove powerup fallback

# Create the window
window = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("Grid Movement Game - Arrow Keys: Move | Space: Place Bomb")

# Player position (starting at top left corner, avoiding walls) - now in pixels
# Spawn at grid position (1, 1) which is just inside the top-left corner
player_x = 1 * CELL_SIZE + CELL_SIZE // 2
player_y = 1 * CELL_SIZE + CELL_SIZE // 2

# Player stats
max_bombs = 1  # Maximum number of bombs player can place at once
can_kick = False  # Whether player can kick bombs
has_glove = False  # Whether player has the glove powerup
thrown_bomb = None  # Bomb currently being thrown (None if not throwing)
is_throwing = False  # Whether player is currently throwing a bomb (prevents movement)
glove_pickup_animation_start_time = None  # Time when glove pickup animation started (None if not animating)

# Powerups on the ground: {(grid_x, grid_y): powerup_type}
powerups = {}

# Game state variables
game_over = False
death_time = None
player_direction = 'down'  # Track player facing direction: 'up', 'right', 'down', 'left'
player_moving = False  # Track if player is currently moving
invincible = False  # Invincibility toggle (press 'i' to toggle)
show_hitboxes = False  # Toggle to show hitboxes (press 'h' to toggle)
music_muted = False  # Track whether music is muted (press 'm' to toggle)

# Player size (radius) - slightly smaller to help with corner navigation
PLAYER_RADIUS = CELL_SIZE // 2 - 6

# Movement speed (pixels per frame) - can be increased by speed powerup
MOVE_SPEED = 3.0

# Bomb settings
BOMB_EXPLOSION_TIME = 2000  # milliseconds (2 seconds)
BOMB_EXPLOSION_DURATION = 500  # milliseconds (0.5 seconds) - how long explosion is visible
BOMB_EXPLOSION_RANGE = 2  # cells in each direction
BOMB_KICK_DELAY = 100  # milliseconds delay before bomb can be kicked after player leaves it
BOMB_KICK_SPEED = 5.5  # Pixels per frame for bomb movement

# Walls - outer perimeter
walls = set()
# Top and bottom rows
for x in range(GRID_WIDTH):
    walls.add((x, 0))
    walls.add((x, GRID_HEIGHT - 1))
# Left and right columns (excluding corners already added)
for y in range(1, GRID_HEIGHT - 1):
    walls.add((0, y))
    walls.add((GRID_WIDTH - 1, y))

# Interior walls - checkerboard pattern, excluding cells directly touching outer wall
# Cells directly touching outer wall are at x=1, x=GRID_WIDTH-2, y=1, y=GRID_HEIGHT-2
# Also exclude rows 3, 5, 7, and 9
excluded_rows = {3, 5, 7, 9}
for x in range(2, GRID_WIDTH - 2):
    for y in range(2, GRID_HEIGHT - 2):
        # Skip excluded rows
        if y not in excluded_rows:
            # Checkerboard pattern: every other square - these are permanent walls
            if (x + y) % 2 == 0:
                walls.add((x, y))

# Breaking blocks animation tracking: {(x, y): start_time}
breaking_blocks = {}
BLOCK_BREAKING_DURATION = 300  # milliseconds for breaking animation

# Item explosion animation tracking: {(x, y): start_time}
item_explosions = {}
ITEM_EXPLOSION_DURATION = 400  # milliseconds for item explosion animation

def generate_destructible_walls():
    """Generate destructible walls with empty corners and random 10% removal"""
    destructible_walls = set()
    
    # Player spawn positions for all 4 corners
    # Top-left corner
    player_spawns = [
        (1, 1),  # Top-left (P1)
        (GRID_WIDTH - 2, GRID_HEIGHT - 2),  # Bottom-right (P2)
        (GRID_WIDTH - 2, 1),  # Top-right (P3)
        (1, GRID_HEIGHT - 2)  # Bottom-left (P4)
    ]
    
    # Generate destructible walls everywhere there isn't a permanent wall or player spawn
    for x in range(GRID_WIDTH):
        for y in range(GRID_HEIGHT):
            # Skip if it's a permanent wall
            if (x, y) in walls:
                continue
            # Skip player spawn positions
            if (x, y) in player_spawns:
                continue
            # Add as destructible wall
            destructible_walls.add((x, y))
    
    # Remove first destructible wall on rows 1 and 2 for top-left corner
    for y in [1, 2]:
        # Find first destructible wall on this row (leftmost)
        for x in range(GRID_WIDTH):
            if (x, y) in destructible_walls:
                destructible_walls.remove((x, y))
                break  # Only remove the first one
    
    # Remove first destructible wall on rows 1 and 2 for top-right corner (rightmost)
    for y in [1, 2]:
        # Find first destructible wall on this row (rightmost)
        for x in range(GRID_WIDTH - 1, -1, -1):
            if (x, y) in destructible_walls:
                destructible_walls.remove((x, y))
                break  # Only remove the first one
    
    # Remove first destructible wall on rows GRID_HEIGHT-2 and GRID_HEIGHT-3 for bottom-left corner (leftmost)
    for y in [GRID_HEIGHT - 2, GRID_HEIGHT - 3]:
        # Find first destructible wall on this row (leftmost)
        for x in range(GRID_WIDTH):
            if (x, y) in destructible_walls:
                destructible_walls.remove((x, y))
                break  # Only remove the first one
    
    # Remove first destructible wall on rows GRID_HEIGHT-2 and GRID_HEIGHT-3 for bottom-right corner (rightmost)
    for y in [GRID_HEIGHT - 2, GRID_HEIGHT - 3]:
        # Find first destructible wall on this row (rightmost)
        for x in range(GRID_WIDTH - 1, -1, -1):
            if (x, y) in destructible_walls:
                destructible_walls.remove((x, y))
                break  # Only remove the first one
    
    # Randomly remove about 10% of remaining blocks
    blocks_list = list(destructible_walls)
    num_to_remove = max(1, int(len(blocks_list) * 0.1))  # Remove 10%, at least 1
    blocks_to_remove = random.sample(blocks_list, min(num_to_remove, len(blocks_list)))
    for block in blocks_to_remove:
        destructible_walls.remove(block)
    
    return destructible_walls

# Generate initial destructible walls
destructible_walls = generate_destructible_walls()

# Bomb class
class Bomb:
    def __init__(self, grid_x, grid_y, placed_time):
        self.grid_x = grid_x
        self.grid_y = grid_y
        # Initialize pixel position at center of grid cell
        self.pixel_x = grid_x * CELL_SIZE + CELL_SIZE // 2
        self.pixel_y = grid_y * CELL_SIZE + CELL_SIZE // 2
        self.placed_time = placed_time
        self.exploded = False
        self.explosion_start_time = None
        self.explosion_cells = None  # Store explosion cells when bomb explodes
        self.powerup_cells = set()  # Store cells that had powerups when explosion happened
        self.velocity_x = 0.0  # Horizontal velocity for kicking (pixels per frame)
        self.velocity_y = 0.0  # Vertical velocity for kicking (pixels per frame)
        self.is_moving = False  # Whether bomb is currently being kicked
        self.is_thrown = False  # Whether bomb is currently being thrown (timer paused)
        self.throw_start_time = None  # Time when bomb started being thrown (to track paused duration)
        self.can_be_kicked = False  # Whether player has left this bomb's cell at least once
        self.left_time = None  # Timestamp when player left this bomb's cell
        self.step_off_cooldown = 0  # Frames to wait before allowing kick after player steps off
        self.just_started_moving = False  # Flag to track if bomb just started moving this frame
    
    def should_explode(self, current_time):
        # If bomb is being thrown, timer is paused
        if self.is_thrown:
            return False
        return current_time - self.placed_time >= BOMB_EXPLOSION_TIME
    
    def is_exploding(self, current_time):
        """Check if bomb is currently in explosion animation"""
        if not self.exploded:
            return False
        if self.explosion_start_time is None:
            return False
        return current_time - self.explosion_start_time < BOMB_EXPLOSION_DURATION
    
    def get_pixel_pos(self):
        return (self.pixel_x, self.pixel_y)
    
    def update_grid_pos(self):
        """Update grid position based on pixel position"""
        self.grid_x = int(self.pixel_x // CELL_SIZE)
        self.grid_y = int(self.pixel_y // CELL_SIZE)

# Active bombs
bombs = []

# Helper function to remove chroma key green background
def remove_chroma_key(surface):
    """Remove light green chroma key background from a surface"""
    corner_color = surface.get_at((0, 0))
    chroma_colors = [
        corner_color[:3],
        (152, 248, 152),
        (144, 248, 144),
        (160, 248, 160),
    ]
    
    result = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    for x in range(surface.get_width()):
        for y in range(surface.get_height()):
            pixel = surface.get_at((x, y))
            r, g, b = pixel[:3]
            is_chroma = False
            for chroma_r, chroma_g, chroma_b in chroma_colors:
                if abs(r - chroma_r) < 30 and abs(g - chroma_g) < 30 and abs(b - chroma_b) < 30:
                    is_chroma = True
                    break
            if not is_chroma and g > 200 and r < 200 and b < 200:
                is_chroma = True
            
            if not is_chroma:
                result.set_at((x, y), (r, g, b, 255))
    return result

# Load bomb sprites for pulsing animation (2nd, 3rd, 4th sprites from first row)
bomb_sprites = []  # List of bomb animation frames
bomb_sprite_loaded = False
BOMB_ANIMATION_SPEED = 200  # milliseconds per frame
try:
    # Suppress libpng warnings about incorrect sRGB profile
    # Redirect stderr temporarily to suppress libpng warnings
    old_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        bomb_sprite_sheet = pygame.image.load("SNES - Super Bomberman 2 - Miscellaneous - Bombs.png")
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr
    bomb_sprite_sheet = bomb_sprite_sheet.convert()
    
    BOMB_SPRITE_SIZE = 16  # Typical SNES sprite size
    # Extract 1st, 2nd, and 3rd sprites from row 8 (y=128, 8 rows down from y=0)
    # 1st sprite: x=0, 2nd sprite: x=16, 3rd sprite: x=32
    BOMB_ROW_Y = 128  # 8 rows down (8 * 16 = 128)
    bomb_sprite_positions = [0, 16, 32]  # x coordinates for sprites 1, 2, 3
    
    for x_pos in bomb_sprite_positions:
        bomb_sprite = pygame.Surface((BOMB_SPRITE_SIZE, BOMB_SPRITE_SIZE))
        bomb_sprite.blit(bomb_sprite_sheet, (0, 0), (x_pos, BOMB_ROW_Y, BOMB_SPRITE_SIZE, BOMB_SPRITE_SIZE))
        
        # Remove chroma key green background using the helper function
        bomb_sprite = remove_chroma_key(bomb_sprite)
        
        # Scale with alpha preservation
        bomb_sprite = pygame.transform.scale(bomb_sprite, (CELL_SIZE, CELL_SIZE))
        bomb_sprites.append(bomb_sprite)
    
    bomb_sprite_loaded = True
except Exception as e:
    bomb_sprite_loaded = False
    print(f"Warning: Could not load bomb sprites: {e}. Using default circle.")

# Load player sprites for all directions with walking animations
# Dictionary: 'up', 'right', 'down', 'left' -> list of sprites [idle, walk1, walk2]
player_sprites = {}
player_sprite_loaded = False
try:
    # Suppress libpng warnings about incorrect sRGB profile
    old_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        player_sprite_sheet = pygame.image.load("SNES - Super Bomberman 2 - Playable Characters - Bomberman.png")
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr
    player_sprite_sheet = player_sprite_sheet.convert()
    # Player sprites have a 1:2 aspect ratio (width:height), so 16x32 pixels
    # Rows: 1st row (y=0) = up, 2nd row (y=32) = right, 3rd row (y=64) = down, 4th row (y=96) = left
    # Columns: 1st column (x=0) = idle, 2nd column (x=16) = walk frame 1, 3rd column (x=32) = walk frame 2
    PLAYER_SPRITE_WIDTH = 16
    PLAYER_SPRITE_HEIGHT = 32
    
    directions = {
        'up': 0,      # Row 1: y = 0
        'right': 32,  # Row 2: y = 32
        'down': 64,   # Row 3: y = 64
        'left': 96    # Row 4: y = 96
    }
    
    # Column offsets for animation frames
    columns = {
        'idle': 0,    # Column 1: x = 0
        'walk1': 16,  # Column 2: x = 16
        'walk2': 32   # Column 3: x = 32
    }
    
    for direction, y_offset in directions.items():
        direction_sprites = []
        for frame_name, x_offset in columns.items():
            sprite = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
            sprite.blit(player_sprite_sheet, (0, 0), (x_offset, y_offset, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
            
            # Remove chroma key green background using the helper function
            sprite = remove_chroma_key(sprite)
            # Scale player sprite to be 2.5x bigger (maintain 1:2 aspect ratio)
            # 16x32 becomes 40x80
            new_width = int(PLAYER_SPRITE_WIDTH * 2.5)
            new_height = int(PLAYER_SPRITE_HEIGHT * 2.5)
            sprite = pygame.transform.scale(sprite, (new_width, new_height))
            direction_sprites.append(sprite)
        
        player_sprites[direction] = direction_sprites  # [idle, walk1, walk2]
    
    player_sprite_loaded = True
    
    # Load death animation sprites
    # Player sprites are 16x32 pixels, rows are 32 pixels apart
    # Row 11 (1-indexed) = y = 10 * 32 = 320
    # Row 12 (1-indexed) = y = 11 * 32 = 352
    # Row 5 (1-indexed) = y = 4 * 32 = 128
    # Columns are 16 pixels apart
    # Sprite 1 = x = 0, Sprite 2 = x = 16, Sprite 3 = x = 32, Sprite 4 = x = 48, Sprite 5 = x = 64
    death_sprites = []
    DEATH_ROW_11_Y = 10 * 32  # Row 11 (1-indexed) = 320
    DEATH_ROW_12_Y = 11 * 32  # Row 12 (1-indexed) = 352
    DEATH_ROW_5_Y = 4 * 32    # Row 5 (1-indexed) = 128
    
    # Front facing: row 11, sprite 1 (x=0)
    front_sprite = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    front_sprite.blit(player_sprite_sheet, (0, 0), (0, DEATH_ROW_11_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    front_sprite = remove_chroma_key(front_sprite)
    front_sprite = pygame.transform.scale(front_sprite, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
    death_sprites.append(front_sprite)
    
    # Right facing: row 11, sprite 2 (x=16)
    right_sprite = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    right_sprite.blit(player_sprite_sheet, (0, 0), (16, DEATH_ROW_11_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    right_sprite = remove_chroma_key(right_sprite)
    right_sprite = pygame.transform.scale(right_sprite, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
    death_sprites.append(right_sprite)
    
    # Back facing: row 5, sprite 1 (x=0)
    back_sprite = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    back_sprite.blit(player_sprite_sheet, (0, 0), (0, DEATH_ROW_5_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    back_sprite = remove_chroma_key(back_sprite)
    back_sprite = pygame.transform.scale(back_sprite, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
    death_sprites.append(back_sprite)
    
    # Left facing: row 11, sprite 3 (x=32)
    left_sprite = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    left_sprite.blit(player_sprite_sheet, (0, 0), (32, DEATH_ROW_11_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    left_sprite = remove_chroma_key(left_sprite)
    left_sprite = pygame.transform.scale(left_sprite, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
    death_sprites.append(left_sprite)
    
    # Additional death animation sprites
    # Row 11, sprite 4 (x=48)
    row11_sprite4 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    row11_sprite4.blit(player_sprite_sheet, (0, 0), (48, DEATH_ROW_11_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    row11_sprite4 = remove_chroma_key(row11_sprite4)
    row11_sprite4 = pygame.transform.scale(row11_sprite4, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
    death_sprites.append(row11_sprite4)
    
    # Row 12, sprite 1 (x=0)
    row12_sprite1 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    row12_sprite1.blit(player_sprite_sheet, (0, 0), (0, DEATH_ROW_12_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    row12_sprite1 = remove_chroma_key(row12_sprite1)
    row12_sprite1 = pygame.transform.scale(row12_sprite1, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
    death_sprites.append(row12_sprite1)
    
    # Row 12, sprite 2 (x=16)
    row12_sprite2 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    row12_sprite2.blit(player_sprite_sheet, (0, 0), (16, DEATH_ROW_12_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    row12_sprite2 = remove_chroma_key(row12_sprite2)
    row12_sprite2 = pygame.transform.scale(row12_sprite2, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
    death_sprites.append(row12_sprite2)
    
    # Row 12, sprite 3 (x=32)
    row12_sprite3 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    row12_sprite3.blit(player_sprite_sheet, (0, 0), (32, DEATH_ROW_12_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    row12_sprite3 = remove_chroma_key(row12_sprite3)
    row12_sprite3 = pygame.transform.scale(row12_sprite3, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
    death_sprites.append(row12_sprite3)
    
    # Row 12, sprite 4 (x=48)
    row12_sprite4 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    row12_sprite4.blit(player_sprite_sheet, (0, 0), (48, DEATH_ROW_12_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    row12_sprite4 = remove_chroma_key(row12_sprite4)
    row12_sprite4 = pygame.transform.scale(row12_sprite4, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
    death_sprites.append(row12_sprite4)
    
    # Row 12, sprite 5 (x=64)
    row12_sprite5 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    row12_sprite5.blit(player_sprite_sheet, (0, 0), (64, DEATH_ROW_12_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    row12_sprite5 = remove_chroma_key(row12_sprite5)
    row12_sprite5 = pygame.transform.scale(row12_sprite5, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
    death_sprites.append(row12_sprite5)
    
    # Load glove pickup animation sprites from row 7 (facing forward/down)
    # Row 7 (1-indexed) = y = 6 * 32 = 192
    # Sprites: 1 = x=0, 2 = x=16, 3 = x=32
    # Animation sequence: 2,3,2,1,2,3
    glove_pickup_sprites = []
    GLOVE_PICKUP_ROW_7_Y = 6 * 32  # Row 7 (1-indexed) = 192
    
    # Sprite 1 (x=0)
    glove_sprite1 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    glove_sprite1.blit(player_sprite_sheet, (0, 0), (0, GLOVE_PICKUP_ROW_7_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    glove_sprite1 = remove_chroma_key(glove_sprite1)
    glove_sprite1 = pygame.transform.scale(glove_sprite1, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
    glove_pickup_sprites.append(glove_sprite1)
    
    # Sprite 2 (x=16)
    glove_sprite2 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    glove_sprite2.blit(player_sprite_sheet, (0, 0), (16, GLOVE_PICKUP_ROW_7_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    glove_sprite2 = remove_chroma_key(glove_sprite2)
    glove_sprite2 = pygame.transform.scale(glove_sprite2, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
    glove_pickup_sprites.append(glove_sprite2)
    
    # Sprite 3 (x=32)
    glove_sprite3 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    glove_sprite3.blit(player_sprite_sheet, (0, 0), (32, GLOVE_PICKUP_ROW_7_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
    glove_sprite3 = remove_chroma_key(glove_sprite3)
    glove_sprite3 = pygame.transform.scale(glove_sprite3, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
    glove_pickup_sprites.append(glove_sprite3)
    
    glove_pickup_sprites_loaded = True
    
except Exception as e:
    player_sprite_loaded = False
    death_sprites = []
    glove_pickup_sprites = []
    glove_pickup_sprites_loaded = False
    print(f"Warning: Could not load player sprite: {e}. Using default circle.")

# Initialize death_sprites as empty list if not loaded
if 'death_sprites' not in globals():
    death_sprites = []

# Initialize glove_pickup_sprites as empty list if not loaded
if 'glove_pickup_sprites' not in globals():
    glove_pickup_sprites = []
    glove_pickup_sprites_loaded = False

# Load pause image
pause_image = None
pause_image_loaded = False
try:
    # Suppress libpng warnings about incorrect sRGB profile
    old_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        pause_image = pygame.image.load("pause.png")
        pause_image = pause_image.convert_alpha()  # Preserve transparency
        pause_image_loaded = True
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr
except Exception as e:
    pause_image_loaded = False
    print(f"Warning: Could not load pause image: {e}")

# Load explosion sprites from bomb sprite sheet
# Explosion sprites are typically arranged in the sprite sheet
# Common layout: center, horizontal, vertical, corners
explosion_sprites = {}
explosion_sprites_loaded = False

try:
    # Load the bomb sprite sheet (which contains explosions)
    # Suppress libpng warnings about incorrect sRGB profile
    # Redirect stderr temporarily to suppress libpng warnings
    old_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        explosion_sheet = pygame.image.load("SNES - Super Bomberman 2 - Miscellaneous - Bombs.png")
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr
    explosion_sheet = explosion_sheet.convert()
    
    SPRITE_SIZE = 16
    
    # Extract explosion sprites from rows 14 down to row 10 (8 rows down from original)
    # Original rows were 6 down to 2 (y=80, 64, 48, 32, 16)
    # 8 rows down (8 * 16 = 128 pixels): y=208, 192, 176, 160, 144
    # Animation starts at row 14 and works down to row 10
    # Column 7 (x=96): Center explosion - for bomb tile
    # Column 6 (x=80): Horizontal segments (left/right arms)
    # Column 5 (x=64): Vertical segments (up/down arms)
    # Column 4 (x=48): Right end sprite
    # Column 3 (x=32): Left end sprite
    # Column 2 (x=16): Bottom end sprite
    # Column 1 (x=0): Top end sprite
    
    # Store sprites by row: explosion_sprites[row_index][sprite_type]
    # Row indices: 0 = row 14 (y=208), 1 = row 13 (y=192), 2 = row 12 (y=176), 3 = row 11 (y=160), 4 = row 10 (y=144)
    explosion_rows = [208, 192, 176, 160, 144]  # y coordinates for rows 14, 13, 12, 11, 10 (8 rows down)
    
    explosion_types = {
        'center': 96,      # Column 7 - 4-way cross explosion
        'horizontal': 80,  # Column 6 - horizontal segment (left/right)
        'vertical': 64,    # Column 5 - vertical segment (up/down)
        'end_right': 48,  # Column 4 - right end
        'end_left': 32,   # Column 3 - left end
        'end_down': 16,   # Column 2 - bottom end
        'end_up': 0,      # Column 1 - top end
    }
    
    # Load sprites for each row
    explosion_sprites = {}  # Will be {row_index: {sprite_type: sprite}}
    for row_idx, row_y in enumerate(explosion_rows):
        explosion_sprites[row_idx] = {}
        for name, sx in explosion_types.items():
            sprite = pygame.Surface((SPRITE_SIZE, SPRITE_SIZE))
            sprite.blit(explosion_sheet, (0, 0), (sx, row_y, SPRITE_SIZE, SPRITE_SIZE))
            sprite = remove_chroma_key(sprite)
            sprite = pygame.transform.scale(sprite, (CELL_SIZE, CELL_SIZE))
            explosion_sprites[row_idx][name] = sprite
    
    # Create 'vertical_down' and 'vertical_up' aliases for backward compatibility
    for row_idx in explosion_sprites:
        explosion_sprites[row_idx]['vertical_down'] = explosion_sprites[row_idx]['vertical']
        explosion_sprites[row_idx]['vertical_up'] = explosion_sprites[row_idx]['vertical']
    
    explosion_sprites_loaded = True
except Exception as e:
    explosion_sprites_loaded = False
    print(f"Warning: Could not load explosion sprites: {e}. Using default visualization.")

# Load item explosion animation sprites from Bombs.png sprite sheet
# Column 7 (x=112), rows 9-13 (y=144, 160, 176, 192, 208) - 5 sprites between (112,144) and (127,223)
item_explosion_sprites = []
item_explosion_sprites_loaded = False
try:
    # Use the Bombs sprite sheet
    old_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        item_explosion_sheet = pygame.image.load("SNES - Super Bomberman 2 - Miscellaneous - Bombs.png")
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr
    item_explosion_sheet = item_explosion_sheet.convert()
    
    ITEM_EXPLOSION_SPRITE_SIZE = 16
    ITEM_EXPLOSION_COLUMN_X = 112  # Column 7 (x=112)
    # 5 sprites: y = 144, 160, 176, 192, 208 (rows 9, 10, 11, 12, 13)
    item_explosion_rows = [144, 160, 176, 192, 208]  # y coordinates for the 5 sprites
    
    for row_y in item_explosion_rows:
        item_sprite = pygame.Surface((ITEM_EXPLOSION_SPRITE_SIZE, ITEM_EXPLOSION_SPRITE_SIZE))
        item_sprite.blit(item_explosion_sheet, (0, 0), (ITEM_EXPLOSION_COLUMN_X, row_y, ITEM_EXPLOSION_SPRITE_SIZE, ITEM_EXPLOSION_SPRITE_SIZE))
        
        # Remove chroma key green background using the helper function
        item_sprite = remove_chroma_key(item_sprite)
        
        # Scale sprite
        item_sprite = pygame.transform.scale(item_sprite, (CELL_SIZE, CELL_SIZE))
        item_explosion_sprites.append(item_sprite)
    
    item_explosion_sprites_loaded = True
except Exception as e:
    item_explosion_sprites_loaded = False
    print(f"Warning: Could not load item explosion sprites: {e}.")

# Load stage tileset sprites
tileset_sprites = {}
tileset_loaded = False
try:
    # Suppress libpng warnings about incorrect sRGB profile
    old_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        tileset_sheet = pygame.image.load("SNES - Super Bomberman 2 - Tilesets - Battle Game Tiles.png")
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr
    tileset_sheet = tileset_sheet.convert_alpha()  # Use convert_alpha to preserve transparency
    
    # Blocks are 1:1 ratio (square), 16x16 pixels each on the tileset.
    # Based on user's coordinates:
    # 1st block: (0, 14) to (15, 29) - breakable blocks
    # 2nd block: (17, 14) to (32, 29) - unbreakable blocks  
    # 4th block: (51, 14) to (66, 29) - empty ground tiles
    
    BLOCK_SPRITE_SIZE = 16  # Blocks are 16x16 on the sheet
    
    # Extract breakable block sprite (1st block) - full 16x16 sprite at (0, 14)
    breakable_rect = pygame.Rect(0, 14, BLOCK_SPRITE_SIZE, BLOCK_SPRITE_SIZE)
    breakable_tile = tileset_sheet.subsurface(breakable_rect).copy()
    breakable_tile = breakable_tile.convert_alpha()
    # Verify we got the full sprite
    if breakable_tile.get_width() != BLOCK_SPRITE_SIZE or breakable_tile.get_height() != BLOCK_SPRITE_SIZE:
        raise ValueError(f"Breakable tile wrong size: {breakable_tile.get_size()}, expected ({BLOCK_SPRITE_SIZE}, {BLOCK_SPRITE_SIZE})")
    breakable_tile = pygame.transform.scale(breakable_tile, (CELL_SIZE, CELL_SIZE))
    tileset_sprites['breakable'] = breakable_tile
    
    # Load breaking animation sprites from second row (row 1, y=30)
    # Extract breaking animation frames from row 1
    breaking_animation_sprites = []
    BREAKING_ROW_Y = 30  # Second row (row 0 is y=14, row 1 is y=30)
    # Load multiple frames from the second row (assuming same x positions as first row)
    breaking_sprite_positions = [0, 16, 32]  # x coordinates for breaking animation frames
    for x_pos in breaking_sprite_positions:
        breaking_sprite = pygame.Surface((BLOCK_SPRITE_SIZE, BLOCK_SPRITE_SIZE))
        breaking_sprite.blit(tileset_sheet, (0, 0), (x_pos, BREAKING_ROW_Y, BLOCK_SPRITE_SIZE, BLOCK_SPRITE_SIZE))
        breaking_sprite = breaking_sprite.convert()
        
        # Remove chroma key green background using the helper function
        breaking_sprite = remove_chroma_key(breaking_sprite)
        
        if breaking_sprite.get_width() != BLOCK_SPRITE_SIZE or breaking_sprite.get_height() != BLOCK_SPRITE_SIZE:
            raise ValueError(f"Breaking sprite wrong size: {breaking_sprite.get_size()}, expected ({BLOCK_SPRITE_SIZE}, {BLOCK_SPRITE_SIZE})")
        breaking_sprite = pygame.transform.scale(breaking_sprite, (CELL_SIZE, CELL_SIZE))
        breaking_animation_sprites.append(breaking_sprite)
    tileset_sprites['breaking'] = breaking_animation_sprites
    
    # Extract unbreakable block sprite (2nd block) - full 16x16 sprite at (17, 14)
    unbreakable_rect = pygame.Rect(17, 14, BLOCK_SPRITE_SIZE, BLOCK_SPRITE_SIZE)
    unbreakable_tile = tileset_sheet.subsurface(unbreakable_rect).copy()
    unbreakable_tile = unbreakable_tile.convert_alpha()
    if unbreakable_tile.get_width() != BLOCK_SPRITE_SIZE or unbreakable_tile.get_height() != BLOCK_SPRITE_SIZE:
        raise ValueError(f"Unbreakable tile wrong size: {unbreakable_tile.get_size()}, expected ({BLOCK_SPRITE_SIZE}, {BLOCK_SPRITE_SIZE})")
    unbreakable_tile = pygame.transform.scale(unbreakable_tile, (CELL_SIZE, CELL_SIZE))
    tileset_sprites['unbreakable'] = unbreakable_tile
    
    # Extract ground tile sprite (4th block) - full 16x16 sprite at (51, 14)
    ground_rect = pygame.Rect(51, 14, BLOCK_SPRITE_SIZE, BLOCK_SPRITE_SIZE)
    ground_tile = tileset_sheet.subsurface(ground_rect).copy()
    ground_tile = ground_tile.convert_alpha()
    if ground_tile.get_width() != BLOCK_SPRITE_SIZE or ground_tile.get_height() != BLOCK_SPRITE_SIZE:
        raise ValueError(f"Ground tile wrong size: {ground_tile.get_size()}, expected ({BLOCK_SPRITE_SIZE}, {BLOCK_SPRITE_SIZE})")
    ground_tile = pygame.transform.scale(ground_tile, (CELL_SIZE, CELL_SIZE))
    tileset_sprites['ground'] = ground_tile
    
    # Extract ground tile with wall above sprite (5th block) - full 16x16 sprite at (68, 14)
    ground_wall_above_rect = pygame.Rect(68, 14, BLOCK_SPRITE_SIZE, BLOCK_SPRITE_SIZE)
    ground_wall_above_tile = tileset_sheet.subsurface(ground_wall_above_rect).copy()
    ground_wall_above_tile = ground_wall_above_tile.convert_alpha()
    if ground_wall_above_tile.get_width() != BLOCK_SPRITE_SIZE or ground_wall_above_tile.get_height() != BLOCK_SPRITE_SIZE:
        raise ValueError(f"Ground wall above tile wrong size: {ground_wall_above_tile.get_size()}, expected ({BLOCK_SPRITE_SIZE}, {BLOCK_SPRITE_SIZE})")
    ground_wall_above_tile = pygame.transform.scale(ground_wall_above_tile, (CELL_SIZE, CELL_SIZE))
    tileset_sprites['ground_wall_above'] = ground_wall_above_tile
    
    tileset_loaded = True
except Exception as e:
    tileset_loaded = False
    print(f"Warning: Could not load tileset sprites: {e}. Using default drawing.")

# Load powerup sprites from items spritesheet (blue and red outline versions)
powerup_sprites = []  # List of bomb powerup animation frames [blue, red]
speed_powerup_sprites = []  # List of speed powerup animation frames [blue, red]
fire_powerup_sprites = []  # List of fire powerup animation frames [blue, red]
kick_powerup_sprites = []  # List of kick powerup animation frames [blue, red]
glove_powerup_sprites = []  # List of glove powerup animation frames [blue, red]
powerup_sprite_loaded = False
speed_powerup_sprite_loaded = False
fire_powerup_sprite_loaded = False
kick_powerup_sprite_loaded = False
glove_powerup_sprite_loaded = False
POWERUP_ANIMATION_SPEED = 100  # milliseconds per frame (switches every 100ms for very fast flashing)
try:
    # Suppress libpng warnings about incorrect sRGB profile
    old_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        items_sheet = pygame.image.load("SNES - Super Bomberman 2 - Miscellaneous - Items.png")
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr
    items_sheet = items_sheet.convert_alpha()  # Use convert_alpha to preserve transparency and colors
    
    POWERUP_SPRITE_SIZE = 16
    
    # Helper function to process a powerup sprite
    def process_powerup_sprite(sprite_surface):
        """Process a powerup sprite: remove chroma key and scale"""
        # Convert to surface with alpha channel for transparency
        sprite_surface = sprite_surface.convert_alpha()
        
        # Remove chroma key green background but preserve ALL colored pixels (red/blue outlines)
        # Only remove pixels that are clearly the green background color
        corner_color = sprite_surface.get_at((0, 0))
        corner_r, corner_g, corner_b, corner_a = corner_color
        
        result = pygame.Surface(sprite_surface.get_size(), pygame.SRCALPHA)
        for x in range(sprite_surface.get_width()):
            for y in range(sprite_surface.get_height()):
                pixel = sprite_surface.get_at((x, y))
                r, g, b, a = pixel
                
                # Only remove if it's clearly the green background
                # Check if it matches corner color (the green background)
                matches_corner = (
                    abs(r - corner_r) < 20 and 
                    abs(g - corner_g) < 20 and 
                    abs(b - corner_b) < 20
                )
                
                # Also check for bright green chroma key colors
                is_bright_green = (g > 200 and r < 150 and b < 150)
                
                # Only remove green background, preserve everything else (including outlines)
                # Red outlines will have high red values, blue outlines will have high blue values
                if not (matches_corner and corner_g > 150) and not is_bright_green:
                    result.set_at((x, y), (r, g, b, 255))
        
        sprite_surface = result
        
        # Scale powerup sprite
        sprite_surface = pygame.transform.scale(sprite_surface, (CELL_SIZE, CELL_SIZE))
        return sprite_surface
    
    # Load bomb powerup sprites:
    # First sprite on first row (blue outline) at (0, 0)
    # First sprite on 4th row (red outline) at (0, 48) - row 4 = y = 3 * 16 = 48
    bomb_powerup_rows = [0, 48]  # y coordinates for row 1 and row 4
    
    for y_pos in bomb_powerup_rows:
        powerup_sprite = pygame.Surface((POWERUP_SPRITE_SIZE, POWERUP_SPRITE_SIZE), pygame.SRCALPHA)
        powerup_sprite.blit(items_sheet, (0, 0), (0, y_pos, POWERUP_SPRITE_SIZE, POWERUP_SPRITE_SIZE))
        powerup_sprite = process_powerup_sprite(powerup_sprite)
        powerup_sprites.append(powerup_sprite)
    
    powerup_sprite_loaded = True
    
    # Load speed powerup sprites:
    # User specified: 2nd sprite on 2nd row is red, 2nd sprite on 5th row is blue
    # To match bomb powerup (blue first at index 0, then red at index 1)
    # If currently starting on red, the colors may be reversed - trying swapped order
    speed_powerup_positions = [(16, 16), (16, 64)]  # Swapped: [row 2, row 5] - testing if row 2 is actually blue
    
    for x_pos, y_pos in speed_powerup_positions:
        speed_sprite = pygame.Surface((POWERUP_SPRITE_SIZE, POWERUP_SPRITE_SIZE), pygame.SRCALPHA)
        speed_sprite.blit(items_sheet, (0, 0), (x_pos, y_pos, POWERUP_SPRITE_SIZE, POWERUP_SPRITE_SIZE))
        speed_sprite = process_powerup_sprite(speed_sprite)
        speed_powerup_sprites.append(speed_sprite)
    
    speed_powerup_sprite_loaded = True
    
    # Load fire powerup sprites:
    # Blue fire sprite on row 4, column 2 at (16, 48) - row 4 = y = 3 * 16 = 48
    # Red fire sprite on row 1, column 2 at (16, 0) - row 1 = y = 0 * 16 = 0
    # Loading blue first (row 4) then red (row 1) to match bomb powerup animation order (blue at index 0, red at index 1)
    # If starting on red, the colors may be reversed - swapping to ensure blue is first
    fire_powerup_positions = [(16, 0), (16, 48)]  # Swapped: [row 1, row 4] - testing if row 1 is actually blue
    
    for x_pos, y_pos in fire_powerup_positions:
        fire_sprite = pygame.Surface((POWERUP_SPRITE_SIZE, POWERUP_SPRITE_SIZE), pygame.SRCALPHA)
        fire_sprite.blit(items_sheet, (0, 0), (x_pos, y_pos, POWERUP_SPRITE_SIZE, POWERUP_SPRITE_SIZE))
        fire_sprite = process_powerup_sprite(fire_sprite)
        fire_powerup_sprites.append(fire_sprite)
    
    fire_powerup_sprite_loaded = True
    
    # Load kick powerup sprites:
    # Blue sprite on 2nd row (y=16), 3rd column (x=32)
    # Red sprite on 5th row (y=64), 3rd column (x=32)
    # Loading blue first then red to match animation order (blue at index 0, red at index 1)
    kick_powerup_positions = [(32, 16), (32, 64)]  # [blue (row 2), red (row 5)]
    
    for x_pos, y_pos in kick_powerup_positions:
        kick_sprite = pygame.Surface((POWERUP_SPRITE_SIZE, POWERUP_SPRITE_SIZE), pygame.SRCALPHA)
        kick_sprite.blit(items_sheet, (0, 0), (x_pos, y_pos, POWERUP_SPRITE_SIZE, POWERUP_SPRITE_SIZE))
        kick_sprite = process_powerup_sprite(kick_sprite)
        kick_powerup_sprites.append(kick_sprite)
    
    kick_powerup_sprite_loaded = True
    
    # Load glove powerup sprites:
    # Red sprite on 5th row (y=64), 4th column (x=48)
    # Blue sprite on 2nd row (y=16), 4th column (x=48)
    # Loading blue first then red to match animation order (blue at index 0, red at index 1)
    glove_powerup_positions = [(48, 16), (48, 64)]  # [blue (row 2), red (row 5)]
    
    for x_pos, y_pos in glove_powerup_positions:
        glove_sprite = pygame.Surface((POWERUP_SPRITE_SIZE, POWERUP_SPRITE_SIZE), pygame.SRCALPHA)
        glove_sprite.blit(items_sheet, (0, 0), (x_pos, y_pos, POWERUP_SPRITE_SIZE, POWERUP_SPRITE_SIZE))
        glove_sprite = process_powerup_sprite(glove_sprite)
        glove_powerup_sprites.append(glove_sprite)
    
    glove_powerup_sprite_loaded = True
except Exception as e:
    powerup_sprite_loaded = False
    speed_powerup_sprite_loaded = False
    fire_powerup_sprite_loaded = False
    kick_powerup_sprite_loaded = False
    glove_powerup_sprite_loaded = False
    print(f"Warning: Could not load powerup sprites: {e}. Using default circle.")

# Clock for controlling frame rate
clock = pygame.time.Clock()

def draw_ground():
    """Draw ground tiles for all empty cells"""
    if tileset_loaded:
        ground_tile = tileset_sprites.get('ground')
        ground_wall_above_tile = tileset_sprites.get('ground_wall_above')
        if ground_tile:
            # Draw ground tiles for all cells
            for x in range(GRID_WIDTH):
                for y in range(GRID_HEIGHT):
                    cell_x = x * CELL_SIZE
                    cell_y = y * CELL_SIZE
                    
                    # Check if there's a permanent wall above this cell
                    has_wall_above = False
                    if y > 0:  # Not at the top row
                        if (x, y - 1) in walls:
                            has_wall_above = True
                    
                    # Use appropriate sprite based on whether there's a wall above
                    if has_wall_above and ground_wall_above_tile:
                        window.blit(ground_wall_above_tile, (cell_x, cell_y))
                    else:
                        window.blit(ground_tile, (cell_x, cell_y))
    else:
        # Fallback: fill with green background
        window.fill(GREEN)

def draw_grid():
    """Draw the grid lines"""
    for x in range(0, WINDOW_WIDTH, CELL_SIZE):
        pygame.draw.line(window, GRAY, (x, 0), (x, WINDOW_HEIGHT))
    for y in range(0, WINDOW_HEIGHT, CELL_SIZE):
        pygame.draw.line(window, GRAY, (0, y), (WINDOW_WIDTH, y))

def draw_walls():
    """Draw permanent walls using tileset sprite"""
    if tileset_loaded:
        unbreakable_tile = tileset_sprites.get('unbreakable')
        if unbreakable_tile:
            for wall_x, wall_y in walls:
                x = wall_x * CELL_SIZE
                y = wall_y * CELL_SIZE
                window.blit(unbreakable_tile, (x, y))
        else:
            # Fallback to colored rectangles
            for wall_x, wall_y in walls:
                x = wall_x * CELL_SIZE
                y = wall_y * CELL_SIZE
                pygame.draw.rect(window, DARK_GRAY, (x, y, CELL_SIZE, CELL_SIZE))
                pygame.draw.rect(window, GRAY, (x, y, CELL_SIZE, CELL_SIZE), 2)
    else:
        # Fallback to colored rectangles
        for wall_x, wall_y in walls:
            x = wall_x * CELL_SIZE
            y = wall_y * CELL_SIZE
            pygame.draw.rect(window, DARK_GRAY, (x, y, CELL_SIZE, CELL_SIZE))
            pygame.draw.rect(window, GRAY, (x, y, CELL_SIZE, CELL_SIZE), 2)

def draw_destructible_walls(current_time=None):
    """Draw destructible walls using tileset sprite, with breaking animation"""
    if tileset_loaded:
        breakable_tile = tileset_sprites.get('breakable')
        breaking_sprites = tileset_sprites.get('breaking', [])
        
        if breakable_tile:
            # Draw normal breakable walls
            for wall_x, wall_y in destructible_walls:
                # Skip if this block is currently breaking
                if (wall_x, wall_y) in breaking_blocks:
                    continue
                x = wall_x * CELL_SIZE
                y = wall_y * CELL_SIZE
                window.blit(breakable_tile, (x, y))
            
            # Draw breaking animation
            if breaking_sprites and current_time is not None:
                ground_tile = tileset_sprites.get('ground')
                ground_wall_above_tile = tileset_sprites.get('ground_wall_above')
                blocks_to_remove = []
                for (wall_x, wall_y), start_time in breaking_blocks.items():
                    x = wall_x * CELL_SIZE
                    y = wall_y * CELL_SIZE
                    
                    # Draw ground tile behind breaking block first
                    if ground_tile or ground_wall_above_tile:
                        # Check if there's a permanent wall above this cell
                        has_wall_above = False
                        if wall_y > 0:  # Not at the top row
                            if (wall_x, wall_y - 1) in walls:
                                has_wall_above = True
                        
                        # Use appropriate ground sprite
                        if has_wall_above and ground_wall_above_tile:
                            window.blit(ground_wall_above_tile, (x, y))
                        elif ground_tile:
                            window.blit(ground_tile, (x, y))
                    
                    # Calculate animation progress (0.0 to 1.0)
                    elapsed = current_time - start_time
                    if elapsed >= BLOCK_BREAKING_DURATION:
                        # Animation complete, mark for removal
                        blocks_to_remove.append((wall_x, wall_y))
                    else:
                        # Select frame based on progress
                        progress = elapsed / BLOCK_BREAKING_DURATION
                        frame_index = int(progress * len(breaking_sprites))
                        frame_index = min(frame_index, len(breaking_sprites) - 1)
                        window.blit(breaking_sprites[frame_index], (x, y))
                
                # Remove completed breaking blocks and spawn powerup
                for block_pos in blocks_to_remove:
                    breaking_blocks.pop(block_pos, None)
                    # Spawn powerup at the block location (randomly choose between bomb_up, speed_up, fire_up, kick, and glove)
                    powerup_type = random.choice(['bomb_up', 'speed_up', 'fire_up', 'kick', 'glove'])
                    powerups[block_pos] = powerup_type
        else:
            # Fallback to colored rectangles
            for wall_x, wall_y in destructible_walls:
                if (wall_x, wall_y) in breaking_blocks:
                    continue
                x = wall_x * CELL_SIZE
                y = wall_y * CELL_SIZE
                pygame.draw.rect(window, BROWN, (x, y, CELL_SIZE, CELL_SIZE))
                pygame.draw.rect(window, DARK_GRAY, (x, y, CELL_SIZE, CELL_SIZE), 2)
    else:
        # Fallback to colored rectangles
        for wall_x, wall_y in destructible_walls:
            if (wall_x, wall_y) in breaking_blocks:
                continue
            x = wall_x * CELL_SIZE
            y = wall_y * CELL_SIZE
            pygame.draw.rect(window, BROWN, (x, y, CELL_SIZE, CELL_SIZE))
            pygame.draw.rect(window, DARK_GRAY, (x, y, CELL_SIZE, CELL_SIZE), 2)

def get_sprite_for_cell(grid_x, grid_y, bomb, animation_row=0):
    """Determine which explosion sprite to use for a cell relative to a bomb
    animation_row: 0 = row 6 (start), 4 = row 2 (end)"""
    dx = grid_x - bomb.grid_x
    dy = grid_y - bomb.grid_y
    
    # Get sprites for the current animation row
    row_sprites = explosion_sprites.get(animation_row, {})
    
    if dx == 0 and dy == 0:
        # Center of explosion - use center sprite (Column 7)
        sprite = row_sprites.get('center')
        if sprite:
            return sprite.copy(), 'center'
        return None, 'center'
    elif dx == 0:
        # Vertical line (up/down from center)
        if abs(dy) == BOMB_EXPLOSION_RANGE:
            # End of vertical line
            if dy > 0:
                sprite = row_sprites.get('end_down')
                if sprite:
                    return sprite.copy(), 'end_down'
            else:
                sprite = row_sprites.get('end_up')
                if sprite:
                    return sprite.copy(), 'end_up'
        else:
            # Middle of vertical line - use vertical segment (Column 5)
            vert = row_sprites.get('vertical')
            if vert:
                vert_copy = vert.copy()
                if dy < 0:
                    # Above bomb - rotate 180 to point up
                    return pygame.transform.rotate(vert_copy, 180), 'vertical_up'
                else:
                    # Below bomb - use as-is (points down)
                    return vert_copy, 'vertical_down'
        return None, 'vertical'
    elif dy == 0:
        # Horizontal line (left/right from center)
        if abs(dx) == BOMB_EXPLOSION_RANGE:
            # End of horizontal line
            if dx > 0:
                sprite = row_sprites.get('end_right')
                if sprite:
                    return sprite.copy(), 'end_right'
            else:
                sprite = row_sprites.get('end_left')
                if sprite:
                    return sprite.copy(), 'end_left'
        else:
            # Middle of horizontal line - use horizontal segment (Column 6)
            sprite = row_sprites.get('horizontal')
            if sprite:
                return sprite.copy(), 'horizontal'
        return None, 'horizontal'
    else:
        # Shouldn't happen in cross pattern, but use center as fallback
        sprite = row_sprites.get('center')
        if sprite:
            return sprite.copy(), 'center'
        return None, 'center'

def get_sprite_for_cell_from_pattern(grid_x, grid_y, all_explosion_cells, bomb_positions, animation_row=0):
    """Determine which explosion sprite to use for a cell based on the overall explosion pattern
    This fixes issues when multiple bombs overlap - determines sprite based on neighbors, not relative to individual bombs"""
    # Get sprites for the current animation row
    row_sprites = explosion_sprites.get(animation_row, {})
    
    # Check if this cell is a bomb center
    if (grid_x, grid_y) in bomb_positions:
        sprite = row_sprites.get('center')
        if sprite:
            return sprite.copy(), 'center'
        return None, 'center'
    
    # Check neighbors in all 4 directions
    has_left = (grid_x - 1, grid_y) in all_explosion_cells
    has_right = (grid_x + 1, grid_y) in all_explosion_cells
    has_up = (grid_x, grid_y - 1) in all_explosion_cells
    has_down = (grid_x, grid_y + 1) in all_explosion_cells
    
    # Determine if horizontal or vertical line
    is_horizontal = (has_left or has_right) and not (has_up or has_down)
    is_vertical = (has_up or has_down) and not (has_left or has_right)
    
    if is_horizontal:
        # Horizontal line
        if has_left and has_right:
            # Middle segment
            sprite = row_sprites.get('horizontal')
            if sprite:
                return sprite.copy(), 'horizontal'
        elif has_right:
            # Left end
            sprite = row_sprites.get('end_left')
            if sprite:
                return sprite.copy(), 'end_left'
        elif has_left:
            # Right end
            sprite = row_sprites.get('end_right')
            if sprite:
                return sprite.copy(), 'end_right'
        return None, 'horizontal'
    elif is_vertical:
        # Vertical line
        if has_up and has_down:
            # Middle segment
            vert = row_sprites.get('vertical')
            if vert:
                vert_copy = vert.copy()
                return vert_copy, 'vertical_down'
        elif has_down:
            # Top end
            sprite = row_sprites.get('end_up')
            if sprite:
                return sprite.copy(), 'end_up'
        elif has_up:
            # Bottom end
            sprite = row_sprites.get('end_down')
            if sprite:
                return sprite.copy(), 'end_down'
        return None, 'vertical'
    else:
        # Cross pattern or isolated - use center as fallback
        sprite = row_sprites.get('center')
        if sprite:
            return sprite.copy(), 'center'
        return None, 'center'

def draw_bombs(current_time):
    """Draw active bombs and their blast radius (only when exploding)"""
    # First, collect all explosion cells from all exploding bombs
    all_explosion_cells = set()  # Set of all (grid_x, grid_y) cells in explosions
    bomb_positions = set()  # Set of (grid_x, grid_y) positions where bombs are
    # Track cells that had powerups when explosion happened (to skip drawing explosion there)
    powerup_explosion_cells = set()
    
    # Find the earliest explosion start time to sync animation
    earliest_explosion_time = None
    for bomb in bombs:
        if bomb.is_exploding(current_time) and bomb.explosion_cells is not None:
            if earliest_explosion_time is None or bomb.explosion_start_time < earliest_explosion_time:
                earliest_explosion_time = bomb.explosion_start_time
            # Collect cells that had powerups when this bomb exploded
            if hasattr(bomb, 'powerup_cells'):
                powerup_explosion_cells.update(bomb.powerup_cells)
            # Collect all explosion cells
            for grid_x, grid_y in bomb.explosion_cells:
                all_explosion_cells.add((grid_x, grid_y))
            # Track bomb positions
            bomb_positions.add((bomb.grid_x, bomb.grid_y))
    
    # Calculate animation progress based on earliest explosion
    animation_row = 0
    if earliest_explosion_time is not None:
        explosion_progress = (current_time - earliest_explosion_time) / BOMB_EXPLOSION_DURATION
        # Map progress to row index: 0 (row 6) to 4 (row 2)
        animation_row = int(explosion_progress * 4.5)  # Reaches row 2 at ~89% of duration
        animation_row = min(animation_row, 4)  # Clamp to max row index (row 2)
    
    # Draw each cell using pattern-based sprite selection
    if explosion_sprites_loaded:
        for grid_x, grid_y in all_explosion_cells:
            # Skip drawing explosion if there's a breaking block, current powerup, or powerup was destroyed here
            if (grid_x, grid_y) in breaking_blocks or (grid_x, grid_y) in powerups or (grid_x, grid_y) in powerup_explosion_cells:
                continue
                
            cell_x = grid_x * CELL_SIZE
            cell_y = grid_y * CELL_SIZE
            
            # Get sprite based on overall explosion pattern
            sprite, sprite_type = get_sprite_for_cell_from_pattern(grid_x, grid_y, all_explosion_cells, bomb_positions, animation_row)
            
            if sprite:
                window.blit(sprite, (cell_x, cell_y))
    
    # Fallback to fiery explosion effect if sprites didn't load (also avoid overlapping)
    if not explosion_sprites_loaded:
        drawn_cells = set()
        for bomb in bombs:
            if bomb.is_exploding(current_time) and bomb.explosion_cells is not None:
                # Collect cells that had powerups when this bomb exploded
                if hasattr(bomb, 'powerup_cells'):
                    powerup_explosion_cells.update(bomb.powerup_cells)
                
                explosion_progress = (current_time - bomb.explosion_start_time) / BOMB_EXPLOSION_DURATION
                
                for grid_x, grid_y in bomb.explosion_cells:
                    if (grid_x, grid_y) in drawn_cells:
                        continue
                    # Skip drawing explosion if there's a breaking block, current powerup, or powerup was destroyed here
                    if (grid_x, grid_y) in breaking_blocks or (grid_x, grid_y) in powerups or (grid_x, grid_y) in powerup_explosion_cells:
                        continue
                    drawn_cells.add((grid_x, grid_y))
                    
                    cell_x = grid_x * CELL_SIZE
                    cell_y = grid_y * CELL_SIZE
                    
                    dx = grid_x - bomb.grid_x
                    dy = grid_y - bomb.grid_y
                    distance = (dx * dx + dy * dy) ** 0.5
                    max_distance = BOMB_EXPLOSION_RANGE
                    
                    pulse = 0.7 + 0.3 * abs(math.sin(explosion_progress * math.pi * 4))
                    alpha = int(180 * pulse)
                    
                    if distance == 0:
                        fire_color = (255, int(50 * pulse), 0)
                    elif distance <= max_distance / 2:
                        fire_color = (255, int(100 * pulse), int(20 * pulse))
                    else:
                        fire_color = (255, int(200 * pulse), int(50 * pulse))
                    
                    blast_surface = pygame.Surface((CELL_SIZE, CELL_SIZE))
                    blast_surface.set_alpha(alpha)
                    blast_surface.fill(fire_color)
                    window.blit(blast_surface, (cell_x, cell_y))
    
    # Draw bomb sprites (only if not exploded) with pulsing animation
    # Animation sequence: first sprite -> second sprite -> third sprite -> loop between second and third
    # Skip drawing bombs that are being held by player (they're drawn over player's head)
    for bomb in bombs:
        if not bomb.exploded:
                
            x, y = bomb.get_pixel_pos()
            if bomb_sprite_loaded and len(bomb_sprites) >= 3:
                # Calculate animation frame based on time elapsed since bomb was placed
                time_since_placed = current_time - bomb.placed_time
                frame_count = time_since_placed // BOMB_ANIMATION_SPEED
                
                # Animation sequence: 0 -> 1 -> 2 -> 1 -> 0 -> 1 -> 2 -> 1 -> 0 -> ...
                # Pattern: [0, 1, 2, 1, 0] repeating
                animation_pattern = [0, 1, 2, 1, 0]
                frame_index = animation_pattern[frame_count % len(animation_pattern)]
                
                bomb_sprite = bomb_sprites[frame_index]
                # Draw bomb sprite centered on bomb position
                sprite_rect = bomb_sprite.get_rect(center=(int(x), int(y)))
                window.blit(bomb_sprite, sprite_rect)
            else:
                # Fallback to circle if sprite didn't load
                pygame.draw.circle(window, ORANGE, (int(x), int(y)), CELL_SIZE // 3)
                pygame.draw.circle(window, BLACK, (int(x), int(y)), CELL_SIZE // 6)

def calculate_circle_rect_overlap(circle_x, circle_y, circle_radius, rect_x, rect_y, rect_width, rect_height):
    """Calculate the overlap area between a circle and rectangle
    Returns overlap percentage (0.0 to 1.0) of the circle area"""
    # Get circle bounding box
    circle_left = circle_x - circle_radius
    circle_right = circle_x + circle_radius
    circle_top = circle_y - circle_radius
    circle_bottom = circle_y + circle_radius
    
    # Get rectangle bounds
    rect_left = rect_x
    rect_right = rect_x + rect_width
    rect_top = rect_y
    rect_bottom = rect_y + rect_height
    
    # Check if they overlap at all
    if circle_right < rect_left or circle_left > rect_right or circle_bottom < rect_top or circle_top > rect_bottom:
        return 0.0
    
    # Calculate overlap by sampling points in the circle and checking if they're in the rectangle
    # This is an approximation - sample points in a grid within the circle
    circle_area = math.pi * circle_radius * circle_radius
    samples_per_dimension = 10
    step = (circle_radius * 2) / samples_per_dimension
    points_in_rect = 0
    total_points = 0
    
    for i in range(samples_per_dimension):
        for j in range(samples_per_dimension):
            # Sample point in circle bounding box
            sample_x = circle_left + i * step
            sample_y = circle_top + j * step
            
            # Check if point is inside circle
            dx = sample_x - circle_x
            dy = sample_y - circle_y
            dist_squared = dx * dx + dy * dy
            if dist_squared <= circle_radius * circle_radius:
                total_points += 1
                # Check if point is inside rectangle
                if rect_left <= sample_x <= rect_right and rect_top <= sample_y <= rect_bottom:
                    points_in_rect += 1
    
    if total_points == 0:
        return 0.0
    
    # Return overlap as percentage of circle area
    overlap_ratio = points_in_rect / total_points
    return overlap_ratio

def check_bomb_can_move(bomb, velocity_x, velocity_y):
    """Check if a bomb can move in the given direction (quick check before kicking)"""
    # Calculate where bomb would move to
    new_bomb_x = bomb.pixel_x + velocity_x
    new_bomb_y = bomb.pixel_y + velocity_y
    
    # Get bomb bounding box
    bomb_radius = CELL_SIZE // 2
    bomb_left = new_bomb_x - bomb_radius
    bomb_right = new_bomb_x + bomb_radius
    bomb_top = new_bomb_y - bomb_radius
    bomb_bottom = new_bomb_y + bomb_radius
    
    # Check bounds
    if bomb_left < 0 or bomb_right >= WINDOW_WIDTH:
        return False
    if bomb_top < 0 or bomb_bottom >= WINDOW_HEIGHT:
        return False
    
    # Check collision with walls (permanent and destructible)
    grid_left = int(bomb_left // CELL_SIZE)
    grid_right = int(bomb_right // CELL_SIZE)
    grid_top = int(bomb_top // CELL_SIZE)
    grid_bottom = int(bomb_bottom // CELL_SIZE)
    
    for grid_x in range(grid_left, grid_right + 1):
        for grid_y in range(grid_top, grid_bottom + 1):
            if (grid_x, grid_y) in walls or (grid_x, grid_y) in destructible_walls:
                # Check if bomb circle overlaps with wall cell
                wall_left = grid_x * CELL_SIZE
                wall_right = wall_left + CELL_SIZE
                wall_top = grid_y * CELL_SIZE
                wall_bottom = wall_top + CELL_SIZE
                
                # Find closest point on wall rectangle to bomb center
                closest_x = max(wall_left, min(new_bomb_x, wall_right))
                closest_y = max(wall_top, min(new_bomb_y, wall_bottom))
                
                dx = new_bomb_x - closest_x
                dy = new_bomb_y - closest_y
                distance_squared = dx * dx + dy * dy
                
                if distance_squared < bomb_radius * bomb_radius:
                    return False
    
    # Don't check collision with powerups - bombs pass through them
    # Powerups will be removed when bomb touches them in the movement update loop
    
    # Check collision with other bombs
    for other_bomb in bombs:
        if other_bomb == bomb or other_bomb.exploded:
            continue
        
        other_left = other_bomb.pixel_x - bomb_radius
        other_right = other_bomb.pixel_x + bomb_radius
        other_top = other_bomb.pixel_y - bomb_radius
        other_bottom = other_bomb.pixel_y + bomb_radius
        
        # Check if bounding boxes overlap
        if not (bomb_right < other_left or bomb_left > other_right or 
                bomb_bottom < other_top or bomb_top > other_bottom):
            # Check actual circle collision
            dx = new_bomb_x - other_bomb.pixel_x
            dy = new_bomb_y - other_bomb.pixel_y
            distance_squared = dx * dx + dy * dy
            
            if distance_squared < (bomb_radius * 2) * (bomb_radius * 2):
                return False
    
    return True

def check_collision(new_x, new_y, exclude_bomb=None):
    """Check if player would collide with walls or bombs at new position"""
    # Get player bounding box
    left = new_x - PLAYER_RADIUS
    right = new_x + PLAYER_RADIUS
    top = new_y - PLAYER_RADIUS
    bottom = new_y + PLAYER_RADIUS
    
    # Check bounds
    if left < 0 or right >= WINDOW_WIDTH or top < 0 or bottom >= WINDOW_HEIGHT:
        return True
    
    # Check collision with bombs (except the one player is currently on and the held bomb)
    for bomb in bombs:
        if bomb.exploded:
            continue
        # Skip the bomb the player is currently standing on
        if exclude_bomb is not None and bomb == exclude_bomb:
            continue
        # Skip the bomb being thrown (player can move through it)
        if bomb.is_thrown:
            continue
        # Check circle collision between player and bomb
        bomb_radius = CELL_SIZE // 2
        dx = new_x - bomb.pixel_x
        dy = new_y - bomb.pixel_y
        distance_squared = dx * dx + dy * dy
        if distance_squared < (PLAYER_RADIUS + bomb_radius) * (PLAYER_RADIUS + bomb_radius):
            return True
    
    # Check collision with walls (both permanent and destructible)
    # Convert pixel position to grid cells that might overlap
    grid_left = int(left // CELL_SIZE)
    grid_right = int(right // CELL_SIZE)
    grid_top = int(top // CELL_SIZE)
    grid_bottom = int(bottom // CELL_SIZE)
    
    for grid_x in range(grid_left, grid_right + 1):
        for grid_y in range(grid_top, grid_bottom + 1):
            # Check permanent walls
            if (grid_x, grid_y) in walls:
                # Check if player circle overlaps with this wall cell
                wall_left = grid_x * CELL_SIZE
                wall_right = wall_left + CELL_SIZE
                wall_top = grid_y * CELL_SIZE
                wall_bottom = wall_top + CELL_SIZE
                
                # Find closest point on wall rectangle to player center
                closest_x = max(wall_left, min(new_x, wall_right))
                closest_y = max(wall_top, min(new_y, wall_bottom))
                
                # Check distance from player center to closest point
                dx = new_x - closest_x
                dy = new_y - closest_y
                distance_squared = dx * dx + dy * dy
                
                # Add tolerance for corner smoothing (prevents getting stuck on corners)
                # Larger tolerance helps slide past corners more easily
                tolerance = 1.5
                if distance_squared < (PLAYER_RADIUS + tolerance) * (PLAYER_RADIUS + tolerance):
                    return True
            
            # Check destructible walls and breaking blocks
            if (grid_x, grid_y) in destructible_walls or (grid_x, grid_y) in breaking_blocks:
                # Same collision check as permanent walls
                wall_left = grid_x * CELL_SIZE
                wall_right = wall_left + CELL_SIZE
                wall_top = grid_y * CELL_SIZE
                wall_bottom = wall_top + CELL_SIZE
                
                closest_x = max(wall_left, min(new_x, wall_right))
                closest_y = max(wall_top, min(new_y, wall_bottom))
                
                dx = new_x - closest_x
                dy = new_y - closest_y
                distance_squared = dx * dx + dy * dy
                
                tolerance = 1.5
                if distance_squared < (PLAYER_RADIUS + tolerance) * (PLAYER_RADIUS + tolerance):
                    return True
    
    return False

def get_explosion_cells(bomb):
    """Get all cells that will be affected by bomb explosion"""
    explosion_cells = [(bomb.grid_x, bomb.grid_y)]  # Center
    
    # Add cells in each direction
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        for i in range(1, BOMB_EXPLOSION_RANGE + 1):
            x = bomb.grid_x + dx * i
            y = bomb.grid_y + dy * i
            
            # Stop if we hit a permanent wall (explosion doesn't go through)
            if (x, y) in walls:
                break
            
            # Add the cell (will be destroyed if it's a destructible wall or powerup)
            explosion_cells.append((x, y))
            
            # Stop if we hit a powerup, destructible wall, or breaking block (explosion stops here)
            if (x, y) in powerups or (x, y) in destructible_walls or (x, y) in breaking_blocks:
                break
    
    return explosion_cells

def get_explosion_visualization_cells(bomb):
    """Get cells to show in visualization - must match exactly what get_explosion_cells returns"""
    # Use the same logic as get_explosion_cells to ensure accuracy
    visualization_cells = []
    
    # Add cells in each direction
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        for i in range(1, BOMB_EXPLOSION_RANGE + 1):
            x = bomb.grid_x + dx * i
            y = bomb.grid_y + dy * i
            
            # Stop if we hit a permanent wall (explosion doesn't go through)
            if (x, y) in walls:
                break
            
            # Add the cell (matches get_explosion_cells logic)
            visualization_cells.append((x, y))
            
            # Stop if we hit a powerup, destructible wall, or breaking block (explosion stops here)
            if (x, y) in powerups or (x, y) in destructible_walls or (x, y) in breaking_blocks:
                break
    
    return visualization_cells

def check_player_in_explosion(player_x, player_y, explosion_cells):
    """Check if player is caught in explosion"""
    # Get player's grid position
    player_grid_x = int(player_x // CELL_SIZE)
    player_grid_y = int(player_y // CELL_SIZE)
    
    # Check if player's grid cell is in explosion cells
    return (player_grid_x, player_grid_y) in explosion_cells

def reset_game():
    """Reset the game state"""
    global player_x, player_y, bombs, destructible_walls, breaking_blocks, max_bombs, powerups, item_explosions, MOVE_SPEED, BOMB_EXPLOSION_RANGE, can_kick, has_glove, thrown_bomb, is_throwing, glove_pickup_animation_start_time
    
    # Reset player position to spawn
    player_x = 1 * CELL_SIZE + CELL_SIZE // 2
    player_y = 1 * CELL_SIZE + CELL_SIZE // 2
    
    # Clear all bombs
    bombs = []
    
    # Clear breaking blocks
    breaking_blocks = {}
    
    # Clear powerups
    powerups = {}
    
    # Clear item explosions
    item_explosions = {}
    
    # Reset max bombs to 1
    max_bombs = 1
    
    # Reset movement speed to default
    MOVE_SPEED = 3.0
    
    # Reset explosion range to default
    BOMB_EXPLOSION_RANGE = 2
    
    # Reset kick ability
    can_kick = False
    
    # Reset glove ability
    has_glove = False
    thrown_bomb = None
    is_throwing = False
    glove_pickup_animation_start_time = None
    
    # Regenerate destructible walls with random removal
    destructible_walls = generate_destructible_walls()

def explode_bomb(bomb, current_time, check_player_death=True):
    """Handle bomb explosion - destroy destructible walls in range and trigger chain explosions"""
    # Declare globals at function level so they're accessible in recursive calls
    global player_x, player_y, game_over, death_time, invincible, powerups, item_explosions
    
    if not bomb.exploded:
        bomb.exploded = True
        bomb.explosion_start_time = current_time
        
        # Play bomb explode sound effect
        if bomb_explode_sound:
            bomb_explode_sound.play()
        
        # Get explosion cells BEFORE destroying walls (so visualization is accurate)
        bomb.explosion_cells = get_explosion_cells(bomb)
        
        # Track which cells had powerups BEFORE removing them (so we can skip explosion graphics there)
        bomb.powerup_cells = set()
        for x, y in bomb.explosion_cells:
            if (x, y) in powerups:
                bomb.powerup_cells.add((x, y))
        
        # Check if player is caught in explosion (for both timer and chain explosions)
        if check_player_death:
            if check_player_in_explosion(player_x, player_y, bomb.explosion_cells):
                # Only kill player if not invincible
                if not invincible and not game_over:  # Only set once
                    game_over = True
                    death_time = current_time
        
        # Mark destructible walls for breaking animation instead of immediately removing
        for x, y in bomb.explosion_cells:
            if (x, y) in destructible_walls:
                # Start breaking animation
                breaking_blocks[(x, y)] = current_time
                # Remove from destructible_walls so it won't be drawn normally
                destructible_walls.remove((x, y))
            
            # Remove powerups caught in explosion and start item explosion animation
            if (x, y) in powerups:
                powerups.pop((x, y))
                # Start item explosion animation
                item_explosions[(x, y)] = current_time
        
        # Check for other bombs in explosion range and trigger chain explosions
        bombs_to_explode = []
        for other_bomb in bombs:
            if other_bomb == bomb or other_bomb.exploded:
                continue
            # Check if other bomb is in this explosion's cells
            if (other_bomb.grid_x, other_bomb.grid_y) in bomb.explosion_cells:
                bombs_to_explode.append(other_bomb)
        
        # Trigger chain explosions immediately (they will also check for player death)
        for chain_bomb in bombs_to_explode:
            explode_bomb(chain_bomb, current_time, check_player_death=True)


def draw_powerups(current_time=None):
    """Draw powerups on the ground with flashing animation"""
    # Calculate animation frame based on time (switches between blue and red)
    if current_time is not None:
        frame_index = int((current_time // POWERUP_ANIMATION_SPEED) % 2)  # Alternates between 0 and 1
    else:
        frame_index = 0  # Default to first frame
    
    for (grid_x, grid_y), powerup_type in powerups.items():
        # Skip if this powerup is currently exploding
        if (grid_x, grid_y) in item_explosions:
            continue
        
        x = grid_x * CELL_SIZE
        y = grid_y * CELL_SIZE
        
        # Select sprite based on powerup type
        if powerup_type == 'speed_up' and speed_powerup_sprite_loaded and len(speed_powerup_sprites) >= 2:
            powerup_sprite = speed_powerup_sprites[frame_index]
            window.blit(powerup_sprite, (x, y))
        elif powerup_type == 'bomb_up' and powerup_sprite_loaded and len(powerup_sprites) >= 2:
            powerup_sprite = powerup_sprites[frame_index]
            window.blit(powerup_sprite, (x, y))
        elif powerup_type == 'fire_up' and fire_powerup_sprite_loaded and len(fire_powerup_sprites) >= 2:
            powerup_sprite = fire_powerup_sprites[frame_index]
            window.blit(powerup_sprite, (x, y))
        elif powerup_type == 'kick' and kick_powerup_sprite_loaded and len(kick_powerup_sprites) >= 2:
            powerup_sprite = kick_powerup_sprites[frame_index]
            window.blit(powerup_sprite, (x, y))
        elif powerup_type == 'glove' and glove_powerup_sprite_loaded and len(glove_powerup_sprites) >= 2:
            powerup_sprite = glove_powerup_sprites[frame_index]
            window.blit(powerup_sprite, (x, y))
        else:
            # Fallback to colored circle if sprite didn't load
            x_center = grid_x * CELL_SIZE + CELL_SIZE // 2
            y_center = grid_y * CELL_SIZE + CELL_SIZE // 2
            # Use different colors for different powerup types
            if powerup_type == 'bomb_up':
                color = YELLOW
            elif powerup_type == 'speed_up':
                color = BLUE
            elif powerup_type == 'fire_up':
                color = RED
            elif powerup_type == 'kick':
                color = ORANGE
            elif powerup_type == 'glove':
                color = PURPLE  # Use purple as fallback color for glove
            else:
                color = YELLOW
            pygame.draw.circle(window, color, (x_center, y_center), CELL_SIZE // 3)

def draw_item_explosions(current_time=None):
    """Draw item explosion animations"""
    if item_explosion_sprites_loaded and len(item_explosion_sprites) >= 5 and current_time is not None:
        items_to_remove = []
        for (grid_x, grid_y), start_time in item_explosions.items():
            x = grid_x * CELL_SIZE
            y = grid_y * CELL_SIZE
            
            # Calculate animation progress (0.0 to 1.0)
            elapsed = current_time - start_time
            if elapsed >= ITEM_EXPLOSION_DURATION:
                # Animation complete, mark for removal
                items_to_remove.append((grid_x, grid_y))
            else:
                # Select frame based on progress (5 frames: rows 10-14)
                progress = elapsed / ITEM_EXPLOSION_DURATION
                frame_index = int(progress * len(item_explosion_sprites))
                frame_index = min(frame_index, len(item_explosion_sprites) - 1)
                window.blit(item_explosion_sprites[frame_index], (x, y))
        
        # Remove completed item explosions
        for item_pos in items_to_remove:
            item_explosions.pop(item_pos, None)

def draw_hitboxes():
    """Draw hitboxes for debugging"""
    # Draw player hitbox (circle)
    pygame.draw.circle(window, RED, (int(player_x), int(player_y)), PLAYER_RADIUS, 2)
    
    # Draw bomb hitboxes (cell-sized rectangles)
    for bomb in bombs:
        if not bomb.exploded:
            bomb_x = bomb.grid_x * CELL_SIZE
            bomb_y = bomb.grid_y * CELL_SIZE
            pygame.draw.rect(window, BLUE, (bomb_x, bomb_y, CELL_SIZE, CELL_SIZE), 2)
    
    # Draw wall hitboxes (cell-sized rectangles)
    for wall_x, wall_y in walls:
        x = wall_x * CELL_SIZE
        y = wall_y * CELL_SIZE
        pygame.draw.rect(window, GREEN, (x, y, CELL_SIZE, CELL_SIZE), 1)
    
    # Draw destructible wall hitboxes
    for wall_x, wall_y in destructible_walls:
        if (wall_x, wall_y) not in breaking_blocks:
            x = wall_x * CELL_SIZE
            y = wall_y * CELL_SIZE
            pygame.draw.rect(window, YELLOW, (x, y, CELL_SIZE, CELL_SIZE), 1)
    
    # Draw powerup hitboxes
    for (grid_x, grid_y), powerup_type in powerups.items():
        if (grid_x, grid_y) not in item_explosions:
            x = grid_x * CELL_SIZE
            y = grid_y * CELL_SIZE
            pygame.draw.rect(window, ORANGE, (x, y, CELL_SIZE, CELL_SIZE), 1)

def draw_player(current_time=None):
    """Draw the player at their current position with walking animation or death animation"""
    global player_direction, player_moving, game_over, death_time, glove_pickup_animation_start_time
    
    # Check if we should show death animation
    if game_over and death_time is not None and current_time is not None and death_sprites:
        # Death animation: 5 spins, getting slower
        # Each spin has 4 frames: front, right, back, left (20 frames total)
        # Frame durations: first spin very quick, gradually getting slower
        
        # Calculate total animation duration with specific pauses
        # Timing breakdown:
        # Frames 0-19: 5 spins (1500ms with easing)
        # Frame 20: Front-facing sprite (250ms pause)
        # Frame 21: Row 11, sprite 4 (0.1 seconds)
        # Frame 22: Row 12, sprite 1 (500ms pause)
        # Frame 23: Row 12, sprite 2 (0.1 seconds)
        # Frame 24: Row 12, sprite 3 (100ms pause)
        # Frames 25-34: Alternating sprites (sprite 4 and 5, 2 times each, 250ms pause per sprite)
        SPIN_DURATION = 1500  # milliseconds for spinning phase (with easing)
        FRONT_PAUSE_DURATION = 250  # milliseconds to pause on front-facing sprite (frame 20)
        FRAME_21_DURATION = 100  # Row 11, sprite 4 - 0.1 seconds
        FRAME_22_PAUSE_DURATION = 250  # Row 12, sprite 1 - pause for 0.25 seconds
        FRAME_23_DURATION = 100  # Row 12, sprite 2 - 0.1 seconds
        FRAME_24_PAUSE_DURATION = 500  # Row 12, sprite 3 - pause for 0.5 seconds
        # Frames 25-32: Sequence with 0.2 second delay between each frame
        # Pattern: sprite 4, sprite 3, sprite 5, sprite 3, sprite 4, sprite 3, sprite 5, sprite 3
        ALTERNATING_FRAME_DURATION = 200  # milliseconds per frame (0.2 second delay between frames)
        ALTERNATING_FRAMES = 7  # Frames 25-31 (7 frames before pause)
        FRAME_32_PAUSE_DURATION = 500  # Frame 32 - pause for 0.5 seconds
        ALTERNATING_TOTAL_DURATION = ALTERNATING_FRAMES * ALTERNATING_FRAME_DURATION + FRAME_32_PAUSE_DURATION  # 1400ms + 500ms = 1900ms
        
        # Calculate cumulative timings
        TIME_FRAME_20_START = SPIN_DURATION
        TIME_FRAME_20_END = TIME_FRAME_20_START + FRONT_PAUSE_DURATION
        TIME_FRAME_21_START = TIME_FRAME_20_END
        TIME_FRAME_21_END = TIME_FRAME_21_START + FRAME_21_DURATION
        TIME_FRAME_22_START = TIME_FRAME_21_END
        TIME_FRAME_22_END = TIME_FRAME_22_START + FRAME_22_PAUSE_DURATION
        TIME_FRAME_23_START = TIME_FRAME_22_END
        TIME_FRAME_23_END = TIME_FRAME_23_START + FRAME_23_DURATION
        TIME_FRAME_24_START = TIME_FRAME_23_END
        TIME_FRAME_24_END = TIME_FRAME_24_START + FRAME_24_PAUSE_DURATION
        TIME_ALTERNATING_START = TIME_FRAME_24_END
        TIME_FRAME_32_START = TIME_ALTERNATING_START + (ALTERNATING_FRAMES * ALTERNATING_FRAME_DURATION)
        TIME_FRAME_32_END = TIME_FRAME_32_START + FRAME_32_PAUSE_DURATION
        
        DEATH_ANIMATION_DURATION = TIME_FRAME_32_END  # Total duration (ends after frame 32 pause)
        elapsed = current_time - death_time
        
        if elapsed < DEATH_ANIMATION_DURATION:
            SPIN_FRAMES = 21  # Frames 0-20 (includes final front-facing sprite in easing)
            TOTAL_FRAMES = 33  # Frames 0-32 (removed frames 33-34)
            
            if elapsed < TIME_FRAME_20_START:
                # Spinning phase: use easing function (fast at start, slow at end)
                # Includes frames 0-20 (5 spins + final front-facing sprite)
                spin_progress = elapsed / SPIN_DURATION
                # Use quadratic easing out: t * (2 - t)
                eased_progress = spin_progress * (2 - spin_progress)
                frame_index = int(eased_progress * SPIN_FRAMES)
                frame_index = min(frame_index, SPIN_FRAMES - 1)
            elif elapsed < TIME_FRAME_20_END:
                # Pause after front-facing sprite (frame 20)
                frame_index = 20
            elif elapsed < TIME_FRAME_21_END:
                # Frame 21: Row 11, sprite 4 (immediate)
                frame_index = 21
            elif elapsed < TIME_FRAME_22_END:
                # Frame 22: Row 12, sprite 1 (pause for 0.25 seconds)
                frame_index = 22
            elif elapsed < TIME_FRAME_23_END:
                # Frame 23: Row 12, sprite 2 (0.1 seconds)
                frame_index = 23
            elif elapsed < TIME_FRAME_24_END:
                # Frame 24: Row 12, sprite 3 (pause for 0.5 seconds)
                frame_index = 24
            elif elapsed < TIME_FRAME_32_START:
                # Frames 25-31: Sequence with 0.2 second delay between frames
                alternating_elapsed = elapsed - TIME_ALTERNATING_START
                sprite_index_in_alternating = int(alternating_elapsed / ALTERNATING_FRAME_DURATION)
                sprite_index_in_alternating = min(sprite_index_in_alternating, ALTERNATING_FRAMES - 1)
                frame_index = 25 + sprite_index_in_alternating
            elif elapsed < TIME_FRAME_32_END:
                # Frame 32: Pause for 0.5 seconds
                frame_index = 32
            else:
                # Animation complete
                frame_index = 32
            
            # Determine sprite index based on frame
            if frame_index <= 20:
                # Spinning frames (0-20): 5 spins + final front-facing sprite (all part of easing)
                if frame_index == 20:
                    # Frame 20: Final front-facing sprite
                    sprite_index = 0  # Front
                else:
                    # Frames 0-19: 5 spins
                    frame_in_spin = frame_index % 4
                    if frame_in_spin == 0:
                        sprite_index = 0  # Front
                    elif frame_in_spin == 1:
                        sprite_index = 3  # Left
                    elif frame_in_spin == 2:
                        sprite_index = 2  # Back
                    else:  # frame_in_spin == 3
                        sprite_index = 1  # Right
            elif frame_index == 21:
                # Row 11, sprite 4
                sprite_index = 4  # death_sprites[4]
            elif frame_index == 22:
                # Row 12, sprite 1
                sprite_index = 5  # death_sprites[5]
            elif frame_index == 23:
                # Row 12, sprite 2
                sprite_index = 6  # death_sprites[6]
            elif frame_index == 24:
                # Row 12, sprite 3
                sprite_index = 7  # death_sprites[7]
            elif frame_index == 32:
                # Frame 32: Row 12, sprite 3 (pause for 0.5 seconds)
                sprite_index = 7  # death_sprites[7]
            else:
                # Frames 25-31: Sequence pattern with 0.2 second delay between frames
                # Pattern: sprite 4, sprite 3, sprite 5, sprite 3, sprite 4, sprite 3, sprite 5
                alternating_frame = frame_index - 25
                pattern = [8, 7, 9, 7, 8, 7, 9]  # sprite 4 (8), sprite 3 (7), sprite 5 (9), etc.
                sprite_index = pattern[alternating_frame] if alternating_frame < len(pattern) else 7  # Default to sprite 3
            
            # Use death sprites
            sprite = death_sprites[sprite_index]
            
            # Draw death sprite
            sprite_width, sprite_height = sprite.get_size()
            offset_below = 4
            sprite_x = int(player_x - sprite_width // 2)
            sprite_y = int((player_y + PLAYER_RADIUS + offset_below) - sprite_height)
            window.blit(sprite, (sprite_x, sprite_y))
            return
    
    # Check if we should show glove pickup animation
    # Animation plays when: player has glove, is standing on bomb, and facing down
    if (glove_pickup_animation_start_time is not None and current_time is not None and 
        glove_pickup_sprites_loaded and len(glove_pickup_sprites) >= 3):
        # Animation sequence: 2,3,2,1,2,3,2 (sprite indices: 1,2,1,0,1,2,1)
        # Each frame duration: 100ms (0.1 seconds)
        GLOVE_PICKUP_FRAME_DURATION = 100  # milliseconds per frame
        GLOVE_PICKUP_ANIMATION_DURATION = 7 * GLOVE_PICKUP_FRAME_DURATION  # 700ms total
        
        elapsed = current_time - glove_pickup_animation_start_time
        
        if elapsed < GLOVE_PICKUP_ANIMATION_DURATION:
            # Determine which frame to show based on elapsed time
            frame_index = int(elapsed / GLOVE_PICKUP_FRAME_DURATION)
            frame_index = min(frame_index, 6)  # Clamp to valid range (0-6)
            
            # Animation sequence: 2,3,2,1,2,3,2 (sprite indices: 1,2,1,0,1,2,1)
            sequence = [1, 2, 1, 0, 1, 2, 1]  # Indices into glove_pickup_sprites array
            sprite_index = sequence[frame_index]
            
            sprite = glove_pickup_sprites[sprite_index]
            
            # Draw glove pickup animation sprite
            sprite_width, sprite_height = sprite.get_size()
            offset_below = 4
            sprite_x = int(player_x - sprite_width // 2)
            sprite_y = int((player_y + PLAYER_RADIUS + offset_below) - sprite_height)
            window.blit(sprite, (sprite_x, sprite_y))
            return
        else:
            # Animation complete, reset
            glove_pickup_animation_start_time = None
    
    # Normal player drawing
    if player_sprite_loaded:
        # Get the sprites for the current direction (default to 'down' if not found)
        direction_sprites = player_sprites.get(player_direction, player_sprites.get('down'))
        if direction_sprites:
            # Choose animation frame based on movement
            if player_moving:
                # Animate between walk1 and walk2 frames
                # Use time-based animation (cycle every 200ms)
                if current_time:
                    frame_index = 1 + int((current_time // 200) % 2)  # Alternates between 1 and 2
                else:
                    frame_index = 1  # Default to walk1
                sprite = direction_sprites[frame_index]  # walk1 or walk2
            else:
                # Use idle frame when not moving
                sprite = direction_sprites[0]  # idle
            
            # Draw player sprite with bottom slightly below the hitbox bottom
            sprite_width, sprite_height = sprite.get_size()
            # Bottom of hitbox is at player_y + PLAYER_RADIUS
            # Position sprite so its bottom extends slightly below hitbox bottom
            offset_below = 4  # Pixels to extend below hitbox
            sprite_x = int(player_x - sprite_width // 2)  # Center horizontally
            sprite_y = int((player_y + PLAYER_RADIUS + offset_below) - sprite_height)  # Bottom slightly below hitbox
            window.blit(sprite, (sprite_x, sprite_y))
            
    else:
        # Fallback to circle if sprite didn't load
        pygame.draw.circle(window, WHITE, (int(player_x), int(player_y)), int(PLAYER_RADIUS))

def restart_music():
    """Restart the background music"""
    global music_muted
    try:
        pygame.mixer.music.stop()
        pygame.mixer.music.load("Super Bomberman 2 - Battle 1 (SNES OST).mp3")
        # Set volume based on mute state (music is quieter at 0.5 volume)
        if music_muted:
            pygame.mixer.music.set_volume(0.0)
        else:
            pygame.mixer.music.set_volume(0.5)  # Reduced from 1.0 to 0.5 (50% volume)
        pygame.mixer.music.play(-1)  # -1 means loop indefinitely
    except Exception as e:
        print(f"Warning: Could not load music: {e}")

def main():
    global player_x, player_y, bombs, game_over, death_time, player_direction, player_moving, invincible, max_bombs, MOVE_SPEED, BOMB_EXPLOSION_RANGE, can_kick, show_hitboxes, music_muted, thrown_bomb, is_throwing, has_glove, glove_pickup_animation_start_time
    
    # Load and play background music
    restart_music()
    
    running = True
    game_over = False
    death_time = None
    paused = False
    pause_start_time = None  # Time when we paused
    total_paused_time = 0  # Total time spent paused (accumulated)
    
    while running:
        current_time = pygame.time.get_ticks()
        
        # Handle events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    # Toggle pause
                    if paused:
                        # Unpausing - adjust all timers to account for paused time
                        if pause_start_time is not None:
                            paused_duration = current_time - pause_start_time
                            # Add paused duration to each bomb's placed_time so they resume correctly
                            for bomb in bombs:
                                if not bomb.exploded:
                                    bomb.placed_time += paused_duration
                                elif bomb.explosion_start_time is not None:
                                    # Adjust explosion start time so animation resumes correctly
                                    bomb.explosion_start_time += paused_duration
                            # Adjust breaking block animation timers
                            for block_pos in list(breaking_blocks.keys()):
                                breaking_blocks[block_pos] += paused_duration
                            # Adjust item explosion animation timers
                            for item_pos in list(item_explosions.keys()):
                                item_explosions[item_pos] += paused_duration
                            # Adjust death time if game is over
                            if death_time is not None:
                                death_time += paused_duration
                            pause_start_time = None
                        paused = False
                    else:
                        # Pausing - record when we paused
                        pause_start_time = current_time
                        paused = True
                    # Play pause jingle both when pausing and unpausing
                    if pause_jingle_sound:
                        pause_jingle_sound.play()
                elif event.key == pygame.K_r:
                    # Restart the game
                    reset_game()
                    game_over = False
                    death_time = None
                    paused = False
                    pause_start_time = None
                    restart_music()
                elif event.key == pygame.K_i:
                    # Toggle invincibility (only when not paused)
                    if not paused:
                        invincible = not invincible
                elif event.key == pygame.K_h:
                    # Toggle hitbox display (only when not paused)
                    if not paused:
                        show_hitboxes = not show_hitboxes
                elif event.key == pygame.K_m:
                    # Toggle music mute (works even when paused)
                    music_muted = not music_muted
                    if music_muted:
                        # Mute music
                        pygame.mixer.music.set_volume(0.0)
                    else:
                        # Unmute music (at reduced volume)
                        pygame.mixer.music.set_volume(0.5)  # Reduced from 1.0 to 0.5 (50% volume)
                elif event.key == pygame.K_SPACE:
                    # Only allow placing bombs when not paused and not in death animation
                    death_animation_playing = False
                    if game_over and death_time is not None:
                        DEATH_ANIMATION_DURATION = 4600
                        death_animation_playing = (current_time - death_time) < DEATH_ANIMATION_DURATION
                    if not paused and not death_animation_playing:
                        # Check if player is standing on a bomb with glove and facing down - start animation
                        player_grid_x = int(player_x // CELL_SIZE)
                        player_grid_y = int(player_y // CELL_SIZE)
                        player_bomb_check = None
                        for bomb in bombs:
                            if bomb.exploded:
                                continue
                            # Check if player is on this bomb using pixel collision
                            bomb_radius = CELL_SIZE // 2
                            dx = player_x - bomb.pixel_x
                            dy = player_y - bomb.pixel_y
                            distance_squared = dx * dx + dy * dy
                            if distance_squared < (PLAYER_RADIUS + bomb_radius) * (PLAYER_RADIUS + bomb_radius):
                                player_bomb_check = bomb
                                break
                        
                        # If standing on bomb with glove facing down, start animation
                        animation_started = False
                        if (has_glove and player_bomb_check is not None and player_direction == 'down' and 
                            not is_throwing):
                            glove_pickup_animation_start_time = current_time
                            animation_started = True
                        
                        # Only allow picking up/throwing if not already throwing, has glove, and animation didn't start
                        # (Animation starting prevents bomb throwing, but normal bomb placement can still happen)
                        if not is_throwing and has_glove and not animation_started:
                            # Try to pick up and throw a bomb in front of player
                            
                            # Determine position in front of player
                            front_x = player_grid_x
                            front_y = player_grid_y
                            if player_direction == 'up':
                                front_y -= 1
                            elif player_direction == 'down':
                                front_y += 1
                            elif player_direction == 'left':
                                front_x -= 1
                            elif player_direction == 'right':
                                front_x += 1
                            
                            # Check if there's a bomb in front of player
                            for bomb in bombs:
                                if (not bomb.exploded and bomb.grid_x == front_x and bomb.grid_y == front_y and
                                    not bomb.is_thrown and not bomb.is_moving):
                                    # Calculate throw destination (2 tiles ahead)
                                    throw_x = player_grid_x
                                    throw_y = player_grid_y
                                    if player_direction == 'up':
                                        throw_y -= 2
                                    elif player_direction == 'down':
                                        throw_y += 2
                                    elif player_direction == 'left':
                                        throw_x -= 2
                                    elif player_direction == 'right':
                                        throw_x += 2
                                    
                                    # Check if throw position is valid (not a wall and within bounds)
                                    if (0 <= throw_x < GRID_WIDTH and 0 <= throw_y < GRID_HEIGHT and
                                        (throw_x, throw_y) not in walls and (throw_x, throw_y) not in destructible_walls):
                                        # Check if there's already a bomb at throw position
                                        bomb_at_throw_pos = False
                                        for other_bomb in bombs:
                                            if other_bomb.grid_x == throw_x and other_bomb.grid_y == throw_y and not other_bomb.exploded:
                                                bomb_at_throw_pos = True
                                                break
                                        
                                        if not bomb_at_throw_pos:
                                            # Start throwing the bomb
                                            bomb.is_thrown = True
                                            bomb.throw_start_time = current_time
                                            bomb.is_moving = True
                                            thrown_bomb = bomb
                                            is_throwing = True
                                            
                                            # Set velocity to move bomb to throw position
                                            target_pixel_x = throw_x * CELL_SIZE + CELL_SIZE // 2
                                            target_pixel_y = throw_y * CELL_SIZE + CELL_SIZE // 2
                                            
                                            # Calculate direction and distance
                                            dx = target_pixel_x - bomb.pixel_x
                                            dy = target_pixel_y - bomb.pixel_y
                                            distance = math.sqrt(dx * dx + dy * dy)
                                            
                                            # Set throw speed (faster than kick speed)
                                            THROW_SPEED = 8.0  # pixels per frame
                                            if distance > 0:
                                                bomb.velocity_x = (dx / distance) * THROW_SPEED
                                                bomb.velocity_y = (dy / distance) * THROW_SPEED
                                            
                                            # Play place bomb sound effect
                                            if place_bomb_sound:
                                                place_bomb_sound.play()
                                            break
                        
                        # Only allow placing new bombs if not throwing
                        if not is_throwing:
                            # Count active bombs
                            active_bomb_count = 0
                            for bomb in bombs:
                                if not bomb.exploded:
                                    active_bomb_count += 1
                            
                            # Only allow placing a bomb if under the max limit
                            if active_bomb_count < max_bombs:
                                # Place bomb at player's current grid position
                                grid_x = int(player_x // CELL_SIZE)
                                grid_y = int(player_y // CELL_SIZE)
                            
                                # Check if there's already a bomb here (shouldn't happen, but safety check)
                                bomb_exists = False
                                for bomb in bombs:
                                    if bomb.grid_x == grid_x and bomb.grid_y == grid_y and not bomb.exploded:
                                        bomb_exists = True
                                        break
                                
                                # Check if position is clear (not a wall)
                                if not bomb_exists and (grid_x, grid_y) not in walls and (grid_x, grid_y) not in destructible_walls:
                                    new_bomb = Bomb(grid_x, grid_y, current_time)
                                    bombs.append(new_bomb)
                                    # Update player_bomb to the newly placed bomb so player doesn't get stuck
                                    player_bomb = new_bomb
                                    # Play place bomb sound effect
                                    if place_bomb_sound:
                                        place_bomb_sound.play()
        
        # Skip game logic updates when paused (but keep rendering and music)
        if paused:
            # Use frozen time (when we paused) for all animations
            frozen_time = pause_start_time if pause_start_time is not None else current_time
            # Still render the game (frozen state)
            draw_ground()
            draw_destructible_walls(frozen_time)
            draw_walls()
            draw_bombs(frozen_time)
            draw_powerups(frozen_time)
            draw_item_explosions(frozen_time)
            draw_player(frozen_time)
            if show_hitboxes:
                draw_hitboxes()
            
            # Draw pause image in the center of the screen (scaled down to 80% of original size)
            if pause_image_loaded and pause_image:
                original_width, original_height = pause_image.get_size()
                scale_factor = 0.8  # 80% of original size
                scaled_width = int(original_width * scale_factor)
                scaled_height = int(original_height * scale_factor)
                scaled_pause_image = pygame.transform.scale(pause_image, (scaled_width, scaled_height))
                pause_x = (WINDOW_WIDTH - scaled_width) // 2
                pause_y = (WINDOW_HEIGHT - scaled_height) // 2
                window.blit(scaled_pause_image, (pause_x, pause_y))
            
            pygame.display.flip()
            clock.tick(60)
            continue
        
        # Check for bomb explosions
        for bomb in bombs[:]:  # Use slice to avoid modification during iteration
            if bomb.should_explode(current_time) and not bomb.exploded:
                explode_bomb(bomb, current_time)
                # Death check is now handled inside explode_bomb for both timer and chain explosions
        
        # Remove exploded bombs after explosion duration has passed
        bombs = [bomb for bomb in bombs if not bomb.exploded or bomb.is_exploding(current_time)]
        
        # Handle game over - wait for death animation, then reset
        if game_over:
            # Wait for death animation to finish before resetting
            # Duration: 1500ms (spin) + 250ms (frame 20) + 100ms (frame 21) + 250ms (frame 22) + 100ms (frame 23) + 500ms (frame 24) + 1400ms (frames 25-31) + 500ms (frame 32) = 4600ms
            DEATH_ANIMATION_DURATION = 4600
            if death_time is not None and current_time - death_time >= DEATH_ANIMATION_DURATION:
                reset_game()
                game_over = False
                death_time = None
                restart_music()
                continue  # Skip rest of frame after reset
            else:
                # During death animation, prevent player movement and game logic
                # Skip all game logic updates, only render
                pass
        
        # Only allow movement if not dead and not paused
        # Also skip if death animation is still playing
        death_animation_playing = False
        if game_over and death_time is not None:
            DEATH_ANIMATION_DURATION = 4600
            death_animation_playing = (current_time - death_time) < DEATH_ANIMATION_DURATION
        
        if not game_over and not paused and not death_animation_playing:
            # Check for held keys (allows continuous smooth movement)
            keys = pygame.key.get_pressed()
            
            # Find which bomb (if any) the player is currently standing on
            player_grid_x = int(player_x // CELL_SIZE)
            player_grid_y = int(player_y // CELL_SIZE)
            player_bomb = None
            for bomb in bombs:
                if bomb.exploded:
                    continue
                # Check if player is on this bomb using pixel collision
                bomb_radius = CELL_SIZE // 2
                dx = player_x - bomb.pixel_x
                dy = player_y - bomb.pixel_y
                distance_squared = dx * dx + dy * dy
                if distance_squared < (PLAYER_RADIUS + bomb_radius) * (PLAYER_RADIUS + bomb_radius):
                    player_bomb = bomb
                    break
            
            # Reset animation if player moves off bomb or changes direction (but keep it running if still on bomb)
            if not (has_glove and player_bomb is not None and player_direction == 'down'):
                # Reset animation if player moves off bomb or changes direction
                glove_pickup_animation_start_time = None
            
            # Check if player collected a powerup
            player_pos = (player_grid_x, player_grid_y)
            if player_pos in powerups:
                powerup_type = powerups[player_pos]
                if powerup_type == 'bomb_up':
                    max_bombs += 1
                    # Play normal item get sound effect
                    if item_get_sound:
                        item_get_sound.play()
                elif powerup_type == 'speed_up':
                    MOVE_SPEED += 0.75  # Increase speed by 0.75
                    # Play normal item get sound effect
                    if item_get_sound:
                        item_get_sound.play()
                elif powerup_type == 'fire_up':
                    global BOMB_EXPLOSION_RANGE
                    BOMB_EXPLOSION_RANGE += 1  # Increase explosion radius by 1
                    # Play normal item get sound effect
                    if item_get_sound:
                        item_get_sound.play()
                elif powerup_type == 'kick':
                    global can_kick
                    can_kick = True  # Enable bomb kicking ability
                    # Play kick voice sound effect
                    if kick_voice_sound:
                        kick_voice_sound.play()
                elif powerup_type == 'glove':
                    has_glove = True  # Enable glove ability
                    # Play normal item get sound effect
                    if item_get_sound:
                        item_get_sound.play()
                powerups.pop(player_pos)  # Remove collected powerup
            
            # Store old position for corner resolution
            old_x = player_x
            old_y = player_y
            
            # Calculate new position based on movement
            new_x = player_x
            new_y = player_y
            
            # Move player with arrow keys (smooth pixel-based movement)
            # Track direction for sprite selection
            player_moving = False
            if keys[pygame.K_UP]:
                new_y = player_y - MOVE_SPEED
                player_direction = 'up'
                player_moving = True
            elif keys[pygame.K_DOWN]:
                new_y = player_y + MOVE_SPEED
                player_direction = 'down'
                player_moving = True
            
            if keys[pygame.K_LEFT]:
                new_x = player_x - MOVE_SPEED
                player_direction = 'left'
                player_moving = True
            elif keys[pygame.K_RIGHT]:
                new_x = player_x + MOVE_SPEED
                player_direction = 'right'
                player_moving = True
            
            # Check for bomb kicking - when player moves into contact with a bomb, kick it away
            # If player has kick ability and is moving, check if they're touching a bomb
            if can_kick and player_moving:
                # Check the target position the player is moving to
                target_grid_x = int(new_x // CELL_SIZE)
                target_grid_y = int(new_y // CELL_SIZE)
                current_grid_x = int(player_x // CELL_SIZE)
                current_grid_y = int(player_y // CELL_SIZE)
                
                # Don't kick if player is moving away from a bomb (stepping off)
                # Check if we're moving AWAY from the bomb we're currently on
                is_stepping_off_bomb = False
                bomb_being_stepped_off = None
                if player_bomb is not None:
                    # Check if we're moving away from the bomb using pixel positions
                    # Calculate distance from bomb before and after movement
                    dx_before = player_x - player_bomb.pixel_x
                    dy_before = player_y - player_bomb.pixel_y
                    distance_before = math.sqrt(dx_before * dx_before + dy_before * dy_before)
                    
                    dx_after = new_x - player_bomb.pixel_x
                    dy_after = new_y - player_bomb.pixel_y
                    distance_after = math.sqrt(dx_after * dx_after + dy_after * dy_after)
                    
                    # If distance is increasing significantly, we're moving away from the bomb
                    # Use a threshold to avoid false positives from small movements
                    bomb_radius = CELL_SIZE // 2
                    distance_threshold = 2.0  # Minimum distance increase to consider stepping off
                    if distance_after > distance_before + distance_threshold and distance_before < (PLAYER_RADIUS + bomb_radius + 15):
                        is_stepping_off_bomb = True
                        bomb_being_stepped_off = player_bomb
                        # Set cooldown immediately when stepping off
                        player_bomb.step_off_cooldown = 15  # 15 frames cooldown
                
                # Always exclude the bomb we're stepping off from, even if detection failed
                # Check if target cell has a bomb (that's not the one we're currently on)
                for bomb in bombs:
                    if bomb.exploded or bomb.is_moving:
                        continue
                    if bomb == player_bomb:
                        continue
                    # Don't kick the bomb we're stepping off from
                    if bomb == bomb_being_stepped_off:
                        continue
                    # Don't kick if bomb is in step-off cooldown period
                    if bomb.step_off_cooldown > 0:
                        continue
                    
                    # If we're stepping off ANY bomb, skip ALL kick checks to prevent accidental kicks
                    if is_stepping_off_bomb:
                        continue
                    
                    # Also check if this bomb was recently stepped off (extra safety check)
                    if bomb == player_bomb and bomb.step_off_cooldown > 0:
                        continue
                    
                    # Check if bomb is in target cell or adjacent to player
                    bomb_in_target = (bomb.grid_x == target_grid_x and bomb.grid_y == target_grid_y)
                    bomb_adjacent = False
                    if not bomb_in_target:
                        # Check if bomb is adjacent to current position
                        bomb_dx = abs(bomb.grid_x - current_grid_x)
                        bomb_dy = abs(bomb.grid_y - current_grid_y)
                        bomb_adjacent = (bomb_dx == 1 and bomb_dy == 0) or (bomb_dx == 0 and bomb_dy == 1)
                    
                    if bomb_in_target:
                        # If bomb is in target cell, player is moving into it - allow kick
                        # Always allow kicking when moving into a bomb's cell
                        should_kick = True
                    elif bomb_adjacent:
                        # For adjacent bombs, require can_be_kicked flag and check distance
                        if not bomb.can_be_kicked:
                            should_kick = False
                        else:
                            # Check distance from player to bomb (using pixel positions)
                            # Use the closer of current or target position
                            dx_current = player_x - bomb.pixel_x
                            dy_current = player_y - bomb.pixel_y
                            distance_current = math.sqrt(dx_current * dx_current + dy_current * dy_current)
                            
                            dx_target = new_x - bomb.pixel_x
                            dy_target = new_y - bomb.pixel_y
                            distance_target = math.sqrt(dx_target * dx_target + dy_target * dy_target)
                            
                            min_distance = min(distance_current, distance_target)
                            # Allow kick if player is within reasonable distance (less than 1.5 cell sizes)
                            should_kick = min_distance < CELL_SIZE * 1.5
                    else:
                        should_kick = False
                    
                    if should_kick:
                        # Player is moving into this bomb - kick it away
                        # Determine direction from player to bomb, then kick opposite
                        dx = bomb.grid_x - current_grid_x
                        dy = bomb.grid_y - current_grid_y
                        
                        # Determine kick velocity
                        kick_vel_x = 0.0
                        kick_vel_y = 0.0
                        if dx > 0:  # Bomb is to the right of player, kick right
                            kick_vel_x = BOMB_KICK_SPEED
                            kick_vel_y = 0.0
                        elif dx < 0:  # Bomb is to the left of player, kick left
                            kick_vel_x = -BOMB_KICK_SPEED
                            kick_vel_y = 0.0
                        elif dy > 0:  # Bomb is below player, kick down
                            kick_vel_x = 0.0
                            kick_vel_y = BOMB_KICK_SPEED
                        elif dy < 0:  # Bomb is above player, kick up
                            kick_vel_x = 0.0
                            kick_vel_y = -BOMB_KICK_SPEED
                        
                        # Check if bomb can actually move before setting flag
                        can_move = check_bomb_can_move(bomb, kick_vel_x, kick_vel_y)
                        
                        bomb.velocity_x = kick_vel_x
                        bomb.velocity_y = kick_vel_y
                        bomb.is_moving = True
                        bomb.just_started_moving = can_move  # Only set flag if bomb can actually move
                        break
                    
                    # Also check adjacent cells for bombs when player is moving
                    # But only if player is NOT currently standing on a bomb (to avoid kicking when stepping off)
                    if player_bomb is None and not is_stepping_off_bomb:
                        adjacent_positions = [
                            (current_grid_x, current_grid_y - 1),  # Up
                            (current_grid_x, current_grid_y + 1),  # Down
                            (current_grid_x - 1, current_grid_y),  # Left
                            (current_grid_x + 1, current_grid_y),  # Right
                        ]
                        
                        for adj_x, adj_y in adjacent_positions:
                            for bomb in bombs:
                                if bomb.exploded or bomb.is_moving:
                                    continue
                                # Check if bomb is at this adjacent position
                                if bomb.grid_x != adj_x or bomb.grid_y != adj_y:
                                    continue
                                # Don't kick the bomb we're stepping off from
                                if bomb == bomb_being_stepped_off:
                                    continue
                                # Only allow kicking if player has left this bomb's cell at least once and delay has passed
                                if not bomb.can_be_kicked:
                                    continue
                                
                                # Check distance from player to bomb (using pixel positions)
                                # Use the closer of current or target position
                                dx_current = player_x - bomb.pixel_x
                                dy_current = player_y - bomb.pixel_y
                                distance_current = math.sqrt(dx_current * dx_current + dy_current * dy_current)
                                
                                dx_target = new_x - bomb.pixel_x
                                dy_target = new_y - bomb.pixel_y
                                distance_target = math.sqrt(dx_target * dx_target + dy_target * dy_target)
                                
                                min_distance = min(distance_current, distance_target)
                                # Allow kick if player is within reasonable distance (less than 1.5 cell sizes)
                                if min_distance < CELL_SIZE * 1.5:
                                    # Determine direction from player to bomb, then kick opposite
                                    dx = bomb.grid_x - current_grid_x
                                    dy = bomb.grid_y - current_grid_y
                                    
                                    # Determine kick velocity
                                    kick_vel_x = 0.0
                                    kick_vel_y = 0.0
                                    if dx > 0:  # Bomb is to the right of player, kick right
                                        kick_vel_x = BOMB_KICK_SPEED
                                        kick_vel_y = 0.0
                                    elif dx < 0:  # Bomb is to the left of player, kick left
                                        kick_vel_x = -BOMB_KICK_SPEED
                                        kick_vel_y = 0.0
                                    elif dy > 0:  # Bomb is below player, kick down
                                        kick_vel_x = 0.0
                                        kick_vel_y = BOMB_KICK_SPEED
                                    elif dy < 0:  # Bomb is above player, kick up
                                        kick_vel_x = 0.0
                                        kick_vel_y = -BOMB_KICK_SPEED
                                    
                                    # Check if bomb can actually move before setting flag
                                    can_move = check_bomb_can_move(bomb, kick_vel_x, kick_vel_y)
                                    
                                    bomb.velocity_x = kick_vel_x
                                    bomb.velocity_y = kick_vel_y
                                    bomb.is_moving = True
                                    bomb.just_started_moving = can_move  # Only set flag if bomb can actually move
                                    break
            
            # Check collision separately for X and Y to allow sliding along walls
            # This prevents getting stuck on corners when moving diagonally
            # Player can move through the bomb they're currently on, but not others
            # Try X movement first
            if not check_collision(new_x, player_y, exclude_bomb=player_bomb):
                player_x = new_x
            
            # Try Y movement (using updated player_x)
            # Update player_bomb check after X movement
            new_player_grid_x = int(player_x // CELL_SIZE)
            new_player_grid_y = int(player_y // CELL_SIZE)
            new_player_bomb = None
            for bomb in bombs:
                if bomb.exploded:
                    continue
                # Check if player is on this bomb using pixel collision
                bomb_radius = CELL_SIZE // 2
                dx = player_x - bomb.pixel_x
                dy = player_y - bomb.pixel_y
                distance_squared = dx * dx + dy * dy
                if distance_squared < (PLAYER_RADIUS + bomb_radius) * (PLAYER_RADIUS + bomb_radius):
                    new_player_bomb = bomb
                    break
            
            if not check_collision(player_x, new_y, exclude_bomb=new_player_bomb):
                player_y = new_y
            
            # Check if player's hitbox has fully left any bombs they were previously on
            # This allows bombs to be kicked after the player has left them
            player_left = player_x - PLAYER_RADIUS
            player_right = player_x + PLAYER_RADIUS
            player_top = player_y - PLAYER_RADIUS
            player_bottom = player_y + PLAYER_RADIUS
            
            for bomb in bombs:
                if bomb.exploded:
                    continue
                # Get bomb boundaries (using pixel position)
                bomb_radius = CELL_SIZE // 2
                bomb_left = bomb.pixel_x - bomb_radius
                bomb_right = bomb.pixel_x + bomb_radius
                bomb_top = bomb.pixel_y - bomb_radius
                bomb_bottom = bomb.pixel_y + bomb_radius
                
                # Check if player's hitbox is completely outside the bomb's hitbox
                player_fully_outside = (
                    player_right < bomb_left or  # Player is to the left of bomb
                    player_left > bomb_right or  # Player is to the right of bomb
                    player_bottom < bomb_top or  # Player is above bomb
                    player_top > bomb_bottom     # Player is below bomb
                )
                
                if player_fully_outside:
                    # Mark when player left the bomb (for delay before kicking)
                    if bomb.left_time is None:
                        bomb.left_time = current_time
                    # Only allow kicking after delay has passed AND cooldown is over
                    if current_time - bomb.left_time >= BOMB_KICK_DELAY and bomb.step_off_cooldown == 0:
                        bomb.can_be_kicked = True
                else:
                    # Player is back on the bomb, reset the leave time
                    bomb.left_time = None
                    bomb.can_be_kicked = False
                    # Reset cooldown if player gets back on bomb
                    bomb.step_off_cooldown = 0
            
            # Update bomb step-off cooldowns
            for bomb in bombs:
                if bomb.step_off_cooldown > 0:
                    bomb.step_off_cooldown -= 1
            
            # Update moving bombs (smooth pixel-based movement)
            for bomb in bombs:
                if bomb.is_moving and not bomb.exploded:
                    # Calculate new pixel position
                    new_bomb_x = bomb.pixel_x + bomb.velocity_x
                    new_bomb_y = bomb.pixel_y + bomb.velocity_y
                    
                    # Check collision at new position
                    can_move_x = True
                    can_move_y = True
                    
                    # Get bomb bounding box (bomb is roughly cell-sized)
                    bomb_radius = CELL_SIZE // 2
                    bomb_left = new_bomb_x - bomb_radius
                    bomb_right = new_bomb_x + bomb_radius
                    bomb_top = new_bomb_y - bomb_radius
                    bomb_bottom = new_bomb_y + bomb_radius
                    
                    # Check bounds
                    if bomb_left < 0 or bomb_right >= WINDOW_WIDTH:
                        can_move_x = False
                    if bomb_top < 0 or bomb_bottom >= WINDOW_HEIGHT:
                        can_move_y = False
                    
                    # Check collision with walls (permanent and destructible)
                    grid_left = int(bomb_left // CELL_SIZE)
                    grid_right = int(bomb_right // CELL_SIZE)
                    grid_top = int(bomb_top // CELL_SIZE)
                    grid_bottom = int(bomb_bottom // CELL_SIZE)
                    
                    for grid_x in range(grid_left, grid_right + 1):
                        for grid_y in range(grid_top, grid_bottom + 1):
                            if (grid_x, grid_y) in walls or (grid_x, grid_y) in destructible_walls:
                                # Check if bomb circle overlaps with wall cell
                                wall_left = grid_x * CELL_SIZE
                                wall_right = wall_left + CELL_SIZE
                                wall_top = grid_y * CELL_SIZE
                                wall_bottom = wall_top + CELL_SIZE
                                
                                # Find closest point on wall rectangle to bomb center
                                closest_x = max(wall_left, min(new_bomb_x, wall_right))
                                closest_y = max(wall_top, min(new_bomb_y, wall_bottom))
                                
                                dx = new_bomb_x - closest_x
                                dy = new_bomb_y - closest_y
                                distance_squared = dx * dx + dy * dy
                                
                                if distance_squared < bomb_radius * bomb_radius:
                                    # Collision detected - stop movement in that direction
                                    if abs(bomb.velocity_x) > 0:
                                        can_move_x = False
                                    if abs(bomb.velocity_y) > 0:
                                        can_move_y = False
                    
                    # Check collision with powerups - remove them but don't stop bomb
                    powerups_to_remove = []
                    for grid_x in range(grid_left, grid_right + 1):
                        for grid_y in range(grid_top, grid_bottom + 1):
                            if (grid_x, grid_y) in powerups:
                                wall_left = grid_x * CELL_SIZE
                                wall_right = wall_left + CELL_SIZE
                                wall_top = grid_y * CELL_SIZE
                                wall_bottom = wall_top + CELL_SIZE
                                
                                closest_x = max(wall_left, min(new_bomb_x, wall_right))
                                closest_y = max(wall_top, min(new_bomb_y, wall_bottom))
                                
                                dx = new_bomb_x - closest_x
                                dy = new_bomb_y - closest_y
                                distance_squared = dx * dx + dy * dy
                                
                                if distance_squared < bomb_radius * bomb_radius:
                                    # Remove powerup without animation
                                    powerups_to_remove.append((grid_x, grid_y))
                    
                    # Remove powerups that were hit by the bomb
                    for powerup_pos in powerups_to_remove:
                        powerups.pop(powerup_pos, None)
                    
                    # Check collision with other bombs
                    for other_bomb in bombs:
                        if other_bomb == bomb or other_bomb.exploded:
                            continue
                        
                        other_left = other_bomb.pixel_x - bomb_radius
                        other_right = other_bomb.pixel_x + bomb_radius
                        other_top = other_bomb.pixel_y - bomb_radius
                        other_bottom = other_bomb.pixel_y + bomb_radius
                        
                        # Check if bounding boxes overlap
                        if not (bomb_right < other_left or bomb_left > other_right or 
                                bomb_bottom < other_top or bomb_top > other_bottom):
                            # Check actual circle collision
                            dx = new_bomb_x - other_bomb.pixel_x
                            dy = new_bomb_y - other_bomb.pixel_y
                            distance_squared = dx * dx + dy * dy
                            
                            if distance_squared < (bomb_radius * 2) * (bomb_radius * 2):
                                if abs(bomb.velocity_x) > 0:
                                    can_move_x = False
                                if abs(bomb.velocity_y) > 0:
                                    can_move_y = False
                    
                    # Check collision with player (only if player is not on the bomb)
                    player_grid_x = int(player_x // CELL_SIZE)
                    player_grid_y = int(player_y // CELL_SIZE)
                    bomb_grid_x = int(bomb.pixel_x // CELL_SIZE)
                    bomb_grid_y = int(bomb.pixel_y // CELL_SIZE)
                    player_on_bomb = (player_grid_x == bomb_grid_x and player_grid_y == bomb_grid_y)
                    
                    if not player_on_bomb:
                        # Check circle collision with player
                        dx = new_bomb_x - player_x
                        dy = new_bomb_y - player_y
                        distance_squared = dx * dx + dy * dy
                        
                        if distance_squared < (bomb_radius + PLAYER_RADIUS) * (bomb_radius + PLAYER_RADIUS):
                            if abs(bomb.velocity_x) > 0:
                                can_move_x = False
                            if abs(bomb.velocity_y) > 0:
                                can_move_y = False
                    
                    # Check if bomb can actually move (at least one direction)
                    can_move = can_move_x or can_move_y
                    
                    # Play kick sound only if bomb can actually move and just started moving
                    if bomb.just_started_moving and can_move and kick_sound:
                        kick_sound.play()
                    
                    # Reset the flag after checking
                    bomb.just_started_moving = False
                    
                    # Play kick sound only if bomb can actually move and just started moving
                    if bomb.just_started_moving and can_move and kick_sound:
                        kick_sound.play()
                    
                    # Reset the flag after checking
                    bomb.just_started_moving = False
                    
                    # Apply movement
                    if can_move_x:
                        bomb.pixel_x = new_bomb_x
                    else:
                        bomb.velocity_x = 0.0
                    
                    if can_move_y:
                        bomb.pixel_y = new_bomb_y
                    else:
                        bomb.velocity_y = 0.0
                    
                    # Update grid position based on pixel position
                    bomb.update_grid_pos()
                    
                    # Stop bomb if both velocities are zero
                    if bomb.velocity_x == 0.0 and bomb.velocity_y == 0.0:
                        bomb.is_moving = False
                        # Snap to center of grid cell when stopped
                        bomb.pixel_x = bomb.grid_x * CELL_SIZE + CELL_SIZE // 2
                        bomb.pixel_y = bomb.grid_y * CELL_SIZE + CELL_SIZE // 2
                        
                        # If this was a thrown bomb, restart its timer
                        if bomb.is_thrown:
                            bomb.is_thrown = False
                            # Restart timer completely by resetting placed_time to current time
                            bomb.placed_time = current_time
                            thrown_bomb = None
                            is_throwing = False
        
        # Clear the screen and draw ground tiles
        draw_ground()
        
        # Draw the grid (optional - you can remove this if you don't want grid lines)
        # draw_grid()
        
        # Draw the destructible walls (before permanent walls so they appear on top)
        draw_destructible_walls(current_time)
        
        # Draw the permanent walls
        draw_walls()
        
        # Draw the bombs
        draw_bombs(current_time)
        
        # Draw powerups
        draw_powerups(current_time)
        
        # Draw item explosion animations
        draw_item_explosions(current_time)
        
        # Draw the player
        draw_player(current_time)
        
        # Draw hitboxes if enabled
        if show_hitboxes:
            draw_hitboxes()
        
        # Update the display
        pygame.display.flip()
        
        # Limit to 60 frames per second
        clock.tick(60)
    
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
