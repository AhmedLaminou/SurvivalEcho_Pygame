"""
Survivor's Echo - Pygame prototype
A single-file prototype demonstrating a 3D-survival-inspired 2D game made with Pygame.
This file intentionally contains many systems to simulate a fuller game:
- World generation (tile-based)
- Player with inventory, crafting and health/hunger/thirst
- Resource nodes and harvesting
- Day/night cycle and weather
- Simple wildlife AI (roaming, hunting, fleeing)
- Base building (place structures)
- Combat, stealth, stamina
- Save/load snapshot (JSON)
- Simple UI and menus

Notes:
- This is a 2D top-down game built with Pygame — not actually 3D.
- Assets are placeholders (colours / procedurally drawn). Replace with images/sounds as needed.
- Requires Python 3.8+ and pygame: pip install pygame

Author: Ahmed Laminou (prototype)
"""


import pygame
import sys
import os
import json
import math
import random
from dataclasses import dataclass, field
from typing import Tuple, Dict, List, Optional

# ---------------------------
# Configuration & Constants
# ---------------------------
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
FPS = 60

TILE_SIZE = 32
WORLD_WIDTH = 80  # number of tiles horizontally
WORLD_HEIGHT = 60  # number of tiles vertically

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DARK_GRAY = (30, 30, 30)
LIGHT_GRAY = (200, 200, 200)
WOOD_BROWN = (140, 100, 60)
STONE_GRAY = (120, 120, 120)
GRASS_GREEN = (75, 160, 80)
WATER_BLUE = (30, 90, 160)
PLAYER_COLOR = (200, 180, 60)
ENEMY_COLOR = (180, 60, 60)
DAY_COLOR = (135, 206, 235)
NIGHT_TINT = (0, 0, 30, 120)

SAVE_FILE = 'survivors_echo_save.json'

# Gameplay constants
MAX_HEALTH = 100
MAX_HUNGER = 100
MAX_THIRST = 100
MAX_STAMINA = 100

HARVEST_TIME = 1.0  # seconds to harvest a resource node
DAY_LENGTH = 300.0  # seconds for a full day-night cycle

# Debug
DEBUG = False

# ---------------------------
# Utility functions
# ---------------------------

def clamp(n, a, b):
    return max(a, min(b, n))


def world_to_screen(tx, ty, cam_x, cam_y):
    sx = (tx * TILE_SIZE) - cam_x + SCREEN_WIDTH // 2
    sy = (ty * TILE_SIZE) - cam_y + SCREEN_HEIGHT // 2
    return int(sx), int(sy)


