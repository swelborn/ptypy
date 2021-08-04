# -*- coding: utf-8 -*-
"""
ePIE reconstruction engine.

This file is part of the PTYPY package.

    :copyright: Copyright 2014 by the PTYPY team, see AUTHORS.
    :license: GPLv2, see LICENSE for details.
"""
import numpy as np
import time
from .. import utils as u
from ..utils.verbose import logger, log
from ..utils import parallel
from . import register
from .stochastic import StochasticBaseEngine
from ..core.manager import Full, Vanilla, Bragg3dModel, BlockVanilla, BlockFull

__all__ = ['EPIE']

@register()
class EPIE(StochasticBaseEngine):
    """
    The ePIE algorithm.

    Defaults:

    [name]
    default = EPIE
    type = str
    help =
    doc =

    [alpha]
    default = 1.0
    type = float
    lowlim = 0.0
    help = Parameter for adjusting the step size of the object update

    [beta]
    default = 1.0
    type = float
    lowlim = 0.0
    help = Parameter for adjusting the step size of the probe update

    """

    SUPPORTED_MODELS = [Full, Vanilla, Bragg3dModel, BlockVanilla, BlockFull]

    def __init__(self, ptycho_parent, pars=None):
        """
        ePIE reconstruction engine.
        """
        super().__init__(ptycho_parent, pars)

        # EPIE Adjustment parameters
        self.alpha = 0.0 # TODO: replace with generic fourier update params
        self.tau = 1.0 # TODO: replace with generic fourier update params
        self.prA = 0.0
        self.prB = self.p.alpha
        self.obA = 0.0
        self.obB = self.p.beta

        self.ptycho.citations.add_article(
            title='An improved ptychographical phase retrieval algorithm for diffractive imaging',
            author='Maiden A. and Rodenburg J.',
            journal='Ultramicroscopy',
            volume=10,
            year=2009,
            page=1256,
            doi='10.1016/j.ultramic.2009.05.012',
            comment='The ePIE reconstruction algorithm',
        )