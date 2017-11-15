from datetime import datetime, timedelta
import pandas as pd
import os
import xarray as xr
import dask.array as dsa
import matplotlib.pyplot as plt
from . utils import concat_dim_da
from . weighted_operations import weighted_mean, weighted_sum


# def convert_boundary_flux(da,da_full,top=True):
#     dummy = xr.DataArray(dsa.zeros_like(da_full.data),
#                     coords = da_full.coords,
#                     dims = da_full.dims)
#     if top:
#         da.coords['st_ocean'] = da_full['st_ocean'][0]
#         dummy_cut = dummy.isel(st_ocean=slice(1,None))
#         out = xr.concat([da,dummy_cut],dim='st_ocean')
#     else:
#         da.coords['st_ocean'] = da_full['st_ocean'][-1]
#         dummy_cut = dummy.isel(st_ocean=slice(0,-1))
#         out = xr.concat([dummy_cut,da],dim='st_ocean')
#     return out


def cm26_convert_boundary_flux(da, da_full, top=True):
    dummy = xr.DataArray(dsa.zeros_like(da_full.data),
                         coords=da_full.coords,
                         dims=da_full.dims)
    if top:
        da.coords['st_ocean'] = da_full['st_ocean'][0]
        dummy_cut = dummy.isel(st_ocean=slice(1, None))
        out = xr.concat([da, dummy_cut], dim='st_ocean')
    else:
        da.coords['st_ocean'] = da_full['st_ocean'][-1]
        dummy_cut = dummy.isel(st_ocean=slice(0, -1))
        out = xr.concat([dummy_cut, da], dim='st_ocean')
    return out


def convert_units(ds, name, new_unit, factor):
    ds = ds.copy()
    ds[name] = ds[name]*factor
    ds[name].attrs['units'] = new_unit
    return ds


def shift_lon(ds, londim, shift=360, crit=0, smaller=True, sort=True):
    ds = ds.copy()
    if smaller:
        ds[londim].data[ds[londim] < crit] = \
            ds[londim].data[ds[londim] < crit] + shift
    else:
        ds[londim].data[ds[londim] > crit] = \
            ds[londim].data[ds[londim] > crit] + shift

    if sort:
        ds = ds.sortby(londim)
    return ds


def mask_tracer(ds, mask_ds, levels, name):
    out = []
    for ll in levels:
        out.append(ds.where(mask_ds <= ll))
    out = xr.concat(out, concat_dim_da(levels, name))
    return out


def metrics_ds(ds, xdim, ydim, zdim, area_w='area_t', volume_w='volume',
               compute_average=False, drop_control=False):
    """applies all needed metrics to a dataset and puts out a dict"""
    metrics = dict()
    if compute_average:
        metrics['x_section'] = weighted_mean(ds, ds[area_w],
                                             dim=[ydim], dimcheck=False)
        metrics['y_section'] = weighted_mean(ds, ds[area_w],
                                             dim=[xdim], dimcheck=False)
        metrics['profile'] = weighted_mean(ds, ds[area_w],
                                           dim=[xdim, ydim])
        metrics['timeseries'] = weighted_mean(ds, ds[volume_w],
                                              dim=[xdim, ydim, zdim])
        if drop_control:
            for ff in metrics.keys():
                metrics[ff] = metrics[ff].drop('ones')

    else:
        metrics['x_section'] = weighted_sum(ds, ds[area_w],
                                            dim=[ydim], dimcheck=False)
        metrics['y_section'] = weighted_sum(ds, ds[area_w],
                                            dim=[xdim], dimcheck=False)
        metrics['profile'] = weighted_sum(ds, ds[volume_w],
                                          dim=[xdim, ydim])
        metrics['timeseries'] = weighted_sum(ds, ds[volume_w],
                                             dim=[xdim, ydim, zdim])

        for ff in metrics.keys():
            if ff == 'timeseries':
                rename = 'integrated_volume'
            else:
                rename = 'integrated_area'
            metrics[ff] = metrics[ff].rename({'ones': rename})

    return metrics


