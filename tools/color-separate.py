#!/usr/bin/env python3

import click
import numpy as np
from PIL import Image
import sys
from pathlib import Path
import json
from sklearn.cluster import KMeans
from collections import Counter
from scipy.optimize import nnls

def load_palette(palette_path):
    """Load Risograph colors from palette file"""
    colors = []
    color_names = []
    
    with open(palette_path, 'r') as f:
        lines = f.readlines()
        current_name = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('#') and len(line) == 7:
                # Check if this is actually a hex color (all chars after # are hex)
                try:
                    r = int(line[1:3], 16)
                    g = int(line[3:5], 16) 
                    b = int(line[5:7], 16)
                    colors.append([r, g, b])
                    color_names.append(current_name or line)
                    current_name = None  # Reset name after use
                except ValueError:
                    # This is a comment, not a color
                    current_name = line[1:].strip()
            elif line.startswith('#'):
                # This is a comment/color name
                current_name = line[1:].strip()
    
    return np.array(colors), color_names

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

def decompose_color(target_color, ink_colors, max_inks=3):
    """Decompose a target color into weighted ink densities using non-negative least squares"""
    # Normalize colors to 0-1 range
    target = np.array(target_color) / 255.0
    inks = ink_colors / 255.0
    
    # Add white (paper) as an implicit color that's always available
    inks_with_white = np.vstack([inks, [1.0, 1.0, 1.0]])
    
    # Try different combinations of inks (up to max_inks)
    best_weights = None
    best_error = float('inf')
    best_indices = None
    
    # Generate all possible combinations of inks
    from itertools import combinations
    n_inks = len(inks)
    
    for r in range(1, min(max_inks + 1, n_inks + 1)):
        for ink_indices in combinations(range(n_inks), r):
            # Create matrix of selected ink colors
            selected_inks = inks[list(ink_indices)]
            
            # Solve for weights using multiplicative color mixing model
            # For Risograph, we use subtractive color mixing
            # Each ink absorbs certain wavelengths, so we work in CMY space
            
            # Convert RGB to CMY (approximate)
            target_cmy = 1.0 - target
            inks_cmy = 1.0 - selected_inks
            
            # Solve for densities that minimize error
            # We want: sum(density_i * ink_i) = target (in CMY space)
            densities, residual = nnls(inks_cmy.T, target_cmy, maxiter=1000)
            
            # Ensure densities sum to <= 1 (can't have more than 100% coverage)
            if densities.sum() > 1.0:
                densities = densities / densities.sum()
            
            # Calculate reconstruction error
            reconstructed_cmy = np.dot(densities, inks_cmy)
            reconstructed_rgb = 1.0 - reconstructed_cmy
            error = np.linalg.norm(reconstructed_rgb - target)
            
            if error < best_error:
                best_error = error
                best_weights = np.zeros(n_inks)
                best_weights[list(ink_indices)] = densities
                best_indices = ink_indices
    
    return best_weights, best_error

def separate_colors(image, colors):
    """Separate image into grayscale layers for each color (binary mode)"""
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

def separate_colors_weighted(image, ink_colors, ink_names, max_inks=3):
    """Separate image into weighted grayscale layers for each ink color"""
    img_array = np.array(image)
    height, width = img_array.shape[:2]
    
    if len(img_array.shape) == 2:
        img_array = np.stack([img_array] * 3, axis=-1)
    
    # Initialize layers for each ink
    n_inks = len(ink_colors)
    layers = [np.zeros((height, width), dtype=np.float32) for _ in range(n_inks)]
    
    # Process each unique color in the image
    unique_colors = extract_unique_colors(Image.fromarray(img_array))
    
    click.echo(f"Decomposing {len(unique_colors)} colors into {n_inks} ink layers...", err=True)
    
    # Create a mapping from colors to ink weights
    color_to_weights = {}
    for color in unique_colors:
        weights, error = decompose_color(color, ink_colors, max_inks)
        color_to_weights[color] = weights
        
        # Report decomposition for debugging
        active_inks = [(ink_names[i], weights[i]) for i in range(n_inks) if weights[i] > 0.01]
        if active_inks:
            ink_str = ", ".join([f"{name}: {w:.1%}" for name, w in active_inks])
            click.echo(f"  RGB{color} → {ink_str} (error: {error:.3f})", err=True)
    
    # Apply weights to create density layers
    for y in range(height):
        for x in range(width):
            pixel_color = tuple(img_array[y, x])
            if pixel_color in color_to_weights:
                weights = color_to_weights[pixel_color]
                for i, weight in enumerate(weights):
                    layers[i][y, x] = weight
    
    # Convert to grayscale images (0-255 range where 0=no ink, 255=full ink)
    layer_images = []
    for i, layer in enumerate(layers):
        # Invert: in printing, darker = more ink
        grayscale = (layer * 255).astype(np.uint8)
        coverage = np.mean(layer) * 100
        layer_images.append((Image.fromarray(grayscale, mode='L'), coverage))
    
    return layer_images

