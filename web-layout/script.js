let uploadedImages = [];
let pageImages = {};
let selectedImage = null;
let draggedImage = null;
let imageIdCounter = 0;
let availablePalettes = {};

// Initialize event listeners
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('imageUpload').addEventListener('change', handleImageUpload);
    document.getElementById('generatePDF').addEventListener('click', generatePDF);
    document.getElementById('paperSize').addEventListener('change', updatePageSizes);
    document.getElementById('orientation').addEventListener('change', updatePageSizes);
    
    // Dithering controls
    const ditherToggle = document.getElementById('ditherToggle');
    ditherToggle.addEventListener('change', function() {
        const ditherOptions = document.querySelectorAll('.dither-options');
        ditherOptions.forEach(option => {
            option.style.display = this.checked ? 'flex' : 'none';
        });
        if (this.checked) {
            updatePaletteVisibility();
        }
        applyDitheringToAll();
    });
    
    document.getElementById('colorMode').addEventListener('change', function() {
        updatePaletteVisibility();
        applyDitheringToAll();
    });
    document.getElementById('ditherMethod').addEventListener('change', applyDitheringToAll);
    document.getElementById('paletteSelect').addEventListener('change', applyDitheringToAll);
    
    // Add click outside to deselect
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.page-image')) {
            deselectAllImages();
        }
    });
    
    // Initialize page sizes
    updatePageSizes();
    
    // Load available palettes
    loadPalettes();
});

function handleImageUpload(e) {
    const files = Array.from(e.target.files);
    const imageList = document.getElementById('imageList');
    
    console.log('Files selected:', files.length);
    
    files.forEach(file => {
        console.log('Processing file:', file.name, file.type);
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = function(event) {
                const img = document.createElement('img');
                img.src = event.target.result;
                img.className = 'library-image';
                img.draggable = true;
                img.dataset.imageId = imageIdCounter++;
                
                img.addEventListener('dragstart', function(e) {
                    draggedImage = {
                        src: img.src,
                        id: img.dataset.imageId
                    };
                    e.dataTransfer.effectAllowed = 'copy';
                });
                
                imageList.appendChild(img);
                uploadedImages.push({
                    id: img.dataset.imageId,
                    src: event.target.result,
                    name: file.name
                });
                console.log('Image added to library:', file.name);
            };
            reader.onerror = function(error) {
                console.error('Error reading file:', error);
            };
            reader.readAsDataURL(file);
        }
    });
}

function allowDrop(e) {
    e.preventDefault();
}

function drop(e) {
    e.preventDefault();
    
    if (!draggedImage) return;
    
    const pageContent = e.target.closest('.page-content');
    if (!pageContent) return;
    
    const page = pageContent.closest('.page');
    const pageNum = page.dataset.page;
    const rect = pageContent.getBoundingClientRect();
    
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    addImageToPage(pageNum, draggedImage.src, x, y);
    draggedImage = null;
}

