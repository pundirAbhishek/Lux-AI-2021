import math, sys
from lux.game import Game
from lux.game_map import Cell, RESOURCE_TYPES
from lux.constants import Constants
from lux.game_constants import GAME_CONSTANTS
from lux import annotate
import logging
import numpy as np
from collections import deque
import random

logging.basicConfig(filename="agent.log", level=logging.INFO, filemode="w")

statsfile = "stats.txt"

DIRECTIONS = Constants.DIRECTIONS
game_state = None

build_location = None

unit_to_city_dict = {}
unit_to_resource_dict = {}
worker_positions = {}

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
        
        if resource_tile in unit_to_resource_dict.values():
            continue

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

def find_empty_tile_near(empty_near, game_state, observation):

    build_location = None

    for i in range(5):
        v = i + 1
        dirs = [(v,0), (0,v), (-v,0), (0,-v), (v,-v), (-v,v), (-v,-v), (v,v)]
        for d in dirs:
            try:
                possible_build_location = game_state.map.get_cell(empty_near.pos.x + d[0], empty_near.pos.y + d[1])
                if possible_build_location.resource == None and possible_build_location.road == 0 and possible_build_location.citytile == None:
                    build_location = possible_build_location                
                    return build_location

            except Exception as e:
                logging.warning(f"{observation['step']} : While searching for empty tiles {str(e)}")


    return None


def find_distance_between_points(unit_pos, city_pos):
    distance = math.sqrt( ((unit_pos.x-city_pos.x)**2)+((unit_pos.y-city_pos.y)**2))
    return distance

