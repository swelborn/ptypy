# .. _simupod:

# Tutorial: Using Pods for simulation
# ===================================

# In the :ref:`ptypyclasses` we have learned to deal with the
# basic data storage-and-access class on small toy arrays.

# In this tutorial we will learn how to create :any:`POD` instances to 
# simulate a ptychography experiment and use larger arrays.

# We would like to point out that the "data" created her is not actual
# data. There is neither light or other wave-like particle involved 
# nor actual diffraction. You will also not find
# an actual movement of motors or stages, nor is there an actual detector
# Everything should be understood as a test for this software.

# The selected physical quantities only mimic a physical experiement.

# We start of with importing some modules
import matplotlib as mpl
import numpy as np
import ptypy
from ptypy import utils as u
from ptypy.core import View,Container,Storage,Base, POD
plt = mpl.pyplot
import sys
scriptname = sys.argv[0]

# We create a managing top level instance. We will not use the
# the :any:`Ptycho` class for now, as its rich set of methods may be
# a bit overwhelming to start. Instead we take a plain Base instance
P = Base()
P.CType = np.complex128
P.FType = np.float64

# Set "experimental" geometry and create propagator
# -------------------------------------------------

# In this tutorial we accept help from the :any:`Geo` class to provide
# a propagator and pixel sizes for sample and detector space.
from ptypy.core import geometry
g = u.Param()
g.energy = None #u.keV2m(1.0)/6.32e-7
g.lam = 5.32e-7
g.distance = 15e-2
g.psize = 24e-6
g.shape = 256
g.propagation = "farfield"
G = geometry.Geo(owner = P, pars=g)

# The Geo instance ``G`` has done a lot already at this moment. First
# of all we find forward and backward propagator at ``G.propagator.fw``
# and ``G.propagator.bw``. It has also calculated the appropriate sample
# space pixel size (aka resolution),
print G.resolution 
# which sets the shifting frame to be of the following size:
fsize = G.shape * G.resolution
print "%.2fx%.2fmm" % tuple(fsize*1e3)

# Create probing illumination
# ---------------------------

# Next we need to create a probing illumination. 
# We start of we a suited container that we call *probe*
P.probe = Container(P,'Cprobe',data_type='complex')

# For convenience, there is a test probing illumination in ptypy's 
# resources.
from ptypy.resources import moon_pr
pr = -moon_pr(G.shape)
pr = P.probe.new_storage(data=pr, psize=G.resolution)
fig = u.plot_storage(pr,0)
fig.savefig('%s_%d.png' % (scriptname,fig.number), dpi=300)
# Ptypy's default testing illumination, an image of the moon. 

# Of course we could have also used the coordinate grids from the propagator,
y,x = G.propagator.grids_sam
apert = u.smooth_step(fsize[0]/5-np.sqrt(x**2+y**2),3e-5)
pr2 = P.probe.new_storage(data=apert, psize=G.resolution)
fig = u.plot_storage(pr2,1)
fig.savefig('%s_%d.png' % (scriptname,fig.number), dpi=300)
# Round test illumination. 

# or the coordinate grids from the Storage itself.
pr3 = P.probe.new_storage(shape=G.shape, psize=G.resolution)
y,x = pr3.grids()
apert = u.smooth_step(fsize[0]/5-np.abs(x),3e-5)*u.smooth_step(fsize[1]/5-np.abs(y),3e-5)
pr3.fill(apert)
fig = u.plot_storage(pr3,2)
fig.savefig('%s_%d.png' % (scriptname,fig.number), dpi=300)
# Square test illumination. 

# In order to put some physics in the illumination we set the number of
# photons to 1 billion
for pp in [pr,pr2,pr3]:
    pp.data *= np.sqrt(1e9/np.sum(pp.data*pp.data.conj()))
print u.norm2(pr.data)

# We quickly test if the propagation works.
ill = pr.data[0]
propagated_ill = G.propagator.fw(ill)
fig=plt.figure(3);ax = fig.add_subplot(111); 
im = ax.imshow(np.log10(np.abs(propagated_ill)+1))
plt.colorbar(im)
fig.savefig('%s_%d.png' % (scriptname,fig.number), dpi=300)
# Logarhitmic intensity of propagated illumination

# Create scan pattern and object
# ------------------------------

# We use the :py:mod:`ptypy.core.xy` module to create a scan pattern.
pos = u.Param()
pos.model = "round"                
pos.spacing = fsize[0]/8                
pos.steps = None        
pos.extent = fsize*1.5
from ptypy.core import xy
positions = xy.from_pars(pos)
fig=plt.figure(4);ax = fig.add_subplot(111);
ax.plot(positions[:,1],positions[:,0],'o-');
fig.savefig('%s_%d.png' % (scriptname,fig.number), dpi=300)
# Created scan pattern.

# Next we need to create an object transmisson/ 
# We start of with a suited container that we call *obj*
P.obj = Container(P,'Cobj',data_type='complex')

# As we have learned from the previous :ref:`ptypyclasses`\ ,
# we can use :any:`View`\ 's to create a Storage data buffer of the
# right size.
oar = View.DEFAULT_ACCESSRULE.copy()
oar.storageID='S00'
oar.psize = G.resolution
oar.layer = 0
oar.shape = G.shape
oar.active = True

for pos in positions:
    # the rule
    r = oar.copy()
    r.coord = pos
    V = View(P.obj,None,r)

# Now we need to let the Storages in ``P.obj`` reformat to 
# include all Views. Conveniently, this can initiated from the top
# with Container.\ :py:meth:`~ptypy.core.classes.Container.reformat`
P.obj.reformat()
print P.obj.formatted_report()

