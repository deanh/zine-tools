#!/usr/bin/env python3

import click
import numpy as np
from PIL import Image
import sys
from pathlib import Path
import json
from sklearn.cluster import KMeans
from collections import Counter

def quantize_colors(image, n_colors):
    """Reduce image to n dominant colors using k-means clustering"""
    img_array = np.array(image)
    
    if len(img_array.shape) == 2:
        img_array = np.stack([img_array] * 3, axis=-1)
    
    pixels = img_array.reshape(-1, 3)
    
    # Sample pixels for faster processing on large images
    if len(pixels) > 10000:
        indices = np.random.choice(len(pixels), 10000, replace=False)
        sample_pixels = pixels[indices]
    else:
        sample_pixels = pixels
    
    # Find dominant colors
    kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=10)
    kmeans.fit(sample_pixels)
    
    # Assign all pixels to nearest cluster center
    labels = kmeans.predict(pixels)
    centers = kmeans.cluster_centers_.astype(int)
    
    # Count pixels per color for sorting by dominance
    color_counts = Counter(labels)
    sorted_indices = sorted(range(n_colors), key=lambda i: color_counts[i], reverse=True)
    
    # Rebuild image with quantized colors
    quantized_pixels = centers[labels]
    quantized_image = quantized_pixels.reshape(img_array.shape)
    
    # Return colors sorted by dominance
    dominant_colors = [tuple(centers[i]) for i in sorted_indices]
    
    return Image.fromarray(quantized_image.astype(np.uint8)), dominant_colors

def extract_unique_colors(image, max_colors=None):
    """Extract unique colors from an image with optional limit"""
    img_array = np.array(image)
    
    if len(img_array.shape) == 2:
        unique_colors = np.unique(img_array)
        unique_colors = [(c, c, c) for c in unique_colors]
    else:
        pixels = img_array.reshape(-1, img_array.shape[-1])
        unique_colors = np.unique(pixels, axis=0)
        unique_colors = [tuple(color) for color in unique_colors]
    
    if max_colors and len(unique_colors) > max_colors:
        click.echo(f"Warning: Found {len(unique_colors)} colors, reducing to {max_colors}", err=True)
        return None
    
    return unique_colors

def separate_colors(image, colors):
    """Separate image into grayscale layers for each color"""
    img_array = np.array(image)
    height, width = img_array.shape[:2]
    
    if len(img_array.shape) == 2:
        img_array = np.stack([img_array] * 3, axis=-1)
    
    layers = []
    
    for color in colors:
        layer = np.ones((height, width), dtype=np.uint8) * 255
        
        if len(color) == 1:
            color = (color[0], color[0], color[0])
        
        mask = np.all(img_array == color, axis=-1)
        layer[mask] = 0
        
        coverage = np.sum(mask) / (height * width) * 100
        layers.append((Image.fromarray(layer, mode='L'), coverage))
    
    return layers

def rgb_to_hex(rgb):
    """Convert RGB tuple to hex string"""
    return '#{:02x}{:02x}{:02x}'.format(*rgb)

def save_color_map(colors, output_dir, prefix):
    """Save color mapping information"""
    color_map = {
        "layers": [
            {
                "index": i + 1,
                "color": {
                    "rgb": [int(c) for c in color],  # Convert numpy types to int
                    "hex": rgb_to_hex(color)
                },
                "filename": f"{prefix}{i + 1}.png"
            }
            for i, color in enumerate(colors)
        ]
    }
    
    if output_dir:
        map_path = Path(output_dir) / f"{prefix}colormap.json"
    else:
        map_path = f"{prefix}colormap.json"
    
    with open(map_path, 'w') as f:
        json.dump(color_map, f, indent=2)
    
    return map_path

@click.command()
@click.option('-i', '--input', 'input_path', type=click.Path(exists=True), help='Input image path')
@click.option('-o', '--output', 'output_path', type=click.Path(), help='Output path (for single output)')
@click.option('--output-prefix', default='layer_', help='Prefix for output files')
@click.option('--output-format', type=click.Choice(['png', 'pdf']), default='png', help='Output format')
@click.option('--output-dir', type=click.Path(), help='Output directory')
@click.option('--max-colors', type=int, default=8, help='Maximum number of colors to separate (default: 8)')
@click.option('--quantize/--no-quantize', default=True, help='Automatically reduce colors if needed')
def main(input_path, output_path, output_prefix, output_format, output_dir, max_colors, quantize):
    """Separate an image into grayscale layers for each color"""
    
    if input_path:
        image = Image.open(input_path)
    else:
        image = Image.open(sys.stdin.buffer)
    
    if image.mode not in ['RGB', 'L']:
        image = image.convert('RGB')
    
    # Extract colors
    colors = extract_unique_colors(image, max_colors)
    
    if colors is None and quantize:
        # Too many colors, need to quantize
        image, colors = quantize_colors(image, max_colors)
        click.echo(f"Quantized to {len(colors)} colors", err=True)
    elif colors is None:
        click.echo(f"Error: Image has too many colors. Use --quantize or increase --max-colors", err=True)
        sys.exit(1)
    else:
        click.echo(f"Found {len(colors)} unique colors", err=True)
    
    # Separate into layers
    layers_with_coverage = separate_colors(image, colors)
    
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
    
    # Save color mapping
    colormap_path = save_color_map(colors, output_dir, output_prefix)
    click.echo(f"Saved color map: {colormap_path}", err=True)
    
    # Save layers
    saved_files = []
    
    for i, (layer, coverage) in enumerate(layers_with_coverage):
        color_hex = rgb_to_hex(colors[i])
        click.echo(f"Layer {i+1}: {color_hex} ({coverage:.1f}% coverage)", err=True)
        
        if output_format == 'pdf':
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A3
            import tempfile
            
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                layer.save(tmp.name, 'PNG')
                
                pdf_path = f"{output_prefix}{i + 1}.pdf"
                if output_dir:
                    pdf_path = output_dir / pdf_path
                
                c = canvas.Canvas(str(pdf_path), pagesize=A3)
                
                img_width, img_height = layer.size
                page_width, page_height = A3
                
                scale = min(page_width / img_width, page_height / img_height)
                scaled_width = img_width * scale
                scaled_height = img_height * scale
                
                x = (page_width - scaled_width) / 2
                y = (page_height - scaled_height) / 2
                
                c.drawImage(tmp.name, x, y, scaled_width, scaled_height)
                c.save()
                
                Path(tmp.name).unlink()
                saved_files.append(pdf_path)
        else:
            filename = f"{output_prefix}{i + 1}.{output_format}"
            if output_dir:
                filepath = output_dir / filename
            else:
                filepath = filename
            
            layer.save(filepath)
            saved_files.append(filepath)

if __name__ == '__main__':
    main()