function addImageToPage(pageNum, src, x, y) {
    const pageContent = document.querySelector(`.page[data-page="${pageNum}"] .page-content`);
    
    const imgContainer = document.createElement('div');
    imgContainer.className = 'page-image';
    imgContainer.style.position = 'absolute';
    imgContainer.style.left = x + 'px';
    imgContainer.style.top = y + 'px';
    imgContainer.dataset.imageId = imageIdCounter++;
    imgContainer.dataset.rotation = '0';
    
    const img = document.createElement('img');
    img.src = src;
    img.style.width = '100px';
    img.style.height = 'auto';
    img.style.display = 'block';
    
    imgContainer.appendChild(img);
    
    // Apply dithering if enabled
    if (document.getElementById('ditherToggle').checked) {
        applyDithering(img, src);
    }
    
    // Add resize handles
    ['nw', 'ne', 'sw', 'se'].forEach(pos => {
        const handle = document.createElement('div');
        handle.className = `resize-handle ${pos}`;
        handle.style.display = 'none';
        imgContainer.appendChild(handle);
    });
    
    // Add rotate handle
    const rotateHandle = document.createElement('div');
    rotateHandle.className = 'rotate-handle';
    imgContainer.appendChild(rotateHandle);
    
    // Add control buttons
    const controls = document.createElement('div');
    controls.className = 'image-controls';
    controls.innerHTML = `
        <button class="control-btn" onclick="rotateImage('${imgContainer.dataset.imageId}', -90)">↺ 90°</button>
        <button class="control-btn" onclick="rotateImage('${imgContainer.dataset.imageId}', 90)">↻ 90°</button>
        <button class="control-btn" onclick="flipImage('${imgContainer.dataset.imageId}', 'h')">↔ Flip</button>
        <button class="control-btn remove-btn" onclick="removeImage('${imgContainer.dataset.imageId}')">✕ Remove</button>
    `;
    imgContainer.appendChild(controls);
    
    // Make draggable within page
    makeDraggable(imgContainer);
    makeResizable(imgContainer);
    makeRotatable(imgContainer);
    
    imgContainer.addEventListener('click', function(e) {
        e.stopPropagation();
        selectImage(imgContainer);
    });
    
    pageContent.appendChild(imgContainer);
    
    // Store image data
    if (!pageImages[pageNum]) {
        pageImages[pageNum] = [];
    }
    
    // Store the image data - will be dithered if dithering is applied
    const imageEntry = {
        id: imgContainer.dataset.imageId,
        src: src,  // This will be updated if dithering is applied
        originalSrc: src,  // Keep original for toggling dithering
        x: x,
        y: y,
        width: 100,
        height: 'auto',
        rotation: 0,
        scaleX: 1
    };
    
    pageImages[pageNum].push(imageEntry);
    
    // Update stored src if dithering is applied
    if (document.getElementById('ditherToggle').checked) {
        setTimeout(() => {
            // Get the dithered image src after it's been processed
            imageEntry.src = img.src;
        }, 100);
    }
    
    updatePreview();
}

function makeDraggable(element) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    
    element.onmousedown = dragMouseDown;
    
    function dragMouseDown(e) {
        if (e.target.classList.contains('resize-handle')) return;
        
        e = e || window.event;
        e.preventDefault();
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.onmouseup = closeDragElement;
        document.onmousemove = elementDrag;
    }
    
    function elementDrag(e) {
        e = e || window.event;
        e.preventDefault();
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;
        
        const newTop = element.offsetTop - pos2;
        const newLeft = element.offsetLeft - pos1;
        
        // Get page and image dimensions
        const parent = element.parentElement;
        const parentWidth = parent.offsetWidth;
        const parentHeight = parent.offsetHeight;
        const elementWidth = element.offsetWidth;
        const elementHeight = element.offsetHeight;
        
        // For oversized images, remove most constraints to allow free positioning
        // Keep a small margin so image doesn't get completely lost
        const margin = 20; // Minimum pixels that must remain visible
        
        // Calculate bounds - these are more permissive for large images
        let minX = -elementWidth + margin;
        let maxX = parentWidth - margin;
        let minY = -elementHeight + margin;
        let maxY = parentHeight - margin;
        
        // Only constrain small images to stay within the page
        if (elementWidth <= parentWidth) {
            minX = 0;
            maxX = parentWidth - elementWidth;
        }
        
        if (elementHeight <= parentHeight) {
            minY = 0;
            maxY = parentHeight - elementHeight;
        }
        
        // Apply the new position
        element.style.left = Math.max(minX, Math.min(newLeft, maxX)) + "px";
        element.style.top = Math.max(minY, Math.min(newTop, maxY)) + "px";
    }
    
    function closeDragElement() {
        document.onmouseup = null;
        document.onmousemove = null;
        updateImagePosition(element);
    }
}

