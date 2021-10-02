import math, sys
from lux.game import Game
from lux.game_map import Cell, RESOURCE_TYPES
from lux.constants import Constants
from lux.game_constants import GAME_CONSTANTS
from lux import annotate
import logging

logging.basicConfig(filename="agent.log", level=logging.INFO, filemode="w")

DIRECTIONS = Constants.DIRECTIONS
game_state = None

build_location = None

def get_resource_tiles(game_state, width, height):
    resource_tiles: list[Cell] = []
    for y in range(height):
        for x in range(width):
            cell = game_state.map.get_cell(x, y)
            if cell.has_resource():
                resource_tiles.append(cell)
    return resource_tiles


def get_close_resource(unit, resource_tiles, player):
    closest_dist = math.inf
    closest_resource_tile = None
    # if the unit is a worker and we have space in cargo, lets find the nearest resource tile and try to mine it
    for resource_tile in resource_tiles:
        if resource_tile.resource.type == Constants.RESOURCE_TYPES.COAL and not player.researched_coal(): continue
        if resource_tile.resource.type == Constants.RESOURCE_TYPES.URANIUM and not player.researched_uranium(): continue
        dist = resource_tile.pos.distance_to(unit.pos)
        if dist < closest_dist:
            closest_dist = dist
            closest_resource_tile = resource_tile
    return closest_resource_tile


def get_close_city(unit, player):
    closest_dist = math.inf
    closest_city_tile = None
    for k, city in player.cities.items():
        for city_tile in city.citytiles:
            dist = city_tile.pos.distance_to(unit.pos)
            if dist < closest_dist:
                closest_dist = dist
                closest_city_tile = city_tile  
    return closest_city_tile



def agent(observation, configuration):
    global game_state
    global build_location

    ### Do not edit ###
    if observation["step"] == 0:
        game_state = Game()
        game_state._initialize(observation["updates"])
        game_state._update(observation["updates"][2:])
        game_state.id = observation.player
    else:
        game_state._update(observation["updates"])
    
    actions = []

    ### AI Code goes down here! ### 
    player = game_state.players[observation.player]
    opponent = game_state.players[(observation.player + 1) % 2]
    width, height = game_state.map.width, game_state.map.height

    cities = player.cities.values()
    city_tiles = []

    for city in cities:
        for c_tile in city.citytiles:
            city_tiles.append(c_tile)

    # logging.info(f"cities : {cities}")
    # logging.info(f"city_tiles : {city_tiles }")

    resource_tiles = get_resource_tiles(game_state, width, height)

    build_city = False
    if(len(city_tiles)) < 2:
        build_city = True

    # we iterate over all our units and do something with them
    for unit in player.units:
        if unit.is_worker() and unit.can_act():
            if unit.get_cargo_space_left() > 0:
                closest_resource_tile = get_close_resource(unit, resource_tiles, player)

                if closest_resource_tile is not None:
                    actions.append(unit.move(unit.pos.direction_to(closest_resource_tile.pos)))
            else:
                # if unit is a worker and there is no cargo space left, and we have cities, lets return to them

                if(build_city):
                    logging.info(f"We want to build a city")
                    if build_location is None:
                        empty_near = get_close_city(unit, player)

                        dirs = [(1,0), (0,1), (-1,0), (0,-1)]

                        for d in dirs:
                            try:
                                possible_build_location = game_state.map.get_cell(empty_near.pos.x + d[0], empty_near.pos.y + d[1])
                                if possible_build_location.resource == None and possible_build_location.road == 0 and possible_build_location.citytile == None:
                                    build_location = possible_build_location
                                    logging.info(f"{observation['step']} : Found Build Location {build_city}") 
                                    break

                            except Exception as e:
                                logging.warning(f"{observation['step']} : While searching for empty tiles {str(e)}")

                    elif unit.pos == build_location.pos:
                        logging.info(f"Elif Case") 

                        action = unit.build_city()
                        actions.append(action)

                        build_city = False
                        build_location = None
                        continue

                    else:
                        logging.info(f"{observation['step']} : Navigate to where we want to build city") 
                        move_dir = unit.pos.direction_to(build_location.pos)
                        actions.append(unit.move(move_dir))
                        continue



                if len(player.cities) > 0:
                    closest_city_tile = get_close_city(unit, player)
                    if closest_city_tile is not None:
                        move_dir = unit.pos.direction_to(closest_city_tile.pos)
                        actions.append(unit.move(move_dir))

    # you can add debug annotations using the functions in the annotate object
    # actions.append(annotate.circle(0, 0))
    
    return actions