def metrics_control_plots(metrics, xdim='xt_ocean', ydim='yt_ocean',
                          zdim='st_ocean', tdim='time'):

    n_data_var = len(metrics['timeseries'].data_vars)
    # n_time = len(metrics['timeseries'][tdim])

    plt.figure(figsize=[14, 5*n_data_var])
    # summed values
    for ii, ip in enumerate(metrics['timeseries'].data_vars):
        plt.subplot(n_data_var, 2, ii+1)
        data = (metrics['timeseries'])
        if 'omz_thresholds' in metrics['timeseries'].dims.keys():
            for oo in metrics['timeseries'].omz_thresholds:
                metrics['timeseries'][ip].sel(omz_thresholds=oo).plot()
        else:
            metrics['timeseries'].plot()
    # mean values (volume should be 1!)
    for ii, ip in enumerate(metrics['timeseries'].data_vars):
        plt.subplot(n_data_var, 2, ii+1+len(metrics['timeseries'].data_vars))
        data = (metrics['timeseries'] /
                metrics['timeseries']['integrated_volume'])
        if 'omz_thresholds' in metrics['timeseries'].dims.keys():
            for oo in metrics['timeseries'].omz_thresholds:
                data[ip].sel(omz_thresholds=oo).plot()
        else:
            data.plot()

    # ################ Sections ###############
    for ii, ip in enumerate(metrics['x_section'].data_vars):

        kwarg_dict = {'robust': True,
                      'yincrease': False}
        if 'omz_thresholds' in metrics['timeseries'].dims.keys():
            kwarg_dict['col'] = 'omz_thresholds'
        for sec in ['x', 'y']:
            plt.figure()
            metrics[sec+'_section'][{tdim: 0}][ip].plot(**kwarg_dict)

            plt.figure()
            l = (metrics[sec+'_section'] /
                 metrics[sec+'_section']['integrated_area'])
            l[{tdim: 0}][ip].plot(**kwarg_dict)

    # plt.imshow(ds_box[plot_var].isel(TIME=0,DEPTH_center=3))
    # plt.figure()
    # ds_box[plot_var].isel(TIME=0,DEPTH_center=3).plot()

    # y_section[plot_var].isel(TIME=0).plot()


def metrics_save(metrics, odir, fname, mf_save=False, **kwargs):
    for kk in metrics.keys():
        if mf_save:
            years, datasets = zip(*metrics[kk].groupby('time.year'))
            paths = [os.path.join(odir,
                '%04i_%s_%s.nc' %(y, fname, kk)) for y in years]
            xr.save_mfdataset(datasets, paths)
        else:
            metrics[kk].to_netcdf(os.path.join(odir, '%s_%s.nc' % (fname, kk)),
                                  **kwargs)


def metrics_load(metrics, odir, fname, **kwargs):
    for kk in metrics.keys():
        metrics[kk] = xr.open_dataset(os.path.join(odir,
                                                   '%s_%s.nc' % (fname, kk)),
                                      **kwargs)


def ds_add_track_dummy(ds, refvar):
    ones = ds[refvar].copy()
    ones = (ones*0)+1
    return ds.assign(ones=ones)


def metrics_wrapper():
    pass


def time_add_refyear(ds, timedim='time', refyear=2000):
    ds = ds.copy()
    # Fix the time axis (I added 1900 years, since otherwise the stupid panda
    # indexing does not work)
    ds[timedim].data = pd.to_datetime(datetime(refyear+1, 1, 1, 0, 0, 0) +
                                      ds[timedim].data*timedelta(1))
    ds.attrs['refyear_shift'] = refyear
    # Weirdly I have to add a year here or the timeline is messed up.

    return ds


def add_grid_geometry(ds, rho_dzt, gridspec_path,
                      rename_dict={'gridlon_t': 'xt_ocean',
                                   'gridlat_t': 'yt_ocean'}):

    g_ds = xr.open_dataset(gridspec_path).rename(rename_dict)
    ds = ds.assign_coords(area_t=g_ds['area_t'])

    # Infer vertical spacing (divided by constant rho=1035, since the model
    # uses the boussinesque appr.
    # [Griffies, Tutorial on budgets])
    ds = ds.assign_coords(dzt=(rho_dzt/1035.0))
    ds = ds.assign_coords(volume=ds['dzt']*ds['area_t'])
    ds = ds.assign_coords(rho_dzt=rho_dzt)
    return ds