function makeResizable(element) {
    const handles = element.querySelectorAll('.resize-handle');
    
    handles.forEach(handle => {
        handle.onmousedown = initResize;
    });
    
    function initResize(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const handle = e.target;
        const handleClass = handle.className;
        const startX = e.clientX;
        const startY = e.clientY;
        const img = element.querySelector('img');
        const startWidth = parseInt(document.defaultView.getComputedStyle(img).width, 10);
        const startHeight = parseInt(document.defaultView.getComputedStyle(img).height, 10);
        const aspectRatio = startHeight / startWidth;
        
        document.onmousemove = doResize;
        document.onmouseup = stopResize;
        
        function doResize(e) {
            let newWidth = startWidth;
            let newHeight = startHeight;
            
            const deltaX = e.clientX - startX;
            const deltaY = e.clientY - startY;
            
            // Determine resize direction based on handle
            if (handleClass.includes('se')) {
                newWidth = startWidth + deltaX;
            } else if (handleClass.includes('sw')) {
                newWidth = startWidth - deltaX;
            } else if (handleClass.includes('ne')) {
                newWidth = startWidth + deltaX;
            } else if (handleClass.includes('nw')) {
                newWidth = startWidth - deltaX;
            }
            
            // Maintain aspect ratio
            newHeight = newWidth * aspectRatio;
            
            if (newWidth > 20 && newHeight > 20) {
                img.style.width = newWidth + 'px';
                img.style.height = newHeight + 'px';
            }
        }
        
        function stopResize() {
            document.onmousemove = null;
            document.onmouseup = null;
            updateImagePosition(element);
        }
    }
}

function makeRotatable(element) {
    const rotateHandle = element.querySelector('.rotate-handle');
    if (!rotateHandle) return;
    
    rotateHandle.onmousedown = initRotate;
    
    function initRotate(e) {
        e.preventDefault();
        e.stopPropagation();
        
        const rect = element.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        const startAngle = Math.atan2(e.clientY - centerY, e.clientX - centerX) * 180 / Math.PI;
        const currentRotation = parseFloat(element.dataset.rotation) || 0;
        
        document.onmousemove = doRotate;
        document.onmouseup = stopRotate;
        
        function doRotate(e) {
            const angle = Math.atan2(e.clientY - centerY, e.clientX - centerX) * 180 / Math.PI;
            const rotation = currentRotation + (angle - startAngle);
            
            element.style.transform = `rotate(${rotation}deg)`;
            element.dataset.rotation = rotation;
        }
        
        function stopRotate() {
            document.onmousemove = null;
            document.onmouseup = null;
            updateImagePosition(element);
        }
    }
}

function selectImage(imgContainer) {
    deselectAllImages();
    imgContainer.classList.add('selected');
    imgContainer.querySelectorAll('.resize-handle').forEach(handle => {
        handle.style.display = 'block';
    });
    selectedImage = imgContainer;
}

function deselectAllImages() {
    document.querySelectorAll('.page-image').forEach(img => {
        img.classList.remove('selected');
        img.querySelectorAll('.resize-handle').forEach(handle => {
            handle.style.display = 'none';
        });
    });
    selectedImage = null;
}

function updateImagePosition(imgContainer) {
    const page = imgContainer.closest('.page');
    const pageNum = page.dataset.page;
    const imageId = imgContainer.dataset.imageId;
    
    if (pageImages[pageNum]) {
        const imageData = pageImages[pageNum].find(img => img.id === imageId);
        if (imageData) {
            const img = imgContainer.querySelector('img');
            imageData.x = parseInt(imgContainer.style.left);
            imageData.y = parseInt(imgContainer.style.top);
            imageData.width = parseInt(img.style.width);
            imageData.height = parseInt(img.style.height) || 'auto';
            imageData.rotation = parseFloat(imgContainer.dataset.rotation) || 0;
            imageData.scaleX = parseFloat(imgContainer.dataset.scaleX) || 1;
        }
    }
    
    updatePreview();
}

function rotateImage(imageId, degrees) {
    const imgContainer = document.querySelector(`[data-image-id="${imageId}"]`);
    if (!imgContainer) return;
    
    const currentRotation = parseFloat(imgContainer.dataset.rotation) || 0;
    const newRotation = currentRotation + degrees;
    
    imgContainer.style.transform = `rotate(${newRotation}deg) scaleX(${imgContainer.dataset.scaleX || 1})`;
    imgContainer.dataset.rotation = newRotation;
    
    updateImagePosition(imgContainer);
}

function flipImage(imageId, direction) {
    const imgContainer = document.querySelector(`[data-image-id="${imageId}"]`);
    if (!imgContainer) return;
    
    const currentScaleX = parseFloat(imgContainer.dataset.scaleX) || 1;
    const newScaleX = currentScaleX * -1;
    const rotation = parseFloat(imgContainer.dataset.rotation) || 0;
    
    imgContainer.style.transform = `rotate(${rotation}deg) scaleX(${newScaleX})`;
    imgContainer.dataset.scaleX = newScaleX;
    
    updateImagePosition(imgContainer);
}

function removeImage(imageId) {
    const imgContainer = document.querySelector(`[data-image-id="${imageId}"]`);
    if (!imgContainer) return;
    
    const page = imgContainer.closest('.page');
    const pageNum = page.dataset.page;
    
    // Remove from data
    if (pageImages[pageNum]) {
        pageImages[pageNum] = pageImages[pageNum].filter(img => img.id !== imageId);
    }
    
    // Remove from DOM
    imgContainer.remove();
    
    // Clear selection if this was selected
    if (selectedImage === imgContainer) {
        selectedImage = null;
    }
    
    updatePreview();
}

function updatePreview() {
    // Update the preview to show which images will appear on which printed pages
    // This is a simplified preview - the actual PDF generation will handle the proper imposition
    const previewPages = document.querySelectorAll('.preview-page');
    
    previewPages.forEach(preview => {
        const pageNum = preview.dataset.preview;
        preview.style.backgroundImage = '';
        preview.style.backgroundSize = 'cover';
        preview.style.backgroundPosition = 'center';
        
        if (pageImages[pageNum] && pageImages[pageNum].length > 0) {
            // Show a simple indicator that this page has content
            preview.style.backgroundColor = '#e8f5e9';
            preview.style.color = '#4caf50';
        } else {
            preview.style.backgroundColor = 'white';
            preview.style.color = '#999';
        }
    });
}

function loadPalettes() {
    fetch('/palettes')
        .then(response => response.json())
        .then(palettes => {
            availablePalettes = palettes;
            const paletteSelect = document.getElementById('paletteSelect');
            paletteSelect.innerHTML = '';
            
            Object.keys(palettes).forEach(name => {
                const option = document.createElement('option');
                option.value = name;
                option.textContent = name.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                paletteSelect.appendChild(option);
            });
            
            // Select first palette by default
            if (Object.keys(palettes).length > 0) {
                paletteSelect.value = Object.keys(palettes)[0];
            }
        })
        .catch(error => {
            console.error('Error loading palettes:', error);
        });
}

function updatePaletteVisibility() {
    const colorMode = document.getElementById('colorMode').value;
    const paletteOptions = document.querySelectorAll('.palette-options');
    
    paletteOptions.forEach(option => {
        option.style.display = colorMode === 'custom' ? 'flex' : 'none';
    });
}

function updatePageSizes() {
    const paperSize = document.getElementById('paperSize').value;
    const orientation = document.getElementById('orientation').value;
    
    // Update page aspect ratios based on selection
    // For a saddle-stitch booklet, each page is 1/4 of the sheet
    const pages = document.querySelectorAll('.page');
    const previewPages = document.querySelectorAll('.preview-page');
    
    let aspectRatio;
    
    if (orientation === 'landscape') {
        // Sheet in landscape: each page is landscape-oriented (wider than tall)
        if (paperSize === 'A4') {
            // A4 landscape (297x210) gives 4 pages of 148.5x105 each
            aspectRatio = '148.5/105';
        } else { // A3
            // A3 landscape (420x297) gives 4 pages of 210x148.5 each
            aspectRatio = '210/148.5';
        }
    } else { // portrait
        // Sheet in portrait: each page is portrait-oriented (taller than wide)
        if (paperSize === 'A4') {
            // A4 portrait (210x297) gives 4 pages of 105x148.5 each
            aspectRatio = '105/148.5';
        } else { // A3
            // A3 portrait (297x420) gives 4 pages of 148.5x210 each
            aspectRatio = '148.5/210';
        }
    }
    
    pages.forEach(page => {
        page.style.aspectRatio = aspectRatio;
    });
    
    previewPages.forEach(page => {
        page.style.aspectRatio = aspectRatio;
    });
}

