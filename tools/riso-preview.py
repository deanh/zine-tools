#!/usr/bin/env python3

import click
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from pathlib import Path
import json
import sys

def load_color_map(directory):
    """Load color mapping from directory"""
    colormap_files = list(Path(directory).glob('*colormap.json'))
    
    if not colormap_files:
        return None
    
    with open(colormap_files[0], 'r') as f:
        return json.load(f)

def blend_layers(layers, colors, opacity=0.8):
    """Blend multiple grayscale layers with colors"""
    if not layers:
        return None
    
    # Get dimensions from first layer
    width, height = layers[0].size
    
    # Create white background
    result = Image.new('RGB', (width, height), (255, 255, 255))
    result_array = np.array(result, dtype=float)
    
    for layer, color in zip(layers, colors):
        # Convert grayscale to numpy array
        layer_array = np.array(layer)
        
        # Create colored version (0 = full color, 255 = white)
        colored = np.zeros((height, width, 3), dtype=float)
        
        # Apply color where layer is dark
        intensity = 1.0 - (layer_array / 255.0)
        
        for i in range(3):
            # Blend color with white based on intensity
            colored[:, :, i] = (1 - intensity) * 255 + intensity * color[i]
        
        # Blend with result using multiply mode (simulates overprinting)
        result_array = result_array * (colored / 255.0)
    
    # Convert back to 0-255 range
    result_array = (result_array * 255).clip(0, 255).astype(np.uint8)
    
    return Image.fromarray(result_array)

def create_color_swatches(colors, swatch_size=50):
    """Create a row of color swatches"""
    width = swatch_size * len(colors)
    height = swatch_size
    
    swatches = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(swatches)
    
    for i, color in enumerate(colors):
        x = i * swatch_size
        draw.rectangle([x, 0, x + swatch_size - 1, swatch_size - 1], 
                      fill=tuple(color), outline=(0, 0, 0))
    
    return swatches

def add_labels(image, labels, position='bottom'):
    """Add text labels to image"""
    # Create new image with space for labels
    width, height = image.size
    label_height = 100
    
    if position == 'bottom':
        new_image = Image.new('RGB', (width, height + label_height), (255, 255, 255))
        new_image.paste(image, (0, 0))
        text_y = height + 20
    else:
        new_image = Image.new('RGB', (width, height), (255, 255, 255))
        new_image.paste(image, (0, 0))
        text_y = 20
    
    draw = ImageDraw.Draw(new_image)
    
    # Try to use a nice font, fall back to default if not available
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except:
        font = ImageFont.load_default()
    
    # Add labels
    text = " + ".join(labels)
    draw.text((20, text_y), text, fill=(0, 0, 0), font=font)
    
    return new_image

@click.command()
@click.option('--layers', '-l', multiple=True, type=click.Path(exists=True), 
              help='Layer image files (can specify multiple)')
@click.option('--directory', '-d', type=click.Path(exists=True), 
              help='Directory containing layers and colormap')
@click.option('--colors', '-c', help='Colors as hex values (comma-separated)')
@click.option('-o', '--output', 'output_path', type=click.Path(), help='Output image path')
@click.option('--swatches/--no-swatches', default=True, help='Include color swatches')
@click.option('--labels/--no-labels', default=True, help='Include color labels')
@click.option('--opacity', type=float, default=0.8, help='Layer opacity (0-1)')
def main(layers, directory, colors, output_path, swatches, labels, opacity):
    """Create a preview by overlaying separated color layers"""
    
    layer_images = []
    layer_colors = []
    color_labels = []
    
    if directory:
        # Load from directory with colormap
        colormap = load_color_map(directory)
        
        if colormap:
            for layer_info in colormap['layers']:
                layer_path = Path(directory) / layer_info['filename']
                if layer_path.exists():
                    layer_images.append(Image.open(layer_path).convert('L'))
                    rgb = layer_info['color']['rgb']
                    layer_colors.append(rgb)
                    color_labels.append(layer_info['color']['hex'])
        else:
            # No colormap, load all grayscale images
            for img_path in sorted(Path(directory).glob('*.png')):
                if 'preview' not in img_path.name:
                    layer_images.append(Image.open(img_path).convert('L'))
    
    elif layers:
        # Load specified layer files
        for layer_path in layers:
            layer_images.append(Image.open(layer_path).convert('L'))
    
    else:
        click.echo("Error: Specify either --directory or --layers", err=True)
        sys.exit(1)
    
    if not layer_images:
        click.echo("Error: No layer images found", err=True)
        sys.exit(1)
    
    # Parse colors if provided
    if colors and not layer_colors:
        for color in colors.split(','):
            color = color.strip().lstrip('#')
            rgb = [int(color[i:i+2], 16) for i in (0, 2, 4)]
            layer_colors.append(rgb)
            color_labels.append(f"#{color}")
    
    # Use default colors if none specified
    if not layer_colors:
        default_colors = [
            [255, 0, 128],    # Riso pink
            [0, 120, 191],    # Riso blue
            [255, 232, 0],    # Riso yellow
            [0, 169, 92],     # Riso green
        ]
        layer_colors = default_colors[:len(layer_images)]
        color_labels = [f"Layer {i+1}" for i in range(len(layer_images))]
    
    # Ensure we have enough colors
    while len(layer_colors) < len(layer_images):
        # Generate a random color for extra layers
        layer_colors.append([np.random.randint(0, 256) for _ in range(3)])
        color_labels.append(f"Layer {len(layer_colors)}")
    
    # Create blended preview
    preview = blend_layers(layer_images, layer_colors, opacity)
    
    if not preview:
        click.echo("Error: Could not create preview", err=True)
        sys.exit(1)
    
    # Add swatches if requested
    if swatches:
        swatch_strip = create_color_swatches(layer_colors[:len(layer_images)])
        
        # Combine preview and swatches
        combined_width = max(preview.width, swatch_strip.width)
        combined_height = preview.height + swatch_strip.height + 20
        
        combined = Image.new('RGB', (combined_width, combined_height), (255, 255, 255))
        combined.paste(preview, ((combined_width - preview.width) // 2, 0))
        combined.paste(swatch_strip, ((combined_width - swatch_strip.width) // 2, preview.height + 20))
        
        preview = combined
    
    # Add labels if requested
    if labels and color_labels:
        preview = add_labels(preview, color_labels[:len(layer_images)])
    
    # Save or output
    if output_path:
        preview.save(output_path)
        click.echo(f"Created preview: {output_path}", err=True)
    else:
        preview.save(sys.stdout.buffer, format='PNG')

if __name__ == '__main__':
    main()