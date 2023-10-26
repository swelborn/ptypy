# -*- coding: utf-8 -*-
"""
A simple implementation of Multislice for the
ePIE algorithm.

authors: Benedikt J. Daurer and more...
"""
from ptypy.engines import stochastic
from ptypy.engines import register
from ptypy.core import geometry
from ptypy.utils import Param
from ptypy.utils.verbose import logger
from ptypy import io
import numpy as np

@register()
class ePIE_multislice(stochastic.EPIE):
    """
    An extension of EPIE to include multislice

    Defaults:

    [number_of_slices]
    default = 2
    type = int
    help = The number of slices
    doc = Defines how many slices are used for the multi-slice object.

    [slice_thickness]
    default = 1e-6
    type = float
    help = Thickness of a single slice in meters
    doc =

    [fslices]
    default = slices.h5
    type = str
    help = File path for the slice data
    doc =

    """
    def __init__(self, ptycho_parent, pars=None):
        super(ePIE_multislice, self).__init__(ptycho_parent, pars)

    def engine_initialize(self):
        super().engine_initialize()

        # Create a list of objects and exit waves (one for each slice)
        self._object = [None] * self.p.number_of_slices
        self._probe = [None] * self.p.number_of_slices
        self._exits = [None] * self.p.number_of_slices
        for i in range(self.p.number_of_slices):
            self._object[i] = self.ob.copy(self.ob.ID + "_o_" + str(i))
            self._probe[i] = self.pr.copy(self.pr.ID + "_p_" + str(i))
            self._exits[i] = self.pr.copy(self.pr.ID + "_e_" + str(i))

        scan = list(self.ptycho.model.scans.values())[0]
        geom = scan.geometries[0]
        g = Param()
        g.energy = geom.energy
        g.distance = self.p.slice_thickness
        g.psize = geom.resolution
        g.shape = geom.shape
        g.propagation = "nearfield"
        G = geometry.Geo(owner=None, pars=g)
        self.fw = G.propagator.fw
        self.bw = G.propagator.bw

    def engine_iterate(self, num=1):
        """
        Compute one iteration.
        """
        vieworder = list(self.di.views.keys())
        vieworder.sort()
        rng = np.random.default_rng()

        for it in range(num):

            error_dct = {}
            rng.shuffle(vieworder)

            for name in vieworder:
                view = self.di.views[name]
                if not view.active:
                    continue

                # Multislice update
                error_dct[name] = self.multislice_update(view)

            self.curiter += 1

        return error_dct

    def engine_finalize(self):
        self.ob.fill(self._object[0])
        for i in range(1, self.p.number_of_slices):
            self.ob *= self._object[i]

        # Save the slices
        slices_info = Param()
        slices_info.number_of_slices = self.p.number_of_slices
        slices_info.slice_thickness = self.p.slice_thickness
        slices_info.objects = {ob.ID: {ID: S._to_dict() for ID, S in ob.storages.items()}
                               for ob in self._object}

        header = {'description': 'multi-slices result details.'}

        h5opt = io.h5options['UNSUPPORTED']
        io.h5options['UNSUPPORTED'] = 'ignore'
        logger.info(f'Saving to {self.p.fslices}')
        io.h5write(self.p.fslices, header=header, content=slices_info)
        io.h5options['UNSUPPORTED'] = h5opt

        return super().engine_finalize()

    def multislice_update(self, view):
        """
        Does multislice ePIE
        based on https://doi.org/10.1364/JOSAA.29.001606
        """
        # Assume single pod
        # TODO: consider probe modes
        pod = view.pod

        # Forward multislice, calculate exit waves
        for i in range(self.p.number_of_slices-1):
            # exit wave for this slice
            self._exits[i][pod.pr_view] = self._probe[i][pod.pr_view] * self._object[i][pod.ob_view]
            # incident wave for next slice
            self._probe[i+1][pod.pr_view] = self.fw(self._exits[i][pod.pr_view])

        # Exit wave for last slice
        self._exits[-1][pod.pr_view] = self._probe[-1][pod.pr_view] * self._object[-1][pod.ob_view]

        # Save final state into pod (need for ptypy fourier update)
        pod.probe = self._probe[-1][pod.pr_view]
        pod.object = self._object[-1][pod.ob_view]

        # Fourier update
        error = self.fourier_update(view)

        # Object/probe update for the last slice
        self.object_update(view, {pod.ID:self._exits[-1][pod.pr_view]})
        self._object[-1][pod.ob_view] = pod.object
        self.probe_update(view, {pod.ID:self._exits[-1][pod.pr_view]})
        self._probe[-1][pod.pr_view] = pod.probe

        # Object/probe update for other slices (backwards)
        for i in range(self.p.number_of_slices-2, -1, -1):

            # Backwards propagation of the probe
            pod.exit = self.bw(self._probe[i+1][pod.pr_view])

            # Save state into pods
            pod.probe = self._probe[i][pod.pr_view]

            pod.object = self._object[i][pod.ob_view]

            # Actual object/probe update
            self.object_update(view, {pod.ID:self._exits[i][pod.pr_view]})
            self._object[i][pod.ob_view] = pod.object
            self.probe_update(view, {pod.ID:self._exits[i][pod.pr_view]})
            self._probe[i][pod.pr_view] = pod.probe

        # set the object as the product of all slices for better live plotting
        self.ob.fill(self._object[0])
        for i in range(1, self.p.number_of_slices):
            self.ob *= self._object[i]

        return error