async function generatePDF() {
    const paperSize = document.getElementById('paperSize').value;
    const orientation = document.getElementById('orientation').value;
    
    const data = {
        paperSize: paperSize,
        orientation: orientation,
        pages: pageImages
    };
    
    try {
        const response = await fetch('/generate-pdf', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = 'booklet.pdf';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
        } else {
            alert('Error generating PDF. Please try again.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error generating PDF. Please make sure the server is running.');
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    if (selectedImage) {
        if (e.key === 'Delete' || e.key === 'Backspace') {
            e.preventDefault();
            const page = selectedImage.closest('.page');
            const pageNum = page.dataset.page;
            const imageId = selectedImage.dataset.imageId;
            
            // Remove from data
            if (pageImages[pageNum]) {
                pageImages[pageNum] = pageImages[pageNum].filter(img => img.id !== imageId);
            }
            
            // Remove from DOM
            selectedImage.remove();
            selectedImage = null;
            updatePreview();
        }
    }
});

// Dithering algorithms
function floydSteinbergDither(imageData, colorMode) {
    const data = imageData.data;
    const width = imageData.width;
    const height = imageData.height;
    
    // Create a working copy with floating point values
    const workingData = new Float32Array(data.length);
    for (let i = 0; i < data.length; i++) {
        workingData[i] = data[i];
    }
    
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const idx = (y * width + x) * 4;
            
            // Get current color from working data
            let r = Math.max(0, Math.min(255, workingData[idx]));
            let g = Math.max(0, Math.min(255, workingData[idx + 1]));
            let b = Math.max(0, Math.min(255, workingData[idx + 2]));
            
            // Apply color mode
            let newR, newG, newB;
            if (colorMode === '1bit') {
                // Convert to grayscale
                const gray = 0.299 * r + 0.587 * g + 0.114 * b;
                const threshold = gray < 128 ? 0 : 255;
                newR = newG = newB = threshold;
            } else if (colorMode === 'rgb') {
                // Quantize to limited RGB palette (8 colors - 1 bit per channel)
                newR = r < 128 ? 0 : 255;
                newG = g < 128 ? 0 : 255;
                newB = b < 128 ? 0 : 255;
            } else if (colorMode === 'cmyk') {
                // Convert RGB to CMYK
                const rNorm = r / 255;
                const gNorm = g / 255;
                const bNorm = b / 255;
                
                const k = 1 - Math.max(rNorm, gNorm, bNorm);
                const c = (1 - rNorm - k) / (1 - k) || 0;
                const m = (1 - gNorm - k) / (1 - k) || 0;
                const y = (1 - bNorm - k) / (1 - k) || 0;
                
                // Threshold each CMYK channel to on/off
                const cBit = c > 0.5 ? 1 : 0;
                const mBit = m > 0.5 ? 1 : 0;
                const yBit = y > 0.5 ? 1 : 0;
                const kBit = k > 0.5 ? 1 : 0;
                
                // Convert back to RGB for display
                // This simulates CMYK printing on white paper
                const cyan = cBit * (1 - kBit);
                const magenta = mBit * (1 - kBit);
                const yellow = yBit * (1 - kBit);
                
                newR = Math.round((1 - Math.min(1, cyan + kBit)) * 255);
                newG = Math.round((1 - Math.min(1, magenta + kBit)) * 255);
                newB = Math.round((1 - Math.min(1, yellow + kBit)) * 255);
            } else if (colorMode === 'custom') {
                // Find nearest color in custom palette
                const paletteName = document.getElementById('paletteSelect').value;
                const palette = availablePalettes[paletteName] || [];
                
                let minDist = Infinity;
                let nearest = { r: 0, g: 0, b: 0 };
                
                palette.forEach(hexColor => {
                    const pR = parseInt(hexColor.substr(1, 2), 16);
                    const pG = parseInt(hexColor.substr(3, 2), 16);
                    const pB = parseInt(hexColor.substr(5, 2), 16);
                    
                    const dist = Math.sqrt(
                        Math.pow(r - pR, 2) +
                        Math.pow(g - pG, 2) +
                        Math.pow(b - pB, 2)
                    );
                    
                    if (dist < minDist) {
                        minDist = dist;
                        nearest = { r: pR, g: pG, b: pB };
                    }
                });
                
                newR = nearest.r;
                newG = nearest.g;
                newB = nearest.b;
            }
            
            // Calculate error
            const errR = r - newR;
            const errG = g - newG;
            const errB = b - newB;
            
            // Set new color in output
            data[idx] = newR;
            data[idx + 1] = newG;
            data[idx + 2] = newB;
            
            // Distribute error to neighboring pixels in working data
            if (x < width - 1) {
                // Right pixel (7/16)
                const rightIdx = idx + 4;
                workingData[rightIdx] += errR * 7 / 16;
                workingData[rightIdx + 1] += errG * 7 / 16;
                workingData[rightIdx + 2] += errB * 7 / 16;
            }
            
            if (y < height - 1) {
                if (x > 0) {
                    // Bottom-left pixel (3/16)
                    const blIdx = idx + (width - 1) * 4;
                    workingData[blIdx] += errR * 3 / 16;
                    workingData[blIdx + 1] += errG * 3 / 16;
                    workingData[blIdx + 2] += errB * 3 / 16;
                }
                
                // Bottom pixel (5/16)
                const bottomIdx = idx + width * 4;
                workingData[bottomIdx] += errR * 5 / 16;
                workingData[bottomIdx + 1] += errG * 5 / 16;
                workingData[bottomIdx + 2] += errB * 5 / 16;
                
                if (x < width - 1) {
                    // Bottom-right pixel (1/16)
                    const brIdx = idx + (width + 1) * 4;
                    workingData[brIdx] += errR * 1 / 16;
                    workingData[brIdx + 1] += errG * 1 / 16;
                    workingData[brIdx + 2] += errB * 1 / 16;
                }
            }
        }
    }
    
    return imageData;
}