# We need to fill the object storag ``S00`` with an object transmission.
# Again there is a convenience transmission function in the resources
from ptypy.resources import flower_obj
storage = P.obj.storages['S00']
storage.fill(flower_obj(storage.shape[-2:]))
fig = u.plot_storage(storage,5)
fig.savefig('%s_%d.png' % (scriptname,fig.number), dpi=300)

# Creating additional Views and the PODs
# --------------------------------------

# A single coherent propagation in ptypy is represented by the pod class
print POD.__doc__
print POD.__init__.__doc__

# For creating a single POD we need a View to *probe*, *object*,
# *exit* wave and *diff*\ raction containers as well as the :any:`Geo` 
# class instance. 

# First we create the missing contianers
P.exit =  Container(P,'Cexit',data_type='complex')
P.diff =  Container(P,'Cdiff',data_type='real')
P.mask =  Container(P,'Cmask',data_type='real')

# We start with the first POD and its views
objviews = P.obj.views.values()
obview = objviews[0]

# We construct the probe View
probe_ar = View.DEFAULT_ACCESSRULE.copy()
probe_ar.psize = G.resolution
probe_ar.shape = G.shape
probe_ar.active = True
probe_ar.storageID = pr.ID
prview = View(P.probe,None,probe_ar)

# We construct exit wave View. This construction is shorter as we only 
# change a few bits in the acces rule.
exit_ar = probe_ar.copy()
exit_ar.layer = 0
exit_ar.active = True
exview = View(P.exit,None,exit_ar)

# We construct diffraction and mask view. Even shorter as the mask is 
# essentially the same access as for the diffraction data.
diff_ar = probe_ar.copy()
diff_ar.layer = 0
diff_ar.active = True
diff_ar.psize = G.psize
mask_ar = diff_ar.copy()
maview = View(P.mask,None,mask_ar)
diview = View(P.diff,None,diff_ar)

# Now we can create the POD
pods = []
views = {'probe':prview,'obj':obview,'exit':exview,'diff':diview,'mask':maview}
pod = POD(P,ID=None,views=views,geometry=G)
pods.append(pod)

# The :any:`POD` is the most important class in ptycho. Its instances 
# are used to write the reconstruction algorithms using local references 
# from their attributes. For example we can create and store and exit
# wave in this convenient fashion:
pod.exit = pod.probe * pod.object

# The result of the calculation is stored in the respective storage.
# Therefore we can use this command to plot the result.
exit_storage = P.exit.storages.values()[0]
fig = u.plot_storage(exit_storage,6)
fig.savefig('%s_%d.png' % (scriptname,fig.number), dpi=300)
# Simulated exit wave using a pod

# The diffraction plane is also conveniently accessible
pod.diff = np.abs(pod.fw(pod.exit))**2

# The result is stored in the diffraction container.
diff_storage = P.diff.storages.values()[0]
fig = u.plot_storage(diff_storage,7,modulus='log')
fig.savefig('%s_%d.png' % (scriptname,fig.number), dpi=300)

 
# Creating the rest of the pods is simple since the data accesses are similar.
for obview in objviews[1:]:
    # we keep the same probe access
    prview = View(P.probe,None,probe_ar)
    # For diffraction diffraction and exit wave we need to increase the
    # layer index as exit wave and diffraction pattern is unique per
    # scan position
    exit_ar.layer +=1
    diff_ar.layer +=1
    exview = View(P.exit,None,exit_ar)
    maview = View(P.mask,None,mask_ar)
    diview = View(P.diff,None,diff_ar)
    views = {'probe':prview,'obj':obview,'exit':exview,'diff':diview,'mask':maview}
    pod = POD(P,ID=None,views=views,geometry=G)
    pods.append(pod)
    
# And the rest of the simulation in three lines
for pod in pods:
    pod.exit = pod.probe * pod.object
    # we use Poisson statistics for a tiny bit of realism in the
    # diffraction images
    pod.diff = np.random.poisson(np.abs(pod.fw(pod.exit))**2)
    pod.mask = np.ones_like(pod.diff)
    
# **Well done!**
# We can now move forward to create and run a reconstruction engine
# as in section :ref:`basic_algorithm` in :ref:`ownengine`
# or store the generated diffraction patterns as in the next section.


# .. _store:

# Storing the simulation
# ----------------------

# On unix system we choose the /tmp folder
save_path = '/tmp/ptypy/sim/'
import os
if not os.path.exists(save_path):
    os.makedirs(save_path)

# First we save the geometric info in a text file.
with open(save_path+'geometry.txt','w') as f:
    f.write('distance %.4e\n' % G.p.distance)
    f.write('energy %.4e\n' % G.energy)
    f.write('psize %.4e\n' % G.psize[0])
    f.write('shape %d\n' % G.shape[0])
    f.close()

# Now we save positions and the diffraction images. We don't burden
# ouselves for now by selecting an image file format such as .tiff or 
# .hdf5 but use numpys binary storage format
with open(save_path+'positions.txt','w') as f:
    if not os.path.exists(save_path+'ccd/'):
        os.mkdir(save_path+'ccd/')
    for pod in pods:
        diff_frame = 'ccd/diffraction_%04d.npy' % pod.di_view.layer
        f.write(diff_frame+' %.4e %.4e\n' % tuple(pod.ob_view.coord))
        frame = pod.diff.astype(np.int32)
        np.save(save_path+diff_frame, frame)

# If you want to learn how to convert this "experiment" into ptypy data
# file (``.ptyd``), see to :ref:`subclassptyscan`


