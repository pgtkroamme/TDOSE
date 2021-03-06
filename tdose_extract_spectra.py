# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
import numpy as np
import sys
import astropy.io.fits as afits
import collections
import tdose_utilities as tu
import tdose_extract_spectra as tes
import tdose_build_mock_cube as tbmc
import pdb
import scipy.ndimage.filters as snf
import matplotlib as mpl
mpl.use('Agg') # prevent pyplot from opening window; enables closing ssh session with detached screen running TDOSE
import matplotlib.pyplot as plt
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
def extract_spectra(model_cube_file,source_association_dictionary=None,nameext='tdose_spectrum',outputdir='./',clobber=False,
                    variance_cube_file=None,variance_cube_ext='ERROR',source_model_cube_file=None,source_cube_ext='DATA',
                    model_cube_ext='DATA',layer_scale_ext='WAVESCL',data_cube_file=None,verbose=True):
    """
    Assemble the spectra determined by the wavelength layer scaling of the normalized models
    when generating the source model cube

    --- INPUT ---
    model_cube_file                     Model cube to base extraction on (using header info and layer scales)
    source_association_dictionary       Source association dictionary defining what sources should be combined into
                                        objects (individual spectra).
    nameext                             The name extension to use for saved spectra
    outputdir                           Directory to save spectra to
    clobber                             Overwrite spectra if they already exists
    variance_cube_file                  File containing variance cube of data to be used to estimate nois on 1D spectrum
    variance_cube_ext                   Extension of variance cube to use
    source_model_cube_file              The source model cube defining the individual sources
    source_cube_ext                     Extension of source model cube file that contins source models
    model_cube_ext                      Extension of model cube file that contains model
    layer_scale_ext                     Extension of model cube file that contains the layer scales
    data_cube_file                      File containing original data cube used for extraction of aperture spectra
    verbose

    --- EXAMPLE OF USE ---


    """
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print(' - Loading data needed for spectral assembly')
    model_cube        = afits.open(model_cube_file)[model_cube_ext].data
    model_cube_hdr    = afits.open(model_cube_file)[model_cube_ext].header
    layer_scale_arr   = afits.open(model_cube_file)[layer_scale_ext].data
    if variance_cube_file is not None:
        stddev_cube       = np.sqrt(afits.open(variance_cube_file)[variance_cube_ext].data) # turn varinace into standard deviation
        source_model_cube = afits.open(source_model_cube_file)[source_cube_ext].data
    else:
        stddev_cube       = None
        source_model_cube = None
    Nsources = layer_scale_arr.shape[0]

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if data_cube_file is not None:
        if verbose: print(' - Loading data cube ')
        data_cube  = afits.open(data_cube_file)[model_cube_ext].data
    else:
        data_cube  = None

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if source_association_dictionary is None:
        if verbose: print(' - Building default source association dictionary ' \
                          '(determining what sources are combined into objects), i.e., one source per object ')
        sourcIDs_dic = collections.OrderedDict()
        for oo in np.arange(int(Nsources)):
            sourcIDs_dic[str(oo)] = [oo]
    else:
        sourcIDs_dic = source_association_dictionary
    Nobj = len(list(sourcIDs_dic.keys()))
    if verbose: print(' - Found '+str(Nobj)+' objects to generate spectra for in source_association_dictionary ')

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print(' - Assembling wavelength vector for spectra ')
    wavelengths     =  np.arange(model_cube_hdr['NAXIS3'])*model_cube_hdr['CD3_3']+model_cube_hdr['CRVAL3']
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    specfiles = []
    for oo, key in enumerate(sourcIDs_dic.keys()):
        obj_cube_hdr = model_cube_hdr.copy()
        try:
            specid       = str("%.10d" % int(key))
        except:
            specid       = str(key)
        specname     = outputdir+nameext+'_'+specid+'.fits'
        specfiles.append(specname)
        sourceIDs    = sourcIDs_dic[key]

        obj_cube_hdr.append(('OBJID   ',specid         ,'ID of object'),end=True)
        obj_cube_hdr.append(('SRCIDS  ',str(sourceIDs) ,'IDs of sources combined in object'),end=True)

        if verbose:
            infostr = ' - Extracting spectrum '+str("%6.f" % (oo+1))+' / '+str("%6.f" % Nobj)
            sys.stdout.write("%s\r" % infostr)
            sys.stdout.flush()

        sourceoutput = tes.extract_spectrum(sourceIDs,layer_scale_arr,wavelengths,noise_cube=stddev_cube,
                                            source_model_cube=source_model_cube, data_cube=data_cube,
                                            specname=specname,obj_cube_hdr=obj_cube_hdr,clobber=clobber,verbose=True)

    if verbose: print('\n - Done extracting spectra. Returning list of fits files generated')
    return specfiles
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
def extract_spectrum(sourceIDs,layer_scale_arr,wavelengths,noise_cube=None,source_model_cube=None,
                     specname='tdose_extract_spectra_extractedspec.fits',obj_cube_hdr=None,data_cube=None,
                     clobber=False,verbose=True):
    """
    Extracting a spectrum based on the layer scale image from the model cube provided a list of sources to combine.
    Noise is estimated from the noise cube (of the data)

    If all layer_scales are 1 a data_cube for the extractions is expected

    --- INPUT ---
    sourceIDs         The source IDs to combine into spectrum
    layer_scale_arr   Layer scale array (or image) produced when generating the model cube
                      fractional flux belonging to the source in each pixel
    wavelengths       Wavelength vector to use for extracted 1D spectrum.
    noise_cube        Cube with uncertainties (sqrt(variance)) of data cube to be used for estimating 1D uncertainties
                      To estimate S/N and 1D noise, providing a source model cube is required
    source_model_cube Source model cube containing the model cube for each individual source seperately
                      Needed in order to estimate noise from noise-cube
    specname          Name of file to save spectrum to
    obj_cube_hdr      Provide a template header to save the object cube (from combining the individual source cube)
                      as an extension to the extracted spectrum
    data_cube         In case all layers scales are 1, it is assumed that the source_model_cube contains a mask for the
                      spectral extraction, which will then be performed on this data_cube.
    clobber           To overwrite existing files set clobber=True
    verbose           Toggle verbosity

    --- EXAMPLE OF USE ---


    """
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print(' - Checking shape of wavelengths and layer_scale_arr')
    if wavelengths.shape[0] != layer_scale_arr.shape[1]:
        sys.exit(' ---> Shape of wavelength vector ('+str(wavelengths.shape)+
                 ') and wavelength dimension of layer scale array ('+
                 layer_scale_arr.shape[1].shape+') do not match.')
    else:
        if verbose: print('   dimensions match; proceeding...')
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print(' - Checking all sources have spectra in layer_scale_arr')
    maxsource = np.max(sourceIDs)
    if maxsource >= layer_scale_arr.shape[0]:
        sys.exit(' ---> Sources in list '+str(str(sourceIDs))+
                 ' not available among '+str(layer_scale_arr.shape[0])+' sources in layer_scale_arr.')
    else:
        if verbose: print('   All sources exist in layer_scale_arr; proceeding...')
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print(' - Assembling object spectrum from source scaling')
    source_ent = np.asarray(sourceIDs).astype(int)

    if (layer_scale_arr == 1).all():
        if verbose: print(' - All layer scales are 1; assuming source model cube contain mask for spectral extraction')
        object_cube  = np.sum(np.abs(source_model_cube[source_ent,:,:]),axis=0)
        if data_cube is None:
            sys.exit(' ---> Did not find a data cube to extrac spectra from as expected')

        object_mask     = (object_cube == 0) # masking all zeros in object mask
        invalid_mask    = np.ma.masked_invalid(data_cube).mask
        comb_mask       = (invalid_mask | object_mask)
        spec_1D_masked  = np.sum(np.sum(  np.ma.array(data_cube,mask=comb_mask)  ,axis=1),axis=1)
        spec_1D         = spec_1D_masked.filled(fill_value=0.0)

        if noise_cube is not None:
            if verbose: print('   Calculating noise as d_spec_k = sqrt( SUMij d_pix_ij**2 ), i.e., as the sqrt of variances summed')
            invalid_mask_noise = np.ma.masked_invalid(noise_cube).mask
            comb_mask          = (comb_mask | invalid_mask_noise)
            variance_1D_masked = np.ma.array(noise_cube,mask=comb_mask)**2
            noise_1D_masked    = np.sqrt( np.sum( np.sum( variance_1D_masked, axis=1), axis=1) )
            noise_1D           = noise_1D_masked.filled(fill_value=np.nan)

            if verbose: print('   Generating S/N vector')
            SN_1D         = spec_1D / noise_1D
        else:
            if verbose: print(' - No "noise_cube" provided. Setting all errors and S/N values to NaN')
            SN_1D    = np.zeros(spec_1D.shape)*np.NaN
            noise_1D = np.zeros(spec_1D.shape)*np.NaN
    else:
        if verbose: print(' - Some layer scales are different from 1; hence assembling spectra using layer scales')
        if len(source_ent) < 1:
            spec_1D   = layer_scale_arr[source_ent,:]
        else:
            spec_1D   = np.sum( layer_scale_arr[source_ent,:],axis=0)

        # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
        if noise_cube is not None:
            if verbose: print(' - Estimate S/N at each wavelength for 1D spectrum (see Eq. 16 of Kamann+2013)')
            if verbose: print('   Estimating fraction of flux in each pixel wrt. total flux in each layer')
            object_cube    = np.sum((source_model_cube[source_ent,:,:,:]),axis=0) # summing source models for all source IDs

            fluxfrac_cube_sents = np.zeros(source_model_cube.shape[1:])
            for sent in source_ent:
                object_cube_sent      = np.sum((source_model_cube[[sent],:,:,:]),axis=0) # getting source model for model 'sent'
                fluxscale1D_sent      = layer_scale_arr[sent,:]
                fluxfrac_cube_sent    = object_cube_sent / fluxscale1D_sent[:,None,None]
                fluxfrac_cube_sents   = fluxfrac_cube_sents + fluxfrac_cube_sent
            fluxfrac_cube = fluxfrac_cube_sents / len(source_ent) # renormalizing flux-fraction cube

            if verbose: print('   Defining pixel mask (ignoring NaN pixels) ') #+\
            #                  'and pixels with <'+str(fluxfrac_min)+' of total pixel flux in model cube) '
            # pix_mask      = (fluxfrac_cube < fluxfrac_min)
            invalid_mask1 = np.ma.masked_invalid(fluxfrac_cube).mask
            invalid_mask2 = np.ma.masked_invalid(noise_cube).mask

            # combining mask making sure all individual mask pixels have True for it to be true in combined mask
            comb_mask     = (invalid_mask1 | invalid_mask2) # | pix_mask

            if verbose: print('   Calculating noise propogated as d_spec_k = 1/sqrt( SUMij (fluxfrac_ij**2 / d_pix_ij**2) )')
            squared_ratio     = np.ma.array(fluxfrac_cube,mask=comb_mask)**2 / np.ma.array(noise_cube,mask=comb_mask)**2

            inv_noise_masked  = np.sqrt( np.sum( np.sum( squared_ratio, axis=1), axis=1) )
            noise_1D          = (1.0/inv_noise_masked).filled(fill_value=0.0)
            if verbose: print('   Generating S/N vector')
            SN_1D         = spec_1D / noise_1D
        else:
            if verbose: print(' - No "noise_cube" provided. Setting all errors and S/N values to NaN')
            SN_1D    = np.zeros(spec_1D.shape)*np.NaN
            noise_1D = np.zeros(spec_1D.shape)*np.NaN

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print(' - Saving extracted 1D spectrum and source cube to \n   '+specname)
    mainHDU = afits.PrimaryHDU()       # primary HDU
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    c1 = afits.Column(name='wave',      format='D', unit='ANGSTROMS', array=wavelengths)
    c2 = afits.Column(name='flux',      format='D', unit='', array=spec_1D)
    c3 = afits.Column(name='fluxerror', format='D', unit='', array=noise_1D)
    c4 = afits.Column(name='s2n',       format='D', unit='', array=SN_1D)

    coldefs = afits.ColDefs([c1,c2,c3,c4])
    th = afits.BinTableHDU.from_columns(coldefs) # creating default header

    # writing hdrkeys:'---KEY--',                             '----------------MAX LENGTH COMMENT-------------'
    th.header.append(('EXTNAME ','SPEC1D'                     ,'cube containing source'),end=True)
    head    = th.header

    tbHDU  = afits.BinTableHDU.from_columns(coldefs, header=head)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if obj_cube_hdr is not None:
        objHDU        = afits.ImageHDU(object_cube)
        for hdrkey in list(obj_cube_hdr.keys()):
            if not hdrkey in list(objHDU.header.keys()):
                objHDU.header.append((hdrkey,obj_cube_hdr[hdrkey],obj_cube_hdr.comments[hdrkey]),end=True)

        try:
            objHDU.header.append(('EXTNAMEC',objHDU.header['EXTNAME'] ,'EXTNAME of original source cube'),end=True)
            del objHDU.header['EXTNAME']
        except:
            pass

        objHDU.header.append(('EXTNAME ','SOURCECUBE'            ,'cube containing source'),end=True)

        hdulist = afits.HDUList([mainHDU,tbHDU,objHDU])
    else:
        hdulist = afits.HDUList([mainHDU,tbHDU])
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    hdulist.writeto(specname, overwrite=clobber)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    return wavelengths, spec_1D, noise_1D, object_cube
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
def extract_spectra_viasourcemodelcube(datacube,sourcemodelcube,wavelengths,speclist,specids='None',outputdir='./',
                                       noisecube=False,sourcemodel_hdr='None',verbose=True):
    """
    Wrapper for tes.extract_spectrum_viasourcemodelcube() to extract mutliple spectra

    --- INPUT ----
    datacube          Datacube to extract spectra from
    sourcemodelcube   Cube containing the source models for each object used as "extraction cube"
                      Dimensions should be [Nsources,datacube.shape]
    wavelengths       Wavelength vector to use for extracted 1D spectrum.
    speclist          List of spectra to extract. Indexes corresponding to the source models in the
                      sourcemodlecube
    specids           List of IDs to use in naming of output for source models referred to in "speclist"
    outputdir         Directory to store spectra to
    noisecube         Cube with uncertainties (sqrt(variance)) of data cube to be used in extraction
    souremodel_hdr    If not 'None' provide a basic fits header for the source model cubes extracted
                      and they will be appended to the individual output fits file containing the extracted
                      spectra.
    verbose           Toggle verbosity

    --- EXAMPLE OF USE ---

    """
    if verbose: print(' - Check that source models indicated are present in source model cube ')
    specnames  = []
    Nmodels    = sourcemodelcube.shape[0]
    maxobj     = np.max(speclist)
    if maxobj >= Nmodels:
        sys.exit(' ---> Object model "'+str(maxobj)+'" is not included in source model cube (models start at 0)')
    else:
        if verbose: print('   All object models appear to be included in the '+str(Nmodels)+' source models found in cube')

    if datacube.shape != sourcemodelcube[0].shape:
        sys.exit(' ---> Shape of datacube ('+str(datacube.shape)+') and shape of source models ('+
                 sourcemodelcube[0].shape+') do not match.')

    sourcemodel_sum = np.sum(sourcemodelcube,axis=0)
    for ss, spec in enumerate(speclist):
        if specids == 'None':
            specid = spec
        else:
            specid = specids[ss]

        specname = outputdir+'tdose_spectrum_'+str("%.12d" % specid)+'.fits'
        specnames.append(specname)

        sourcemodel     = sourcemodelcube[spec,:,:,:]
        sourceweights   = sourcemodel/sourcemodel_sum  # fractional flux of model for given source in each pixel
        sourcemodel_hdr.append(('OBJMODEL',spec      ,'Source model number in parent source model cube'),end=True)
        sourcemodel_hdr.append(('OBJID   ',specid    ,'ID of source'),end=True)

        if verbose:
            infostr = ' - Extracting spectrum '+str("%6.f" % (spec+1))+' / '+str("%6.f" % len(speclist))
            sys.stdout.write("%s\r" % infostr)
            sys.stdout.flush()

        sourceoutput = tes.extract_spectrum_viasourcemodelcube(datacube,sourceweights,wavelengths,specname=specname,
                                                               noisecube=noisecube,spec1Dmethod='sum',
                                                               sourcecube_hdr=sourcemodel_hdr,verbose=verbose)

    if verbose: print('\n - Done extracting spectra. Returning list of fits files containing spectra')
    return specnames
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
def extract_spectrum_viasourcemodelcube(datacube,sourceweights,wavelengths,
                                        specname='tdose_extract_spectra_extractedspec.fits',
                                        noisecube=None,spec1Dmethod='sum',sourcecube_hdr='None',verbose=True):
    """
    Extracting a spectrum from a data cube given a source model (cube) to be used as 'extraction cube'

    --- INPUT ---
    datacube          Datacube to extract spectra from
    sourceweights     Weights from source model to use as "extraction cube". The weights should contain the
                      fractional flux belonging to the source in each pixel
    wavelengths       Wavelength vector to use for extracted 1D spectrum.
    specname          Name of spectrum to generate
    noisecube         Cube with uncertainties (sqrt(variance)) of data cube to be used in extraction
    spec1Dmethod      Method used to extract 1D spectrum from source cube with
    sourcecube_hdr    If not 'None' provide a fits header for the source cube and it ill be appended to the
                      output fits file.
    verbose           Toggle verbosity

    --- EXAMPLE OF USE ---


    """
    if verbose: print(' - Checking shape of data and source model cubes')

    if datacube.shape != sourceweights.shape:
        sys.exit(' ---> Shape of datacube ('+str(datacube.shape)+') and source weights ('+
                 sourceweights.shape+') do not match.')
    else:
        if verbose: print('   dimensions match; proceeding with extraction ')
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print(' - Applying weights to "datacube" to obtain source cube ')
    sourcecube     = datacube*sourceweights

    if noisecube is not None:
        if verbose: print(' - Using "noisecube" for error propagation ')
        datanoise = noisecube
    else:
        if verbose: print(' - No "noisecube" provided. Setting all errors to 1')
        datanoise = np.ones(datacube.shape)

    if verbose: print(' - Assuming uncertainty on source weights equals the datanoise when propgating errors')
    sourceweights_err = datanoise
    sourcecube_err    = sourcecube * np.sqrt( (datanoise/datacube)**2 + (sourceweights_err/sourceweights)**2 )

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print(' - Generating 1D spectrum from source cube via:')
    spec_wave   = wavelengths
    maskinvalid = np.ma.masked_invalid(sourcecube * sourcecube_err).mask
    if spec1Dmethod == 'sum':
        if verbose: print('   Simple summation of fluxes in sourcecube.')
        spec_flux = np.sum(np.sum(np.ma.array(sourcecube,mask=maskinvalid),axis=1),axis=1).filled()
        if verbose: print('   Errors are propagated as sum of squares.')
        spec_err  = np.sqrt( np.sum( np.sum(np.ma.array(sourcecube_err,mask=maskinvalid)**2,axis=1),axis=1) ).filled()
    elif spec1Dmethod == 'sum_SNweight':
        pdb.set_trace()
    else:
        sys.exit(' ---> The chosen spec1Dmethod ('+str(spec1Dmethod)+') is invalid')

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print(' - Saving extracted 1D spectrum and source cube to \n   '+specname)
    mainHDU = afits.PrimaryHDU()       # primary HDU
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    c1 = afits.Column(name='wave', format='D', unit='ANGSTROMS', array=spec_wave)
    c2 = afits.Column(name='flux', format='D', unit='', array=spec_flux)
    c3 = afits.Column(name='fluxerror', format='D', unit='', array=spec_err)

    coldefs = afits.ColDefs([c1,c2,c3])
    th = afits.BinTableHDU.from_columns(coldefs) # creating default header

    # writing hdrkeys:'---KEY--',                             '----------------MAX LENGTH COMMENT-------------'
    th.header.append(('EXTNAME ','SPEC1D'                     ,'cube containing source'),end=True)
    th.header.append(('SPECMETH' , spec1Dmethod               ,'Method used for spectral extraction'),end=True)
    head    = th.header

    tbHDU  = afits.BinTableHDU.from_columns(coldefs, header=head)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if sourcecube_hdr != 'None':
        sourceHDU        = afits.ImageHDU(sourcecube)       # default HDU with default minimal header
        for hdrkey in list(sourcecube_hdr.keys()):
            if not hdrkey in list(sourceHDU.header.keys()):
                sourceHDU.header.append((hdrkey,sourcecube_hdr[hdrkey],sourcecube_hdr.comments[hdrkey]),end=True)

        sourceHDU.header.append(('EXTNAME ','SOURCECUBE'            ,'cube containing source'),end=True)

        hdulist = afits.HDUList([mainHDU,tbHDU,sourceHDU])
    else:
        hdulist = afits.HDUList([mainHDU,tbHDU])
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

    hdulist.writeto(specname, overwrite=True)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    return sourcecube, sourcecube_err, spec_wave, spec_flux, spec_err
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
def plot_1Dspecs(filelist,plotname='./tdose_1Dspectra.pdf',colors=None,labels=None,plotSNcurve=False,
                 tdose_wavecol='wave',tdose_fluxcol='flux',tdose_errcol='fluxerror',
                 simsources=None,simsourcefile='/Users/kschmidt/work/TDOSE/mock_cube_sourcecat161213_all.fits',
                 sim_cube_dim=None,comparisonspecs=None,comp_colors=['blue'],comp_labels=None,
                 comp_wavecol='WAVE_AIR',comp_fluxcol='FLUX',comp_errcol='FLUXERR',
                 xrange=None,yrange=None,showspecs=False,shownoise=True,
                 skyspecs=None,sky_colors=['red'],sky_labels=['sky'],
                 sky_wavecol='lambda',sky_fluxcol='data',sky_errcol='stat',
                 showlinelists=None,linelistcolors=['gray'],smooth=0,ylog=False,
                 plotratio=False,
                 verbose=True,pubversion=False):
    """
    Plots of multiple 1D spectra

    --- INPUT ---
    filelist            List of spectra filenames to plot
    plotname            Name of plot to generate
    colors              Colors of the spectra in filelist to use
    labels              Labels of the spectra in filelist to use
    plotSNcurve         Show signal-to-noise curve instead of flux spectra
    tdose_wavecol       Wavelength column of the spectra in filelist
    tdose_fluxcol       Flux column of the spectra in filelist
    tdose_errcol        Flux error column of the spectra in filelist
    simsources          To plot simulated sources provide ids here
    simsourcefile       Source file with simulated sources to plot
    sim_cube_dim        Dimensions of simulated cubes
    comparisonspecs     To plot comparison spectra provide the filenames of those here
    comp_colors         Colors of the spectra in comparisonspecs list to use
    comp_labels         Labels of the spectra in comparisonspecs list to use
    comp_wavecol        Wavelength column of the spectra in comparisonspecs list
    comp_fluxcol        Flux column of the spectra in comparisonspecs list
    comp_errcol         Flux error column of the spectra in comparisonspecs list
    xrange              Xrange of plot
    yrange              Yrange of plot
    showspecs           To show plot instead of storing it to disk set showspecs=True
    shownoise           To add noise envelope around spectrum set shownoise=True
    skyspecs            To plot sky spectra provide the filenames of those here
    sky_colors          Colors of the spectra in skyspecs list to use
    sky_labels          Labels of the spectra in skyspecs list to use
    sky_wavecol         Wavelength column of the spectra in skyspecs list
    sky_fluxcol         Flux column of the spectra in skyspecs list
    sky_errcol          Flux error column of the spectra in skyspecs list
    showlinelists       To show line lists provide a list of arrays of dimension (Nlines,2) where each row in the
                        arrays contains [waveobs, name], where 'waveobs' is the observed wavelengths and 'name' is
                        a string with the name of each of the Nlines postions to mark on the spectrum.
    linelistcolors      List of colors for line lists provided in showlinelists
    smooth              To smooth the spectra, provide sigma of the 1D gaussian smoothing kernel to apply.
                        For smooth = 0, no smoothing is performed.
    ylog                To plot y-axis in log scale set to true
    plotratio           To plot the ratio between the main spectrum and the comparison spectra instead of the actual
                        spectra, set this keyword to true.
    verbose             Toggle verbosity
    pubversion          Generate more publication friendly version of figure

    """
    if len(filelist) == 1:
        if verbose: print(' - Plotting data from '+filelist[0])
    else:
        if verbose: print(' - Plotting data from filelist ')

    if pubversion:
        fig = plt.figure(figsize=(6, 3))
        fig.subplots_adjust(wspace=0.1, hspace=0.1,left=0.15, right=0.95, bottom=0.18, top=0.83)
        Fsize  = 12
    else:
        fig = plt.figure(figsize=(10, 3))
        fig.subplots_adjust(wspace=0.1, hspace=0.1,left=0.06, right=0.81, bottom=0.15, top=0.95)
        Fsize  = 10

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    # Looking for flux units in spectra
    bunit = 'BUNIT FLUX' # Default BUNIT
    for unitspec in filelist:

        if bunit == 'BUNIT FLUX':
            try:
                sourcecubehdr = afits.open(unitspec)['SOURCECUBE'].header
                bunit         = sourcecubehdr['BUNIT']
            except:
                try: # Backwards compatibility to TDOSE v2.0 extractions
                    sourcecubehdr = afits.open(unitspec)[2].header
                    bunit         = sourcecubehdr['BUNIT']
                except:
                    pass
    if bunit == 'BUNIT FLUX':
        if verbose: print(' - Did not find BUNIT in SOURCECUBE header for any spectra in filelist - are they not from TDOSE?')

    if bunit == '10**(-20)*erg/s/cm**2/Angstrom': # Making bunit LaTeXy for MUSE-Wide BUNIT format
        bunit = '1e-20 erg/s/cm$^2$/\AA'
    else:
        bunit = '$'+bunit+'$' # minimizing pronlems with LaTeXing plot axes
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    lthick = 1
    plt.rc('text', usetex=True)
    plt.rc('font', family='serif',size=Fsize)
    plt.rc('xtick', labelsize=Fsize)
    plt.rc('ytick', labelsize=Fsize)
    plt.clf()
    plt.ioff()
    #plt.title(plotname.split('TDOSE 1D spectra'),fontsize=Fsize)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    for ff, specfile in enumerate(filelist):
        specdat = afits.open(specfile)[1].data

        if colors is None:
            spec_color = None
        else:
            spec_color = colors[ff]

        if labels is None:
            spec_label = specfile
        else:
            spec_label = labels[ff]

        if xrange is not None:
            goodent = np.where((specdat[tdose_wavecol] > xrange[0]) & (specdat[tdose_wavecol] < xrange[1]))[0]
            if goodent == []:
                if verbose: print(' - The chosen xrange is not covered by the input spectrum. Plotting full spectrum')
                goodent = np.arange(len(specdat[tdose_wavecol]))
        else:
            goodent = np.arange(len(specdat[tdose_wavecol]))

        if plotSNcurve:
            try:
                s2ndat = specdat['s2n'][goodent]
            except:
                s2ndat = specdat[tdose_fluxcol][goodent]/specdat[tdose_errcol][goodent]

            if smooth > 0:
                s2ndat = snf.gaussian_filter(s2ndat, smooth)

            if not plotratio:
                plt.plot(specdat[tdose_wavecol][goodent],s2ndat,color=spec_color,lw=lthick, label=spec_label)
                ylabel = 'S/N'
            else:
                plt.plot(specdat[tdose_wavecol][goodent],s2ndat/s2ndat,color=spec_color,lw=lthick, label=None)
                ylabel = 'S/N ratio'
            #plotname = plotname.replace('.pdf','_S2N.pdf')
        else:
            fillalpha = 0.30
            fluxdat   = specdat[tdose_fluxcol][goodent]
            errlow    = specdat[tdose_fluxcol][goodent]-specdat[tdose_errcol][goodent]
            errhigh   = specdat[tdose_fluxcol][goodent]+specdat[tdose_errcol][goodent]

            if smooth > 0:
                fluxdat = snf.gaussian_filter(fluxdat, smooth)
                errlow      = snf.gaussian_filter(errlow,  smooth)
                errhigh     = snf.gaussian_filter(errhigh, smooth)

            if smooth > 0:
                fluxdat = snf.gaussian_filter(fluxdat, smooth)

            if not plotratio:
                if shownoise:
                    plt.fill_between(specdat[tdose_wavecol][goodent],errlow,errhigh,
                                     alpha=fillalpha,color=spec_color)

                plt.plot(specdat[tdose_wavecol][goodent],fluxdat,
                         color=spec_color,lw=lthick, label=spec_label)
                ylabel = tdose_fluxcol
            else:
                plt.plot(specdat[tdose_wavecol][goodent],fluxdat/fluxdat,
                         color=spec_color,lw=lthick, label=None)
                ylabel = tdose_fluxcol+' ratio '
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if simsources is not None:
        sim_total = np.zeros(len(specdat[tdose_wavecol]))
        for sourcenumber in simsources:
            sourcedat = afits.open(simsourcefile)[1].data
            xpos       = sourcedat['xpos'][sourcenumber]
            ypos       = sourcedat['ypos'][sourcenumber]
            fluxscale  = sourcedat['fluxscale'][sourcenumber]
            sourcetype = sourcedat['sourcetype'][sourcenumber]
            spectype   = sourcedat['spectype'][sourcenumber]
            sourcecube = tbmc.gen_source_cube([ypos,xpos],fluxscale,sourcetype,spectype,cube_dim=sim_cube_dim,
                                              verbose=verbose,showsourceimgs=False)

            simspec    = np.sum( np.sum(sourcecube, axis=1), axis=1)
            sim_total  = sim_total + simspec
            if smooth > 0:
                simspec = snf.gaussian_filter(simspec, smooth)

            plt.plot(specdat[tdose_wavecol],simspec,'--',color='black',lw=lthick)

        plt.plot(specdat[tdose_wavecol],sim_total,'--',color='black',lw=lthick,
                 label='Sim. spectrum: \nsimsource='+str(simsources))

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if comparisonspecs is not None:
        for cc, comparisonspec in enumerate(comparisonspecs):
            compdat = afits.open(comparisonspec)[1].data

            if xrange is not None:
                goodent = np.where((compdat[comp_wavecol] > xrange[0]) & (compdat[comp_wavecol] < xrange[1]))[0]
                if goodent == []:
                    if verbose: print(' - The chosen xrange is not covered by the comparison spectrum. Plotting full spectrum')
                    goodent = np.arange(len(compdat[comp_wavecol]))
            else:
                goodent = np.arange(len(compdat[comp_wavecol]))

            if comp_colors is None:
                comp_color = None
            else:
                comp_color = comp_colors[cc]

            if comp_labels is None:
                comp_label = comparisonspec
            else:
                comp_label = comp_labels[cc]

            if plotSNcurve:
                s2ncompdat = compdat[comp_fluxcol][goodent]/compdat[comp_errcol][goodent]
                if smooth > 0:
                    s2ncompdat = snf.gaussian_filter(s2ncompdat, smooth)

                if not plotratio:
                    plt.plot(compdat[comp_wavecol][goodent],s2ncompdat,
                             color=comp_color,lw=lthick, label=comp_label)
                else:
                    plt.plot(compdat[comp_wavecol][goodent],s2ndat/s2ncompdat,
                             color=comp_color,lw=lthick, label=comp_label)

            else:
                fillalpha = 0.30
                fluxcompdat = compdat[comp_fluxcol][goodent]
                errlow      = compdat[comp_fluxcol][goodent]-compdat[comp_errcol][goodent]
                errhigh     = compdat[comp_fluxcol][goodent]+compdat[comp_errcol][goodent]

                if smooth > 0:
                    fluxcompdat = snf.gaussian_filter(fluxcompdat, smooth)
                    errlow      = snf.gaussian_filter(errlow,  smooth)
                    errhigh     = snf.gaussian_filter(errhigh, smooth)


                if not plotratio:
                    if shownoise:
                        plt.fill_between(compdat[comp_wavecol][goodent],errlow,errhigh,
                                         alpha=fillalpha,color=comp_color)

                    plt.plot(compdat[comp_wavecol][goodent],fluxcompdat,
                             color=comp_color,lw=lthick, label=comp_label)
                else:
                    plt.plot(compdat[comp_wavecol][goodent],fluxdat/fluxcompdat,
                             color=comp_color,lw=lthick, label=comp_label)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if skyspecs is not None:
        for ss, skyspec in enumerate(skyspecs):
            skydat = afits.open(skyspec)[1].data

            if xrange is not None:
                goodent = np.where((skydat[sky_wavecol] > xrange[0]) & (skydat[sky_wavecol] < xrange[1]))[0]
                if goodent == []:
                    if verbose: print(' - The chosen xrange is not covered by the sky spectrum. Plotting full spectrum')
                    goodent = np.arange(len(skydat[sky_wavecol]))
            else:
                goodent = np.arange(len(skydat[sky_wavecol]))

            if sky_colors is None:
                sky_color = None
            else:
                sky_color = sky_colors[ss]

            if sky_labels is None:
                sky_label = skyspec
            else:
                sky_label = sky_labels[ss]

            if plotSNcurve:
                s2nsky = skydat[sky_fluxcol][goodent]/skydat[sky_errcol][goodent]
                if smooth > 0:
                    s2nsky = snf.gaussian_filter(s2nsky, smooth)

                plt.plot(skydat[sky_wavecol][goodent],s2nsky,
                         color=sky_color,lw=lthick, label=sky_label)
            else:
                fillalpha = 0.30
                fluxsky   = skydat[sky_fluxcol][goodent]
                errlow    = skydat[sky_fluxcol][goodent]-skydat[sky_errcol][goodent]
                errhigh   = skydat[sky_fluxcol][goodent]+skydat[sky_errcol][goodent]

                if smooth > 0:
                    fluxsky = snf.gaussian_filter(fluxsky, smooth)
                    errlow  = snf.gaussian_filter(errlow,  smooth)
                    errhigh = snf.gaussian_filter(errhigh, smooth)

                if shownoise:
                    plt.fill_between(skydat[sky_wavecol][goodent],errlow,errhigh,
                                     alpha=fillalpha,color=sky_color)

                plt.plot(skydat[sky_wavecol][goodent],fluxsky,
                         color=sky_color,lw=lthick, label=sky_label)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if xrange is None:
        xvals = [4800,9300]
    else:
        xvals = xrange
    plt.plot(xvals,[0,0],'--k',lw=lthick)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    plt.xlabel('Wavelength [\AA]', fontsize=Fsize)

    if pubversion:
        if plotSNcurve:
            ylabel = 'Signal-to-Noise'
        else:
            ylabel = 'Flux ['+str(bunit)+']'

        if plotratio:
            ylabel = ylabel+' ratio'

    plt.ylabel(ylabel, fontsize=Fsize)

    if ylog:
        plt.yscale('log')

    if yrange is not None:
        plt.ylim(yrange)

    if xrange is not None:
        plt.xlim(xrange)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if showlinelists is not None:
        for sl, showlinelist in enumerate(showlinelists):
            ymin, ymax = plt.ylim()
            xmin, xmax = plt.xlim()
            for ww, wave in enumerate(showlinelist[:,0]):
                wave = float(wave)
                if (wave < xmax) & (wave > xmin):
                    plt.plot([wave,wave],[ymin,ymax],linestyle='--',color=linelistcolors[sl],lw=lthick)
                    plt.text(wave,ymin+1.03*np.abs([ymax-ymin]),showlinelist[:,1][ww],color=linelistcolors[sl], fontsize=Fsize-2., ha='center')
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if pubversion:
        leg = plt.legend(fancybox=True, loc='upper center',prop={'size':Fsize-2},ncol=4,numpoints=1,
                         bbox_to_anchor=(0.44, 1.27))  # add the legend
    else:
        leg = plt.legend(fancybox=True, loc='upper right',prop={'size':Fsize},ncol=1,numpoints=1,
                         bbox_to_anchor=(1.25, 1.03))  # add the legend


    leg.get_frame().set_alpha(0.7)

    if showspecs:
        if verbose: print('   Showing plot (not saving to file)')
        plt.show()
    else:
        if verbose: print('   Saving plot to',plotname)
        plt.savefig(plotname)

    plt.clf()
    plt.close('all')
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
def plot_histograms(datavectors,plotname='./tdose_cubehist.pdf',colors=None,labels=None,bins=None,
                    xrange=None,yrange=None,verbose=True,norm=True,ylog=True):
    """
    Plot histograms of a set of data vectors.

    --- INPUT ---
    datavectors     Set of data vectors to plot histograms of
    plotname        Name of plot to generate
    colors          Colors to use for histograms
    labels          Labels for the data vectors
    bins            Bins to use for histograms. Can be generated with np.arange(minval,maxval+binwidth,binwidth)
    xrange          Xrange of plot
    yrange          Yrange of plot
    verbose         Toggle verbosity
    norm            Noramlize the histograms
    ylog            Use a logarithmic y-axes when plotting

    """
    Ndat = len(datavectors)
    if verbose: print(' - Plotting histograms of N = '+str(Ndat)+' data vectors')

    if colors is None:
        colors = ['blue']*Ndat

    if labels is None:
        labels = ['data vector no. '+str(ii+1) for ii in np.arange(Ndat)]

    if bins is None:
        bins = np.arange(-100,102,2)

    fig = plt.figure(figsize=(10, 3))
    fig.subplots_adjust(wspace=0.1, hspace=0.1,left=0.08, right=0.81, bottom=0.1, top=0.95)
    Fsize  = 10
    lthick = 1
    plt.rc('text', usetex=True)
    plt.rc('font', family='serif',size=Fsize)
    plt.rc('xtick', labelsize=Fsize)
    plt.rc('ytick', labelsize=Fsize)
    plt.clf()
    plt.ioff()
    #plt.title(plotname.split('TDOSE 1D spectra'),fontsize=Fsize)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    for dd, datavec in enumerate(datavectors):
        hist = plt.hist(datavec[~np.isnan(datavec)],color=colors[dd],bins=bins,histtype="step",lw=lthick,
                        label=labels[dd],normed=norm)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if yrange is None:
        yvals = [1e-5,1e8]
    else:
        yvals = yrange
    plt.plot([0,0],yvals,'--k',lw=lthick)
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    plt.xlabel('', fontsize=Fsize)
    plt.ylabel('\#', fontsize=Fsize)

    if yrange is not None:
        plt.ylim(yrange)

    if xrange is not None:
        plt.xlim(xrange)

    if ylog:
        plt.yscale('log')

    leg = plt.legend(fancybox=True, loc='upper right',prop={'size':Fsize},ncol=1,numpoints=1,
                     bbox_to_anchor=(1.25, 1.03))  # add the legend
    leg.get_frame().set_alpha(0.7)

    if verbose: print('   Saving plot to',plotname)
    plt.savefig(plotname)
    plt.clf()
    plt.close('all')
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =