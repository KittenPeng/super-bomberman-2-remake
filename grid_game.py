import pygame
import sys
import math
import os
import random

# Helper function to get resource path (works with PyInstaller)
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# Initialize Pygame
pygame.init()

# Initialize mixer for music with more channels for multiple sounds
pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
# Reserve more channels for simultaneous sounds (bounce sounds can overlap)
pygame.mixer.set_num_channels(16)

# Load sound effects
place_bomb_sound = None
bomb_explode_sound = None
item_get_sound = None
kick_voice_sound = None
kick_sound = None
throw_sound = None
bomb_bounce_sound = None
try:
    place_bomb_sound = pygame.mixer.Sound(resource_path("Place Bomb.wav"))
except Exception as e:
    print(f"Warning: Could not load place bomb sound: {e}")

try:
    bomb_explode_sound = pygame.mixer.Sound(resource_path("Bomb Explodes.wav"))
except Exception as e:
    print(f"Warning: Could not load bomb explode sound: {e}")

try:
    item_get_sound = pygame.mixer.Sound(resource_path("Item Get.wav"))
except Exception as e:
    print(f"Warning: Could not load item get sound: {e}")

try:
    kick_voice_sound = pygame.mixer.Sound(resource_path("kick voice.wav"))
except Exception as e:
    print(f"Warning: Could not load kick voice sound: {e}")

try:
    kick_sound_raw = pygame.mixer.Sound(resource_path("kick.wav"))
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
    pause_jingle_sound = pygame.mixer.Sound(resource_path("Pause Jingle.wav"))
    # Set volume to be louder (1.0 is max, but we can go higher if needed)
    pause_jingle_sound.set_volume(1.0)
except Exception as e:
    pause_jingle_sound = None
    print(f"Warning: Could not load pause jingle sound: {e}")

try:
    throw_sound = pygame.mixer.Sound(resource_path("Throw.wav"))
except Exception as e:
    throw_sound = None
    print(f"Warning: Could not load throw sound: {e}")

try:
    bomb_bounce_sound = pygame.mixer.Sound(resource_path("Bomb Bounce.wav"))
except Exception as e:
    bomb_bounce_sound = None
    print(f"Warning: Could not load bomb bounce sound: {e}")

try:
    pressure_block_sound = pygame.mixer.Sound(resource_path("Pressure Block.wav"))
except Exception as e:
    pressure_block_sound = None
    print(f"Warning: Could not load pressure block sound: {e}")

try:
    hurry_up_1_sound = pygame.mixer.Sound(resource_path("Hurry Up 1.wav"))
except Exception as e:
    hurry_up_1_sound = None
    print(f"Warning: Could not load hurry up 1 sound: {e}")

try:
    hurry_up_2_sound = pygame.mixer.Sound(resource_path("Hurry Up 2.wav"))
except Exception as e:
    hurry_up_2_sound = None
    print(f"Warning: Could not load hurry up 2 sound: {e}")

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
pygame.display.set_caption("Grid Movement Game - P1: Arrow Keys + Space | P2: WASD + E")

# Powerups on the ground: {(grid_x, grid_y): powerup_type}
powerups = {}

# Game state variables
show_hitboxes = False  # Toggle to show hitboxes (press 'h' to toggle)
music_muted = False  # Track whether music is muted (press 'm' to toggle)
walk_through_walls = False  # Toggle to allow all players to walk through walls (press 't' to toggle)

# Players will be initialized after sprite loading
player1 = None
player2 = None

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

# Sudden death mechanic
sudden_death_blocks = set()  # Set of (x, y) positions for sudden death blocks
sudden_death_spawn_times = {}  # {(x, y): spawn_time} - tracks when each block was spawned for flash animation
sudden_death_active = False  # Whether sudden death is active
sudden_death_path = []  # List of (x, y) positions in clockwise order
sudden_death_index = 0  # Current index in the path
sudden_death_last_spawn_time = 0  # Time when last block was spawned
sudden_death_hurry_start_time = None  # Time when hurry animation started
sudden_death_hurry_animation_end_time = None  # Time when hurry animation completed (for 2 second delay)
sudden_death_hurry_sound_state = 0  # 0=not started, 1=playing hurry2, 2=waiting delay, 3=playing hurry2 again, 4=done
sudden_death_hurry_sound_start_time = None  # Time when current sound started
SUDDEN_DEATH_SPAWN_INTERVAL = 300  # milliseconds between block spawns (0.3 seconds)
SUDDEN_DEATH_FLASH_DURATION = 100  # milliseconds for each white flash (2 flashes total = 200ms)
HURRY_ANIMATION_DURATION = 3000  # milliseconds for hurry graphic to cross screen (slower movement)
HURRY_FLASH_INTERVAL = 100  # milliseconds between flash states (visible/invisible)
HURRY_SOUND_DELAY = 500  # milliseconds delay between sound sequences
HURRY_POST_ANIMATION_DELAY = 2000  # milliseconds to wait after animation completes before starting blocks
HURRY_POST_ANIMATION_DELAY = 2000  # milliseconds to wait after animation completes before starting blocks

def generate_sudden_death_path():
    """Generate a clockwise path starting from top-left, going around the map twice"""
    path = []
    # Start from top-left corner (1, 1) and go clockwise around the map twice
    
    # Start from outer edge
    min_x, max_x = 1, GRID_WIDTH - 2
    min_y, max_y = 1, GRID_HEIGHT - 2
    
    # Generate path for 2 loops around the map
    # Blocks can spawn over any tile including unbreakable walls
    for loop in range(2):
        # Top edge: left to right
        for x in range(min_x, max_x + 1):
            path.append((x, min_y))
        
        # Right edge: top to bottom (excluding top corner already added)
        for y in range(min_y + 1, max_y + 1):
            path.append((max_x, y))
        
        # Bottom edge: right to left (excluding right corner already added)
        if min_y != max_y:  # Only if not a single row
            for x in range(max_x - 1, min_x - 1, -1):
                path.append((x, max_y))
        
        # Left edge: bottom to top (excluding bottom and top corners already added)
        if min_x != max_x:  # Only if not a single column
            for y in range(max_y - 1, min_y, -1):
                path.append((min_x, y))
        
        # Move inward for second loop
        if loop == 0:
            min_x += 1
            max_x -= 1
            min_y += 1
            max_y -= 1
    
    return path

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
    def __init__(self, grid_x, grid_y, placed_time, placed_by=None):
        self.grid_x = grid_x
        self.grid_y = grid_y
        # Initialize pixel position at center of grid cell
        self.pixel_x = grid_x * CELL_SIZE + CELL_SIZE // 2
        self.pixel_y = grid_y * CELL_SIZE + CELL_SIZE // 2
        self.placed_time = placed_time
        self.placed_by = placed_by  # Track which player placed this bomb (1 or 2)
        self.exploded = False
        self.explosion_start_time = None
        self.explosion_cells = None  # Store explosion cells when bomb explodes
        self.powerup_cells = set()  # Store cells that had powerups when explosion happened
        self.velocity_x = 0.0  # Horizontal velocity for kicking (pixels per frame)
        self.velocity_y = 0.0  # Vertical velocity for kicking (pixels per frame)
        self.is_moving = False  # Whether bomb is currently being kicked
        self.is_thrown = False  # Whether bomb is currently being thrown (timer paused)
        self.throw_start_time = None  # Time when bomb started being thrown (to track paused duration)
        self.throw_target_x = None  # Target X position when thrown (pixels)
        self.throw_target_y = None  # Target Y position when thrown (pixels)
        self.throw_direction_x = 0  # Direction X when thrown (-1, 0, or 1) for wrapping
        self.throw_direction_y = 0  # Direction Y when thrown (-1, 0, or 1) for wrapping
        self.can_be_kicked = False  # Whether player has left this bomb's cell at least once
        self.left_time = None  # Timestamp when player left this bomb's cell
        self.step_off_cooldown = 0  # Frames to wait before allowing kick after player steps off
        self.just_started_moving = False  # Flag to track if bomb just started moving this frame
        self.bounce_offset = 0.0  # Vertical offset for bounce animation (pixels)
        self.bounce_velocity = 0.0  # Vertical velocity for bounce animation
        self.bounce_start_time = None  # Time when bounce animation started
        self.bounced_walls = set()  # Track walls this bomb has already bounced off (grid coordinates)
        self.initial_target_x = None  # Initial 3-tile target X position (pixels)
        self.initial_target_y = None  # Initial 3-tile target Y position (pixels)
        self.reached_initial_target = False  # Whether bomb has reached the initial 3-tile target
        self.just_wrapped_back_offscreen = False  # Flag to track if bomb just wrapped back after being thrown offscreen
        self.wrap_back_time = None  # Time when bomb wrapped back onscreen (to delay bounce detection)
        self.wrap_back_pixel_x = None  # Pixel X position when bomb wrapped back onscreen
        self.wrap_back_pixel_y = None  # Pixel Y position when bomb wrapped back onscreen
    
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

# Player class
class Player:
    def __init__(self, x, y, player_num, sprites):
        self.x = x  # Pixel position
        self.y = y  # Pixel position
        self.player_num = player_num  # 1 or 2
        self.sprites = sprites  # Dictionary of sprites for this player
        self.max_bombs = 1
        self.can_kick = False
        self.has_glove = False
        self.thrown_bomb = None
        self.is_throwing = False
        self.glove_pickup_animation_start_time = None
        self.glove_pickup_animation_direction = None
        self.glove_pickup_bomb = None
        self.direction = 'down'
        self.moving = False
        self.game_over = False
        self.death_time = None
        self.invincible = False
        self.move_speed = 3.0  # Individual movement speed (can be increased by speed powerup)
        self.explosion_range = 2  # Individual explosion range (can be increased by fire powerup)

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

# Load bomb sprites for pulsing animation
# Player 1 bombs: Row 8 (y=128), columns x=0, 16, 32
# Player 2 bombs: Row 8 (y=128), columns x=128, 144, 160 (8 columns further than player 1)
bomb_sprites = []  # List of bomb animation frames for player 1
bomb2_sprites = []  # List of bomb animation frames for player 2
bomb_sprite_loaded = False
bomb2_sprite_loaded = False
BOMB_ANIMATION_SPEED = 200  # milliseconds per frame
try:
    # Suppress libpng warnings about incorrect sRGB profile
    # Redirect stderr temporarily to suppress libpng warnings
    old_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        bomb_sprite_sheet = pygame.image.load(resource_path("SNES - Super Bomberman 2 - Miscellaneous - Bombs.png"))
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr
    bomb_sprite_sheet = bomb_sprite_sheet.convert()
    
    BOMB_SPRITE_SIZE = 16  # Typical SNES sprite size
    bomb_sprite_positions = [0, 16, 32]  # x coordinates for sprites 1, 2, 3
    
    # Load Player 1 bomb sprites from row 8 (y=128, 8 rows down from y=0)
    # 1st sprite: x=0, 2nd sprite: x=16, 3rd sprite: x=32
    BOMB_ROW_Y_P1 = 128  # Row 8: 8 rows down (8 * 16 = 128)
    
    for x_pos in bomb_sprite_positions:
        bomb_sprite = pygame.Surface((BOMB_SPRITE_SIZE, BOMB_SPRITE_SIZE))
        bomb_sprite.blit(bomb_sprite_sheet, (0, 0), (x_pos, BOMB_ROW_Y_P1, BOMB_SPRITE_SIZE, BOMB_SPRITE_SIZE))
        
        # Remove chroma key green background using the helper function
        bomb_sprite = remove_chroma_key(bomb_sprite)
        
        # Scale with alpha preservation
        bomb_sprite = pygame.transform.scale(bomb_sprite, (CELL_SIZE, CELL_SIZE))
        bomb_sprites.append(bomb_sprite)
    
    # Load Player 2 bomb sprites from row 8 (same row as player 1), but 8 columns further
    # 1st sprite: x=128 (column 8), 2nd sprite: x=144 (column 9), 3rd sprite: x=160 (column 10)
    BOMB_ROW_Y_P2 = 128  # Row 8: same as player 1 (8 * 16 = 128)
    bomb2_sprite_positions = [128, 144, 160]  # x coordinates for columns 8, 9, 10 (8 columns further than player 1)
    
    for x_pos in bomb2_sprite_positions:
        bomb_sprite = pygame.Surface((BOMB_SPRITE_SIZE, BOMB_SPRITE_SIZE))
        bomb_sprite.blit(bomb_sprite_sheet, (0, 0), (x_pos, BOMB_ROW_Y_P2, BOMB_SPRITE_SIZE, BOMB_SPRITE_SIZE))
        
        # Remove chroma key green background using the helper function
        bomb_sprite = remove_chroma_key(bomb_sprite)
        
        # Scale with alpha preservation
        bomb_sprite = pygame.transform.scale(bomb_sprite, (CELL_SIZE, CELL_SIZE))
        bomb2_sprites.append(bomb_sprite)
    
    bomb_sprite_loaded = True
    bomb2_sprite_loaded = True
except Exception as e:
    bomb_sprite_loaded = False
    bomb2_sprite_loaded = False
    print(f"Warning: Could not load bomb sprites: {e}. Using default circle.")

