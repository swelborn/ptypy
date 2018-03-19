'''
All propagation based kernels 
'''
import numpy as np
from . import COMPLEX_TYPE
#import scipy as sci

#import pyfftw
#import pyfftw.interfaces.numpy_fft as fftw_np


def farfield_propagator(data_to_be_transformed, prefilter=None, postfilter=None, direction='forward'):
    '''
    performs a fourier transform on the nd exit wave stack. FFT shift and normalisation performed by 
    multiplication with prefilter and postfilter 
    :param data_to_be_transformed. The nd stack of the current iterant.
    :param prefilter. The filter to multiply before fourier transforming. Default: None.
    :param postfilter. The filter to multiply after fourier transforming. Default: None.
    :param direction. The direction of the transform forward or backward. Default: Forward.
    :return: The transformed stack.
    '''

    #pyfftw.interfaces.cache.enable()
    #pyfftw.interfaces.cache.set_keepalive_time(15.0)
    #pe = 'FFTW_MEASURE'

    dtype = data_to_be_transformed.dtype
    if direction is 'forward':
        fft = lambda x: np.fft.fft2(x, axes=(-2, -1)).astype(dtype)
        #fft = lambda x: fftw_np.fft2(x, planner_effort=pe, axes=(-2, -1))
        #fft = sci.fftpack.fft2
        sc = 1.0 / np.sqrt(np.prod(data_to_be_transformed.shape[-2:]))

    elif direction is 'backward':
        fft = lambda x: np.fft.ifft2(x,  axes=(-2, -1)).astype(dtype)
        #fft = lambda x: fftw_np.ifft2(x, planner_effort=pe, axes=(-2, -1))
        #fft = sci.fftpack.ifft2

        sc = np.sqrt(np.prod(data_to_be_transformed.shape[-2:]))

    if (prefilter is None) and (postfilter is None):
        return fft(data_to_be_transformed) * sc
    elif (prefilter is None) and (postfilter is not None):
        postfilter = postfilter.astype(dtype)
        return np.multiply(postfilter, fft(data_to_be_transformed)) * sc
    elif (prefilter is not None) and (postfilter is None):
        prefilter = prefilter.astype(dtype)
        return fft(np.multiply(data_to_be_transformed, prefilter))* sc
    elif (prefilter is not None) and (postfilter is not None):
        prefilter = prefilter.astype(dtype)
        postfilter = postfilter.astype(dtype)
        return np.multiply(postfilter, fft(np.multiply(data_to_be_transformed, prefilter))) * sc

def sqrt_abs(diffraction):
    return np.sqrt(np.abs(diffraction))