def agent(observation, configuration):
    global game_state
    global build_location
    global unit_to_city_dict
    global unit_to_resource_dict 
    global worker_positions

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

    resource_tiles = get_resource_tiles(game_state, width, height)

    workers = [u for u in player.units if u.is_worker()]

    for w in workers:

        if w.id in worker_positions:
            worker_positions[w.id].append((w.pos.x, w.pos.y))
        else:
            worker_positions[w.id] = deque(maxlen=3)
            worker_positions[w.id].append((w.pos.x, w.pos.y))

        if w.id not in unit_to_city_dict:
            city_assignment = get_close_city(w, player)
            unit_to_city_dict[w.id] = city_assignment

        if w.id not in unit_to_resource_dict:
            resource_assignment = get_close_resource(w, resource_tiles, player)
            unit_to_resource_dict[w.id] = resource_assignment        

    cities = player.cities.values()
    city_tiles = []

    for city in cities:
        for c_tile in city.citytiles:
            city_tiles.append(c_tile)

    build_city = False

    if len(city_tiles) == 0:
        build_city = True
    elif (len(workers) / len(city_tiles) >= 0.75):
        build_city = True

    # we iterate over all our units and do something with them
    for unit in player.units:
        if unit.is_worker() and unit.can_act():

            last_positions = worker_positions[unit.id]
            if len(last_positions) >=2:
                hm_positions = set(last_positions)
                if len(list(hm_positions)) == 1:
                    logging.info("Seems like worker is stuck")
                    actions.append(unit.move(random.choice(["n","s","e","w"])))
                    continue

            associated_city_id = unit_to_city_dict[unit.id].cityid
            unit_city = None
            for city in cities:
                if(city.cityid == associated_city_id):
                    unit_city = city
                    break

            if(unit_city == None):
                continue

            unit_city_tile = unit_to_city_dict[unit.id]

            cyclesToNight = (observation['step'] % 40) - 40
            distance = find_distance_between_points(unit_city_tile.pos, unit.pos)

            if (np.abs(cyclesToNight) <= distance and unit_city.fuel < unit_city.get_light_upkeep() * 10):
                move_dir = unit.pos.direction_to(unit_city_tile.pos)
                actions.append(unit.move(move_dir))

            else:

                if unit.get_cargo_space_left() > 0:
                    # closest_resource_tile = get_close_resource(unit, resource_tiles, player)

                    # if closest_resource_tile is not None:
                    #     actions.append(unit.move(unit.pos.direction_to(closest_resource_tile.pos)))

                    intended_resource = unit_to_resource_dict[unit.id]

                    cell = game_state.map.get_cell(intended_resource.pos.x, intended_resource.pos.y)

                    if cell.has_resource():
                        actions.append(unit.move(unit.pos.direction_to(intended_resource.pos)))

                    else:
                        intended_resource = get_close_resource(unit, resource_tiles, player)
                        unit_to_resource_dict[unit.id] = intended_resource
                        actions.append(unit.move(unit.pos.direction_to(intended_resource.pos)))



                else:
                    # if unit is a worker and there is no cargo space left, and we have cities, lets return to them

                    if(build_city):
                        logging.info(f"We want to build a city")

                        unit_city_fuel = unit_city.fuel
                        unit_city_size = len(unit_city.citytiles)

                        enough_fuel = (unit_city_fuel / unit_city_size) > 300

                        if enough_fuel:
                            if build_location is None:
                                empty_near = get_close_city(unit, player)
                                build_location = find_empty_tile_near(empty_near, game_state, observation)
                                
                                if(build_location == None):
                                    continue

                            if unit.pos == build_location.pos: 
                                action = unit.build_city()
                                actions.append(action)

                                build_city = False
                                build_location = None
                                continue

                            else:
                                logging.info(f"{observation['step']} : Navigate to where we want to build city")

                                # move_dir = unit.pos.direction_to(build_location.pos)
                                # actions.append(unit.move(move_dir))

                                dir_diff = (build_location.pos.x-unit.pos.x, build_location.pos.y-unit.pos.y)
                                xdiff = dir_diff[0]
                                ydiff = dir_diff[1]

                                # decrease in x? West
                                # increase in x? East
                                # decrease in y? North
                                # increase in y? South
                                
                                if abs(ydiff) > abs(xdiff):
                                    # if the move is greater in the y axis, then lets consider moving once in that dir
                                    check_tile = game_state.map.get_cell(unit.pos.x, unit.pos.y+np.sign(ydiff))
                                    if check_tile.citytile == None:
                                        if np.sign(ydiff) == 1:
                                            actions.append(unit.move("s"))
                                        else:
                                            actions.append(unit.move("n"))

                                    else:
                                        # there's a city tile, so we want to move in the other direction that we overall want to move
                                        if np.sign(xdiff) == 1:
                                            actions.append(unit.move("e"))
                                        else:
                                            actions.append(unit.move("w"))

                                else:
                                    # if the move is greater in the y axis, then lets consider moving once in that dir
                                    check_tile = game_state.map.get_cell(unit.pos.x+np.sign(xdiff), unit.pos.y)
                                    if check_tile.citytile == None:
                                        if np.sign(xdiff) == 1:
                                            actions.append(unit.move("e"))
                                        else:
                                            actions.append(unit.move("w"))

                                    else:
                                        # there's a city tile, so we want to move in the other direction that we overall want to move
                                        if np.sign(ydiff) == 1:
                                            actions.append(unit.move("s"))
                                        else:
                                            actions.append(unit.move("n"))


                                continue
                        
                        elif len(player.cities) > 0: 

                            if unit.id in unit_to_city_dict and unit_to_city_dict[unit.id] in city_tiles:
                                move_dir = unit.pos.direction_to(unit_to_city_dict[unit.id].pos)
                                actions.append(unit.move(move_dir))

                            else:
                                unit_to_city_dict[unit] = get_close_city(unit, player)
                                move_dir = unit.pos.direction_to(unit_to_city_dict[unit.id].pos)
                                actions.append(unit.move(move_dir))


                    elif len(player.cities) > 0:
                        # closest_city_tile = get_close_city(unit, player)
                        # if closest_city_tile is not None:
                        #     move_dir = unit.pos.direction_to(closest_city_tile.pos)
                        #     actions.append(unit.move(move_dir))

                        if unit.id in unit_to_city_dict and unit_to_city_dict[unit.id] in city_tiles:
                            move_dir = unit.pos.direction_to(unit_to_city_dict[unit.id].pos)
                            actions.append(unit.move(move_dir))

                        else:
                            unit_to_city_dict[unit] = get_close_city(unit, player)
                            move_dir = unit.pos.direction_to(unit_to_city_dict[unit.id].pos)
                            actions.append(unit.move(move_dir))


    # you can add debug annotations using the functions in the annotate object
    # actions.append(annotate.circle(0, 0))
    

    can_create_workers = len(city_tiles) - len(workers)

    if len(city_tiles) > 0:
        for city_tile in city_tiles:
            if city_tile.can_act():
                if(can_create_workers > 0):
                    actions.append(city_tile.build_worker())
                    can_create_workers -= 1
                else:
                    actions.append(city_tile.research())
                    
    if observation["step"] == 359:
        with open(statsfile,"a") as f:
            f.write(f"{len(city_tiles)}\n")
        
    return actions
