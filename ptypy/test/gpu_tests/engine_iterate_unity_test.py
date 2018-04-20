'''
This test checks the GPU vs Array based iterate methods

'''

import unittest
import numpy as np
from copy import deepcopy

import utils as tu
from ptypy.array_based import data_utils as du
from ptypy.gpu import constraints as gcon
from ptypy.array_based import constraints as con
from ptypy.gpu.config import init_gpus, reset_function_cache
init_gpus(0)


class EngineIterateUnityTest(unittest.TestCase):

    def tearDown(self):
        # reset the cached GPU functions after each test
        reset_function_cache()

    def test_DM_engine_iterate_mathod(self):
        num_probe_modes = 2  # number of modes
        num_iters = 10  # number of iterations
        frame_size = 64  # frame size
        num_points = 50  # number of points in the scan (length of the diffraction array).

        alpha = 1.0  # this is basically always 1

        for m in range(num_probe_modes):
            number_of_probe_modes = m + 1
            PtychoInstanceVec = tu.get_ptycho_instance('testing_iterate', num_modes=number_of_probe_modes,
                                                       frame_size=frame_size,
                                                       scan_length=num_points)  # this one we run with GPU
            vectorised_scan = du.pod_to_arrays(PtychoInstanceVec, 'S0000')
            diffraction_storage = PtychoInstanceVec.di.storages['S0000']
            pbound = (0.25 * PtychoInstanceVec.p.engine.DM.fourier_relax_factor ** 2 * diffraction_storage.pbound_stub)
            mean_power = diffraction_storage.tot_power / np.prod(diffraction_storage.shape)

            print("pbound:%s" % pbound)
            print("mean_power:%s" % mean_power)

            first_view_id = vectorised_scan['meta']['view_IDs'][0]
            master_pod = PtychoInstanceVec.diff.V[first_view_id].pod
            propagator = master_pod.geometry.propagator

            # this is for the numpy based
            diffraction = vectorised_scan['diffraction']
            obj = vectorised_scan['obj']
            probe = vectorised_scan['probe']
            mask = vectorised_scan['mask']
            exit_wave = vectorised_scan['exit wave']
            addr_info = vectorised_scan['meta']['addr']
            object_weights = vectorised_scan['object weights']
            probe_weights = vectorised_scan['probe weights']

            prefilter = propagator.pre_fft
            postfilter = propagator.post_fft
            cfact_object = PtychoInstanceVec.p.engine.DM.object_inertia * mean_power * \
                           (vectorised_scan['object viewcover'] + 1.)
            cfact_probe = (PtychoInstanceVec.p.engine.DM.probe_inertia * len(addr_info) /
                           vectorised_scan['probe'].shape[0]) * np.ones_like(vectorised_scan['probe'])

            probe_support = np.zeros_like(probe)
            X, Y = np.meshgrid(range(probe.shape[1]), range(probe.shape[2]))
            R = (0.7 * probe.shape[1]) / 2
            for idx in range(probe.shape[0]):
                probe_support[idx, X ** 2 + Y ** 2 < R ** 2] = 1.0

            print("For number of probe modes: %s\n"
                  "number of scan points: %s\n"
                  "and frame size: %s\n" % (number_of_probe_modes, num_points, frame_size))

            print("The sizes of the arrays are:\n"
                  "diffraction: %s\n"
                  "obj: %s\n"
                  "probe: %s\n"
                  "mask: %s \n"
                  "exit wave: %s \n"
                  "addr_info: %s\n"
                  "object_weights: %s\n"
                  "probe_weights: %s\n"
                  "prefilter: %s\n"
                  "postfilter: %s\n"
                  "cfact_object: %s\n"
                  "cfact_probe: %s\n"
                  "probe_support: %s\n" % (diffraction.shape,
                                           obj.shape,
                                           probe.shape,
                                           mask.shape,
                                           exit_wave.shape,
                                           addr_info.shape,
                                           object_weights.shape,
                                           probe_weights.shape,
                                           prefilter.shape,
                                           postfilter.shape,
                                           cfact_object.shape,
                                           cfact_probe.shape,
                                           probe_support.shape))

            # take exact copies for the gpu implementation
            gdiffraction = deepcopy(diffraction)
            gobj = deepcopy(diffraction)
            gprobe = deepcopy(probe)
            gmask = deepcopy(mask)
            gexit_wave = deepcopy(exit_wave)
            gaddr_info = deepcopy(addr_info)
            gobject_weights = deepcopy(object_weights)
            gprobe_weights = deepcopy(probe_weights)

            gprefilter = deepcopy(prefilter)
            gpostfilter = deepcopy(postfilter)
            gcfact_object = deepcopy(cfact_object)
            gcfact_probe = deepcopy(cfact_probe)

            gpbound = deepcopy(pbound)
            galpha = deepcopy(alpha)
            gprobe_support = deepcopy(probe_support)

            errors = con.difference_map_iterator(diffraction=diffraction,
                                                 obj=obj,
                                                 object_weights=object_weights,
                                                 cfact_object=cfact_object,
                                                 mask=mask,
                                                 probe=probe,
                                                 cfact_probe=cfact_probe,
                                                 probe_support=probe_support,
                                                 probe_weights=probe_weights,
                                                 exit_wave=exit_wave,
                                                 addr=addr_info,
                                                 pre_fft=prefilter,
                                                 post_fft=postfilter,
                                                 pbound=pbound,
                                                 overlap_max_iterations=10,
                                                 update_object_first=False,
                                                 obj_smooth_std=None,
                                                 overlap_converge_factor=0.05,
                                                 probe_center_tol=None,
                                                 probe_update_start=1,
                                                 alpha=alpha,
                                                 clip_object=None,
                                                 LL_error=True,
                                                 num_iterations=num_iters)

            gerrors = gcon.difference_map_iterator(diffraction=gdiffraction,
                                                  obj=gobj,
                                                  object_weights=gobject_weights,
                                                  cfact_object=gcfact_object,
                                                  mask=gmask,
                                                  probe=gprobe,
                                                  cfact_probe=gcfact_probe,
                                                  probe_support=gprobe_support,
                                                  probe_weights=gprobe_weights,
                                                  exit_wave=gexit_wave,
                                                  addr=gaddr_info,
                                                  pre_fft=gprefilter,
                                                  post_fft=gpostfilter,
                                                  pbound=gpbound,
                                                  overlap_max_iterations=10,
                                                  update_object_first=False,
                                                  obj_smooth_std=None,
                                                  overlap_converge_factor=0.05,
                                                  probe_center_tol=None,
                                                  probe_update_start=1,
                                                  alpha=galpha,
                                                  clip_object=None,
                                                  LL_error=True,
                                                  num_iterations=num_iters)


            for idx in range(len(exit_wave)):
                np.testing.assert_allclose(gexit_wave[idx], exit_wave[idx], err_msg="Output exit waves for index {} don't match".format(idx))

            for idx in range(len(probe)):
                np.testing.assert_allclose(gprobe[idx], probe[idx], err_msg="Output probes for index {} don't match".format(idx))

            for idx in range(len(errors)):
                np.testing.assert_allclose(gerrors[idx], errors[idx], err_msg="Output errors for index {} don't match".format(idx))

            np.testing.assert_allclose(obj, gobj, err_msg="The output objects don't match.")

            # clean this up to prevent a leak.
            del PtychoInstanceVec

if __name__=='__main__':
    unittest.main()