function atkinsonDither(imageData, colorMode) {
    const data = imageData.data;
    const width = imageData.width;
    const height = imageData.height;
    
    // Create a working copy with floating point values
    const workingData = new Float32Array(data.length);
    for (let i = 0; i < data.length; i++) {
        workingData[i] = data[i];
    }
    
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            const idx = (y * width + x) * 4;
            
            // Get current color from working data
            let r = Math.max(0, Math.min(255, workingData[idx]));
            let g = Math.max(0, Math.min(255, workingData[idx + 1]));
            let b = Math.max(0, Math.min(255, workingData[idx + 2]));
            
            // Apply color mode
            let newR, newG, newB;
            if (colorMode === '1bit') {
                const gray = 0.299 * r + 0.587 * g + 0.114 * b;
                const threshold = gray < 128 ? 0 : 255;
                newR = newG = newB = threshold;
            } else if (colorMode === 'rgb') {
                // Quantize to limited RGB palette (8 colors - 1 bit per channel)
                newR = r < 128 ? 0 : 255;
                newG = g < 128 ? 0 : 255;
                newB = b < 128 ? 0 : 255;
            } else if (colorMode === 'cmyk') {
                // Convert RGB to CMYK
                const rNorm = r / 255;
                const gNorm = g / 255;
                const bNorm = b / 255;
                
                const k = 1 - Math.max(rNorm, gNorm, bNorm);
                const c = (1 - rNorm - k) / (1 - k) || 0;
                const m = (1 - gNorm - k) / (1 - k) || 0;
                const y = (1 - bNorm - k) / (1 - k) || 0;
                
                // Threshold each CMYK channel to on/off
                const cBit = c > 0.5 ? 1 : 0;
                const mBit = m > 0.5 ? 1 : 0;
                const yBit = y > 0.5 ? 1 : 0;
                const kBit = k > 0.5 ? 1 : 0;
                
                // Convert back to RGB for display
                const cyan = cBit * (1 - kBit);
                const magenta = mBit * (1 - kBit);
                const yellow = yBit * (1 - kBit);
                
                newR = Math.round((1 - Math.min(1, cyan + kBit)) * 255);
                newG = Math.round((1 - Math.min(1, magenta + kBit)) * 255);
                newB = Math.round((1 - Math.min(1, yellow + kBit)) * 255);
            } else if (colorMode === 'custom') {
                // Find nearest color in custom palette
                const paletteName = document.getElementById('paletteSelect').value;
                const palette = availablePalettes[paletteName] || [];
                
                let minDist = Infinity;
                let nearest = { r: 0, g: 0, b: 0 };
                
                palette.forEach(hexColor => {
                    const pR = parseInt(hexColor.substr(1, 2), 16);
                    const pG = parseInt(hexColor.substr(3, 2), 16);
                    const pB = parseInt(hexColor.substr(5, 2), 16);
                    
                    const dist = Math.sqrt(
                        Math.pow(r - pR, 2) +
                        Math.pow(g - pG, 2) +
                        Math.pow(b - pB, 2)
                    );
                    
                    if (dist < minDist) {
                        minDist = dist;
                        nearest = { r: pR, g: pG, b: pB };
                    }
                });
                
                newR = nearest.r;
                newG = nearest.g;
                newB = nearest.b;
            }
            
            // Calculate error (Atkinson distributes 3/4 of the error)
            const errR = (r - newR) * 3 / 4 / 6;  // Divided by 6 neighbors
            const errG = (g - newG) * 3 / 4 / 6;
            const errB = (b - newB) * 3 / 4 / 6;
            
            // Set new color in output
            data[idx] = newR;
            data[idx + 1] = newG;
            data[idx + 2] = newB;
            
            // Distribute error to neighboring pixels (1/8 of total error to each)
            const positions = [
                { x: x + 1, y: y },     // right
                { x: x + 2, y: y },     // right+1
                { x: x - 1, y: y + 1 }, // bottom-left
                { x: x, y: y + 1 },     // bottom
                { x: x + 1, y: y + 1 }, // bottom-right
                { x: x, y: y + 2 }      // bottom+1
            ];
            
            positions.forEach(pos => {
                if (pos.x >= 0 && pos.x < width && pos.y >= 0 && pos.y < height) {
                    const neighborIdx = (pos.y * width + pos.x) * 4;
                    workingData[neighborIdx] += errR;
                    workingData[neighborIdx + 1] += errG;
                    workingData[neighborIdx + 2] += errB;
                }
            });
        }
    }
    
    return imageData;
}

