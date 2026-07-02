"""JTool object IDs and room constants."""

ROOM_WIDTH = 800
ROOM_HEIGHT = 608
GRID_SIZE = 32

MIN_COORD = -128
MAX_COORD = 896

OBJ_BLOCK = 1
OBJ_MINI_BLOCK = 2
OBJ_SPIKE_UP = 3
OBJ_SPIKE_RIGHT = 4
OBJ_SPIKE_LEFT = 5
OBJ_SPIKE_DOWN = 6
OBJ_MINI_SPIKE_UP = 7
OBJ_MINI_SPIKE_RIGHT = 8
OBJ_MINI_SPIKE_LEFT = 9
OBJ_MINI_SPIKE_DOWN = 10
OBJ_APPLE = 11
OBJ_SAVE = 12
OBJ_PLATFORM = 13
OBJ_WATER = 14
OBJ_WATER_2 = 15
OBJ_WALLJUMP_LEFT = 16
OBJ_WALLJUMP_RIGHT = 17
OBJ_KILLER_BLOCK = 18
OBJ_BULLET_BLOCKER = 19
OBJ_PLAYER_START = 20
OBJ_WARP = 21
OBJ_JUMP_REFRESHER = 22
OBJ_WATER_3 = 23
OBJ_GRAVITY_UP = 24
OBJ_GRAVITY_DOWN = 25
OBJ_SAVE_FLIP = 26
OBJ_MINI_KILLER_BLOCK = 27

OBJECT_NAMES = {
    OBJ_BLOCK: "block",
    OBJ_MINI_BLOCK: "mini_block",
    OBJ_SPIKE_UP: "spike_up",
    OBJ_SPIKE_RIGHT: "spike_right",
    OBJ_SPIKE_LEFT: "spike_left",
    OBJ_SPIKE_DOWN: "spike_down",
    OBJ_MINI_SPIKE_UP: "mini_spike_up",
    OBJ_MINI_SPIKE_RIGHT: "mini_spike_right",
    OBJ_MINI_SPIKE_LEFT: "mini_spike_left",
    OBJ_MINI_SPIKE_DOWN: "mini_spike_down",
    OBJ_APPLE: "apple",
    OBJ_SAVE: "save",
    OBJ_PLATFORM: "platform",
    OBJ_WATER: "water",
    OBJ_WATER_2: "water_2",
    OBJ_WALLJUMP_LEFT: "walljump_left",
    OBJ_WALLJUMP_RIGHT: "walljump_right",
    OBJ_KILLER_BLOCK: "killer_block",
    OBJ_BULLET_BLOCKER: "bullet_blocker",
    OBJ_PLAYER_START: "player_start",
    OBJ_WARP: "warp",
    OBJ_JUMP_REFRESHER: "jump_refresher",
    OBJ_WATER_3: "water_3",
    OBJ_GRAVITY_UP: "gravity_up",
    OBJ_GRAVITY_DOWN: "gravity_down",
    OBJ_SAVE_FLIP: "save_flip",
    OBJ_MINI_KILLER_BLOCK: "mini_killer_block",
}

OFFICIAL_SAVE_IDS = set(OBJECT_NAMES)

