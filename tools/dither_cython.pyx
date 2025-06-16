# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True

import numpy as np
cimport numpy as np
cimport cython
from libc.math cimport sqrt

np.import_array()

ctypedef np.uint8_t uint8_t
ctypedef np.float32_t float32_t

@cython.boundscheck(False)
@cython.wraparound(False)
cdef inline int find_nearest_color(float32_t r, float32_t g, float32_t b, 
                                  float32_t[:, :] palette, int n_colors) nogil:
    """Find nearest color in palette using squared distance"""
    cdef int i, nearest = 0
    cdef float32_t min_dist = 1e10
    cdef float32_t dist, dr, dg, db
    
    for i in range(n_colors):
        dr = r - palette[i, 0]
        dg = g - palette[i, 1] 
        db = b - palette[i, 2]
        dist = dr*dr + dg*dg + db*db
        if dist < min_dist:
            min_dist = dist
            nearest = i
    
    return nearest

@cython.boundscheck(False)
@cython.wraparound(False)
def floyd_steinberg_cython(np.ndarray[uint8_t, ndim=3] image, 
                          np.ndarray[uint8_t, ndim=2] palette_array):
    """Fast Floyd-Steinberg dithering implementation"""
    cdef int height = image.shape[0]
    cdef int width = image.shape[1]
    cdef int n_colors = palette_array.shape[0]
    cdef int y, x, i
    cdef float32_t r, g, b, er, eg, eb
    cdef int nearest_idx
    
    # Convert palette to float for calculations
    cdef np.ndarray[float32_t, ndim=2] palette = palette_array.astype(np.float32)
    
    # Working copy in float32 for error accumulation
    cdef np.ndarray[float32_t, ndim=3] work = image.astype(np.float32)
    
    # Output array
    cdef np.ndarray[uint8_t, ndim=3] output = np.empty((height, width, 3), dtype=np.uint8)
    
    # Memory views for fast access
    cdef float32_t[:, :, :] work_view = work
    cdef uint8_t[:, :, :] output_view = output
    cdef float32_t[:, :] palette_view = palette
    
    with nogil:
        for y in range(height):
            for x in range(width):
                # Get current pixel with clamping
                r = work_view[y, x, 0]
                g = work_view[y, x, 1]
                b = work_view[y, x, 2]
                
                # Clamp values to valid range
                if r < 0: r = 0
                if r > 255: r = 255
                if g < 0: g = 0
                if g > 255: g = 255
                if b < 0: b = 0
                if b > 255: b = 255
                
                # Find nearest color
                nearest_idx = find_nearest_color(r, g, b, palette_view, n_colors)
                
                # Set output pixel
                output_view[y, x, 0] = <uint8_t>palette_view[nearest_idx, 0]
                output_view[y, x, 1] = <uint8_t>palette_view[nearest_idx, 1]
                output_view[y, x, 2] = <uint8_t>palette_view[nearest_idx, 2]
                
                # Calculate error
                er = r - palette_view[nearest_idx, 0]
                eg = g - palette_view[nearest_idx, 1]
                eb = b - palette_view[nearest_idx, 2]
                
                # Distribute error
                if x + 1 < width:
                    work_view[y, x + 1, 0] = work_view[y, x + 1, 0] + er * 7 / 16
                    work_view[y, x + 1, 1] = work_view[y, x + 1, 1] + eg * 7 / 16
                    work_view[y, x + 1, 2] = work_view[y, x + 1, 2] + eb * 7 / 16
                
                if y + 1 < height:
                    if x > 0:
                        work_view[y + 1, x - 1, 0] += er * 3 / 16
                        work_view[y + 1, x - 1, 1] += eg * 3 / 16
                        work_view[y + 1, x - 1, 2] += eb * 3 / 16
                    
                    work_view[y + 1, x, 0] += er * 5 / 16
                    work_view[y + 1, x, 1] += eg * 5 / 16
                    work_view[y + 1, x, 2] += eb * 5 / 16
                    
                    if x + 1 < width:
                        work_view[y + 1, x + 1, 0] += er * 1 / 16
                        work_view[y + 1, x + 1, 1] += eg * 1 / 16
                        work_view[y + 1, x + 1, 2] += eb * 1 / 16
    
    return output

@cython.boundscheck(False)
@cython.wraparound(False)
def atkinson_cython(np.ndarray[uint8_t, ndim=3] image,
                   np.ndarray[uint8_t, ndim=2] palette_array):
    """Fast Atkinson dithering implementation"""
    cdef int height = image.shape[0]
    cdef int width = image.shape[1]
    cdef int n_colors = palette_array.shape[0]
    cdef int y, x, i
    cdef float32_t r, g, b, er, eg, eb
    cdef int nearest_idx
    
    # Convert palette to float
    cdef np.ndarray[float32_t, ndim=2] palette = palette_array.astype(np.float32)
    
    # Working copy
    cdef np.ndarray[float32_t, ndim=3] work = image.astype(np.float32)
    
    # Output array
    cdef np.ndarray[uint8_t, ndim=3] output = np.empty((height, width, 3), dtype=np.uint8)
    
    # Memory views
    cdef float32_t[:, :, :] work_view = work
    cdef uint8_t[:, :, :] output_view = output
    cdef float32_t[:, :] palette_view = palette
    
    with nogil:
        for y in range(height):
            for x in range(width):
                # Get current pixel
                r = work_view[y, x, 0]
                g = work_view[y, x, 1]
                b = work_view[y, x, 2]
                
                # Find nearest color
                nearest_idx = find_nearest_color(r, g, b, palette_view, n_colors)
                
                # Set output pixel
                output_view[y, x, 0] = <uint8_t>palette_view[nearest_idx, 0]
                output_view[y, x, 1] = <uint8_t>palette_view[nearest_idx, 1]
                output_view[y, x, 2] = <uint8_t>palette_view[nearest_idx, 2]
                
                # Calculate error (Atkinson uses 3/4 of error)
                er = (r - palette_view[nearest_idx, 0]) * 3 / 4 / 6
                eg = (g - palette_view[nearest_idx, 1]) * 3 / 4 / 6
                eb = (b - palette_view[nearest_idx, 2]) * 3 / 4 / 6
                
                # Distribute error to 6 neighbors
                if x + 1 < width:
                    work_view[y, x + 1, 0] += er
                    work_view[y, x + 1, 1] += eg
                    work_view[y, x + 1, 2] += eb
                
                if x + 2 < width:
                    work_view[y, x + 2, 0] += er
                    work_view[y, x + 2, 1] += eg
                    work_view[y, x + 2, 2] += eb
                
                if y + 1 < height:
                    if x > 0:
                        work_view[y + 1, x - 1, 0] += er
                        work_view[y + 1, x - 1, 1] += eg
                        work_view[y + 1, x - 1, 2] += eb
                    
                    work_view[y + 1, x, 0] += er
                    work_view[y + 1, x, 1] += eg
                    work_view[y + 1, x, 2] += eb
                    
                    if x + 1 < width:
                        work_view[y + 1, x + 1, 0] += er
                        work_view[y + 1, x + 1, 1] += eg
                        work_view[y + 1, x + 1, 2] += eb
                
                if y + 2 < height:
                    work_view[y + 2, x, 0] += er
                    work_view[y + 2, x, 1] += eg
                    work_view[y + 2, x, 2] += eb
    
    return output