import numpy as np
import pylab as plt
import os,subprocess,sys,time
import cPickle as pickle
import pandas as pd

import haloutils
from caterpillaranalysis import PluginBase
from MTanalysis2 import ExtantDataFirstPass

def get_snap_reion(hpath,zreion,justafter=False):
    numsnaps = haloutils.get_numsnaps(hpath)
    z = haloutils.get_z_snap(hpath,np.arange(numsnaps))
    snap_reion = np.max(np.where(z >= zreion)[0])
    if justafter: snap_reion += 1
    return snap_reion

class SimpleSAMsPlugin(PluginBase):
    def __init__(self):
        super(SimpleSAMsPlugin,self).__init__()
        self.filename='SimpleSAMs.p'

        self.xmin = 0; self.xmax = 1
        self.ymin = 0; self.ymax = 1
        self.xlabel = 'b/a'
        self.ylabel = 'c/a'
        self.xlog=False; self.ylog=False
        self.autofigname='SAMs'

        self.modelnames = {'R1':  'z=8 reionization',
                           'R2': 'z=10 reionization',
                           'R3': 'z=12 reionization',
                           'I1': 'first infall to any galaxy',
                           'I2': 'first infall to MW',
                           'A1': 'Moster abundance matching',
                           'S1': 'Stochastic abundance matching'
                           }
        self.extant = ExtantDataFirstPass()

    def _analyze(self,hpath):
        if not haloutils.check_last_rockstar_exists(hpath):
            raise IOError("No rockstar")
        if not haloutils.check_mergertree_exists(hpath):
            raise IOError("No merger tree")
        rscat = haloutils.load_rscat(hpath,haloutils.get_numsnaps(hpath)-1)
        zoomid= haloutils.load_zoomid(hpath)
        hpos = np.array(rscat.ix[zoomid][['posX','posY','posZ']])
        hvel = np.array(rscat.ix[zoomid][['pecVX','pecVY','pecVZ']])
        subs = self.get_rssubs(rscat,zoomid)
        subs = subs.copy()
        mtc = haloutils.load_mtc(hpath,haloids=[zoomid],indexbyrsid=True)
        
        ## properties at infall to MW
        extdat = self.extant.read(hpath)
        extdat.index = extdat['rsid']
        infall_labels = ['rsid','snap','vmax','mvir','posx','posy','posz',
                         'pecvx','pecvy','pecvz','virialratio','hostid_MT',
                         'rvir','spinbullock','rs','scale_of_last_MM',
                         'Jx','Jy','Jz','xoff']
        infall_labels = ['infall_'+l for l in infall_labels]
        for col in infall_labels:
            assert col not in subs.columns
            subs[col] = extdat.ix[subs.index][col]
        infall_scale = haloutils.get_scale_snap(hpath,np.array(subs['infall_snap']))
        infall_z = haloutils.get_z_snap(hpath,np.array(subs['infall_snap']))
        subs['infall_scale'] = infall_scale; subs['infall_z'] = infall_z

        ## setup properties at z=8,10,12 reionization
        subids = np.array(subs['id'])
        base_reionz_labels = ['origid','mvir','vmax'] #columns in MT
        for zreion in [8,10,12]:
            reionz_labels = ['z'+str(zreion)+'_'+label for label in base_reionz_labels]
            for reionz_label in reionz_labels:
                subs[reionz_label] = np.zeros(len(subs))+np.nan
        ## setup properties at first infall to any galaxy
        subs['finfall_snap'] = np.zeros(len(subs))+np.nan
        base_finfall_labels = base_reionz_labels
        finfall_labels = ['finfall_'+label for label in base_finfall_labels]
        for finfall_label in finfall_labels:
            subs[finfall_label] = np.zeros(len(subs))+np.nan
        ## setup properties at formation
        subs['form_snap'] = np.zeros(len(subs))+np.nan
        base_form_labels = base_reionz_labels
        form_labels = ['form_'+label for label in base_form_labels]
        for form_label in form_labels:
            subs[form_label] = np.zeros(len(subs))+np.nan

        for subid in subids:
            try:
                mt = mtc[subid]
            except KeyError:
                #print "WARNING: MTCatalogue does not have sub id {0}".format(subid)
                continue
            mb = mt.getMainBranch()
            ## properties at z=8,10,12 reionization
            for zreion in [8,10,12]:
                snap_reion = get_snap_reion(hpath,zreion)
                reion_ii = mb['snap']==snap_reion
                if np.sum(reion_ii)==0:
                    continue

                this_data = [float(mb[reion_ii][label][0]) for label in base_reionz_labels]
                reionz_labels = ['z'+str(zreion)+'_'+label for label in base_reionz_labels]
                for reionz_label,val in zip(reionz_labels,this_data):
                    subs[reionz_label][subid] = val
            ## properties at first infall to any galaxy
            #the pid is the MTid, not rsid; but -1 still denotes it's a host
            whensub = mb['pid'] != -1 
            finfall_snap = np.min(mb['snap'][whensub])
            finfall_ii = mb['snap']==finfall_snap
            subs['finfall_snap'][subid] = finfall_snap
            this_data = [float(mb[finfall_ii][label][0]) for label in base_finfall_labels]
            for finfall_label,val in zip(finfall_labels,this_data):
                subs[finfall_label][subid] = val
            ## properties at formation
            Mform = float(subs['infall_mvir'][subid])/2.
            form_snap = np.min(mb['snap'][mb['mvir']>Mform])
            form_ii = mb['snap']==form_snap
            subs['form_snap'][subid] = form_snap
            this_data = [float(mb[form_ii][label][0]) for label in base_form_labels]
            for form_label,val in zip(form_labels,this_data):
                subs[form_label][subid] = val

        with open(self.get_outfname(hpath),'w') as f:
            pickle.dump(subs,f)

    def _read(self,hpath):
        with open(self.get_outfname(hpath),'r') as f:
            subs = pickle.load(f)
        return subs
    def _plot(self,hpath,data,ax,lx=None,labelon=False,normtohost=False,**kwargs):
        subs = data
        raise NotImplementedError

if __name__=="__main__":
    hpath = haloutils.get_hpath_lx(5320,14)
    plug = SimpleSAMsPlugin()
    subs = plug.read(hpath,recalc=True)