def rgb_to_hex(rgb):
    """Convert RGB tuple to hex string"""
    if isinstance(rgb, (list, np.ndarray)):
        rgb = tuple(int(c) for c in rgb)
    return '#{:02x}{:02x}{:02x}'.format(*rgb)

def save_color_map(ink_colors, ink_names, output_dir, prefix):
    """Save ink color mapping information"""
    color_map = {
        "layers": [
            {
                "index": i + 1,
                "ink_name": ink_names[i] if i < len(ink_names) else f"Ink {i+1}",
                "color": {
                    "rgb": [int(c) for c in ink_colors[i]],
                    "hex": rgb_to_hex(ink_colors[i])
                },
                "filename": f"{prefix}{i + 1}.png"
            }
            for i in range(len(ink_colors))
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
@click.option('--palette', type=click.Path(exists=True), help='Risograph color palette file')
@click.option('--max-inks', type=int, default=3, help='Maximum number of inks to mix per color (default: 3)')
@click.option('--mode', type=click.Choice(['binary', 'weighted']), default='weighted', help='Separation mode: binary (exact match) or weighted (overlapping inks)')
def main(input_path, output_path, output_prefix, output_format, output_dir, max_colors, quantize, palette, max_inks, mode):
    """Separate an image into grayscale layers for each color"""
    
    if input_path:
        image = Image.open(input_path)
    else:
        image = Image.open(sys.stdin.buffer)
    
    if image.mode not in ['RGB', 'L']:
        image = image.convert('RGB')
    
    # Load palette if specified and using weighted mode
    if mode == 'weighted' and palette:
        ink_colors, ink_names = load_palette(palette)
        click.echo(f"Loaded {len(ink_colors)} ink colors from palette", err=True)
    elif mode == 'weighted':
        click.echo("Error: Weighted mode requires a palette file (--palette)", err=True)
        sys.exit(1)
    
    if mode == 'binary':
        # Original binary separation mode
        colors = extract_unique_colors(image, max_colors)
        
        if colors is None and quantize:
            image, colors = quantize_colors(image, max_colors)
            click.echo(f"Quantized to {len(colors)} colors", err=True)
        elif colors is None:
            click.echo(f"Error: Image has too many colors. Use --quantize or increase --max-colors", err=True)
            sys.exit(1)
        else:
            click.echo(f"Found {len(colors)} unique colors", err=True)
        
        layers_with_coverage = separate_colors(image, colors)
        
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(exist_ok=True)
        
        colormap_path = save_color_map(colors, [rgb_to_hex(c) for c in colors], output_dir, output_prefix)
    else:
        # Weighted separation mode with overlaps
        # First, optionally quantize the image if it has too many colors
        unique_colors = extract_unique_colors(image)
        if len(unique_colors) > max_colors and quantize:
            image, _ = quantize_colors(image, max_colors)
            click.echo(f"Quantized image to {max_colors} colors", err=True)
        
        layers_with_coverage = separate_colors_weighted(image, ink_colors, ink_names, max_inks)
        
        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(exist_ok=True)
        
        colormap_path = save_color_map(ink_colors, ink_names, output_dir, output_prefix)
    
    click.echo(f"Saved color map: {colormap_path}", err=True)
    
    # Save layers
    saved_files = []
    
    for i, (layer, coverage) in enumerate(layers_with_coverage):
        if mode == 'binary':
            color_hex = rgb_to_hex(colors[i])
            click.echo(f"Layer {i+1}: {color_hex} ({coverage:.1f}% coverage)", err=True)
        else:
            ink_name = ink_names[i] if i < len(ink_names) else f"Ink {i+1}"
            click.echo(f"Layer {i+1}: {ink_name} ({coverage:.1f}% average density)", err=True)
        
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