# Load player sprites for all directions with walking animations
# Dictionary: 'up', 'right', 'down', 'left' -> list of sprites [idle, walk1, walk2]
player_sprites = {}
player2_sprites = {}
player_sprite_loaded = False
player2_sprite_loaded = False
try:
    # Suppress libpng warnings about incorrect sRGB profile
    old_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        player_sprite_sheet = pygame.image.load(resource_path("SNES - Super Bomberman 2 - Playable Characters - Bomberman.png"))
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr
    player_sprite_sheet = player_sprite_sheet.convert()
    # Player sprites have a 1:2 aspect ratio (width:height), so 16x32 pixels
    # Rows: 1st row (y=0) = up, 2nd row (y=32) = right, 3rd row (y=64) = down, 4th row (y=96) = left
    # Columns: 1st column (x=0) = idle, 2nd column (x=16) = walk frame 1, 3rd column (x=32) = walk frame 2
    PLAYER_SPRITE_WIDTH = 16
    PLAYER_SPRITE_HEIGHT = 32
    
    # Player 1 directions (rows 1-4)
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
    
    # Load Player 1 sprites
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
    
    # Load Player 2 sprites from separate file (player 2.png)
    # Use the same sprite positions as player 1 (rows 1-4)
    try:
        old_stderr = sys.stderr
        sys.stderr = open(os.devnull, 'w')
        try:
            player2_sprite_sheet = pygame.image.load(resource_path("player 2.png"))
        finally:
            sys.stderr.close()
            sys.stderr = old_stderr
        player2_sprite_sheet = player2_sprite_sheet.convert()
        
        # Load Player 2 sprites using same positions as Player 1
        for direction, y_offset in directions.items():
            direction_sprites = []
            for frame_name, x_offset in columns.items():
                sprite = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
                sprite.blit(player2_sprite_sheet, (0, 0), (x_offset, y_offset, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
                
                # Remove chroma key green background using the helper function
                sprite = remove_chroma_key(sprite)
                # Scale player sprite to be 2.5x bigger (maintain 1:2 aspect ratio)
                # 16x32 becomes 40x80
                new_width = int(PLAYER_SPRITE_WIDTH * 2.5)
                new_height = int(PLAYER_SPRITE_HEIGHT * 2.5)
                sprite = pygame.transform.scale(sprite, (new_width, new_height))
                direction_sprites.append(sprite)
            
            player2_sprites[direction] = direction_sprites  # [idle, walk1, walk2]
        
        # Load Player 2 death animation sprites from player2_sprite_sheet using same positions as player 1
        # Player sprites are 16x32 pixels, rows are 32 pixels apart
        # Row 11 (1-indexed) = y = 10 * 32 = 320
        # Row 12 (1-indexed) = y = 11 * 32 = 352
        # Row 5 (1-indexed) = y = 4 * 32 = 128
        # Columns are 16 pixels apart
        # Sprite 1 = x = 0, Sprite 2 = x = 16, Sprite 3 = x = 32, Sprite 4 = x = 48, Sprite 5 = x = 64
        death_sprites2 = []
        DEATH_ROW_11_Y = 10 * 32  # Row 11 (1-indexed) = 320
        DEATH_ROW_12_Y = 11 * 32  # Row 12 (1-indexed) = 352
        DEATH_ROW_5_Y = 4 * 32    # Row 5 (1-indexed) = 128
        
        # Front facing: row 11, sprite 1 (x=0)
        front_sprite2 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        front_sprite2.blit(player2_sprite_sheet, (0, 0), (0, DEATH_ROW_11_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        front_sprite2 = remove_chroma_key(front_sprite2)
        front_sprite2 = pygame.transform.scale(front_sprite2, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
        death_sprites2.append(front_sprite2)
        
        # Right facing: row 11, sprite 2 (x=16)
        right_sprite2 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        right_sprite2.blit(player2_sprite_sheet, (0, 0), (16, DEATH_ROW_11_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        right_sprite2 = remove_chroma_key(right_sprite2)
        right_sprite2 = pygame.transform.scale(right_sprite2, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
        death_sprites2.append(right_sprite2)
        
        # Back facing: row 5, sprite 1 (x=0)
        back_sprite2 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        back_sprite2.blit(player2_sprite_sheet, (0, 0), (0, DEATH_ROW_5_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        back_sprite2 = remove_chroma_key(back_sprite2)
        back_sprite2 = pygame.transform.scale(back_sprite2, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
        death_sprites2.append(back_sprite2)
        
        # Left facing: row 11, sprite 3 (x=32)
        left_sprite2 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        left_sprite2.blit(player2_sprite_sheet, (0, 0), (32, DEATH_ROW_11_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        left_sprite2 = remove_chroma_key(left_sprite2)
        left_sprite2 = pygame.transform.scale(left_sprite2, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
        death_sprites2.append(left_sprite2)
        
        # Additional death animation sprites
        # Row 11, sprite 4 (x=48)
        row11_sprite4_2 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        row11_sprite4_2.blit(player2_sprite_sheet, (0, 0), (48, DEATH_ROW_11_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        row11_sprite4_2 = remove_chroma_key(row11_sprite4_2)
        row11_sprite4_2 = pygame.transform.scale(row11_sprite4_2, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
        death_sprites2.append(row11_sprite4_2)
        
        # Row 12, sprite 1 (x=0)
        row12_sprite1_2 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        row12_sprite1_2.blit(player2_sprite_sheet, (0, 0), (0, DEATH_ROW_12_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        row12_sprite1_2 = remove_chroma_key(row12_sprite1_2)
        row12_sprite1_2 = pygame.transform.scale(row12_sprite1_2, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
        death_sprites2.append(row12_sprite1_2)
        
        # Row 12, sprite 2 (x=16)
        row12_sprite2_2 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        row12_sprite2_2.blit(player2_sprite_sheet, (0, 0), (16, DEATH_ROW_12_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        row12_sprite2_2 = remove_chroma_key(row12_sprite2_2)
        row12_sprite2_2 = pygame.transform.scale(row12_sprite2_2, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
        death_sprites2.append(row12_sprite2_2)
        
        # Row 12, sprite 3 (x=32)
        row12_sprite3_2 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        row12_sprite3_2.blit(player2_sprite_sheet, (0, 0), (32, DEATH_ROW_12_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        row12_sprite3_2 = remove_chroma_key(row12_sprite3_2)
        row12_sprite3_2 = pygame.transform.scale(row12_sprite3_2, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
        death_sprites2.append(row12_sprite3_2)
        
        # Row 12, sprite 4 (x=48)
        row12_sprite4_2 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        row12_sprite4_2.blit(player2_sprite_sheet, (0, 0), (48, DEATH_ROW_12_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        row12_sprite4_2 = remove_chroma_key(row12_sprite4_2)
        row12_sprite4_2 = pygame.transform.scale(row12_sprite4_2, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
        death_sprites2.append(row12_sprite4_2)
        
        # Row 12, sprite 5 (x=64)
        row12_sprite5_2 = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        row12_sprite5_2.blit(player2_sprite_sheet, (0, 0), (64, DEATH_ROW_12_Y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
        row12_sprite5_2 = remove_chroma_key(row12_sprite5_2)
        row12_sprite5_2 = pygame.transform.scale(row12_sprite5_2, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
        death_sprites2.append(row12_sprite5_2)
        
        # Load Player 2 glove pickup animation sprites from player2_sprite_sheet using same positions as player 1
        # Dictionary: 'up', 'right', 'down', 'left' -> list of sprites [sprite1, sprite2, sprite3, sprite4]
        # Sprites: 1 = x=0, 2 = x=16, 3 = x=32, 4 = x=48
        glove_pickup_sprites2 = {}
        
        # Helper function to load sprites from a row for player 2
        def load_glove_row_sprites2(row_y):
            sprites = []
            for sprite_num in range(1, 5):  # Sprites 1-4
                x_offset = (sprite_num - 1) * 16  # x=0, 16, 32, 48
                sprite = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
                sprite.blit(player2_sprite_sheet, (0, 0), (x_offset, row_y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
                sprite = remove_chroma_key(sprite)
                sprite = pygame.transform.scale(sprite, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
                sprites.append(sprite)
            return sprites
        
        # Row 5 (1-indexed) = y = 4 * 32 = 128 (facing up)
        GLOVE_PICKUP_ROW_5_Y = 4 * 32
        glove_pickup_sprites2['up'] = load_glove_row_sprites2(GLOVE_PICKUP_ROW_5_Y)
        
        # Row 6 (1-indexed) = y = 5 * 32 = 160 (facing right)
        GLOVE_PICKUP_ROW_6_Y = 5 * 32
        glove_pickup_sprites2['right'] = load_glove_row_sprites2(GLOVE_PICKUP_ROW_6_Y)
        
        # Row 7 (1-indexed) = y = 6 * 32 = 192 (facing down)
        GLOVE_PICKUP_ROW_7_Y = 6 * 32
        glove_pickup_sprites2['down'] = load_glove_row_sprites2(GLOVE_PICKUP_ROW_7_Y)
        
        # Row 8 (1-indexed) = y = 7 * 32 = 224 (facing left)
        GLOVE_PICKUP_ROW_8_Y = 7 * 32
        glove_pickup_sprites2['left'] = load_glove_row_sprites2(GLOVE_PICKUP_ROW_8_Y)
        
        player2_sprite_loaded = True
        death_sprites2_loaded = True
        glove_pickup_sprites2_loaded = True
    except Exception as e:
        player2_sprite_loaded = False
        death_sprites2_loaded = False
        glove_pickup_sprites2_loaded = False
        print(f"Warning: Could not load player 2 sprite: {e}. Using default circle.")
    
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
    
    # Load glove pickup animation sprites for all directions
    # Dictionary: 'up', 'right', 'down', 'left' -> list of sprites [sprite1, sprite2, sprite3, sprite4]
    # Sprites: 1 = x=0, 2 = x=16, 3 = x=32, 4 = x=48
    glove_pickup_sprites = {}
    
    # Helper function to load sprites from a row
    def load_glove_row_sprites(row_y):
        sprites = []
        for sprite_num in range(1, 5):  # Sprites 1-4
            x_offset = (sprite_num - 1) * 16  # x=0, 16, 32, 48
            sprite = pygame.Surface((PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
            sprite.blit(player_sprite_sheet, (0, 0), (x_offset, row_y, PLAYER_SPRITE_WIDTH, PLAYER_SPRITE_HEIGHT))
            sprite = remove_chroma_key(sprite)
            sprite = pygame.transform.scale(sprite, (int(PLAYER_SPRITE_WIDTH * 2.5), int(PLAYER_SPRITE_HEIGHT * 2.5)))
            sprites.append(sprite)
        return sprites
    
    # Row 5 (1-indexed) = y = 4 * 32 = 128 (facing up)
    GLOVE_PICKUP_ROW_5_Y = 4 * 32
    glove_pickup_sprites['up'] = load_glove_row_sprites(GLOVE_PICKUP_ROW_5_Y)
    
    # Row 6 (1-indexed) = y = 5 * 32 = 160 (facing right)
    GLOVE_PICKUP_ROW_6_Y = 5 * 32
    glove_pickup_sprites['right'] = load_glove_row_sprites(GLOVE_PICKUP_ROW_6_Y)
    
    # Row 7 (1-indexed) = y = 6 * 32 = 192 (facing down)
    GLOVE_PICKUP_ROW_7_Y = 6 * 32
    glove_pickup_sprites['down'] = load_glove_row_sprites(GLOVE_PICKUP_ROW_7_Y)
    
    # Row 8 (1-indexed) = y = 7 * 32 = 224 (facing left)
    GLOVE_PICKUP_ROW_8_Y = 7 * 32
    glove_pickup_sprites['left'] = load_glove_row_sprites(GLOVE_PICKUP_ROW_8_Y)
    
    glove_pickup_sprites_loaded = True
    
except Exception as e:
    player_sprite_loaded = False
    death_sprites = []
    glove_pickup_sprites = {}
    glove_pickup_sprites_loaded = False
    print(f"Warning: Could not load player sprite: {e}. Using default circle.")

# Initialize death_sprites as empty list if not loaded
if 'death_sprites' not in globals():
    death_sprites = []

# Initialize player 2 death and glove pickup sprites
if 'death_sprites2' not in globals():
    death_sprites2 = []
if 'glove_pickup_sprites2' not in globals():
    glove_pickup_sprites2 = {}
if 'death_sprites2_loaded' not in globals():
    death_sprites2_loaded = False
if 'glove_pickup_sprites2_loaded' not in globals():
    glove_pickup_sprites2_loaded = False

# Initialize glove_pickup_sprites as empty dictionary if not loaded
if 'glove_pickup_sprites' not in globals():
    glove_pickup_sprites = {}
    glove_pickup_sprites_loaded = False

# Create player instances after sprite loading
# Player 1 spawns at top-left (1, 1)
player1 = Player(1 * CELL_SIZE + CELL_SIZE // 2, 1 * CELL_SIZE + CELL_SIZE // 2, 1, player_sprites if player_sprite_loaded else {})
# Player 2 spawns at bottom-right (GRID_WIDTH - 2, GRID_HEIGHT - 2)
player2 = Player((GRID_WIDTH - 2) * CELL_SIZE + CELL_SIZE // 2, (GRID_HEIGHT - 2) * CELL_SIZE + CELL_SIZE // 2, 2, player2_sprites if player2_sprite_loaded else {})

# Load pause image
pause_image = None
pause_image_loaded = False
try:
    # Suppress libpng warnings about incorrect sRGB profile
    old_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        pause_image = pygame.image.load(resource_path("pause.png"))
        pause_image = pause_image.convert_alpha()  # Preserve transparency
        pause_image_loaded = True
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr
except Exception as e:
    pause_image_loaded = False
    print(f"Warning: Could not load pause image: {e}")

# Load hurry image
hurry_image = None
hurry_image_loaded = False
try:
    # Suppress libpng warnings about incorrect sRGB profile
    old_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        hurry_image = pygame.image.load(resource_path("hurry.png"))
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr
    hurry_image = hurry_image.convert_alpha()  # Preserve transparency
    # Remove chroma key green background using the helper function
    hurry_image = remove_chroma_key(hurry_image)
    hurry_image_loaded = True
except Exception as e:
    hurry_image_loaded = False
    print(f"Warning: Could not load hurry image: {e}")

# Load explosion sprites from bomb sprite sheet
# Player 1 explosions: rows 14-10 (original positions)
# Player 2 explosions: rows 9-13, columns 9-16
explosion_sprites = {}  # Player 1 explosion sprites
explosion2_sprites = {}  # Player 2 explosion sprites
explosion_sprites_loaded = False
explosion2_sprites_loaded = False

try:
    # Load the bomb sprite sheet (which contains explosions)
    # Suppress libpng warnings about incorrect sRGB profile
    # Redirect stderr temporarily to suppress libpng warnings
    old_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        explosion_sheet = pygame.image.load(resource_path("SNES - Super Bomberman 2 - Miscellaneous - Bombs.png"))
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr
    explosion_sheet = explosion_sheet.convert()
    
    SPRITE_SIZE = 16
    
    # Load Player 1 explosion sprites (original positions)
    # Extract explosion sprites from rows 14 down to row 10
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
    explosion_rows_p1 = [208, 192, 176, 160, 144]  # y coordinates for rows 14, 13, 12, 11, 10
    
    explosion_types_p1 = {
        'center': 96,      # Column 7 - 4-way cross explosion
        'horizontal': 80,  # Column 6 - horizontal segment (left/right)
        'vertical': 64,    # Column 5 - vertical segment (up/down)
        'end_right': 48,  # Column 4 - right end
        'end_left': 32,   # Column 3 - left end
        'end_down': 16,   # Column 2 - bottom end
        'end_up': 0,      # Column 1 - top end
    }
    
    # Load Player 1 sprites for each row
    explosion_sprites = {}  # Will be {row_index: {sprite_type: sprite}}
    for row_idx, row_y in enumerate(explosion_rows_p1):
        explosion_sprites[row_idx] = {}
        for name, sx in explosion_types_p1.items():
            sprite = pygame.Surface((SPRITE_SIZE, SPRITE_SIZE))
            sprite.blit(explosion_sheet, (0, 0), (sx, row_y, SPRITE_SIZE, SPRITE_SIZE))
            sprite = remove_chroma_key(sprite)
            sprite = pygame.transform.scale(sprite, (CELL_SIZE, CELL_SIZE))
            explosion_sprites[row_idx][name] = sprite
    
    # Create 'vertical_down' and 'vertical_up' aliases for backward compatibility
    for row_idx in explosion_sprites:
        explosion_sprites[row_idx]['vertical_down'] = explosion_sprites[row_idx]['vertical']
        explosion_sprites[row_idx]['vertical_up'] = explosion_sprites[row_idx]['vertical']
    
    # Load Player 2 explosion sprites from rows 10-14, columns 9-15
    # Rows 10-14: y = 144, 160, 176, 192, 208 (same rows as player 1)
    # Columns 9-15: x = 128, 144, 160, 176, 192, 208, 224
    # Column 9 (x=128): Top end sprite
    # Column 10 (x=144): Bottom end sprite
    # Column 11 (x=160): Left end sprite
    # Column 12 (x=176): Right end sprite
    # Column 13 (x=192): Vertical segments (up/down arms)
    # Column 14 (x=208): Horizontal segments (left/right arms)
    # Column 15 (x=224): Center explosion - for bomb tile
    
    explosion_rows_p2 = [208, 192, 176, 160, 144]  # y coordinates for rows 14, 13, 12, 11, 10 (same as player 1, animation from row 14 down to row 10)
    
    explosion_types_p2 = {
        'end_up': 128,     # Column 9 - top end sprite
        'end_down': 144,   # Column 10 - bottom end sprite
        'end_left': 160,   # Column 11 - left end sprite
        'end_right': 176,  # Column 12 - right end sprite
        'vertical': 192,   # Column 13 - vertical segment (up/down arms)
        'horizontal': 208, # Column 14 - horizontal segment (left/right arms)
        'center': 224,     # Column 15 - 4-way cross explosion
    }
    
    # Load Player 2 sprites for each row
    explosion2_sprites = {}  # Will be {row_index: {sprite_type: sprite}}
    for row_idx, row_y in enumerate(explosion_rows_p2):
        explosion2_sprites[row_idx] = {}
        for name, sx in explosion_types_p2.items():
            sprite = pygame.Surface((SPRITE_SIZE, SPRITE_SIZE))
            sprite.blit(explosion_sheet, (0, 0), (sx, row_y, SPRITE_SIZE, SPRITE_SIZE))
            sprite = remove_chroma_key(sprite)
            sprite = pygame.transform.scale(sprite, (CELL_SIZE, CELL_SIZE))
            explosion2_sprites[row_idx][name] = sprite
    
    # Create 'vertical_down' and 'vertical_up' aliases for backward compatibility
    for row_idx in explosion2_sprites:
        explosion2_sprites[row_idx]['vertical_down'] = explosion2_sprites[row_idx]['vertical']
        explosion2_sprites[row_idx]['vertical_up'] = explosion2_sprites[row_idx]['vertical']
    
    explosion_sprites_loaded = True
    explosion2_sprites_loaded = True
except Exception as e:
    explosion_sprites_loaded = False
    explosion2_sprites_loaded = False
    print(f"Warning: Could not load explosion sprites: {e}. Using default visualization.")

# Load item explosion animation sprites from Bombs.png sprite sheet
# Column 16, rows 10-14 (5 animation frames)
item_explosion_sprites = []
item_explosion_sprites_loaded = False
try:
    # Use the Bombs sprite sheet
    old_stderr = sys.stderr
    sys.stderr = open(os.devnull, 'w')
    try:
        item_explosion_sheet = pygame.image.load(resource_path("SNES - Super Bomberman 2 - Miscellaneous - Bombs.png"))
    finally:
        sys.stderr.close()
        sys.stderr = old_stderr
    item_explosion_sheet = item_explosion_sheet.convert()
    
    ITEM_EXPLOSION_SPRITE_SIZE = 16
    ITEM_EXPLOSION_COLUMN_X = 240  # Column 16 (x=240, which is 15 * 16)
    # 5 sprites from column 16, rows 10-14 (y=144, 160, 176, 192, 208)
    item_explosion_rows = [144, 160, 176, 192, 208]  # y coordinates for rows 10, 11, 12, 13, 14
    
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
        tileset_sheet = pygame.image.load(resource_path("SNES - Super Bomberman 2 - Tilesets - Battle Game Tiles.png"))
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
    
    # Extract sudden death block sprite (next to ground_wall_above) - at (85, 14)
    # ground_wall_above is at (68, 14), next sprite is at (85, 14) which is 68 + 17
    sudden_death_rect = pygame.Rect(85, 14, BLOCK_SPRITE_SIZE, BLOCK_SPRITE_SIZE)
    sudden_death_tile = tileset_sheet.subsurface(sudden_death_rect).copy()
    sudden_death_tile = sudden_death_tile.convert_alpha()
    if sudden_death_tile.get_width() != BLOCK_SPRITE_SIZE or sudden_death_tile.get_height() != BLOCK_SPRITE_SIZE:
        # Fallback: if sprite doesn't exist at that position, use ground_wall_above
        sudden_death_tile = ground_wall_above_tile.copy()
    else:
        sudden_death_tile = pygame.transform.scale(sudden_death_tile, (CELL_SIZE, CELL_SIZE))
    tileset_sprites['sudden_death'] = sudden_death_tile
    
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
        items_sheet = pygame.image.load(resource_path("SNES - Super Bomberman 2 - Miscellaneous - Items.png"))
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

def draw_hurry_animation(current_time=None):
    """Draw hurry graphic moving from right to left across middle of screen, flashing"""
    if hurry_image_loaded and hurry_image and sudden_death_hurry_start_time is not None and current_time is not None:
        hurry_elapsed = current_time - sudden_death_hurry_start_time
        
        if hurry_elapsed < HURRY_ANIMATION_DURATION:
            # Scale down the hurry image (make it smaller)
            scale_factor = 0.7  # 70% of original size
            scaled_width = int(hurry_image.get_width() * scale_factor)
            scaled_height = int(hurry_image.get_height() * scale_factor)
            scaled_hurry_image = pygame.transform.scale(hurry_image, (scaled_width, scaled_height))
            
            # Calculate position (moving from right to left)
            progress = hurry_elapsed / HURRY_ANIMATION_DURATION
            start_x = WINDOW_WIDTH  # Start off-screen right
            end_x = -scaled_width  # End off-screen left
            current_x = start_x + (end_x - start_x) * progress
            
            # Calculate flash state (visible/invisible)
            flash_phase = int(hurry_elapsed / HURRY_FLASH_INTERVAL) % 2
            is_visible = (flash_phase == 0)
            
            # Draw if visible
            if is_visible:
                # Center vertically in middle of screen
                y_pos = (WINDOW_HEIGHT - scaled_height) // 2
                window.blit(scaled_hurry_image, (current_x, y_pos))

def draw_sudden_death_blocks(current_time=None):
    """Draw sudden death blocks using the sprite next to ground_wall_above, with white flash animation"""
    if tileset_loaded:
        sudden_death_tile = tileset_sprites.get('sudden_death')
        if sudden_death_tile:
            for block_x, block_y in sudden_death_blocks:
                x = block_x * CELL_SIZE
                y = block_y * CELL_SIZE
                
                # Check if this block should flash white (within 200ms of spawn, flashing twice)
                should_flash = False
                if current_time is not None and (block_x, block_y) in sudden_death_spawn_times:
                    spawn_time = sudden_death_spawn_times[(block_x, block_y)]
                    elapsed = current_time - spawn_time
                    if elapsed < SUDDEN_DEATH_FLASH_DURATION * 2:  # Flash for 200ms total (2 flashes of 100ms each)
                        # Flash pattern: white at 0-100ms, normal at 100-200ms
                        flash_phase = int(elapsed / SUDDEN_DEATH_FLASH_DURATION) % 2
                        should_flash = (flash_phase == 0)
                
                if should_flash:
                    # Draw white flash
                    pygame.draw.rect(window, WHITE, (x, y, CELL_SIZE, CELL_SIZE))
                else:
                    # Draw normal sprite
                    window.blit(sudden_death_tile, (x, y))
        else:
            # Fallback to colored rectangles if sprite didn't load
            SUDDEN_DEATH_COLOR = (255, 100, 100)  # Bright red
            SUDDEN_DEATH_BORDER = (200, 50, 50)  # Darker red border
            for block_x, block_y in sudden_death_blocks:
                x = block_x * CELL_SIZE
                y = block_y * CELL_SIZE
                
                # Check if this block should flash white
                should_flash = False
                if current_time is not None and (block_x, block_y) in sudden_death_spawn_times:
                    spawn_time = sudden_death_spawn_times[(block_x, block_y)]
                    elapsed = current_time - spawn_time
                    if elapsed < SUDDEN_DEATH_FLASH_DURATION * 2:
                        flash_phase = int(elapsed / SUDDEN_DEATH_FLASH_DURATION) % 2
                        should_flash = (flash_phase == 0)
                
                if should_flash:
                    pygame.draw.rect(window, WHITE, (x, y, CELL_SIZE, CELL_SIZE))
                else:
                    pygame.draw.rect(window, SUDDEN_DEATH_COLOR, (x, y, CELL_SIZE, CELL_SIZE))
                    pygame.draw.rect(window, SUDDEN_DEATH_BORDER, (x, y, CELL_SIZE, CELL_SIZE), 2)
    else:
        # Fallback to colored rectangles if tileset didn't load
        SUDDEN_DEATH_COLOR = (255, 100, 100)  # Bright red
        SUDDEN_DEATH_BORDER = (200, 50, 50)  # Darker red border
        for block_x, block_y in sudden_death_blocks:
            x = block_x * CELL_SIZE
            y = block_y * CELL_SIZE
            
            # Check if this block should flash white
            should_flash = False
            if current_time is not None and (block_x, block_y) in sudden_death_spawn_times:
                spawn_time = sudden_death_spawn_times[(block_x, block_y)]
                elapsed = current_time - spawn_time
                if elapsed < SUDDEN_DEATH_FLASH_DURATION * 2:
                    flash_phase = int(elapsed / SUDDEN_DEATH_FLASH_DURATION) % 2
                    should_flash = (flash_phase == 0)
            
            if should_flash:
                pygame.draw.rect(window, WHITE, (x, y, CELL_SIZE, CELL_SIZE))
            else:
                pygame.draw.rect(window, SUDDEN_DEATH_COLOR, (x, y, CELL_SIZE, CELL_SIZE))
                pygame.draw.rect(window, SUDDEN_DEATH_BORDER, (x, y, CELL_SIZE, CELL_SIZE), 2)

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
    
    # Get explosion range from the player who placed the bomb
    explosion_range = BOMB_EXPLOSION_RANGE  # Default fallback
    if bomb.placed_by == 1 and player1:
        explosion_range = player1.explosion_range
    elif bomb.placed_by == 2 and player2:
        explosion_range = player2.explosion_range
    
    # Get sprites for the current animation row - use appropriate sprite set based on which player placed the bomb
    bomb_owner = bomb.placed_by if bomb.placed_by else 1  # Default to player 1 if not set
    sprite_set = explosion_sprites if bomb_owner == 1 else (explosion2_sprites if bomb_owner == 2 else explosion_sprites)
    row_sprites = sprite_set.get(animation_row, {})
    
    if dx == 0 and dy == 0:
        # Center of explosion - use center sprite (Column 7)
        sprite = row_sprites.get('center')
        if sprite:
            return sprite.copy(), 'center'
        return None, 'center'
    elif dx == 0:
        # Vertical line (up/down from center)
        if abs(dy) == explosion_range:
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
        if abs(dx) == explosion_range:
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

def get_sprite_for_cell_from_pattern(grid_x, grid_y, all_explosion_cells, bomb_positions, animation_row=0, placed_by=1):
    """Determine which explosion sprite to use for a cell based on the overall explosion pattern
    This fixes issues when multiple bombs overlap - determines sprite based on neighbors, not relative to individual bombs
    placed_by: 1 for player 1, 2 for player 2"""
    # Get sprites for the current animation row - use appropriate sprite set based on player
    sprite_set = explosion_sprites if placed_by == 1 else (explosion2_sprites if placed_by == 2 else explosion_sprites)
    row_sprites = sprite_set.get(animation_row, {})
    
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
    # Track which bomb owns each explosion cell (for sprite selection)
    cell_bomb_owner = {}  # {(grid_x, grid_y): placed_by} - tracks which player's bomb owns each cell
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
            # Collect all explosion cells and track which bomb owns them
            bomb_owner = bomb.placed_by if bomb.placed_by else 1  # Default to player 1 if not set
            for grid_x, grid_y in bomb.explosion_cells:
                all_explosion_cells.add((grid_x, grid_y))
                # Track which bomb owns this cell (use first bomb that claims it, or prefer player 1)
                if (grid_x, grid_y) not in cell_bomb_owner:
                    cell_bomb_owner[(grid_x, grid_y)] = bomb_owner
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
            
            # Determine which player's bomb owns this cell (default to player 1)
            cell_owner = cell_bomb_owner.get((grid_x, grid_y), 1)
            
            # Get sprite based on overall explosion pattern, using the correct sprite set
            sprite, sprite_type = get_sprite_for_cell_from_pattern(grid_x, grid_y, all_explosion_cells, bomb_positions, animation_row, cell_owner)
            
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
                    # Get explosion range from the player who placed the bomb
                    max_distance = BOMB_EXPLOSION_RANGE  # Default fallback
                    if bomb.placed_by == 1 and player1:
                        max_distance = player1.explosion_range
                    elif bomb.placed_by == 2 and player2:
                        max_distance = player2.explosion_range
                    
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
    # Skip drawing bombs that are being picked up (they're drawn in draw_player function)
    # Skip drawing thrown bombs (they're drawn separately after powerups)
    for bomb in bombs:
        if not bomb.exploded:
            # Skip drawing if bomb is being held (thrown and not moving)
            if bomb.is_thrown and not bomb.is_moving:
                continue
            # Skip drawing if bomb is being picked up (drawn in draw_player function)
            if (player1 and bomb == player1.glove_pickup_bomb) or (player2 and bomb == player2.glove_pickup_bomb):
                continue
            # Skip drawing thrown bombs (they're drawn separately after powerups)
            if bomb.is_thrown:
                continue
                
            # Use grid position for non-thrown bombs
            x, y = bomb.get_pixel_pos()
            
            # Apply bounce offset for visual bounce animation
            bounce_offset = bomb.bounce_offset if hasattr(bomb, 'bounce_offset') else 0.0
            draw_y = y - bounce_offset  # Subtract offset so bomb bounces upward
            
            # Normal drawing for non-thrown bombs
            # Choose sprite list based on which player placed the bomb
            # NOTE: Animation pattern, timing, and rendering logic are IDENTICAL for both players
            # Only the sprite source differs (bomb_sprites vs bomb2_sprites)
            sprite_list = bomb_sprites if bomb.placed_by == 1 else (bomb2_sprites if bomb.placed_by == 2 else bomb_sprites)
            sprite_loaded = bomb_sprite_loaded if bomb.placed_by == 1 else (bomb2_sprite_loaded if bomb.placed_by == 2 else bomb_sprite_loaded)
            
            if sprite_loaded and len(sprite_list) >= 3:
                # Calculate animation frame based on time elapsed since bomb was placed
                # Same calculation for both players
                time_since_placed = current_time - bomb.placed_time
                frame_count = time_since_placed // BOMB_ANIMATION_SPEED
                
                # Animation sequence: 0 -> 1 -> 2 -> 1 -> 0 -> 1 -> 2 -> 1 -> 0 -> ...
                # Pattern: [0, 1, 2, 1, 0] repeating - IDENTICAL for both players
                animation_pattern = [0, 1, 2, 1, 0]
                frame_index = animation_pattern[frame_count % len(animation_pattern)]
                
                bomb_sprite = sprite_list[frame_index]
                # Draw bomb sprite centered on bomb position with bounce offset
                sprite_rect = bomb_sprite.get_rect(center=(int(x), int(draw_y)))
                window.blit(bomb_sprite, sprite_rect)
            else:
                # Fallback to circle if sprite didn't load
                # Use different colors for different players
                if bomb.placed_by == 2:
                    pygame.draw.circle(window, BLUE, (int(x), int(draw_y)), CELL_SIZE // 3)
                    pygame.draw.circle(window, BLACK, (int(x), int(draw_y)), CELL_SIZE // 6)
                else:
                    pygame.draw.circle(window, ORANGE, (int(x), int(draw_y)), CELL_SIZE // 3)
                    pygame.draw.circle(window, BLACK, (int(x), int(draw_y)), CELL_SIZE // 6)

def draw_thrown_bombs(current_time):
    """Draw thrown bombs (called after powerups so they appear in front)"""
    for bomb in bombs:
        if not bomb.exploded and bomb.is_thrown and bomb.is_moving:
            # Skip drawing if bomb is being picked up (drawn in draw_player function)
            if (player1 and bomb == player1.glove_pickup_bomb) or (player2 and bomb == player2.glove_pickup_bomb):
                continue
                
            # Use actual pixel position for thrown bombs to show wrapping correctly
            x = bomb.pixel_x
            y = bomb.pixel_y
            
            # Apply bounce offset for visual bounce animation
            bounce_offset = bomb.bounce_offset if hasattr(bomb, 'bounce_offset') else 0.0
            draw_y = y - bounce_offset  # Subtract offset so bomb bounces upward
            
            # Draw bomb at current position and wrapped positions when offscreen (Pac-Man style)
            draw_positions = set()  # Use set to avoid duplicates
            bomb_radius = CELL_SIZE // 2
            
            # Check if bomb is wrapping on X or Y axis
            x_wrapping = (x < 0 or x > WINDOW_WIDTH)
            y_wrapping = (draw_y < 0 or draw_y > WINDOW_HEIGHT)
            
            # Check if bomb just wrapped back onscreen (for wraparound animation)
            # Show wraparound animation as long as the flag is active, regardless of distance or bouncing
            just_wrapped_back_draw = False
            if hasattr(bomb, 'just_wrapped_back_offscreen') and bomb.just_wrapped_back_offscreen:
                # Always show wraparound animation when flag is active
                # Check distance traveled since wrapping back to determine if animation should continue
                if hasattr(bomb, 'wrap_back_pixel_x') and bomb.wrap_back_pixel_x is not None:
                    # Calculate actual distance traveled (accounting for wrapping)
                    dx_wrap = x - bomb.wrap_back_pixel_x
                    dy_wrap = draw_y - bomb.wrap_back_pixel_y
                    # Account for wrapping in distance calculation
                    if abs(dx_wrap) > WINDOW_WIDTH / 2:
                        if dx_wrap > 0:
                            dx_wrap = dx_wrap - WINDOW_WIDTH
                        else:
                            dx_wrap = dx_wrap + WINDOW_WIDTH
                    if abs(dy_wrap) > WINDOW_HEIGHT / 2:
                        if dy_wrap > 0:
                            dy_wrap = dy_wrap - WINDOW_HEIGHT
                        else:
                            dy_wrap = dy_wrap + WINDOW_HEIGHT
                    distance_from_wrap_edge = math.sqrt(dx_wrap**2 + dy_wrap**2)
                    # Show animation until bomb has traveled at least 3 tiles from wrap edge
                    # This ensures wraparound is visible even when target is far away or when bouncing
                    if distance_from_wrap_edge < CELL_SIZE * 3:
                        just_wrapped_back_draw = True
                elif hasattr(bomb, 'wrap_back_pixel_y') and bomb.wrap_back_pixel_y is not None:
                    # Calculate actual distance traveled (accounting for wrapping)
                    dx_wrap = x - bomb.wrap_back_pixel_x if hasattr(bomb, 'wrap_back_pixel_x') and bomb.wrap_back_pixel_x is not None else 0
                    dy_wrap = draw_y - bomb.wrap_back_pixel_y
                    # Account for wrapping in distance calculation
                    if abs(dx_wrap) > WINDOW_WIDTH / 2:
                        if dx_wrap > 0:
                            dx_wrap = dx_wrap - WINDOW_WIDTH
                        else:
                            dx_wrap = dx_wrap + WINDOW_WIDTH
                    if abs(dy_wrap) > WINDOW_HEIGHT / 2:
                        if dy_wrap > 0:
                            dy_wrap = dy_wrap - WINDOW_HEIGHT
                        else:
                            dy_wrap = dy_wrap + WINDOW_HEIGHT
                    distance_from_wrap_edge = math.sqrt(dx_wrap**2 + dy_wrap**2)
                    # Show animation until bomb has traveled at least 3 tiles from wrap edge
                    if distance_from_wrap_edge < CELL_SIZE * 3:
                        just_wrapped_back_draw = True
                else:
                    # If wrap position not set, show animation anyway if flag is active
                    just_wrapped_back_draw = True
            
            # Calculate wrapped positions
            if x < 0:
                wrapped_x = x + WINDOW_WIDTH
            elif x > WINDOW_WIDTH:
                wrapped_x = x - WINDOW_WIDTH
            else:
                wrapped_x = x
            
            if draw_y < 0:
                wrapped_y = draw_y + WINDOW_HEIGHT
            elif draw_y > WINDOW_HEIGHT:
                wrapped_y = draw_y - WINDOW_HEIGHT
            else:
                wrapped_y = draw_y
            
            # Pac-Man style: Show bomb at both edges when wrapping
            # Always add current position (will be clipped if offscreen)
            draw_positions.add((x, draw_y))
            
            # Add wrapped positions when wrapping OR when bomb just wrapped back onscreen (for animation)
            # This ensures wraparound animation is visible even when bomb is onscreen but recently wrapped
            if x_wrapping or just_wrapped_back_draw:
                # Show wrapped X position with current Y
                # If bomb just wrapped back, calculate wrapped position based on throw direction
                if just_wrapped_back_draw and not x_wrapping:
                    # Bomb wrapped back and is now onscreen - show at opposite edge for wraparound effect
                    if hasattr(bomb, 'throw_direction_x') and bomb.throw_direction_x != 0:
                        if bomb.throw_direction_x > 0:  # Moving right, show at left edge
                            wrapped_x_draw = x - WINDOW_WIDTH
                        else:  # Moving left, show at right edge
                            wrapped_x_draw = x + WINDOW_WIDTH
                        draw_positions.add((wrapped_x_draw, draw_y))
                else:
                    # Normal wrapping - show wrapped position
                    draw_positions.add((wrapped_x, draw_y))
                
                # If Y is also wrapping, show fully wrapped position
                if y_wrapping:
                    draw_positions.add((wrapped_x, wrapped_y))
            
            if y_wrapping or just_wrapped_back_draw:
                # Show wrapped Y position with current X (if X wasn't already handled)
                if not x_wrapping and not (just_wrapped_back_draw and hasattr(bomb, 'throw_direction_x') and bomb.throw_direction_x != 0):
                    # If bomb just wrapped back vertically, calculate wrapped position
                    if just_wrapped_back_draw and not y_wrapping:
                        if hasattr(bomb, 'throw_direction_y') and bomb.throw_direction_y != 0:
                            if bomb.throw_direction_y > 0:  # Moving down, show at top edge
                                wrapped_y_draw = draw_y - WINDOW_HEIGHT
                            else:  # Moving up, show at bottom edge
                                wrapped_y_draw = draw_y + WINDOW_HEIGHT
                            draw_positions.add((x, wrapped_y_draw))
                    else:
                        draw_positions.add((x, wrapped_y))
                # Fully wrapped position already added above if x_wrapping is True
            
            # Draw at all positions (only positions that are actually visible on screen)
            # Use larger margin to show bomb going offscreen and coming back onscreen (Pac-Man style)
            visibility_margin = CELL_SIZE * 2  # Allow bomb to be visible even when partially offscreen
            for draw_x, draw_y_pos in draw_positions:
                # Only draw if position is actually on the visible screen (with margin for partial visibility)
                if (draw_x >= -visibility_margin and draw_x <= WINDOW_WIDTH + visibility_margin and
                    draw_y_pos >= -visibility_margin and draw_y_pos <= WINDOW_HEIGHT + visibility_margin):
                    # Choose sprite list based on which player placed the bomb
                    # NOTE: Animation pattern, timing, and rendering logic are IDENTICAL for both players
                    # Only the sprite source differs (bomb_sprites vs bomb2_sprites)
                    sprite_list = bomb_sprites if bomb.placed_by == 1 else (bomb2_sprites if bomb.placed_by == 2 else bomb_sprites)
                    sprite_loaded = bomb_sprite_loaded if bomb.placed_by == 1 else (bomb2_sprite_loaded if bomb.placed_by == 2 else bomb_sprite_loaded)
                    
                    if sprite_loaded and len(sprite_list) >= 3:
                        # Calculate animation frame based on time elapsed since bomb was placed
                        # Same calculation for both players
                        time_since_placed = current_time - bomb.placed_time
                        frame_count = time_since_placed // BOMB_ANIMATION_SPEED
                        
                        # Animation sequence: 0 -> 1 -> 2 -> 1 -> 0 -> 1 -> 2 -> 1 -> 0 -> ...
                        # Pattern: [0, 1, 2, 1, 0] repeating - IDENTICAL for both players
                        animation_pattern = [0, 1, 2, 1, 0]
                        frame_index = animation_pattern[frame_count % len(animation_pattern)]
                        
                        bomb_sprite = sprite_list[frame_index]
                        # Draw bomb sprite centered on bomb position with bounce offset
                        sprite_rect = bomb_sprite.get_rect(center=(int(draw_x), int(draw_y_pos)))
                        window.blit(bomb_sprite, sprite_rect)
                    else:
                        # Fallback to circle if sprite didn't load
                        # Use different colors for different players
                        if bomb.placed_by == 2:
                            pygame.draw.circle(window, BLUE, (int(draw_x), int(draw_y_pos)), CELL_SIZE // 3)
                            pygame.draw.circle(window, BLACK, (int(draw_x), int(draw_y_pos)), CELL_SIZE // 6)
                        else:
                            pygame.draw.circle(window, ORANGE, (int(draw_x), int(draw_y_pos)), CELL_SIZE // 3)
                            pygame.draw.circle(window, BLACK, (int(draw_x), int(draw_y_pos)), CELL_SIZE // 6)

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
    
    # Check collision with walls (permanent, destructible, and sudden death)
    grid_left = int(bomb_left // CELL_SIZE)
    grid_right = int(bomb_right // CELL_SIZE)
    grid_top = int(bomb_top // CELL_SIZE)
    grid_bottom = int(bomb_bottom // CELL_SIZE)
    
    for grid_x in range(grid_left, grid_right + 1):
        for grid_y in range(grid_top, grid_bottom + 1):
            if (grid_x, grid_y) in walls or (grid_x, grid_y) in destructible_walls or (grid_x, grid_y) in sudden_death_blocks:
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
    global walk_through_walls
    
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
    
    # Skip wall collision checks if walk_through_walls is enabled
    if walk_through_walls:
        return False
    
    # Check collision with walls (both permanent and destructible)
    # Convert pixel position to grid cells that might overlap
    grid_left = int(left // CELL_SIZE)
    grid_right = int(right // CELL_SIZE)
    grid_top = int(top // CELL_SIZE)
    grid_bottom = int(bottom // CELL_SIZE)
    
    for grid_x in range(grid_left, grid_right + 1):
        for grid_y in range(grid_top, grid_bottom + 1):
            # Check sudden death blocks (unbreakable)
            if (grid_x, grid_y) in sudden_death_blocks:
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
                tolerance = 1.5
                if distance_squared < (PLAYER_RADIUS + tolerance) * (PLAYER_RADIUS + tolerance):
                    return True
            
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
    
    # Get explosion range from the player who placed the bomb
    explosion_range = BOMB_EXPLOSION_RANGE  # Default fallback
    if bomb.placed_by == 1 and player1:
        explosion_range = player1.explosion_range
    elif bomb.placed_by == 2 and player2:
        explosion_range = player2.explosion_range
    
    # Add cells in each direction
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        for i in range(1, explosion_range + 1):
            x = bomb.grid_x + dx * i
            y = bomb.grid_y + dy * i
            
            # Stop if we hit a permanent wall or sudden death block (explosion doesn't go through)
            if (x, y) in walls or (x, y) in sudden_death_blocks:
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
    
    # Get explosion range from the player who placed the bomb (same as get_explosion_cells)
    explosion_range = BOMB_EXPLOSION_RANGE  # Default fallback
    if bomb.placed_by == 1 and player1:
        explosion_range = player1.explosion_range
    elif bomb.placed_by == 2 and player2:
        explosion_range = player2.explosion_range
    
    # Add cells in each direction
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        for i in range(1, explosion_range + 1):
            x = bomb.grid_x + dx * i
            y = bomb.grid_y + dy * i
            
            # Stop if we hit a permanent wall or sudden death block (explosion doesn't go through)
            if (x, y) in walls or (x, y) in sudden_death_blocks:
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
    global bombs, destructible_walls, breaking_blocks, powerups, item_explosions, MOVE_SPEED, BOMB_EXPLOSION_RANGE
    global sudden_death_blocks, sudden_death_spawn_times, sudden_death_active, sudden_death_path, sudden_death_index
    global sudden_death_hurry_start_time, sudden_death_hurry_animation_end_time, sudden_death_hurry_sound_state, sudden_death_hurry_sound_start_time
    
    # Reset player positions to spawn
    if player1:
        player1.x = 1 * CELL_SIZE + CELL_SIZE // 2
        player1.y = 1 * CELL_SIZE + CELL_SIZE // 2
        player1.max_bombs = 1
        player1.can_kick = False
        player1.has_glove = False
        player1.thrown_bomb = None
        player1.is_throwing = False
        player1.glove_pickup_animation_start_time = None
        player1.glove_pickup_animation_direction = None
        player1.glove_pickup_bomb = None
        player1.direction = 'down'
        player1.moving = False
        player1.game_over = False
        player1.death_time = None
    
    if player2:
        player2.x = (GRID_WIDTH - 2) * CELL_SIZE + CELL_SIZE // 2
        player2.y = (GRID_HEIGHT - 2) * CELL_SIZE + CELL_SIZE // 2
        player2.max_bombs = 1
        player2.can_kick = False
        player2.has_glove = False
        player2.thrown_bomb = None
        player2.is_throwing = False
        player2.glove_pickup_animation_start_time = None
        player2.glove_pickup_animation_direction = None
        player2.glove_pickup_bomb = None
        player2.direction = 'down'
        player2.moving = False
        player2.game_over = False
        player2.death_time = None
    
    # Clear all bombs
    bombs = []
    
    # Clear breaking blocks
    breaking_blocks = {}
    
    # Clear powerups
    powerups = {}
    
    # Clear item explosions
    item_explosions = {}
    
    # Reset movement speed to default
    MOVE_SPEED = 3.0
    
    # Reset explosion range to default
    BOMB_EXPLOSION_RANGE = 2
    
    # Regenerate destructible walls with random removal
    destructible_walls = generate_destructible_walls()
    
    # Clear sudden death blocks
    sudden_death_blocks.clear()
    sudden_death_spawn_times.clear()
    sudden_death_active = False
    sudden_death_path = []
    sudden_death_index = 0
    sudden_death_hurry_start_time = None
    sudden_death_hurry_animation_end_time = None
    sudden_death_hurry_sound_state = 0
    sudden_death_hurry_sound_start_time = None

def explode_bomb(bomb, current_time, check_player_death=True):
    """Handle bomb explosion - destroy destructible walls in range and trigger chain explosions"""
    global powerups, item_explosions
    
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
        
        # Check if players are caught in explosion (for both timer and chain explosions)
        if check_player_death:
            if player1 and not player1.game_over:
                if check_player_in_explosion(player1.x, player1.y, bomb.explosion_cells):
                    if not player1.invincible:
                        player1.game_over = True
                        player1.death_time = current_time
            if player2 and not player2.game_over:
                if check_player_in_explosion(player2.x, player2.y, bomb.explosion_cells):
                    if not player2.invincible:
                        player2.game_over = True
                        player2.death_time = current_time
        
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
    # Draw player hitboxes (circles)
    if player1:
        pygame.draw.circle(window, RED, (int(player1.x), int(player1.y)), PLAYER_RADIUS, 2)
    if player2:
        pygame.draw.circle(window, BLUE, (int(player2.x), int(player2.y)), PLAYER_RADIUS, 2)
    
    # Draw bomb hitboxes (cell-sized rectangles)
    for bomb in bombs:
        if not bomb.exploded:
            # For thrown/bouncing bombs, use pixel position for hitbox
            # For stationary bombs, use grid position
            if bomb.is_thrown and bomb.is_moving:
                # Use pixel position for moving thrown bombs
                bomb_radius = CELL_SIZE // 2
                bomb_x = bomb.pixel_x - bomb_radius
                bomb_y = bomb.pixel_y - bomb_radius
            else:
                # Use grid position for stationary bombs
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

def draw_player(player, current_time=None):
    """Draw the player at their current position with walking animation or death animation"""
    
    # Check if we should show death animation
    # Choose appropriate death sprites based on player number
    player_death_sprites = death_sprites2 if player.player_num == 2 and death_sprites2_loaded else (death_sprites if death_sprites else [])
    if player.game_over and player.death_time is not None and current_time is not None and player_death_sprites:
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
        elapsed = current_time - player.death_time
        
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
            
            # Use death sprites (already selected based on player number)
            sprite = player_death_sprites[sprite_index]
            
            # Draw death sprite
            sprite_width, sprite_height = sprite.get_size()
            offset_below = 4
            sprite_x = int(player.x - sprite_width // 2)
            sprite_y = int((player.y + PLAYER_RADIUS + offset_below) - sprite_height)
            window.blit(sprite, (sprite_x, sprite_y))
            return
    
    # Check if we should show glove pickup animation
    # Animation plays when: player has glove, is standing on bomb
    # Choose appropriate glove pickup sprites based on player number
    player_glove_sprites = glove_pickup_sprites2 if player.player_num == 2 and glove_pickup_sprites2_loaded else (glove_pickup_sprites if glove_pickup_sprites_loaded else {})
    player_glove_sprites_loaded = (player.player_num == 2 and glove_pickup_sprites2_loaded) or (player.player_num == 1 and glove_pickup_sprites_loaded)
    
    if (player.glove_pickup_animation_start_time is not None and player.glove_pickup_animation_direction is not None and 
        current_time is not None and player_glove_sprites_loaded and 
        player.glove_pickup_animation_direction in player_glove_sprites):
        
        # Get sprites for current direction
        direction_sprites = player_glove_sprites[player.glove_pickup_animation_direction]
        
        # Define animation sequences for each direction (sprite indices: 0=sprite1, 1=sprite2, 2=sprite3, 3=sprite4)
        sequences = {
            'up': [2, 3, 2, 1, 0, 2, 3, 2],      # Row 5: 3,4,3,2,1,3,4,3 (8 frames)
            'right': [2, 3, 1, 3, 2],            # Row 6: 3,4,2,4,3 (5 frames)
            'down': [1, 2, 1, 0, 1, 2, 1],       # Row 7: 2,3,2,1,2,3,2 (7 frames)
            'left': [2, 3, 1, 0, 1, 3, 1]       # Row 8: 3,4,2,1,2,4,2 (7 frames)
        }
        
        # Define frame durations for each direction (in milliseconds)
        # Reduced durations for faster pickup animation
        # For 'right': frame 1 (index 1) has +200ms buffer, frame 2 (index 2) has +100ms buffer
        frame_durations = {
            'up': [60] * 8,  # All frames 60ms (faster)
            'right': [60, 180, 120, 60, 60],  # Reduced proportionally: Frame 1: 180ms, Frame 2: 120ms
            'down': [60] * 7,  # All frames 60ms (faster)
            'left': [60] * 7   # All frames 60ms (faster)
        }
        
        sequence = sequences[player.glove_pickup_animation_direction]
        durations = frame_durations[player.glove_pickup_animation_direction]
        GLOVE_PICKUP_ANIMATION_DURATION = sum(durations)  # Total duration
        
        elapsed = current_time - player.glove_pickup_animation_start_time
        
        if elapsed < GLOVE_PICKUP_ANIMATION_DURATION:
            # Determine which frame to show based on cumulative elapsed time
            cumulative_time = 0
            frame_index = 0
            for i, duration in enumerate(durations):
                if elapsed < cumulative_time + duration:
                    frame_index = i
                    break
                cumulative_time += duration
            
            frame_index = min(frame_index, len(sequence) - 1)  # Clamp to valid range
            
            sprite_index = sequence[frame_index]
            sprite = direction_sprites[sprite_index]
            
            # Update bomb position to follow player during animation
            # Make bomb move upward as animation progresses to simulate picking it up
            if player.glove_pickup_bomb is not None:
                # Calculate animation progress (0.0 to 1.0)
                animation_progress = elapsed / GLOVE_PICKUP_ANIMATION_DURATION
                
                # Throw bomb halfway through animation (at 0.5 progress)
                if animation_progress >= 0.5 and not player.glove_pickup_bomb.is_moving:
                    # Initialize variables
                    target_pixel_x = None
                    target_pixel_y = None
                    dx_dir = 0
                    dy_dir = 0
                    
                    # Check if throw target was pre-stored (when throwing bomb not on same tile)
                    throw_start_grid_x = None
                    throw_start_grid_y = None
                    if hasattr(player.glove_pickup_bomb, '_throw_target_x') and hasattr(player.glove_pickup_bomb, '_throw_target_y'):
                        # Use pre-stored throw target
                        target_pixel_x = player.glove_pickup_bomb._throw_target_x
                        target_pixel_y = player.glove_pickup_bomb._throw_target_y
                        dx_dir = player.glove_pickup_bomb._throw_direction_x
                        dy_dir = player.glove_pickup_bomb._throw_direction_y
                        # Store initial throw start position from original position
                        throw_start_grid_x = int(player.glove_pickup_bomb._original_pixel_x // CELL_SIZE)
                        throw_start_grid_y = int(player.glove_pickup_bomb._original_pixel_y // CELL_SIZE)
                        # Use pre-stored initial target if available, otherwise use final target
                        if hasattr(player.glove_pickup_bomb, '_initial_target_x') and hasattr(player.glove_pickup_bomb, '_initial_target_y'):
                            initial_target_x = player.glove_pickup_bomb._initial_target_x
                            initial_target_y = player.glove_pickup_bomb._initial_target_y
                        else:
                            initial_target_x = target_pixel_x
                            initial_target_y = target_pixel_y
                    else:
                        # Calculate throw destination - find first available tile in direction (when standing on bomb)
                        initial_target_x = None
                        initial_target_y = None
                        player_grid_x = int(player.x // CELL_SIZE)
                        player_grid_y = int(player.y // CELL_SIZE)
                        
                        # Determine direction vector
                        if player.glove_pickup_animation_direction == 'up':
                            dx_dir = 0
                            dy_dir = -1
                        elif player.glove_pickup_animation_direction == 'down':
                            dx_dir = 0
                            dy_dir = 1
                        elif player.glove_pickup_animation_direction == 'left':
                            dx_dir = -1
                            dy_dir = 0
                        elif player.glove_pickup_animation_direction == 'right':
                            dx_dir = 1
                            dy_dir = 0
                        else:
                            dx_dir = 0
                            dy_dir = 0
                        
                        # Always throw to exactly 3 tiles for initial arc
                        initial_distance = 3  # Always throw to exactly 3 tiles for initial arc
                        initial_target_grid_x = (player_grid_x + dx_dir * initial_distance) % GRID_WIDTH
                        initial_target_grid_y = (player_grid_y + dy_dir * initial_distance) % GRID_HEIGHT
                        
                        # Set initial target to exactly 3 tiles (for pronounced arc animation)
                        initial_target_x = initial_target_grid_x * CELL_SIZE + CELL_SIZE // 2
                        initial_target_y = initial_target_grid_y * CELL_SIZE + CELL_SIZE // 2
                        
                        # Find final target (first available tile starting from 3 tiles)
                        throw_x = None
                        throw_y = None
                        max_search_distance = GRID_WIDTH + GRID_HEIGHT
                        
                        for distance in range(initial_distance, max_search_distance + 1):
                            check_x = (player_grid_x + dx_dir * distance) % GRID_WIDTH
                            check_y = (player_grid_y + dy_dir * distance) % GRID_HEIGHT
                            
                            # Check if tile has a block (wall, destructible wall, or powerup)
                            has_block = (check_x, check_y) in walls or (check_x, check_y) in destructible_walls or (check_x, check_y) in powerups
                            
                            # Check if tile has another bomb
                            has_bomb = False
                            for other_bomb in bombs:
                                if other_bomb.grid_x == check_x and other_bomb.grid_y == check_y and not other_bomb.exploded:
                                    has_bomb = True
                                    break
                            
                            # If tile is clear, use it as final target
                            if not has_block and not has_bomb:
                                throw_x = check_x
                                throw_y = check_y
                                break
                        
                        if throw_x is not None and throw_y is not None:
                            target_pixel_x = throw_x * CELL_SIZE + CELL_SIZE // 2
                            target_pixel_y = throw_y * CELL_SIZE + CELL_SIZE // 2
                    
                    # If we found a valid tile (or have pre-stored target), throw the bomb
                    if target_pixel_x is not None and target_pixel_y is not None:
                        # Throw the bomb (can be thrown over walls)
                        # Store reference to bomb before clearing it
                        thrown_bomb_ref = player.glove_pickup_bomb
                        player.glove_pickup_bomb.is_thrown = True
                        thrown_bomb_ref.throw_start_time = current_time
                        thrown_bomb_ref.is_moving = True
                        
                        thrown_bomb_ref.throw_target_x = target_pixel_x
                        thrown_bomb_ref.throw_target_y = target_pixel_y
                        thrown_bomb_ref.throw_direction_x = dx_dir  # Store direction for wrapping
                        thrown_bomb_ref.throw_direction_y = dy_dir
                        
                        # Store initial 3-tile target for pronounced arc animation
                        if initial_target_x is not None and initial_target_y is not None:
                            thrown_bomb_ref.initial_target_x = initial_target_x
                            thrown_bomb_ref.initial_target_y = initial_target_y
                            thrown_bomb_ref.reached_initial_target = False
                        else:
                            # If no initial target set, mark as reached immediately (fallback)
                            thrown_bomb_ref.reached_initial_target = True
                        
                        # Store initial throw start position (grid coordinates) for tracking distance
                        if throw_start_grid_x is not None and throw_start_grid_y is not None:
                            # Use pre-stored start position (when throwing from distance)
                            thrown_bomb_ref.throw_start_grid_x = throw_start_grid_x
                            thrown_bomb_ref.throw_start_grid_y = throw_start_grid_y
                        else:
                            # Use current position (when standing on bomb)
                            thrown_bomb_ref.throw_start_grid_x = int(thrown_bomb_ref.pixel_x // CELL_SIZE)
                            thrown_bomb_ref.throw_start_grid_y = int(thrown_bomb_ref.pixel_y // CELL_SIZE)
                        
                        # Calculate direction - use direct path unless it's very long or target is same as start
                        current_x = thrown_bomb_ref.pixel_x
                        current_y = thrown_bomb_ref.pixel_y
                        
                        # Calculate direct path distance
                        dx_direct = target_pixel_x - current_x
                        dy_direct = target_pixel_y - current_y
                        direct_distance = math.sqrt(dx_direct * dx_direct + dy_direct * dy_direct)
                        
                        # Check if target is same as starting position (or very close - within 1 cell)
                        target_is_same_as_start = direct_distance < CELL_SIZE * 1.5
                        
                        # Check if target requires wrapping (is on opposite side of screen)
                        # Wrap only if direct path distance is longer than screen width/height
                        # This means target is actually on opposite side, not just far away on same side
                        screen_center_x = WINDOW_WIDTH / 2
                        screen_center_y = WINDOW_HEIGHT / 2
                        
                        # Check if target is on opposite side of screen center
                        current_on_right = current_x > screen_center_x
                        current_on_bottom = current_y > screen_center_y
                        target_on_right = target_pixel_x > screen_center_x
                        target_on_bottom = target_pixel_y > screen_center_y
                        
                        target_opposite_side_x = (current_on_right != target_on_right)
                        target_opposite_side_y = (current_on_bottom != target_on_bottom)
                        
                        # Check if throw is going offscreen (target is on opposite side)
                        is_thrown_offscreen = (abs(dx_direct) > WINDOW_WIDTH * 0.75 and target_opposite_side_x) or (abs(dy_direct) > WINDOW_HEIGHT * 0.75 and target_opposite_side_y)
                        
                        # Wrap if:
                        # 1. Target is same as start position (force wrap), OR
                        # 2. Throw is going offscreen (target is on opposite side)
                        # This ensures bombs wrap when thrown offscreen but bounce when there are many blocks on same side
                        should_wrap_x = (target_is_same_as_start and abs(dx_direct) < CELL_SIZE and thrown_bomb_ref.throw_direction_x != 0) or (is_thrown_offscreen and abs(dx_direct) > WINDOW_WIDTH * 0.75 and target_opposite_side_x)
                        should_wrap_y = (target_is_same_as_start and abs(dy_direct) < CELL_SIZE and thrown_bomb_ref.throw_direction_y != 0) or (is_thrown_offscreen and abs(dy_direct) > WINDOW_HEIGHT * 0.75 and target_opposite_side_y)
                        
                        THROW_SPEED = 10.0  # Faster throw speed
                        
                        # If wrapping is needed (thrown offscreen), move in throw direction to go offscreen first
                        # Otherwise, bomb should go to initial 3-tile target first (ignoring walls)
                        if should_wrap_x or should_wrap_y:
                            # Move in throw direction - bomb will go offscreen and wrap naturally
                            if thrown_bomb_ref.throw_direction_x != 0:
                                thrown_bomb_ref.velocity_x = thrown_bomb_ref.throw_direction_x * THROW_SPEED
                                thrown_bomb_ref.velocity_y = 0.0
                            elif thrown_bomb_ref.throw_direction_y != 0:
                                thrown_bomb_ref.velocity_x = 0.0
                                thrown_bomb_ref.velocity_y = thrown_bomb_ref.throw_direction_y * THROW_SPEED
                            else:
                                # Fallback - shouldn't happen
                                dx = dx_direct
                                dy = dy_direct
                                distance = math.sqrt(dx * dx + dy * dy)
                                if distance > 0:
                                    thrown_bomb_ref.velocity_x = (dx / distance) * THROW_SPEED
                                    thrown_bomb_ref.velocity_y = (dy / distance) * THROW_SPEED
                        else:
                            # Not thrown offscreen - bomb should ALWAYS go to initial 3-tile target first (ignoring walls)
                            # Calculate direction to initial target (ignoring walls for first 3 tiles)
                            if initial_target_x is not None and initial_target_y is not None:
                                # Use initial 3-tile target - bomb will fly over walls for first 3 tiles
                                dx_initial = initial_target_x - current_x
                                dy_initial = initial_target_y - current_y
                                distance_initial = math.sqrt(dx_initial * dx_initial + dy_initial * dy_initial)
                                if distance_initial > 0:
                                    thrown_bomb_ref.velocity_x = (dx_initial / distance_initial) * THROW_SPEED
                                    thrown_bomb_ref.velocity_y = (dy_initial / distance_initial) * THROW_SPEED
                            else:
                                # Fallback to final target if no initial target (shouldn't happen normally)
                                dx = dx_direct
                                dy = dy_direct
                                distance = math.sqrt(dx * dx + dy * dy)
                                if distance > 0:
                                    thrown_bomb_ref.velocity_x = (dx / distance) * THROW_SPEED
                                    thrown_bomb_ref.velocity_y = (dy / distance) * THROW_SPEED
                        
                        # Initialize wrap tracking for same-target throws
                        if target_is_same_as_start:
                            thrown_bomb_ref._has_wrapped = False
                            thrown_bomb_ref._start_pixel_x = thrown_bomb_ref.pixel_x
                            thrown_bomb_ref._start_pixel_y = thrown_bomb_ref.pixel_y
                        
                        # Start pronounced bounce animation for initial throw arc
                        thrown_bomb_ref.bounce_start_time = current_time
                        thrown_bomb_ref.bounce_velocity = 5.0  # Lower upward velocity for initial arc (positive = upward)
                        thrown_bomb_ref.bounce_offset = 0.0
                        thrown_bomb_ref.bounced_walls = set()  # Initialize bounced walls tracking
                        
                        # Play throw sound effect
                        if throw_sound:
                            throw_sound.play()
                        
                        # Clean up stored throw target attributes
                        if hasattr(player.glove_pickup_bomb, '_throw_target_x'):
                            delattr(player.glove_pickup_bomb, '_throw_target_x')
                        if hasattr(player.glove_pickup_bomb, '_throw_target_y'):
                            delattr(player.glove_pickup_bomb, '_throw_target_y')
                        if hasattr(player.glove_pickup_bomb, '_throw_direction_x'):
                            delattr(player.glove_pickup_bomb, '_throw_direction_x')
                        if hasattr(player.glove_pickup_bomb, '_throw_direction_y'):
                            delattr(player.glove_pickup_bomb, '_throw_direction_y')
                        if hasattr(player.glove_pickup_bomb, '_original_pixel_x'):
                            delattr(player.glove_pickup_bomb, '_original_pixel_x')
                        if hasattr(player.glove_pickup_bomb, '_original_pixel_y'):
                            delattr(player.glove_pickup_bomb, '_original_pixel_y')
                        
                        # Clear the pickup bomb reference since it's now thrown
                        # Animation will continue until completion
                        player.glove_pickup_bomb = None
                
                # Before halfway point, move bomb upward to player's middle
                if player.glove_pickup_bomb is not None:
                    # Check if bomb was thrown from a different tile (has stored original position)
                    if hasattr(player.glove_pickup_bomb, '_original_pixel_x'):
                        # Bomb was thrown from in front - interpolate from original position to player
                        original_x = player.glove_pickup_bomb._original_pixel_x
                        original_y = player.glove_pickup_bomb._original_pixel_y
                        target_x = player.x
                        target_y = player.y
                        
                        # Faster interpolation - accelerate progress to make bomb move faster
                        half_progress = min(animation_progress / 0.5, 1.0)  # Clamp to 1.0 at halfway
                        # Apply speed multiplier for faster movement (1.5x speed)
                        speed_multiplier = 1.5
                        eased_progress = min(half_progress * speed_multiplier, 1.0)
                        bomb_x = original_x + (target_x - original_x) * eased_progress
                        bomb_y = original_y + (target_y - original_y) * eased_progress
                    else:
                        # Bomb was on same tile - move upward to player's middle
                        base_y = player.y + PLAYER_RADIUS  # Ground level
                        target_y = player.y  # Player's middle (center of player)
                        
                        # Faster interpolation - accelerate progress to make bomb move faster
                        half_progress = min(animation_progress / 0.5, 1.0)  # Clamp to 1.0 at halfway
                        # Apply speed multiplier for faster movement (1.5x speed)
                        speed_multiplier = 1.5
                        eased_progress = min(half_progress * speed_multiplier, 1.0)
                        bomb_y = base_y + (target_y - base_y) * eased_progress
                        bomb_x = player.x
                    
                    # Position bomb slightly in front of player based on direction
                    # This makes it appear in front of the character model
                    offset_forward = 8  # Pixels forward from center
                    if player.glove_pickup_animation_direction == 'up':
                        bomb_x = player.x
                        bomb_y_offset = -offset_forward  # Slightly forward (up)
                    elif player.glove_pickup_animation_direction == 'down':
                        bomb_x = player.x
                        bomb_y_offset = offset_forward  # Slightly forward (down)
                    elif player.glove_pickup_animation_direction == 'left':
                        bomb_x = player.x - offset_forward
                        bomb_y_offset = 0
                    elif player.glove_pickup_animation_direction == 'right':
                        bomb_x = player.x + offset_forward
                        bomb_y_offset = 0
                    else:
                        bomb_x = player.x
                        bomb_y_offset = 0
                    
                    # Update bomb position to follow player and move upward
                    player.glove_pickup_bomb.pixel_x = bomb_x
                    player.glove_pickup_bomb.pixel_y = bomb_y + bomb_y_offset
                    player.glove_pickup_bomb.update_grid_pos()
            
            # Draw glove pickup animation sprite (player sprite)
            sprite_width, sprite_height = sprite.get_size()
            offset_below = 4
            sprite_x = int(player.x - sprite_width // 2)
            sprite_y = int((player.y + PLAYER_RADIUS + offset_below) - sprite_height)
            window.blit(sprite, (sprite_x, sprite_y))
            
            # Draw the bomb in front of the player sprite during pickup animation
            if player.glove_pickup_bomb is not None:
                # Choose sprite list based on which player is picking up the bomb
                # NOTE: Animation and rendering logic are IDENTICAL for both players
                # Only the sprite source differs (bomb_sprites vs bomb2_sprites)
                sprite_list = bomb_sprites if player.player_num == 1 else bomb2_sprites
                sprite_loaded = bomb_sprite_loaded if player.player_num == 1 else bomb2_sprite_loaded
                
                if sprite_loaded and len(sprite_list) >= 3:
                    # Use first bomb sprite frame (index 0) during pickup - same for both players
                    bomb_sprite = sprite_list[0]
                    sprite_rect = bomb_sprite.get_rect(center=(int(player.glove_pickup_bomb.pixel_x), int(player.glove_pickup_bomb.pixel_y)))
                    window.blit(bomb_sprite, sprite_rect)
                else:
                    # Fallback to circle
                    # Use different colors for different players
                    if player.player_num == 2:
                        pygame.draw.circle(window, BLUE, (int(player.glove_pickup_bomb.pixel_x), int(player.glove_pickup_bomb.pixel_y)), CELL_SIZE // 3)
                        pygame.draw.circle(window, BLACK, (int(player.glove_pickup_bomb.pixel_x), int(player.glove_pickup_bomb.pixel_y)), CELL_SIZE // 6)
                    else:
                        pygame.draw.circle(window, ORANGE, (int(player.glove_pickup_bomb.pixel_x), int(player.glove_pickup_bomb.pixel_y)), CELL_SIZE // 3)
                        pygame.draw.circle(window, BLACK, (int(player.glove_pickup_bomb.pixel_x), int(player.glove_pickup_bomb.pixel_y)), CELL_SIZE // 6)
            
            return
        else:
            # Animation complete - reset animation state
            if player.glove_pickup_bomb is not None:
                # Bomb should have been thrown, but if it wasn't, clean up
                player.glove_pickup_bomb = None
            
            # Reset animation state now that it's complete
            player.glove_pickup_animation_start_time = None
            player.glove_pickup_animation_direction = None
    
    # Normal player drawing
    player_sprites_dict = player.sprites if player.sprites else {}
    if player_sprites_dict:
        # Get the sprites for the current direction (default to 'down' if not found)
        direction_sprites = player_sprites_dict.get(player.direction, player_sprites_dict.get('down'))
        if direction_sprites:
            # Choose animation frame based on movement
            if player.moving:
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
            # Bottom of hitbox is at player.y + PLAYER_RADIUS
            # Position sprite so its bottom extends slightly below hitbox bottom
            offset_below = 4  # Pixels to extend below hitbox
            sprite_x = int(player.x - sprite_width // 2)  # Center horizontally
            sprite_y = int((player.y + PLAYER_RADIUS + offset_below) - sprite_height)  # Bottom slightly below hitbox
            window.blit(sprite, (sprite_x, sprite_y))
            
    else:
        # Fallback to circle if sprite didn't load
        pygame.draw.circle(window, WHITE, (int(player.x), int(player.y)), int(PLAYER_RADIUS))

def restart_music():
    """Restart the background music"""
    global music_muted
    try:
        pygame.mixer.music.stop()
        pygame.mixer.music.load(resource_path("Super Bomberman 2 - Battle 1 (SNES OST).mp3"))
        # Set volume based on mute state (music is quieter at 0.5 volume)
        if music_muted:
            pygame.mixer.music.set_volume(0.0)
        else:
            pygame.mixer.music.set_volume(0.5)  # Reduced from 1.0 to 0.5 (50% volume)
        pygame.mixer.music.play(-1)  # -1 means loop indefinitely
    except Exception as e:
        print(f"Warning: Could not load music: {e}")

def main():
    global bombs, MOVE_SPEED, BOMB_EXPLOSION_RANGE, show_hitboxes, music_muted, walk_through_walls
    global sudden_death_active, sudden_death_path, sudden_death_index, sudden_death_last_spawn_time, sudden_death_blocks, sudden_death_spawn_times
    global sudden_death_hurry_start_time, sudden_death_hurry_animation_end_time, sudden_death_hurry_sound_state, sudden_death_hurry_sound_start_time
    
    # Debug: Test console output
    print("=" * 50)
    print("GAME STARTED - Debug mode active")
    print(f"Bomb bounce sound loaded: {bomb_bounce_sound is not None}")
    if bomb_bounce_sound:
        print(f"Bomb bounce sound length: {bomb_bounce_sound.get_length()} seconds")
    print("=" * 50)
    
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
                    paused = False
                    pause_start_time = None
                    restart_music()
                elif event.key == pygame.K_i:
                    # Toggle invincibility for player 1 (only when not paused)
                    if not paused and player1:
                        player1.invincible = not player1.invincible
                elif event.key == pygame.K_u:
                    # Toggle invincibility for player 2 (only when not paused)
                    if not paused and player2:
                        player2.invincible = not player2.invincible
                elif event.key == pygame.K_h:
                    # Toggle hitbox display (only when not paused)
                    if not paused:
                        show_hitboxes = not show_hitboxes
                elif event.key == pygame.K_t:
                    # Toggle walk through walls (only when not paused)
                    if not paused:
                        walk_through_walls = not walk_through_walls
                elif event.key == pygame.K_m:
                    # Toggle music mute (works even when paused)
                    music_muted = not music_muted
                    if music_muted:
                        # Mute music
                        pygame.mixer.music.set_volume(0.0)
                    else:
                        # Unmute music (at reduced volume)
                        pygame.mixer.music.set_volume(0.5)  # Reduced from 1.0 to 0.5 (50% volume)
                elif event.key == pygame.K_g:
                    # Give both players glove powerup (debug/cheat)
                    if not paused:
                        if player1 and not player1.has_glove:
                            player1.has_glove = True
                        if player2 and not player2.has_glove:
                            player2.has_glove = True
                        # Play item get sound effect (only once)
                        if item_get_sound and (player1 or player2):
                            item_get_sound.play()
                elif event.key == pygame.K_0:
                    # Start sudden death mechanic
                    if not paused and not sudden_death_active:
                        sudden_death_active = True
                        sudden_death_path = generate_sudden_death_path()
                        sudden_death_index = 0
                        sudden_death_last_spawn_time = current_time
                        sudden_death_blocks.clear()
                        # Start hurry animation
                        sudden_death_hurry_start_time = current_time
                        sudden_death_hurry_animation_end_time = None
                        sudden_death_hurry_sound_state = 0
                        sudden_death_hurry_sound_start_time = None
                elif event.key == pygame.K_SPACE:
                    # Player 1 bomb placement
                    if player1:
                        death_animation_playing = False
                        if player1.game_over and player1.death_time is not None:
                            DEATH_ANIMATION_DURATION = 4600
                            death_animation_playing = (current_time - player1.death_time) < DEATH_ANIMATION_DURATION
                        if not paused and not death_animation_playing:
                            player_grid_x = int(player1.x // CELL_SIZE)
                            player_grid_y = int(player1.y // CELL_SIZE)
                            player_bomb_check = None
                            for bomb in bombs:
                                if bomb.exploded:
                                    continue
                                bomb_radius = CELL_SIZE // 2
                                dx = player1.x - bomb.pixel_x
                                dy = player1.y - bomb.pixel_y
                                distance_squared = dx * dx + dy * dy
                                if distance_squared < (PLAYER_RADIUS + bomb_radius) * (PLAYER_RADIUS + bomb_radius):
                                    player_bomb_check = bomb
                                    break
                            
                            animation_started = False
                            if (player1.has_glove and player_bomb_check is not None and player1.direction in ['up', 'right', 'down', 'left'] and 
                                not player1.is_throwing and player1.glove_pickup_animation_start_time is None):
                                player1.glove_pickup_animation_start_time = current_time
                                player1.glove_pickup_animation_direction = player1.direction
                                player1.glove_pickup_bomb = player_bomb_check
                                animation_started = True
                            
                            if not player1.is_throwing and player1.has_glove and not animation_started:
                                front_x = player_grid_x
                                front_y = player_grid_y
                                if player1.direction == 'up':
                                    front_y -= 1
                                elif player1.direction == 'down':
                                    front_y += 1
                                elif player1.direction == 'left':
                                    front_x -= 1
                                elif player1.direction == 'right':
                                    front_x += 1
                                
                                for bomb in bombs:
                                    if (not bomb.exploded and bomb.grid_x == front_x and bomb.grid_y == front_y and
                                        not bomb.is_thrown and not bomb.is_moving):
                                        if player1.direction == 'up':
                                            dx_dir = 0
                                            dy_dir = -1
                                        elif player1.direction == 'down':
                                            dx_dir = 0
                                            dy_dir = 1
                                        elif player1.direction == 'left':
                                            dx_dir = -1
                                            dy_dir = 0
                                        elif player1.direction == 'right':
                                            dx_dir = 1
                                            dy_dir = 0
                                        else:
                                            dx_dir = 0
                                            dy_dir = 0
                                        
                                        initial_distance = 3
                                        initial_target_grid_x = (player_grid_x + dx_dir * initial_distance) % GRID_WIDTH
                                        initial_target_grid_y = (player_grid_y + dy_dir * initial_distance) % GRID_HEIGHT
                                        
                                        throw_x = None
                                        throw_y = None
                                        max_search_distance = GRID_WIDTH + GRID_HEIGHT
                                        
                                        for distance in range(initial_distance, max_search_distance + 1):
                                            check_x = (player_grid_x + dx_dir * distance) % GRID_WIDTH
                                            check_y = (player_grid_y + dy_dir * distance) % GRID_HEIGHT
                                            
                                            has_block = (check_x, check_y) in walls or (check_x, check_y) in destructible_walls
                                            
                                            has_bomb = False
                                            for other_bomb in bombs:
                                                if other_bomb != bomb and other_bomb.grid_x == check_x and other_bomb.grid_y == check_y and not other_bomb.exploded:
                                                    has_bomb = True
                                                    break
                                            
                                            if not has_block and not has_bomb:
                                                throw_x = check_x
                                                throw_y = check_y
                                                break
                                        
                                        if throw_x is not None and throw_y is not None:
                                            player1.glove_pickup_animation_start_time = current_time
                                            player1.glove_pickup_animation_direction = player1.direction
                                            player1.glove_pickup_bomb = bomb
                                            player1.is_throwing = True
                                            player1.thrown_bomb = bomb
                                            
                                            bomb._throw_target_x = throw_x * CELL_SIZE + CELL_SIZE // 2
                                            bomb._throw_target_y = throw_y * CELL_SIZE + CELL_SIZE // 2
                                            bomb._initial_target_x = initial_target_grid_x * CELL_SIZE + CELL_SIZE // 2
                                            bomb._initial_target_y = initial_target_grid_y * CELL_SIZE + CELL_SIZE // 2
                                            bomb._throw_direction_x = dx_dir
                                            bomb._throw_direction_y = dy_dir
                                            
                                            bomb._original_pixel_x = bomb.pixel_x
                                            bomb._original_pixel_y = bomb.pixel_y
                                            break
                            
                            if not player1.is_throwing:
                                # Count only player 1's active bombs
                                active_bomb_count = 0
                                for bomb in bombs:
                                    if not bomb.exploded and bomb.placed_by == 1:
                                        active_bomb_count += 1
                                
                                if active_bomb_count < player1.max_bombs:
                                    grid_x = int(player1.x // CELL_SIZE)
                                    grid_y = int(player1.y // CELL_SIZE)
                                    
                                    bomb_exists = False
                                    for bomb in bombs:
                                        if bomb.grid_x == grid_x and bomb.grid_y == grid_y and not bomb.exploded:
                                            bomb_exists = True
                                            break
                                    
                                    if not bomb_exists and (grid_x, grid_y) not in walls and (grid_x, grid_y) not in destructible_walls:
                                        new_bomb = Bomb(grid_x, grid_y, current_time, placed_by=1)
                                        bombs.append(new_bomb)
                                        if place_bomb_sound:
                                            place_bomb_sound.play()
                elif event.key == pygame.K_e:
                    # Player 2 bomb placement (same logic as player 1)
                    if player2:
                        death_animation_playing = False
                        if player2.game_over and player2.death_time is not None:
                            DEATH_ANIMATION_DURATION = 4600
                            death_animation_playing = (current_time - player2.death_time) < DEATH_ANIMATION_DURATION
                        if not paused and not death_animation_playing:
                            player_grid_x = int(player2.x // CELL_SIZE)
                            player_grid_y = int(player2.y // CELL_SIZE)
                            player_bomb_check = None
                            for bomb in bombs:
                                if bomb.exploded:
                                    continue
                                bomb_radius = CELL_SIZE // 2
                                dx = player2.x - bomb.pixel_x
                                dy = player2.y - bomb.pixel_y
                                distance_squared = dx * dx + dy * dy
                                if distance_squared < (PLAYER_RADIUS + bomb_radius) * (PLAYER_RADIUS + bomb_radius):
                                    player_bomb_check = bomb
                                    break
                            
                            animation_started = False
                            if (player2.has_glove and player_bomb_check is not None and player2.direction in ['up', 'right', 'down', 'left'] and 
                                not player2.is_throwing and player2.glove_pickup_animation_start_time is None):
                                player2.glove_pickup_animation_start_time = current_time
                                player2.glove_pickup_animation_direction = player2.direction
                                player2.glove_pickup_bomb = player_bomb_check
                                animation_started = True
                            
                            if not player2.is_throwing and player2.has_glove and not animation_started:
                                front_x = player_grid_x
                                front_y = player_grid_y
                                if player2.direction == 'up':
                                    front_y -= 1
                                elif player2.direction == 'down':
                                    front_y += 1
                                elif player2.direction == 'left':
                                    front_x -= 1
                                elif player2.direction == 'right':
                                    front_x += 1
                                
                                for bomb in bombs:
                                    if (not bomb.exploded and bomb.grid_x == front_x and bomb.grid_y == front_y and
                                        not bomb.is_thrown and not bomb.is_moving):
                                        if player2.direction == 'up':
                                            dx_dir = 0
                                            dy_dir = -1
                                        elif player2.direction == 'down':
                                            dx_dir = 0
                                            dy_dir = 1
                                        elif player2.direction == 'left':
                                            dx_dir = -1
                                            dy_dir = 0
                                        elif player2.direction == 'right':
                                            dx_dir = 1
                                            dy_dir = 0
                                        else:
                                            dx_dir = 0
                                            dy_dir = 0
                                        
                                        initial_distance = 3
                                        initial_target_grid_x = (player_grid_x + dx_dir * initial_distance) % GRID_WIDTH
                                        initial_target_grid_y = (player_grid_y + dy_dir * initial_distance) % GRID_HEIGHT
                                        
                                        throw_x = None
                                        throw_y = None
                                        max_search_distance = GRID_WIDTH + GRID_HEIGHT
                                        
                                        for distance in range(initial_distance, max_search_distance + 1):
                                            check_x = (player_grid_x + dx_dir * distance) % GRID_WIDTH
                                            check_y = (player_grid_y + dy_dir * distance) % GRID_HEIGHT
                                            
                                            has_block = (check_x, check_y) in walls or (check_x, check_y) in destructible_walls
                                            
                                            has_bomb = False
                                            for other_bomb in bombs:
                                                if other_bomb != bomb and other_bomb.grid_x == check_x and other_bomb.grid_y == check_y and not other_bomb.exploded:
                                                    has_bomb = True
                                                    break
                                            
                                            if not has_block and not has_bomb:
                                                throw_x = check_x
                                                throw_y = check_y
                                                break
                                        
                                        if throw_x is not None and throw_y is not None:
                                            player2.glove_pickup_animation_start_time = current_time
                                            player2.glove_pickup_animation_direction = player2.direction
                                            player2.glove_pickup_bomb = bomb
                                            player2.is_throwing = True
                                            player2.thrown_bomb = bomb
                                            
                                            bomb._throw_target_x = throw_x * CELL_SIZE + CELL_SIZE // 2
                                            bomb._throw_target_y = throw_y * CELL_SIZE + CELL_SIZE // 2
                                            bomb._initial_target_x = initial_target_grid_x * CELL_SIZE + CELL_SIZE // 2
                                            bomb._initial_target_y = initial_target_grid_y * CELL_SIZE + CELL_SIZE // 2
                                            bomb._throw_direction_x = dx_dir
                                            bomb._throw_direction_y = dy_dir
                                            
                                            bomb._original_pixel_x = bomb.pixel_x
                                            bomb._original_pixel_y = bomb.pixel_y
                                            break
                            
                            if not player2.is_throwing:
                                # Count only player 2's active bombs
                                active_bomb_count = 0
                                for bomb in bombs:
                                    if not bomb.exploded and bomb.placed_by == 2:
                                        active_bomb_count += 1
                                
                                if active_bomb_count < player2.max_bombs:
                                    grid_x = int(player2.x // CELL_SIZE)
                                    grid_y = int(player2.y // CELL_SIZE)
                                    
                                    bomb_exists = False
                                    for bomb in bombs:
                                        if bomb.grid_x == grid_x and bomb.grid_y == grid_y and not bomb.exploded:
                                            bomb_exists = True
                                            break
                                    
                                    if not bomb_exists and (grid_x, grid_y) not in walls and (grid_x, grid_y) not in destructible_walls:
                                        new_bomb = Bomb(grid_x, grid_y, current_time, placed_by=2)
                                        bombs.append(new_bomb)
                                        if place_bomb_sound:
                                            place_bomb_sound.play()
        
        # Update sudden death mechanic - handle hurry animation and sound sequence first
        if sudden_death_active and not paused and sudden_death_hurry_start_time is not None:
            hurry_elapsed = current_time - sudden_death_hurry_start_time
            
            # Handle sound sequence - only play hurry up 2 twice
            if sudden_death_hurry_sound_state == 0:
                # Start playing hurry up 2
                if hurry_up_2_sound:
                    hurry_up_2_sound.play()
                sudden_death_hurry_sound_state = 1
                sudden_death_hurry_sound_start_time = current_time
            elif sudden_death_hurry_sound_state == 1:
                # Wait for first hurry up 2 to finish
                hurry2_length = hurry_up_2_sound.get_length() * 1000 if hurry_up_2_sound else 0  # Convert to milliseconds
                if current_time - sudden_death_hurry_sound_start_time >= hurry2_length:
                    # Wait half a second before playing again
                    sudden_death_hurry_sound_state = 2
                    sudden_death_hurry_sound_start_time = current_time
            elif sudden_death_hurry_sound_state == 2:
                # Wait 500ms delay
                if current_time - sudden_death_hurry_sound_start_time >= HURRY_SOUND_DELAY:
                    # Play hurry up 2 again
                    if hurry_up_2_sound:
                        hurry_up_2_sound.play()
                    sudden_death_hurry_sound_state = 3
                    sudden_death_hurry_sound_start_time = current_time
            elif sudden_death_hurry_sound_state == 3:
                # Wait for second hurry up 2 to finish
                hurry2_length = hurry_up_2_sound.get_length() * 1000 if hurry_up_2_sound else 0  # Convert to milliseconds
                if current_time - sudden_death_hurry_sound_start_time >= hurry2_length:
                    # Sound sequence complete
                    sudden_death_hurry_sound_state = 4
            
            # Check if hurry animation is complete (after animation duration)
            if hurry_elapsed >= HURRY_ANIMATION_DURATION:
                # Mark animation end time if not already set
                if sudden_death_hurry_animation_end_time is None:
                    sudden_death_hurry_animation_end_time = current_time
                # Wait 2 seconds after animation completes before starting blocks
                if current_time - sudden_death_hurry_animation_end_time >= HURRY_POST_ANIMATION_DELAY:
                    # Animation and delay complete, start spawning blocks
                    sudden_death_hurry_start_time = None
                    sudden_death_hurry_animation_end_time = None
        
        # Update sudden death mechanic - spawn blocks one by one (only after hurry animation completes)
        if sudden_death_active and not paused and sudden_death_hurry_start_time is None:
            if sudden_death_index < len(sudden_death_path):
                # Check if enough time has passed since last spawn
                if current_time - sudden_death_last_spawn_time >= SUDDEN_DEATH_SPAWN_INTERVAL:
                    # Get next position from path
                    next_pos = sudden_death_path[sudden_death_index]
                    # Spawn block on any tile, replacing anything in the way
                    
                    # Check if a player is at this position and kill them
                    player1_grid_x = int(player1.x // CELL_SIZE) if player1 else -1
                    player1_grid_y = int(player1.y // CELL_SIZE) if player1 else -1
                    player2_grid_x = int(player2.x // CELL_SIZE) if player2 else -1
                    player2_grid_y = int(player2.y // CELL_SIZE) if player2 else -1
                    
                    if player1 and not player1.game_over:
                        if player1_grid_x == next_pos[0] and player1_grid_y == next_pos[1]:
                            if not player1.invincible:
                                player1.game_over = True
                                player1.death_time = current_time
                    
                    if player2 and not player2.game_over:
                        if player2_grid_x == next_pos[0] and player2_grid_y == next_pos[1]:
                            if not player2.invincible:
                                player2.game_over = True
                                player2.death_time = current_time
                    
                    # Remove any bombs at this position
                    bombs_to_remove = []
                    for bomb in bombs:
                        if bomb.grid_x == next_pos[0] and bomb.grid_y == next_pos[1]:
                            bombs_to_remove.append(bomb)
                    for bomb in bombs_to_remove:
                        bombs.remove(bomb)
                    
                    # Remove any powerups at this position
                    if next_pos in powerups:
                        powerups.pop(next_pos)
                    
                    # Remove from destructible walls if present
                    if next_pos in destructible_walls:
                        destructible_walls.remove(next_pos)
                    
                    # Add sudden death block (can spawn over permanent walls too)
                    sudden_death_blocks.add(next_pos)
                    sudden_death_spawn_times[next_pos] = current_time  # Track spawn time for flash animation
                    sudden_death_last_spawn_time = current_time
                    
                    # Play pressure block sound
                    if pressure_block_sound:
                        pressure_block_sound.play()
                    
                    sudden_death_index += 1
            else:
                # All blocks spawned, sudden death complete
                sudden_death_active = False
        
        # Skip game logic updates when paused (but keep rendering and music)
        if paused:
            # Use frozen time (when we paused) for all animations
            frozen_time = pause_start_time if pause_start_time is not None else current_time
            # Still render the game (frozen state)
            draw_ground()
            draw_destructible_walls(frozen_time)
            draw_walls()
            draw_sudden_death_blocks(frozen_time)
            draw_bombs(frozen_time)
            draw_powerups(frozen_time)
            draw_item_explosions(frozen_time)
            # Draw the players - sort by Y position so higher Y (closer to bottom) is drawn on top
            active_players = []
            if player1:
                active_players.append(player1)
            if player2:
                active_players.append(player2)
            
            # Sort by Y position (lower Y first, higher Y last) so higher Y appears on top
            active_players.sort(key=lambda p: p.y)
            
            for player in active_players:
                draw_player(player, frozen_time)
            
            # Draw hurry animation last so it appears on top of everything (including players)
            draw_hurry_animation(frozen_time)
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
        # Check both players for game over
        any_player_dead = (player1 and player1.game_over) or (player2 and player2.game_over)
        if any_player_dead:
            # Check if death animations are complete
            DEATH_ANIMATION_DURATION = 4600
            p1_dead = player1 and player1.game_over and player1.death_time is not None and (current_time - player1.death_time) < DEATH_ANIMATION_DURATION
            p2_dead = player2 and player2.game_over and player2.death_time is not None and (current_time - player2.death_time) < DEATH_ANIMATION_DURATION
            
            if not p1_dead and not p2_dead:
                # Both death animations complete, reset game
                reset_game()
                if player1:
                    player1.game_over = False
                    player1.death_time = None
                if player2:
                    player2.game_over = False
                    player2.death_time = None
                restart_music()
                continue  # Skip rest of frame after reset
        
        # Only allow movement if not dead and not paused
        # Also skip if death animation is still playing
        p1_death_animation_playing = False
        p2_death_animation_playing = False
        if player1 and player1.game_over and player1.death_time is not None:
            DEATH_ANIMATION_DURATION = 4600
            p1_death_animation_playing = (current_time - player1.death_time) < DEATH_ANIMATION_DURATION
        if player2 and player2.game_over and player2.death_time is not None:
            DEATH_ANIMATION_DURATION = 4600
            p2_death_animation_playing = (current_time - player2.death_time) < DEATH_ANIMATION_DURATION
        
        if not paused:
            # Check for held keys (allows continuous smooth movement)
            keys = pygame.key.get_pressed()
            
            # Process Player 1 movement (Arrow keys + Space)
            if player1 and not p1_death_animation_playing:
                # Find which bomb (if any) player 1 is currently standing on
                player_grid_x = int(player1.x // CELL_SIZE)
                player_grid_y = int(player1.y // CELL_SIZE)
                player_bomb = None
                for bomb in bombs:
                    if bomb.exploded:
                        continue
                    bomb_radius = CELL_SIZE // 2
                    dx = player1.x - bomb.pixel_x
                    dy = player1.y - bomb.pixel_y
                    distance_squared = dx * dx + dy * dy
                    if distance_squared < (PLAYER_RADIUS + bomb_radius) * (PLAYER_RADIUS + bomb_radius):
                        player_bomb = bomb
                        break
                
                # Check if player collected a powerup
                player_pos = (player_grid_x, player_grid_y)
                if player_pos in powerups:
                    powerup_type = powerups[player_pos]
                    if powerup_type == 'bomb_up':
                        player1.max_bombs += 1
                        if item_get_sound:
                            item_get_sound.play()
                    elif powerup_type == 'speed_up':
                        player1.move_speed += 0.75
                        if item_get_sound:
                            item_get_sound.play()
                    elif powerup_type == 'fire_up':
                        player1.explosion_range += 1
                        if item_get_sound:
                            item_get_sound.play()
                    elif powerup_type == 'kick':
                        player1.can_kick = True
                        if kick_voice_sound:
                            kick_voice_sound.play()
                    elif powerup_type == 'glove':
                        player1.has_glove = True
                        if item_get_sound:
                            item_get_sound.play()
                    powerups.pop(player_pos)
                
                # Store old position for corner resolution
                old_x = player1.x
                old_y = player1.y
                
                # Calculate new position based on movement
                new_x = player1.x
                new_y = player1.y
                
                # Move player with arrow keys
                player1.moving = False
                if player1.glove_pickup_animation_start_time is not None:
                    player1.moving = False
                else:
                    if keys[pygame.K_UP]:
                        new_y = player1.y - player1.move_speed
                        player1.direction = 'up'
                        player1.moving = True
                    elif keys[pygame.K_DOWN]:
                        new_y = player1.y + player1.move_speed
                        player1.direction = 'down'
                        player1.moving = True
                    
                    if keys[pygame.K_LEFT]:
                        new_x = player1.x - player1.move_speed
                        player1.direction = 'left'
                        player1.moving = True
                    elif keys[pygame.K_RIGHT]:
                        new_x = player1.x + player1.move_speed
                        player1.direction = 'right'
                        player1.moving = True
            
            # Check for bomb kicking - when player moves into contact with a bomb, kick it away
            # If player has kick ability and is moving, check if they're touching a bomb
            if player1.can_kick and player1.moving:
                # Check the target position the player is moving to
                target_grid_x = int(new_x // CELL_SIZE)
                target_grid_y = int(new_y // CELL_SIZE)
                current_grid_x = int(player1.x // CELL_SIZE)
                current_grid_y = int(player1.y // CELL_SIZE)
                
                # Don't kick if player is moving away from a bomb (stepping off)
                # Check if we're moving AWAY from the bomb we're currently on
                is_stepping_off_bomb = False
                bomb_being_stepped_off = None
                if player_bomb is not None:
                    # Check if we're moving away from the bomb using pixel positions
                    # Calculate distance from bomb before and after movement
                    dx_before = player1.x - player_bomb.pixel_x
                    dy_before = player1.y - player_bomb.pixel_y
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
                            dx_current = player1.x - bomb.pixel_x
                            dy_current = player1.y - bomb.pixel_y
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
                                dx_current = player1.x - bomb.pixel_x
                                dy_current = player1.y - bomb.pixel_y
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
            # Skip movement updates during glove pickup animation
            if player1.glove_pickup_animation_start_time is None:
                # Try X movement first
                if not check_collision(new_x, player1.y, exclude_bomb=player_bomb):
                    player1.x = new_x
                
                # Try Y movement (using updated player1.x)
                # Update player_bomb check after X movement
                new_player_grid_x = int(player1.x // CELL_SIZE)
                new_player_grid_y = int(player1.y // CELL_SIZE)
                new_player_bomb = None
                for bomb in bombs:
                    if bomb.exploded:
                        continue
                    bomb_radius = CELL_SIZE // 2
                    dx = player1.x - bomb.pixel_x
                    dy = player1.y - bomb.pixel_y
                    distance_squared = dx * dx + dy * dy
                    if distance_squared < (PLAYER_RADIUS + bomb_radius) * (PLAYER_RADIUS + bomb_radius):
                        new_player_bomb = bomb
                        break
                
                if not check_collision(player1.x, new_y, exclude_bomb=new_player_bomb):
                    player1.y = new_y
            
            # Check if player's hitbox has fully left any bombs they were previously on
            # This allows bombs to be kicked after the player has left them
            player_left = player1.x - PLAYER_RADIUS
            player_right = player1.x + PLAYER_RADIUS
            player_top = player1.y - PLAYER_RADIUS
            player_bottom = player1.y + PLAYER_RADIUS
            
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
            # Update thrown bomb to follow player if being held
            if player1.is_throwing and player1.thrown_bomb is not None and not player1.thrown_bomb.is_moving:
                # Make bomb follow player position
                player1.thrown_bomb.pixel_x = player1.x
                player1.thrown_bomb.pixel_y = player1.y
                player1.thrown_bomb.update_grid_pos()
            
            # Process Player 2 movement (WASD + E)
            if player2 and not p2_death_animation_playing:
                # Find which bomb (if any) player 2 is currently standing on
                player_grid_x = int(player2.x // CELL_SIZE)
                player_grid_y = int(player2.y // CELL_SIZE)
                player_bomb2 = None
                for bomb in bombs:
                    if bomb.exploded:
                        continue
                    bomb_radius = CELL_SIZE // 2
                    dx = player2.x - bomb.pixel_x
                    dy = player2.y - bomb.pixel_y
                    distance_squared = dx * dx + dy * dy
                    if distance_squared < (PLAYER_RADIUS + bomb_radius) * (PLAYER_RADIUS + bomb_radius):
                        player_bomb2 = bomb
                        break
                
                # Check if player collected a powerup
                player_pos = (player_grid_x, player_grid_y)
                if player_pos in powerups:
                    powerup_type = powerups[player_pos]
                    if powerup_type == 'bomb_up':
                        player2.max_bombs += 1
                        if item_get_sound:
                            item_get_sound.play()
                    elif powerup_type == 'speed_up':
                        player2.move_speed += 0.75
                        if item_get_sound:
                            item_get_sound.play()
                    elif powerup_type == 'fire_up':
                        player2.explosion_range += 1
                        if item_get_sound:
                            item_get_sound.play()
                    elif powerup_type == 'kick':
                        player2.can_kick = True
                        if kick_voice_sound:
                            kick_voice_sound.play()
                    elif powerup_type == 'glove':
                        player2.has_glove = True
                        if item_get_sound:
                            item_get_sound.play()
                    powerups.pop(player_pos)
                
                # Store old position
                old_x2 = player2.x
                old_y2 = player2.y
                
                # Calculate new position
                new_x2 = player2.x
                new_y2 = player2.y
                
                # Move player with WASD keys
                player2.moving = False
                if player2.glove_pickup_animation_start_time is not None:
                    player2.moving = False
                else:
                    if keys[pygame.K_w]:
                        new_y2 = player2.y - player2.move_speed
                        player2.direction = 'up'
                        player2.moving = True
                    elif keys[pygame.K_s]:
                        new_y2 = player2.y + player2.move_speed
                        player2.direction = 'down'
                        player2.moving = True
                    
                    if keys[pygame.K_a]:
                        new_x2 = player2.x - player2.move_speed
                        player2.direction = 'left'
                        player2.moving = True
                    elif keys[pygame.K_d]:
                        new_x2 = player2.x + player2.move_speed
                        player2.direction = 'right'
                        player2.moving = True
                
                # Collision checking for player 2
                if player2.glove_pickup_animation_start_time is None:
                    if not check_collision(new_x2, player2.y, exclude_bomb=player_bomb2):
                        player2.x = new_x2
                    
                    new_player_grid_x2 = int(player2.x // CELL_SIZE)
                    new_player_grid_y2 = int(player2.y // CELL_SIZE)
                    new_player_bomb2 = None
                    for bomb in bombs:
                        if bomb.exploded:
                            continue
                        bomb_radius = CELL_SIZE // 2
                        dx = player2.x - bomb.pixel_x
                        dy = player2.y - bomb.pixel_y
                        distance_squared = dx * dx + dy * dy
                        if distance_squared < (PLAYER_RADIUS + bomb_radius) * (PLAYER_RADIUS + bomb_radius):
                            new_player_bomb2 = bomb
                            break
                    
                    if not check_collision(player2.x, new_y2, exclude_bomb=new_player_bomb2):
                        player2.y = new_y2
                
                # Update thrown bomb for player 2
                if player2.is_throwing and player2.thrown_bomb is not None and not player2.thrown_bomb.is_moving:
                    player2.thrown_bomb.pixel_x = player2.x
                    player2.thrown_bomb.pixel_y = player2.y
                    player2.thrown_bomb.update_grid_pos()
            
            for bomb in bombs:
                if bomb.is_moving and not bomb.exploded:
                    # Calculate new pixel position
                    new_bomb_x = bomb.pixel_x + bomb.velocity_x
                    new_bomb_y = bomb.pixel_y + bomb.velocity_y
                    
                    # Apply wrapping and edge wall bouncing for thrown bombs
                    if bomb.is_thrown:
                        bomb_radius = CELL_SIZE // 2
                        bomb_left = new_bomb_x - bomb_radius
                        bomb_right = new_bomb_x + bomb_radius
                        bomb_top = new_bomb_y - bomb_radius
                        bomb_bottom = new_bomb_y + bomb_radius
                        
                        # Thrown bombs should wrap around screen edges, not bounce off edge walls
                        # Edge wall bouncing is disabled for thrown bombs to allow wrapping
                        
                        # Update bounce animation for thrown bombs
                        if bomb.bounce_start_time is not None:
                            # Calculate bounce animation
                            bounce_elapsed = current_time - bomb.bounce_start_time
                            
                            # Use more pronounced arc for initial throw (before reaching initial target)
                            if hasattr(bomb, 'reached_initial_target') and not bomb.reached_initial_target:
                                GRAVITY = 0.35  # Moderate gravity for lower arc
                                BOUNCE_DAMPING = 0.2  # More damping to keep arc lower
                                MAX_BOUNCE_TIME = 250  # Shorter bounce duration for lower arc
                            else:
                                GRAVITY = 0.3  # Reduced gravity for less bouncy effect
                                BOUNCE_DAMPING = 0.2  # Increased damping for less bouncy effect (lower = more damping)
                                MAX_BOUNCE_TIME = 200  # Reduced bounce duration (ms)
                            
                            if bounce_elapsed < MAX_BOUNCE_TIME:
                                # Apply gravity (making velocity less positive, eventually negative)
                                bomb.bounce_velocity -= GRAVITY
                                bomb.bounce_offset += bomb.bounce_velocity
                                
                                # Bounce off ground (when offset reaches 0 from above)
                                # bounce_offset starts positive (upward), gravity makes it less positive, eventually negative
                                if bomb.bounce_offset <= 0:
                                    bomb.bounce_offset = 0
                                    if bomb.bounce_velocity < 0:
                                        # Reverse and dampen the bounce
                                        bomb.bounce_velocity = -bomb.bounce_velocity * BOUNCE_DAMPING
                                        # Stop bounce if velocity is too small
                                        if abs(bomb.bounce_velocity) < 0.5:
                                            bomb.bounce_velocity = 0
                                            bomb.bounce_offset = 0
                                            bomb.bounce_start_time = None
                            else:
                                # Bounce animation complete
                                bomb.bounce_offset = 0
                                bomb.bounce_velocity = 0
                                bomb.bounce_start_time = None
                        
                        # Don't wrap position immediately - let bomb go offscreen for visual animation
                        # Wrapping will be handled in drawing and collision detection
                        
                        # If bomb has wrapped around (gone offscreen), mark as ready to bounce
                        if (new_bomb_x < 0 or new_bomb_x > WINDOW_WIDTH or 
                            new_bomb_y < 0 or new_bomb_y > WINDOW_HEIGHT):
                            # Bomb has wrapped - mark that it has wrapped and allow bouncing
                            bomb._has_wrapped = True
                            # Also mark as reached initial target so it can bounce
                            if not hasattr(bomb, 'reached_initial_target'):
                                bomb.reached_initial_target = False
                            if not bomb.reached_initial_target:
                                bomb.reached_initial_target = True
                    
                    # Check if thrown bomb has reached its target destination
                    # Use wrapped position for target detection but keep actual position for visual
                    if bomb.is_thrown and bomb.throw_target_x is not None and bomb.throw_target_y is not None:
                        # Track if bomb just wrapped (was offscreen, now onscreen)
                        was_offscreen = (bomb.pixel_x < 0 or bomb.pixel_x > WINDOW_WIDTH or
                                        bomb.pixel_y < 0 or bomb.pixel_y > WINDOW_HEIGHT)
                        is_now_onscreen = (new_bomb_x >= 0 and new_bomb_x <= WINDOW_WIDTH and
                                          new_bomb_y >= 0 and new_bomb_y <= WINDOW_HEIGHT)
                        just_wrapped_back = was_offscreen and is_now_onscreen
                        
                        # If bomb just wrapped back, check if it was thrown offscreen
                        if just_wrapped_back:
                            was_thrown_offscreen_flag = False
                            if hasattr(bomb, 'throw_start_grid_x') and hasattr(bomb, 'throw_start_grid_y'):
                                start_x = bomb.throw_start_grid_x % GRID_WIDTH
                                start_y = bomb.throw_start_grid_y % GRID_HEIGHT
                                start_pixel_x = start_x * CELL_SIZE + CELL_SIZE // 2
                                start_pixel_y = start_y * CELL_SIZE + CELL_SIZE // 2
                                
                                screen_center_x = WINDOW_WIDTH / 2
                                screen_center_y = WINDOW_HEIGHT / 2
                                start_on_right = start_pixel_x > screen_center_x
                                start_on_bottom = start_pixel_y > screen_center_y
                                final_target_on_right = bomb.throw_target_x > screen_center_x
                                final_target_on_bottom = bomb.throw_target_y > screen_center_y
                                
                                target_opposite_x = (start_on_right != final_target_on_right)
                                target_opposite_y = (start_on_bottom != final_target_on_bottom)
                                
                                dx_to_final = bomb.throw_target_x - start_pixel_x
                                dy_to_final = bomb.throw_target_y - start_pixel_y
                                
                                was_thrown_offscreen_flag = ((abs(dx_to_final) > WINDOW_WIDTH * 0.75 and target_opposite_x) or 
                                                              (abs(dy_to_final) > WINDOW_HEIGHT * 0.75 and target_opposite_y))
                            
                            # Set flag to maintain throw direction after wrapping back
                            if was_thrown_offscreen_flag:
                                bomb.just_wrapped_back_offscreen = True
                                bomb.wrap_back_time = current_time  # Record when bomb wrapped back
                        
                        # Calculate wrapped position for target detection
                        wrapped_x = new_bomb_x
                        wrapped_y = new_bomb_y
                        if wrapped_x < 0:
                            wrapped_x = wrapped_x + WINDOW_WIDTH
                        elif wrapped_x >= WINDOW_WIDTH:
                            wrapped_x = wrapped_x - WINDOW_WIDTH
                        if wrapped_y < 0:
                            wrapped_y = wrapped_y + WINDOW_HEIGHT
                        elif wrapped_y >= WINDOW_HEIGHT:
                            wrapped_y = wrapped_y - WINDOW_HEIGHT
                        
                        # Check target using grid position for more reliable detection
                        # If bomb hasn't reached initial target yet, use initial target for checking
                        if hasattr(bomb, 'initial_target_x') and hasattr(bomb, 'initial_target_y') and hasattr(bomb, 'reached_initial_target') and not bomb.reached_initial_target:
                            # Use initial target for grid checking
                            check_target_x = bomb.initial_target_x
                            check_target_y = bomb.initial_target_y
                        else:
                            # Use final target
                            check_target_x = bomb.throw_target_x
                            check_target_y = bomb.throw_target_y
                        
                        target_grid_x = int(check_target_x // CELL_SIZE)
                        target_grid_y = int(check_target_y // CELL_SIZE)
                        current_grid_x = int(wrapped_x // CELL_SIZE)
                        current_grid_y = int(wrapped_y // CELL_SIZE)
                        
                        # Wrap grid coordinates
                        target_grid_x = target_grid_x % GRID_WIDTH
                        target_grid_y = target_grid_y % GRID_HEIGHT
                        current_grid_x = current_grid_x % GRID_WIDTH
                        current_grid_y = current_grid_y % GRID_HEIGHT
                        
                        # If bomb just wrapped back onscreen, only update target if it has reached initial target
                        # Otherwise, let bomb continue to initial 3-tile target first
                        if just_wrapped_back:
                            # Check if bomb has reached initial target first
                            has_reached_initial = (hasattr(bomb, 'reached_initial_target') and bomb.reached_initial_target)
                            
                            # Check if bomb was thrown offscreen - if so, always update target when wrapping back
                            was_thrown_offscreen_wrap = False
                            if hasattr(bomb, 'throw_start_grid_x') and hasattr(bomb, 'throw_start_grid_y'):
                                start_x = bomb.throw_start_grid_x % GRID_WIDTH
                                start_y = bomb.throw_start_grid_y % GRID_HEIGHT
                                start_pixel_x = start_x * CELL_SIZE + CELL_SIZE // 2
                                start_pixel_y = start_y * CELL_SIZE + CELL_SIZE // 2
                                
                                screen_center_x = WINDOW_WIDTH / 2
                                screen_center_y = WINDOW_HEIGHT / 2
                                start_on_right = start_pixel_x > screen_center_x
                                start_on_bottom = start_pixel_y > screen_center_y
                                final_target_on_right = bomb.throw_target_x > screen_center_x
                                final_target_on_bottom = bomb.throw_target_y > screen_center_y
                                
                                target_opposite_x = (start_on_right != final_target_on_right)
                                target_opposite_y = (start_on_bottom != final_target_on_bottom)
                                
                                dx_to_final = bomb.throw_target_x - start_pixel_x
                                dy_to_final = bomb.throw_target_y - start_pixel_y
                                
                                was_thrown_offscreen_wrap = ((abs(dx_to_final) > WINDOW_WIDTH * 0.75 and target_opposite_x) or 
                                                              (abs(dy_to_final) > WINDOW_HEIGHT * 0.75 and target_opposite_y))
                            
                            # Only update target if initial target has been reached OR bomb was thrown offscreen
                            # This ensures bomb goes 3 tiles ahead first (ignoring walls) before checking for available tiles
                            # But if thrown offscreen, always check for available tiles when wrapping back
                            if has_reached_initial or was_thrown_offscreen_wrap:
                                # Check tiles systematically in throw direction, starting from current position
                                # This ensures we check tiles next to edge walls first
                                found_available_tile = False
                                
                                # Check tiles in throw direction, starting from current position
                                # Check up to 6 tiles ahead to catch fast-moving bombs
                                for distance in range(0, 7):  # Start from 0 (current tile) to 6 tiles ahead
                                    check_x = (current_grid_x + bomb.throw_direction_x * distance) % GRID_WIDTH
                                    check_y = (current_grid_y + bomb.throw_direction_y * distance) % GRID_HEIGHT
                                    
                                    # Check if tile is edge wall (x=0, x=GRID_WIDTH-1, etc.)
                                    # Edge walls themselves are skipped, but tiles NEXT TO them are checked
                                    is_check_edge = (check_x == 0 or check_x == GRID_WIDTH - 1 or 
                                                   check_y == 0 or check_y == GRID_HEIGHT - 1)
                                    
                                    # Skip actual edge walls (to allow wrapping), but check tiles next to them
                                    if is_check_edge:
                                        continue
                                    
                                    # Check if tile has block
                                    check_tile_has_block = (check_x, check_y) in walls or (check_x, check_y) in destructible_walls or (check_x, check_y) in powerups
                                    
                                    # Check if tile has bomb
                                    check_tile_has_bomb = False
                                    for other_bomb in bombs:
                                        if other_bomb != bomb and other_bomb.grid_x == check_x and other_bomb.grid_y == check_y and not other_bomb.exploded:
                                            check_tile_has_bomb = True
                                            break
                                    
                                    # If tile is available (not blocked, no bomb), update target immediately
                                    # BUT: Only set target if it's close (within 2 tiles) when just wrapped back
                                    # This prevents bomb from flying across screen before bouncing
                                    if not check_tile_has_block and not check_tile_has_bomb:
                                        # If bomb just wrapped back, only set target if it's nearby (within 2 tiles)
                                        # This ensures bomb bounces off blocks instead of flying to distant targets
                                        should_set_target = True
                                        if just_wrapped_back and was_thrown_offscreen_wrap:
                                            if distance > 2:  # Only allow targets within 2 tiles
                                                should_set_target = False
                                        
                                        if should_set_target:
                                            bomb.throw_target_x = check_x * CELL_SIZE + CELL_SIZE // 2
                                            bomb.throw_target_y = check_y * CELL_SIZE + CELL_SIZE // 2
                                            # Recalculate target grid for consistency
                                            target_grid_x = check_x
                                            target_grid_y = check_y
                                            
                                            # Recalculate velocity toward new target to continue movement
                                            # When thrown offscreen, maintain throw direction to continue wrapping behavior
                                            THROW_SPEED = 10.0
                                            
                                            # If thrown offscreen and just wrapped back, maintain strict direction (don't recalculate based on target position)
                                            # This ensures bomb continues in throw direction after wrapping, not back across screen
                                            # Use the persistent flag to maintain direction even when target is not immediately adjacent
                                            if was_thrown_offscreen_wrap or (hasattr(bomb, 'just_wrapped_back_offscreen') and bomb.just_wrapped_back_offscreen):
                                                # Maintain throw direction - bomb should continue moving in same direction
                                                if bomb.throw_direction_x != 0:
                                                    bomb.velocity_x = bomb.throw_direction_x * THROW_SPEED
                                                    bomb.velocity_y = 0.0
                                                elif bomb.throw_direction_y != 0:
                                                    bomb.velocity_x = 0.0
                                                    bomb.velocity_y = bomb.throw_direction_y * THROW_SPEED
                                            else:
                                                # Not thrown offscreen - calculate direction to target normally
                                                dx_new = bomb.throw_target_x - wrapped_x
                                                dy_new = bomb.throw_target_y - wrapped_y
                                                
                                                # Account for wrapping in direction calculation
                                                if abs(dx_new) > WINDOW_WIDTH / 2:
                                                    if dx_new > 0:
                                                        dx_new = dx_new - WINDOW_WIDTH
                                                    else:
                                                        dx_new = dx_new + WINDOW_WIDTH
                                                if abs(dy_new) > WINDOW_HEIGHT / 2:
                                                    if dy_new > 0:
                                                        dy_new = dy_new - WINDOW_HEIGHT
                                                    else:
                                                        dy_new = dy_new + WINDOW_HEIGHT
                                                
                                                distance_new = math.sqrt(dx_new * dx_new + dy_new * dy_new)
                                                if distance_new > 0:
                                                    bomb.velocity_x = (dx_new / distance_new) * THROW_SPEED
                                                    bomb.velocity_y = (dy_new / distance_new) * THROW_SPEED
                                            
                                            found_available_tile = True
                                            break  # Use first available tile found
                                
                                # If no available tile found in throw direction, also check adjacent tiles
                                # This handles cases where bomb might be slightly off-center
                                if not found_available_tile:
                                    for adj_x in [-1, 0, 1]:
                                        for adj_y in [-1, 0, 1]:
                                            if adj_x == 0 and adj_y == 0:
                                                continue  # Skip current tile (already checked)
                                            check_x = (current_grid_x + adj_x) % GRID_WIDTH
                                            check_y = (current_grid_y + adj_y) % GRID_HEIGHT
                                            
                                            # Skip edge walls
                                            is_check_edge = (check_x == 0 or check_x == GRID_WIDTH - 1 or 
                                                           check_y == 0 or check_y == GRID_HEIGHT - 1)
                                            if is_check_edge:
                                                continue
                                            
                                            # Check if tile is available
                                            check_tile_has_block = (check_x, check_y) in walls or (check_x, check_y) in destructible_walls or (check_x, check_y) in powerups
                                            check_tile_has_bomb = False
                                            for other_bomb in bombs:
                                                if other_bomb != bomb and other_bomb.grid_x == check_x and other_bomb.grid_y == check_y and not other_bomb.exploded:
                                                    check_tile_has_bomb = True
                                                    break
                                            
                                            if not check_tile_has_block and not check_tile_has_bomb:
                                                bomb.throw_target_x = check_x * CELL_SIZE + CELL_SIZE // 2
                                                bomb.throw_target_y = check_y * CELL_SIZE + CELL_SIZE // 2
                                                target_grid_x = check_x
                                                target_grid_y = check_y
                                                
                                                # Recalculate velocity toward new target to continue movement
                                                # When thrown offscreen, maintain throw direction to continue wrapping behavior
                                                THROW_SPEED = 10.0
                                                
                                                # If thrown offscreen and just wrapped back, maintain strict direction (don't recalculate based on target position)
                                                # This ensures bomb continues in throw direction after wrapping, not back across screen
                                                # Use the persistent flag to maintain direction even when target is not immediately adjacent
                                                if was_thrown_offscreen_wrap or (hasattr(bomb, 'just_wrapped_back_offscreen') and bomb.just_wrapped_back_offscreen):
                                                    # Maintain throw direction - bomb should continue moving in same direction
                                                    if bomb.throw_direction_x != 0:
                                                        bomb.velocity_x = bomb.throw_direction_x * THROW_SPEED
                                                        bomb.velocity_y = 0.0
                                                    elif bomb.throw_direction_y != 0:
                                                        bomb.velocity_x = 0.0
                                                        bomb.velocity_y = bomb.throw_direction_y * THROW_SPEED
                                                else:
                                                    # Not thrown offscreen - calculate direction to target normally
                                                    dx_new = bomb.throw_target_x - wrapped_x
                                                    dy_new = bomb.throw_target_y - wrapped_y
                                                    
                                                    # Account for wrapping in direction calculation
                                                    if abs(dx_new) > WINDOW_WIDTH / 2:
                                                        if dx_new > 0:
                                                            dx_new = dx_new - WINDOW_WIDTH
                                                        else:
                                                            dx_new = dx_new + WINDOW_WIDTH
                                                    if abs(dy_new) > WINDOW_HEIGHT / 2:
                                                        if dy_new > 0:
                                                            dy_new = dy_new - WINDOW_HEIGHT
                                                        else:
                                                            dy_new = dy_new + WINDOW_HEIGHT
                                                    
                                                    distance_new = math.sqrt(dx_new * dx_new + dy_new * dy_new)
                                                    if distance_new > 0:
                                                        bomb.velocity_x = (dx_new / distance_new) * THROW_SPEED
                                                        bomb.velocity_y = (dy_new / distance_new) * THROW_SPEED
                                                
                                                found_available_tile = True
                                                break
                                        
                                        if found_available_tile:
                                            break
                        
                        # Check if bomb is currently over a block (wall or destructible wall)
                        # Initialize bounced_walls if not exists
                        if not hasattr(bomb, 'bounced_walls'):
                            bomb.bounced_walls = set()
                        
                        # Check if bomb has reached initial target (3-tile throw)
                        # IMPORTANT: Don't override target every frame - velocity is already set correctly when thrown
                        # Just check if we've reached the initial target and switch to final target when reached
                        if hasattr(bomb, 'initial_target_x') and hasattr(bomb, 'initial_target_y') and hasattr(bomb, 'reached_initial_target') and not bomb.reached_initial_target:
                            # Check if bomb was thrown offscreen - if so, skip initial target check
                            was_thrown_offscreen_initial = False
                            if hasattr(bomb, 'throw_start_grid_x') and hasattr(bomb, 'throw_start_grid_y'):
                                start_x = bomb.throw_start_grid_x % GRID_WIDTH
                                start_y = bomb.throw_start_grid_y % GRID_HEIGHT
                                start_pixel_x = start_x * CELL_SIZE + CELL_SIZE // 2
                                start_pixel_y = start_y * CELL_SIZE + CELL_SIZE // 2
                                
                                screen_center_x = WINDOW_WIDTH / 2
                                screen_center_y = WINDOW_HEIGHT / 2
                                start_on_right = start_pixel_x > screen_center_x
                                start_on_bottom = start_pixel_y > screen_center_y
                                final_target_on_right = bomb.throw_target_x > screen_center_x
                                final_target_on_bottom = bomb.throw_target_y > screen_center_y
                                
                                target_opposite_x = (start_on_right != final_target_on_right)
                                target_opposite_y = (start_on_bottom != final_target_on_bottom)
                                
                                dx_to_final = bomb.throw_target_x - start_pixel_x
                                dy_to_final = bomb.throw_target_y - start_pixel_y
                                
                                was_thrown_offscreen_initial = ((abs(dx_to_final) > WINDOW_WIDTH * 0.75 and target_opposite_x) or 
                                                                 (abs(dy_to_final) > WINDOW_HEIGHT * 0.75 and target_opposite_y))
                            
                            # If thrown offscreen, skip initial target and go straight to final target
                            if was_thrown_offscreen_initial:
                                bomb.reached_initial_target = True
                            else:
                                # Not thrown offscreen - check if bomb has reached initial 3-tile target
                                # Use initial target for distance check (but don't override throw_target_x/y - velocity already points there)
                                wrapped_x_for_target = wrapped_x
                                wrapped_y_for_target = wrapped_y
                                
                                # Check pixel distance to initial target
                                dx_initial = bomb.initial_target_x - wrapped_x_for_target
                                dy_initial = bomb.initial_target_y - wrapped_y_for_target
                                
                                # Account for wrapping in pixel distance
                                if abs(dx_initial) > WINDOW_WIDTH / 2:
                                    if dx_initial > 0:
                                        dx_initial = dx_initial - WINDOW_WIDTH
                                    else:
                                        dx_initial = dx_initial + WINDOW_WIDTH
                                if abs(dy_initial) > WINDOW_HEIGHT / 2:
                                    if dy_initial > 0:
                                        dy_initial = dy_initial - WINDOW_HEIGHT
                                    else:
                                        dy_initial = dy_initial + WINDOW_HEIGHT
                                
                                pixel_distance_initial = math.sqrt(dx_initial * dx_initial + dy_initial * dy_initial)
                                
                                # Mark as reached if very close to initial target
                                if pixel_distance_initial < 15.0:
                                    bomb.reached_initial_target = True
                                    # Now switch to final target and recalculate velocity
                                    # Find final target (first available tile starting from 3 tiles)
                                    if hasattr(bomb, 'throw_start_grid_x') and hasattr(bomb, 'throw_start_grid_y'):
                                        start_x = bomb.throw_start_grid_x % GRID_WIDTH
                                        start_y = bomb.throw_start_grid_y % GRID_HEIGHT
                                        
                                        # Find first available tile starting from 3 tiles
                                        for distance in range(3, GRID_WIDTH + GRID_HEIGHT + 1):
                                            check_x = (start_x + bomb.throw_direction_x * distance) % GRID_WIDTH
                                            check_y = (start_y + bomb.throw_direction_y * distance) % GRID_HEIGHT
                                            
                                            is_edge = (check_x == 0 or check_x == GRID_WIDTH - 1 or 
                                                      check_y == 0 or check_y == GRID_HEIGHT - 1)
                                            
                                            has_block = False
                                            if not is_edge:
                                                has_block = (check_x, check_y) in walls or (check_x, check_y) in destructible_walls or (check_x, check_y) in powerups
                                            
                                            has_bomb = False
                                            for other_bomb in bombs:
                                                if other_bomb != bomb and other_bomb.grid_x == check_x and other_bomb.grid_y == check_y and not other_bomb.exploded:
                                                    has_bomb = True
                                                    break
                                            
                                            if not has_block and not has_bomb:
                                                bomb.throw_target_x = check_x * CELL_SIZE + CELL_SIZE // 2
                                                bomb.throw_target_y = check_y * CELL_SIZE + CELL_SIZE // 2
                                                target_grid_x = check_x
                                                target_grid_y = check_y
                                                
                                                # Recalculate velocity toward final target
                                                THROW_SPEED = 10.0
                                                dx_final = bomb.throw_target_x - wrapped_x_for_target
                                                dy_final = bomb.throw_target_y - wrapped_y_for_target
                                                
                                                # Account for wrapping
                                                if abs(dx_final) > WINDOW_WIDTH / 2:
                                                    if dx_final > 0:
                                                        dx_final = dx_final - WINDOW_WIDTH
                                                    else:
                                                        dx_final = dx_final + WINDOW_WIDTH
                                                if abs(dy_final) > WINDOW_HEIGHT / 2:
                                                    if dy_final > 0:
                                                        dy_final = dy_final - WINDOW_HEIGHT
                                                    else:
                                                        dy_final = dy_final + WINDOW_HEIGHT
                                                
                                                distance_final = math.sqrt(dx_final * dx_final + dy_final * dy_final)
                                                if distance_final > 0:
                                                    bomb.velocity_x = (dx_final / distance_final) * THROW_SPEED
                                                    bomb.velocity_y = (dy_final / distance_final) * THROW_SPEED
                                                break
                        
                        # Check if current position is an edge wall (screen boundary)
                        is_edge_wall = (current_grid_x == 0 or current_grid_x == GRID_WIDTH - 1 or 
                                       current_grid_y == 0 or current_grid_y == GRID_HEIGHT - 1)
                        
                        # Check for blocks at current position (skip edge walls to allow wrapping)
                        # Use actual bomb position to check which grid cells it overlaps
                        bomb_radius = CELL_SIZE // 2
                        bomb_left = wrapped_x - bomb_radius
                        bomb_right = wrapped_x + bomb_radius
                        bomb_top = wrapped_y - bomb_radius
                        bomb_bottom = wrapped_y + bomb_radius
                        
                        # Check all grid cells the bomb overlaps
                        # Expand range slightly to catch fast-moving bombs near tile boundaries
                        grid_left = max(0, int(bomb_left // CELL_SIZE) - 1)
                        grid_right = min(GRID_WIDTH - 1, int(bomb_right // CELL_SIZE) + 1)
                        grid_top = max(0, int(bomb_top // CELL_SIZE) - 1)
                        grid_bottom = min(GRID_HEIGHT - 1, int(bomb_bottom // CELL_SIZE) + 1)
                        
                        current_has_block = False
                        current_wall_pos = None
                        
                        # Check if bomb has reached initial target OR if bomb has wrapped around
                        # Check if bomb is currently offscreen
                        is_currently_offscreen = (new_bomb_x < 0 or new_bomb_x > WINDOW_WIDTH or 
                                                 new_bomb_y < 0 or new_bomb_y > WINDOW_HEIGHT)
                        
                        # Mark that bomb has wrapped if it goes offscreen
                        if is_currently_offscreen:
                            bomb._has_wrapped = True
                        
                        # Check if bomb was thrown offscreen (target is on opposite side)
                        was_thrown_offscreen = False
                        if hasattr(bomb, 'throw_start_grid_x') and hasattr(bomb, 'throw_start_grid_y'):
                            start_x = bomb.throw_start_grid_x % GRID_WIDTH
                            start_y = bomb.throw_start_grid_y % GRID_HEIGHT
                            start_pixel_x = start_x * CELL_SIZE + CELL_SIZE // 2
                            start_pixel_y = start_y * CELL_SIZE + CELL_SIZE // 2
                            
                            # Check if target is on opposite side from start
                            screen_center_x = WINDOW_WIDTH / 2
                            screen_center_y = WINDOW_HEIGHT / 2
                            start_on_right = start_pixel_x > screen_center_x
                            start_on_bottom = start_pixel_y > screen_center_y
                            target_on_right = bomb.throw_target_x > screen_center_x
                            target_on_bottom = bomb.throw_target_y > screen_center_y
                            
                            target_opposite_x = (start_on_right != target_on_right)
                            target_opposite_y = (start_on_bottom != target_on_bottom)
                            
                            dx_to_target = bomb.throw_target_x - start_pixel_x
                            dy_to_target = bomb.throw_target_y - start_pixel_y
                            
                            was_thrown_offscreen = ((abs(dx_to_target) > WINDOW_WIDTH * 0.75 and target_opposite_x) or 
                                                   (abs(dy_to_target) > WINDOW_HEIGHT * 0.75 and target_opposite_y))
                        
                        # Bomb can bounce if:
                        # 1. It has reached initial target (3 tiles), OR
                        # 2. It was thrown offscreen (skip 3-tile check), OR
                        # 3. It has wrapped at least once
                        # IMPORTANT: If bomb just wrapped back onscreen, allow bouncing immediately
                        # This ensures bomb bounces off blocks instead of flying across screen
                        has_wrapped_before = (hasattr(bomb, '_has_wrapped') and bomb._has_wrapped)
                        can_bounce = (hasattr(bomb, 'reached_initial_target') and bomb.reached_initial_target) or was_thrown_offscreen or has_wrapped_before or just_wrapped_back
                        
                        if can_bounce:
                            # Check all overlapping grid cells for blocks
                            # Also check adjacent cells to catch fast-moving bombs
                            extended_grid_left = max(0, grid_left - 1)
                            extended_grid_right = min(GRID_WIDTH - 1, grid_right + 1)
                            extended_grid_top = max(0, grid_top - 1)
                            extended_grid_bottom = min(GRID_HEIGHT - 1, grid_bottom + 1)
                            
                            for check_grid_x in range(extended_grid_left, extended_grid_right + 1):
                                for check_grid_y in range(extended_grid_top, extended_grid_bottom + 1):
                                    # Skip actual edge walls (x=0, x=GRID_WIDTH-1, etc.) to allow wrapping
                                    # But check tiles NEXT TO edge walls (x=1, x=GRID_WIDTH-2, etc.)
                                    is_check_edge = (check_grid_x == 0 or check_grid_x == GRID_WIDTH - 1 or 
                                                   check_grid_y == 0 or check_grid_y == GRID_HEIGHT - 1)
                                    
                                    # Check blocks in all tiles except actual edge walls
                                    # Tiles adjacent to edge walls (like x=1 when edge is x=0) should be checked
                                    if not is_check_edge:
                                        check_pos = (check_grid_x, check_grid_y)
                                        if (check_pos in walls or check_pos in destructible_walls):
                                            # Check if bomb circle actually overlaps with this cell
                                            cell_left = check_grid_x * CELL_SIZE
                                            cell_right = cell_left + CELL_SIZE
                                            cell_top = check_grid_y * CELL_SIZE
                                            cell_bottom = cell_top + CELL_SIZE
                                            
                                            # Find closest point on cell to bomb center
                                            closest_x = max(cell_left, min(wrapped_x, cell_right))
                                            closest_y = max(cell_top, min(wrapped_y, cell_bottom))
                                            
                                            dx = wrapped_x - closest_x
                                            dy = wrapped_y - closest_y
                                            distance_sq = dx * dx + dy * dy
                                            
                                            if distance_sq < bomb_radius * bomb_radius:
                                                current_has_block = True
                                                current_wall_pos = check_pos
                                                break
                                
                                if current_has_block:
                                    break
                        
                        # If bomb enters a wall cell it hasn't bounced off yet, bounce off it
                        # Skip edge walls to allow wrapping
                        # BUT: If bomb just wrapped back onscreen after being thrown offscreen, delay bounce detection
                        # Let it continue in throw direction first to show wraparound animation
                        should_skip_bounce = False
                        
                        # Check if bomb just wrapped back (this frame) or recently wrapped back
                        if just_wrapped_back or (hasattr(bomb, 'just_wrapped_back_offscreen') and bomb.just_wrapped_back_offscreen):
                            # Check if bomb was thrown offscreen
                            was_thrown_offscreen_bounce = False
                            if hasattr(bomb, 'throw_start_grid_x') and hasattr(bomb, 'throw_start_grid_y'):
                                start_x = bomb.throw_start_grid_x % GRID_WIDTH
                                start_y = bomb.throw_start_grid_y % GRID_HEIGHT
                                start_pixel_x = start_x * CELL_SIZE + CELL_SIZE // 2
                                start_pixel_y = start_y * CELL_SIZE + CELL_SIZE // 2
                                
                                screen_center_x = WINDOW_WIDTH / 2
                                screen_center_y = WINDOW_HEIGHT / 2
                                start_on_right = start_pixel_x > screen_center_x
                                start_on_bottom = start_pixel_y > screen_center_y
                                final_target_on_right = bomb.throw_target_x > screen_center_x
                                final_target_on_bottom = bomb.throw_target_y > screen_center_y
                                
                                target_opposite_x = (start_on_right != final_target_on_right)
                                target_opposite_y = (start_on_bottom != final_target_on_bottom)
                                
                                dx_to_final = bomb.throw_target_x - start_pixel_x
                                dy_to_final = bomb.throw_target_y - start_pixel_y
                                
                                was_thrown_offscreen_bounce = ((abs(dx_to_final) > WINDOW_WIDTH * 0.75 and target_opposite_x) or 
                                                               (abs(dy_to_final) > WINDOW_HEIGHT * 0.75 and target_opposite_y))
                            
                            # Allow bouncing immediately, but maintain throw speed and wraparound animation
                            # The wraparound animation will be shown via drawing logic, not by delaying bounce
                            # This ensures bomb bounces correctly while still showing animation
                            # Don't skip bounce - let it bounce, but maintain throw speed during wraparound period
                            should_skip_bounce = False
                        
                        if current_has_block and current_wall_pos is not None and current_wall_pos not in bomb.bounced_walls and not should_skip_bounce:
                            # Mark this wall as bounced
                            bomb.bounced_walls.add(current_wall_pos)
                            
                            # Start bounce animation
                            bomb.bounce_start_time = current_time
                            bomb.bounce_velocity = 5.0  # Small upward velocity for subtle bounce (positive = upward)
                            bomb.bounce_offset = 0.0
                            
                            # Find next available tile in the same direction from the wall we hit
                            wall_grid_x, wall_grid_y = current_wall_pos
                            next_x = None
                            next_y = None
                            max_search = GRID_WIDTH * GRID_HEIGHT * 2
                            
                            # Start from the tile immediately after the wall (distance=1)
                            # This ensures we check tiles next to edge walls
                            for distance in range(1, max_search + 1):
                                check_x = (wall_grid_x + bomb.throw_direction_x * distance) % GRID_WIDTH
                                check_y = (wall_grid_y + bomb.throw_direction_y * distance) % GRID_HEIGHT
                                
                                # Check if current position is an edge wall (screen boundary) - allow wrapping through edge walls
                                # Edge walls themselves (x=0, x=GRID_WIDTH-1) are skipped, but tiles next to them are checked
                                is_edge_wall = (check_x == 0 or check_x == GRID_WIDTH - 1 or 
                                               check_y == 0 or check_y == GRID_HEIGHT - 1)
                                
                                # Check if tile has a block (exclude actual edge walls to allow wrapping)
                                # But tiles NEXT TO edge walls (like x=1 when edge is x=0) should be checked
                                tile_has_block = False
                                if not is_edge_wall:
                                    tile_has_block = (check_x, check_y) in walls or (check_x, check_y) in destructible_walls or (check_x, check_y) in powerups
                                
                                # Check if tile has another bomb
                                tile_has_bomb = False
                                for other_bomb in bombs:
                                    if other_bomb != bomb and other_bomb.grid_x == check_x and other_bomb.grid_y == check_y and not other_bomb.exploded:
                                        tile_has_bomb = True
                                        break
                                
                                # If tile is clear, use it as new target
                                # This includes tiles next to edge walls (like x=1, y=1, etc.)
                                if not tile_has_block and not tile_has_bomb:
                                    next_x = check_x
                                    next_y = check_y
                                    break
                            
                            # If we found a next tile, update target and velocity
                            if next_x is not None and next_y is not None:
                                bomb.throw_target_x = next_x * CELL_SIZE + CELL_SIZE // 2
                                bomb.throw_target_y = next_y * CELL_SIZE + CELL_SIZE // 2
                                
                                # Maintain strict direction - only move in original throw direction
                                # This ensures bomb stays on the same row (horizontal) or column (vertical)
                                # If bomb just wrapped back onscreen, maintain THROW_SPEED for wraparound animation
                                # Otherwise use BOUNCE_SPEED for normal bouncing
                                if hasattr(bomb, 'just_wrapped_back_offscreen') and bomb.just_wrapped_back_offscreen:
                                    # During wraparound animation period, maintain throw speed
                                    THROW_SPEED_BOUNCE = 10.0
                                    if bomb.throw_direction_x != 0:
                                        # Horizontal throw - only move horizontally
                                        bomb.velocity_x = bomb.throw_direction_x * THROW_SPEED_BOUNCE
                                        bomb.velocity_y = 0.0
                                    elif bomb.throw_direction_y != 0:
                                        # Vertical throw - only move vertically
                                        bomb.velocity_x = 0.0
                                        bomb.velocity_y = bomb.throw_direction_y * THROW_SPEED_BOUNCE
                                    else:
                                        # Fallback: calculate direction but ensure it's axis-aligned
                                        bounce_dx = bomb.throw_target_x - new_bomb_x
                                        bounce_dy = bomb.throw_target_y - new_bomb_y
                                        
                                        # Account for wrapping in direction calculation
                                        if abs(bounce_dx) > WINDOW_WIDTH / 2:
                                            if bounce_dx > 0:
                                                bounce_dx = bounce_dx - WINDOW_WIDTH
                                            else:
                                                bounce_dx = bounce_dx + WINDOW_WIDTH
                                        if abs(bounce_dy) > WINDOW_HEIGHT / 2:
                                            if bounce_dy > 0:
                                                bounce_dy = bounce_dy - WINDOW_HEIGHT
                                            else:
                                                bounce_dy = bounce_dy + WINDOW_HEIGHT
                                        
                                        # Determine which axis has larger movement and use that direction only
                                        THROW_SPEED_BOUNCE = 10.0
                                        if abs(bounce_dx) > abs(bounce_dy):
                                            # Horizontal movement
                                            bomb.velocity_x = (1 if bounce_dx > 0 else -1) * THROW_SPEED_BOUNCE
                                            bomb.velocity_y = 0.0
                                        else:
                                            # Vertical movement
                                            bomb.velocity_x = 0.0
                                            bomb.velocity_y = (1 if bounce_dy > 0 else -1) * THROW_SPEED_BOUNCE
                                else:
                                    # Normal bounce - use slower speed
                                    BOUNCE_SPEED = 4.0
                                    if bomb.throw_direction_x != 0:
                                        # Horizontal throw - only move horizontally
                                        bomb.velocity_x = bomb.throw_direction_x * BOUNCE_SPEED
                                        bomb.velocity_y = 0.0
                                    elif bomb.throw_direction_y != 0:
                                        # Vertical throw - only move vertically
                                        bomb.velocity_x = 0.0
                                        bomb.velocity_y = bomb.throw_direction_y * BOUNCE_SPEED
                                    else:
                                        # Fallback: calculate direction but ensure it's axis-aligned
                                        bounce_dx = bomb.throw_target_x - new_bomb_x
                                        bounce_dy = bomb.throw_target_y - new_bomb_y
                                        
                                        # Account for wrapping in direction calculation
                                        if abs(bounce_dx) > WINDOW_WIDTH / 2:
                                            if bounce_dx > 0:
                                                bounce_dx = bounce_dx - WINDOW_WIDTH
                                            else:
                                                bounce_dx = bounce_dx + WINDOW_WIDTH
                                        if abs(bounce_dy) > WINDOW_HEIGHT / 2:
                                            if bounce_dy > 0:
                                                bounce_dy = bounce_dy - WINDOW_HEIGHT
                                            else:
                                                bounce_dy = bounce_dy + WINDOW_HEIGHT
                                        
                                        # Determine which axis has larger movement and use that direction only
                                        BOUNCE_SPEED = 4.0
                                        if abs(bounce_dx) > abs(bounce_dy):
                                            # Horizontal movement
                                            bomb.velocity_x = (1 if bounce_dx > 0 else -1) * BOUNCE_SPEED
                                            bomb.velocity_y = 0.0
                                        else:
                                            # Vertical movement
                                            bomb.velocity_x = 0.0
                                            bomb.velocity_y = (1 if bounce_dy > 0 else -1) * BOUNCE_SPEED
                                
                                # Play bounce sound effect
                                if bomb_bounce_sound:
                                    try:
                                        bomb_bounce_sound.play()
                                    except Exception as e:
                                        pass  # Ignore sound errors
                        
                        # Check if bomb is currently over a block (for bounce sound)
                        # Only play sound if bomb has traveled 3+ tiles from throw start
                        if current_has_block and bomb_bounce_sound:
                            # Calculate distance traveled in tiles
                            tiles_traveled = 0
                            if hasattr(bomb, 'throw_start_grid_x') and hasattr(bomb, 'throw_start_grid_y'):
                                start_x = bomb.throw_start_grid_x % GRID_WIDTH
                                start_y = bomb.throw_start_grid_y % GRID_HEIGHT
                                # Calculate Manhattan distance (tiles traveled)
                                dx_tiles = abs((current_grid_x - start_x + GRID_WIDTH // 2) % GRID_WIDTH - GRID_WIDTH // 2)
                                dy_tiles = abs((current_grid_y - start_y + GRID_HEIGHT // 2) % GRID_HEIGHT - GRID_HEIGHT // 2)
                                tiles_traveled = dx_tiles + dy_tiles
                            
                            # Only play sound if bomb has traveled 3+ tiles
                            if tiles_traveled >= 3:
                                # Check if we haven't already played sound for this block
                                if not hasattr(bomb, '_last_bounce_block') or bomb._last_bounce_block != (current_grid_x, current_grid_y):
                                    bomb._last_bounce_block = (current_grid_x, current_grid_y)
                                    try:
                                        bomb_bounce_sound.play()
                                    except Exception as e:
                                        pass  # Ignore sound errors
                        
                        # Check if we're at the target grid cell
                        at_target_grid = (current_grid_x == target_grid_x and current_grid_y == target_grid_y)
                        
                        # Also check pixel distance for fine-tuning (within same cell)
                        # Use initial target if bomb hasn't reached it yet, otherwise use final target
                        if hasattr(bomb, 'initial_target_x') and hasattr(bomb, 'initial_target_y') and hasattr(bomb, 'reached_initial_target') and not bomb.reached_initial_target:
                            check_target_pixel_x = bomb.initial_target_x
                            check_target_pixel_y = bomb.initial_target_y
                        else:
                            check_target_pixel_x = bomb.throw_target_x
                            check_target_pixel_y = bomb.throw_target_y
                        
                        # Use wrapped positions for distance calculation
                        dx = check_target_pixel_x - wrapped_x
                        dy = check_target_pixel_y - wrapped_y
                        
                        # Account for wrapping in pixel distance
                        if abs(dx) > WINDOW_WIDTH / 2:
                            if dx > 0:
                                dx = dx - WINDOW_WIDTH
                            else:
                                dx = dx + WINDOW_WIDTH
                        if abs(dy) > WINDOW_HEIGHT / 2:
                            if dy > 0:
                                dy = dy - WINDOW_HEIGHT
                            else:
                                dy = dy + WINDOW_HEIGHT
                        
                        pixel_distance = math.sqrt(dx * dx + dy * dy)
                        
                        # Check if target tile is available BEFORE checking if we've reached it
                        # Use the actual target grid position
                        target_grid_x = int(bomb.throw_target_x // CELL_SIZE) % GRID_WIDTH
                        target_grid_y = int(bomb.throw_target_y // CELL_SIZE) % GRID_HEIGHT
                        
                        # Continuously check for available tiles in throw direction
                        # BUT only after bomb has reached initial 3-tile target (unless thrown offscreen)
                        # This prevents skipping tiles, especially after wrapping or near edge walls
                        # Check if bomb has reached initial target first
                        has_reached_initial = (hasattr(bomb, 'reached_initial_target') and bomb.reached_initial_target)
                        was_thrown_offscreen_check = False
                        if hasattr(bomb, 'throw_start_grid_x') and hasattr(bomb, 'throw_start_grid_x'):
                            start_x = bomb.throw_start_grid_x % GRID_WIDTH
                            start_y = bomb.throw_start_grid_y % GRID_HEIGHT
                            start_pixel_x = start_x * CELL_SIZE + CELL_SIZE // 2
                            start_pixel_y = start_y * CELL_SIZE + CELL_SIZE // 2
                            
                            screen_center_x = WINDOW_WIDTH / 2
                            screen_center_y = WINDOW_HEIGHT / 2
                            start_on_right = start_pixel_x > screen_center_x
                            start_on_bottom = start_pixel_y > screen_center_y
                            target_on_right = bomb.throw_target_x > screen_center_x
                            target_on_bottom = bomb.throw_target_y > screen_center_y
                            
                            target_opposite_x = (start_on_right != target_on_right)
                            target_opposite_y = (start_on_bottom != target_on_bottom)
                            
                            dx_to_target = bomb.throw_target_x - start_pixel_x
                            dy_to_target = bomb.throw_target_y - start_pixel_y
                            
                            was_thrown_offscreen_check = ((abs(dx_to_target) > WINDOW_WIDTH * 0.75 and target_opposite_x) or 
                                                          (abs(dy_to_target) > WINDOW_HEIGHT * 0.75 and target_opposite_y))
                        
                        # Only check for closer tiles if bomb has reached initial target OR was thrown offscreen
                        if (has_reached_initial or was_thrown_offscreen_check) and (bomb.throw_direction_x != 0 or bomb.throw_direction_y != 0):
                            # Check up to 5 tiles ahead in throw direction
                            # This catches fast-moving bombs and ensures we check tiles next to edge walls
                            for check_dist in range(0, 6):  # Check current tile (0) through 5 tiles ahead
                                check_x = (current_grid_x + bomb.throw_direction_x * check_dist) % GRID_WIDTH
                                check_y = (current_grid_y + bomb.throw_direction_y * check_dist) % GRID_HEIGHT
                                
                                # Skip actual edge walls (to allow wrapping)
                                is_check_edge = (check_x == 0 or check_x == GRID_WIDTH - 1 or 
                                               check_y == 0 or check_y == GRID_HEIGHT - 1)
                                if is_check_edge:
                                    continue
                                
                                # Check if this tile is available
                                check_tile_has_block = (check_x, check_y) in walls or (check_x, check_y) in destructible_walls or (check_x, check_y) in powerups
                                check_tile_has_bomb = False
                                for other_bomb in bombs:
                                    if other_bomb != bomb and other_bomb.grid_x == check_x and other_bomb.grid_y == check_y and not other_bomb.exploded:
                                        check_tile_has_bomb = True
                                        break
                                
                                # If we find an available tile, check if it's closer than current target
                                if not check_tile_has_block and not check_tile_has_bomb:
                                    # Calculate distance to current target
                                    if bomb.throw_direction_x != 0:
                                        dist_to_current_target = abs((target_grid_x - current_grid_x + GRID_WIDTH // 2) % GRID_WIDTH - GRID_WIDTH // 2)
                                    else:
                                        dist_to_current_target = abs((target_grid_y - current_grid_y + GRID_HEIGHT // 2) % GRID_HEIGHT - GRID_HEIGHT // 2)
                                    
                                    # If this tile is closer than current target, update target
                                    if check_dist < dist_to_current_target:
                                        bomb.throw_target_x = check_x * CELL_SIZE + CELL_SIZE // 2
                                        bomb.throw_target_y = check_y * CELL_SIZE + CELL_SIZE // 2
                                        target_grid_x = check_x
                                        target_grid_y = check_y
                                        
                                        # If bomb just wrapped back after being thrown offscreen, maintain throw direction
                                        # This ensures smooth wraparound animation even when target is not immediately adjacent
                                        if hasattr(bomb, 'just_wrapped_back_offscreen') and bomb.just_wrapped_back_offscreen:
                                            THROW_SPEED = 10.0
                                            if bomb.throw_direction_x != 0:
                                                bomb.velocity_x = bomb.throw_direction_x * THROW_SPEED
                                                bomb.velocity_y = 0.0
                                            elif bomb.throw_direction_y != 0:
                                                bomb.velocity_x = 0.0
                                                bomb.velocity_y = bomb.throw_direction_y * THROW_SPEED
                                        
                                        break  # Use first available tile found
                        
                        # Check if current position is an edge wall (screen boundary)
                        is_target_edge_wall = (target_grid_x == 0 or target_grid_x == GRID_WIDTH - 1 or 
                                               target_grid_y == 0 or target_grid_y == GRID_HEIGHT - 1)
                        
                        # Check if target tile has a block (exclude edge walls to allow wrapping)
                        target_has_block = False
                        if not is_target_edge_wall:
                            target_has_block = (target_grid_x, target_grid_y) in walls or (target_grid_x, target_grid_y) in destructible_walls or (target_grid_x, target_grid_y) in powerups
                        
                        # Check if tile has another bomb
                        target_has_bomb = False
                        for other_bomb in bombs:
                            if other_bomb != bomb and other_bomb.grid_x == target_grid_x and other_bomb.grid_y == target_grid_y and not other_bomb.exploded:
                                target_has_bomb = True
                                break
                        
                        # If target is blocked, find next available tile and update target
                        if target_has_block or target_has_bomb:
                            # Initialize bounced_walls if not exists
                            if not hasattr(bomb, 'bounced_walls'):
                                bomb.bounced_walls = set()
                            
                            # Mark target wall as bounced if we're close to it
                            if at_target_grid and pixel_distance < CELL_SIZE:
                                bomb.bounced_walls.add((target_grid_x, target_grid_y))
                                
                                # Start bounce animation
                                bomb.bounce_start_time = current_time
                                bomb.bounce_velocity = 5.0
                                bomb.bounce_offset = 0.0
                            
                            # Find next available tile in same direction
                            next_x = None
                            next_y = None
                            max_search = GRID_WIDTH * GRID_HEIGHT * 2
                            
                            for distance in range(1, max_search + 1):
                                check_x = (target_grid_x + bomb.throw_direction_x * distance) % GRID_WIDTH
                                check_y = (target_grid_y + bomb.throw_direction_y * distance) % GRID_HEIGHT
                                
                                # Check if current position is an edge wall (screen boundary) - allow wrapping through edge walls
                                is_edge_wall = (check_x == 0 or check_x == GRID_WIDTH - 1 or 
                                               check_y == 0 or check_y == GRID_HEIGHT - 1)
                                
                                # Check if tile has a block (exclude edge walls to allow wrapping)
                                tile_has_block = False
                                if not is_edge_wall:
                                    tile_has_block = (check_x, check_y) in walls or (check_x, check_y) in destructible_walls or (check_x, check_y) in powerups
                                
                                # Check if tile has another bomb
                                tile_has_bomb = False
                                for other_bomb in bombs:
                                    if other_bomb != bomb and other_bomb.grid_x == check_x and other_bomb.grid_y == check_y and not other_bomb.exploded:
                                        tile_has_bomb = True
                                        break
                                
                                # If tile is clear, use it as new target
                                if not tile_has_block and not tile_has_bomb:
                                    next_x = check_x
                                    next_y = check_y
                                    break
                            
                            # If we found a next tile, update target and velocity
                            if next_x is not None and next_y is not None:
                                bomb.throw_target_x = next_x * CELL_SIZE + CELL_SIZE // 2
                                bomb.throw_target_y = next_y * CELL_SIZE + CELL_SIZE // 2
                                
                                # Maintain strict direction - only move in original throw direction
                                # This ensures bomb stays on the same row (horizontal) or column (vertical)
                                THROW_SPEED = 10.0
                                if bomb.throw_direction_x != 0:
                                    # Horizontal throw - only move horizontally
                                    bomb.velocity_x = bomb.throw_direction_x * THROW_SPEED
                                    bomb.velocity_y = 0.0
                                elif bomb.throw_direction_y != 0:
                                    # Vertical throw - only move vertically
                                    bomb.velocity_x = 0.0
                                    bomb.velocity_y = bomb.throw_direction_y * THROW_SPEED
                                else:
                                    # Fallback: calculate direction but ensure it's axis-aligned
                                    new_dx = bomb.throw_target_x - new_bomb_x
                                    new_dy = bomb.throw_target_y - new_bomb_y
                                    
                                    # Account for wrapping in direction calculation
                                    if abs(new_dx) > WINDOW_WIDTH / 2:
                                        if new_dx > 0:
                                            new_dx = new_dx - WINDOW_WIDTH
                                        else:
                                            new_dx = new_dx + WINDOW_WIDTH
                                    if abs(new_dy) > WINDOW_HEIGHT / 2:
                                        if new_dy > 0:
                                            new_dy = new_dy - WINDOW_HEIGHT
                                        else:
                                            new_dy = new_dy + WINDOW_HEIGHT
                                    
                                    # Determine which axis has larger movement and use that direction only
                                    if abs(new_dx) > abs(new_dy):
                                        # Horizontal movement
                                        bomb.velocity_x = (1 if new_dx > 0 else -1) * THROW_SPEED
                                        bomb.velocity_y = 0.0
                                    else:
                                        # Vertical movement
                                        bomb.velocity_x = 0.0
                                        bomb.velocity_y = (1 if new_dy > 0 else -1) * THROW_SPEED
                                
                                # Play bounce sound effect
                                if bomb_bounce_sound:
                                    try:
                                        bomb_bounce_sound.play()
                                    except Exception as e:
                                        pass  # Ignore sound errors
                                
                                continue  # Continue moving to next tile
                        
                        # Check if target is same as start position (requires wrapping animation)
                        target_same_as_start = False
                        start_x = None
                        start_y = None
                        start_pixel_x = None
                        start_pixel_y = None
                        if hasattr(bomb, 'throw_start_grid_x') and hasattr(bomb, 'throw_start_grid_y'):
                            start_x = bomb.throw_start_grid_x % GRID_WIDTH
                            start_y = bomb.throw_start_grid_y % GRID_HEIGHT
                            target_same_as_start = (target_grid_x == start_x and target_grid_y == start_y)
                            
                            # Get starting pixel position
                            if hasattr(bomb, '_start_pixel_x'):
                                start_pixel_x = bomb._start_pixel_x
                                start_pixel_y = bomb._start_pixel_y
                            else:
                                # Store starting pixel position
                                start_pixel_x = bomb.pixel_x
                                start_pixel_y = bomb.pixel_y
                                bomb._start_pixel_x = start_pixel_x
                                bomb._start_pixel_y = start_pixel_y
                        
                        # If target is same as start, require bomb to wrap around at least once
                        # Check if bomb has actually wrapped (gone offscreen and come back)
                        has_wrapped = False
                        has_moved_away = False
                        if target_same_as_start and start_pixel_x is not None and start_pixel_y is not None:
                            # Check if bomb has moved away from start position (at least 2 cells in pixels)
                            pixel_distance_from_start = math.sqrt((new_bomb_x - start_pixel_x)**2 + (new_bomb_y - start_pixel_y)**2)
                            has_moved_away = pixel_distance_from_start > CELL_SIZE * 2
                            
                            # Check if bomb has gone offscreen (wrapped) at least once
                            # Mark that bomb has wrapped if it's currently offscreen
                            if new_bomb_x < 0 or new_bomb_x > WINDOW_WIDTH or new_bomb_y < 0 or new_bomb_y > WINDOW_HEIGHT:
                                bomb._has_wrapped = True
                            
                            # Bomb has wrapped if it's been offscreen
                            has_wrapped = (hasattr(bomb, '_has_wrapped') and bomb._has_wrapped)
                        
                        # Check if bomb has reached initial 3-tile target
                        # Bomb should NOT stop at final target until it reaches initial target first (unless thrown offscreen)
                        has_reached_initial_target = (hasattr(bomb, 'reached_initial_target') and bomb.reached_initial_target)
                        
                        # Clear the just_wrapped_back_offscreen flag when bomb reaches its target
                        # OR when bomb has traveled far enough to show wraparound animation (at least 3 tiles)
                        # Only clear if target is actually available (not blocked)
                        should_clear_flag = False
                        
                        # Check if bomb has traveled far enough from wrap-back position
                        if hasattr(bomb, 'wrap_back_pixel_x') and bomb.wrap_back_pixel_x is not None:
                            distance_since_wrap = math.sqrt((wrapped_x - bomb.wrap_back_pixel_x)**2 + (wrapped_y - bomb.wrap_back_pixel_y)**2)
                            # Clear flag if bomb has traveled at least 3 tiles (enough for animation)
                            if distance_since_wrap >= CELL_SIZE * 3:
                                should_clear_flag = True
                        
                        # Also clear if bomb reaches its target
                        if at_target_grid and pixel_distance < 10.0:
                            # Check if target is available
                            is_target_edge_wall_check = (target_grid_x == 0 or target_grid_x == GRID_WIDTH - 1 or 
                                                         target_grid_y == 0 or target_grid_y == GRID_HEIGHT - 1)
                            target_has_block_check = False
                            if not is_target_edge_wall_check:
                                target_has_block_check = (target_grid_x, target_grid_y) in walls or (target_grid_x, target_grid_y) in destructible_walls or (target_grid_x, target_grid_y) in powerups
                            
                            target_has_bomb_check = False
                            for other_bomb in bombs:
                                if other_bomb != bomb and other_bomb.grid_x == target_grid_x and other_bomb.grid_y == target_grid_y and not other_bomb.exploded:
                                    target_has_bomb_check = True
                                    break
                            
                            # Only clear flag if target is actually available (bomb can stop here)
                            if not target_has_block_check and not target_has_bomb_check:
                                should_clear_flag = True
                        
                        if should_clear_flag:
                            if hasattr(bomb, 'just_wrapped_back_offscreen'):
                                bomb.just_wrapped_back_offscreen = False
                        
                        # Reached target if we're at the grid cell AND very close in pixels (< 10 pixels) AND target is available
                        # AND bomb has reached initial target (unless thrown offscreen)
                        # IMPORTANT: If target is same as start, don't stop until bomb has moved away and wrapped
                        
                        # Check if bomb was thrown offscreen
                        was_thrown_offscreen_stop = False
                        if hasattr(bomb, 'throw_start_grid_x') and hasattr(bomb, 'throw_start_grid_y'):
                            start_x = bomb.throw_start_grid_x % GRID_WIDTH
                            start_y = bomb.throw_start_grid_y % GRID_HEIGHT
                            start_pixel_x = start_x * CELL_SIZE + CELL_SIZE // 2
                            start_pixel_y = start_y * CELL_SIZE + CELL_SIZE // 2
                            
                            screen_center_x = WINDOW_WIDTH / 2
                            screen_center_y = WINDOW_HEIGHT / 2
                            start_on_right = start_pixel_x > screen_center_x
                            start_on_bottom = start_pixel_y > screen_center_y
                            target_on_right = bomb.throw_target_x > screen_center_x
                            target_on_bottom = bomb.throw_target_y > screen_center_y
                            
                            target_opposite_x = (start_on_right != target_on_right)
                            target_opposite_y = (start_on_bottom != target_on_bottom)
                            
                            dx_to_target = bomb.throw_target_x - start_pixel_x
                            dy_to_target = bomb.throw_target_y - start_pixel_y
                            
                            was_thrown_offscreen_stop = ((abs(dx_to_target) > WINDOW_WIDTH * 0.75 and target_opposite_x) or 
                                                         (abs(dy_to_target) > WINDOW_HEIGHT * 0.75 and target_opposite_y))
                        
                        # If target is same as start, prevent stopping until bomb has wrapped
                        if target_same_as_start:
                            # Don't allow stopping until bomb has wrapped around
                            if not has_wrapped:
                                # Bomb hasn't wrapped yet - force it to keep moving
                                can_stop = False
                            else:
                                # Bomb has wrapped - now check if it can stop
                                # Require bomb to have moved away from start (at least 2 cells) AND wrapped around AND come back
                                can_stop = (not target_has_block and not target_has_bomb and has_moved_away)
                                
                                # Additional check: bomb must be back on screen (not offscreen)
                                if new_bomb_x < 0 or new_bomb_x > WINDOW_WIDTH or new_bomb_y < 0 or new_bomb_y > WINDOW_HEIGHT:
                                    can_stop = False
                        else:
                            # Normal target - can stop if available AND bomb has reached initial target (unless thrown offscreen)
                            can_stop = (not target_has_block and not target_has_bomb)
                            
                            # Don't stop until initial target is reached (unless thrown offscreen)
                            if not was_thrown_offscreen_stop and not has_reached_initial_target:
                                can_stop = False
                            
                            # If bomb just wrapped back onscreen after being thrown offscreen, ensure it continues moving
                            # Don't stop until it has traveled far enough to show wraparound animation
                            if hasattr(bomb, 'just_wrapped_back_offscreen') and bomb.just_wrapped_back_offscreen:
                                if hasattr(bomb, 'wrap_back_pixel_x') and bomb.wrap_back_pixel_x is not None:
                                    distance_since_wrap = math.sqrt((wrapped_x - bomb.wrap_back_pixel_x)**2 + (wrapped_y - bomb.wrap_back_pixel_y)**2)
                                    # Don't stop until bomb has traveled at least 3 tiles since wrapping back
                                    # This ensures wraparound animation is visible even when target is far away
                                    if distance_since_wrap < CELL_SIZE * 3:
                                        can_stop = False
                                else:
                                    # If wrap position not set, prevent stopping for a bit to show animation
                                    can_stop = False
                        
                        if at_target_grid and pixel_distance < 10.0 and can_stop:
                            # Check if this is the initial target
                            if hasattr(bomb, 'initial_target_x') and hasattr(bomb, 'initial_target_y') and hasattr(bomb, 'reached_initial_target'):
                                initial_target_grid_x = int(bomb.initial_target_x // CELL_SIZE) % GRID_WIDTH
                                initial_target_grid_y = int(bomb.initial_target_y // CELL_SIZE) % GRID_HEIGHT
                                if current_grid_x == initial_target_grid_x and current_grid_y == initial_target_grid_y:
                                    bomb.reached_initial_target = True
                            # Snap to target position (accounting for wrapping)
                            # Find the wrapped version of target that's closest to current position
                            target_x = bomb.throw_target_x
                            target_y = bomb.throw_target_y
                            
                            # Check all possible wrapped positions of target
                            target_options = [
                                (target_x, target_y),  # Direct
                                (target_x - WINDOW_WIDTH, target_y),  # Wrapped left
                                (target_x + WINDOW_WIDTH, target_y),  # Wrapped right
                                (target_x, target_y - WINDOW_HEIGHT),  # Wrapped up
                                (target_x, target_y + WINDOW_HEIGHT),  # Wrapped down
                                (target_x - WINDOW_WIDTH, target_y - WINDOW_HEIGHT),  # Wrapped diagonal
                                (target_x - WINDOW_WIDTH, target_y + WINDOW_HEIGHT),
                                (target_x + WINDOW_WIDTH, target_y - WINDOW_HEIGHT),
                                (target_x + WINDOW_WIDTH, target_y + WINDOW_HEIGHT),
                            ]
                            
                            # Find closest wrapped target to current position
                            closest_target = target_options[0]
                            min_dist = math.sqrt((target_x - new_bomb_x)**2 + (target_y - new_bomb_y)**2)
                            for tx, ty in target_options:
                                dist = math.sqrt((tx - new_bomb_x)**2 + (ty - new_bomb_y)**2)
                                if dist < min_dist:
                                    min_dist = dist
                                    closest_target = (tx, ty)
                            
                            # Wrap the closest target back to screen bounds
                            final_x = closest_target[0]
                            final_y = closest_target[1]
                            if final_x < 0:
                                final_x = final_x + WINDOW_WIDTH
                            elif final_x >= WINDOW_WIDTH:
                                final_x = final_x - WINDOW_WIDTH
                            if final_y < 0:
                                final_y = final_y + WINDOW_HEIGHT
                            elif final_y >= WINDOW_HEIGHT:
                                final_y = final_y - WINDOW_HEIGHT
                            
                            # Keep actual position unwrapped for visual animation
                            bomb.pixel_x = new_bomb_x  # Keep unwrapped for visual
                            bomb.pixel_y = new_bomb_y  # Keep unwrapped for visual
                            # Update grid position using wrapped coordinates for collision detection
                            bomb.grid_x = int(final_x // CELL_SIZE)
                            bomb.grid_y = int(final_y // CELL_SIZE)
                            # Store wrapped position for later use when landing
                            bomb._wrapped_x = final_x
                            bomb._wrapped_y = final_y
                            
                            # Target is clear, stop the bomb
                            # Snap bomb to grid center using wrapped coordinates
                            # Use stored wrapped position if available, otherwise calculate it
                            if hasattr(bomb, '_wrapped_x'):
                                snap_x = bomb._wrapped_x
                                snap_y = bomb._wrapped_y
                            else:
                                # Calculate wrapped position
                                snap_x = new_bomb_x
                                snap_y = new_bomb_y
                                # Wrap X position
                                while snap_x < 0:
                                    snap_x = snap_x + WINDOW_WIDTH
                                while snap_x >= WINDOW_WIDTH:
                                    snap_x = snap_x - WINDOW_WIDTH
                                # Wrap Y position
                                while snap_y < 0:
                                    snap_y = snap_y + WINDOW_HEIGHT
                                while snap_y >= WINDOW_HEIGHT:
                                    snap_y = snap_y - WINDOW_HEIGHT
                            
                            # Snap to grid center - ensure pixel position matches grid center exactly
                            bomb.grid_x = int(snap_x // CELL_SIZE)
                            bomb.grid_y = int(snap_y // CELL_SIZE)
                            # Ensure grid coordinates are within bounds
                            bomb.grid_x = bomb.grid_x % GRID_WIDTH
                            bomb.grid_y = bomb.grid_y % GRID_HEIGHT
                            # Set pixel position to exact grid center
                            bomb.pixel_x = bomb.grid_x * CELL_SIZE + CELL_SIZE // 2
                            bomb.pixel_y = bomb.grid_y * CELL_SIZE + CELL_SIZE // 2
                            # Reset bounce offset to ensure sprite aligns
                            bomb.bounce_offset = 0.0
                            bomb.bounce_velocity = 0.0
                            bomb.bounce_start_time = None
                            
                            # Clean up stored wrapped position
                            if hasattr(bomb, '_wrapped_x'):
                                delattr(bomb, '_wrapped_x')
                                delattr(bomb, '_wrapped_y')
                            
                            bomb.velocity_x = 0.0
                            bomb.velocity_y = 0.0
                            bomb.is_moving = False
                            # Restart timer
                            bomb.is_thrown = False
                            bomb.placed_time = current_time
                            bomb.throw_target_x = None
                            bomb.throw_target_y = None
                            bomb.throw_direction_x = 0
                            bomb.throw_direction_y = 0
                            # Clear player throwing state if this bomb was thrown by a player
                            if player1 and bomb == player1.thrown_bomb:
                                player1.thrown_bomb = None
                                player1.is_throwing = False
                            if player2 and bomb == player2.thrown_bomb:
                                player2.thrown_bomb = None
                                player2.is_throwing = False
                            continue  # Skip rest of movement logic
                    
                    # Check collision at new position
                    can_move_x = True
                    can_move_y = True
                    
                    # Get bomb bounding box (bomb is roughly cell-sized)
                    bomb_radius = CELL_SIZE // 2
                    bomb_left = new_bomb_x - bomb_radius
                    bomb_right = new_bomb_x + bomb_radius
                    bomb_top = new_bomb_y - bomb_radius
                    bomb_bottom = new_bomb_y + bomb_radius
                    
                    # Bounds check for kicked bombs (wrapping already applied for thrown bombs above)
                    if not bomb.is_thrown:
                        # Normal bounds check for kicked bombs
                        if bomb_left < 0 or bomb_right >= WINDOW_WIDTH:
                            can_move_x = False
                        if bomb_top < 0 or bomb_bottom >= WINDOW_HEIGHT:
                            can_move_y = False
                    
                    # Check collision with walls (permanent and destructible)
                    grid_left = int(bomb_left // CELL_SIZE)
                    grid_right = int(bomb_right // CELL_SIZE)
                    grid_top = int(bomb_top // CELL_SIZE)
                    grid_bottom = int(bomb_bottom // CELL_SIZE)
                    
                    # Thrown bombs can pass over walls, kicked bombs cannot
                    if not bomb.is_thrown:
                        for grid_x in range(grid_left, grid_right + 1):
                            for grid_y in range(grid_top, grid_bottom + 1):
                                if (grid_x, grid_y) in walls or (grid_x, grid_y) in destructible_walls or (grid_x, grid_y) in sudden_death_blocks:
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
                    # Only remove powerups when bomb is on-screen (not when wrapping or offscreen)
                    # Use actual bomb position (not bounce offset) for collision detection
                    powerups_to_remove = []
                    
                    # Check if bomb is actually onscreen (not offscreen)
                    # For thrown bombs, only check collision if bomb is onscreen (not wrapped)
                    is_onscreen = (new_bomb_x >= 0 and new_bomb_x < WINDOW_WIDTH and 
                                  new_bomb_y >= 0 and new_bomb_y < WINDOW_HEIGHT)
                    
                    # Skip powerup removal for thrown bombs (they bounce over powerups instead)
                    if not bomb.is_thrown:
                        # For non-thrown bombs, check collision with powerups
                        if is_onscreen:
                            # Use actual bomb position for collision (not wrapped position)
                            actual_bomb_x = new_bomb_x
                            actual_bomb_y = new_bomb_y
                            
                            # Calculate grid cell the bomb is in
                            bomb_grid_x = int(actual_bomb_x // CELL_SIZE)
                            bomb_grid_y = int(actual_bomb_y // CELL_SIZE)
                            
                            # Only check the single grid cell the bomb is in (not a range)
                            # This prevents removing powerups from adjacent cells
                            if (bomb_grid_x >= 0 and bomb_grid_x < GRID_WIDTH and 
                                bomb_grid_y >= 0 and bomb_grid_y < GRID_HEIGHT):
                                
                                if (bomb_grid_x, bomb_grid_y) in powerups:
                                    # Check if bomb is actually colliding with powerup in this cell
                                    powerup_x = bomb_grid_x * CELL_SIZE + CELL_SIZE // 2
                                    powerup_y = bomb_grid_y * CELL_SIZE + CELL_SIZE // 2
                                    
                                    dx = actual_bomb_x - powerup_x
                                    dy = actual_bomb_y - powerup_y
                                    distance_squared = dx * dx + dy * dy
                                    
                                    if distance_squared < bomb_radius * bomb_radius:
                                        # Remove powerup without animation
                                        powerups_to_remove.append((bomb_grid_x, bomb_grid_y))
                    
                    # Remove powerups that were hit by the bomb
                    for powerup_pos in powerups_to_remove:
                        powerups.pop(powerup_pos, None)
                    
                    # Check collision with other bombs (thrown bombs with target can pass through other bombs until they reach target)
                    if not (bomb.is_thrown and bomb.throw_target_x is not None):
                        # Only check bomb collisions for non-thrown bombs or thrown bombs without a target
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
                    
                    # Check collision with players (thrown bombs with target skip player collision to allow them to travel to target)
                    if not (bomb.is_thrown and bomb.throw_target_x is not None):
                        # Check collision with player 1
                        if player1:
                            player_grid_x = int(player1.x // CELL_SIZE)
                            player_grid_y = int(player1.y // CELL_SIZE)
                            bomb_grid_x = int(bomb.pixel_x // CELL_SIZE)
                            bomb_grid_y = int(bomb.pixel_y // CELL_SIZE)
                            player_on_bomb = (player_grid_x == bomb_grid_x and player_grid_y == bomb_grid_y)
                            
                            if not player_on_bomb:
                                # Check circle collision with player
                                dx = new_bomb_x - player1.x
                                dy = new_bomb_y - player1.y
                                distance_squared = dx * dx + dy * dy
                                
                                if distance_squared < (bomb_radius + PLAYER_RADIUS) * (bomb_radius + PLAYER_RADIUS):
                                    if abs(bomb.velocity_x) > 0:
                                        can_move_x = False
                                    if abs(bomb.velocity_y) > 0:
                                        can_move_y = False
                        
                        # Check collision with player 2
                        if player2:
                            player_grid_x = int(player2.x // CELL_SIZE)
                            player_grid_y = int(player2.y // CELL_SIZE)
                            bomb_grid_x = int(bomb.pixel_x // CELL_SIZE)
                            bomb_grid_y = int(bomb.pixel_y // CELL_SIZE)
                            player_on_bomb = (player_grid_x == bomb_grid_x and player_grid_y == bomb_grid_y)
                            
                            if not player_on_bomb:
                                # Check circle collision with player
                                dx = new_bomb_x - player2.x
                                dy = new_bomb_y - player2.y
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
                    # Skip grid position update for thrown bombs while moving - let them move freely
                    if not (bomb.is_thrown and bomb.is_moving):
                        bomb.update_grid_pos()
                    
                    # Stop bomb if both velocities are zero
                    if bomb.velocity_x == 0.0 and bomb.velocity_y == 0.0:
                        bomb.is_moving = False
                        # Snap to center of grid cell when stopped - ensure alignment
                        # Wrap grid coordinates if needed
                        bomb.grid_x = bomb.grid_x % GRID_WIDTH
                        bomb.grid_y = bomb.grid_y % GRID_HEIGHT
                        # Set pixel position to exact grid center
                        bomb.pixel_x = bomb.grid_x * CELL_SIZE + CELL_SIZE // 2
                        bomb.pixel_y = bomb.grid_y * CELL_SIZE + CELL_SIZE // 2
                        # Reset bounce offset to ensure sprite aligns
                        if hasattr(bomb, 'bounce_offset'):
                            bomb.bounce_offset = 0.0
                            bomb.bounce_velocity = 0.0
                            bomb.bounce_start_time = None
                        
                        # If this was a thrown bomb, restart its timer
                        if bomb.is_thrown:
                            bomb.is_thrown = False
                            # Restart timer completely by resetting placed_time to current time
                            bomb.placed_time = current_time
                            bomb.throw_target_x = None
                            bomb.throw_target_y = None
                            # Clear player throwing state if this bomb was thrown by a player
                            if player1 and bomb == player1.thrown_bomb:
                                player1.thrown_bomb = None
                                player1.is_throwing = False
                            if player2 and bomb == player2.thrown_bomb:
                                player2.thrown_bomb = None
                                player2.is_throwing = False
        
        # Clear the screen and draw ground tiles
        draw_ground()
        
        # Draw the grid (optional - you can remove this if you don't want grid lines)
        # draw_grid()
        
        # Draw the destructible walls (before permanent walls so they appear on top)
        draw_destructible_walls(current_time)
        
        # Draw the permanent walls
        draw_walls()
        
        # Draw sudden death blocks
        draw_sudden_death_blocks(current_time)
        
        # Draw the bombs (non-thrown bombs only)
        draw_bombs(current_time)
        
        # Draw powerups
        draw_powerups(current_time)
        
        # Draw thrown bombs (after powerups so they appear in front)
        draw_thrown_bombs(current_time)
        
        # Draw item explosion animations
        draw_item_explosions(current_time)
        
        # Draw the players - sort by Y position so higher Y (closer to bottom) is drawn on top
        active_players = []
        if player1:
            active_players.append(player1)
        if player2:
            active_players.append(player2)
        
        # Sort by Y position (lower Y first, higher Y last) so higher Y appears on top
        active_players.sort(key=lambda p: p.y)
        
        for player in active_players:
            draw_player(player, current_time)
        
        # Draw hurry animation last so it appears on top of everything (including players)
        draw_hurry_animation(current_time)
        
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
