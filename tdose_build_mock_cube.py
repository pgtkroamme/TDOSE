# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
import numpy as np
import os
import sys
import pyfits
from scipy.stats import multivariate_normal
import matplotlib.pylab as plt
import pdb
import tdose_utilities as tu
import tdose_build_mock_cube as tbmc
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
def build_cube(sourcecatalog,cube_dim=[10,60,30],outputname='default',
               xpos_col='xpos',ypos_col='ypos',sourcetype_col='sourcetype',
               spectype_col='spectype',fluxscale_col='fluxscale',
               noisetype=None,noise_gauss_std=2.0,outputhdr=None,clobber=False,verbose=True):
    """
    Put together cube of dimensions [x,y,z] based on source catalog.

    --- INPUT ---
    sourcecatalog    Cource catalog to build cube for. Expects catlog with (at least) four columns
                     specifying the individual object's x and y position in the image, the source
                     type, the spectral type to used for the model and the flux scaling. The column
                     names of these indputs are set with xpos_col, ypos_col, sourcetype_col, spectype_col, flux_col
    cube_dim         Dimensions of cube to generate (z,y,x)
    outputname       Name of cube to generate; 'default' will append '_tdose_mock_cube' to source catalog name
    xpos_col         Source catalog column containing x position
    ypos_col         Source catalog column containing x position
    sourcetype_col   Source catalog column containing string specifying the source model to use for source:
                        gauss_sx_sy_a   A 2D gaussian source with sigma_x = sx, sigma_y = sy and angle = a.
                                        These values are used to generate the covariance matrix of the 2D gauss
                                        Means are given by [xpos,ypos]
    spectype_col     Source catalog column containing string specifying the spectrum model to use for source
                        line_az         Linear spectrum using expression a*z. Flux col is used to scale relation,
                                        i.e., the final spectrum will by a*z + f0_ij where f0_ij is the flux in pixel
                                        (i,j) resulting from the flux_col scaling of the 0th layer in the cube (x,y,0)
                        file_fielname   An actual spectrum stored in file with name 'filename' and columns
                                        'wave' and 'flux'
    fluxscale_col    Source catalog column containing flux scaling to use for source
    noisetype        To add noise to output cube, defune type of noise with this keyword.
                     For Gaussian noise use noise_gauss_std to define the std of the Guassian PDF
    noise_gauss_std  The standard deviation of the Gaussian PDF used to generate Gaussian noise on cube
    outputhdr        use a specific hdr including wcs strucutre etc provide it here.
    clobber          Clobber=True overwrites output fits file if it already exists
    verbose          Toggle verbosity

    --- EXAMPLE OF USE ---
    import tdose_build_mock_cube as tbmc
    sourcecat  = '/Users/kschmidt/work/TDOSE/mock_cube_sourcecat161213.fits'
    outputcube = tbmc.build_cube(sourcecat,cube_dim=[100,200,150],clobber=True,noisetype='gauss',noise_gauss_std=0.03)

    """
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print ' - Loading source catalog information to build mock data cube for'
    try:
        sourcedat = pyfits.open(sourcecatalog)[1].data
    except:
        sys.exit(' ---> Problems loading fits source catalog for mock cube')

    if outputname == 'default':
        outname = sourcecatalog.replace('.fits','_tdose_mock_cube.fits')
    else:
        outname = outputname
    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print ' - Generating sources and inserting them into mock cube'
    Nobjects   = len(sourcedat)
    outputcube = np.zeros(cube_dim)

    for oo in xrange(Nobjects):
        xpos       = sourcedat[xpos_col][oo]
        ypos       = sourcedat[ypos_col][oo]
        fluxscale  = sourcedat[fluxscale_col][oo]
        sourcetype = sourcedat[sourcetype_col][oo]
        spectype   = sourcedat[spectype_col][oo]
        sourcecube = tbmc.gen_source_cube([ypos,xpos],fluxscale,sourcetype,spectype,cube_dim=cube_dim,verbose=False)

        outputcube = outputcube + sourcecube

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if noisetype != None:
        if verbose: ' - Adding noise to mock cube'
        outputcube = tu.gen_noisy_cube(outputcube,type=noisetype,gauss_std=noise_gauss_std,verbose=verbose)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    if verbose: print ' - Saving generated mock cube to '+outname
    if outputhdr == None:
        if verbose: print ' - No header provided so will generate one '

        hducube = pyfits.PrimaryHDU(outputcube)       # creating default fits header

        # writing hdrkeys:    '---KEY--',                       '----------------MAX LENGTH COMMENT-------------'
        hducube.header.append(('BUNIT  '                      ,'(10**(-20)*erg/s/cm**2/Angstrom)**2'),end=True)
        hducube.header.append(('OBJECT '                      ,'mock_cube'),end=True)
        hducube.header.append(('CRPIX1 ',    201.043514357863 ,' Pixel coordinate of reference point'),end=True)
        hducube.header.append(('CRPIX2 ',    201.629151352493 ,' Pixel coordinate of reference point'),end=True)
        hducube.header.append(('CD1_1  ',-5.55555555555556E-05,' Coordinate transformation matrix element'),end=True)
        hducube.header.append(('CD1_2  ',                  0.,' Coordinate transformation matrix element'),end=True)
        hducube.header.append(('CD2_1  ',                  0. ,' Coordinate transformation matrix element'),end=True)
        hducube.header.append(('CD2_2  ',5.55555555555556E-05 ,' Coordinate transformation matrix element'),end=True)
        hducube.header.append(('CUNIT1 ','deg     '           ,' Units of coordinate increment and value'),end=True)
        hducube.header.append(('CUNIT2 ','deg     '           ,' Units of coordinate increment and value'),end=True)
        hducube.header.append(('CTYPE1 ','RA---TAN'           ,' Right ascension, gnomonic projection'),end=True)
        hducube.header.append(('CTYPE2 ','DEC--TAN'           ,' Declination, gnomonic projection'),end=True)
        hducube.header.append(('CSYER1 ',   1.50464086916E-05 ,' [deg] Systematic error in coordinate'),end=True)
        hducube.header.append(('CSYER2 ',   6.61226954775E-06 ,' [deg] Systematic error in coordinate'),end=True)
        hducube.header.append(('CRVAL1 ',          53.1078417 ,' '),end=True)
        hducube.header.append(('CRVAL2 ',         -27.8267356 ,' '),end=True)
        hducube.header.append(('CTYPE3 ','AWAV    '           ,' '),end=True)
        hducube.header.append(('CUNIT3 ','Angstrom'           ,' '),end=True)
        hducube.header.append(('CD3_3  ',                1.25 ,' '),end=True)
        hducube.header.append(('CRPIX3 ',                  1. ,' '),end=True)
        hducube.header.append(('CRVAL3 ',    4800             ,' '),end=True)
        hducube.header.append(('CD1_3  ',                  0. ,' '),end=True)
        hducube.header.append(('CD2_3  ',                  0. ,' '),end=True)
        hducube.header.append(('CD3_1  ',                  0. ,' '),end=True)
        hducube.header.append(('CD3_2  ',                  0. ,' '),end=True)
    else:
        hducube = outputhdr

    hdulist = pyfits.HDUList([hducube])       # turn header into to hdulist
    hdulist.writeto(outname,clobber=clobber)  # write fits file (clobber=True overwrites excisting file)

    # - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
    return outname
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
def gen_source_cube(position,scale,sourcetype,spectype,cube_dim=[10,60,30],verbose=True,showsourceimgs=False):
    """
    Generating a source to insert into model cube

    --- INPUT ---
    position      psotion of source in cube (spatial dimensions): [ydim,xdim]
    cube_dim      Dimensions of source cube to generate: [zdim,ydim,xdim]


    sourcetype    Source catalog column containing string specifying the source model to use for source:
                     gauss_sx_sy_a   A 2D gaussian source with sigma_x = sx, sigma_y = sy and angle = a.
                                     These values are used to generate the covariance matrix of the 2D gauss
                                     Means are given by [xpos,ypos]
    spectype      Source catalog column containing string specifying the spectrum model to use for source
                     line_az         Linear spectrum using expression a*z. Flux col is used to scale relation,
                                     i.e., the final spectrum will by a*z + f0_ij where f0_ij is the flux in pixel
                                     (i,j) resulting from the flux_col scaling of the 0th layer in the cube (x,y,0)
                     file_fielname   An actual spectrum stored in file with name 'filename' and columns
                                     'wave' and 'flux'


    --- EXAMPLE OF USE ---
    import tdose_build_mock_cube as tbmc
    sourcecube = tbmc.gen_source_cube([5,10],5,'gauss_8.2_15.1_45','linear_-0.05',cube_dim=[20,30,10],verbose=True,showsourceimgs=False)

    sourcecube = tbmc.gen_source_cube([30,70],20,'gauss_1.2_2.1_33','linear_-0.01',cube_dim=[100,130,50],verbose=True,showsourceimgs=True)

    """
    if verbose: print ' - Genrating source in spatial dimensions according to sourcetype='+sourcetype
    if sourcetype.startswith('gauss'):
        stdx            = float(sourcetype.split('_')[1])
        stdy            = float(sourcetype.split('_')[2])
        angle           = float(sourcetype.split('_')[3])
        cov             = tu.build_2D_cov_matrix(stdx,stdy,angle,verbose=verbose)
        source_centered = tbmc.gen_2Dgauss(cube_dim[1:],cov,scale,show2Dgauss=showsourceimgs,verbose=verbose)
    else:
        sys.exit(' ---> sourcetype="'+sourcetype+'" is not valid in call to mock_cube_sources.gen_source_cube() ')

    if verbose: print ' - Positioning source at requested pixel position (x,y) = ('+\
                      str(position[1])+','+str(position[0])+') in output cube'
    yroll = np.int(position[0]-cube_dim[1]/2.)
    xroll = np.int(position[1]-cube_dim[2]/2.)

    source_positioned = np.roll(np.roll(source_centered,yroll,axis=0),xroll,axis=1)

    if showsourceimgs:
        vmaxval = np.max(source_positioned)
        plt.imshow(source_positioned,interpolation='none',vmin=-vmaxval, vmax=vmaxval)
        plt.title('Positioned Source')
        plt.show()

    if yroll < 0:
        source_positioned[yroll:,:] = 0.0
    else:
        source_positioned[:yroll,:] = 0.0

    if xroll < 0:
        source_positioned[:,xroll:] = 0.0
    else:
        source_positioned[:,:xroll] = 0.0

    if showsourceimgs:
        plt.imshow(source_positioned,interpolation='none',vmin=-vmaxval, vmax=vmaxval)
        plt.title('Positioned Source with 0s inserted')
        plt.show()

    if verbose: print ' - Assemble flat spectrum cube with z-dimension '+str(cube_dim[0])
    sourcecube = np.stack([source_positioned]*cube_dim[0])

    if verbose: print ' - Genrate wavelength dimension by scaling source according to spectype='+spectype
    if spectype.startswith('linear'):
        slope           = float(spectype.split('_')[1])
        slopestack      = np.stack([slope*np.arange(cube_dim[0])]*cube_dim[2], axis=1)
        slopecube       = np.stack([slopestack]*cube_dim[1], axis=1)
        sourcecube_out  = sourcecube + sourcecube * slopecube
    elif spectype.startswith('flat'):
        sourcecube_out  = sourcecube
    else:
        sys.exit(' ---> spectype="'+spectype+'" is not valid in call to mock_cube_sources.gen_source_cub(); '
                                             'returning flat spectrum source ')

    if showsourceimgs:
        Nlayers = 4
        layers  = np.floor(np.linspace(0,cube_dim[0]-1,Nlayers)).astype(int)
        for layer in layers:
            plt.imshow(sourcecube_out[layer,:,:],interpolation='none',vmin=-vmaxval, vmax=vmaxval)
            plt.title('Cube layer (z-slice) '+str(layer))
            plt.show()


    return sourcecube_out
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
def gen_2Dgauss(size,cov,scale,verbose=True,show2Dgauss=False):
    """
    Generating a 2D gaussian with specified parameters

    --- INPUT ---
    size    The dimensions of the array to return. Expects [y-size,x-size].
            The 2D gauss will be positioned in the center of a (+/-x-size/2., +/-y-size/2) sized array
    cov     Covariance matrix of gaussian, i.e., variances and rotation
            Can be build with cov = tdose_utilities.build_2D_cov_matrix(stdx,stdy,angle)

    --- EXAMPLE OF USE ---
    import tdose_utilities as tu
    import tdose_build_mock_cube as tbmc
    covmatrix   = tu.build_2D_cov_matrix(4,1,5)
    gauss2Dimg  = tbmc.gen_2Dgauss([20,40],covmatrix,5,show2Dgauss=True)

    covmatrix   = tu.build_2D_cov_matrix(4,1,0)
    gauss2Dimg  = tbmc.gen_2Dgauss([20,40],covmatrix,25,show2Dgauss=True)

    """
    if verbose: print ' - Generating multivariate_normal object for generating 2D gauss'
    mvn = multivariate_normal([0, 0], cov)

    if verbose: print ' - Setting up grid to populate with 2D gauss PDF'
    x, y = np.mgrid[-np.round(size[0]/2.):np.round(size[0]/2.):1.0, -np.round(size[1]/2.):np.round(size[1]/2.):1.0]
    pos = np.zeros(x.shape + (2,))
    pos[:, :, 0] = x; pos[:, :, 1] = y
    gauss2D = mvn.pdf(pos)

    if verbose: print ' - Scaling 2D gaussian by a factor '+str(scale)
    gauss2D = gauss2D*scale

    if show2Dgauss:
        if verbose: print ' - Displaying resulting image of 2D gaussian'
        plt.imshow(gauss2D,interpolation='none')
        plt.title('Generated 2D Gauss')
        plt.show()

    return gauss2D
# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =
def gen_spectrum(size,mean,std,scale,verbose=True):
    """
    Generating a 2D gaussian with specified parameters

    --- INPUT ---

    --- EXAMPLE OF USE ---

    """

# = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = = =