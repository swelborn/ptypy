"""   
This module provides simulated 3D Bragg data. 
"""

import ptypy
from ptypy.core.data import PtyScan
import ptypy.utils as u
from ptypy.utils.descriptor import defaults_tree
from ptypy.core import geometry_bragg

import numpy as np
import time

logger = u.verbose.logger


@defaults_tree.parse_doc('scandata.Bragg3dSimScan')
class Bragg3dSimScan(PtyScan):
    """
    Provides simulated 3D Bragg data based on the numerical 
    experiment in Berenguer et al., PRB 88 (2013) 144101.

    Defaults:

    [name]
    default = Bragg3dSimScan
    type = str
    help = PtyScan subclass identifier

    [shape]
    # Godard: default = 1024
    default = 256

    [distance]
    default = 2

    [psize]
    default = 13e-6

    [energy]
    default = 8.5

    [probe_fwhm]
    default = 1e-6
    type = float
    lowlim = 0.0
    help = FWHM of the gaussian probe

    [rocking_step]
    # Godard: default = .01
    default = .0025
    type = float
    help = Step size in the rocking curve in degrees

    [n_rocking_positions]
    # Godard: default = 9
    default = 40
    type = int
    help = Number of rocking positions

    [theta_bragg]
    default = 22.32
    type = float
    help = Bragg angle in degrees

    [shuffle]
    default = False
    type = bool
    help = Shuffles all diffraction patterns
    doc = Mainly to test that they are still assembled correctly.

    [dump]
    default = None
    type = str
    help = Dump raw simulated 3d diffraction data to npz file

    """

    def __init__(self, pars=None, **kwargs):
        self.p = self.DEFAULT.copy(99)
        self.p.update(pars)
        self.p.update(kwargs)
        super(Bragg3dSimScan, self).__init__(self.p)

        # do the simulation
        self.simulate()

    def simulate(self):
        # Set up a 3D geometry and a scan
        # -------------------------------

        shape = tuple(u.expect2(self.p.shape))
        psize = tuple(u.expect2(self.p.psize))
        g = ptypy.core.geometry_bragg.Geo_Bragg(
            psize=(self.p.rocking_step,) + psize, 
            shape=(self.p.n_rocking_positions,) + shape,
            energy=self.p.energy, 
            distance=self.p.distance, 
            theta_bragg=self.p.theta_bragg)

        # The Geo_Bragg object contains mostly the same things as Geo, but in
        # three dimensions. The third element of the shape is the number of
        # rocking curve positions, the third element of the psize denotes theta
        # step in degrees. 
        logger.info('Data will be simulated with these geometric parameters:')
        logger.info(g)

        # Set up scan positions along y, perpendicular to the incoming beam and
        # to the thin layer stripes.
        Npos = 11
        positions = np.zeros((Npos,3))
        positions[:, 2] = np.arange(Npos) - Npos/2.0
        positions *= .43e-6

        # Set up the object and its views
        # -------------------------------

        # Create a container for the object array, which will represent the
        # object in the non-orthogonal coordinate system conjugate to the
        # q-space measurement frame.
        C = ptypy.core.Container(data_type=np.complex128, data_dims=3)

        # For each scan position in the orthogonal coordinate system, find the
        # natural coordinates and create a View instance there.
        views = []
        for pos in positions:
            pos_ = g._r3r1r2(pos)
            views.append(ptypy.core.View(C, storageID='Sobj', psize=g.resolution, coord=pos_, shape=g.shape))
        S = C.storages['Sobj']
        C.reformat()

        # Define the test sample based on the orthogonal position of each voxel.
        # First, the cartesian grid is obtained from the geometry object, then
        # this grid is used as a condition for the sample's magnitude.
        xx, zz, yy = g.transformed_grid(S, input_space='real', input_system='natural')
        S.fill(0.0)
        S.data[(zz >= -90e-9) & (zz < 90e-9) & (yy + .3*zz >= 1e-6) & (yy - .3*zz< 2e-6) & (xx < 1e-6)] = 1
        S.data[(zz >= -90e-9) & (zz < 90e-9) & (yy + .3*zz >= -2e-6) & (yy - .3*zz < -1e-6)] = 1
        #import matplotlib.pyplot as plt
        #plt.imshow(np.abs(S.data[0, S.data.shape[0]/2, :, :]), interpolation='none')
        #plt.show()

        # Set up the probe and calculate diffraction patterns
        # ---------------------------------------------------

        # First set up a two-dimensional representation of the probe, with
        # arbitrary pixel spacing. The probe here is defined as a 1.5 um by 3 um
        # flat square, but this container will typically come from a 2d
        # transmission ptycho scan of an easy test object.
        Cprobe = ptypy.core.Container(data_dims=2, data_type='float')
        Sprobe = Cprobe.new_storage(psize=10e-9, shape=500)
        print 'WARNING! fix simulation probe extent'
        zi, yi = Sprobe.grids()

        # gaussian probe
        sigma = self.p.probe_fwhm / 2.3548
        Sprobe.data = np.exp(-zi**2 / (2 * sigma**2) - yi**2 / (2 * sigma**2))

        # The Bragg geometry has a method to prepare a 3d Storage by extruding
        # the 2d probe and interpolating to the right grid. The returned storage
        # contains a single view compatible with the object views.
        Sprobe_3d = g.prepare_3d_probe(Sprobe, system='natural')
        probeView = Sprobe_3d.views[0]

        # Calculate diffraction patterns by using the geometry's propagator.
        diff = []
        for v in views:
            diff.append(np.abs(g.propagator.fw(v.data * probeView.data))**2)

        # dump the 3d arrays for testing
        if self.p.dump is not None:
            np.savez(self.p.dump, **{'diff%02d'%i : diff[i] for i in range(len(diff))})

        # stack the 2d diffraction patterns and save
        self.diff = []
        for i in range(len(diff)):
            for j in range(len(diff[i])):
                self.diff.append(diff[i][j,:,:])

        # convert the positions from (x, z, y) to (angle, x, z, y) and 
        # save, we need the angle and in future we won't know in which 
        # plane the scan was done (although here it is in xy).
        # these xyz axis still follow Berenguer et al PRB 2013.
        self.positions = np.empty((g.shape[0] * Npos, 4), dtype=float)
        angles = (np.arange(g.shape[0]) - g.shape[0] / 2.0 + 1.0/2) * g.psize[0]
        for i in range(Npos):
            for j in range(g.shape[0]):
                self.positions[i * g.shape[0] + j, 1:] = positions[i, :]
                self.positions[i * g.shape[0] + j, 0] = angles[j]

        # shuffle everything as a test
        if self.p.shuffle:
            order = range(len(self.diff))
            from random import shuffle
            shuffle(order)
            self.diff = [self.diff[i] for i in order]
            new_pos = np.empty_like(self.positions)
            for i in range(len(new_pos)):
                new_pos[i] = self.positions[order[i]]
            self.positions = new_pos

    def load_common(self):
        """
        We have to communicate the number of rocking positions that the
        model should expect, otherwise it never knows when there is data
        for a complete POD.
        """
        return {
            'rocking_step': self.p.rocking_step,
            'n_rocking_positions': self.p.n_rocking_positions,
            'theta_bragg': self.p.theta_bragg,
            }

    def load_positions(self):
        """
        For the 3d Bragg model, load_positions returns N-by-4 positions,
        (angle, x, z, y). The angle can be relative or absolute, the
        model doesn't care, but it does have to be uniformly spaced for
        the analysis to make any sense.
        """
        return self.positions

    def load(self, indices):
        raw, positions, weights = {}, {}, {}

        # pick out the requested indices
        for i in indices:
            raw[i] = self.diff[i]

        return raw, positions, weights

    def load_weight(self):
        return np.ones_like(self.diff[0])


if __name__ == '__main__':
    u.verbose.set_level(3)
    ps = Bragg3dSimScan()
    ps.initialize()
    while True:
        msg = ps.auto(23)
        if msg == ps.EOS:
            break
        logger.info('Got %d images' % len(msg['iterable']))