function applyDithering(imgElement, originalSrc) {
    if (!document.getElementById('ditherToggle').checked) {
        imgElement.src = originalSrc;
        return;
    }
    
    const colorMode = document.getElementById('colorMode').value;
    const ditherMethod = document.getElementById('ditherMethod').value;
    
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const tempImg = new Image();
    
    tempImg.onload = function() {
        canvas.width = tempImg.width;
        canvas.height = tempImg.height;
        ctx.drawImage(tempImg, 0, 0);
        
        let imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        
        if (ditherMethod === 'floyd-steinberg') {
            imageData = floydSteinbergDither(imageData, colorMode);
        } else if (ditherMethod === 'atkinson') {
            imageData = atkinsonDither(imageData, colorMode);
        }
        
        ctx.putImageData(imageData, 0, 0);
        imgElement.src = canvas.toDataURL();
    };
    
    tempImg.src = originalSrc;
}

function applyDitheringToAll() {
    const ditherEnabled = document.getElementById('ditherToggle').checked;
    
    // Apply dithering to library images
    document.querySelectorAll('.library-image').forEach(img => {
        const originalSrc = uploadedImages.find(i => i.id === img.dataset.imageId)?.src;
        if (originalSrc) {
            applyDithering(img, originalSrc);
        }
    });
    
    // Apply dithering to placed images and update stored data
    document.querySelectorAll('.page-image img').forEach(img => {
        const imgContainer = img.closest('.page-image');
        const page = imgContainer.closest('.page');
        const pageNum = page.dataset.page;
        const imageId = imgContainer.dataset.imageId;
        
        if (pageImages[pageNum]) {
            const imageData = pageImages[pageNum].find(i => i.id === imageId);
            if (imageData) {
                const srcToUse = imageData.originalSrc || imageData.src;
                applyDithering(img, srcToUse);
                
                // Update the stored src with dithered or original version
                if (ditherEnabled) {
                    setTimeout(() => {
                        imageData.src = img.src;  // Store the dithered version
                    }, 100);
                } else {
                    imageData.src = srcToUse;  // Restore original
                }
            }
        }
    });
}