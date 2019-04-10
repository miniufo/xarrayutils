from xgcm import Grid
import xarray as xr
import numpy as np
import pytest
from xarray.testing import assert_allclose
from xarrayutils.xgcm_utils import (
    _infer_gridtype,
    _get_name,
    _get_axis_dim,
    _check_dims,
    interp_all,
    calculate_rel_vorticity,
)


def datasets():
    xt = np.arange(4)
    xu = xt + 0.5
    yt = np.arange(4)
    yu = yt + 0.5

    # Need to add a tracer here to get the tracer dimsuffix
    tr = xr.DataArray(np.random.rand(4, 4), coords=[("xt", xt), ("yt", yt)])

    u_b = xr.DataArray(np.random.rand(4, 4), coords=[("xu", xu), ("yu", yu)])
    v_b = xr.DataArray(np.random.rand(4, 4), coords=[("xu", xu), ("yu", yu)])

    u_c = xr.DataArray(np.random.rand(4, 4), coords=[("xu", xu), ("yt", yt)])
    v_c = xr.DataArray(np.random.rand(4, 4), coords=[("xt", xt), ("yu", yu)])

    # northeast distance
    dx = 0.3
    dy = 2

    dx_ne = xr.DataArray(np.ones([4, 4]) * dx, coords=[("xu", xu), ("yu", yu)])
    dx_n = xr.DataArray(np.ones([4, 4]) * dx, coords=[("xt", xt), ("yu", yu)])
    dx_e = xr.DataArray(np.ones([4, 4]) * dx, coords=[("xu", xu), ("yt", yt)])
    dx_t = xr.DataArray(np.ones([4, 4]) * dx, coords=[("xt", xt), ("yt", yt)])

    dy_ne = xr.DataArray(np.ones([4, 4]) * dy, coords=[("xu", xu), ("yu", yu)])
    dy_n = xr.DataArray(np.ones([4, 4]) * dy, coords=[("xt", xt), ("yu", yu)])
    dy_e = xr.DataArray(np.ones([4, 4]) * dy, coords=[("xu", xu), ("yt", yt)])
    dy_t = xr.DataArray(np.ones([4, 4]) * dy, coords=[("xt", xt), ("yt", yt)])

    area_ne = dx_ne * dy_ne
    area_n = dx_n * dy_n
    area_e = dx_e * dy_e
    area_t = dx_t * dy_t

    def _add_metrics(obj):
        obj = obj.copy()
        for name, data in zip(
            [
                "dx_ne",
                "dx_n",
                "dx_e",
                "dx_t",
                "dy_ne",
                "dy_n",
                "dy_e",
                "dy_t",
                "area_ne",
                "area_n",
                "area_e",
                "area_t",
            ],
            [
                dx_ne,
                dx_n,
                dx_e,
                dx_t,
                dy_ne,
                dy_n,
                dy_e,
                dy_t,
                area_ne,
                area_n,
                area_e,
                area_t,
            ],
        ):
            obj.coords[name] = data
        return obj

    coords = {
        "X": {"center": "xt", "right": "xu"},
        "Y": {"center": "yt", "right": "yu"},
    }
    coords_outer = {
        "X": {"center": "xt", "outer": "xu"},
        "Y": {"center": "yt", "outer": "yu"},
    }

    ds_b = _add_metrics(xr.Dataset({"u": u_b, "v": v_b, "tracer": tr}))
    ds_c = _add_metrics(xr.Dataset({"u": u_c, "v": v_c, "tracer": tr}))

    ds_fail = _add_metrics(xr.Dataset({"u": u_b, "v": v_c, "tracer": tr}))
    ds_fail2 = _add_metrics(xr.Dataset({"u": u_b, "v": v_c, "tracer": tr}))

    return {
        "B": ds_b,
        "C": ds_c,
        "fail_gridtype": ds_fail,
        "fail_dimtype": ds_fail2,
        "coords": coords,
        "fail_coords": coords_outer,
    }


def test_get_name():
    datadict = datasets()
    ds = datadict["C"]
    assert _get_name(ds.xt) == "xt"


def test_get_axis_dim():
    datadict = datasets()
    ds = datadict["C"]
    coords = datadict["coords"]
    grid = Grid(ds, coords=coords)
    assert _get_axis_dim(grid, "X", ds.u)


def test_infer_gridtype():
    datadict = datasets()
    coords = datadict["coords"]
    ds_b = datadict["B"]
    grid_b = Grid(ds_b, coords=coords)

    ds_c = datadict["C"]
    grid_c = Grid(ds_c, coords=coords)

    # This should fail(unkown gridtype)
    ds_fail = datadict["fail_gridtype"]
    grid_fail = Grid(ds_fail, coords=coords)

    # This is not supported yet ('inner' and 'outer' dims)
    coords2 = datadict["fail_coords"]
    ds_fail2 = datadict["fail_dimtype"]
    grid_fail2 = Grid(ds_fail2, coords=coords2)

    assert _infer_gridtype(grid_b, ds_b.u, ds_b.v) == "B"
    assert _infer_gridtype(grid_c, ds_c.u, ds_c.v) == "C"
    with pytest.raises(RuntimeError, match=r"Gridtype not recognized *"):
        _infer_gridtype(grid_fail, ds_fail.u, ds_fail.v)
    with pytest.raises(RuntimeError):  # , match=r'`inner` or `outer` *'
        _infer_gridtype(grid_fail2, ds_fail2.u, ds_fail2.v)


def test_check_dims():
    datadict = datasets()
    ds = datadict["C"]
    assert _check_dims(ds.u, ds.u, "dummy")
    with pytest.raises(RuntimeError):
        _check_dims(ds.u, ds.v, "dummy")


def test_calculate_rel_vorticity():
    datadict = datasets()
    coords = datadict["coords"]
    ds_b = datadict["B"]
    grid_b = Grid(ds_b, coords=coords)

    ds_c = datadict["C"]
    grid_c = Grid(ds_c, coords=coords)

    test_b = (
        grid_b.diff(grid_b.interp(ds_b.v * ds_b.dy_ne, "Y"), "X")
        - grid_b.diff(grid_b.interp(ds_b.u * ds_b.dx_ne, "X"), "Y")
    ) / ds_b.area_t

    zeta_b = calculate_rel_vorticity(
        grid_b,
        ds_b.u,
        ds_b.v,
        ds_b.dx_ne,
        ds_b.dy_ne,
        ds_b.area_t,
        gridtype=None,
    )

    test_c = (
        grid_c.diff(ds_c.v * ds_c.dy_n, "X")
        - grid_c.diff(ds_c.u * ds_c.dx_e, "Y")
    ) / ds_c.area_ne

    zeta_c = calculate_rel_vorticity(
        grid_c,
        ds_c.u,
        ds_c.v,
        ds_c.dx_e,
        ds_c.dy_n,
        ds_c.area_ne,
        gridtype=None,
    )

    assert_allclose(test_b, zeta_b)
    assert_allclose(test_c, zeta_c)
    with pytest.raises(RuntimeError):
        zeta_c = calculate_rel_vorticity(
            grid_b,
            ds_c.u,
            ds_c.v,
            ds_c.dx_n,  # wrong coordinate
            ds_c.dy_n,
            ds_c.area_ne,
            gridtype=None,
        )


def test_interp_all():
    datadict = datasets()
    coords = datadict["coords"]
    ds_b = datadict["B"]
    grid_b = Grid(ds_b, coords=coords)

    ds_c = datadict["C"]
    grid_c = Grid(ds_c, coords=coords)

    for var in ["u", "v", "tracer"]:
        for ds, grid in zip([ds_b, ds_c], [grid_b, grid_c]):
            for target, control_dims in zip(
                ["center", "right"], [["xt", "yt"], ["xu", "yu"]]
            ):
                print(ds)
                print(grid)
                ds_interp = interp_all(grid, ds, target=target)
                assert set(ds_interp[var].dims) == set(control_dims)
