# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
import numpy as np
import sys
import astropy.io.fits as fits
import tdose_utilities as tu
import tdose_modify_cube as tmc
import time
import os
import pdb
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
def perform_modification(setupfile='./tdose_setup_template_modify.txt',clobber=False,verbose=True):
    """
    Modify a data cube using the information stored in a generated TDOSE source model cube.

    --- INPUT ---
    setupfile       TDOSE modification setup file. Template can be generated
                    with tdose_utilities.generate_setup_template_modify()
    clobber         Overwrite existing output?
    verbose         Toggle verbosity

    --- EXAMPLE OF USE ---
    import tdose_modify_cube as tmc
    setupfile = './tdose_setup_template_modify.txt'
    tmc.perform_modification(setupfile=setupfile)

    """

    start_time = time.clock()
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print('==================================================================================================')
    if verbose: print(' TDOSE: Loading setup                                       '+\
                      '      ( Total runtime = '+str("%10.4f" % (time.clock() - start_time))+' seconds )')

    setupdic        = tu.load_setup(setupfile,verbose=verbose)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print('==================================================================================================')
    if verbose: print(' TDOSE: Logging setup                                       '+\
                      '      ( Total runtime = '+str("%10.4f" % (time.clock() - start_time))+' seconds )')

    setuplog = setupdic['modified_cube_dir']+setupfile.split('/')[-1].replace('.txt','_logged.txt')
    if os.path.isfile(setuplog) & (clobber == False):
        if verbose: print(' - WARNING Logged setupfile exists and clobber = False. Not storing setup ')
    else:
        if verbose: print(' - Writing setup and command to spec1D_directory to log extraction setup and command that was run')
        setupinfo    = open(setupfile,'r')
        setupcontent = setupinfo.read()
        setupinfo.close()

        cmdthatwasrun = "import tdose_modify_cube as tmc; tmc.perform_modification(setupfile='%s',clobber=%s,verbose=%s)" % \
                        (setuplog,clobber,verbose)

        loginfo = open(setuplog, 'w')
        loginfo.write("# The setup file appended below was run with the command: \n# "+cmdthatwasrun+
                      " \n# on "+tu.get_now_string()+'\n# ')

        loginfo.write(setupcontent)
        loginfo.close()

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print('==================================================================================================')
    if verbose: print(' TDOSE: Modifying data cube                                 '+\
                      '      ( Total runtime = '+str("%10.4f" % (time.clock() - start_time))+' seconds )')

    savestring = 'satelitesremoved'

    if setupdic['sources_action'].lower() == 'remove':
        removing = True
    elif setupdic['sources_action'].lower() == 'keep':
        removing = False
    else:
        if verbose: print(' - WARNING "sources_action" keyword in setup ('+setupdic['sources_action']+') is invalid. Removing source.')
        removing = True

    modified_cube = tmc.remove_object(setupdic['data_cube'],setupdic['source_model_cube'],
                                      objects=setupdic['modify_sources_list'],remove=removing,
                                      dataext=setupdic['cube_extension'],
                                      sourcemodelext=setupdic['source_extension'],savecube=setupdic['modified_cube'],
                                      savedir=setupdic['modified_cube_dir'],clobber=clobber,verbose=verbose)

# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
def remove_object(datacube,sourcemodelcube,objects=[1,3],remove=True,dataext=1,sourcemodelext=1,
                  savecube=False,savedir=None,clobber=False,verbose=True):
    """
    Use source model cube to remove object(s) from data cube

    --- INPUT ---
    datacube            Datacube to modify
    sourcemodelcube     Source model cube of data cube defining models of each source in the datacube
    objects             The objects to remove from data cube. Provide number of source sub-cube in
                        "sourcemodelcube".
    remove              If true objects in "objects" will be removed from "datacube". If remove=False
                        everything but the objects listed in "objects" will be removed.
    dataext             Extension of datacube containing actual data
    sourcemodelext      Extension of source model cube containing the models
    savecube            If a string is provided the modified cube will be stored in a new fits file
                        appending the provided string to the data cube file name.
    savedir             If a directory path is provided, the modified cube will be stored here. Otherwise
                        it will be stored at the same location as the datacube.
    clobber             If true any existing fits file will be overwritten if modified cube is saved
    verbose             Toggle verbosity

    --- EXAMPLE OF USE ---
    import tdose_modify_cube

    datacube        = 'datacube_spectra_are_extracted_from.fits'
    sourcemodelcube = 'tdose_source_modelcube.fits'

    modified_cube   = tdose_modify_cube.remove_object(datacube,sourcemodelcube,savecube='source1and3removed')


    """
    if verbose: print(' - Loading data and source model cubes ')
    datacubehdu     = fits.open(datacube)
    dataarr         = datacubehdu[dataext].data
    dataarr_hdr     = datacubehdu[dataext].header

    sourcemodelhdu  = fits.open(sourcemodelcube)
    sourcemodel     = sourcemodelhdu[sourcemodelext].data
    sourcemodel_hdr = sourcemodelhdu[sourcemodelext].header
    sourcemodelhdu.close()

    Nmodels         = sourcemodel.shape[0]
    models          = np.arange(Nmodels)

    if verbose: print(' - Check that all objects indicated are present in source model cube')
    objects  = np.asarray(objects)

    maxobj = np.max(np.abs(objects))
    if maxobj >= Nmodels:
        sys.exit(' ---> Object model "'+str(maxobj)+'" is not included in source model cube (models start at 0) ')
    else:
        if verbose: print(('   All object models appear to be included in the '+str(Nmodels)+' source models found in cube'))

    if verbose: print(' - Determining objects (source models) to remove from data cube ')
    if remove:
        obj_remove = objects
        obj_keep   = np.setdiff1d(models,obj_remove)
    else:
        obj_keep   = objects
        obj_remove = np.setdiff1d(models,obj_keep)

    remove_cube = np.sum(sourcemodel[obj_remove.astype(int),:,:,:],axis=0)

    modified_cube = dataarr - remove_cube

    if savecube:
        datacubehdu[dataext].data = modified_cube # Replacing original data with modified cube
        if savedir is None:
            outname = datacube.replace('.fits','_'+str(savecube)+'.fits')
        else:
            outname = savedir+datacube.split('/')[-1].replace('.fits','_'+str(savecube)+'.fits')
        if verbose: print((' - Saving modified cube to \n   '+outname))
        if verbose: print('   (Using datacube header with modification keywords appended) ')
        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        # hducube = fits.PrimaryHDU(modified_cube)       # default HDU with default minimal header
        # hducube.header = dataarr_hdr

        # adding hdrkeys:   '---KEY--',                       '----------------MAX LENGTH COMMENT-------------'
        dataarr_hdr.append(('MODIFIED',                'True','Cube is modified with tdose_modify_cube.py?'),end=True)
        dataarr_hdr.append(('MODTIME ',   tu.get_now_string(),'Date and time of cube modification'),end=True)
        dataarr_hdr.append(('SMC     ',       sourcemodelcube,'Name of Source Model Cube'),end=True)
        dataarr_hdr.append(('NREMOVE ',       len(obj_remove),'Number of sources removed from cube'),end=True)
        dataarr_hdr.append(('NKEEP   ',         len(obj_keep),'Number of sources kept in cube'),end=True)
        dataarr_hdr.append(('SREMOVE ',','.join([str(oo) for oo in obj_remove])),'Source indexes removed',end=True)
        dataarr_hdr.append(('SKEEP   ',','.join([str(oo) for oo in obj_keep])),'Source indexes kept',end=True)
        # dataarr_hdr.append(('COMMENT ','Source indexes removed:'+','.join([str(oo) for oo in obj_remove])),end=True)
        # dataarr_hdr.append(('COMMENT ','Source indexes kept:'+','.join([str(oo) for oo in obj_keep])),end=True)

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        datacubehdu.writeto(outname,overwrite=clobber)

    return modified_cube

# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =