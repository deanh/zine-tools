#!/usr/bin/env python3

import click
import numpy as np
from PIL import Image
import sys
from pathlib import Path

# Import Cython functions
try:
    from dither_cython import floyd_steinberg_cython, atkinson_cython
    CYTHON_AVAILABLE = True
except ImportError:
    CYTHON_AVAILABLE = False
    print("Warning: Cython module not available, using slower Python implementation", file=sys.stderr)

def floyd_steinberg_python(image, palette):
    """Python fallback for Floyd-Steinberg dithering"""
    img_array = np.array(image, dtype=np.float64)
    height, width = img_array.shape[:2]
    
    if len(img_array.shape) == 2:
        img_array = np.stack([img_array] * 3, axis=-1)
    
    palette = np.array(palette, dtype=np.float64)
    
    for y in range(height):
        for x in range(width):
            old_pixel = img_array[y, x]
            
            # Vectorized nearest color search
            distances = np.sum((palette - old_pixel) ** 2, axis=1)
            nearest_idx = np.argmin(distances)
            new_pixel = palette[nearest_idx]
            
            img_array[y, x] = new_pixel
            error = old_pixel - new_pixel
            
            if x + 1 < width:
                img_array[y, x + 1] += error * 7 / 16
            if y + 1 < height:
                if x > 0:
                    img_array[y + 1, x - 1] += error * 3 / 16
                img_array[y + 1, x] += error * 5 / 16
                if x + 1 < width:
                    img_array[y + 1, x + 1] += error * 1 / 16
    
    return Image.fromarray(np.clip(img_array, 0, 255).astype(np.uint8))

def floyd_steinberg(image, palette):
    """Floyd-Steinberg dithering using Cython if available"""
    if CYTHON_AVAILABLE:
        img_array = np.array(image, dtype=np.uint8)
        if len(img_array.shape) == 2:
            img_array = np.stack([img_array] * 3, axis=-1)
        
        palette_array = np.array(palette, dtype=np.uint8)
        result = floyd_steinberg_cython(img_array, palette_array)
        return Image.fromarray(result)
    else:
        return floyd_steinberg_python(image, palette)

def atkinson_python(image, palette):
    """Python fallback for Atkinson dithering"""
    img_array = np.array(image, dtype=np.float64)
    height, width = img_array.shape[:2]
    
    if len(img_array.shape) == 2:
        img_array = np.stack([img_array] * 3, axis=-1)
    
    palette = np.array(palette, dtype=np.float64)
    
    for y in range(height):
        for x in range(width):
            old_pixel = img_array[y, x]
            
            distances = np.sum((palette - old_pixel) ** 2, axis=1)
            nearest_idx = np.argmin(distances)
            new_pixel = palette[nearest_idx]
            
            img_array[y, x] = new_pixel
            error = (old_pixel - new_pixel) / 8
            
            if x + 1 < width:
                img_array[y, x + 1] += error
            if x + 2 < width:
                img_array[y, x + 2] += error
            if y + 1 < height:
                if x > 0:
                    img_array[y + 1, x - 1] += error
                img_array[y + 1, x] += error
                if x + 1 < width:
                    img_array[y + 1, x + 1] += error
            if y + 2 < height:
                img_array[y + 2, x] += error
    
    return Image.fromarray(np.clip(img_array, 0, 255).astype(np.uint8))

def atkinson(image, palette):
    """Atkinson dithering using Cython if available"""
    if CYTHON_AVAILABLE:
        img_array = np.array(image, dtype=np.uint8)
        if len(img_array.shape) == 2:
            img_array = np.stack([img_array] * 3, axis=-1)
        
        palette_array = np.array(palette, dtype=np.uint8)
        result = atkinson_cython(img_array, palette_array)
        return Image.fromarray(result)
    else:
        return atkinson_python(image, palette)

def ordered_dither(image, palette, pattern_size=4):
    """Ordered (Bayer) dithering - already reasonably fast"""
    patterns = {
        2: np.array([[0, 2], [3, 1]]) / 4,
        4: np.array([[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]) / 16,
        8: np.array([
            [0, 32, 8, 40, 2, 34, 10, 42],
            [48, 16, 56, 24, 50, 18, 58, 26],
            [12, 44, 4, 36, 14, 46, 6, 38],
            [60, 28, 52, 20, 62, 30, 54, 22],
            [3, 35, 11, 43, 1, 33, 9, 41],
            [51, 19, 59, 27, 49, 17, 57, 25],
            [15, 47, 7, 39, 13, 45, 5, 37],
            [63, 31, 55, 23, 61, 29, 53, 21]
        ]) / 64
    }
    
    pattern = patterns.get(pattern_size, patterns[4])
    img_array = np.array(image)
    height, width = img_array.shape[:2]
    
    if len(img_array.shape) == 2:
        img_array = np.stack([img_array] * 3, axis=-1)
    
    # Create threshold map
    threshold = np.tile(pattern, (height // pattern_size + 1, width // pattern_size + 1))
    threshold = threshold[:height, :width] * 255
    
    # Apply threshold
    img_thresh = img_array + threshold[:, :, np.newaxis] - 128
    
    # Vectorized color matching
    result = np.zeros_like(img_array)
    palette_array = np.array(palette)
    
    for y in range(height):
        row_pixels = img_thresh[y]
        distances = np.sum((row_pixels[:, np.newaxis, :] - palette_array[np.newaxis, :, :]) ** 2, axis=2)
        nearest_indices = np.argmin(distances, axis=1)
        result[y] = palette_array[nearest_indices]
    
    return Image.fromarray(result.astype(np.uint8))

def parse_palette(palette_str):
    """Parse palette from hex string or file"""
    colors = []
    
    if Path(palette_str).exists():
        with open(palette_str, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith('#'):
                    continue
                if line and line.startswith('#') and len(line) >= 7:
                    # Check if it's a hex color (not a comment)
                    if all(c in '0123456789ABCDEFabcdef' for c in line[1:7]):
                        colors.append(hex_to_rgb(line))
    else:
        for color in palette_str.split(','):
            color = color.strip()
            if color.startswith('#'):
                colors.append(hex_to_rgb(color))
    
    return colors

def hex_to_rgb(hex_color):
    """Convert hex color to RGB"""
    hex_color = hex_color.lstrip('#')
    return [int(hex_color[i:i+2], 16) for i in (0, 2, 4)]

def load_preset_palette(preset_name):
    """Load a preset palette"""
    presets = {
        'riso-pink-blue': ['#FF0080', '#0078BF'],
        'riso-fluoro': ['#FF48B0', '#FFE800', '#00A95C'],
        'riso-primary': ['#FF0000', '#0000FF', '#FFFF00'],
        'riso-warm': ['#FF6600', '#FFE800', '#FF0080'],
        'riso-cool': ['#0078BF', '#00A95C', '#5C55A6'],
    }
    
    if preset_name in presets:
        return [hex_to_rgb(color) for color in presets[preset_name]]
    else:
        raise ValueError(f"Unknown preset: {preset_name}")

@click.command()
@click.option('-i', '--input', 'input_path', type=click.Path(exists=True), help='Input image path')
@click.option('-o', '--output', 'output_path', type=click.Path(), help='Output image path')
@click.option('--palette', required=True, help='Palette as hex colors, file path, or preset name')
@click.option('--algorithm', type=click.Choice(['floyd-steinberg', 'atkinson', 'ordered-2x2', 'ordered-4x4', 'ordered-8x8']), 
              default='floyd-steinberg', help='Dithering algorithm')
def main(input_path, output_path, palette, algorithm):
    """Fast dithering tool with Cython optimization"""
    
    if palette in ['riso-pink-blue', 'riso-fluoro', 'riso-primary', 'riso-warm', 'riso-cool']:
        palette_colors = load_preset_palette(palette)
    else:
        palette_colors = parse_palette(palette)
    
    if input_path:
        image = Image.open(input_path).convert('RGB')
    else:
        image = Image.open(sys.stdin.buffer).convert('RGB')
    
    if algorithm == 'floyd-steinberg':
        result = floyd_steinberg(image, palette_colors)
    elif algorithm == 'atkinson':
        result = atkinson(image, palette_colors)
    elif algorithm.startswith('ordered'):
        size = int(algorithm.split('-')[1].split('x')[0])
        result = ordered_dither(image, palette_colors, size)
    
    if output_path:
        result.save(output_path)
    else:
        result.save(sys.stdout.buffer, format='PNG')

if __name__ == '__main__':
    main()