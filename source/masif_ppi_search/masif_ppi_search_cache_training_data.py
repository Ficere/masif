# Header variables and parameters.
import sys
import os
import numpy as np
from IPython.core.debugger import set_trace
import importlib

import pyflann

from masif_modules.compute_input_feat import compute_input_feat
from default_config.masif_opts import masif_opts


params = masif_opts['ppi_search']

if sys.argv[1] > 0:
    custom_params_file = sys.argv[1]
    custom_params = importlib.import_module(custom_params_file, package=None)
    custom_params = custom_params.custom_params

    for key in custom_params: 
        print('Setting {} to {} '.format(key, custom_params[key]))
        params[key] = custom_params[key]

if 'pids' not in params: 
    params['pids'] = ['p1', 'p2']


# Read the positive first 
parent_in_dir = params['masif_precomputation_dir']

binder_rho_wrt_center = []
binder_theta_wrt_center = []
binder_input_feat = []
binder_mask = []

pos_rho_wrt_center = []
pos_theta_wrt_center = []
pos_input_feat = []
pos_mask = []

neg_rho_wrt_center = []
neg_theta_wrt_center = []
neg_input_feat = []
neg_mask = []

np.random.seed(0)
training_idx = []
val_idx = []
test_idx = []
pos_names = []
neg_names = []

training_list = [x.rstrip() for x in open(params['training_list']).readlines()]
testing_list = [x.rstrip() for x in open(params['testing_list']).readlines()]

idx_count = 0
for count, ppi_pair_id in enumerate(os.listdir(parent_in_dir)):
    if ppi_pair_id not in testing_list and ppi_pair_id not in training_list:
        continue
    in_dir = parent_in_dir + ppi_pair_id+'/'
    print(ppi_pair_id)

    # Read binder and pos.
    train_val = np.random.random()
    # Read binder first, which is p1.
    try:
        labels = np.load(in_dir+'p1'+'_sc_labels.npy')
        # Take the median of the percentile 25 shape complementarity.
        mylabels = labels[0]
        labels = np.median(mylabels, axis=1)
            
    except Exception, e:
        print('Could not open '+in_dir+'p1'+'_sc_labels.npy: '+str(e))
        continue

    # pos_labels: points > max_sc_filt and >  min_sc_filt.
    pos_labels = np.where((labels < params['max_sc_filt']) & (labels > params['min_sc_filt'])) [0]
    K = int(params['pos_surf_accept_probability']*len(pos_labels))
    if K < 1: 
        continue
    l = range(len(pos_labels))
    np.random.shuffle(l)
    l = l[:K] 
    l = pos_labels[l]

    X1 = np.load(in_dir+'p1'+'_X.npy')
    Y1 = np.load(in_dir+'p1'+'_Y.npy')
    Z1 = np.load(in_dir+'p1'+'_Z.npy')
    v1 = np.stack([X1[l],Y1[l],Z1[l]], axis=1)

    X2 = np.load(in_dir+'p2'+'_X.npy')
    Y2 = np.load(in_dir+'p2'+'_Y.npy')
    Z2 = np.load(in_dir+'p2'+'_Z.npy')
    v2 = np.stack([X2,Y2,Z2], axis=1)

    # For each point in v1, find the closest point in v2.
    flann = pyflann.FLANN()
    r,d = flann.nn(v2, v1)
    d = np.sqrt(d)
    # Contact points: those within a cutoff distance.
    contact_points = np.where(d < params['pos_interface_cutoff'])[0]
    k1 = l[contact_points]
    k2 = r[contact_points]

    # For negatives, get points in v2 far from p1.
    try:
        rneg,dneg = flann.nn(v1, v2)
    except:
        set_trace()
    k_neg2 = np.where(dneg > params['pos_interface_cutoff'])[0]



    assert len(k1) == len(k2) 
    n_pos = len(k1)

    pid = 'p1' # Binder is p1
    for ii in k1:
        pos_names.append('{}_{}_{}'.format(ppi_pair_id, pid, ii))

    rho_wrt_center = np.load(in_dir+pid+'_rho_wrt_center.npy')
    theta_wrt_center = np.load(in_dir+pid+'_theta_wrt_center.npy')
    input_feat = np.load(in_dir+pid+'_input_feat.npy')
    mask = np.load(in_dir+pid+'_mask.npy')

    binder_rho_wrt_center.append(rho_wrt_center[k1])
    binder_theta_wrt_center.append(theta_wrt_center[k1])
    binder_input_feat.append(input_feat[k1])
    binder_mask.append(mask[k1])

    # Read pos, which is p2.
    pid = 'p2'
    
    # Read as positives those points.
    rho_wrt_center = np.load(in_dir+pid+'_rho_wrt_center.npy')
    theta_wrt_center = np.load(in_dir+pid+'_theta_wrt_center.npy')
    input_feat = np.load(in_dir+pid+'_input_feat.npy')
    mask = np.load(in_dir+pid+'_mask.npy')
    pos_rho_wrt_center.append(rho_wrt_center[k2])
    pos_theta_wrt_center.append(theta_wrt_center[k2])
    pos_input_feat.append(input_feat[k2])
    pos_mask.append(mask[k2])

    # Get a set of negatives from  p2. 
    np.random.shuffle(k_neg2)
    k_neg2 = k_neg2[:(len(k2))]
    assert(len(k_neg2) == n_pos)
    neg_rho_wrt_center.append(rho_wrt_center[k_neg2])
    neg_theta_wrt_center.append(theta_wrt_center[k_neg2])
    neg_input_feat.append(input_feat[k_neg2])
    neg_mask.append(mask[k_neg2]) 
    for ii in k_neg2:
        neg_names.append('{}_{}_{}'.format(ppi_pair_id, pid, ii))


    # Training, validation or test?
    if ppi_pair_id in training_list:
        if train_val <= params['range_val_samples']:
            training_idx = training_idx + range(idx_count, idx_count+n_pos)
        elif train_val > params['range_val_samples']: 
            val_idx = val_idx + range(idx_count, idx_count+n_pos)
    else: 
        test_idx = test_idx + range(idx_count, idx_count+n_pos)
    idx_count += n_pos

