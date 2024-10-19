import datetime
import json
import osmnx as ox
import math
import click
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def km_to_lat(km, current_lat):
    """
    Calculate the new latitude based on a distance in kilometers.

    Parameters:
    km (float): Distance in kilometers to travel in latitude.
    current_lat (float): Current latitude.

    Returns:
    float: New latitude.
    """
    delta_lat = km / 111  # 1 degree latitude = 111 km
    return current_lat + delta_lat


def km_to_lon(km, current_lon, latitude):
    """
    Calculate the new longitude based on a distance in kilometers and latitude.

    Parameters:
    km (float): Distance in kilometers to travel in longitude.
    current_lon (float): Current longitude.
    latitude (float): The latitude at which the distance is being calculated.

    Returns:
    float: New longitude.
    """
    delta_lon = km / (111 * math.cos(math.radians(latitude)))
    return current_lon + delta_lon


def plot_roads(G, ax, road_styles):
    """
    Plot roads on the map.

    Parameters:
    G (networkx.MultiDiGraph): The graph representing the street network.
    ax (matplotlib.axes.Axes): The axes on which to plot.
    road_styles (dict): Styles for different road types.
    """
    for road_type, style in road_styles.items():
        roads = ox.graph_to_gdfs(G, nodes=False, edges=True)
        road_subset = roads[roads['highway'].apply(
            lambda x: road_type in x
            if isinstance(x, list) else road_type == x)]
        try:
            road_subset.plot(ax=ax,
                             edgecolor=style['color'],
                             linewidth=style['width'])
        except Exception as e:
            logging.error(f"Error plotting {road_type} roads: {e}")


def plot_park(ax, parks):
    """
    Plot parks on the map.

    Parameters:
    ax (matplotlib.axes.Axes): The axes on which to plot.
    parks (geopandas.GeoDataFrame): The GeoDataFrame containing park geometries.
    """
    if not parks.empty:
        parks.plot(ax=ax, facecolor="#98fb98", edgecolor="#98fb98")


def plot_water_bodies(ax, water):
    """
    Plot water bodies on the map.

    Parameters:
    ax (matplotlib.axes.Axes): The axes on which to plot.
    water (geopandas.GeoDataFrame): The GeoDataFrame containing water geometries.
    """
    water.plot(ax=ax, facecolor="#add8e6", edgecolor="#add8e6")


def plot_metro_lines(ax, metro_lines, metro_colors):
    """
    Plot metro lines on the map.

    Parameters:
    ax (matplotlib.axes.Axes): The axes on which to plot.
    metro_lines (geopandas.GeoDataFrame): The GeoDataFrame containing metro line geometries.
    metro_colors (dict): Colors for different metro lines.
    """
    for _, metro in metro_lines.iterrows():
        line_name = metro.get('name', 'Unnamed Line')
        if line_name not in metro_colors:
            logging.info(f"Unknown metro line: {line_name}")
            metro_colors[line_name] = "#FEC8D8"
        try:
            metro_lines[metro_lines['name'] == line_name].plot(
                ax=ax, color=metro_colors[line_name], linewidth=2)
        except Exception as e:
            logging.error(f"Error plotting metro line {line_name}: {e}")


def add_building_icon(ax,
                      icon_path,
                      building_location,
                      name,
                      zoom=0.05,
                      alpha=0.8):
    """
    Add a building icon to the map.

    Parameters:
    ax (matplotlib.axes.Axes): The axes on which to plot.
    icon_path (str): Path to the icon image.
    building_location (tuple): Coordinates of the building.
    name (str): Name of the building.
    zoom (float): Zoom level for the icon.
    alpha (float): Transparency level for the icon.
    """
    if icon_path:
        img = Image.open(icon_path)
        imagebox = OffsetImage(img, zoom=zoom, alpha=alpha)
        ab = AnnotationBbox(imagebox, building_location, frameon=False)
        ax.add_artist(ab)


@click.command()
@click.option('--output',
              type=str,
              default='out/map.png',
              help='Output file name (default: out/map.png)')
@click.option('--config',
              default='config.json',
              type=str,
              help='Configuration file in JSON format')
def generate_map(output, config):
    """
    Generate a map with specified parameters.

    Parameters:
    output (str): Output file name for the map image.
    config (str): Configuration file in JSON format.
    """
    # Calculate the limits based on the aspect ratio
    with open(config, 'r') as f:
        config_data = json.load(f)

    center_latitude = config_data['center_latitude']
    center_longitude = config_data['center_longitude']
    distance = config_data['distance']
    aspect_ratio = config_data['aspect_ratio']
    points_of_interest = config_data.get('points_of_interest', {})
    road_styles = config_data.get('road_styles', {})
    metro_colors = config_data.get('metro_colors', {})
    title = config_data.get('title', '')
    font_settings = config_data.get('font_settings', {})
    logging.info(
        f"Generating map for center: ({center_latitude}, {center_longitude}), distance: {distance} km"
    )
    if aspect_ratio >= 1:
        half_width = distance / 1000 * aspect_ratio / 2
        half_height = distance / 1000 / 2
    else:
        half_width = distance / 1000 / 2
        half_height = distance / 1000 / aspect_ratio / 2

    min_longitude = km_to_lon(-half_width, center_longitude, center_latitude)
    max_longitude = km_to_lon(half_width, center_longitude, center_latitude)
    min_latitude = km_to_lat(-half_height, center_latitude)
    max_latitude = km_to_lat(half_height, center_latitude)

    G = ox.graph_from_point((center_latitude, center_longitude),
                            dist=distance,
                            network_type='all')

    water = ox.geometries_from_point((center_latitude, center_longitude),
                                     dist=distance,
                                     tags={'natural': ['water']})

    metro_lines = ox.geometries_from_point((center_latitude, center_longitude),
                                           dist=distance,
                                           tags={'railway': ['subway']})

    fig, ax = plt.subplots(figsize=(10 * aspect_ratio, 10 / aspect_ratio))

    plot_roads(G, ax, road_styles)
    plot_water_bodies(ax, water)
    plot_metro_lines(ax, metro_lines, metro_colors)

    for poi in points_of_interest:
        building_location = poi['coords']
        add_building_icon(ax,
                          poi['icon'],
                          building_location,
                          poi['name'],
                          zoom=0.03,
                          alpha=1)

    ax.set_facecolor("white")
    ax.set_xlim(min_longitude, max_longitude)
    ax.set_ylim(min_latitude, max_latitude)
    ax.set_axis_off()

    current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    plt.savefig(f"{output}", dpi=600, bbox_inches="tight")


if __name__ == '__main__':
    generate_map()