def screen_to_world(sx, sy, cam_x, cam_y):
    tx = (sx - SCREEN_WIDTH // 2 + cam_x) // TILE_SIZE
    ty = (sy - SCREEN_HEIGHT // 2 + cam_y) // TILE_SIZE
    return int(tx), int(ty)


# ---------------------------
# World & Tile system
# ---------------------------
TILE_GRASS = 'grass'
TILE_WATER = 'water'
TILE_FOREST = 'forest'
TILE_ROCK = 'rock'
TILE_SAND = 'sand'

RESOURCE_TREE = 'tree'
RESOURCE_STONE = 'stone'
RESOURCE_BUSH = 'bush'

@dataclass
class Tile:
    kind: str = TILE_GRASS
    resource: Optional[str] = None
    resource_amount: int = 0
    built: Optional[str] = None  # structure placed


class World:
    def __init__(self, w=WORLD_WIDTH, h=WORLD_HEIGHT):
        self.w = w
        self.h = h
        self.tiles: List[List[Tile]] = [[Tile() for _ in range(h)] for _ in range(w)]
        self.generate()

    def generate(self):
        # Simple procedural generation using noise-like placement
        random.seed(42)
        for x in range(self.w):
            for y in range(self.h):
                r = random.random()
                if r < 0.05:
                    self.tiles[x][y] = Tile(kind=TILE_WATER)
                elif r < 0.20:
                    self.tiles[x][y] = Tile(kind=TILE_FOREST, resource=RESOURCE_TREE, resource_amount=random.randint(3, 8))
                elif r < 0.28:
                    self.tiles[x][y] = Tile(kind=TILE_ROCK, resource=RESOURCE_STONE, resource_amount=random.randint(2, 6))
                elif r < 0.35:
                    self.tiles[x][y] = Tile(kind=TILE_SAND)
                else:
                    # mixture of grass and occasional bushes
                    if random.random() < 0.03:
                        self.tiles[x][y] = Tile(kind=TILE_GRASS, resource=RESOURCE_BUSH, resource_amount=random.randint(1, 4))
                    else:
                        self.tiles[x][y] = Tile(kind=TILE_GRASS)

    def in_bounds(self, tx, ty):
        return 0 <= tx < self.w and 0 <= ty < self.h

    def get_tile(self, tx, ty) -> Optional[Tile]:
        if not self.in_bounds(tx, ty):
            return None
        return self.tiles[tx][ty]

    def harvest(self, tx, ty, amount=1):
        tile = self.get_tile(tx, ty)
        if not tile or not tile.resource:
            return 0
        taken = min(amount, tile.resource_amount)
        tile.resource_amount -= taken
        if tile.resource_amount <= 0:
            # resource depleted
            tile.resource = None
            # optional: change tile appearance
            if tile.kind == TILE_FOREST:
                tile.kind = TILE_GRASS
            if tile.kind == TILE_ROCK:
                tile.kind = TILE_GRASS
        return taken

    def place_structure(self, tx, ty, structure_name):
        tile = self.get_tile(tx, ty)
        if not tile or tile.built:
            return False
        tile.built = structure_name
        return True

    def remove_structure(self, tx, ty):
        tile = self.get_tile(tx, ty)
        if not tile or not tile.built:
            return False
        tile.built = None
        return True

    def to_dict(self):
        data = {
            'w': self.w,
            'h': self.h,
            'tiles': []
        }
        for x in range(self.w):
            col = []
            for y in range(self.h):
                t = self.tiles[x][y]
                col.append({'k': t.kind, 'r': t.resource, 'a': t.resource_amount, 'b': t.built})
            data['tiles'].append(col)
        return data

    @staticmethod
    def from_dict(data):
        w = data['w']
        h = data['h']
        world = World(w, h)
        world.tiles = [[Tile() for _ in range(h)] for _ in range(w)]
        for x in range(w):
            for y in range(h):
                cell = data['tiles'][x][y]
                world.tiles[x][y] = Tile(kind=cell['k'], resource=cell['r'], resource_amount=cell['a'], built=cell['b'])
        return world


# ---------------------------
# Player & Inventory
# ---------------------------
@dataclass
class Item:
    id: str
    name: str
    amount: int = 1


@dataclass
class Inventory:
    items: Dict[str, Item] = field(default_factory=dict)
    capacity: int = 30

    def add(self, item_id: str, name: str, amount: int = 1) -> bool:
        # naive capacity: number of distinct stacks
        if item_id in self.items:
            self.items[item_id].amount += amount
            return True
        if len(self.items) >= self.capacity:
            return False
        self.items[item_id] = Item(id=item_id, name=name, amount=amount)
        return True

    def remove(self, item_id: str, amount: int = 1) -> bool:
        if item_id not in self.items:
            return False
        it = self.items[item_id]
        if it.amount < amount:
            return False
        it.amount -= amount
        if it.amount == 0:
            del self.items[item_id]
        return True

    def has(self, item_id: str, amount: int = 1) -> bool:
        return item_id in self.items and self.items[item_id].amount >= amount

    def to_list(self):
        return [{ 'id': it.id, 'name': it.name, 'amount': it.amount } for it in self.items.values()]

    @staticmethod
    def from_list(lst):
        inv = Inventory()
        inv.items = {i['id']: Item(id=i['id'], name=i['name'], amount=i['amount']) for i in lst}
        return inv


@dataclass
class Player:
    x: float
    y: float
    angle: float = 0.0
    health: float = MAX_HEALTH
    hunger: float = 0.0
    thirst: float = 0.0
    stamina: float = MAX_STAMINA
    inventory: Inventory = field(default_factory=Inventory)
    equipped: Optional[str] = None
    attack_power: float = 10.0

    def to_dict(self):
        return {
            'x': self.x,
            'y': self.y,
            'health': self.health,
            'hunger': self.hunger,
            'thirst': self.thirst,
            'stamina': self.stamina,
            'inventory': self.inventory.to_list(),
            'equipped': self.equipped
        }

    @staticmethod
    def from_dict(d):
        p = Player(x=d['x'], y=d['y'])
        p.health = d['health']
        p.hunger = d['hunger']
        p.thirst = d['thirst']
        p.stamina = d['stamina']
        p.inventory = Inventory.from_list(d['inventory'])
        p.equipped = d['equipped']
        return p


# ---------------------------
# Entities: animals / NPCs
# ---------------------------
class Entity:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.health = 50
        self.speed = 40.0
        self.target = None
        self.state = 'idle'
        self.radius = 10

    def update(self, dt, world, player):
        # simple roaming AI
        if self.state == 'idle':
            if random.random() < 0.01:
                self.state = 'roam'
                ang = random.random() * math.tau
                self.vx = math.cos(ang) * self.speed
                self.vy = math.sin(ang) * self.speed
        elif self.state == 'roam':
            # slight chance to stop
            if random.random() < 0.005:
                self.state = 'idle'
                self.vx = self.vy = 0
        # pursue player if close
        dx = player.x - self.x
        dy = player.y - self.y
        dist = math.hypot(dx, dy)
        if dist < 150:
            # detect player
            self.state = 'attack'
            self.vx = (dx / dist) * (self.speed * 1.2)
            self.vy = (dy / dist) * (self.speed * 1.2)
        # flee if low health
        if self.health < 20 and random.random() < 0.3:
            self.state = 'flee'
            ang = math.atan2(self.y - player.y, self.x - player.x)
            self.vx = math.cos(ang) * self.speed * 1.5
            self.vy = math.sin(ang) * self.speed * 1.5

        # integrate
        self.x += self.vx * dt
        self.y += self.vy * dt


# ---------------------------
# Crafting recipes
# ---------------------------
RECIPES = {
    'wooden_spear': {
        'requires': {'wood': 3, 'stone': 1},
        'name': 'Wooden Spear'
    },
    'campfire': {
        'requires': {'wood': 5},
        'name': 'Campfire'
    },
    'stone_axe': {
        'requires': {'wood': 2, 'stone': 3},
        'name': 'Stone Axe'
    },
    'wooden_shack': {
        'requires': {'wood': 20},
        'name': 'Wooden Shack'
    }
}


# ---------------------------
# Game class orchestrating
# ---------------------------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Survivor's Echo - Pygame Prototype")
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont('Consolas', 18)
        self.large_font = pygame.font.SysFont('Consolas', 28, bold=True)

        self.world = World()
        # spawn player in center-ish
        self.player = Player(x=self.world.w * TILE_SIZE // 2, y=self.world.h * TILE_SIZE // 2)
        self.camera_x = self.player.x
        self.camera_y = self.player.y

        # entities
        self.entities: List[Entity] = []
        for i in range(12):
            ex = random.randint(0, self.world.w * TILE_SIZE)
            ey = random.randint(0, self.world.h * TILE_SIZE)
            self.entities.append(Entity(ex, ey))

        # gameplay state
        self.is_running = True
        self.paused = False
        self.time_of_day = 0.0  # 0..DAY_LENGTH
        self.weather = None  # 'rain' or None
        self.harvest_cooldown = 0.0
        self.last_harvest_time = 0.0
        self.build_mode = False
        self.selected_structure = 'campfire'
        self.debug = DEBUG

        # sounds placeholders
        self.sounds = {}

        # starter items
        self.player.inventory.add('wood', 'Wood', 5)
        self.player.inventory.add('stone', 'Stone', 3)

        # load save if exists
        if os.path.exists(SAVE_FILE):
            try:
                self.load(SAVE_FILE)
                print('Save loaded')
            except Exception as e:
                print('Failed to load save:', e)

    def run(self):
        while self.is_running:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            if not self.paused:
                self.update(dt)
            self.render()
        pygame.quit()
        sys.exit()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.save(SAVE_FILE)
                self.is_running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.paused = not self.paused
                elif event.key == pygame.K_b:
                    self.build_mode = not self.build_mode
                elif event.key == pygame.K_e:
                    self.try_interact()
                elif event.key == pygame.K_TAB:
                    self.dump_debug()
                elif event.key == pygame.K_F5:
                    self.save(SAVE_FILE)
                elif event.key == pygame.K_F9:
                    # quick heal for testing
                    self.player.health = min(MAX_HEALTH, self.player.health + 20)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # left click
                    if self.build_mode:
                        mx, my = event.pos
                        tx, ty = screen_to_world(mx, my, self.camera_x, self.camera_y)
                        ok = self.world.place_structure(tx, ty, self.selected_structure)
                        if ok:
                            print('Placed', self.selected_structure, 'at', tx, ty)
                    else:
                        # attack / interact at range
                        pass

    def dump_debug(self):
        print('Player', self.player.x, self.player.y, 'HP', self.player.health)
        print('Inventory', self.player.inventory.to_list())

    def try_interact(self):
        # interact with tile under player
        tx = int(self.player.x // TILE_SIZE)
        ty = int(self.player.y // TILE_SIZE)
        tile = self.world.get_tile(tx, ty)
        if not tile:
            return
        if tile.resource:
            print('Starting harvest on', tile.resource)
            taken = self.world.harvest(tx, ty, amount=1)
            if taken > 0:
                if tile.resource == RESOURCE_TREE:
                    self.player.inventory.add('wood', 'Wood', taken)
                elif tile.resource == RESOURCE_STONE:
                    self.player.inventory.add('stone', 'Stone', taken)
                elif tile.resource == RESOURCE_BUSH:
                    self.player.inventory.add('berries', 'Berries', taken)
        elif tile.built:
            # interact with structure
            if tile.built == 'campfire':
                # restore stamina / health slowly
                self.player.stamina = min(MAX_STAMINA, self.player.stamina + 20)
                self.player.health = min(MAX_HEALTH, self.player.health + 5)
                print('Warmed at campfire')

    def update(self, dt):
        # update day/night
        self.time_of_day = (self.time_of_day + dt) % DAY_LENGTH
        day_fraction = self.time_of_day / DAY_LENGTH
        # 0 -> day start, 0.5 -> night
        if random.random() < 0.001:
            self.weather = 'rain' if random.random() < 0.3 else None

        # update player input
        self.update_player(dt)

        # update entities
        for e in self.entities:
            e.update(dt, self.world, self.player)
            # simple collision with player
            dx = e.x - self.player.x
            dy = e.y - self.player.y
            dist = math.hypot(dx, dy)
            if dist < 20:
                # attack player
                dmg = 5 * dt
                self.player.health -= dmg
                if self.player.health <= 0:
                    print('You died!')
                    self.paused = True

        # hunger/thirst
        self.player.hunger += dt * 0.5
        self.player.thirst += dt * 0.9
        if self.player.hunger > 80:
            self.player.health -= dt * 0.5
        if self.player.thirst > 90:
            self.player.health -= dt * 1.0

        # stamina regen slowly
        if self.player.stamina < MAX_STAMINA:
            self.player.stamina = min(MAX_STAMINA, self.player.stamina + dt * 5)

        # camera follow
        self.camera_x = self.player.x
        self.camera_y = self.player.y

    def update_player(self, dt):
        keys = pygame.key.get_pressed()
        speed = 160.0
        if keys[pygame.K_LSHIFT] and self.player.stamina > 1:
            speed *= 1.8
            self.player.stamina -= dt * 10
        vx = 0.0
        vy = 0.0
        if keys[pygame.K_w]:
            vy -= 1
        if keys[pygame.K_s]:
            vy += 1
        if keys[pygame.K_a]:
            vx -= 1
        if keys[pygame.K_d]:
            vx += 1
        norm = math.hypot(vx, vy)
        if norm > 0:
            vx /= norm
            vy /= norm
            self.player.x += vx * speed * dt
            self.player.y += vy * speed * dt
            # stamina cost
            self.player.stamina = max(0, self.player.stamina - dt * 7)
        # clamp to world
        self.player.x = clamp(self.player.x, 0, self.world.w * TILE_SIZE - 1)
        self.player.y = clamp(self.player.y, 0, self.world.h * TILE_SIZE - 1)

    def craft(self, recipe_id):
        if recipe_id not in RECIPES:
            return False
        req = RECIPES[recipe_id]['requires']
        # check inventory
        for rid, amt in req.items():
            if not self.player.inventory.has(rid, amt):
                return False
        # remove resources
        for rid, amt in req.items():
            self.player.inventory.remove(rid, amt)
        # give item or structure
        if recipe_id == 'campfire':
            # place campfire at player tile
            tx = int(self.player.x // TILE_SIZE)
            ty = int(self.player.y // TILE_SIZE)
            placed = self.world.place_structure(tx, ty, 'campfire')
            if not placed:
                # refund
                for rid, amt in req.items():
                    self.player.inventory.add(rid, rid.capitalize(), amt)
                return False
            return True
        elif recipe_id == 'wooden_shack':
            tx = int(self.player.x // TILE_SIZE)
            ty = int(self.player.y // TILE_SIZE)
            placed = self.world.place_structure(tx, ty, 'shack')
            if not placed:
                for rid, amt in req.items():
                    self.player.inventory.add(rid, rid.capitalize(), amt)
                return False
            return True
        else:
            # give as item
            self.player.inventory.add(recipe_id, RECIPES[recipe_id]['name'], 1)
            return True

    def save(self, filename):
        data = {
            'world': self.world.to_dict(),
            'player': self.player.to_dict(),
            'time_of_day': self.time_of_day,
            'entities': [{'x': e.x, 'y': e.y, 'health': e.health} for e in self.entities]
        }
        with open(filename, 'w') as f:
            json.dump(data, f)
        print('Saved to', filename)

    def load(self, filename):
        with open(filename, 'r') as f:
            data = json.load(f)
        self.world = World.from_dict(data['world'])
        self.player = Player.from_dict(data['player'])
        self.time_of_day = data.get('time_of_day', 0.0)
        self.entities = [Entity(d['x'], d['y']) for d in data.get('entities', [])]
        for e, d in zip(self.entities, data.get('entities', [])):
            e.health = d.get('health', 50)

    def render(self):
        # sky background that changes with time
        day_frac = (math.cos((self.time_of_day / DAY_LENGTH) * math.tau) + 1) / 2
        sky_r = int(DAY_COLOR[0] * day_frac + NIGHT_TINT[0] * (1 - day_frac))
        sky_g = int(DAY_COLOR[1] * day_frac + NIGHT_TINT[1] * (1 - day_frac))
        sky_b = int(DAY_COLOR[2] * day_frac + NIGHT_TINT[2] * (1 - day_frac))
        self.screen.fill((sky_r, sky_g, sky_b))

        # draw tiles in view
        left = max(0, int((self.camera_x - SCREEN_WIDTH/2) // TILE_SIZE) - 1)
        right = min(self.world.w, int((self.camera_x + SCREEN_WIDTH/2) // TILE_SIZE) + 2)
        top = max(0, int((self.camera_y - SCREEN_HEIGHT/2) // TILE_SIZE) - 1)
        bottom = min(self.world.h, int((self.camera_y + SCREEN_HEIGHT/2) // TILE_SIZE) + 2)

        for tx in range(left, right):
            for ty in range(top, bottom):
                tile = self.world.get_tile(tx, ty)
                sx, sy = world_to_screen(tx, ty, self.camera_x, self.camera_y)
                rect = pygame.Rect(sx, sy, TILE_SIZE, TILE_SIZE)
                if tile.kind == TILE_WATER:
                    pygame.draw.rect(self.screen, WATER_BLUE, rect)
                elif tile.kind == TILE_FOREST:
                    pygame.draw.rect(self.screen, GRASS_GREEN, rect)
                    # draw trees
                    if tile.resource:
                        pygame.draw.circle(self.screen, WOOD_BROWN, rect.center, TILE_SIZE//3)
                elif tile.kind == TILE_ROCK:
                    pygame.draw.rect(self.screen, LIGHT_GRAY, rect)
                    if tile.resource:
                        pygame.draw.rect(self.screen, STONE_GRAY, rect.inflate(-8, -8))
                elif tile.kind == TILE_SAND:
                    pygame.draw.rect(self.screen, (194, 178, 128), rect)
                else:
                    pygame.draw.rect(self.screen, GRASS_GREEN, rect)
                    if tile.resource == RESOURCE_BUSH:
                        pygame.draw.circle(self.screen, (34, 120, 30), rect.center, TILE_SIZE//4)
                # drawn built structures
                if tile.built:
                    if tile.built == 'campfire':
                        pygame.draw.circle(self.screen, (255, 120, 0), rect.center, TILE_SIZE//4)
                    elif tile.built == 'shack':
                        pygame.draw.rect(self.screen, WOOD_BROWN, rect.inflate(-6, -6))

        # draw entities
        for e in self.entities:
            sx = int(e.x - self.camera_x + SCREEN_WIDTH//2)
            sy = int(e.y - self.camera_y + SCREEN_HEIGHT//2)
            pygame.draw.circle(self.screen, ENEMY_COLOR, (sx, sy), e.radius)

        # draw player
        px = int(self.player.x - self.camera_x + SCREEN_WIDTH//2)
        py = int(self.player.y - self.camera_y + SCREEN_HEIGHT//2)
        pygame.draw.circle(self.screen, PLAYER_COLOR, (px, py), 12)
        # direction indicator
        mx, my = pygame.mouse.get_pos()
        dx = mx - SCREEN_WIDTH//2
        dy = my - SCREEN_HEIGHT//2
        angle = math.atan2(dy, dx)
        ex = px + int(math.cos(angle) * 20)
        ey = py + int(math.sin(angle) * 20)
        pygame.draw.line(self.screen, BLACK, (px, py), (ex, ey), 2)

        # HUD
        self.render_hud()

        # debug overlays
        if self.debug:
            self.render_debug()

        pygame.display.flip()

    def render_debug(self):
        text = f'Player ({int(self.player.x)}, {int(self.player.y)}) HP:{int(self.player.health)} HUN:{int(self.player.hunger)}'
        surf = self.font.render(text, True, WHITE)
        self.screen.blit(surf, (10, SCREEN_HEIGHT - 30))

    def render_hud(self):
        # health bar
        self.draw_bar(10, 10, 200, 20, self.player.health / MAX_HEALTH, 'Health')
        self.draw_bar(10, 40, 200, 16, 1 - self.player.hunger / MAX_HUNGER, 'Hunger')
        self.draw_bar(10, 62, 200, 16, 1 - self.player.thirst / MAX_THIRST, 'Thirst')
        self.draw_bar(10, 84, 200, 12, self.player.stamina / MAX_STAMINA, 'Stamina')

        # inventory preview
        inv_items = list(self.player.inventory.items.values())[:6]
        tx = SCREEN_WIDTH - 220
        ty = 10
        pygame.draw.rect(self.screen, (40, 40, 40), (tx, ty, 210, 120))
        label = self.font.render('Inventory (preview)', True, WHITE)
        self.screen.blit(label, (tx+8, ty+6))
        oy = 30
        for it in inv_items:
            s = f'{it.name} x{it.amount}'
            surf = self.font.render(s, True, WHITE)
            self.screen.blit(surf, (tx+10, ty+oy))
            oy += 18

        # build mode indicator
        if self.build_mode:
            surf = self.large_font.render('BUILD MODE', True, (255, 200, 50))
            self.screen.blit(surf, (SCREEN_WIDTH//2 - surf.get_width()//2, 8))

        # watermark
        wm = self.font.render("Survivor's Echo - Prototype - Open Source", True, WHITE)
        self.screen.blit(wm, (SCREEN_WIDTH - wm.get_width() - 10, SCREEN_HEIGHT - wm.get_height() - 6))

    def draw_bar(self, x, y, w, h, fraction, label=''):
        pygame.draw.rect(self.screen, DARK_GRAY, (x, y, w, h))
        inner_w = int(w * clamp(fraction, 0, 1))
        pygame.draw.rect(self.screen, (50, 200, 50), (x, y, inner_w, h))
        if label:
            surf = self.font.render(label, True, WHITE)
            self.screen.blit(surf, (x + w + 6, y))


# ---------------------------
# Entry point
# ---------------------------

def main():
    game = Game()
    game.run()


if __name__ == '__main__':
    main()