if not os.path.exists(params['cache_dir']):
    os.makedirs(params['cache_dir'])

binder_rho_wrt_center = np.concatenate(binder_rho_wrt_center, axis=0)
binder_theta_wrt_center = np.concatenate(binder_theta_wrt_center, axis=0)
binder_input_feat = np.concatenate(binder_input_feat, axis=0)
binder_mask = np.concatenate(binder_mask, axis=0)

pos_rho_wrt_center = np.concatenate(pos_rho_wrt_center, axis=0)
pos_theta_wrt_center = np.concatenate(pos_theta_wrt_center, axis=0)
pos_input_feat = np.concatenate(pos_input_feat, axis=0)
pos_mask = np.concatenate(pos_mask, axis=0)
np.save(params['cache_dir']+'/pos_names.npy', pos_names)

neg_rho_wrt_center = np.concatenate(neg_rho_wrt_center, axis=0)
neg_theta_wrt_center = np.concatenate(neg_theta_wrt_center, axis=0)
neg_input_feat = np.concatenate(neg_input_feat, axis=0)
neg_mask = np.concatenate(neg_mask, axis=0)
np.save(params['cache_dir']+'/neg_names.npy', neg_names)

print("Read {} negative shapes".format(len(neg_rho_wrt_center)))
print("Read {} positive shapes".format(len(pos_rho_wrt_center)))
np.save(params['cache_dir']+'/binder_rho_wrt_center.npy', binder_rho_wrt_center)
np.save(params['cache_dir']+'/binder_theta_wrt_center.npy', binder_theta_wrt_center)
np.save(params['cache_dir']+'/binder_input_feat.npy', binder_input_feat)
np.save(params['cache_dir']+'/binder_mask.npy', binder_mask)

np.save(params['cache_dir']+'/pos_training_idx.npy', training_idx)
np.save(params['cache_dir']+'/pos_val_idx.npy', val_idx)
np.save(params['cache_dir']+'/pos_test_idx.npy', test_idx)
np.save(params['cache_dir']+'/pos_rho_wrt_center.npy', pos_rho_wrt_center)
np.save(params['cache_dir']+'/pos_theta_wrt_center.npy', pos_theta_wrt_center)
np.save(params['cache_dir']+'/pos_input_feat.npy', pos_input_feat)
np.save(params['cache_dir']+'/pos_mask.npy', pos_mask)

np.save(params['cache_dir']+'/neg_training_idx.npy', training_idx)
np.save(params['cache_dir']+'/neg_val_idx.npy', val_idx)
np.save(params['cache_dir']+'/neg_test_idx.npy', test_idx)
np.save(params['cache_dir']+'/neg_rho_wrt_center.npy', neg_rho_wrt_center)
np.save(params['cache_dir']+'/neg_theta_wrt_center.npy', neg_theta_wrt_center)
np.save(params['cache_dir']+'/neg_input_feat.npy', neg_input_feat)
np.save(params['cache_dir']+'/neg_mask.npy', neg_mask)
np.save(params['cache_dir']+'/neg_names.npy', neg_names)


